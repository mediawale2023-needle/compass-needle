"""
jobs/classify_pq_topics.py — Classify global_parliamentary_questions into a fixed 12-topic taxonomy.

Fixed taxonomy (applied uniformly across all ministries):
  Infrastructure & Projects     Budget & Finance          Welfare & Beneficiaries
  Implementation & Progress     Challenges & Delays       Policy & Legislation
  Data & Statistics             Appointments & Administration
  International & Bilateral     Environment & Sustainability
  Research & Technology         Legal & Regulatory        Other

GPT-4o-mini assigns one label per question subject. Subject only — not answer text.
Batch size: 100 subjects per GPT call.
Incremental: only processes rows where topic IS NULL.

Usage:
  python -m jobs.classify_pq_topics               # classify up to 2000 unclassified rows
  python -m jobs.classify_pq_topics --limit 500   # smaller run
  python -m jobs.classify_pq_topics --stats        # print coverage stats

Programmatic:
  from jobs.classify_pq_topics import run_classification, get_stats
"""

from __future__ import annotations

import os
import sys
import json
import time
import logging
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import text
from sansadx_backend.db import engine

logger = logging.getLogger("needle.classify_pq_topics")

# ── Taxonomy ──────────────────────────────────────────────────────────────────

TOPICS = [
    "Infrastructure & Projects",
    "Budget & Finance",
    "Welfare & Beneficiaries",
    "Implementation & Progress",
    "Challenges & Delays",
    "Policy & Legislation",
    "Data & Statistics",
    "Appointments & Administration",
    "International & Bilateral",
    "Environment & Sustainability",
    "Research & Technology",
    "Legal & Regulatory",
    "Other",
]

TOPIC_SET = set(TOPICS)

SYSTEM_PROMPT = f"""You are a parliamentary classification engine for India.
Your job is to assign ONE topic label from this fixed list to each parliamentary question subject.

TOPICS:
{chr(10).join(f'  - {t}' for t in TOPICS)}

Rules:
- Output ONLY valid JSON: an array of objects with "id" and "topic".
- Use EXACTLY the topic label as written above.
- Assign "Other" only if no topic fits clearly.
- Classify by subject text only — do not speculate beyond the subject.
- One label per question. No commentary."""

BATCH_SIZE = 100
DEFAULT_LIMIT = 2000
INTER_BATCH_DELAY = 1.0   # seconds between batches


# ── GPT call ─────────────────────────────────────────────────────────────────

def _classify_batch(rows: list[dict]) -> dict[int, str]:
    """
    Send a batch of {id, subject, ministry} rows to GPT-4o-mini.
    Returns {id: topic} mapping. Falls back to "Other" on failure.
    """
    try:
        import openai
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=60.0)
    except Exception as e:
        logger.error("OpenAI init failed: %s", e)
        return {r["id"]: "Other" for r in rows}

    user_lines = []
    for r in rows:
        ministry_hint = f" [Ministry: {r['ministry']}]" if r.get("ministry") else ""
        user_lines.append(f'{{"id": {r["id"]}, "subject": {json.dumps(r["subject"] or "")}' +
                          (f', "ministry": {json.dumps(r["ministry"])}' if r.get("ministry") else "") +
                          "}")

    user_content = "Classify each subject:\n" + "\n".join(user_lines)

    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                temperature=0,
                max_tokens=len(rows) * 25 + 100,
                response_format={"type": "json_object"},
            )
            raw = resp.choices[0].message.content or "{}"
            parsed = json.loads(raw)

            # GPT may return {"results": [...]} or directly [...]
            items = parsed if isinstance(parsed, list) else parsed.get("results", parsed.get("classifications", []))
            if not isinstance(items, list):
                # Try to find any list value in the response
                for v in parsed.values():
                    if isinstance(v, list):
                        items = v
                        break

            result: dict[int, str] = {}
            for item in items:
                row_id = item.get("id")
                topic  = item.get("topic", "Other")
                if row_id is not None and topic in TOPIC_SET:
                    result[int(row_id)] = topic
                elif row_id is not None:
                    result[int(row_id)] = "Other"

            # Fill any missing IDs
            for r in rows:
                if r["id"] not in result:
                    result[r["id"]] = "Other"

            return result

        except Exception as e:
            logger.warning("GPT batch attempt %d failed: %s", attempt + 1, e)
            if attempt < 2:
                time.sleep(2 ** attempt * 2)

    return {r["id"]: "Other" for r in rows}


# ── DB helpers ────────────────────────────────────────────────────────────────

