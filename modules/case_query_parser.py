"""
case_query_parser.py — Natural language query parser for MP/PA WhatsApp case queries.

Converts messages like "Pending water cases in Tilakwadi last 1 month" into
structured filter dicts that case_query_engine.py can execute against the DB.

Uses GPT-4o-mini with a regex fallback so queries still work if OpenAI is down.
"""
import os
import re
import json
import logging
from openai import OpenAI

from core.pii_redaction import redact_pii

logger = logging.getLogger("needle.case_query_parser")

# ── OpenAI client (lazy, same pattern as ai_engine.py) ──────────────────────
def _get_client():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


# ── Prompt ───────────────────────────────────────────────────────────────────
_PARSER_SYSTEM_PROMPT = """\
You are a query parser for an Indian parliamentary constituency case management system.

Extract structured filters from a staff member's natural language query about constituency cases/grievances.

Return ONLY valid JSON with exactly these fields:
{
  "location": "",        // area, ward, village or locality name — empty string if not mentioned
  "constituency": "",    // assembly constituency name — empty string if not mentioned
  "days": 7,            // integer: time range in days (default 7 when not mentioned; 30 for "last month" or "ek mahina"; 1 for "today" or "aaj")
  "issue_type": "",     // category: Water, Road, Electricity, Health, Sanitation, Housing, Land, Education, etc. — empty if not mentioned
  "status": ""          // one of: pending, resolved, in_progress, new — empty if not mentioned
}

Rules:
- "last week" / "ek hapta" = 7 days
- "last month" / "ek mahina" / "pichle mahine" = 30 days
- "last 3 months" = 90 days
- "today" / "aaj" = 1 day
- "last 2 weeks" = 14 days
- Never return null — use empty string "" for unknown text fields and integer 7 for unknown days
- status "in progress" → "in_progress"; "done" / "closed" → "resolved"; "open" / "active" → "pending"
- Do not invent locations or constituencies not present in the query

Examples:
Input: "Cases in Tilakwadi"
Output: {"location": "Tilakwadi", "constituency": "", "days": 7, "issue_type": "", "status": ""}

Input: "Complaints in Tilakwadi last 1 month"
Output: {"location": "Tilakwadi", "constituency": "", "days": 30, "issue_type": "", "status": ""}

Input: "Pending cases in Vikhroli assembly last 7 days"
Output: {"location": "", "constituency": "Vikhroli", "days": 7, "issue_type": "", "status": "pending"}

Input: "Water issues in Ward 5"
Output: {"location": "Ward 5", "constituency": "", "days": 7, "issue_type": "Water", "status": ""}

Input: "Show me all resolved road cases from Bhandup this week"
Output: {"location": "Bhandup", "constituency": "", "days": 7, "issue_type": "Road", "status": "resolved"}
"""

# ── Regex fallback constants ──────────────────────────────────────────────────
_STATUS_MAP = {
    r"\bpending\b":     "pending",
    r"\bopen\b":        "pending",
    r"\bactive\b":      "pending",
    r"\bresolved\b":    "resolved",
    r"\bdone\b":        "resolved",
    r"\bclosed\b":      "resolved",
    r"\bin.progres+\b": "in_progress",
    r"\bongoing\b":     "in_progress",
}

_ISSUE_MAP = {
    r"\bwater\b":        "Water",
    r"\broads?\b":       "Road",
    r"\belectricit\b":   "Electricity",
    r"\blight\b":        "Electricity",
    r"\bsanitation\b":   "Sanitation",
    r"\bdrainage\b":     "Sanitation",
    r"\bhealth\b":       "Health",
    r"\bhousing\b":      "Housing",
    r"\bland\b":         "Land",
    r"\beducation\b":    "Education",
    r"\bschool\b":       "Education",
    r"\btoilet\b":       "Sanitation",
}

_DAY_PATTERNS = [
    (r"\blast\s+(\d+)\s+days?\b",        lambda m: int(m.group(1))),
    (r"\blast\s+(\d+)\s+weeks?\b",       lambda m: int(m.group(1)) * 7),
    (r"\blast\s+(\d+)\s+months?\b",      lambda m: int(m.group(1)) * 30),
    (r"\blast\s+week\b",                 lambda m: 7),
    (r"\blast\s+month\b",                lambda m: 30),
    (r"\bthis\s+month\b",                lambda m: 30),   # FIX P2: "this month" → 30 days (was missing)
    (r"\bthis\s+week\b",                 lambda m: 7),
    (r"\btoday\b|\baaj\b",               lambda m: 1),
    (r"\bek\s+hapta\b",                  lambda m: 7),
    (r"\bek\s+mahina\b",                 lambda m: 30),
    (r"\bpichle\s+(\d+)\s+din\b",        lambda m: int(m.group(1))),
]


