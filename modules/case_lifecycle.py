"""
modules/case_lifecycle.py — the single owner of Needle case-status rules.

Two independent lifecycles live on a case:

  * cases.status       — Needle's internal workflow status.
  * cases.govt_status  — what the government portal reports. Never derived
                         from cases.status and never written here.

Internal status may move to `in_progress` automatically ONLY on verified
external evidence (see EVIDENCE_TYPES). Receipt, AI classification, category
acceptance, assignment, geography, acknowledgements, citizen messages, AI
worksheet preparation, and scheduled-but-unexecuted work are NOT evidence and
never move a case. Staff may still set any canonical status manually — that
is the correction path, validated by `validate_manual_status`.

A portal reporting resolution never resolves a case. Instead the derived
`resolution_verification` flag asks staff to verify; it is computed, not
stored, so every existing status filter and list keeps working.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import text


# Every value Needle itself writes to cases.status.
CANONICAL_STATUSES = frozenset({
    "pending", "new", "awaiting_location", "pending_review", "incomplete",
    "contact_buffered", "emergency", "offensive", "irrelevant", "case_comment",
    "in_progress", "resolved", "completed", "closed",
})

# Retired values still accepted on input and mapped to their successor.
STATUS_ALIASES = {"escalated": "in_progress"}

# Intake/system-only states staff never set by hand.
_SYSTEM_ONLY_STATUSES = frozenset({"contact_buffered"})

# Open, not-yet-progressing states that verified external evidence may move
# to in_progress. Emergency cases are included: urgency lives in is_critical
# / priority / category, which this module never touches.
AUTO_PROGRESS_ELIGIBLE = frozenset({
    "pending", "new", "awaiting_location", "pending_review", "incomplete", "emergency",
})

# Terminal and intent-lane states evidence must never move.
PROTECTED_STATUSES = frozenset({
    "resolved", "completed", "closed", "irrelevant", "offensive", "case_comment",
    "contact_buffered",
})

INTERNALLY_RESOLVED = frozenset({"resolved", "completed", "closed", "irrelevant", "offensive"})

EVIDENCE_GOVT_FILING_RECORDED = "govt_filing_recorded"
EVIDENCE_GOVT_PORTAL_CONFIRMED = "govt_portal_confirmed"
# Reserved for a future forwarding channel that can prove receipt by the
# authority (delivery receipt / acknowledgement / reply). No producer exists
# today; an API call returning without error is never sufficient.
EVIDENCE_AUTHORITY_FORWARD_DELIVERED = "authority_forward_delivered"
EVIDENCE_TYPES = frozenset({
    EVIDENCE_GOVT_FILING_RECORDED,
    EVIDENCE_GOVT_PORTAL_CONFIRMED,
    EVIDENCE_AUTHORITY_FORWARD_DELIVERED,
})

# Portal statuses that prove the grievance exists and is open on the portal.
# resolved/disposed/rejected are deliberately excluded: they never start
# progress (resolution goes through resolution_verification instead).
PORTAL_CONFIRMING_STATUSES = frozenset({
    "submitted", "registered", "under_review", "forwarded", "escalated",
})

_GOVT_FILED_STATUSES = frozenset({
    "submitted", "registered", "forwarded", "under_review",
    "escalated", "resolved", "rejected", "disposed",
})
GOVT_RESOLUTION_STATUSES = frozenset({"resolved", "disposed"})


def normalize_status(value) -> str:
    normalized = str(value or "").strip().lower()
    return STATUS_ALIASES.get(normalized, normalized)


def validate_manual_status(value) -> str:
    """Normalize a staff-requested status; raise ValueError if it is unknown."""
    normalized = normalize_status(value)
    if normalized not in CANONICAL_STATUSES or normalized in _SYSTEM_ONLY_STATUSES:
        raise ValueError(f"Unsupported case status: {value!r}")
    return normalized


def portal_status_confirms_filing(govt_status) -> bool:
    return str(govt_status or "").strip().lower() in PORTAL_CONFIRMING_STATUSES


def apply_external_evidence(
    conn,
    *,
    tenant_id: int,
    case_id: int,
    evidence: str,
    source: dict | None = None,
    now: datetime | None = None,
) -> bool:
    """Move an eligible case to in_progress on verified external evidence.

    Runs on the caller's connection so it commits with the evidence itself.
    Compare-and-set on the observed status makes it atomic against a
    concurrent staff change, idempotent (a case already in_progress is not
    eligible, so repeats are no-ops) and tenant-scoped. Each real move writes
    one case_activity_log 'status_change' row naming the evidence.
    Returns True only when the status actually moved.
    """
    if evidence not in EVIDENCE_TYPES:
        raise ValueError(f"Unknown lifecycle evidence: {evidence!r}")
    row = conn.execute(
        text("SELECT status FROM cases WHERE id = :cid AND tenant_id = :tid"),
        {"cid": case_id, "tid": tenant_id},
    ).fetchone()
    if row is None:
        return False
    observed = row[0]
    if normalize_status(observed) not in AUTO_PROGRESS_ELIGIBLE:
        return False

    now = now or datetime.utcnow()
    moved = conn.execute(
        text(
            "UPDATE cases SET status = 'in_progress', updated_at = :now, status_changed_at = :now "
            "WHERE id = :cid AND tenant_id = :tid AND status = :observed"
        ),
        {"now": now, "cid": case_id, "tid": tenant_id, "observed": observed},
    ).rowcount
    if moved != 1:
        return False

    conn.execute(
        text(
            "INSERT INTO case_activity_log "
            "(tenant_id, case_id, username, action, old_value, new_value, details, created_at) "
            "VALUES (:tid, :cid, :actor, 'status_change', :old, 'in_progress', :details, :now)"
        ),
        {
            "tid": tenant_id,
            "cid": case_id,
            "actor": f"system:{evidence}",
            "old": observed,
            "details": json.dumps({"evidence": evidence, **(source or {})}, default=str),
            "now": now,
        },
    )
    return True


def apply_portal_confirmation(conn, *, tenant_id: int, case_id: int, govt_status, source: dict | None = None) -> bool:
    """Shared rule for every successful portal status check."""
    if not portal_status_confirms_filing(govt_status):
        return False
    return apply_external_evidence(
        conn,
        tenant_id=tenant_id,
        case_id=case_id,
        evidence=EVIDENCE_GOVT_PORTAL_CONFIRMED,
        source={"govt_status": str(govt_status).strip().lower(), **(source or {})},
    )


def cycle_marker(value):
    """Canonical ISO form of govt_status_updated_at.

    A government-resolution review is stamped with this marker; a later
    resolution round has a different marker and starts verification afresh.
    """
    if not value:
        return value
    try:
        if isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return value
        else:
            if not hasattr(value, "isoformat"):
                return value
            dt = value
        if getattr(dt, "tzinfo", None) is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")
    except Exception:
        return value.isoformat() if hasattr(value, "isoformat") else value


def is_govt_filed(case: dict) -> bool:
    if str(case.get("govt_reference_number") or "").strip():
        return True
    return str(case.get("govt_status") or "").strip().lower() in _GOVT_FILED_STATUSES


def resolution_verification(case: dict, reviewed_cycles: Iterable[str] = ()) -> str | None:
    """Derived flag: 'pending' when the portal reports resolution for the
    current round, Needle has not resolved the case, and staff have not yet
    reviewed this round; 'reviewed' once they have; None otherwise."""
    if not is_govt_filed(case):
        return None
    if str(case.get("govt_status") or "").strip().lower() not in GOVT_RESOLUTION_STATUSES:
        return None
    if normalize_status(case.get("status")) in INTERNALLY_RESOLVED:
        return None
    current = cycle_marker(case.get("govt_status_updated_at"))
    if current and current in set(reviewed_cycles or ()):
        return "reviewed"
    return "pending"


def reviewed_cycles_by_case(conn_or_rows) -> dict[int, set[str]]:
    """Group govt_resolution_reviewed activity rows into {case_id: cycles}."""
    cycles: dict[int, set[str]] = {}
    for row in conn_or_rows:
        details = row.get("details")
        try:
            parsed = json.loads(details) if isinstance(details, str) else (details or {})
        except Exception:
            parsed = {}
        marker = parsed.get("govt_status_updated_at") if isinstance(parsed, dict) else None
        if marker:
            cycles.setdefault(row["case_id"], set()).add(str(marker))
    return cycles
