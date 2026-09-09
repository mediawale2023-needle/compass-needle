"""
modules/govt_sync/orchestrator.py — shared, single-case government-status
persistence sequence.

BACKGROUND: docs/GOVERNMENT_PORTAL_ARCHITECTURE_AUDIT.md (Part F, Part O,
Part P Phase 1) found that api_router.py's on-demand `POST /cases/{id}/
govt/poll` endpoint and modules/govt_sync/poller.py's unattended
`poll_all_pending()` sweep each independently implemented the SAME
"a status check just succeeded — now persist it" sequence: compute whether
the normalized status actually changed, update `cases.govt_status`/
`govt_status_updated_at` only if so, write a `govt_submission_log`
'status_polled' audit row, and persist a `govt_status_snapshots` row. This
module is that sequence, extracted once, called from both places.

SCOPE — DELIBERATELY NARROW. This module owns ONLY the part of the two
callers' behavior that was already byte-for-byte identical (module the
`actor_username` each caller already supplies differently). Everything
else that differs between the two callers stays in the caller, unchanged:

  * Resolving the portal/adapter (`get_adapter()`) — caller's job.
  * Calling `adapter.check_status(...)` itself, and how each caller
    reacts to it raising — on-demand lets the exception propagate
    uncaught; the background poller catches it, warns, and continues the
    batch. This module is never in the call stack for that decision: it
    is only ever invoked with an ALREADY-OBTAINED, ALREADY-SUCCESSFUL
    `StatusResult` (`result.checked` and `result.status` both truthy).
  * Deciding a result is `needs_verification` or otherwise inconclusive,
    and how that gets logged — the two callers' payload shapes for those
    branches genuinely differ today (background's carries an extra
    `govt_status_at_time` key; see the architecture audit) and this
    extraction does not touch or unify either of them.
  * `supports_unattended_status_check` gating, the background sweep's
    `skip_pairs` optimization, batch counters, and its 4-6h cadence —
    all `poller.py`'s job.
  * `[GOVT_STATUS_DIAG]` diagnostic tracing, HTTP request/response
    shaping, and authentication — all `api_router.py`'s job. This module
    performs no logging beyond a best-effort `logger.exception()` if the
    (already independently try/excepted) snapshot persistence step fails,
    matching both callers' pre-existing behavior of never letting a
    snapshot-persistence failure surface to anything above it.
  * Status normalization, portal adapters, browser/session lifecycle,
    OTP/CAPTCHA flows, citizen notification, resolution review, and any
    SLA/escalation logic — none of that lives here, and none of it is
    planned to move here later without a fresh, explicit decision.

`case_row` accepts either caller's existing SELECT shape (they already
share every column this function reads: `govt_status`, `portal_id` or
`govt_portal_id`, `portal_name`, `portal_type`, `status_check_adapter`,
`status_check_url`, `base_url`, `govt_reference_number` — the two callers'
row dicts only disagree on unrelated columns neither one needs from here,
e.g. the background sweep's own `case_id`/`tenant_id` keys, which is why
those are passed as explicit parameters instead of read off the row).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import text

logger = logging.getLogger("needle.govt_sync.orchestrator")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _payload_expr(engine, bind_name: str) -> str:
    if getattr(getattr(engine, "dialect", None), "name", "") == "sqlite":
        return f":{bind_name}"
    return f"CAST(:{bind_name} AS JSONB)"


def _status_poll_payload(case_row: dict, result) -> dict:
    """Identical shape to what both callers already built independently
    (api_router.py's _govt_status_poll_payload / poller.py's
    _status_poll_payload) — moved here verbatim, not redesigned."""
    return {
        "old_status": case_row.get("govt_status"),
        "new_status": result.status,
        "raw_portal_status": result.raw_portal_status,
        "portal_detail": getattr(result, "portal_detail", None) or {},
        "portal": case_row.get("portal_name"),
        "changed": result.status != case_row.get("govt_status"),
    }


def persist_successful_status_result(
    *,
    tenant_id: int,
    case_id: int,
    case_row: dict,
    result,
    actor_username: str | None = None,
) -> bool:
    """The shared core: given a StatusResult the caller has ALREADY
    confirmed is a genuine success (`result.checked` and `result.status`
    both truthy — this function does not check either), performs:

      1. compute whether the normalized status actually changed
      2. update cases.govt_status / govt_status_updated_at iff changed
      3. write the govt_submission_log 'status_polled' audit row
      4. persist a govt_status_snapshot (best-effort; a persistence
         failure here is logged and swallowed, never raised, matching
         both callers' existing behavior)

    Steps 2 and 3 are performed inside one transaction — the two callers
    previously did this in one transaction (the background sweep) or two
    (the on-demand endpoint) respectively; combining them into one is not
    independently observable by any caller in the non-crash case (the
    same two writes still happen, in the same order, with the same final
    values) and is the more correct of the two pre-existing shapes.

    `actor_username` is the one caller-supplied value that legitimately
    differs and is passed straight through as both the audit row's
    `actor_username` and the snapshot's `created_by` — the on-demand
    endpoint passes the real authenticated username; the background
    sweep passes None (no human triggered it).

    Returns whether the status actually changed, so each caller can build
    its own response/summary shape — this function owns no HTTP response
    construction and no batch/pending-case selection.
    """
    from sansadx_backend.db import engine

    changed = result.status != case_row.get("govt_status")
    payload_expr = _payload_expr(engine, "payload")
    with engine.begin() as conn:
        if changed:
            conn.execute(
                text(
                    "UPDATE cases SET govt_status = :status, govt_status_updated_at = :now "
                    "WHERE id = :cid AND tenant_id = :tid"
                ),
                {"status": result.status, "now": _utcnow(), "cid": case_id, "tid": tenant_id},
            )
        conn.execute(
            text(
                "INSERT INTO govt_submission_log (tenant_id, case_id, action, actor_username, payload, created_at) "
                f"VALUES (:tid, :cid, 'status_polled', :actor, {payload_expr}, :now)"
            ),
            {
                "tid": tenant_id,
                "cid": case_id,
                "actor": actor_username,
                "payload": json.dumps(_status_poll_payload(case_row, result), default=str),
                "now": _utcnow(),
            },
        )

    try:
        from modules.govt_sync.status_snapshot import persist_status_snapshot

        persist_status_snapshot(
            tenant_id=tenant_id,
            case_id=case_id,
            portal_id=case_row.get("portal_id") or case_row.get("govt_portal_id"),
            reference_number=case_row.get("govt_reference_number"),
            adapter_key=case_row.get("status_check_adapter") or case_row.get("portal_type"),
            result=result,
            portal_name=case_row.get("portal_name"),
            source_url=case_row.get("status_check_url") or case_row.get("base_url"),
            created_by=actor_username,
        )
    except Exception:
        logger.exception("Govt status snapshot observer failed tenant=%s case=%s", tenant_id, case_id)

    return changed
