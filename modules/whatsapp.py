"""
Meta WhatsApp Cloud API — outbound message helper.

Extracted into its own module to avoid circular imports between main.py and api_router.py.
"""

import os
import logging
import requests as http_requests

logger = logging.getLogger("needle.whatsapp")


def send_whatsapp_message(to_number: str, body_text: str, phone_number_id: str | None = None) -> bool:
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

    if not phone_number_id or not access_token:
        logger.error("WHATSAPP_PHONE_NUMBER_ID or META_ACCESS_TOKEN not set.")
        raise ValueError("WhatsApp API credentials not configured")

    # Strip any whatsapp: prefix and leading + — Meta uses bare E.164 digits only
    to_number = to_number.replace("whatsapp:", "").strip()
    if to_number.startswith("+"):
        to_number = to_number[1:]

    url = f"https://graph.facebook.com/v21.0/{phone_number_id}/messages"
    logger.info(f"WhatsApp send → to={to_number} phone_number_id={phone_number_id}")
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

    try:
        resp = http_requests.post(url, json=payload, headers=headers, timeout=10)
        if resp.ok:
            msg_id = resp.json().get("messages", [{}])[0].get("id", "unknown")
            logger.info(f"WhatsApp reply sent to {to_number} (id={msg_id})")
            return True
        else:
            error_detail = resp.text[:500]
            logger.error(f"Meta send failed: {resp.status_code} {error_detail}")
            raise RuntimeError(f"Meta API error {resp.status_code}: {error_detail}")
    except http_requests.exceptions.RequestException as e:
        logger.error(f"Meta send error: {e}")
        raise RuntimeError(f"WhatsApp send failed: {e}")
