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
import re
import json
import time
import logging
import threading
from typing import Optional

from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy import text

from sansadx_backend.db import engine

logger = logging.getLogger("needle.schemes_api")

# ── In-memory runtime cache (avoids repeated DB reads for hot schemes) ─────
_runtime_cache: dict[str, dict] = {}
_RUNTIME_TTL = 3600  # 1 hour
_generation_guard = threading.Lock()
_active_generations: set[str] = set()
_INDIA_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
    "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya",
    "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim",
    "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand",
    "West Bengal", "Andaman and Nicobar Islands", "Chandigarh",
    "Dadra and Nagar Haveli and Daman and Diu", "Delhi", "Jammu and Kashmir",
    "Ladakh", "Lakshadweep", "Puducherry",
]
_FACT_SIGNAL_RE = re.compile(
    r"\b(?:\d[\d,\.]*\s*(?:crore|lakh|lakhs|million|billion|percent|%|students|schools|households|beneficiaries|villages|units|centres|centers)|Rs\.?\s*\d)",
    re.IGNORECASE,
)
_STAT_EXCLUDE_RE = re.compile(r"\b(?:neet|jee|board exam|exam pass|qualified)\b", re.IGNORECASE)


def _clean_sentence(text: str) -> Optional[str]:
    value = _trim_text(text)
    if not value:
        return None
    value = re.sub(r"\s+", " ", value).strip(" \"'")
    return value or None


def _split_sentences(text_value: str) -> list[str]:
    text_value = re.sub(r"\s+", " ", text_value or "").strip()
    if not text_value:
        return []
    parts = re.split(r"(?<=[\.\?!;])\s+", text_value)
    return [_clean_sentence(part) for part in parts if _clean_sentence(part)]


def _extract_states_from_text(text_value: str, current_state: str = "") -> list[str]:
    found = []
    lowered = (text_value or "").lower()
    current_state_lc = (current_state or "").strip().lower()
    for state_name in _INDIA_STATES:
        if state_name.lower() == current_state_lc:
            continue
        pattern = r"\b" + re.escape(state_name.lower()) + r"\b"
        if re.search(pattern, lowered):
            found.append(state_name)
    return found


def _find_sentence(
    answers: list[dict],
    include_terms: list[str],
    *,
    exclude_terms: Optional[list[str]] = None,
    required_state: str = "",
) -> Optional[str]:
    required_state_lc = required_state.strip().lower()
    include_terms_lc = [term.lower() for term in include_terms]
    exclude_terms_lc = [term.lower() for term in (exclude_terms or [])]

    for answer in answers:
        for sentence in _split_sentences(answer.get("answer_text") or ""):
            lowered = sentence.lower()
            if required_state_lc and required_state_lc not in lowered:
                continue
            if exclude_terms_lc and any(term in lowered for term in exclude_terms_lc):
                continue
            if include_terms_lc and not any(term in lowered for term in include_terms_lc):
                continue
            if not _FACT_SIGNAL_RE.search(sentence) and len(sentence) < 35:
                continue
            return sentence[:320]
    return None


def _collect_fact_sentences(
    answers: list[dict],
    *,
    required_state: str = "",
    exclude_exam: bool = False,
    limit: int = 5,
) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    required_state_lc = required_state.strip().lower()

    for answer in answers:
        for sentence in _split_sentences(answer.get("answer_text") or ""):
            lowered = sentence.lower()
            if required_state_lc and required_state_lc not in lowered:
                continue
            if exclude_exam and _STAT_EXCLUDE_RE.search(lowered):
                continue
            if not _FACT_SIGNAL_RE.search(sentence):
                continue
            cleaned = sentence[:320]
            if cleaned in seen:
                continue
            seen.add(cleaned)
            out.append(cleaned)
            if len(out) >= limit:
                return out
    return out


