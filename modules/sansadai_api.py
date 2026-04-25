"""
modules/sansadai_api.py — SansadAI issue intelligence engine.

Public API:
  get_issue_ministries()                                → ministry list for SansadAI
  get_issue_topics(ministry, tenant_id, state_override) → topics under a ministry
  get_issue_intelligence(ministry, topic, tenant_id)   → cached issue brief by ministry/topic/state
  mark_stale_issue_briefs(pq_ids)                      → stale affected issue briefs after answer updates
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from typing import Optional

from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy import text

from sansadx_backend.db import engine

logger = logging.getLogger("needle.sansadai_api")

_runtime_cache: dict[str, dict] = {}
_RUNTIME_TTL = 3600
_generation_guard = threading.Lock()
_active_generations: set[str] = set()

_NUMERIC_RE = re.compile(
    r"\b(?:Rs\.?\s*)?\d[\d,\.]*(?:\s*(?:crore|cr|lakh|lakhs|million|billion|percent|%|days|months|years|villages|districts|projects|beneficiaries|schools|students|km|MW|MT))?\b",
    re.IGNORECASE,
)
_DATE_RE = re.compile(
    r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s,.-]+\d{2,4}|\d{4})\b",
    re.IGNORECASE,
)
_GAP_TERMS = [
    "delay", "delayed", "pending", "shortfall", "gap", "vacanc", "backlog",
    "not completed", "not released", "awaiting", "under process", "lag",
]
_POSITION_TERMS = [
    "stated", "informed", "reported", "clarified", "submitted", "approved",
    "sanctioned", "implemented", "launched", "under consideration", "proposal",
]
_STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "have", "has", "had",
    "been", "were", "was", "will", "shall", "their", "there", "about", "under",
    "into", "over", "than", "them", "they", "said", "state", "states", "union",
    "government", "ministry", "question", "answer", "regarding", "subject",
}

ISSUE_TOPICS = [
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
ISSUE_TOPIC_SET = set(ISSUE_TOPICS)
_ISSUE_TOPIC_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("Challenges & Delays", (
        "delay", "delayed", "pending", "shortfall", "shortage", "vacancy",
        "vacancies", "backlog", "underutilized", "under-utilized", "slow progress",
        "not completed", "not functional", "incomplete", "bottleneck",
    )),
    ("Budget & Finance", (
        "budget", "allocation", "allocated", "fund", "funding", "funds", "outlay",
        "expenditure", "spent", "financial", "finance", "grant", "subsidy",
        "loan", "credit", "tax", "pricing", "price rise", "reimbursement",
        "compensation", "fiscal",
    )),
    ("Welfare & Beneficiaries", (
        "beneficiary", "beneficiaries", "welfare", "pension", "scholarship",
        "ration", "insurance", "stipend", "livelihood", "self help group",
        "self-help group", "shg", "anganwadi", "hostel", "relief", "farmer welfare",
    )),
    ("Implementation & Progress", (
        "implementation", "progress", "status", "coverage", "achievement",
        "completed", "completion", "rollout", "operational", "functioning",
        "execution", "progress made", "work completed",
    )),
    ("Policy & Legislation", (
        "policy", "bill", "act", "amendment", "guideline", "guidelines",
        "framework", "mission", "policy decision", "cabinet", "ordinance",
        "rules", "scheme norms",
    )),
    ("Data & Statistics", (
        "statistics", "statistical", "data", "census", "survey", "details thereof",
        "year-wise", "state-wise", "district-wise", "number of", "count of",
        "how many", "figures", "reported data",
    )),
    ("Appointments & Administration", (
        "appointment", "appointments", "recruitment", "recruited", "vacancy",
        "vacancies", "post of", "posts in", "cadre", "staff", "officer",
        "officers", "committee", "chairperson", "secretary", "administration",
        "administrative", "transfer", "promotion",
    )),
    ("International & Bilateral", (
        "international", "bilateral", "foreign", "cross-border", "cross border",
        "export", "import", "embassy", "visa", "trade agreement", "united nations",
        "neighbouring country", "neighboring country", "global cooperation",
    )),
    ("Environment & Sustainability", (
        "environment", "environmental", "climate", "pollution", "forest",
        "wildlife", "emission", "sustainability", "sustainable", "renewable",
        "solar", "waste management", "conservation", "ecology", "air quality",
        "river cleaning",
    )),
    ("Research & Technology", (
        "research", "technology", "technological", "innovation", "digital",
        "artificial intelligence", "ai ", "startup", "scientific", "science",
        "patent", "satellite", "space", "cyber", "telecom technology",
    )),
    ("Legal & Regulatory", (
        "regulation", "regulatory", "legal", "court", "tribunal", "license",
        "licence", "compliance", "penalty", "violation", "litigation", "judicial",
        "adjudication", "statutory",
    )),
    ("Infrastructure & Projects", (
        "infrastructure", "project", "construction", "road", "highway", "bridge",
        "rail", "railway", "airport", "port", "pipeline", "power plant",
        "transmission line", "metro", "building", "housing", "connectivity",
        "broadband", "fibre", "fiber", "dam", "corridor",
    )),
]
_ISSUE_TOPIC_PRIORITY = {
    topic: index for index, (topic, _) in enumerate(_ISSUE_TOPIC_KEYWORDS)
}
for topic in ISSUE_TOPICS:
    _ISSUE_TOPIC_PRIORITY.setdefault(topic, len(_ISSUE_TOPIC_PRIORITY))


def _runtime_get(key: str) -> Optional[dict]:
    entry = _runtime_cache.get(key)
    if entry and (time.time() - entry["ts"]) < _RUNTIME_TTL:
        return entry["data"]
    return None


def _runtime_set(key: str, data):
    _runtime_cache[key] = {"data": data, "ts": time.time()}


def _generation_key(ministry: str, topic: str, state: str) -> str:
    return f"{_norm(ministry)}::{_norm(topic)}::{_norm(state)}"


def _begin_generation(key: str) -> bool:
    with _generation_guard:
        if key in _active_generations:
            return False
        _active_generations.add(key)
        return True


def _end_generation(key: str):
    with _generation_guard:
        _active_generations.discard(key)


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).lower()


def _joined_topic_text(subject: str, ministry: str = "", topic_tags: Optional[list[str]] = None) -> str:
    tags = " ".join(tag for tag in (topic_tags or []) if tag)
    text = " ".join(part for part in [subject or "", ministry or "", tags] if part)
    lowered = _norm(text)
    return re.sub(r"[^a-z0-9&/\-\s]+", " ", lowered)


def _date_sort_value(value) -> str:
    if value and hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value or "")


def infer_issue_topic(subject: str, ministry: str = "", topic_tags: Optional[list[str]] = None) -> str:
    """
    Derive the fixed SansadAI topic from raw PQ metadata.

    This is the read-time fallback used when the batch topic-classification
    job has not yet populated global_parliamentary_questions.topic.
    """
    text = _joined_topic_text(subject, ministry, topic_tags)
    if not text:
        return "Other"

    scores = {topic: 0 for topic in ISSUE_TOPICS}
    for topic, keywords in _ISSUE_TOPIC_KEYWORDS:
        for keyword in keywords:
            if keyword in text:
                scores[topic] += 2 if " " in keyword else 1

    # Common parliamentary phrasing that points to numeric/status questions.
    if any(phrase in text for phrase in ("details thereof", "state-wise", "district-wise", "year-wise", "how many", "number of")):
        scores["Data & Statistics"] += 2
    if any(phrase in text for phrase in ("status of", "progress of", "progress made", "implementation of")):
        scores["Implementation & Progress"] += 2
    if any(phrase in text for phrase in ("delay in", "pending", "shortfall in", "vacancies in")):
        scores["Challenges & Delays"] += 2

    ranked = sorted(
        scores.items(),
        key=lambda item: (-item[1], _ISSUE_TOPIC_PRIORITY.get(item[0], len(ISSUE_TOPICS))),
    )
    best_topic, best_score = ranked[0]
    return best_topic if best_score > 0 else "Other"


def _trim_text(value) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    value = re.sub(r"\s+", " ", value).strip(" \"'")
    if not value or value.lower() in {"null", "none", "n/a", "na", "unknown", "not stated"}:
        return None
    return value


def _normalize_payload(value):
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            normalized = _normalize_payload(item)
            if normalized is not None:
                out[str(key)] = normalized
        return out or None
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


def _split_sentences(text_value: str) -> list[str]:
    text_value = re.sub(r"\s+", " ", text_value or "").strip()
    if not text_value:
        return []
    parts = re.split(r"(?<=[\.\?!;])\s+", text_value)
    return [_trim_text(part) for part in parts if _trim_text(part)]


def _stance_bucket(sentence: str) -> str:
    lowered = (sentence or "").lower()
    if any(term in lowered for term in ["no proposal", "not under consideration", "no such", "not available", "not received"]):
        return "negative"
    if any(term in lowered for term in ["under consideration", "being examined", "proposal received", "under process", "being taken up"]):
        return "pending"
    if any(term in lowered for term in ["approved", "sanctioned", "implemented", "completed", "launched", "released"]):
        return "positive"
    return "neutral"


def _keyword_set(sentence: str) -> set[str]:
    tokens = re.findall(r"[a-zA-Z]{4,}", (sentence or "").lower())
    return {token for token in tokens if token not in _STOPWORDS}


def _sentence_overlap(a: str, b: str) -> float:
    left = _keyword_set(a)
    right = _keyword_set(b)
    if not left or not right:
        return 0.0
    return len(left & right) / max(1, min(len(left), len(right)))


def _sentence_entry(answer: dict, sentence: str) -> dict:
    return {
        "sentence": sentence[:320],
        "date": answer.get("date_asked"),
        "numbers": _NUMERIC_RE.findall(sentence or ""),
        "dates": _DATE_RE.findall(sentence or ""),
        "stance": _stance_bucket(sentence),
    }


def _collect_sentences(
    answers: list[dict],
    *,
    include_terms: Optional[list[str]] = None,
    require_numbers: bool = False,
    required_state: str = "",
    limit: int = 6,
) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    include_terms_lc = [term.lower() for term in (include_terms or [])]
    required_state_lc = required_state.lower().strip()

    for answer in answers:
        for sentence in _split_sentences(answer.get("answer_text") or ""):
            lowered = sentence.lower()
            if required_state_lc and required_state_lc not in lowered:
                continue
            if include_terms_lc and not any(term in lowered for term in include_terms_lc):
                continue
            if require_numbers and not _NUMERIC_RE.search(sentence):
                continue
            cleaned = sentence[:320]
            if cleaned in seen:
                continue
            seen.add(cleaned)
            out.append(cleaned)
            if len(out) >= limit:
                return out
    return out


def _extract_position_summary(answers: list[dict]) -> tuple[Optional[str], Optional[str]]:
    if not answers:
        return None, None
    latest = sorted(answers, key=lambda row: row.get("date_asked") or "", reverse=True)[0]
    for sentence in _split_sentences(latest.get("answer_text") or ""):
        lowered = sentence.lower()
        if any(term in lowered for term in _POSITION_TERMS):
            return sentence[:320], latest.get("date_asked")
    return _trim_text((latest.get("answer_text") or "")[:320]), latest.get("date_asked")


def _detect_deltas(answers: list[dict]) -> dict:
    if len(answers) < 2:
        return {}

    ordered = sorted(answers, key=lambda row: row.get("date_asked") or "")
    older_answers = ordered[: min(6, max(1, len(ordered) // 2))]
    recent_answers = ordered[-min(6, len(ordered)) :]

    older_facts = []
    recent_facts = []
    for answer in older_answers:
        for sentence in _split_sentences(answer.get("answer_text") or ""):
            if _NUMERIC_RE.search(sentence) or _DATE_RE.search(sentence) or _stance_bucket(sentence) != "neutral":
                older_facts.append(_sentence_entry(answer, sentence))
    for answer in recent_answers:
        for sentence in _split_sentences(answer.get("answer_text") or ""):
            if _NUMERIC_RE.search(sentence) or _DATE_RE.search(sentence) or _stance_bucket(sentence) != "neutral":
                recent_facts.append(_sentence_entry(answer, sentence))

    changed_numbers: list[str] = []
    changed_deadlines: list[str] = []
    stance_shifts: list[str] = []
    seen_pairs: set[str] = set()

    for recent in recent_facts:
        best = None
        best_score = 0.0
        for older in older_facts:
            score = _sentence_overlap(recent["sentence"], older["sentence"])
            if score > best_score:
                best_score = score
                best = older
        if not best or best_score < 0.34:
            continue

        pair_key = f"{best['sentence']}::{recent['sentence']}"
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)

        if best["numbers"] and recent["numbers"] and best["numbers"] != recent["numbers"]:
            changed_numbers.append(
                f"{best.get('date') or 'Earlier'}: {best['sentence']} | {recent.get('date') or 'Later'}: {recent['sentence']}"
            )
        if best["dates"] and recent["dates"] and best["dates"] != recent["dates"]:
            changed_deadlines.append(
                f"{best.get('date') or 'Earlier'}: {best['sentence']} | {recent.get('date') or 'Later'}: {recent['sentence']}"
            )
        if best["stance"] != "neutral" and recent["stance"] != "neutral" and best["stance"] != recent["stance"]:
            stance_shifts.append(
                f"{best.get('date') or 'Earlier'}: {best['sentence']} | {recent.get('date') or 'Later'}: {recent['sentence']}"
            )

    return _normalize_payload({
        "changed_numbers": changed_numbers[:4],
        "changed_deadlines": changed_deadlines[:4],
        "stance_shifts": stance_shifts[:4],
    }) or {}


def _get_tenant_state(tenant_id: Optional[int]) -> str:
    if not tenant_id:
        return ""
    try:
        with engine.connect() as conn:
            row = conn.execute(text(
                "SELECT state FROM tenant_profiles WHERE tenant_id = :tid"
            ), {"tid": tenant_id}).mappings().fetchone()
        return _trim_text((row or {}).get("state")) or ""
    except Exception:
        return ""


def _resolved_state(tenant_id: Optional[int], state_override: Optional[str] = None) -> str:
    return _trim_text(state_override) or _get_tenant_state(tenant_id)


class _BaseIntelModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class CurrentGovernmentPositionModel(_BaseIntelModel):
    summary: Optional[str] = None
    latest_update: Optional[str] = None
    latest_date: Optional[str] = None


class DeltasOnRecordModel(_BaseIntelModel):
    changed_numbers: list[str] = []
    changed_deadlines: list[str] = []
    stance_shifts: list[str] = []


class IssueIntelModel(_BaseIntelModel):
    current_government_position: Optional[CurrentGovernmentPositionModel] = None
    key_numbers_on_record: list[str] = []
    implementation_gaps: list[str] = []
    state_specific_mentions: list[str] = []
    deltas_on_record: Optional[DeltasOnRecordModel] = None


def _validate_payload(raw: dict, answers: list[dict]) -> dict:
    normalized = _normalize_payload(raw) or {}
    try:
        parsed = IssueIntelModel.model_validate(normalized)
    except ValidationError as e:
        logger.warning("SansadAI payload validation failed: %s", e)
        return {}

    payload = parsed.model_dump(exclude_none=True)
    if not payload.get("current_government_position"):
        summary, latest_date = _extract_position_summary(answers)
        if summary:
            payload["current_government_position"] = {
                "summary": summary,
                "latest_update": summary,
                "latest_date": latest_date,
            }
    return payload


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


def _rows_to_answer_dicts(rows, seen: set[int]) -> list[dict]:
    out = []
    for row in rows:
        pq_id = int(row["id"])
        if pq_id in seen:
            continue
        seen.add(pq_id)
        out.append({
            "pq_id": pq_id,
            "subject": row["subject"],
            "answer_text": (row["answer_text"] or "")[:1600],
            "date_asked": row["date_asked"].isoformat() if row["date_asked"] else None,
            "question_type": row["question_type"],
            "session_name": row["session_name"],
            "question_number": row.get("question_number"),
            "mp_name": row.get("mp_name"),
            "prs_url": row.get("prs_url"),
        })
    return out


def _effective_topic_for_row(row: dict) -> str:
    topic = _trim_text(row.get("topic"))
    if topic in ISSUE_TOPIC_SET:
        return topic
    topic_tags = row.get("topic_tags")
    if isinstance(topic_tags, str):
        try:
            topic_tags = json.loads(topic_tags)
        except Exception:
            topic_tags = [topic_tags]
    if not isinstance(topic_tags, list):
        topic_tags = []
    return infer_issue_topic(
        row.get("subject") or "",
        row.get("ministry") or "",
        topic_tags,
    )


def _fetch_ministry_answer_rows(ministry: str) -> list[dict]:
    cache_key = f"sansadai:ministry-rows:{_norm(ministry)}"
    cached = _runtime_get(cache_key)
    if cached is not None:
        return cached

    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT id, subject, answer_text, date_asked, question_type,
                       session_name, question_number, mp_name, prs_url,
                       topic, topic_tags, TRIM(ministry) AS ministry
                FROM global_parliamentary_questions
                WHERE answer_text IS NOT NULL AND answer_text != ''
                  AND ministry IS NOT NULL AND ministry != ''
                  AND LOWER(TRIM(ministry)) = LOWER(TRIM(:ministry))
            """), {"ministry": ministry}).mappings().all()
        result = [dict(row) for row in rows]
        _runtime_set(cache_key, result)
        return result
    except Exception as e:
        logger.error("_fetch_ministry_answer_rows(%s) failed: %s", ministry, e)
        return []


