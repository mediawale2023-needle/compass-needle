"""
jobs/extract_prs_schemes.py — Build prs_schemes from global_parliamentary_questions.

Two modes:
  full      — process all subjects (first-time setup)
  incremental — process only subjects with id > last watermark

Rule-based extraction catches ~80% of Indian govt scheme names for free.
GPT-4o-mini only runs on ambiguous subjects, minimising token cost.

Usage:
  python -m jobs.extract_prs_schemes --full
  python -m jobs.extract_prs_schemes --incremental
  python -m jobs.extract_prs_schemes --stats
"""
from __future__ import annotations

import os
import re
import sys
import json
import time
import logging
from typing import Optional

from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from sansadx_backend.db import engine

logger = logging.getLogger("needle.extract_prs_schemes")

# ── Watermark key stored in a simple settings table ───────────────────────────
_WATERMARK_KEY = "extract_prs_schemes.last_pq_id"

# ── Rule-based patterns for Indian govt scheme names ─────────────────────────
_RULE_PATTERNS = [
    # Pradhan Mantri / PM prefix
    r"(?:Pradhan\s+Mantri|PM)[\s\-]+[A-Z][A-Za-z\s\-]+(?:Yojana|Scheme|Mission|Programme|Abhiyan|Nidhi|Samman|Kisan|Awas|Gram|Sadak|Jeevan|Ujjwala|Mudra|KISAN|PMAY|PMGSY|PMJAY)?",
    # Named schemes ending in Yojana/Mission/Abhiyan/Programme/Scheme
    r"[A-Z][A-Za-z\s]{3,40}(?:Yojana|Abhiyan|Mission|Programme|Scheme|Initiative|Fund|Authority|Board)",
    # Known acronyms
    r"\b(?:MGNREGS?|MGNREGA|PMJAY|PMKVY|PMGSY|PMAY|NREGA|JAM|DBT|NEP|AMRUT|JNNURM|RKVY|NHM|ICDS|MDM|SSA|RMSA|NLEP|NPCDCS)\b",
    # Ayushman / Jal / Swachh / Beti / Skill
    r"(?:Ayushman|Jal\s+Jeevan|Jal\s+Shakti|Swachh\s+Bharat|Beti\s+Bachao|Skill\s+India|Make\s+in\s+India|Digital\s+India|Start[- ]?up\s+India|Stand[- ]?Up\s+India|Atmanirbhar)[A-Za-z\s]*",
    # National + noun + Mission/Programme/Policy
    r"National\s+[A-Z][A-Za-z\s]{2,35}(?:Mission|Programme|Policy|Scheme|Authority|Fund|Initiative|Board)",
]
_COMPILED = [re.compile(p, re.IGNORECASE) for p in _RULE_PATTERNS]

# Common stop-words that indicate a subject is NOT a scheme name
_NON_SCHEME_WORDS = {
    "status", "implementation", "details", "information", "funds", "allocation",
    "utilisation", "utilization", "expenditure", "release", "pending", "progress",
    "report", "update", "review", "committee", "meeting", "statement",
}

GPT_BATCH_SIZE = 150   # subjects per GPT call
MIN_ANSWER_COUNT = 2   # minimum answers to include a scheme


# ── Watermark helpers ─────────────────────────────────────────────────────────

def _get_watermark() -> int:
    try:
        with engine.connect() as conn:
            r = conn.execute(text(
                "SELECT value FROM app_settings WHERE key = :k"
            ), {"k": _WATERMARK_KEY}).mappings().fetchone()
        return int(r["value"]) if r else 0
    except Exception:
        return 0


def _set_watermark(val: int):
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO app_settings (key, value)
                VALUES (:k, :v)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """), {"k": _WATERMARK_KEY, "v": str(val)})
    except Exception as e:
        logger.warning("Could not save watermark: %s", e)


def _ensure_settings_table():
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS app_settings (
                    key   VARCHAR(200) PRIMARY KEY,
                    value TEXT
                )
            """))
    except Exception as e:
        logger.warning("app_settings table create failed: %s", e)


