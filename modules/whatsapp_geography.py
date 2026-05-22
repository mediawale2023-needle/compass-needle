import logging
import re
from typing import Any, Callable

from modules.localized_replies import get_awaiting_location_reply, get_generic_ack_reply

logger = logging.getLogger(__name__)


def _clean_location_candidate(value: Any) -> str | None:
    """Keep only a human place name, never an internal OCR/location hint blob."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None

    if re.search(r"\blocation\s*:", text, flags=re.IGNORECASE):
        text = re.split(r"\blocation\s*:", text, maxsplit=1, flags=re.IGNORECASE)[-1].strip()

    # OCR/media hints are stored as "Roman / Original"; prefer the dashboard-safe
    # roman side, while preserving normal detailed locations like "Meerapur Galli".
    if " / " in text:
        text = text.split(" / ", 1)[0].strip()

    text = re.sub(r"\s+", " ", text).strip(" \t\r\n:-")
    if not text:
        return None
    return text


def finalize_geography_decision(
    *,
    grievance: dict[str, Any],
    ai_result: dict[str, Any],
    status: str,
    political_reply: str,
    detected_language: str,
    message_body: str,
    current_tenant: int,
    is_emergency_complaint: bool,
    resolve_location_fn: Callable[..., dict[str, Any]],
    resolve_constituency_fn: Callable[..., tuple[Any, Any]],
    get_tenant_constituency_fn: Callable[[int], str | None] | None = None,
    resolver_message_body: str | None = None,
) -> dict[str, Any]:
    """
    Final authority for citizen-grievance geography and reply state.

    Deterministic geography decides location/assembly whenever it can. OpenAI
    may classify, summarize, and detect language, but it must not leave a stale
    "need location" reply after deterministic geography succeeds.
    """
    location_name = _clean_location_candidate(grievance.get("location"))
    final_constituency = None
    raw_message_geo = {"location_resolved": False}

    try:
        tenant_const = get_tenant_constituency_fn(current_tenant) if get_tenant_constituency_fn else None
        raw_message_geo = resolve_location_fn(
            resolver_message_body or message_body,
            scope_parliamentary=tenant_const,
            tenant_id=current_tenant,
        )
    except Exception as exc:
        logger.warning("Raw message geography resolution failed: %s", exc)

    if raw_message_geo.get("location_resolved"):
        location_name = _clean_location_candidate(raw_message_geo.get("matched_value")) or location_name
        final_constituency = raw_message_geo.get("assembly_constituency")
        grievance["location"] = location_name
        grievance["assembly_constituency"] = final_constituency
        grievance["_match_confidence"] = f"raw_message_{raw_message_geo.get('confidence', 'high')}"
        if status not in ("emergency", "offensive", "irrelevant"):
            status = "new"
            political_reply = get_generic_ack_reply(detected_language, message_body)

    if not final_constituency:
        final_constituency = (
            grievance.get("assembly_constituency") or
            grievance.get("constituency") or
            ai_result.get("constituency") or
            ai_result.get("assembly_constituency")
        )
        location_name = _clean_location_candidate(location_name)
        if location_name:
            grievance["location"] = location_name
        if (not final_constituency or final_constituency == "Unknown") and location_name:
            _, resolved = resolve_constituency_fn(location_name, current_tenant)
            final_constituency = resolved if resolved and resolved != "Unknown" else None

    if not final_constituency:
        final_constituency = "Unknown"

    if final_constituency == "Unknown" and location_name and not is_emergency_complaint:
        status = "awaiting_location"
        political_reply = get_awaiting_location_reply(location_name, detected_language, message_body)

    return {
        "grievance": grievance,
        "status": status,
        "political_reply": political_reply,
        "location_name": location_name,
        "final_constituency": final_constituency,
        "raw_message_geo": raw_message_geo,
    }
