"""
modules/schemes_api.py — Scheme Intelligence Engine.

Three public functions consumed by api_router.py:
  get_ministry_overview()          → all ministries with scheme + answer counts
  get_ministry_schemes(ministry)   → schemes under one ministry
  get_scheme_intelligence(name)    → AI-structured 6-section brief (cached)

Staleness is managed by mark_stale_schemes(pq_ids), called from the
answer fetcher and global crawler after each batch.
Background regeneration fires automatically when a stale brief is requested.
"""
from __future__ import annotations

import os
import json
import time
import logging
import threading
from typing import Optional

from sqlalchemy import text

from sansadx_backend.db import engine

logger = logging.getLogger("needle.schemes_api")

# ── In-memory runtime cache (avoids repeated DB reads for hot schemes) ─────
_runtime_cache: dict[str, dict] = {}
_RUNTIME_TTL = 3600  # 1 hour


def _runtime_get(key: str) -> Optional[dict]:
    entry = _runtime_cache.get(key)
    if entry and (time.time() - entry["ts"]) < _RUNTIME_TTL:
        return entry["data"]
    return None


def _runtime_set(key: str, data):
    _runtime_cache[key] = {"data": data, "ts": time.time()}


# ── Ministry overview ─────────────────────────────────────────────────────────

def get_ministry_overview() -> list[dict]:
    """
    Returns all ministries that have schemes in prs_schemes,
    enriched with PQ answer counts from global_parliamentary_questions.
    """
    cached = _runtime_get("ministry_overview")
    if cached is not None:
        return cached

    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT
                    ps.ministry,
                    COUNT(ps.id)                          AS scheme_count,
                    SUM(ps.answer_count)                  AS total_answers,
                    MAX(ps.last_seen)                     AS latest_activity,
                    COUNT(ps.id) FILTER (WHERE ps.answer_count >= 2) AS schemes_with_data
                FROM prs_schemes ps
                WHERE ps.ministry IS NOT NULL AND ps.ministry != ''
                  AND ps.answer_count >= 1
                GROUP BY ps.ministry
                ORDER BY total_answers DESC NULLS LAST, scheme_count DESC
            """)).mappings().all()

        result = [
            {
                "ministry":          r["ministry"],
                "scheme_count":      int(r["scheme_count"]),
                "total_answers":     int(r["total_answers"] or 0),
                "schemes_with_data": int(r["schemes_with_data"]),
                "latest_activity":   r["latest_activity"].isoformat() if r["latest_activity"] else None,
            }
            for r in rows
        ]
        _runtime_set("ministry_overview", result)
        return result
    except Exception as e:
        logger.error("get_ministry_overview failed: %s", e)
        return []


# ── Ministry schemes ──────────────────────────────────────────────────────────

def get_ministry_schemes(ministry: str) -> list[dict]:
    """Returns all schemes for a given ministry, ordered by answer count."""
    cache_key = f"ministry_schemes:{ministry.lower()}"
    cached = _runtime_get(cache_key)
    if cached is not None:
        return cached

    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT
                    id, name, full_name, ministry,
                    aliases, answer_count, first_seen, last_seen
                FROM prs_schemes
                WHERE LOWER(ministry) = LOWER(:m)
                  AND answer_count >= 2
                ORDER BY answer_count DESC, name
            """), {"m": ministry}).mappings().all()

        scheme_names = [r["name"] for r in rows]
        cached_names: set[str] = set()
        stale_names: set[str] = set()
        if scheme_names:
            with engine.connect() as conn:
                intel_rows = conn.execute(text("""
                    SELECT scheme_name, is_stale
                    FROM scheme_intelligence_cache
                    WHERE scheme_name = ANY(:names)
                """), {"names": scheme_names}).mappings().all()
            for ir in intel_rows:
                if ir["is_stale"]:
                    stale_names.add(ir["scheme_name"])
                else:
                    cached_names.add(ir["scheme_name"])

        result = []
        for r in rows:
            name = r["name"]
            if name in cached_names:
                intel_status = "ready"
            elif name in stale_names:
                intel_status = "stale"
            else:
                intel_status = "pending"

            result.append({
                "id":            r["id"],
                "name":          r["name"],
                "full_name":     r["full_name"] or r["name"],
                "ministry":      r["ministry"],
                "answer_count":  r["answer_count"],
                "first_seen":    r["first_seen"].isoformat() if r["first_seen"] else None,
                "last_seen":     r["last_seen"].isoformat() if r["last_seen"] else None,
                "intel_status":  intel_status,
            })

        _runtime_set(cache_key, result)
        return result
    except Exception as e:
        logger.error("get_ministry_schemes(%s) failed: %s", ministry, e)
        return []