def _derive_deterministic_intel(state: str, state_answers: list[dict], national_answers: list[dict]) -> dict:
    latest_answer = sorted(
        national_answers,
        key=lambda answer: answer.get("date_asked") or "",
        reverse=True,
    )[0] if national_answers else None

    other_states: list[str] = []
    seen_states: set[str] = set()
    for answer in national_answers:
        combined = " ".join([
            answer.get("subject") or "",
            answer.get("answer_text") or "",
        ])
        for state_name in _extract_states_from_text(combined, state):
            if state_name in seen_states:
                continue
            seen_states.add(state_name)
            other_states.append(state_name)
            if len(other_states) >= 6:
                break
        if len(other_states) >= 6:
            break

    derived = {
        "your_state": {
            "fund_flow": {
                "received": _find_sentence(
                    state_answers,
                    ["released", "allocated", "sanctioned", "approved", "provided"],
                    required_state=state,
                ),
                "utilization": _find_sentence(
                    state_answers,
                    ["utilisation", "utilization", "spent", "used"],
                    required_state=state,
                ),
                "discrepancies": _find_sentence(
                    state_answers,
                    ["shortfall", "gap", "pending", "delay", "vacanc", "not released"],
                    required_state=state,
                ),
            },
            "beneficiaries": _find_sentence(
                state_answers,
                ["beneficiar", "enrol", "covered", "operational", "household", "student", "school"],
                exclude_terms=["neet", "jee", "exam", "qualified"],
                required_state=state,
            ),
            "implementation": {
                "progress": _find_sentence(
                    state_answers,
                    ["operational", "sanctioned", "constructed", "approved", "progress"],
                    required_state=state,
                ),
                "achievements": _find_sentence(
                    state_answers,
                    ["completed", "established", "operational", "achievement", "provided"],
                    required_state=state,
                ),
                "challenges": _find_sentence(
                    state_answers,
                    ["delay", "pending", "vacanc", "land", "gap", "challenge", "shortfall"],
                    required_state=state,
                ),
            },
            "key_facts": _collect_fact_sentences(
                state_answers,
                required_state=state,
                exclude_exam=True,
                limit=4,
            ),
        } if state else None,
        "national_picture": {
            "fund_flow": {
                "allocated": _find_sentence(national_answers, ["allocated", "budget", "outlay", "sanctioned"]),
                "released": _find_sentence(national_answers, ["released", "provided", "shared"]),
                "disbursed": _find_sentence(national_answers, ["disbursed", "transferred", "paid"]),
                "utilization_pct": _find_sentence(national_answers, ["utilisation", "utilization", "%", "percent"]),
                "discrepancies": _find_sentence(national_answers, ["shortfall", "gap", "audit", "pending", "delay"]),
            },
            "beneficiary_coverage": {
                "total_beneficiaries": _find_sentence(
                    national_answers,
                    ["beneficiar", "covered", "enrol", "household", "student", "school"],
                    exclude_terms=["neet", "jee", "exam", "qualified"],
                ),
                "demographic_breakdown": _find_sentence(
                    national_answers,
                    ["sc", "st", "obc", "women", "minority", "girl", "children"],
                ),
                "coverage_note": _find_sentence(
                    national_answers,
                    ["across", "states", "districts", "villages", "coverage"],
                ),
            },
            "implementation_status": {
                "progress": _find_sentence(national_answers, ["sanctioned", "operational", "progress", "completed"]),
                "achievements": _find_sentence(national_answers, ["achieved", "operational", "established", "provided"]),
                "timeline": _find_sentence(national_answers, ["by", "during", "since", "from", "timeline", "phase"]),
            },
            "challenges_acknowledged": {
                "delays": _find_sentence(national_answers, ["delay", "delayed", "pending"]),
                "gaps": _find_sentence(national_answers, ["gap", "shortfall", "vacanc", "deficit"]),
                "pending_issues": _find_sentence(national_answers, ["pending", "under consideration", "remaining"]),
            },
            "key_statistics": _collect_fact_sentences(national_answers, limit=6),
            "latest_position": {
                "statement": _clean_sentence(((latest_answer or {}).get("answer_text") or "")[:320]) if latest_answer else None,
                "date": (latest_answer or {}).get("date_asked") if latest_answer else None,
            },
        },
        "other_states": {
            "top_mentioned": other_states[:5],
        },
    }

    return _normalize_payload(derived) or {}


def _merge_intel(primary, secondary):
    if isinstance(primary, dict) and isinstance(secondary, dict):
        merged = {}
        for key in set(primary) | set(secondary):
            if key in primary and key in secondary:
                merged[key] = _merge_intel(primary[key], secondary[key])
            elif key in primary:
                merged[key] = primary[key]
            else:
                merged[key] = secondary[key]
        return merged
    if isinstance(primary, list):
        return primary or secondary
    return primary if primary not in (None, "", [], {}) else secondary


