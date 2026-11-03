"""
modules/govt_sync/delhi_ai.py — AI *suggestions* of a Delhi department and category.

A suggestion is never a selection. The model is constrained to choose a value copied verbatim from the
portal's own catalogue (modules/data/delhi_catalogue.json); anything else it returns is discarded, so a
made-up department or category can never reach a worksheet. The caller stores the result with
source="ai_suggested" and staff must confirm it (delhi_filing.validate_filing refuses an unconfirmed one).
No network request to the government portal is made here.
"""
import json
import logging

from core.gemini_client import get_gemini_client
from modules.auth import sanitize_prompt_input
from modules.govt_sync import delhi_filing

logger = logging.getLogger("needle.govt_sync.delhi_ai")

_DEPT_PROMPT = """You help an Indian MP's office choose the government department for a constituent grievance
that will be filed on the Delhi CM Jan Sunwai portal. Output ONLY a JSON object: {{"department": "<one value copied
EXACTLY from the list below, or null if none clearly fits>"}}.

Valid departments (copy exactly, one per line):
{departments}

<constituent_grievance>
{grievance}
</constituent_grievance>
"""

_CAT_PROMPT = """The grievance below will be filed with the department "{department}" on the Delhi CM Jan Sunwai portal.
Output ONLY a JSON object: {{"category": "<one value copied EXACTLY from the list below, or null if none clearly fits>"}}.

Valid categories (copy exactly, one per line):
{categories}

<constituent_grievance>
{grievance}
</constituent_grievance>
"""


def _ask(prompt: str) -> dict | None:
    client = get_gemini_client()
    if not client:
        logger.error("Gemini client unavailable — cannot suggest a Delhi department")
        return None
    try:
        from google.genai import types as genai_types
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt],
            config=genai_types.GenerateContentConfig(temperature=0.0, response_mime_type="application/json"),
        )
        out = json.loads(response.text.strip())
        return out if isinstance(out, dict) else None
    except Exception as e:  # network, quota, bad JSON ...
        logger.error(f"Delhi suggestion failed: {e}")
        return None


def suggest_department_and_category(raw_grievance: str) -> dict | None:
    """{"department": str|None, "category": str|None} with every value verified against the catalogue,
    or None if the AI could not be reached. A department/category the catalogue does not contain is dropped."""
    grievance = sanitize_prompt_input(raw_grievance or "")
    names = [d["name"] for d in delhi_filing.list_departments()]
    got = _ask(_DEPT_PROMPT.format(departments="\n".join(names), grievance=grievance))
    if got is None:
        return None
    dept = got.get("department")
    dept = dept.strip() if isinstance(dept, str) and dept.strip() in names else None
    category = None
    if dept:
        info = delhi_filing.get_categories(dept) or {}
        texts = [c["text"] for c in info.get("categories", [])]
        if texts:
            got_c = _ask(_CAT_PROMPT.format(department=dept, categories="\n".join(texts), grievance=grievance))
            cand = (got_c or {}).get("category")
            category = cand.strip() if isinstance(cand, str) and cand.strip() in texts else None
    return {"department": dept, "category": category}
