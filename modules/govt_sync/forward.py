"""
modules/govt_sync/forward.py — one-click "forward status update to citizen".

Every message goes out on the rep's existing WhatsApp thread via
modules.whatsapp.send_whatsapp_message — the constituent never sees the
government portal's name in the sender identity, only in the message body
where the department name is useful context.
"""
import json
import logging
from datetime import datetime, timezone

from core.db_helpers import _q_one
from sansadx_backend.db import engine, get_tenant_phone_number_id
from sqlalchemy import text

logger = logging.getLogger("needle.govt_sync.forward")

STATUS_TEMPLATES = {
    "pending_staff_submit": "Your complaint is being prepared for formal submission to {department}. We'll update you once it's filed.",
    "submitted": "Your complaint has been formally registered with {department} (Ref: {ref}). We'll update you as soon as there's movement.",
    "under_review": "Update: {department} is now reviewing your complaint (Ref: {ref}).",
    "escalated": "Update: your complaint (Ref: {ref}) has been escalated with {department} for faster resolution.",
    "resolved": "Good news — {department} has marked your complaint as resolved (Ref: {ref}). Let us know if the issue isn't actually fixed.",
    "rejected": "{department} was unable to act on this complaint (Ref: {ref}). We're looking at next steps — will follow up.",
}


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def forward_status_to_citizen(case_id: int, tenant_id: int, staff_username: str) -> dict:
    """Send the current govt_status update to the case's citizen over WhatsApp.

    Raises ValueError for caller-facing 4xx conditions (no case, no phone,
    no template for current status) so api_router.py can turn those into
    HTTPExceptions without this module importing FastAPI.
    """
    case = _q_one(
        "SELECT id, tenant_id, user_phone, govt_status, govt_department, govt_reference_number "
        "FROM cases WHERE id = :cid AND tenant_id = :tid",
        {"cid": case_id, "tid": tenant_id},
    )
    if not case:
        raise ValueError("Case not found")

    phone = case.get("user_phone")
    if not phone:
        raise ValueError("Cannot notify: citizen phone number missing")

    status = case.get("govt_status") or "not_forwarded"
    template = STATUS_TEMPLATES.get(status)
    if not template:
        raise ValueError(f"No citizen-facing update to send for status '{status}'")

    message = template.format(
        department=case.get("govt_department") or "the department",
        ref=case.get("govt_reference_number") or "pending",
    )

    from modules.whatsapp import send_whatsapp_message
    send_whatsapp_message(phone, message, get_tenant_phone_number_id(tenant_id))

    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE cases SET govt_last_forwarded_to_citizen_at = :now "
                "WHERE id = :cid AND tenant_id = :tid"
            ),
            {"now": _utcnow(), "cid": case_id, "tid": tenant_id},
        )
        conn.execute(
            text(
                "INSERT INTO govt_submission_log (tenant_id, case_id, action, actor_username, payload, created_at) "
                "VALUES (:tid, :cid, 'forwarded_to_citizen', :actor, CAST(:payload AS JSONB), :now)"
            ),
            {
                "tid": tenant_id,
                "cid": case_id,
                "actor": staff_username,
                "payload": json.dumps({"status": status, "message": message}),
                "now": _utcnow(),
            },
        )

    logger.info(f"Govt sync: forwarded status update to citizen — case={case_id} status={status} by={staff_username}")
    return {"message": message}