def _runtime_get(key: str) -> Optional[dict]:
    entry = _runtime_cache.get(key)
    if entry and (time.time() - entry["ts"]) < _RUNTIME_TTL:
        return entry["data"]
    return None


def _runtime_set(key: str, data):
    _runtime_cache[key] = {"data": data, "ts": time.time()}


def _generation_key(scheme_name: str, state: str) -> str:
    return f"{scheme_name}::{state}"


def _begin_generation(key: str) -> bool:
    with _generation_guard:
        if key in _active_generations:
            return False
        _active_generations.add(key)
        return True


def _end_generation(key: str):
    with _generation_guard:
        _active_generations.discard(key)


def _trim_text(value) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    value = value.strip()
    if not value or value.lower() in {"null", "none", "n/a", "na", "not stated", "unknown"}:
        return None
    return value


def _normalize_payload(value):
    if isinstance(value, dict):
        return {
            str(k): _normalize_payload(v)
            for k, v in value.items()
            if _normalize_payload(v) is not None
        }
    if isinstance(value, list):
        out = []
        seen = set()
        for item in value:
            normalized = _normalize_payload(item)
            if normalized is None:
                continue
            marker = json.dumps(normalized, sort_keys=True, default=str)
            if marker in seen:
                continue
            seen.add(marker)
            out.append(normalized)
        return out or None
    return _trim_text(value)


class _BaseIntelModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class FundFlowModel(_BaseIntelModel):
    allocated: Optional[str] = None
    released: Optional[str] = None
    disbursed: Optional[str] = None
    utilization_pct: Optional[str] = None
    discrepancies: Optional[str] = None
    received: Optional[str] = None
    utilization: Optional[str] = None


class ImplementationModel(_BaseIntelModel):
    progress: Optional[str] = None
    achievements: Optional[str] = None
    challenges: Optional[str] = None
    timeline: Optional[str] = None


class LatestPositionModel(_BaseIntelModel):
    statement: Optional[str] = None
    date: Optional[str] = None


class BeneficiaryCoverageModel(_BaseIntelModel):
    total_beneficiaries: Optional[str] = None
    demographic_breakdown: Optional[str] = None
    coverage_note: Optional[str] = None


class ChallengesModel(_BaseIntelModel):
    delays: Optional[str] = None
    gaps: Optional[str] = None
    pending_issues: Optional[str] = None


class YourStateModel(_BaseIntelModel):
    fund_flow: Optional[FundFlowModel] = None
    beneficiaries: Optional[str] = None
    implementation: Optional[ImplementationModel] = None
    key_facts: list[str] = []


class NationalPictureModel(_BaseIntelModel):
    fund_flow: Optional[FundFlowModel] = None
    beneficiary_coverage: Optional[BeneficiaryCoverageModel] = None
    implementation_status: Optional[ImplementationModel] = None
    challenges_acknowledged: Optional[ChallengesModel] = None
    key_statistics: list[str] = []
    latest_position: Optional[LatestPositionModel] = None


class OtherStatesModel(_BaseIntelModel):
    top_mentioned: list[str] = []
    comparison: Optional[str] = None
    lagging_issues: Optional[str] = None


class SchemeIntelModel(_BaseIntelModel):
    your_state: Optional[YourStateModel] = None
    national_picture: Optional[NationalPictureModel] = None
    other_states: Optional[OtherStatesModel] = None


def _validate_intel_payload(raw: dict, national_answers: list[dict]) -> dict:
    normalized = _normalize_payload(raw) or {}
    try:
        intel = SchemeIntelModel.model_validate(normalized)
    except ValidationError as e:
        logger.warning("Scheme intel validation failed: %s", e)
        return {}

    payload = intel.model_dump(exclude_none=True)

    latest = payload.setdefault("national_picture", {}).get("latest_position")
    if (not latest or not latest.get("statement")) and national_answers:
        latest_answer = sorted(
            national_answers,
            key=lambda a: a.get("date_asked") or "",
            reverse=True,
        )[0]
        excerpt = _trim_text((latest_answer.get("answer_text") or "")[:320])
        if excerpt:
            payload.setdefault("national_picture", {})["latest_position"] = {
                "statement": excerpt,
                "date": latest_answer.get("date_asked"),
            }

    return payload


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

