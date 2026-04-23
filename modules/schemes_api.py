"""
modules/schemes_api.py — Scheme Intelligence Engine.

Three public functions consumed by api_router.py:
  get_ministry_overview()                     → all ministries with scheme + answer counts
  get_ministry_schemes(ministry)              → schemes under one ministry
  get_scheme_intelligence(name, tenant_id)    → AI-structured 3-layer brief (cached per state)

The intelligence brief has three layers:
  • Your State   — what Parliament said specifically about the MP's state
  • National     — aggregate numbers and overall ministry position
  • Other States — how other states compare

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
                    TRIM(REGEXP_REPLACE(REPLACE(ps.ministry, ' & ', ' and '), '\\s+', ' ', 'g'))
                        AS ministry,
                    COUNT(ps.id)                          AS scheme_count,
                    SUM(ps.answer_count)                  AS total_answers,
                    MAX(ps.last_seen)                     AS latest_activity,
                    COUNT(ps.id) FILTER (WHERE ps.answer_count >= 2) AS schemes_with_data
                FROM prs_schemes ps
                WHERE ps.ministry IS NOT NULL AND ps.ministry != ''
                  AND ps.answer_count >= 1
                GROUP BY TRIM(REGEXP_REPLACE(REPLACE(ps.ministry, ' & ', ' and '), '\\s+', ' ', 'g'))
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
                WHERE LOWER(TRIM(REGEXP_REPLACE(REPLACE(ministry, ' & ', ' and '), '\\s+', ' ', 'g')))
                    = LOWER(TRIM(REGEXP_REPLACE(REPLACE(:m, ' & ', ' and '), '\\s+', ' ', 'g')))
                  AND answer_count >= 2
                ORDER BY answer_count DESC, name
            """), {"m": ministry}).mappings().all()

        scheme_names = [r["name"] for r in rows]
        cached_names: set[str] = set()
        stale_names: set[str] = set()
        if scheme_names:
            with engine.connect() as conn:
                intel_rows = conn.execute(text("""
                    SELECT DISTINCT ON (scheme_name) scheme_name, is_stale
                    FROM scheme_intelligence_cache
                    WHERE scheme_name = ANY(:names)
                    ORDER BY scheme_name, is_stale ASC
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


# ── Tenant state lookup ───────────────────────────────────────────────────────

def _get_tenant_state(tenant_id: Optional[int]) -> str:
    """Returns the MP's state from tenant_profiles, or '' if not found."""
    if not tenant_id:
        return ""
    try:
        with engine.connect() as conn:
            r = conn.execute(text(
                "SELECT state FROM tenant_profiles WHERE tenant_id = :tid"
            ), {"tid": tenant_id}).mappings().fetchone()
        return (r["state"] or "").strip() if r else ""
    except Exception:
        return ""


# ── Answer fetching (tiered) ──────────────────────────────────────────────────

def _fetch_scheme_answers_tiered(
    scheme_name: str, aliases: list[str], ministry: str, state: str
) -> dict:
    """
    Returns {"state_answers": [...], "national_answers": [...]}.

    Runs three national passes (recent / longest / financial+challenge keywords).
    Ministry filter is applied first; if it yields 0 national answers the
    queries are retried without it — this handles cases where the ministry
    name stored in global_parliamentary_questions doesn't match the prs_schemes
    canonical name (different abbreviation, formatting, etc.).
    """
    all_aliases = list({scheme_name} | set(aliases or []))
    ilike_parts = " OR ".join(
        f"(subject ILIKE :a{i} OR answer_text ILIKE :a{i})"
        for i in range(len(all_aliases))
    )
    base_params: dict = {f"a{i}": f"%{a}%" for i, a in enumerate(all_aliases)}

    ministry_filter = ""
    ministry_params: dict = {}
    if ministry:
        keyword = ministry.lower().split("ministry of")[-1].strip()[:25]
        ministry_filter = "AND LOWER(ministry) LIKE :mf"
        ministry_params = {"mf": f"%{keyword}%"}

    def _rows_to_dicts(rows, seen: set) -> list[dict]:
        out = []
        for r in rows:
            fp = (r["answer_text"] or "")[:120]
            if fp not in seen:
                seen.add(fp)
                out.append({
                    "answer_text":   (r["answer_text"] or "")[:800],
                    "subject":       r["subject"],
                    "date_asked":    r["date_asked"].isoformat() if r["date_asked"] else None,
                    "question_type": r["question_type"],
                    "session_name":  r["session_name"],
                })
        return out

    def _run_national_passes(conn, mf: str, params: dict) -> list[dict]:
        seen: set[str] = set()
        out: list[dict] = []

        recent = conn.execute(text(f"""
            SELECT answer_text, subject, date_asked, question_type, session_name
            FROM global_parliamentary_questions
            WHERE answer_text IS NOT NULL AND answer_text != ''
              {mf}
              AND ({ilike_parts})
            ORDER BY date_asked DESC NULLS LAST
            LIMIT 5
        """), params).mappings().all()
        out.extend(_rows_to_dicts(recent, seen))

        longest = conn.execute(text(f"""
            SELECT answer_text, subject, date_asked, question_type, session_name
            FROM global_parliamentary_questions
            WHERE answer_text IS NOT NULL AND answer_text != ''
              {mf}
              AND ({ilike_parts})
            ORDER BY LENGTH(answer_text) DESC
            LIMIT 5
        """), params).mappings().all()
        out.extend(_rows_to_dicts(longest, seen))

        fp_params = {**params,
                     "kw1": "%crore%",    "kw2": "%allocated%", "kw3": "%released%",
                     "kw4": "%shortage%", "kw5": "%delay%",     "kw6": "%gap%",
                     "kw7": "%pending%",  "kw8": "%challenge%"}
        challenge = conn.execute(text(f"""
            SELECT answer_text, subject, date_asked, question_type, session_name
            FROM global_parliamentary_questions
            WHERE answer_text IS NOT NULL AND answer_text != ''
              {mf}
              AND ({ilike_parts})
              AND (answer_text ILIKE :kw1 OR answer_text ILIKE :kw2
                   OR answer_text ILIKE :kw3 OR answer_text ILIKE :kw4
                   OR answer_text ILIKE :kw5 OR answer_text ILIKE :kw6
                   OR answer_text ILIKE :kw7 OR answer_text ILIKE :kw8)
            ORDER BY date_asked DESC NULLS LAST
            LIMIT 4
        """), fp_params).mappings().all()
        out.extend(_rows_to_dicts(challenge, seen))

        return out[:12]

    state_answers: list[dict] = []
    national_answers: list[dict] = []

    try:
        with engine.connect() as conn:
            # ── State-specific pass ───────────────────────────────────────
            if state:
                sp = {**base_params, **ministry_params, "state": f"%{state}%"}
                state_rows = conn.execute(text(f"""
                    SELECT answer_text, subject, date_asked, question_type, session_name
                    FROM global_parliamentary_questions
                    WHERE answer_text IS NOT NULL AND answer_text != ''
                      {ministry_filter}
                      AND ({ilike_parts})
                      AND answer_text ILIKE :state
                    ORDER BY
                        (answer_text ILIKE '%crore%' OR answer_text ILIKE '%school%'
                         OR answer_text ILIKE '%fund%' OR answer_text ILIKE '%sanctioned%'
                         OR answer_text ILIKE '%operational%') DESC,
                        date_asked DESC NULLS LAST
                    LIMIT 4
                """), sp).mappings().all()
                seen_state: set[str] = set()
                state_answers = _rows_to_dicts(state_rows, seen_state)

                # Fallback: if ministry filter blocked state results, retry without
                if not state_answers and ministry_filter:
                    sp_no_mf = {**base_params, "state": f"%{state}%"}
                    state_rows_fb = conn.execute(text(f"""
                        SELECT answer_text, subject, date_asked, question_type, session_name
                        FROM global_parliamentary_questions
                        WHERE answer_text IS NOT NULL AND answer_text != ''
                          AND ({ilike_parts})
                          AND answer_text ILIKE :state
                        ORDER BY
                            (answer_text ILIKE '%crore%' OR answer_text ILIKE '%school%'
                             OR answer_text ILIKE '%fund%' OR answer_text ILIKE '%sanctioned%'
                             OR answer_text ILIKE '%operational%') DESC,
                            date_asked DESC NULLS LAST
                        LIMIT 4
                    """), sp_no_mf).mappings().all()
                    seen_state2: set[str] = set()
                    state_answers = _rows_to_dicts(state_rows_fb, seen_state2)

            # ── National passes — try with ministry filter, fall back without ──
            params_with_mf = {**base_params, **ministry_params}
            national_answers = _run_national_passes(conn, ministry_filter, params_with_mf)

            if not national_answers and ministry_filter:
                logger.info(
                    "Ministry filter yielded 0 answers for '%s' (%s) — retrying without",
                    scheme_name, ministry,
                )
                national_answers = _run_national_passes(conn, "", base_params)

    except Exception as e:
        logger.error("_fetch_scheme_answers_tiered failed: %s", e)

    return {"state_answers": state_answers, "national_answers": national_answers}


# ── GPT call (3-layer brief) ──────────────────────────────────────────────────

def _call_gpt(
    scheme_name: str, ministry: str, state: str,
    state_answers: list[dict], national_answers: list[dict]
) -> dict:
    """Call GPT-4o-mini to produce a 3-layer intelligence brief."""
    try:
        import openai
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    except Exception as e:
        logger.error("OpenAI init failed: %s", e)
        return {}

    def _fmt_block(answers, label):
        if not answers:
            return f"[No {label} answers available]\n"
        block = ""
        for i, a in enumerate(answers, 1):
            date_label = a.get("date_asked") or "unknown date"
            qtype = (a.get("question_type") or "").upper()
            block += (
                f"[{i} | {qtype} | {date_label}]\n"
                f"Subject: {a.get('subject','')}\n"
                f"{a.get('answer_text','')}\n\n"
            )
        return block

    state_block    = _fmt_block(state_answers,    f"{state}-specific" if state else "state")
    national_block = _fmt_block(national_answers, "national")

    system = (
        "You are a parliamentary intelligence analyst for India. "
        "Extract ONLY facts explicitly stated in the ministry answers. "
        "No inference, no external knowledge. Return valid JSON."
    )

    state_section = f"""
"your_state": {{
  "fund_flow": {{
    "received": "<budget/funds specifically released or allocated to {state} — do NOT use national totals; null if not stated>",
    "utilization": "<utilisation rate or note specific to {state}; null if not stated>",
    "discrepancies": "<funding shortfalls or gaps specific to {state}; null if not stated>"
  }},
  "beneficiaries": "<total enrolled students, operational schools, or households covered IN {state} — this must be an enrollment/coverage count, NOT competitive exam qualifiers; null if only exam data available>",
  "implementation": {{
    "progress": "<sanctioned vs operational school/unit counts in {state}, or rollout status; null if not stated>",
    "achievements": "<positive milestones in {state} per ministry; null if not stated>",
    "challenges": "<delays, land issues, staff vacancies, or infrastructure gaps in {state}; null if not stated>"
  }},
  "key_facts": ["<infrastructure, enrollment, or fund facts about {state} — do NOT put competitive exam results (NEET/JEE/board pass rates) here; those belong in national_picture.key_statistics>"]
}},""" if state else '"your_state": null,'

    user_prompt = f"""Scheme: {scheme_name}
Ministry: {ministry}
MP's State: {state or "Not specified"}

=== STATE-SPECIFIC ANSWERS (mentions {state or "state"}) ===
{state_block}
=== ALL ANSWERS (national/general) ===
{national_block}

IMPORTANT EXTRACTION RULES:
1. beneficiaries = enrolled students / operational schools / covered households — NEVER competitive exam qualifiers
2. If a number like "344 students qualified NEET" appears, put it in key_statistics, NOT in total_beneficiaries
3. Exam outcomes (NEET/JEE/board results) must only appear in national_picture.key_statistics, never as beneficiary counts
4. For your_state.key_facts: include school counts, fund amounts, operational status — exclude exam outcomes

Return JSON with exactly these 3 keys:
{{
{state_section}
  "national_picture": {{
    "fund_flow": {{
      "allocated": "<total national budget allocated; null if not stated>",
      "released": "<total released to states; null if not stated>",
      "disbursed": "<total disbursed to beneficiaries; null if not stated>",
      "utilization_pct": "<national utilisation percentage; null if not stated>",
      "discrepancies": "<national shortfalls or audit gaps ministry mentioned; null if not stated>"
    }},
    "beneficiary_coverage": {{
      "total_beneficiaries": "<total enrolled students, operational schools, or covered households nationally — NOT exam qualifiers; null if only exam data available>",
      "demographic_breakdown": "<beneficiary categories e.g. ST/SC/OBC/women; null if not stated>",
      "coverage_note": "<notable national coverage detail; null if not stated>"
    }},
    "implementation_status": {{
      "progress": "<national sanctioned vs operational counts, or progress against targets; null if not stated>",
      "achievements": "<what ministry says is working nationally; null if not stated>",
      "timeline": "<key dates or milestones; null if not stated>"
    }},
    "challenges_acknowledged": {{
      "delays": "<delays ministry admitted nationally; null if not stated>",
      "gaps": "<implementation gaps nationally; null if not stated>",
      "pending_issues": "<outstanding national issues; null if not stated>"
    }},
    "key_statistics": ["<verbatim figures from answers — include exam outcomes, sanctioned counts, financial figures>"],
    "latest_position": {{
      "statement": "<most recent substantive ministry claim verbatim; null if not stated>",
      "date": "<date or null>"
    }}
  }},
  "other_states": {{
    "top_mentioned": ["<states explicitly named in answers>"],
    "comparison": "<how different states compare in allocation/progress per answers; null if not stated>",
    "lagging_issues": "<issues or delays specifically reported for other states; null if not stated>"
  }}
}}
Null for any field with no supporting evidence in the answers."""

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0,
            max_tokens=1800,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or "{}"
        return json.loads(raw)
    except Exception as e:
        logger.error("GPT call failed for '%s': %s", scheme_name, e)
        return {}


# ── Cache helpers (state-keyed) ───────────────────────────────────────────────

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


def _write_cache(scheme_name: str, ministry: str, state: str, intel: dict,
                 pq_count: int, error: Optional[str] = None):
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO scheme_intelligence_cache
                    (scheme_name, ministry, state, structured_intel, generated_at,
                     pq_count_at_gen, is_stale, error)
                VALUES
                    (:name, :ministry, :state, CAST(:intel AS JSONB), NOW(),
                     :count, false, :err)
                ON CONFLICT (scheme_name, state) DO UPDATE SET
                    ministry         = EXCLUDED.ministry,
                    structured_intel = EXCLUDED.structured_intel,
                    generated_at     = EXCLUDED.generated_at,
                    pq_count_at_gen  = EXCLUDED.pq_count_at_gen,
                    is_stale         = false,
                    error            = EXCLUDED.error
            """), {
                "name":     scheme_name,
                "ministry": ministry,
                "state":    state,
                "intel":    json.dumps(intel),
                "count":    pq_count,
                "err":      error,
            })
    except Exception as e:
        logger.error("_write_cache failed for '%s'/%s: %s", scheme_name, state, e)


def _load_db_cache(scheme_name: str, state: str) -> Optional[dict]:
    try:
        with engine.connect() as conn:
            r = conn.execute(text("""
                SELECT structured_intel, is_stale, generated_at, pq_count_at_gen, error
                FROM scheme_intelligence_cache
                WHERE scheme_name = :name AND state = :state
            """), {"name": scheme_name, "state": state}).mappings().fetchone()
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


def _regenerate_in_background(scheme_name: str, scheme_row: dict, state: str):
    try:
        tiered = _fetch_scheme_answers_tiered(
            scheme_row["name"],
            list(scheme_row.get("aliases") or []),
            scheme_row.get("ministry") or "",
            state,
        )
        state_answers    = tiered["state_answers"]
        national_answers = tiered["national_answers"]
        if not state_answers and not national_answers:
            _write_cache(scheme_name, scheme_row.get("ministry") or "", state, {}, 0, "no_answers")
            return
        intel = _call_gpt(
            scheme_row["name"], scheme_row.get("ministry") or "", state,
            state_answers, national_answers,
        )
        pq_count = _count_scheme_answers(
            scheme_row["name"],
            list(scheme_row.get("aliases") or []),
            scheme_row.get("ministry") or "",
        )
        _write_cache(scheme_name, scheme_row.get("ministry") or "", state, intel, pq_count)
        _runtime_cache.pop(f"intel:{scheme_name}:{state}", None)
        logger.info("Background regen complete for '%s' [%s]", scheme_name, state or "national")
    except Exception as e:
        logger.error("Background regen failed for '%s': %s", scheme_name, e)


# ── Main entry point ──────────────────────────────────────────────────────────

def get_scheme_intelligence(scheme_name: str, tenant_id: Optional[int] = None) -> dict:
    """
    Returns the AI intelligence brief for a scheme, personalised to the MP's state.
    Fresh cache → instant. Stale → instant + background regen. No cache → generate now.
    """
    state = _get_tenant_state(tenant_id)
    rt_key = f"intel:{scheme_name}:{state}"

    rt = _runtime_get(rt_key)
    if rt:
        return rt

    db_cache   = _load_db_cache(scheme_name, state)
    scheme_row = _get_scheme_row(scheme_name)

    if not scheme_row:
        return {"error": "Scheme not found", "scheme_name": scheme_name}

    def _build_result(intel, is_stale, pq_count, generated_at=None):
        return {
            "scheme_name":  scheme_name,
            "full_name":    scheme_row.get("full_name") or scheme_name,
            "ministry":     scheme_row.get("ministry"),
            "state":        state or None,
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
        _runtime_set(rt_key, result)
        return result

    if db_cache and db_cache.get("structured_intel") and db_cache.get("is_stale"):
        threading.Thread(
            target=_regenerate_in_background,
            args=(scheme_name, scheme_row, state),
            daemon=True,
        ).start()
        return _build_result(
            db_cache["structured_intel"], True,
            db_cache.get("pq_count_at_gen", 0), db_cache.get("generated_at"),
        )

    # No cache — generate now
    tiered = _fetch_scheme_answers_tiered(
        scheme_row["name"], list(scheme_row.get("aliases") or []),
        scheme_row.get("ministry") or "", state,
    )
    state_answers    = tiered["state_answers"]
    national_answers = tiered["national_answers"]

    if not state_answers and not national_answers:
        return {**_build_result(None, False, 0), "no_data": True}

    intel = _call_gpt(
        scheme_row["name"], scheme_row.get("ministry") or "", state,
        state_answers, national_answers,
    )
    pq_count = _count_scheme_answers(
        scheme_row["name"], list(scheme_row.get("aliases") or []),
        scheme_row.get("ministry") or "",
    )
    _write_cache(scheme_name, scheme_row.get("ministry") or "", state, intel, pq_count)
    result = _build_result(intel, False, pq_count)
    _runtime_set(rt_key, result)
    return result


# ── Staleness marking (called from crawlers after each batch) ─────────────────

def mark_stale_schemes(new_pq_ids: list[int]):
    """
    Lightweight: no GPT, just DB lookup + UPDATE. Runs in milliseconds.
    Called automatically by answer_fetcher and global_crawler after each batch.
    Marks ALL state variants of a scheme stale (not just one).
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
