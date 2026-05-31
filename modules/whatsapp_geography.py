import logging
import re
from typing import Any, Callable

from modules.localized_replies import get_awaiting_location_reply, get_generic_ack_reply

logger = logging.getLogger(__name__)

_LOW_CONFIDENCE_LEVELS = {"fuzzy", "speech_phonetic"}
_PROTECTED_STATUSES = {"emergency", "offensive", "irrelevant"}


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


def _looks_like_full_message_location(location: str | None, message_body: str) -> bool:
    if not location:
        return False
    normalized_location = re.sub(r"\s+", " ", str(location).strip(" .,:;!?")).lower()
    normalized_message = re.sub(r"\s+", " ", str(message_body or "").strip(" .,:;!?")).lower()
    if not normalized_location or not normalized_message:
        return False
    location_words = normalized_location.split()
    message_words = normalized_message.split()
    if len(location_words) >= 5 and normalized_location == normalized_message:
        return True
    if len(location_words) >= 5 and normalized_location in normalized_message and len(normalized_location) >= max(20, int(len(normalized_message) * 0.65)):
        return True
    if len(location_words) >= max(5, len(message_words) - 1) and len(message_words) >= 5:
        return True
    return False


def _normalize_confidence_level(resolution: dict[str, Any] | None) -> str:
    if not resolution:
        return "unknown"
    value = str(resolution.get("confidence_level") or "").strip().lower()
    if value in {"exact", "boundary", "fuzzy", "speech_phonetic", "manual"}:
        return value

    match_type = str(resolution.get("match_type") or "").strip().lower()
    if match_type == "speech_phonetic":
        return "speech_phonetic"
    if match_type in {"exact_full", "exact_substring", "db_alias_exact", "god_mode"}:
        return "exact"
    if match_type in {"word_boundary", "spaceless", "db_alias_boundary"}:
        return "boundary"
    if match_type.startswith("fuzzy_") or match_type.startswith("fuzzy_phrase"):
        return "fuzzy"

    confidence = str(resolution.get("confidence") or "").strip().lower()
    if confidence == "db_alias_boundary":
        return "boundary"
    if confidence in {"db_alias_exact", "god_mode", "high"}:
        return "exact"
    return "unknown"


def _init_geography_diagnostics(
    *,
    grievance: dict[str, Any],
    tenant_id: int,
    tenant_constituency: str | None,
    message_body: str,
) -> dict[str, Any]:
    diagnostics = grievance.get("geography_diagnostics")
    if not isinstance(diagnostics, dict):
        diagnostics = {}
    diagnostics.setdefault("version", 1)
    diagnostics["tenant_id"] = tenant_id
    diagnostics["tenant_scope"] = tenant_constituency
    diagnostics["message_excerpt"] = str(message_body or "")[:160]
    diagnostics["attempts"] = list(diagnostics.get("attempts") or [])
    return diagnostics


def _record_geography_attempt(
    diagnostics: dict[str, Any],
    *,
    source: str,
    input_text: str | None,
    resolution: dict[str, Any] | None,
    reason: str | None = None,
) -> None:
    resolution = resolution or {}
    diagnostics.setdefault("attempts", []).append(
        {
            "source": source,
            "input_excerpt": str(input_text or "")[:160],
            "location_resolved": bool(resolution.get("location_resolved")),
            "matched_value": _clean_location_candidate(resolution.get("matched_value")) or "",
            "assembly_constituency": str(resolution.get("assembly_constituency") or "").strip(),
            "confidence_level": _normalize_confidence_level(resolution),
            "match_type": str(resolution.get("match_type") or "").strip(),
            "reason": reason or str(resolution.get("reason") or "").strip(),
        }
    )