def get_ministry_schemes(ministry: str, tenant_id: Optional[int] = None) -> list[dict]:
    """Returns all schemes for a given ministry, ordered by answer count."""
    state = _get_tenant_state(tenant_id)
    cache_key = f"ministry_schemes:{ministry.lower()}:{(state or '_').lower()}"
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
                      AND state = :state
                    ORDER BY scheme_name, is_stale ASC
                """), {"names": scheme_names, "state": state or ""}).mappings().all()
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

def _rows_to_answer_dicts(rows, seen: set[int]) -> list[dict]:
    out = []
    for r in rows:
        pq_id = int(r["id"])
        if pq_id in seen:
            continue
        seen.add(pq_id)
        out.append({
            "pq_id":         pq_id,
            "answer_text":   (r["answer_text"] or "")[:1200],
            "subject":       r["subject"],
            "date_asked":    r["date_asked"].isoformat() if r["date_asked"] else None,
            "question_type": r["question_type"],
            "session_name":  r["session_name"],
        })
    return out


def _fetch_scheme_answers_from_mentions(scheme_id: int, state: str) -> dict:
    state_answers: list[dict] = []
    national_answers: list[dict] = []
    seen_state: set[int] = set()
    seen_national: set[int] = set()

    try:
        with engine.connect() as conn:
            if state:
                state_rows = conn.execute(text("""
                    SELECT
                        gpq.id, gpq.answer_text, gpq.subject, gpq.date_asked,
                        gpq.question_type, gpq.session_name
                    FROM scheme_mentions sm
                    JOIN global_parliamentary_questions gpq ON gpq.id = sm.pq_id
                    WHERE sm.scheme_id = :scheme_id
                      AND gpq.answer_text IS NOT NULL AND gpq.answer_text != ''
                      AND gpq.answer_text ILIKE :state
                    ORDER BY
                        (gpq.answer_text ILIKE '%crore%' OR gpq.answer_text ILIKE '%fund%'
                         OR gpq.answer_text ILIKE '%sanctioned%' OR gpq.answer_text ILIKE '%operational%') DESC,
                        gpq.date_asked DESC NULLS LAST
                    LIMIT 4
                """), {"scheme_id": scheme_id, "state": f"%{state}%"}).mappings().all()
                state_answers = _rows_to_answer_dicts(state_rows, seen_state)

            recent_rows = conn.execute(text("""
                SELECT
                    gpq.id, gpq.answer_text, gpq.subject, gpq.date_asked,
                    gpq.question_type, gpq.session_name
                FROM scheme_mentions sm
                JOIN global_parliamentary_questions gpq ON gpq.id = sm.pq_id
                WHERE sm.scheme_id = :scheme_id
                  AND gpq.answer_text IS NOT NULL AND gpq.answer_text != ''
                ORDER BY gpq.date_asked DESC NULLS LAST
                LIMIT 5
            """), {"scheme_id": scheme_id}).mappings().all()
            national_answers.extend(_rows_to_answer_dicts(recent_rows, seen_national))

            longest_rows = conn.execute(text("""
                SELECT
                    gpq.id, gpq.answer_text, gpq.subject, gpq.date_asked,
                    gpq.question_type, gpq.session_name
                FROM scheme_mentions sm
                JOIN global_parliamentary_questions gpq ON gpq.id = sm.pq_id
                WHERE sm.scheme_id = :scheme_id
                  AND gpq.answer_text IS NOT NULL AND gpq.answer_text != ''
                ORDER BY LENGTH(gpq.answer_text) DESC
                LIMIT 5
            """), {"scheme_id": scheme_id}).mappings().all()
            national_answers.extend(_rows_to_answer_dicts(longest_rows, seen_national))

            challenge_rows = conn.execute(text("""
                SELECT
                    gpq.id, gpq.answer_text, gpq.subject, gpq.date_asked,
                    gpq.question_type, gpq.session_name
                FROM scheme_mentions sm
                JOIN global_parliamentary_questions gpq ON gpq.id = sm.pq_id
                WHERE sm.scheme_id = :scheme_id
                  AND gpq.answer_text IS NOT NULL AND gpq.answer_text != ''
                  AND (
                    gpq.answer_text ILIKE '%crore%' OR gpq.answer_text ILIKE '%allocated%'
                    OR gpq.answer_text ILIKE '%released%' OR gpq.answer_text ILIKE '%shortage%'
                    OR gpq.answer_text ILIKE '%delay%' OR gpq.answer_text ILIKE '%gap%'
                    OR gpq.answer_text ILIKE '%pending%' OR gpq.answer_text ILIKE '%challenge%'
                  )
                ORDER BY gpq.date_asked DESC NULLS LAST
                LIMIT 4
            """), {"scheme_id": scheme_id}).mappings().all()
            national_answers.extend(_rows_to_answer_dicts(challenge_rows, seen_national))
    except Exception as e:
        logger.error("_fetch_scheme_answers_from_mentions failed: %s", e)

    return {"state_answers": state_answers, "national_answers": national_answers[:12]}


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
    scheme_row = _get_scheme_row(scheme_name)
    if scheme_row and scheme_row.get("id"):
        exact = _fetch_scheme_answers_from_mentions(int(scheme_row["id"]), state)
        if exact["state_answers"] or exact["national_answers"]:
            return exact

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

    def _run_national_passes(conn, mf: str, params: dict) -> list[dict]:
        seen: set[int] = set()
        out: list[dict] = []

        recent = conn.execute(text(f"""
            SELECT id, answer_text, subject, date_asked, question_type, session_name
            FROM global_parliamentary_questions
            WHERE answer_text IS NOT NULL AND answer_text != ''
              {mf}
              AND ({ilike_parts})
            ORDER BY date_asked DESC NULLS LAST
            LIMIT 5
        """), params).mappings().all()
        out.extend(_rows_to_answer_dicts(recent, seen))

        longest = conn.execute(text(f"""
            SELECT id, answer_text, subject, date_asked, question_type, session_name
            FROM global_parliamentary_questions
            WHERE answer_text IS NOT NULL AND answer_text != ''
              {mf}
              AND ({ilike_parts})
            ORDER BY LENGTH(answer_text) DESC
            LIMIT 5
        """), params).mappings().all()
        out.extend(_rows_to_answer_dicts(longest, seen))

        fp_params = {**params,
                     "kw1": "%crore%",    "kw2": "%allocated%", "kw3": "%released%",
                     "kw4": "%shortage%", "kw5": "%delay%",     "kw6": "%gap%",
                     "kw7": "%pending%",  "kw8": "%challenge%"}
        challenge = conn.execute(text(f"""
            SELECT id, answer_text, subject, date_asked, question_type, session_name
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
        out.extend(_rows_to_answer_dicts(challenge, seen))

        return out[:12]

    state_answers: list[dict] = []
    national_answers: list[dict] = []

    try:
        with engine.connect() as conn:
            # ── State-specific pass ───────────────────────────────────────
            if state:
                sp = {**base_params, **ministry_params, "state": f"%{state}%"}
                state_rows = conn.execute(text(f"""
                    SELECT id, answer_text, subject, date_asked, question_type, session_name
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
                seen_state: set[int] = set()
                state_answers = _rows_to_answer_dicts(state_rows, seen_state)

                # Fallback: if ministry filter blocked state results, retry without
                if not state_answers and ministry_filter:
                    sp_no_mf = {**base_params, "state": f"%{state}%"}
                    state_rows_fb = conn.execute(text(f"""
                        SELECT id, answer_text, subject, date_asked, question_type, session_name
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
                    seen_state2: set[int] = set()
                    state_answers = _rows_to_answer_dicts(state_rows_fb, seen_state2)

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
    state_answers: list[dict], national_answers: list[dict],
    deterministic_facts: Optional[dict] = None,
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
    fact_sheet = json.dumps(deterministic_facts or {}, ensure_ascii=True, indent=2)

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
5. Prefer the structured fact sheet below when filling fields. Only use answer text to support or refine those facts, never to invent new ones.

=== DETERMINISTIC FACT SHEET ===
{fact_sheet}

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
    scheme_row = _get_scheme_row(scheme_name)
    if scheme_row and scheme_row.get("id"):
        try:
            with engine.connect() as conn:
                r = conn.execute(text("""
                    SELECT COUNT(DISTINCT sm.pq_id) AS cnt
                    FROM scheme_mentions sm
                    JOIN global_parliamentary_questions gpq ON gpq.id = sm.pq_id
                    WHERE sm.scheme_id = :scheme_id
                      AND gpq.answer_text IS NOT NULL AND gpq.answer_text != ''
                """), {"scheme_id": int(scheme_row["id"])}).mappings().fetchone()
            if r and r["cnt"] is not None:
                return int(r["cnt"])
        except Exception:
            pass

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
                "SELECT id, name, full_name, ministry, aliases, answer_count "
                "FROM prs_schemes WHERE name = :n"
            ), {"n": scheme_name}).mappings().fetchone()
        return dict(r) if r else None
    except Exception:
        return None