def _fetch_unclassified(limit: int) -> list[dict]:
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT id, subject, ministry
                FROM global_parliamentary_questions
                WHERE topic IS NULL AND subject IS NOT NULL AND subject != ''
                ORDER BY id
                LIMIT :lim
            """), {"lim": limit}).mappings().all()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error("_fetch_unclassified failed: %s", e)
        return []


def _write_topics(mapping: dict[int, str]):
    if not mapping:
        return
    try:
        with engine.begin() as conn:
            for row_id, topic in mapping.items():
                conn.execute(text(
                    "UPDATE global_parliamentary_questions SET topic = :topic WHERE id = :id"
                ), {"topic": topic, "id": row_id})
    except Exception as e:
        logger.error("_write_topics failed: %s", e)


# ── Public API ────────────────────────────────────────────────────────────────

def run_classification(limit: int = DEFAULT_LIMIT) -> dict:
    """
    Classify up to `limit` unclassified rows. Incremental — safe to call repeatedly.
    Returns summary dict: {processed, batches, elapsed_s}
    """
    rows = _fetch_unclassified(limit)
    if not rows:
        logger.info("classify_pq_topics: nothing to classify")
        return {"processed": 0, "batches": 0, "elapsed_s": 0}

    logger.info("classify_pq_topics: classifying %d subjects", len(rows))
    t0 = time.time()
    total_processed = 0
    batches = 0

    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i: i + BATCH_SIZE]
        mapping = _classify_batch(batch)
        _write_topics(mapping)
        total_processed += len(batch)
        batches += 1
        logger.info("classify_pq_topics: batch %d done (%d/%d)", batches, total_processed, len(rows))
        if i + BATCH_SIZE < len(rows):
            time.sleep(INTER_BATCH_DELAY)

    elapsed = round(time.time() - t0, 1)
    logger.info("classify_pq_topics: done — %d rows in %ds", total_processed, elapsed)
    return {"processed": total_processed, "batches": batches, "elapsed_s": elapsed}


def get_stats() -> dict:
    """Return classification coverage stats."""
    try:
        with engine.connect() as conn:
            total_row = conn.execute(text(
                "SELECT COUNT(*) AS cnt FROM global_parliamentary_questions "
                "WHERE subject IS NOT NULL AND subject != ''"
            )).mappings().fetchone()
            classified_row = conn.execute(text(
                "SELECT COUNT(*) AS cnt FROM global_parliamentary_questions WHERE topic IS NOT NULL"
            )).mappings().fetchone()
            topic_rows = conn.execute(text(
                "SELECT topic, COUNT(*) AS cnt FROM global_parliamentary_questions "
                "WHERE topic IS NOT NULL GROUP BY topic ORDER BY cnt DESC"
            )).mappings().all()

        total      = int((total_row or {}).get("cnt", 0))
        classified = int((classified_row or {}).get("cnt", 0))
        return {
            "total":       total,
            "classified":  classified,
            "unclassified": total - classified,
            "pct":         round(classified / total * 100, 1) if total else 0,
            "by_topic":    [{"topic": r["topic"], "count": int(r["cnt"])} for r in topic_rows],
        }
    except Exception as e:
        logger.error("get_stats failed: %s", e)
        return {"total": 0, "classified": 0, "unclassified": 0, "pct": 0, "by_topic": []}


def get_ministry_topic_counts(ministry: str, state: Optional[str] = None) -> list[dict]:
    """
    For a given ministry, return per-topic counts:
      total  — all classified PQs for this ministry
      state  — PQs where answer_text mentions this state (if state provided)
    """
    try:
        with engine.connect() as conn:
            params: dict = {"ministry": ministry}
            state_col = ""
            state_join = ""
            if state:
                params["state"] = f"%{state}%"
                state_col = """, COUNT(*) FILTER (
                    WHERE answer_text IS NOT NULL AND answer_text ILIKE :state
                ) AS state_count"""

            rows = conn.execute(text(f"""
                SELECT topic, COUNT(*) AS total_count{state_col}
                FROM global_parliamentary_questions
                WHERE topic IS NOT NULL
                  AND answer_text IS NOT NULL AND answer_text != ''
                  AND LOWER(TRIM(ministry)) = LOWER(TRIM(:ministry))
                GROUP BY topic
                ORDER BY total_count DESC
            """), params).mappings().all()  # nosec B608

        return [
            {
                "topic":       r["topic"],
                "total_count": int(r["total_count"]),
                "state_count": int(r.get("state_count") or 0) if state else None,
            }
            for r in rows
        ]
    except Exception as e:
        logger.error("get_ministry_topic_counts failed: %s", e)
        return []


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Classify PQ subjects into 12-topic taxonomy")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--stats", action="store_true")
    args = parser.parse_args()

    if args.stats:
        s = get_stats()
        print(f"Total:      {s['total']}")
        print(f"Classified: {s['classified']} ({s['pct']}%)")
        print(f"Remaining:  {s['unclassified']}")
        for t in s["by_topic"]:
            print(f"  {t['topic']:<35} {t['count']}")
    else:
        result = run_classification(limit=args.limit)
        print(f"Done: {result['processed']} rows in {result['elapsed_s']}s ({result['batches']} batches)")