def _fetch_issue_answers(ministry: str, topic: str, state: str) -> dict:
    state_answers: list[dict] = []
    issue_answers: list[dict] = []
    seen_state: set[int] = set()
    seen_issue: set[int] = set()
    try:
        rows = [
            row for row in _fetch_ministry_answer_rows(ministry)
            if _effective_topic_for_row(row) == topic
        ]
        if state:
            state_rows = [
                row for row in rows
                if state.lower() in (row.get("answer_text") or "").lower()
            ]
            state_rows = sorted(
                state_rows,
                key=lambda row: _date_sort_value(row.get("date_asked")),
                reverse=True,
            )[:6]
            state_answers = _rows_to_answer_dicts(state_rows, seen_state)

        recent_rows = sorted(
            rows,
            key=lambda row: _date_sort_value(row.get("date_asked")),
            reverse=True,
        )[:8]
        issue_answers.extend(_rows_to_answer_dicts(recent_rows, seen_issue))

        longest_rows = sorted(
            rows,
            key=lambda row: len(row.get("answer_text") or ""),
            reverse=True,
        )[:6]
        issue_answers.extend(_rows_to_answer_dicts(longest_rows, seen_issue))

        keyword_rows = []
        for row in rows:
            answer_text = (row.get("answer_text") or "").lower()
            if any(term in answer_text for term in ("delay", "pending", "shortfall", "gap", "approved", "released", "crore", "percent")):
                keyword_rows.append(row)
        keyword_rows = sorted(
            keyword_rows,
            key=lambda row: _date_sort_value(row.get("date_asked")),
            reverse=True,
        )[:6]
        issue_answers.extend(_rows_to_answer_dicts(keyword_rows, seen_issue))
    except Exception as e:
        logger.error("_fetch_issue_answers failed for %s / %s: %s", ministry, topic, e)

    issue_answers = sorted(
        issue_answers,
        key=lambda row: row.get("date_asked") or "",
        reverse=True,
    )[:14]
    return {"state_answers": state_answers, "issue_answers": issue_answers}