def _extract_days(text: str) -> int:
    days = 7
    for pattern, extractor in _DAY_PATTERNS:
        m = re.search(pattern, text)
        if m:
            try:
                days = extractor(m)
            except (ValueError, AttributeError):
                days = 7
            break
    return max(1, min(days, 365))


def _is_generic_case_list_query(message: str) -> bool:
    """Fast path for common staff commands that should list recent cases."""
    text = message.lower().strip()
    has_case_word = re.search(r"\b(cases?|complaints?|grievances?|issues?)\b", text)
    has_list_intent = re.search(r"\b(list|show|send|give|get|dikhao|batao)\b", text)
    has_specific_filter = re.search(
        r"\b(in|from|at|ward|assembly|pending|resolved|closed|done|open|active|"
        r"in\s*progress|water|road|electricity|light|sanitation|drainage|health|"
        r"housing|land|education|school|toilet)\b",
        text,
    )
    return bool(has_case_word and has_list_intent and not has_specific_filter)


def _regex_fallback(message: str) -> dict:
    """Rule-based fallback parser — fast, zero cost, handles common patterns."""
    text = message.lower()

    # Status
    status = ""
    for pattern, val in _STATUS_MAP.items():
        if re.search(pattern, text):
            status = val
            break

    # Issue type
    issue_type = ""
    for pattern, val in _ISSUE_MAP.items():
        if re.search(pattern, text):
            issue_type = val
            break

    days = _extract_days(text)

    # Location: strip known keywords, take remaining capitalised token
    # This is a best-effort extraction — GPT path is preferred
    stripped = re.sub(
        r"\b(cases?|complaints?|issues?|grievances?|in|from|at|last|week|"
        r"month|days?|assembly|ward|pending|resolved|closed|done|open|active|"
        r"list|show|send|give|get|all|me|of|please|water|road|electricity|"
        r"health|sanitation|housing|land|education|today|aaj|dikhao|batao)\b",
        " ", text
    )
    tokens = [t.strip() for t in stripped.split() if len(t.strip()) >= 3]
    location = tokens[0].title() if tokens else ""

    return {
        "location": location,
        "constituency": "",
        "days": days,
        "issue_type": issue_type,
        "status": status,
    }


def parse_query(message: str, tenant_id: int = 1) -> dict:
    """
    Parse a natural language case query into structured filters.

    Returns a dict with keys: location, constituency, days, issue_type, status.
    Never raises — falls back to regex on any error.
    """
    if _is_generic_case_list_query(message):
        result = {
            "location": "",
            "constituency": "",
            "days": _extract_days(message.lower()),
            "issue_type": "",
            "status": "",
        }
        logger.info(
            "Query parsed via generic list fast path: tenant=%s message=%r → %s",
            tenant_id, message[:80], result
        )
        return result

    client = _get_client()

    if client:
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": _PARSER_SYSTEM_PROMPT},
                    # DPDP data-minimisation: phone numbers never appear in a
                    # valid query filter (location/days/issue/status), so strip
                    # them before the text leaves our servers.
                    {"role": "user",   "content": redact_pii(message)},
                ],
                max_tokens=200,
                temperature=0,
            )
            raw = response.choices[0].message.content or "{}"
            parsed = json.loads(raw)

            # Normalise and validate fields
            result = {
                "location":     str(parsed.get("location", "") or "").strip(),
                "constituency": str(parsed.get("constituency", "") or "").strip(),
                "days":         int(parsed.get("days", 7) or 7),
                "issue_type":   str(parsed.get("issue_type", "") or "").strip(),
                "status":       str(parsed.get("status", "") or "").strip().lower(),
            }
            # Clamp days to a sane range
            result["days"] = max(1, min(result["days"], 365))
            logger.info(
                "Query parsed via GPT: tenant=%s message=%r → %s",
                tenant_id, message[:80], result
            )
            return result

        except Exception as exc:
            logger.warning("GPT parse failed (%s), using regex fallback", exc)

    result = _regex_fallback(message)
    logger.info(
        "Query parsed via regex fallback: tenant=%s message=%r → %s",
        tenant_id, message[:80], result
    )
    return result