# ── Rule-based extraction ─────────────────────────────────────────────────────

def _extract_by_rules(subject: str) -> list[str]:
    """Extract scheme name candidates from a subject using regex patterns."""
    found = []
    for pat in _COMPILED:
        for m in pat.finditer(subject):
            candidate = m.group(0).strip()
            # Reject if too short or pure stop-words
            words = candidate.lower().split()
            if len(candidate) < 5 or all(w in _NON_SCHEME_WORDS for w in words):
                continue
            found.append(candidate)
    return found


# ── GPT extraction for ambiguous subjects ────────────────────────────────────

def _gpt_extract_batch(subjects: list[str]) -> list[dict]:
    """
    Send a batch of subjects to GPT-4o-mini.
    Returns list of {name, full_name, ministry} dicts.
    """
    try:
        import openai
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    except Exception as e:
        logger.warning("OpenAI not available: %s", e)
        return []

    numbered = "\n".join(f"{i+1}. {s}" for i, s in enumerate(subjects))
    prompt = (
        "These are Indian parliamentary question subjects. "
        "Extract every government scheme name mentioned. "
        "Return JSON array: [{\"name\": \"<short canonical name>\", "
        "\"full_name\": \"<full official name or same as name>\", "
        "\"ministry\": \"<ministry if inferable else null>\"}]. "
        "Skip subjects with no scheme. Return [] if none found.\n\n"
        f"Subjects:\n{numbered}"
    )
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Extract scheme names only. Return valid JSON array."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_tokens=800,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or "{}"
        data = json.loads(raw)
        if isinstance(data, list):
            return data
        # GPT sometimes wraps in {"schemes": [...]}
        for v in data.values():
            if isinstance(v, list):
                return v
        return []
    except Exception as e:
        logger.warning("GPT batch extraction failed: %s", e)
        return []


# ── Normalisation & dedup ─────────────────────────────────────────────────────

def _normalise(name: str) -> str:
    """Canonical form: strip leading articles, normalise spaces, title-case."""
    name = re.sub(r"\s+", " ", name).strip()
    # Remove trailing punctuation
    name = name.rstrip(".,;:-")
    return name