def _derive_deterministic_intel(state: str, issue_answers: list[dict], state_answers: list[dict]) -> dict:
    summary, latest_date = _extract_position_summary(issue_answers)
    gaps = _collect_sentences(issue_answers, include_terms=_GAP_TERMS, limit=5)
    numbers = _collect_sentences(issue_answers, require_numbers=True, limit=6)
    state_mentions = _collect_sentences(state_answers, required_state=state, limit=5) if state else []
    deltas = _detect_deltas(issue_answers)

    derived = {
        "current_government_position": {
            "summary": summary,
            "latest_update": summary,
            "latest_date": latest_date,
        },
        "key_numbers_on_record": numbers,
        "implementation_gaps": gaps,
        "state_specific_mentions": state_mentions,
        "deltas_on_record": deltas,
    }
    if not state:
        derived["state_specific_mentions"] = []
    return _normalize_payload(derived) or {}


def _call_gpt(
    ministry: str,
    topic: str,
    state: str,
    issue_answers: list[dict],
    state_answers: list[dict],
    deterministic_facts: Optional[dict] = None,
) -> dict:
    try:
        import openai
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    except Exception as e:
        logger.error("OpenAI init failed for SansadAI: %s", e)
        return {}

    def _fmt_block(answers, label):
        if not answers:
            return f"[No {label} answers available]\n"
        block = ""
        for i, answer in enumerate(answers, 1):
            block += (
                f"[{i} | {(answer.get('question_type') or '').upper()} | {answer.get('date_asked') or 'unknown date'}]\n"
                f"Subject: {answer.get('subject') or ''}\n"
                f"{answer.get('answer_text') or ''}\n\n"
            )
        return block

    state_block = _fmt_block(state_answers, f"{state}-specific" if state else "state")
    issue_block = _fmt_block(issue_answers, "issue-cluster")
    fact_sheet = json.dumps(deterministic_facts or {}, ensure_ascii=True, indent=2)

    user_prompt = f"""SansadAI issue brief
Ministry: {ministry}
Topic: {topic}
State focus: {state or "National"}

=== DETERMINISTIC FACT SHEET ===
{fact_sheet}

=== STATE-SPECIFIC ANSWERS ===
{state_block}

=== ISSUE CLUSTER ANSWERS ===
{issue_block}

Return valid JSON with exactly these keys:
{{
  "current_government_position": {{
    "summary": "<2-4 line plain-English summary of what the government currently says on this issue>",
    "latest_update": "<most recent substantive position on record>",
    "latest_date": "<date or null>"
  }},
  "key_numbers_on_record": ["<important figures or quantified claims on record>"],
  "implementation_gaps": ["<gaps, delays, pending issues, or execution bottlenecks on record>"],
  "state_specific_mentions": ["<facts explicitly mentioning the selected state>"],
  "deltas_on_record": {{
    "changed_numbers": ["<where the record shows changed numbers over time>"],
    "changed_deadlines": ["<where timelines or deadlines shifted over time>"],
    "stance_shifts": ["<where the ministry stance appears to have changed over time>"]
  }}
}}

Rules:
- Use only facts explicitly present in the answers or deterministic fact sheet.
- Do not add any advice, pressure angles, or suggested follow-up questions/letters/speeches.
- Keep each list item concise and factual.
- If evidence is missing, return null or [] for that field."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a parliamentary intelligence analyst. Return valid JSON only."},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            max_tokens=1600,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content or "{}"
        return json.loads(raw)
    except Exception as e:
        logger.error("SansadAI GPT call failed for %s / %s: %s", ministry, topic, e)
        return {}


def _write_cache(ministry: str, topic: str, state: str, intel: dict, pq_count: int, error: Optional[str] = None):
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO issue_intelligence_cache
                    (ministry, topic, state, structured_intel, generated_at, pq_count_at_gen, is_stale, error)
                VALUES
                    (:ministry, :topic, :state, CAST(:intel AS JSONB), NOW(), :count, false, :error)
                ON CONFLICT (ministry, topic, state) DO UPDATE SET
                    structured_intel = EXCLUDED.structured_intel,
                    generated_at = EXCLUDED.generated_at,
                    pq_count_at_gen = EXCLUDED.pq_count_at_gen,
                    is_stale = false,
                    error = EXCLUDED.error
            """), {
                "ministry": ministry,
                "topic": topic,
                "state": state,
                "intel": json.dumps(intel),
                "count": pq_count,
                "error": error,
            })
    except Exception as e:
        logger.error("_write_cache failed for SansadAI %s / %s / %s: %s", ministry, topic, state, e)


