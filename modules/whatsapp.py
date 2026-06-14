"""
Meta WhatsApp Cloud API — outbound message helper.

Extracted into its own module to avoid circular imports between main.py and api_router.py.
"""

import os
import json
import logging
import requests as http_requests
from datetime import datetime

from sansadx_backend.db import SessionLocal, WAOutboundMessage

logger = logging.getLogger("needle.whatsapp")


def _utcnow() -> datetime:
    return datetime.utcnow()


def _json_safe(value):
    if value is None:
        return None
    try:
        json.dumps(value, default=str)
        return value
    except Exception:
        return {"value": str(value)}


def _upsert_outbound_log(
    *,
    log_id: int | None,
    tenant_id: int | None,
    case_id: int | None,
    to_number: str,
    phone_number_id: str | None,
    body_text: str,
    template_key: str | None,
    initiated_by: str | None,
    initiated_via: str | None,
    payload: dict,
) -> int | None:
    db = SessionLocal()
    try:
        now = _utcnow()
        if log_id:
            row = db.query(WAOutboundMessage).filter(WAOutboundMessage.id == log_id).first()
            if not row:
                raise ValueError(f"Outbound WhatsApp log {log_id} not found")
        else:
            row = WAOutboundMessage(created_at=now)
            db.add(row)

        row.tenant_id = tenant_id
        row.case_id = case_id
        row.to_number = to_number
        row.phone_number_id = phone_number_id
        row.message_body = body_text
        row.template_key = template_key
        row.initiated_by = initiated_by
        row.initiated_via = initiated_via
        row.request_payload = _json_safe(payload) or {}
        row.attempt_count = int(row.attempt_count or 0) + 1
        row.last_attempt_at = now
        row.updated_at = now
        row.last_error = None
        row.meta_response = {}
        row.meta_message_id = None
        row.sent_at = None
        row.status = "retrying" if row.attempt_count > 1 else "pending"
        db.commit()
        db.refresh(row)
        return row.id
    except Exception:
        db.rollback()
        logger.exception("Failed to persist outbound WhatsApp pre-send log")
        return None
    finally:
        db.close()


def _finalize_outbound_log(
    *,
    log_id: int | None,
    status: str,
    meta_response=None,
    meta_message_id: str | None = None,
    last_error: str | None = None,
) -> None:
    if not log_id:
        return
    db = SessionLocal()
    try:
        row = db.query(WAOutboundMessage).filter(WAOutboundMessage.id == log_id).first()
        if not row:
            return
        row.status = status
        row.meta_response = _json_safe(meta_response) or {}
        row.meta_message_id = meta_message_id
        row.last_error = last_error
        row.updated_at = _utcnow()
        if status == "sent":
            row.sent_at = row.updated_at
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to update outbound WhatsApp log %s", log_id)
    finally:
        db.close()


def send_whatsapp_message(
    to_number: str,
    body_text: str,
    phone_number_id: str | None = None,
    *,
    tenant_id: int | None = None,
    case_id: int | None = None,
    template_key: str | None = None,
    initiated_by: str | None = None,
    initiated_via: str | None = None,
    log_id: int | None = None,
) -> bool:
    """Send a WhatsApp text message via Meta Cloud API.

    Args:
        to_number: Recipient phone number (bare digits, no +).
        body_text: Message body.
        phone_number_id: Meta Phone Number ID for this tenant. Falls back to
            the WHATSAPP_PHONE_NUMBER_ID env var when not provided (single-tenant
            or legacy callers).

    Raises:
        ValueError: if API credentials are not configured.
        RuntimeError: if the Meta API returns an error or the request fails.

    Returns True on success.
    """
    # Per-tenant ID takes priority; fall back to global env var
    phone_number_id = phone_number_id or os.getenv("WHATSAPP_PHONE_NUMBER_ID") or os.getenv("META_PHONE_NUMBER_ID")
    access_token = os.getenv("META_ACCESS_TOKEN")

    # Strip any whatsapp: prefix and leading + — Meta uses bare E.164 digits only
    to_number = to_number.replace("whatsapp:", "").strip()
    if to_number.startswith("+"):
        to_number = to_number[1:]

    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": body_text},
    }
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    log_id = _upsert_outbound_log(
        log_id=log_id,
        tenant_id=tenant_id,
        case_id=case_id,
        to_number=to_number,
        phone_number_id=phone_number_id,
        body_text=body_text,
        template_key=template_key,
        initiated_by=initiated_by,
        initiated_via=initiated_via,
        payload=payload,
    )
    if not phone_number_id or not access_token:
        _finalize_outbound_log(
            log_id=log_id,
            status="failed",
            meta_response={"reason": "missing_credentials"},
            last_error="WhatsApp API credentials not configured",
        )
        logger.error("WHATSAPP_PHONE_NUMBER_ID or META_ACCESS_TOKEN not set.")
        raise ValueError("WhatsApp API credentials not configured")

    url = f"https://graph.facebook.com/v21.0/{phone_number_id}/messages"
    logger.info(f"WhatsApp send → to={to_number} phone_number_id={phone_number_id}")

    try:
        resp = http_requests.post(url, json=payload, headers=headers, timeout=10)
        if resp.ok:
            meta_json = resp.json()
            msg_id = meta_json.get("messages", [{}])[0].get("id", "unknown")
            _finalize_outbound_log(
                log_id=log_id,
                status="sent",
                meta_response=meta_json,
                meta_message_id=msg_id,
            )
            logger.info(f"WhatsApp reply sent to {to_number} (id={msg_id})")
            return True
        else:
            error_detail = resp.text[:500]
            _finalize_outbound_log(
                log_id=log_id,
                status="failed",
                meta_response={"status_code": resp.status_code, "body": error_detail},
                last_error=f"Meta API error {resp.status_code}: {error_detail}",
            )
            logger.error(f"Meta send failed: {resp.status_code} {error_detail}")
            raise RuntimeError(f"Meta API error {resp.status_code}: {error_detail}")
    except http_requests.exceptions.RequestException as e:
        _finalize_outbound_log(
            log_id=log_id,
            status="failed",
            meta_response={"request_error": str(e)},
            last_error=f"WhatsApp send failed: {e}",
        )
        logger.error(f"Meta send error: {e}")
        raise RuntimeError(f"WhatsApp send failed: {e}")


def retry_outbound_message(log_id: int) -> bool:
    db = SessionLocal()
    try:
        row = db.query(WAOutboundMessage).filter(WAOutboundMessage.id == log_id).first()
        if not row:
            raise ValueError("Outbound WhatsApp log not found")
        return send_whatsapp_message(
            row.to_number,
            row.message_body,
            row.phone_number_id,
            tenant_id=row.tenant_id,
            case_id=row.case_id,
            template_key=row.template_key,
            initiated_by=row.initiated_by or "admin_retry",
            initiated_via="admin_retry",
            log_id=row.id,
        )
    finally:
        db.close()
