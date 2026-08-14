"""
modules/govt_sync/poller.py — scheduled status polling for grievances that
have been filed on a govt portal.

Deliberately does NOT auto-forward the update to the citizen — that stays a
staff click (POST /api/cases/{id}/govt/notify-citizen via modules/govt_sync/forward.py)
so the rep's office controls exactly when and how the constituent hears
about it. This job only updates the dashboard-visible status.

Run every 4-6 hours — wired into main.py the same way as the other
threading.Timer-based background sweeps (see _schedule_inbound_ledger_sweep).
"""
import logging
from datetime import datetime, timezone

from core.db_helpers import _q
from sansadx_backend.db import engine
from sqlalchemy import text

from modules.govt_sync.adapters import get_adapter

logger = logging.getLogger("needle.govt_sync.poller")

_PENDING_STATUSES = ("submitted", "escalated", "under_review")


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def poll_all_pending() -> dict:
    """Poll every case with an open govt-portal submission. Returns a summary dict."""
    rows = _q(
        """
        SELECT c.id AS case_id, c.tenant_id, c.govt_status, c.govt_reference_number,
               c.govt_portal_id, p.state, p.portal_name, p.portal_type, p.base_url,
               p.status_check_url, p.status_check_mode, p.otp_bound
        FROM cases c
        JOIN govt_portals p ON p.id = c.govt_portal_id
        WHERE c.govt_status = ANY(:statuses)
          AND c.govt_reference_number IS NOT NULL
          AND (c.is_deleted = false OR c.is_deleted IS NULL)
        """,
        {"statuses": list(_PENDING_STATUSES)},
    )

    checked = 0
    changed = 0
    for row in rows:
        adapter = get_adapter(row)
        try:
            result = adapter.check_status(row["govt_reference_number"])
        except Exception as e:
            logger.warning(f"Status poll raised for case={row['case_id']} portal={row['portal_name']}: {e}")
            continue

        checked += 1
        if not result.checked or not result.status:
            continue
        if result.status == row["govt_status"]:
            continue

        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE cases SET govt_status = :status, govt_status_updated_at = :now "
                    "WHERE id = :cid AND tenant_id = :tid"
                ),
                {"status": result.status, "now": _utcnow(), "cid": row["case_id"], "tid": row["tenant_id"]},
            )
            conn.execute(
                text(
                    "INSERT INTO govt_submission_log (tenant_id, case_id, action, actor_username, payload, created_at) "
                    "VALUES (:tid, :cid, 'status_polled', NULL, CAST(:payload AS JSONB), :now)"
                ),
                {
                    "tid": row["tenant_id"],
                    "cid": row["case_id"],
                    "payload": _json_dumps({
                        "old_status": row["govt_status"],
                        "new_status": result.status,
                        "raw_portal_status": result.raw_portal_status,
                        "portal": row["portal_name"],
                    }),
                    "now": _utcnow(),
                },
            )
        changed += 1
        logger.info(
            f"Govt sync poll: case={row['case_id']} portal={row['portal_name']} "
            f"{row['govt_status']} -> {result.status}"
        )

    logger.info(f"Govt sync poll complete: {checked} checked, {changed} changed (of {len(rows)} pending)")
    return {"pending": len(rows), "checked": checked, "changed": changed}


def _json_dumps(d: dict) -> str:
    import json
    return json.dumps(d, default=str)