def _schedule_regeneration(scheme_name: str, scheme_row: dict, state: str) -> bool:
    key = _generation_key(scheme_name, state)
    if not _begin_generation(key):
        return False
    threading.Thread(
        target=_regenerate_in_background,
        args=(scheme_name, scheme_row, state, key),
        daemon=True,
    ).start()
    return True


def _regenerate_in_background(scheme_name: str, scheme_row: dict, state: str, generation_key: str):
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
        deterministic_facts = _derive_deterministic_intel(state, state_answers, national_answers)
        raw_intel = _call_gpt(
            scheme_row["name"], scheme_row.get("ministry") or "", state,
            state_answers, national_answers, deterministic_facts,
        )
        validated_intel = _validate_intel_payload(raw_intel, national_answers)
        intel = _validate_intel_payload(
            _merge_intel(deterministic_facts, validated_intel),
            national_answers,
        )
        if not state:
            intel.pop("your_state", None)
        pq_count = _count_scheme_answers(
            scheme_row["name"],
            list(scheme_row.get("aliases") or []),
            scheme_row.get("ministry") or "",
        )
        cache_error = None if intel else "validation_failed"
        _write_cache(scheme_name, scheme_row.get("ministry") or "", state, intel, pq_count, cache_error)
        _runtime_cache.pop(f"intel:{scheme_name}:{state}", None)
        logger.info("Background regen complete for '%s' [%s]", scheme_name, state or "national")
    except Exception as e:
        logger.error("Background regen failed for '%s': %s", scheme_name, e)
        _write_cache(scheme_name, scheme_row.get("ministry") or "", state, {}, 0, "generation_failed")
    finally:
        _end_generation(generation_key)


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
            "pending":      False,
        }

    if db_cache and db_cache.get("structured_intel") and not db_cache.get("is_stale"):
        result = _build_result(
            db_cache["structured_intel"], False,
            db_cache.get("pq_count_at_gen", 0), db_cache.get("generated_at"),
        )
        _runtime_set(rt_key, result)
        return result

    if db_cache and db_cache.get("structured_intel") and db_cache.get("is_stale"):
        _schedule_regeneration(scheme_name, scheme_row, state)
        return _build_result(
            db_cache["structured_intel"], True,
            db_cache.get("pq_count_at_gen", 0), db_cache.get("generated_at"),
        )

    if int(scheme_row.get("answer_count") or 0) < 1:
        return {**_build_result(None, False, 0), "no_data": True}

    _schedule_regeneration(scheme_name, scheme_row, state)
    result = _build_result(None, False, int(scheme_row.get("answer_count") or 0))
    result["pending"] = True
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
            exact_rows = conn.execute(text("""
                SELECT DISTINCT ps.name
                FROM scheme_mentions sm
                JOIN prs_schemes ps ON ps.id = sm.scheme_id
                JOIN global_parliamentary_questions gpq ON gpq.id = sm.pq_id
                WHERE sm.pq_id = ANY(:ids)
                  AND gpq.answer_text IS NOT NULL AND gpq.answer_text != ''
            """), {"ids": new_pq_ids}).mappings().all()

        exact_names = [r["name"] for r in exact_rows if r["name"]]
        if exact_names:
            with engine.begin() as conn:
                conn.execute(text("""
                    UPDATE scheme_intelligence_cache
                    SET is_stale = true
                    WHERE scheme_name = ANY(:names) AND is_stale = false
                """), {"names": exact_names})
            logger.info("Marked %d scheme briefs stale from exact scheme_mentions", len(exact_names))
            return

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
