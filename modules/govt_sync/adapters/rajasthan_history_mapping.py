"""Fixture-only Rajasthan Sampark history mapping.

This module deliberately contains no URL, HTTP client, gateway helper, or
fetch function. Rajasthan history retrieval remains security-blocked; these
pure functions only let local fixtures validate the future normalized shape.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from dateutil import parser as date_parser

from modules.govt_sync.adapters.base import normalize_status_keywords
from modules.govt_sync.portal_history import PortalHistoryDocument, PortalHistoryEvent


def _parse_occurred_at(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = date_parser.parse(str(value), dayfirst=True)
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _documents(value: Any) -> tuple[PortalHistoryDocument, ...]:
    if value in (None, "", 0, "0"):
        return ()
    raw_ids = value if isinstance(value, (list, tuple)) else str(value).split(",")
    result = []
    for raw_id in raw_ids:
        document_id = str(raw_id).strip()
        if document_id and document_id != "0":
            result.append(PortalHistoryDocument(source_document_id=document_id))
    return tuple(result)


def map_rajasthan_history_event(item: dict) -> PortalHistoryEvent:
    raw_status = item.get("complainStatus")
    normalized_status = normalize_status_keywords(str(raw_status or ""))
    from_display = item.get("fromDetails")
    to_display = item.get("toDetails")
    comment = item.get("Remarks")
    routing_changed = bool(
        (from_display or to_display)
        and str(from_display or "").strip() != str(to_display or "").strip()
    )
    if normalized_status in {"resolved", "disposed"}:
        event_type = "resolution"
    elif routing_changed:
        event_type = "routing_update"
    elif comment not in (None, ""):
        event_type = "department_remark"
    elif raw_status not in (None, ""):
        event_type = "status_update"
    else:
        event_type = "portal_history_entry"

    original_date = item.get("FormatDate")
    source_metadata = {
        key: value
        for key, value in {
            "original_occurred_at": original_date if _parse_occurred_at(original_date) is None else None,
            "regional_status": item.get("complainStatusRegional"),
            "regional_from_display": item.get("fromDetailsRegional"),
            "regional_to_display": item.get("toDetailsRegional"),
        }.items()
        if value not in (None, "")
    }
    return PortalHistoryEvent(
        occurred_at=_parse_occurred_at(original_date),
        event_type=event_type,
        status=normalized_status,
        raw_status=raw_status,
        from_display=from_display,
        to_display=to_display,
        comment=comment,
        documents=_documents(item.get("DocId")),
        source="rajasthan_sampark",
        source_metadata=source_metadata or None,
    )


def map_rajasthan_history(items: Any) -> tuple[PortalHistoryEvent, ...]:
    if not isinstance(items, list):
        return ()
    return tuple(map_rajasthan_history_event(item) for item in items if isinstance(item, dict))