# ── Scheme intelligence (AI brief) ───────────────────────────────────────────

def _fetch_scheme_answers(scheme_name: str, aliases: list[str], ministry: str) -> list[dict]:
    """
    Two-stage filter: ministry first, then scheme ILIKE on subject + answer_text.
    Selects 5 most-recent + 5 longest answers, deduped. Max 10, each 700 chars.
    """
    all_aliases = list({scheme_name} | set(aliases or []))
    ilike_parts = " OR ".join(
        f"(subject ILIKE :a{i} OR answer_text ILIKE :a{i})"
        for i in range(len(all_aliases))
    )
    params: dict = {f"a{i}": f"%{a}%" for i, a in enumerate(all_aliases)}

    ministry_filter = ""
    if ministry:
        keyword = ministry.lower().split("ministry of")[-1].strip()[:25]
        ministry_filter = "AND LOWER(ministry) LIKE :mf"
        params["mf"] = f"%{keyword}%"

    try:
        with engine.connect() as conn:
            recent = conn.execute(text(f"""
                SELECT answer_text, subject, date_asked, question_type, session_name
                FROM global_parliamentary_questions
                WHERE answer_text IS NOT NULL AND answer_text != ''
                  {ministry_filter}
                  AND ({ilike_parts})
                ORDER BY date_asked DESC NULLS LAST
                LIMIT 5
            """), params).mappings().all()

            longest = conn.execute(text(f"""
                SELECT answer_text, subject, date_asked, question_type, session_name
                FROM global_parliamentary_questions
                WHERE answer_text IS NOT NULL AND answer_text != ''
                  {ministry_filter}
                  AND ({ilike_parts})
                ORDER BY LENGTH(answer_text) DESC
                LIMIT 5
            """), params).mappings().all()

        seen: set[str] = set()
        combined = []
        for r in list(recent) + list(longest):
            fp = (r["answer_text"] or "")[:120]
            if fp not in seen:
                seen.add(fp)
                combined.append({
                    "answer_text":   (r["answer_text"] or "")[:700],
                    "subject":       r["subject"],
                    "date_asked":    r["date_asked"].isoformat() if r["date_asked"] else None,
                    "question_type": r["question_type"],
                    "session_name":  r["session_name"],
                })
        return combined[:10]
    except Exception as e:
        logger.error("_fetch_scheme_answers failed: %s", e)
        return []


def _call_gpt(scheme_name: str, ministry: str, answers: list[dict]) -> dict:
    """Call GPT-4o-mini to produce a 6-section structured intelligence brief."""
    try:
        import openai
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    except Exception as e:
        logger.error("OpenAI init failed: %s", e)
        return {}

    answer_block = ""
    for i, a in enumerate(answers, 1):
        date_label = a.get("date_asked") or "unknown date"
        qtype = (a.get("question_type") or "").upper()
        answer_block += (
            f"[{i} | {qtype} | {date_label}]\n"
            f"Subject: {a.get('subject','')}\n"
            f"{a.get('answer_text','')}\n\n"
        )

    system = (
        "You are a parliamentary intelligence analyst for India. "
        "Extract ONLY facts explicitly stated in the ministry answers. "
        "No inference, no external knowledge. Return valid JSON."
    )

    user = f"""Scheme: {scheme_name}
Ministry: {ministry}

Ministry answers from Parliament ({len(answers)} selected):
{answer_block}

Return JSON with exactly these 6 keys:
{{
  "fund_flow": {{
    "allocated": "<amount or null>",
    "released": "<amount or null>",
    "disbursed": "<amount or null>",
    "utilization_pct": "<percentage or null>",
    "discrepancies": "<shortfalls or gaps ministry mentioned, or null>"
  }},
  "beneficiary_coverage": {{
    "total_beneficiaries": "<number or null>",
    "demographic_breakdown": "<beneficiary categories or null>",
    "states_mentioned": ["<state>"],
    "coverage_note": "<notable coverage detail or null>"
  }},
  "implementation_status": {{
    "progress": "<progress against targets or null>",
    "achievements": "<what ministry says is working or null>",
    "timeline": "<key dates or milestones or null>"
  }},
  "challenges_acknowledged": {{
    "delays": "<delays ministry admitted or null>",
    "gaps": "<implementation gaps or null>",
    "pending_issues": "<outstanding issues or null>"
  }},
  "key_statistics": ["<verbatim figure from answers>"],
  "latest_position": {{
    "statement": "<most recent substantive ministry claim, verbatim>",
    "date": "<date or null>"
  }}
}}
Null for any field with no data in the answers."""

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            temperature=0,
            max_tokens=900,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or "{}"
        return json.loads(raw)
    except Exception as e:
        logger.error("GPT call failed for '%s': %s", scheme_name, e)
        return {}


