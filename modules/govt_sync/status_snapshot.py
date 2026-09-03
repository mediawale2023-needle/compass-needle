"""
Generic Government Status Snapshot layer.

This module is deliberately observational: it records successful status reads
after the existing govt-sync current-state writes have already happened. It
does not replace cases.govt_status, govt_submission_log, adapters, OTP/CAPTCHA,
or filing behavior.
"""
from __future__ import annotations

import json
import logging
import re
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

logger = logging.getLogger("needle.govt_sync.status_snapshot")

AVAILABILITY_PRESENT = "present"
AVAILABILITY_EXPLICITLY_EMPTY = "explicitly_empty"
AVAILABILITY_UNAVAILABLE = "unavailable"
AVAILABILITY_REDACTED = "redacted"
COMPARABLE_AVAILABILITIES = {AVAILABILITY_PRESENT, AVAILABILITY_EXPLICITLY_EMPTY}

VALID_AVAILABILITIES = {
    AVAILABILITY_PRESENT,
    AVAILABILITY_EXPLICITLY_EMPTY,
    AVAILABILITY_UNAVAILABLE,
    AVAILABILITY_REDACTED,
}
VALID_SOURCES = {"list_card", "detail_page", "api_response", "iframe", "unknown"}
VALID_CONFIDENCE = {"high", "medium", "low", None}

FIELD_EVENT_TYPES = {
    "status": "status_changed",
    "department": "department_changed",
}
OFFICER_FIELD_KEYS = {"officer", "designation"}
COMMUNICATION_FIELD_EVENTS = {"comment": "comment_added", "reply": "reply_added"}