def _load_db_cache(ministry: str, topic: str, state: str) -> Optional[dict]:
    try:
        with engine.connect() as conn:
            row = conn.execute(text("""
                SELECT structured_intel, generated_at, pq_count_at_gen, is_stale, error
                FROM issue_intelligence_cache
                WHERE ministry = :ministry AND topic = :topic AND state = :state
            """), {"ministry": ministry, "topic": topic, "state": state}).mappings().fetchone()
        return dict(row) if row else None
    except Exception:
        return None


def _count_issue_answers(ministry: str, topic: str) -> int:
    try:
        return sum(
            1
            for row in _fetch_ministry_answer_rows(ministry)
            if _effective_topic_for_row(row) == topic
        )
    except Exception:
        return 0


def _schedule_regeneration(ministry: str, topic: str, state: str) -> bool:
    key = _generation_key(ministry, topic, state)
    if not _begin_generation(key):
        return False
    threading.Thread(
        target=_regenerate_in_background,
        args=(ministry, topic, state, key),
        daemon=True,
    ).start()
    return True


def _regenerate_in_background(ministry: str, topic: str, state: str, generation_key: str):
    try:
        bundle = _fetch_issue_answers(ministry, topic, state)
        state_answers = bundle["state_answers"]
        issue_answers = bundle["issue_answers"]
        if not issue_answers:
            _write_cache(ministry, topic, state, {}, 0, "no_answers")
            return

        deterministic = _derive_deterministic_intel(state, issue_answers, state_answers)
        raw = _call_gpt(ministry, topic, state, issue_answers, state_answers, deterministic)
        validated = _validate_payload(raw, issue_answers)
        intel = _validate_payload(_merge_intel(deterministic, validated), issue_answers)
        cache_error = None if intel else "validation_failed"
        _write_cache(ministry, topic, state, intel, len(issue_answers), cache_error)
        _runtime_cache.pop(f"sansadai:intel:{_generation_key(ministry, topic, state)}", None)
    except Exception as e:
        logger.error("SansadAI background regeneration failed for %s / %s / %s: %s", ministry, topic, state, e)
        _write_cache(ministry, topic, state, {}, 0, "generation_failed")
    finally:
        _end_generation(generation_key)