def _canonical_key(name: str) -> str:
    """Lowercase, no punctuation, no spaces — for dedup comparison."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


# ── DB upsert ────────────────────────────────────────────────────────────────

def _upsert_scheme(name: str, full_name: str, ministry: Optional[str],
                   alias: Optional[str], date_seen: Optional[str]):
    """Insert or update a scheme in prs_schemes."""
    canonical = _normalise(name)
    if not canonical or len(canonical) < 4:
        return

    try:
        with engine.begin() as conn:
            # Check if already exists (by canonical key similarity)
            existing = conn.execute(text("""
                SELECT id, name, aliases FROM prs_schemes
                WHERE LOWER(REGEXP_REPLACE(name, '[^a-zA-Z0-9]', '', 'g'))
                    = LOWER(REGEXP_REPLACE(:cname, '[^a-zA-Z0-9]', '', 'g'))
            """), {"cname": canonical}).mappings().fetchone()

            if existing:
                # Update last_seen, add alias if new
                new_aliases = list(existing["aliases"] or [])
                if alias and alias not in new_aliases and alias != canonical:
                    new_aliases.append(alias)
                conn.execute(text("""
                    UPDATE prs_schemes
                    SET last_seen = GREATEST(last_seen, CAST(:d AS DATE)),
                        aliases   = :aliases,
                        updated_at = NOW()
                    WHERE id = :id
                """), {
                    "d":       date_seen or "2024-01-01",
                    "aliases": new_aliases,
                    "id":      existing["id"],
                })
            else:
                aliases_arr = [alias] if alias and alias != canonical else []
                conn.execute(text("""
                    INSERT INTO prs_schemes
                        (name, full_name, ministry, aliases, first_seen, last_seen)
                    VALUES
                        (:name, :full_name, :ministry, :aliases,
                         CAST(:first AS DATE), CAST(:last AS DATE))
                    ON CONFLICT (name) DO UPDATE SET
                        last_seen  = GREATEST(prs_schemes.last_seen, CAST(:last AS DATE)),
                        updated_at = NOW()
                """), {
                    "name":      canonical,
                    "full_name": _normalise(full_name) if full_name else canonical,
                    "ministry":  ministry,
                    "aliases":   aliases_arr,
                    "first":     date_seen or "2024-01-01",
                    "last":      date_seen or "2024-01-01",
                })
    except Exception as e:
        logger.debug("Upsert scheme '%s' failed: %s", canonical, e)


# ── Answer count refresh ──────────────────────────────────────────────────────

def refresh_answer_counts():
    """Update prs_schemes.answer_count based on current global_parliamentary_questions."""
    logger.info("Refreshing answer counts for all schemes...")
    try:
        with engine.connect() as conn:
            schemes = conn.execute(text(
                "SELECT id, name, aliases FROM prs_schemes"
            )).mappings().all()

        for s in schemes:
            aliases = list(s["aliases"] or []) + [s["name"]]
            # Build ILIKE conditions for all aliases
            conditions = " OR ".join(
                f"(subject ILIKE :a{i} OR answer_text ILIKE :a{i})"
                for i in range(len(aliases))
            )
            params = {f"a{i}": f"%{a}%" for i, a in enumerate(aliases)}
            sql = f"""
                SELECT COUNT(*) AS cnt
                FROM global_parliamentary_questions
                WHERE answer_text IS NOT NULL AND answer_text != ''
                  AND ({conditions})
            """
            with engine.connect() as conn:
                r = conn.execute(text(sql), params).mappings().fetchone()
                count = int(r["cnt"]) if r else 0

            with engine.begin() as conn:
                conn.execute(text(
                    "UPDATE prs_schemes SET answer_count = :c WHERE id = :id"
                ), {"c": count, "id": s["id"]})

        logger.info("Answer counts refreshed for %d schemes", len(schemes))
    except Exception as e:
        logger.error("refresh_answer_counts failed: %s", e)


# ── Main extraction ───────────────────────────────────────────────────────────

def run_extraction(full: bool = False, _progress: dict = None) -> dict:
    """
    Extract schemes from global_parliamentary_questions subjects.

    full=True  → process all records (first-time setup)
    full=False → process only records with id > last watermark (incremental)
    _progress  → mutable dict updated in-place for live polling (done/total/label)
    """
    def _upd(done, total, label):
        if _progress is not None:
            _progress["done"] = done
            _progress["total"] = total
            _progress["label"] = label

    _ensure_settings_table()

    watermark = 0 if full else _get_watermark()
    logger.info("Starting extraction (full=%s, watermark=%d)", full, watermark)

    _upd(0, 0, "loading subjects…")

    # Fetch subjects from DB
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT id, subject, ministry, date_asked
            FROM global_parliamentary_questions
            WHERE id > :w
              AND subject IS NOT NULL AND subject != ''
            ORDER BY id
        """), {"w": watermark}).mappings().all()

    if not rows:
        logger.info("No new subjects to process.")
        return {"processed": 0, "schemes_upserted": 0}

    total_rows = len(rows)
    logger.info("Processing %d subjects", total_rows)
    max_id = max(r["id"] for r in rows)

    _upd(0, total_rows, "subjects (rule pass)")

    rule_matched = 0
    gpt_subjects = []
    gpt_meta: dict[str, dict] = {}  # subject → {ministry, date}
    schemes_upserted = 0

    for idx, row in enumerate(rows):
        subject  = row["subject"] or ""
        ministry = row["ministry"] or None
        date_str = row["date_asked"].isoformat() if row["date_asked"] else None

        found = _extract_by_rules(subject)
        if found:
            rule_matched += 1
            for scheme_name in found:
                _upsert_scheme(scheme_name, scheme_name, ministry, None, date_str)
                schemes_upserted += 1
        else:
            gpt_subjects.append(subject)
            gpt_meta[subject] = {"ministry": ministry, "date": date_str}

        if idx % 200 == 0:
            _upd(idx, total_rows, "subjects (rule pass)")

    _upd(total_rows, total_rows, "subjects (rule pass)")

    # GPT pass for ambiguous subjects
    gpt_calls = 0
    if gpt_subjects:
        total_batches = (len(gpt_subjects) + GPT_BATCH_SIZE - 1) // GPT_BATCH_SIZE
        _upd(0, total_batches, "GPT batches")
        logger.info("%d subjects going to GPT (%d caught by rules)",
                    len(gpt_subjects), rule_matched)
        for i in range(0, len(gpt_subjects), GPT_BATCH_SIZE):
            batch = gpt_subjects[i: i + GPT_BATCH_SIZE]
            extracted = _gpt_extract_batch(batch)
            for item in extracted:
                name = (item.get("name") or "").strip()
                if not name or len(name) < 4:
                    continue
                # Find the most relevant ministry from the batch meta
                ministry = item.get("ministry") or None
                if not ministry:
                    for subj in batch:
                        if name.lower()[:8] in subj.lower():
                            ministry = gpt_meta[subj]["ministry"]
                            break
                date_str = None
                for subj in batch:
                    if name.lower()[:8] in subj.lower():
                        date_str = gpt_meta[subj]["date"]
                        break
                _upsert_scheme(name, item.get("full_name") or name, ministry, None, date_str)
                schemes_upserted += 1
            gpt_calls += 1
            _upd(gpt_calls, total_batches, "GPT batches")
            if i + GPT_BATCH_SIZE < len(gpt_subjects):
                time.sleep(0.3)

    # Update watermark
    _set_watermark(max_id)

    # Refresh answer counts after extraction
    _upd(0, 1, "refreshing answer counts")
    refresh_answer_counts()
    _upd(1, 1, "refreshing answer counts")

    summary = {
        "subjects_processed": len(rows),
        "rule_matched":        rule_matched,
        "gpt_subjects":        len(gpt_subjects),
        "gpt_calls":           gpt_calls,
        "schemes_upserted":    schemes_upserted,
        "new_watermark":       max_id,
    }
    logger.info("Extraction done: %s", summary)
    return summary


