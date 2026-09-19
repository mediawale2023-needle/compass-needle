"""Portal-authored grievance history, separate from Needle poll snapshots."""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from sqlalchemy import text

from modules.govt_sync.identity import portal_history_identity

logger = logging.getLogger("needle.govt_sync.portal_history")


class HistoryCapability(str, Enum):
    NOT_SUPPORTED = "not_supported"
    SUPPORTED = "supported"
    SECURITY_BLOCKED = "security_blocked"


class HistoryAvailability(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    TEMPORARILY_UNAVAILABLE = "temporarily_unavailable"


@dataclass(frozen=True)
class PortalHistoryDocument:
    source_document_id: str | None = None
    name: str | None = None
    media_type: str | None = None
    size_bytes: int | None = None
    checksum: str | None = None
    retrieval_state: str = "metadata_only"
    source_metadata: dict | None = None


@dataclass(frozen=True)
class PortalHistoryEvent:
    occurred_at: datetime | None = None
    event_type: str | None = None
    status: str | None = None
    raw_status: str | None = None
    sub_status: str | None = None
    from_department: str | None = None
    from_office: str | None = None
    from_display: str | None = None
    to_department: str | None = None
    to_office: str | None = None
    to_display: str | None = None
    actor: str | None = None
    designation: str | None = None
    comment: str | None = None
    documents: tuple[PortalHistoryDocument, ...] = ()
    source: str = "unknown"
    source_event_id: str | None = None
    source_metadata: dict | None = None


@dataclass(frozen=True)
class PortalHistoryResult:
    availability: HistoryAvailability
    events: tuple[PortalHistoryEvent, ...] = ()
    checked_at: datetime | None = None
    diagnostic_code: str | None = None


@dataclass(frozen=True)
class PortalHistoryPersistResult:
    inserted_event_ids: tuple[int, ...] = ()
    inserted_events: tuple[PortalHistoryEvent, ...] = ()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _json_expr(engine, bind_name: str) -> str:
    if getattr(getattr(engine, "dialect", None), "name", "") == "sqlite":
        return f":{bind_name}"
    return f"CAST(:{bind_name} AS JSONB)"


def _json_param(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, sort_keys=True, default=str, ensure_ascii=False)


def _decode_json(value: Any) -> Any:
    if value is None or not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except Exception:
        return value


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return str(value)


def _event_identity_payload(event: PortalHistoryEvent) -> dict:
    payload = asdict(event)
    payload["occurred_at"] = _iso(event.occurred_at)
    return payload


def is_meaningful_portal_event(event: PortalHistoryEvent) -> bool:
    return any((
        event.status,
        event.raw_status,
        event.sub_status,
        event.from_department,
        event.from_office,
        event.from_display,
        event.to_department,
        event.to_office,
        event.to_display,
        event.actor,
        event.designation,
        event.comment,
        event.documents,
    ))


def persist_portal_history_events(
    *,
    tenant_id: int,
    case_id: int,
    portal_id: int,
    reference_number: str,
    events: tuple[PortalHistoryEvent, ...] | list[PortalHistoryEvent],
    observed_at: datetime | None = None,
) -> PortalHistoryPersistResult:
    """Persist new immutable source events; the unique key is the race arbiter."""
    from sansadx_backend.db import engine

    observed_at = observed_at or _utcnow()
    documents_expr = _json_expr(engine, "documents")
    metadata_expr = _json_expr(engine, "source_metadata")
    inserted_ids: list[int] = []
    inserted_events: list[PortalHistoryEvent] = []

    with engine.begin() as conn:
        for event in events:
            if not is_meaningful_portal_event(event):
                logger.warning(
                    "Skipping malformed portal history event tenant=%s case=%s portal=%s",
                    tenant_id, case_id, portal_id,
                )
                continue
            identity = portal_history_identity(_event_identity_payload(event))
            documents = [asdict(document) for document in event.documents]
            inserted_id = conn.execute(
                text(
                    f"""
                    INSERT INTO govt_portal_history_events (
                        tenant_id, case_id, portal_id, reference_number,
                        event_identity, identity_quality, source, source_event_id,
                        occurred_at, event_type, status, raw_status, sub_status,
                        from_department, from_office, from_display,
                        to_department, to_office, to_display,
                        actor, designation, comment, documents, source_metadata,
                        first_seen_at, last_seen_at, created_at
                    ) VALUES (
                        :tenant_id, :case_id, :portal_id, :reference_number,
                        :event_identity, :identity_quality, :source, :source_event_id,
                        :occurred_at, :event_type, :status, :raw_status, :sub_status,
                        :from_department, :from_office, :from_display,
                        :to_department, :to_office, :to_display,
                        :actor, :designation, :comment, {documents_expr}, {metadata_expr},
                        :first_seen_at, :last_seen_at, :created_at
                    )
                    ON CONFLICT (tenant_id, case_id, portal_id, reference_number, event_identity)
                    DO NOTHING
                    RETURNING id
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "case_id": case_id,
                    "portal_id": portal_id,
                    "reference_number": reference_number,
                    "event_identity": identity["identity"],
                    "identity_quality": identity["identity_quality"],
                    "source": event.source,
                    "source_event_id": event.source_event_id,
                    "occurred_at": event.occurred_at,
                    "event_type": event.event_type,
                    "status": event.status,
                    "raw_status": event.raw_status,
                    "sub_status": event.sub_status,
                    "from_department": event.from_department,
                    "from_office": event.from_office,
                    "from_display": event.from_display,
                    "to_department": event.to_department,
                    "to_office": event.to_office,
                    "to_display": event.to_display,
                    "actor": event.actor,
                    "designation": event.designation,
                    "comment": event.comment,
                    "documents": _json_param(documents),
                    "source_metadata": _json_param(event.source_metadata),
                    "first_seen_at": observed_at,
                    "last_seen_at": observed_at,
                    "created_at": observed_at,
                },
            ).scalar()
            if inserted_id is not None:
                inserted_ids.append(int(inserted_id))
                inserted_events.append(event)
            else:
                conn.execute(
                    text(
                        """
                        UPDATE govt_portal_history_events
                        SET last_seen_at = :last_seen_at
                        WHERE tenant_id = :tenant_id AND case_id = :case_id
                          AND portal_id = :portal_id AND reference_number = :reference_number
                          AND event_identity = :event_identity
                        """
                    ),
                    {
                        "last_seen_at": observed_at,
                        "tenant_id": tenant_id,
                        "case_id": case_id,
                        "portal_id": portal_id,
                        "reference_number": reference_number,
                        "event_identity": identity["identity"],
                    },
                )

    return PortalHistoryPersistResult(tuple(inserted_ids), tuple(inserted_events))


def _row_to_public(row: dict) -> dict:
    documents = _decode_json(row.get("documents")) or []
    public_documents = [
        {
            key: document.get(key)
            for key in (
                "source_document_id", "name", "media_type", "size_bytes",
                "checksum", "retrieval_state",
            )
            if document.get(key) is not None
        }
        for document in documents
        if isinstance(document, dict)
    ]
    return {
        "id": row.get("id"),
        "occurred_at": _iso(row.get("occurred_at")),
        "event_type": row.get("event_type"),
        "status": row.get("status"),
        "raw_status": row.get("raw_status"),
        "sub_status": row.get("sub_status"),
        "from_department": row.get("from_department"),
        "from_office": row.get("from_office"),
        "from_display": row.get("from_display"),
        "to_department": row.get("to_department"),
        "to_office": row.get("to_office"),
        "to_display": row.get("to_display"),
        "actor": row.get("actor"),
        "designation": row.get("designation"),
        "comment": row.get("comment"),
        "documents": public_documents,
        "source": row.get("source"),
        "source_event_id": row.get("source_event_id"),
        "first_seen_at": _iso(row.get("first_seen_at")),
    }


def build_portal_history_response(
    *,
    conn,
    tenant_id: int,
    case: dict,
    limit: int = 25,
    before_id: int | None = None,
) -> dict:
    portal_id = case.get("govt_portal_id") or case.get("portal_id")
    reference_number = case.get("govt_reference_number")
    if not portal_id or not reference_number:
        return {"availability": "unavailable", "events": [], "latest_meaningful_event": None,
                "pagination": {"limit": limit, "next_before_id": None, "has_more": False}}
    params = {
        "tenant_id": tenant_id,
        "case_id": case.get("id"),
        "portal_id": portal_id,
        "reference_number": reference_number,
        "limit_plus_one": limit + 1,
    }
    before_clause = ""
    if before_id is not None:
        cursor = conn.execute(
            text(
                """
                SELECT occurred_at, id
                FROM govt_portal_history_events
                WHERE tenant_id = :tenant_id AND case_id = :case_id
                  AND portal_id = :portal_id AND reference_number = :reference_number
                  AND id = :before_id
                """
            ),
            {**params, "before_id": before_id},
        ).mappings().first()
        if not cursor:
            return {"availability": "unavailable", "events": [], "latest_meaningful_event": None,
                    "pagination": {"limit": limit, "next_before_id": None, "has_more": False}}
        if cursor["occurred_at"] is None:
            before_clause = "AND occurred_at IS NULL AND id < :before_id"
            params["before_id"] = before_id
        else:
            before_clause = (
                "AND (occurred_at < :cursor_occurred_at OR occurred_at IS NULL "
                "OR (occurred_at = :cursor_occurred_at AND id < :before_id))"
            )
            params.update({"before_id": before_id, "cursor_occurred_at": cursor["occurred_at"]})
    rows = conn.execute(
        text(
            f"""
            SELECT * FROM govt_portal_history_events
            WHERE tenant_id = :tenant_id AND case_id = :case_id
              AND portal_id = :portal_id AND reference_number = :reference_number
              {before_clause}
            ORDER BY occurred_at DESC NULLS LAST, id DESC
            LIMIT :limit_plus_one
            """
        ),
        params,
    ).mappings().all()
    has_more = len(rows) > limit
    page = [dict(row) for row in rows[:limit]]
    events = [_row_to_public(row) for row in page]
    return {
        "availability": "available" if events else "unavailable",
        "events": events,
        "latest_meaningful_event": events[0] if events else None,
        "pagination": {
            "limit": limit,
            "next_before_id": page[-1]["id"] if has_more and page else None,
            "has_more": has_more,
        },
    }


def latest_terminal_portal_history_event(
    *, conn, tenant_id: int, case_id: int, portal_id: int | None, reference_number: str | None,
) -> dict | None:
    if not portal_id or not reference_number:
        return None
    row = conn.execute(
        text(
            """
            SELECT * FROM govt_portal_history_events
            WHERE tenant_id = :tenant_id AND case_id = :case_id
              AND portal_id = :portal_id AND reference_number = :reference_number
              AND comment IS NOT NULL AND TRIM(comment) <> ''
              AND (status IN ('resolved', 'disposed') OR event_type = 'resolution')
            ORDER BY occurred_at DESC NULLS LAST, id DESC
            LIMIT 1
            """
        ),
        {"tenant_id": tenant_id, "case_id": case_id, "portal_id": portal_id, "reference_number": reference_number},
    ).mappings().first()
    return _row_to_public(dict(row)) if row else None