def get_issue_ministries() -> list[dict]:
    cache_key = "sansadai:ministries"
    cached = _runtime_get(cache_key)
    if cached is not None:
        return cached

    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT
                    TRIM(ministry) AS ministry,
                    subject,
                    topic,
                    topic_tags,
                    date_asked
                FROM global_parliamentary_questions
                WHERE ministry IS NOT NULL AND ministry != ''
                  AND answer_text IS NOT NULL AND answer_text != ''
            """)).mappings().all()

        by_ministry: dict[str, dict] = {}
        for row in rows:
            ministry = _trim_text(row.get("ministry"))
            if not ministry:
                continue
            entry = by_ministry.setdefault(ministry, {
                "ministry": ministry,
                "classified_count": 0,
                "topics": set(),
                "latest_activity": None,
            })
            entry["classified_count"] += 1
            entry["topics"].add(_effective_topic_for_row(dict(row)))
            if row.get("date_asked") and (entry["latest_activity"] is None or row["date_asked"] > entry["latest_activity"]):
                entry["latest_activity"] = row["date_asked"]

        result = sorted(
            (
                {
                    "ministry": entry["ministry"],
                    "topic_count": len(entry["topics"]),
                    "latest_activity": entry["latest_activity"].isoformat() if entry["latest_activity"] else None,
                }
                for entry in by_ministry.values()
            ),
            key=lambda item: (
                -by_ministry[item["ministry"]]["classified_count"],
                -item["topic_count"],
                item["ministry"].lower(),
            ),
        )
        _runtime_set(cache_key, result)
        return result
    except Exception as e:
        logger.error("get_issue_ministries failed: %s", e)
        return []


def get_issue_topics(ministry: str, tenant_id: Optional[int] = None, state_override: Optional[str] = None) -> list[dict]:
    state = _resolved_state(tenant_id, state_override)
    cache_key = f"sansadai:topics:{_norm(ministry)}::{_norm(state)}"
    cached = _runtime_get(cache_key)
    if cached is not None:
        return cached

    try:
        rows = _fetch_ministry_answer_rows(ministry)
        aggregates: dict[str, dict] = {}
        state_lc = (state or "").lower()
        for row in rows:
            topic = _effective_topic_for_row(row)
            entry = aggregates.setdefault(topic, {
                "topic": topic,
                "total_count": 0,
                "latest_activity": None,
                "state_count": 0,
            })
            entry["total_count"] += 1
            if row.get("date_asked") and (entry["latest_activity"] is None or row["date_asked"] > entry["latest_activity"]):
                entry["latest_activity"] = row["date_asked"]
            if state_lc and state_lc in (row.get("answer_text") or "").lower():
                entry["state_count"] += 1

        topic_rows = sorted(
            aggregates.values(),
            key=lambda row: (
                -row["total_count"],
                -(row["latest_activity"].toordinal() if row["latest_activity"] else 0),
                row["topic"],
            ),
        )
        topic_names = [row["topic"] for row in topic_rows if row["topic"]]
        cached_topics: set[str] = set()
        stale_topics: set[str] = set()
        if topic_names:
            try:
                with engine.connect() as conn:
                    cache_rows = conn.execute(text("""
                        SELECT DISTINCT ON (topic) topic, is_stale
                        FROM issue_intelligence_cache
                        WHERE ministry = :ministry
                          AND topic = ANY(:topics)
                          AND state = :state
                        ORDER BY topic, is_stale ASC
                    """), {"ministry": ministry, "topics": topic_names, "state": state}).mappings().all()
                for item in cache_rows:
                    if item["is_stale"]:
                        stale_topics.add(item["topic"])
                    else:
                        cached_topics.add(item["topic"])
            except Exception as e:
                logger.warning(
                    "get_issue_topics cache lookup failed for %s / %s: %s",
                    ministry,
                    state or "national",
                    e,
                )

        result = []
        for row in topic_rows:
            topic = row["topic"]
            if topic in cached_topics:
                intel_status = "ready"
            elif topic in stale_topics:
                intel_status = "stale"
            else:
                intel_status = "pending"
            result.append({
                "topic": topic,
                "latest_activity": row["latest_activity"].isoformat() if row["latest_activity"] else None,
                "state_has_mentions": bool(int(row.get("state_count") or 0)) if state else False,
                "intel_status": intel_status,
            })

        _runtime_set(cache_key, result)
        return result
    except Exception as e:
        logger.error("get_issue_topics(%s) failed: %s", ministry, e)
        return []


def get_issue_intelligence(
    ministry: str,
    topic: str,
    tenant_id: Optional[int] = None,
    state_override: Optional[str] = None,
) -> dict:
    state = _resolved_state(tenant_id, state_override)
    rt_key = f"sansadai:intel:{_generation_key(ministry, topic, state)}"

    cached = _runtime_get(rt_key)
    if cached is not None:
        return cached

    db_cache = _load_db_cache(ministry, topic, state)

    def _result(intel, is_stale=False, generated_at=None, no_data=False, pending=False):
        return {
            "ministry": ministry,
            "topic": topic,
            "state": state or None,
            "intel": intel,
            "is_stale": is_stale,
            "generated_at": generated_at.isoformat() if generated_at else None,
            "no_data": no_data,
            "pending": pending,
        }

    if db_cache and db_cache.get("structured_intel") and not db_cache.get("is_stale"):
        result = _result(db_cache["structured_intel"], False, db_cache.get("generated_at"))
        _runtime_set(rt_key, result)
        return result

    if db_cache and db_cache.get("structured_intel") and db_cache.get("is_stale"):
        _schedule_regeneration(ministry, topic, state)
        return _result(db_cache["structured_intel"], True, db_cache.get("generated_at"))

    if _count_issue_answers(ministry, topic) < 1:
        return _result(None, False, None, True, False)

    _schedule_regeneration(ministry, topic, state)
    result = _result(None, False, None, False, True)
    _runtime_set(rt_key, result)
    return result


def mark_stale_issue_briefs(new_pq_ids: list[int]):
    if not new_pq_ids:
        return
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT DISTINCT id, TRIM(ministry) AS ministry, topic, subject, topic_tags
                FROM global_parliamentary_questions
                WHERE id = ANY(:ids)
                  AND ministry IS NOT NULL AND ministry != ''
                  AND answer_text IS NOT NULL AND answer_text != ''
            """), {"ids": new_pq_ids}).mappings().all()
        if not rows:
            return

        with engine.begin() as conn:
            for row in rows:
                topic = _effective_topic_for_row(dict(row))
                conn.execute(text("""
                    UPDATE issue_intelligence_cache
                    SET is_stale = true
                    WHERE ministry = :ministry
                      AND topic = :topic
                      AND is_stale = false
                """), {"ministry": row["ministry"], "topic": topic})

        _runtime_cache.clear()
        logger.info("Marked %d SansadAI issue briefs stale", len(rows))
    except Exception as e:
        logger.warning("mark_stale_issue_briefs failed (non-fatal): %s", e)