PORTAL_DETAIL_FIELD_MAP = {
    "status_text": ("status", "Portal status", "text"),
    "sub_status_text": ("sub_status", "Sub-status", "text"),
    "department_name": ("department", "Department", "text"),
    "department": ("department", "Department", "text"),
    "category": ("category", "Category", "text"),
    "office": ("office", "Office", "text"),
    "officer": ("officer", "Officer", "text"),
    "designation": ("designation", "Designation", "text"),
    "pendency_details": ("current_position", "Current position", "text"),
    "current_position": ("current_position", "Current position", "text"),
    "grievance_date": ("registration_date", "Registration date", "date"),
    "registration_date": ("registration_date", "Registration date", "date"),
    "last_action_date": ("last_action_date", "Last action date", "date"),
    "disposed_date": ("disposal_date", "Disposal date", "date"),
    "disposal_date": ("disposal_date", "Disposal date", "date"),
    "action_taken_report": ("action_taken_report", "Action Taken Report", "text"),
    "replies": ("reply", "Reply", "json"),
    "documents": ("document", "Document", "json"),
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass(frozen=True)
class GovtStatusField:
    field_key: str
    field_label: str
    field_type: str = "text"
    value_text: str | None = None
    value_json: Any | None = None
    availability: str = AVAILABILITY_PRESENT
    source: str = "unknown"
    selector_or_path: str | None = None
    confidence: str | None = "medium"
    raw_excerpt: str | None = None

    def __post_init__(self):
        if self.availability not in VALID_AVAILABILITIES:
            raise ValueError(f"Invalid govt status field availability: {self.availability}")
        if self.source not in VALID_SOURCES:
            raise ValueError(f"Invalid govt status field source: {self.source}")
        if self.confidence not in VALID_CONFIDENCE:
            raise ValueError(f"Invalid govt status field confidence: {self.confidence}")


@dataclass(frozen=True)
class GovtStatusSnapshotResult:
    normalized_status: str | None = None
    raw_status: str | None = None
    fields: list[GovtStatusField] = field(default_factory=list)
    raw_capture: dict | None = None
    checked: bool = True
    partial: bool = False


@dataclass(frozen=True)
class GovtStatusFieldChange:
    field_key: str
    event_type: str
    old_value_text: str | None = None
    new_value_text: str | None = None
    old_value_json: Any | None = None
    new_value_json: Any | None = None


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text_value = re.sub(r"\s+", " ", str(value)).strip()
    return text_value


def _json_dump(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _public_availability(availability: str | None) -> str:
    return "empty" if availability == AVAILABILITY_EXPLICITLY_EMPTY else (availability or AVAILABILITY_UNAVAILABLE)


def _field_value(field: GovtStatusField | dict) -> Any:
    value_json = field.value_json if isinstance(field, GovtStatusField) else field.get("value_json")
    if value_json is not None:
        if isinstance(value_json, str):
            try:
                return json.loads(value_json)
            except Exception:
                return value_json
        return value_json
    return field.value_text if isinstance(field, GovtStatusField) else field.get("value_text")


def _field_to_public(field: GovtStatusField | dict, *, observed_at: str | None = None, snapshot_id: int | None = None) -> dict:
    availability = field.availability if isinstance(field, GovtStatusField) else field.get("availability")
    field_key = field.field_key if isinstance(field, GovtStatusField) else field.get("field_key")
    field_label = field.field_label if isinstance(field, GovtStatusField) else field.get("field_label")
    field_type = field.field_type if isinstance(field, GovtStatusField) else field.get("field_type")
    return {
        "key": field_key,
        "label": field_label,
        "type": field_type or "text",
        "state": _public_availability(availability),
        "value": _field_value(field) if availability == AVAILABILITY_PRESENT else None,
        "observed_at": observed_at,
        "snapshot_id": snapshot_id,
    }


def _field_from_value(
    field_key: str,
    label: str,
    field_type: str,
    value: Any,
    *,
    source: str = "api_response",
    selector_or_path: str | None = None,
    confidence: str | None = "medium",
) -> GovtStatusField:
    if value is None:
        return GovtStatusField(
            field_key=field_key,
            field_label=label,
            field_type=field_type,
            availability=AVAILABILITY_UNAVAILABLE,
            source=source,
            selector_or_path=selector_or_path,
            confidence=confidence,
        )
    if isinstance(value, str):
        cleaned = _clean_text(value)
        return GovtStatusField(
            field_key=field_key,
            field_label=label,
            field_type=field_type,
            value_text=cleaned or None,
            availability=AVAILABILITY_PRESENT if cleaned else AVAILABILITY_EXPLICITLY_EMPTY,
            source=source,
            selector_or_path=selector_or_path,
            confidence=confidence,
            raw_excerpt=(cleaned[:500] if cleaned else None),
        )
    return GovtStatusField(
        field_key=field_key,
        field_label=label,
        field_type=field_type if field_type != "text" else "json",
        value_json=value,
        availability=AVAILABILITY_PRESENT,
        source=source,
        selector_or_path=selector_or_path,
        confidence=confidence,
    )


def status_result_to_snapshot_result(result) -> GovtStatusSnapshotResult:
    """Compatibility wrapper for the existing StatusResult contract.

    Known limitation: StatusResult.portal_detail is an unstructured, per-
    adapter dict with no fixed schema — a key's total absence can mean
    either "this portal/adapter never reports this field" or "checked, not
    found this time." We cannot distinguish those without a per-portal field
    whitelist (not invented here), so an absent key produces NO field row at
    all (omitted), never a fabricated `unavailable` one. This is safe: both
    are excluded from COMPARABLE_AVAILABILITIES, so omitted and explicit
    `unavailable` are handled identically everywhere that matters (diffing,
    latest_known) — only per-snapshot field listings could tell them apart,
    and inventing that distinction would require guessing at adapter internals.
    """
    fields: list[GovtStatusField] = []
    status = _clean_text(getattr(result, "status", None))
    if status:
        fields.append(_field_from_value("status", "Status", "text", status))

    portal_detail = getattr(result, "portal_detail", None) or {}
    if isinstance(portal_detail, str):
        try:
            portal_detail = json.loads(portal_detail)
        except Exception:
            portal_detail = {}
    if isinstance(portal_detail, dict):
        seen: set[str] = {f.field_key for f in fields}
        for key, value in portal_detail.items():
            mapped = PORTAL_DETAIL_FIELD_MAP.get(key)
            if mapped:
                field_key, label, field_type = mapped
                if field_key in seen:
                    continue
                seen.add(field_key)
            else:
                field_key, label, field_type = f"portal:{key}", key.replace("_", " ").title(), "json" if isinstance(value, (dict, list)) else "text"
            fields.append(
                _field_from_value(
                    field_key,
                    label,
                    field_type,
                    value,
                    source="api_response",
                    selector_or_path=f"portal_detail.{key}",
                )
            )

    return GovtStatusSnapshotResult(
        normalized_status=status,
        raw_status=getattr(result, "raw_portal_status", None),
        fields=fields,
        checked=bool(getattr(result, "checked", False)),
        partial=False,
    )


def build_snapshot_result(result) -> GovtStatusSnapshotResult:
    if isinstance(result, GovtStatusSnapshotResult):
        return result
    return status_result_to_snapshot_result(result)


def _comparable_value(field: GovtStatusField | dict) -> tuple[str, str] | None:
    availability = field.availability if isinstance(field, GovtStatusField) else field.get("availability")
    if availability not in COMPARABLE_AVAILABILITIES:
        return None
    value_json = field.value_json if isinstance(field, GovtStatusField) else field.get("value_json")
    if value_json is not None:
        if isinstance(value_json, str):
            try:
                value_json = json.loads(value_json)
            except Exception:
                pass
        return ("json", _json_dump(value_json))
    value_text = field.value_text if isinstance(field, GovtStatusField) else field.get("value_text")
    return ("text", _clean_text(value_text) or "")


def diff_snapshot_fields(previous_fields: list[GovtStatusField | dict], current_fields: list[GovtStatusField | dict]) -> list[GovtStatusFieldChange]:
    if not previous_fields:
        return []
    previous_by_key = {
        (f.field_key if isinstance(f, GovtStatusField) else f.get("field_key")): f
        for f in previous_fields
    }
    current_by_key = {
        (f.field_key if isinstance(f, GovtStatusField) else f.get("field_key")): f
        for f in current_fields
    }
    changes: list[GovtStatusFieldChange] = []
    officer_change = _diff_officer(previous_by_key, current_by_key)
    if officer_change:
        changes.append(officer_change)
    for current in current_fields:
        key = current.field_key if isinstance(current, GovtStatusField) else current.get("field_key")
        if not key or key.startswith("portal:") or key in OFFICER_FIELD_KEYS or key in COMMUNICATION_FIELD_EVENTS:
            continue
        event_type = FIELD_EVENT_TYPES.get(key)
        if not event_type:
            continue
        previous = previous_by_key.get(key)
        if not previous:
            continue
        old_value = _comparable_value(previous)
        new_value = _comparable_value(current)
        if old_value is None or new_value is None:
            continue
        if old_value == new_value:
            continue
        old_json = previous.value_json if isinstance(previous, GovtStatusField) else previous.get("value_json")
        new_json = current.value_json if isinstance(current, GovtStatusField) else current.get("value_json")
        changes.append(
            GovtStatusFieldChange(
                field_key=key,
                event_type=event_type,
                old_value_text=previous.value_text if isinstance(previous, GovtStatusField) else previous.get("value_text"),
                new_value_text=current.value_text if isinstance(current, GovtStatusField) else current.get("value_text"),
                old_value_json=old_json,
                new_value_json=new_json,
            )
        )
    changes.extend(_diff_communications(previous_by_key, current_by_key))
    return changes


def _officer_payload(fields_by_key: dict, *, include_unavailable: bool = False) -> tuple[dict, dict]:
    payload: dict[str, str | None] = {"name": None, "designation": None}
    comparable: dict[str, bool] = {"name": False, "designation": False}
    for key, payload_key in (("officer", "name"), ("designation", "designation")):
        field = fields_by_key.get(key)
        if not field:
            continue
        availability = field.availability if isinstance(field, GovtStatusField) else field.get("availability")
        if availability in COMPARABLE_AVAILABILITIES:
            comparable[payload_key] = True
            payload[payload_key] = _clean_text(_field_value(field))
        elif include_unavailable:
            payload[payload_key] = None
    return payload, comparable


def _diff_officer(previous_by_key: dict, current_by_key: dict) -> GovtStatusFieldChange | None:
    previous, previous_comparable = _officer_payload(previous_by_key)
    current, current_comparable = _officer_payload(current_by_key)
    changed_parts = [
        part for part in ("name", "designation")
        if previous_comparable.get(part) and current_comparable.get(part)
        and (previous.get(part) or "") != (current.get(part) or "")
    ]
    if not changed_parts:
        return None
    return GovtStatusFieldChange(
        field_key="officer",
        event_type="officer_changed",
        old_value_json={**previous, "changed_parts": changed_parts},
        new_value_json={**current, "changed_parts": changed_parts},
    )


def _normalize_communication_items(value: Any) -> list[dict]:
    if value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            value = [{"text": value}]
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def communication_identity(item: dict) -> dict:
    stable_id = item.get("id") or item.get("portal_message_id") or item.get("message_id")
    if stable_id:
        return {"identity": f"stable:{stable_id}", "identity_quality": "stable"}
    author = _clean_text(item.get("author") or item.get("by") or item.get("sender"))
    posted_at = _clean_text(item.get("posted_at") or item.get("created_at") or item.get("date") or item.get("time"))
    text_value = _clean_text(item.get("text") or item.get("message") or item.get("body") or item.get("reply"))
    if author and posted_at and text_value:
        digest = hashlib.sha256(_json_dump({"author": author, "posted_at": posted_at, "text": text_value}).encode("utf-8")).hexdigest()
        return {"identity": f"derived:{digest}", "identity_quality": "derived"}
    digest = hashlib.sha256(_json_dump(item).encode("utf-8")).hexdigest()
    return {"identity": f"weak:{digest}", "identity_quality": "weak"}


def _communication_identities(field: GovtStatusField | dict | None) -> dict[str, dict]:
    if not field:
        return {}
    availability = field.availability if isinstance(field, GovtStatusField) else field.get("availability")
    if availability != AVAILABILITY_PRESENT:
        return {}
    identities = {}
    for item in _normalize_communication_items(_field_value(field)):
        ident = communication_identity(item)
        identities[ident["identity"]] = {**item, **ident}
    return identities


def _diff_communications(previous_by_key: dict, current_by_key: dict) -> list[GovtStatusFieldChange]:
    changes: list[GovtStatusFieldChange] = []
    for field_key, event_type in COMMUNICATION_FIELD_EVENTS.items():
        previous_items = _communication_identities(previous_by_key.get(field_key))
        current_items = _communication_identities(current_by_key.get(field_key))
        for identity, item in current_items.items():
            if identity in previous_items:
                continue
            changes.append(
                GovtStatusFieldChange(
                    field_key=field_key,
                    event_type=event_type,
                    new_value_json=item,
                )
            )
    return changes


def _json_param(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, sort_keys=True, default=str)


def _json_expr(engine, bind_name: str) -> str:
    if getattr(getattr(engine, "dialect", None), "name", "") == "sqlite":
        return f":{bind_name}"
    return f"CAST(:{bind_name} AS JSONB)"


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        except Exception:
            return value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return str(value)


def _decode_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


def _load_previous_snapshot(conn, current_snapshot_id: int, *, tenant_id: int, case_id: int, portal_id: int, reference_number: str) -> tuple[int | None, list[dict]]:
    previous = conn.execute(
        text(
            """
            SELECT id FROM govt_status_snapshots
            WHERE tenant_id = :tenant_id
              AND case_id = :case_id
              AND portal_id = :portal_id
              AND reference_number = :reference_number
              AND id <> :snapshot_id
              AND snapshot_status IN ('complete', 'partial')
            ORDER BY captured_at DESC, id DESC
            LIMIT 1
            """
        ),
        {
            "tenant_id": tenant_id,
            "case_id": case_id,
            "portal_id": portal_id,
            "reference_number": reference_number,
            "snapshot_id": current_snapshot_id,
        },
    ).mappings().first()
    if not previous:
        return None, []
    rows = conn.execute(
        text(
            """
            SELECT field_key, field_label, field_type, value_text, value_json,
                   availability, source, selector_or_path, confidence, raw_excerpt
            FROM govt_status_snapshot_fields
            WHERE snapshot_id = :snapshot_id
            """
        ),
        {"snapshot_id": previous["id"]},
    ).mappings().all()
    return previous["id"], [dict(row) for row in rows]


def _load_seen_communication_identities(conn, *, tenant_id: int, case_id: int, portal_id: int, reference_number: str) -> set[str]:
    rows = conn.execute(
        text(
            """
            SELECT new_value_json
            FROM govt_status_snapshot_events
            WHERE tenant_id = :tenant_id
              AND case_id = :case_id
              AND portal_id = :portal_id
              AND reference_number = :reference_number
              AND event_type IN ('comment_added', 'reply_added')
            """
        ),
        {
            "tenant_id": tenant_id,
            "case_id": case_id,
            "portal_id": portal_id,
            "reference_number": reference_number,
        },
    ).mappings().all()
    identities = set()
    for row in rows:
        value = _decode_json(row.get("new_value_json")) or {}
        identity = value.get("identity") if isinstance(value, dict) else None
        if identity:
            identities.add(identity)
    return identities


def _load_snapshot_fields(conn, snapshot_ids: list[int]) -> dict[int, list[dict]]:
    if not snapshot_ids:
        return {}
    placeholders = ", ".join(f":sid_{i}" for i in range(len(snapshot_ids)))
    params = {f"sid_{i}": sid for i, sid in enumerate(snapshot_ids)}
    rows = conn.execute(
        text(
            f"""
            SELECT snapshot_id, field_key, field_label, field_type, value_text, value_json,
                   availability, source, selector_or_path, confidence, raw_excerpt
            FROM govt_status_snapshot_fields
            WHERE snapshot_id IN ({placeholders})
            ORDER BY id ASC
            """
        ),
        params,
    ).mappings().all()
    grouped: dict[int, list[dict]] = {}
    for row in rows:
        item = dict(row)
        item["value_json"] = _decode_json(item.get("value_json"))
        grouped.setdefault(item["snapshot_id"], []).append(item)
    return grouped


def _load_latest_known_fields(conn, *, tenant_id: int, case_id: int, portal_id: int, reference_number: str) -> dict[str, dict]:
    """Most recent comparable (present/explicitly_empty) observation per
    field_key across this case's ENTIRE scoped snapshot history — independent
    of any history-page window, so a field's latest known value can never be
    truncated just because it lies outside the current page."""
    rows = conn.execute(
        text(
            """
            SELECT field_key, field_label, field_type, value_text, value_json,
                   availability, source, selector_or_path, confidence, raw_excerpt,
                   snapshot_id, captured_at
            FROM (
                SELECT f.field_key, f.field_label, f.field_type, f.value_text, f.value_json,
                       f.availability, f.source, f.selector_or_path, f.confidence, f.raw_excerpt,
                       f.snapshot_id, s.captured_at,
                       ROW_NUMBER() OVER (
                           PARTITION BY f.field_key
                           ORDER BY s.captured_at DESC, s.id DESC
                       ) AS rn
                FROM govt_status_snapshot_fields f
                JOIN govt_status_snapshots s ON s.id = f.snapshot_id
                WHERE s.tenant_id = :tenant_id
                  AND s.case_id = :case_id
                  AND s.portal_id = :portal_id
                  AND s.reference_number = :reference_number
                  AND s.snapshot_status IN ('complete', 'partial')
                  AND f.availability IN ('present', 'explicitly_empty')
            ) ranked
            WHERE rn = 1
            """
        ),
        {
            "tenant_id": tenant_id,
            "case_id": case_id,
            "portal_id": portal_id,
            "reference_number": reference_number,
        },
    ).mappings().all()
    latest_known: dict[str, dict] = {}
    for row in rows:
        item = dict(row)
        item["value_json"] = _decode_json(item.get("value_json"))
        observed_at = _iso(item.get("captured_at"))
        public_field = _field_to_public(item, observed_at=observed_at, snapshot_id=item.get("snapshot_id"))
        public_field["last_confirmed_at"] = observed_at
        latest_known[item["field_key"]] = public_field
    return latest_known


def _snapshot_to_public(snapshot: dict, fields: list[dict], event_count: int = 0) -> dict:
    observed_at = _iso(snapshot.get("captured_at"))
    return {
        "id": snapshot.get("id"),
        "captured_at": observed_at,
        "snapshot_status": snapshot.get("snapshot_status"),
        "normalized_status": snapshot.get("normalized_status"),
        "raw_status": snapshot.get("raw_status"),
        "fields": {
            field.get("field_key"): _field_to_public(field, observed_at=observed_at, snapshot_id=snapshot.get("id"))
            for field in fields
            if field.get("field_key")
        },
        "event_count": event_count,
    }


def _event_to_public(row: dict) -> dict:
    old_json = _decode_json(row.get("old_value_json")) or {}
    new_json = _decode_json(row.get("new_value_json")) or {}
    event_type = row.get("event_type")
    event = {
        "id": row.get("id"),
        "type": event_type,
        "occurred_at": _iso(row.get("created_at")),
        "snapshot_id": row.get("snapshot_id"),
        "previous_snapshot_id": row.get("previous_snapshot_id"),
    }
    if event_type == "officer_changed":
        changed_parts = new_json.get("changed_parts") or old_json.get("changed_parts") or []
        event.update({
            "from": {"name": old_json.get("name"), "designation": old_json.get("designation")},
            "to": {"name": new_json.get("name"), "designation": new_json.get("designation")},
            "changed_parts": changed_parts,
        })
    elif event_type in {"comment_added", "reply_added"}:
        item = new_json
        event.update({
            "identity": item.get("identity"),
            "identity_quality": item.get("identity_quality") or "weak",
            "parent_id": item.get("parent_id") or item.get("parent"),
            "communication": {
                "author": item.get("author") or item.get("by") or item.get("sender"),
                "text": item.get("text") or item.get("message") or item.get("body") or item.get("reply"),
                "posted_at": item.get("posted_at") or item.get("created_at") or item.get("date") or item.get("time"),
            },
        })
    else:
        event.update({
            "field_key": row.get("field_key"),
            "from": row.get("old_value_text") if row.get("old_value_json") is None else old_json,
            "to": row.get("new_value_text") if row.get("new_value_json") is None else new_json,
        })
    return event


def build_history_response(
    *,
    conn,
    tenant_id: int,
    case: dict,
    limit: int = 25,
    before_snapshot_id: int | None = None,
) -> dict:
    reference_number = case.get("govt_reference_number")
    portal_id = case.get("govt_portal_id") or case.get("portal_id")
    if not reference_number or not portal_id:
        return {
            "case_id": case.get("id"),
            "government_reference_number": reference_number,
            "portal": None,
            "current_state": {
                "needle_govt_status": case.get("govt_status"),
                "needle_govt_status_updated_at": _iso(case.get("govt_status_updated_at")),
                "latest_successful_check_at": None,
                "latest_snapshot_id": None,
            },
            "latest_known": {},
            "latest_snapshot": None,
            "events": [],
            "snapshots": [],
            "pagination": {"limit": limit, "next_before_snapshot_id": None, "has_more": False},
        }

    params = {
        "tenant_id": tenant_id,
        "case_id": case.get("id"),
        "portal_id": portal_id,
        "reference_number": reference_number,
        "limit": limit + 1,
    }
    before_clause = ""
    if before_snapshot_id:
        # Resolve the cursor's own captured_at so the seek predicate matches
        # the declared ORDER BY (captured_at DESC, id DESC) exactly — id
        # alone is not guaranteed to correlate with captured_at (captured_at
        # is computed in Python before the insert transaction, and callers
        # may override it), so a plain `id < cursor` can permanently skip a
        # row whose id is higher but captured_at is earlier. An invalid/
        # foreign cursor (not found for this case/portal/reference) is
        # treated as no cursor at all — least invasive: same page-1 result
        # a client would get by omitting it, no new error/empty-page shape.
        cursor_captured_at = conn.execute(
            text(
                """
                SELECT captured_at FROM govt_status_snapshots
                WHERE id = :before_snapshot_id AND tenant_id = :tenant_id
                  AND case_id = :case_id AND portal_id = :portal_id
                  AND reference_number = :reference_number
                """
            ),
            {
                "before_snapshot_id": before_snapshot_id,
                "tenant_id": tenant_id,
                "case_id": case.get("id"),
                "portal_id": portal_id,
                "reference_number": reference_number,
            },
        ).scalar()
        if cursor_captured_at is not None:
            before_clause = (
                "AND (captured_at < :before_captured_at "
                "OR (captured_at = :before_captured_at AND id < :before_snapshot_id))"
            )
            params["before_captured_at"] = cursor_captured_at
            params["before_snapshot_id"] = before_snapshot_id

    snapshots = [dict(row) for row in conn.execute(
        text(
            f"""
            SELECT id, tenant_id, case_id, portal_id, reference_number, adapter_key,
                   snapshot_status, normalized_status, raw_status, captured_at,
                   source_url, raw_capture_ref, created_by, created_at
            FROM govt_status_snapshots
            WHERE tenant_id = :tenant_id
              AND case_id = :case_id
              AND portal_id = :portal_id
              AND reference_number = :reference_number
              AND snapshot_status IN ('complete', 'partial')
              {before_clause}
            ORDER BY captured_at DESC, id DESC
            LIMIT :limit
            """
        ),
        params,
    ).mappings().all()]
    has_more = len(snapshots) > limit
    page_snapshots = snapshots[:limit]
    snapshot_ids = [row["id"] for row in page_snapshots]
    latest_snapshot = page_snapshots[0] if page_snapshots else None
    fields_by_snapshot = _load_snapshot_fields(conn, snapshot_ids)
    event_rows = [dict(row) for row in conn.execute(
        text(
            """
            SELECT id, tenant_id, case_id, portal_id, reference_number, previous_snapshot_id,
                   snapshot_id, field_key, event_type, old_value_text, new_value_text,
                   old_value_json, new_value_json, created_at
            FROM govt_status_snapshot_events
            WHERE tenant_id = :tenant_id
              AND case_id = :case_id
              AND portal_id = :portal_id
              AND reference_number = :reference_number
              AND (:latest_snapshot_id IS NULL OR snapshot_id <= :latest_snapshot_id)
            ORDER BY created_at DESC, id DESC
            LIMIT :limit
            """
        ),
        {**params, "latest_snapshot_id": latest_snapshot.get("id") if latest_snapshot else None},
    ).mappings().all()]
    event_count_by_snapshot: dict[int, int] = {}
    for event in event_rows:
        event_count_by_snapshot[event["snapshot_id"]] = event_count_by_snapshot.get(event["snapshot_id"], 0) + 1

    latest_known = _load_latest_known_fields(
        conn, tenant_id=tenant_id, case_id=case.get("id"), portal_id=portal_id, reference_number=reference_number,
    )

    public_snapshots = [
        _snapshot_to_public(row, fields_by_snapshot.get(row["id"], []), event_count_by_snapshot.get(row["id"], 0))
        for row in page_snapshots
    ]
    latest_public = public_snapshots[0] if public_snapshots else None
    latest_successful_at = _iso(latest_snapshot.get("captured_at")) if latest_snapshot else None
    return {
        "case_id": case.get("id"),
        "government_reference_number": reference_number,
        "portal": {
            "id": portal_id,
            "name": case.get("portal_name"),
            "state": case.get("portal_state"),
        },
        "current_state": {
            "needle_govt_status": case.get("govt_status"),
            "needle_govt_status_updated_at": _iso(case.get("govt_status_updated_at")),
            "latest_successful_check_at": latest_successful_at,
            "latest_snapshot_id": latest_snapshot.get("id") if latest_snapshot else None,
        },
        "latest_known": latest_known,
        "latest_snapshot": latest_public,
        "events": [_event_to_public(row) for row in event_rows],
        "snapshots": public_snapshots,
        "pagination": {
            "limit": limit,
            "next_before_snapshot_id": page_snapshots[-1]["id"] if has_more and page_snapshots else None,
            "has_more": has_more,
        },
    }


def persist_status_snapshot(
    *,
    tenant_id: int,
    case_id: int,
    portal_id: int,
    reference_number: str,
    adapter_key: str | None,
    result,
    portal_name: str | None = None,
    source_url: str | None = None,
    created_by: str | None = None,
    captured_at: datetime | None = None,
) -> int | None:
    """Best-effort snapshot observer. Never raises to status-check callers."""
    try:
        if not reference_number or not portal_id:
            return None
        snapshot_result = build_snapshot_result(result)
        if not snapshot_result.checked:
            return None
        captured_at = captured_at or _utcnow()
        snapshot_status = "partial" if snapshot_result.partial else "complete"

        from sansadx_backend.db import engine

        value_json_expr = _json_expr(engine, "value_json")
        raw_capture_ref = None
        if snapshot_result.raw_capture:
            # V1 deliberately does not store raw captures. Keep the schema hook
            # nullable until a separate PII-safe raw storage design exists.
            raw_capture_ref = snapshot_result.raw_capture.get("ref")

        with engine.begin() as conn:
            snapshot_id = conn.execute(
                text(
                    """
                    INSERT INTO govt_status_snapshots (
                        tenant_id, case_id, portal_id, reference_number, adapter_key,
                        snapshot_status, normalized_status, raw_status, captured_at,
                        source_url, raw_capture_ref, created_by, created_at
                    ) VALUES (
                        :tenant_id, :case_id, :portal_id, :reference_number, :adapter_key,
                        :snapshot_status, :normalized_status, :raw_status, :captured_at,
                        :source_url, :raw_capture_ref, :created_by, :created_at
                    )
                    RETURNING id
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "case_id": case_id,
                    "portal_id": portal_id,
                    "reference_number": reference_number,
                    "adapter_key": adapter_key or portal_name,
                    "snapshot_status": snapshot_status,
                    "normalized_status": snapshot_result.normalized_status,
                    "raw_status": snapshot_result.raw_status,
                    "captured_at": captured_at,
                    "source_url": source_url,
                    "raw_capture_ref": raw_capture_ref,
                    "created_by": created_by,
                    "created_at": _utcnow(),
                },
            ).scalar()

            for f in snapshot_result.fields:
                conn.execute(
                    text(
                        f"""
                        INSERT INTO govt_status_snapshot_fields (
                            snapshot_id, field_key, field_label, field_type,
                            value_text, value_json, availability, source,
                            selector_or_path, confidence, raw_excerpt
                        ) VALUES (
                            :snapshot_id, :field_key, :field_label, :field_type,
                            :value_text, {value_json_expr}, :availability, :source,
                            :selector_or_path, :confidence, :raw_excerpt
                        )
                        """
                    ),
                    {
                        "snapshot_id": snapshot_id,
                        "field_key": f.field_key,
                        "field_label": f.field_label,
                        "field_type": f.field_type,
                        "value_text": f.value_text,
                        "value_json": _json_param(f.value_json),
                        "availability": f.availability,
                        "source": f.source,
                        "selector_or_path": f.selector_or_path,
                        "confidence": f.confidence,
                        "raw_excerpt": f.raw_excerpt,
                    },
                )

            previous_id, previous_fields = _load_previous_snapshot(
                conn,
                snapshot_id,
                tenant_id=tenant_id,
                case_id=case_id,
                portal_id=portal_id,
                reference_number=reference_number,
            )
            changes = diff_snapshot_fields(previous_fields, snapshot_result.fields)
            seen_communication_ids = _load_seen_communication_identities(
                conn,
                tenant_id=tenant_id,
                case_id=case_id,
                portal_id=portal_id,
                reference_number=reference_number,
            )
            changes = [
                change for change in changes
                if change.event_type not in {"comment_added", "reply_added"}
                or not isinstance(change.new_value_json, dict)
                or change.new_value_json.get("identity") not in seen_communication_ids
            ]
            old_value_json_expr = _json_expr(engine, "old_value_json")
            new_value_json_expr = _json_expr(engine, "new_value_json")
            for change in changes:
                conn.execute(
                    text(
                        f"""
                        INSERT INTO govt_status_snapshot_events (
                            tenant_id, case_id, portal_id, reference_number,
                            previous_snapshot_id, snapshot_id, field_key, event_type,
                            old_value_text, new_value_text, old_value_json, new_value_json,
                            created_at
                        ) VALUES (
                            :tenant_id, :case_id, :portal_id, :reference_number,
                            :previous_snapshot_id, :snapshot_id, :field_key, :event_type,
                            :old_value_text, :new_value_text, {old_value_json_expr}, {new_value_json_expr},
                            :created_at
                        )
                        """
                    ),
                    {
                        "tenant_id": tenant_id,
                        "case_id": case_id,
                        "portal_id": portal_id,
                        "reference_number": reference_number,
                        "previous_snapshot_id": previous_id,
                        "snapshot_id": snapshot_id,
                        "field_key": change.field_key,
                        "event_type": change.event_type,
                        "old_value_text": change.old_value_text,
                        "new_value_text": change.new_value_text,
                        "old_value_json": _json_param(change.old_value_json),
                        "new_value_json": _json_param(change.new_value_json),
                        "created_at": _utcnow(),
                    },
                )
            return snapshot_id
    except Exception:
        logger.exception(
            "Govt status snapshot persistence failed tenant=%s case=%s portal=%s reference=%s",
            tenant_id,
            case_id,
            portal_id,
            reference_number,
        )
        return None
