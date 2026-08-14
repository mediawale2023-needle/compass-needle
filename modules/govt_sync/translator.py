"""
modules/govt_sync/translator.py — AI translation layer.

Turns a raw citizen grievance (WhatsApp text, often informal/mixed-language)
into a portal-ready submission: correct department (from the portal's own
hand-verified taxonomy — never inferred freely), formal register, char-limit
compliant, and stripped of any constituent PII beyond what's needed to
describe the issue location.

The department classifier is the part that actually determines whether this
scales — get department_taxonomy right per portal (see modules/data/govt_portals.json)
and the rest is templating. Wrong department = grievance goes nowhere and
nobody finds out for weeks, so callers MUST use portal.department_taxonomy
values verbatim; the LLM is constrained to that enum, not free text.
"""
import json
import logging

from core.gemini_client import get_gemini_client
from modules.auth import sanitize_prompt_input

logger = logging.getLogger("needle.govt_sync.translator")

TRANSLATION_PROMPT_TEMPLATE = """You are formatting a constituent grievance for submission to {portal_name}, a
government grievance-redressal portal. Output ONLY a single JSON object, no
markdown, matching this exact shape:

{{
  "department": "<one of the valid department values below, chosen by best fit>",
  "subject": "<plain factual summary, max {subject_max_chars} chars>",
  "description": "<formal register description, max {description_max_chars} chars>",
  "priority_category": "<'senior_citizen' | 'women' | 'disability' | null>"
}}

Rules:
- "department" MUST be copied verbatim from this list — do not invent a new value:
{department_list}
- "subject": plain factual summary, no salutation, max {subject_max_chars} characters.
- "description": formal register, third person, no constituent phone number
  or personal identifiers beyond what's needed to describe the issue and its
  location. Do not include the constituent's name unless it appeared in the
  location description itself.
- "priority_category": set ONLY if the grievance clearly and explicitly
  involves a senior citizen, a woman, a person with disability, or a similar
  flagged group. Do not guess — leave null if unclear.

Resolved location: district={district}, sub-district/ULB={ulb}

<constituent_grievance>
{raw_grievance}
</constituent_grievance>
"""


def _department_list_text(department_taxonomy: dict) -> str:
    return "\n".join(f'- "{v}"' for v in department_taxonomy.values())


def translate_for_portal(
    raw_grievance: str,
    category: str,
    district: str,
    ulb: str,
    portal_name: str,
    department_taxonomy: dict,
    field_schema: dict,
) -> dict | None:
    """Return a dict shaped like PortalSubmission, or None on failure.

    department_taxonomy is portal.department_taxonomy — {needle_category: portal_dept_value}.
    If Needle's own classifier already resolved `category`, that's a strong
    prior and is passed as a hint, but the LLM still must pick from the
    portal's own valid values in case the grievance content reads differently
    once translated to formal register.
    """
    client = get_gemini_client()
    if not client:
        logger.error("Gemini client unavailable — GEMINI_API_KEY missing, cannot translate for govt portal")
        return None

    if not department_taxonomy:
        logger.error(f"Portal '{portal_name}' has no department_taxonomy configured — refusing to translate")
        return None

    subject_max = int(field_schema.get("subject_max_chars", 100))
    description_max = int(field_schema.get("description_max_chars", 1000))

    hinted_dept = department_taxonomy.get(category)
    prompt = TRANSLATION_PROMPT_TEMPLATE.format(
        portal_name=portal_name,
        subject_max_chars=subject_max,
        description_max_chars=description_max,
        department_list=_department_list_text(department_taxonomy),
        district=district or "unknown",
        ulb=ulb or "unknown",
        raw_grievance=sanitize_prompt_input(raw_grievance or ""),
    )
    if hinted_dept:
        prompt += f'\nNeedle\'s own classifier suggests department "{hinted_dept}" — use it unless the grievance text clearly points elsewhere.\n'

    try:
        from google.genai import types as genai_types

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt],
            config=genai_types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
            ),
        )
        result = json.loads(response.text.strip())
    except json.JSONDecodeError:
        logger.exception(f"Gemini returned invalid JSON for govt portal translation (portal={portal_name})")
        return None
    except Exception as e:
        logger.error(f"Govt portal translation failed (portal={portal_name}): {e}")
        return None

    department = str(result.get("department") or "").strip()
    if department not in department_taxonomy.values():
        # Never let the LLM's free-text guess reach the portal — fall back to
        # Needle's own taxonomy hint, or fail closed.
        if hinted_dept:
            logger.warning(
                f"Govt translation returned unrecognised department '{department}' for portal={portal_name} — "
                f"falling back to taxonomy hint '{hinted_dept}'"
            )
            department = hinted_dept
        else:
            logger.error(f"Govt translation returned unrecognised department '{department}' with no fallback — refusing")
            return None

    subject = str(result.get("subject") or "").strip()[:subject_max]
    description = str(result.get("description") or "").strip()[:description_max]
    priority_category = result.get("priority_category")
    if priority_category not in ("senior_citizen", "women", "disability"):
        priority_category = None

    if not subject or not description:
        logger.error(f"Govt translation produced empty subject/description (portal={portal_name})")
        return None

    return {
        "department": department,
        "district": district,
        "subdistrict_or_ulb": ulb,
        "subject": subject,
        "description": description,
        "priority_category": priority_category,
    }