def _finalize_geography_diagnostics(
    grievance: dict[str, Any],
    diagnostics: dict[str, Any],
    *,
    final_constituency: str | None,
    location_name: str | None,
    status: str,
    review_reason: str | None = None,
) -> None:
    diagnostics["final"] = {
        "location_resolved": bool(location_name and final_constituency and final_constituency != "Unknown"),
        "matched_value": location_name or "",
        "assembly_constituency": final_constituency or "",
        "status": status,
        "geography_confidence": grievance.get("geography_confidence", "unknown"),
        "geography_source": grievance.get("geography_source", "unknown"),
        "needs_geography_review": bool(grievance.get("needs_geography_review")),
        "review_reason": review_reason or grievance.get("geography_review_reason") or "",
    }
    grievance["geography_diagnostics"] = diagnostics


def _apply_resolved_geography(
    *,
    grievance: dict[str, Any],
    resolution: dict[str, Any],
    location_name: str | None,
    source: str,
    status: str,
    political_reply: str,
    detected_language: str,
    message_body: str,
) -> tuple[str | None, str | None, str, str]:
    final_constituency = str(resolution.get("assembly_constituency") or "").strip() or None
    location_name = _clean_location_candidate(resolution.get("matched_value")) or location_name
    confidence_level = _normalize_confidence_level(resolution)

    if location_name:
        grievance["location"] = location_name
    if final_constituency:
        grievance["assembly_constituency"] = final_constituency

    grievance["_match_confidence"] = f"{source}_{confidence_level}"
    grievance["geography_confidence"] = confidence_level
    grievance["geography_source"] = source
    grievance["location_resolved"] = bool(location_name and final_constituency)
    grievance["needs_geography_review"] = confidence_level in _LOW_CONFIDENCE_LEVELS
    grievance.pop("geography_review_reason", None)

    if grievance["needs_geography_review"]:
        grievance["geography_review_reason"] = "low_confidence_match"

    if status not in _PROTECTED_STATUSES:
        status = "pending_review" if grievance["needs_geography_review"] else "new"
        political_reply = get_generic_ack_reply(detected_language, message_body)

    return location_name, final_constituency, status, political_reply


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
    location_required: bool = True,
    resolve_location_fn: Callable[..., dict[str, Any]],
    resolve_constituency_fn: Callable[..., tuple[Any, Any]],
    get_tenant_constituency_fn: Callable[[int], str | None] | None = None,
    assembly_belongs_to_parliamentary_fn: Callable[[str | None, str | None], bool] | None = None,
    resolver_message_body: str | None = None,
) -> dict[str, Any]:
    """
    Final authority for citizen-grievance geography and reply state.

    Deterministic geography decides location/assembly whenever it can. OpenAI
    may classify, summarize, and detect language, but it must not leave a stale
    "need location" reply after deterministic geography succeeds.
    """
    location_name = _clean_location_candidate(grievance.get("location"))
    if _looks_like_full_message_location(location_name, message_body):
        location_name = None
        grievance["location"] = None
    final_constituency = None
    tenant_const = None
    raw_message_geo = {"location_resolved": False}
    diagnostics = _init_geography_diagnostics(
        grievance=grievance,
        tenant_id=current_tenant,
        tenant_constituency=None,
        message_body=message_body,
    )
    try:
        tenant_const = get_tenant_constituency_fn(current_tenant) if get_tenant_constituency_fn else None
        diagnostics["tenant_scope"] = tenant_const
        raw_message_geo = resolve_location_fn(
            resolver_message_body or message_body,
            scope_parliamentary=tenant_const,
            tenant_id=current_tenant,
        )
    except Exception as exc:
        logger.warning("Raw message geography resolution failed: %s", exc)
        _record_geography_attempt(
            diagnostics,
            source="raw_message",
            input_text=resolver_message_body or message_body,
            resolution={"location_resolved": False},
            reason=f"resolver_exception:{exc.__class__.__name__}",
        )
    else:
        _record_geography_attempt(
            diagnostics,
            source="raw_message",
            input_text=resolver_message_body or message_body,
            resolution=raw_message_geo,
        )

    if raw_message_geo.get("location_resolved"):
        location_name, final_constituency, status, political_reply = _apply_resolved_geography(
            grievance=grievance,
            resolution=raw_message_geo,
            location_name=location_name,
            source="raw_message",
            status=status,
            political_reply=political_reply,
            detected_language=detected_language,
            message_body=message_body,
        )

    if not final_constituency:
        ai_constituency = (
            grievance.get("assembly_constituency") or
            grievance.get("constituency") or
            ai_result.get("constituency") or
            ai_result.get("assembly_constituency")
        )
        if ai_constituency and assembly_belongs_to_parliamentary_fn and tenant_const:
            if not assembly_belongs_to_parliamentary_fn(ai_constituency, tenant_const):
                logger.warning(
                    "Rejected AI assembly outside tenant constituency: assembly=%s tenant_constituency=%s tenant=%s",
                    ai_constituency,
                    tenant_const,
                    current_tenant,
                )
                diagnostics["rejected_ai_assembly"] = {
                    "assembly_constituency": ai_constituency,
                    "tenant_scope": tenant_const,
                    "reason": "outside_tenant_scope",
                }
                final_constituency = None
                grievance.pop("assembly_constituency", None)
                grievance.pop("constituency", None)

        location_name = _clean_location_candidate(location_name)
        if location_name:
            grievance["location"] = location_name
        if location_name:
            location_hint_geo = {"location_resolved": False}
            try:
                location_hint_geo = resolve_location_fn(
                    location_name,
                    scope_parliamentary=tenant_const,
                    tenant_id=current_tenant,
                )
            except Exception as exc:
                logger.warning("Location-hint geography resolution failed: %s", exc)
                _record_geography_attempt(
                    diagnostics,
                    source="location_hint",
                    input_text=location_name,
                    resolution={"location_resolved": False},
                    reason=f"resolver_exception:{exc.__class__.__name__}",
                )
            else:
                _record_geography_attempt(
                    diagnostics,
                    source="location_hint",
                    input_text=location_name,
                    resolution=location_hint_geo,
                )

            if location_hint_geo.get("location_resolved"):
                location_name, final_constituency, status, political_reply = _apply_resolved_geography(
                    grievance=grievance,
                    resolution=location_hint_geo,
                    location_name=location_name,
                    source="location_hint",
                    status=status,
                    political_reply=political_reply,
                    detected_language=detected_language,
                    message_body=message_body,
                )
            else:
                _, resolved = resolve_constituency_fn(location_name, current_tenant)
                final_constituency = resolved if resolved and resolved != "Unknown" else None
                if final_constituency:
                    grievance["assembly_constituency"] = final_constituency
                    grievance["_match_confidence"] = "location_hint_boundary"
                    grievance["geography_confidence"] = "boundary"
                    grievance["geography_source"] = "location_hint"
                    grievance["location_resolved"] = True
                    grievance["needs_geography_review"] = False
                    if status not in _PROTECTED_STATUSES:
                        status = "new"
                        political_reply = get_generic_ack_reply(detected_language, message_body)
                else:
                    diagnostics["fallback_constituency_lookup"] = {
                        "input_excerpt": str(location_name or "")[:160],
                        "resolved": False,
                    }

    if not final_constituency:
        final_constituency = "Unknown"
        grievance["assembly_constituency"] = "Unknown"
        grievance["geography_confidence"] = "unknown"
        grievance["geography_source"] = grievance.get("geography_source") or "unknown"
        grievance["location_resolved"] = False
        grievance["needs_geography_review"] = False

    if final_constituency == "Unknown" and location_required and location_name and not is_emergency_complaint:
        status = "awaiting_location"
        political_reply = get_awaiting_location_reply(location_name, detected_language, message_body)

    _finalize_geography_diagnostics(
        grievance,
        diagnostics,
        final_constituency=final_constituency,
        location_name=location_name,
        status=status,
        review_reason=grievance.get("geography_review_reason"),
    )

    return {
        "grievance": grievance,
        "status": status,
        "political_reply": political_reply,
        "location_name": location_name,
        "final_constituency": final_constituency,
        "raw_message_geo": raw_message_geo,
    }