def get_stats() -> dict:
    """Quick stats on current prs_schemes table."""
    try:
        with engine.connect() as conn:
            r = conn.execute(text("""
                SELECT
                    COUNT(*)                                  AS total_schemes,
                    COUNT(*) FILTER (WHERE answer_count >= 2) AS schemes_with_answers,
                    COUNT(DISTINCT ministry)                  AS ministries,
                    SUM(answer_count)                         AS total_answers
                FROM prs_schemes
            """)).mappings().fetchone()
        return dict(r) if r else {}
    except Exception as e:
        return {"error": str(e)}


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    ap = argparse.ArgumentParser(description="Extract PRS schemes from parliamentary questions")
    ap.add_argument("--full", action="store_true", help="Process all subjects (first-time setup)")
    ap.add_argument("--incremental", action="store_true", help="Process only new subjects")
    ap.add_argument("--stats", action="store_true", help="Show current stats")
    ap.add_argument("--refresh-counts", action="store_true", help="Refresh answer counts only")
    args = ap.parse_args()

    if args.stats:
        print(json.dumps(get_stats(), indent=2, default=str))
    elif args.refresh_counts:
        refresh_answer_counts()
    elif args.full or args.incremental:
        result = run_extraction(full=args.full)
        print(json.dumps(result, indent=2, default=str))
    else:
        ap.print_help()