def _count_scheme_answers(scheme_name: str, aliases: list[str], ministry: str) -> int:
    all_aliases = list({scheme_name} | set(aliases or []))
    ilike_parts = " OR ".join(
        f"(subject ILIKE :a{i} OR answer_text ILIKE :a{i})"
        for i in range(len(all_aliases))
    )
    params: dict = {f"a{i}": f"%{a}%" for i, a in enumerate(all_aliases)}
    try:
        with engine.connect() as conn:
            r = conn.execute(text(f"""
                SELECT COUNT(*) AS cnt
                FROM global_parliamentary_questions
                WHERE answer_text IS NOT NULL AND answer_text != ''
                  AND ({ilike_parts})
            """), params).mappings().fetchone()
        return int(r["cnt"]) if r else 0
    except Exception:
        return 0


def _write_cache(scheme_name: str, ministry: str, intel: dict,
                 pq_count: int, error: Optional[str] = None):
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO scheme_intelligence_cache
                    (scheme_name, ministry, structured_intel, generated_at,
                     pq_count_at_gen, is_stale, error)
                VALUES
                    (:name, :ministry, CAST(:intel AS JSONB), NOW(),
                     :count, false, :err)
                ON CONFLICT (scheme_name) DO UPDATE SET
                    ministry         = EXCLUDED.ministry,
                    structured_intel = EXCLUDED.structured_intel,
                    generated_at     = EXCLUDED.generated_at,
                    pq_count_at_gen  = EXCLUDED.pq_count_at_gen,
                    is_stale         = false,
                    error            = EXCLUDED.error
            """), {
                "name":     scheme_name,
                "ministry": ministry,
                "intel":    json.dumps(intel),
                "count":    pq_count,
                "err":      error,
            })
    except Exception as e:
        logger.error("_write_cache failed for '%s': %s", scheme_name, e)


def _load_db_cache(scheme_name: str) -> Optional[dict]:
    try:
        with engine.connect() as conn:
            r = conn.execute(text("""
                SELECT structured_intel, is_stale, generated_at, pq_count_at_gen, error
                FROM scheme_intelligence_cache
                WHERE scheme_name = :name
            """), {"name": scheme_name}).mappings().fetchone()
        return dict(r) if r else None
    except Exception:
        return None


def _get_scheme_row(scheme_name: str) -> Optional[dict]:
    try:
        with engine.connect() as conn:
            r = conn.execute(text(
                "SELECT name, full_name, ministry, aliases, answer_count "
                "FROM prs_schemes WHERE name = :n"
            ), {"n": scheme_name}).mappings().fetchone()
        return dict(r) if r else None
    except Exception:
        return None


def _regenerate_in_background(scheme_name: str, scheme_row: dict):
    try:
        answers = _fetch_scheme_answers(
            scheme_row["name"],
            list(scheme_row.get("aliases") or []),
            scheme_row.get("ministry") or "",
        )
        if not answers:
            _write_cache(scheme_name, scheme_row.get("ministry") or "", {}, 0, "no_answers")
            return
        intel = _call_gpt(
            scheme_row["name"], scheme_row.get("ministry") or "", answers
        )
        pq_count = _count_scheme_answers(
            scheme_row["name"],
            list(scheme_row.get("aliases") or []),
            scheme_row.get("ministry") or "",
        )
        _write_cache(scheme_name, scheme_row.get("ministry") or "", intel, pq_count)
        _runtime_cache.pop(f"intel:{scheme_name}", None)
        logger.info("Background regen complete for '%s'", scheme_name)
    except Exception as e:
        logger.error("Background regen failed for '%s': %s", scheme_name, e)


def get_scheme_intelligence(scheme_name: str) -> dict:
    """
    Returns the AI intelligence brief for a scheme.
    Fresh cache → instant. Stale → instant + background regen. No cache → generate now.
    """
    rt = _runtime_get(f"intel:{scheme_name}")
    if rt:
        return rt

    db_cache  = _load_db_cache(scheme_name)
    scheme_row = _get_scheme_row(scheme_name)

    if not scheme_row:
        return {"error": "Scheme not found", "scheme_name": scheme_name}

    def _build_result(intel, is_stale, pq_count, generated_at=None):
        return {
            "scheme_name":  scheme_name,
            "full_name":    scheme_row.get("full_name") or scheme_name,
            "ministry":     scheme_row.get("ministry"),
            "intel":        intel,
            "generated_at": generated_at.isoformat() if generated_at else None,
            "is_stale":     is_stale,
            "answer_count": pq_count,
        }

    if db_cache and db_cache.get("structured_intel") and not db_cache.get("is_stale"):
        result = _build_result(
            db_cache["structured_intel"], False,
            db_cache.get("pq_count_at_gen", 0), db_cache.get("generated_at"),
        )
        _runtime_set(f"intel:{scheme_name}", result)
        return result

    if db_cache and db_cache.get("structured_intel") and db_cache.get("is_stale"):
        threading.Thread(
            target=_regenerate_in_background, args=(scheme_name, scheme_row), daemon=True
        ).start()
        return _build_result(
            db_cache["structured_intel"], True,
            db_cache.get("pq_count_at_gen", 0), db_cache.get("generated_at"),
        )

    # No cache — generate now
    answers = _fetch_scheme_answers(
        scheme_row["name"], list(scheme_row.get("aliases") or []),
        scheme_row.get("ministry") or "",
    )
    if not answers:
        return {**_build_result(None, False, 0), "no_data": True}

    intel = _call_gpt(scheme_row["name"], scheme_row.get("ministry") or "", answers)
    pq_count = _count_scheme_answers(
        scheme_row["name"], list(scheme_row.get("aliases") or []),
        scheme_row.get("ministry") or "",
    )
    _write_cache(scheme_name, scheme_row.get("ministry") or "", intel, pq_count)
    result = _build_result(intel, False, pq_count)
    _runtime_set(f"intel:{scheme_name}", result)
    return result


# ── Staleness marking (called from crawlers after each batch) ─────────────────

def mark_stale_schemes(new_pq_ids: list[int]):
    """
    Lightweight: no GPT, just DB lookup + UPDATE. Runs in milliseconds.
    Called automatically by answer_fetcher and global_crawler after each batch.
    """
    if not new_pq_ids:
        return
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT subject FROM global_parliamentary_questions
                WHERE id = ANY(:ids)
                  AND answer_text IS NOT NULL AND answer_text != ''
                  AND subject IS NOT NULL
            """), {"ids": new_pq_ids}).mappings().all()

        subjects = [r["subject"] for r in rows if r["subject"]]
        if not subjects:
            return

        with engine.connect() as conn:
            scheme_names = conn.execute(
                text("SELECT name FROM prs_schemes WHERE answer_count >= 1")
            ).mappings().all()

        stale = [
            sn["name"] for sn in scheme_names
            if any(sn["name"].lower()[:10] in s.lower() for s in subjects)
        ]
        if not stale:
            return

        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE scheme_intelligence_cache
                SET is_stale = true
                WHERE scheme_name = ANY(:names) AND is_stale = false
            """), {"names": stale})

        logger.info("Marked %d scheme briefs stale from %d new PQ answers",
                    len(stale), len(new_pq_ids))
    except Exception as e:
        logger.warning("mark_stale_schemes failed (non-fatal): %s", e)
