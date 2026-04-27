"""
pa_alerter.py — PA alert dispatch for emergency surge events.

Handles two alert channels:
  1. WhatsApp text alert
  2. Exotel outbound voice call

State advances only on successful delivery.
"""
import base64
import logging
import os

logger = logging.getLogger("needle.pa_alerter")

_EXOTEL_API_KEY = os.getenv("EXOTEL_API_KEY", "")
_EXOTEL_API_TOKEN = os.getenv("EXOTEL_API_TOKEN", "")
_EXOTEL_SID = os.getenv("EXOTEL_SID", "")
_EXOTEL_CALLER_ID = os.getenv("EXOTEL_CALLER_ID", "")
_EXOTEL_API_HOST = os.getenv("EXOTEL_API_HOST", "api.exotel.com")


def _format_wa_t1(summary: dict) -> str:
    hazard = summary["hazard_type"].upper()
    area = summary["assembly"]
    ward = f", {summary['ward']}" if summary.get("ward") else ""
    count = summary["unique_sender_count"]
    cid = summary["cluster_id"]
    return (
        f"⚠️ POSSIBLE {hazard} — {area}{ward}\n"
        f"{count} unique reports in last 10 min\n"
        f"Status: UNVERIFIED\n"
        f"Cluster #{cid} | Reply ACK {cid} to confirm receipt"
    )


def _format_wa_t2(summary: dict) -> str:
    hazard = summary["hazard_type"].upper()
    area = summary["assembly"]
    ward = f", {summary['ward']}" if summary.get("ward") else ""
    count = summary["unique_sender_count"]
    cid = summary["cluster_id"]
    return (
        f"🚨 SURGE ALERT — {hazard}\n"
        f"Location: {area}{ward}\n"
        f"Reports: {count} unique senders (unverified)\n"
        f"Calling you now. Reply ACK {cid} to stop further alerts."
    )


def _format_wa_t3(summary: dict) -> str:
    hazard = summary["hazard_type"].upper()
    area = summary["assembly"]
    count = summary["unique_sender_count"]
    cid = summary["cluster_id"]
    attempt = summary.get("call_attempt_count", 1)
    return (
        f"🚨 ESCALATION (Attempt {attempt}) — {hazard}\n"
        f"Location: {area}\n"
        f"Reports: {count} unique senders\n"
        f"Main PA not responding. Calling you now.\n"
        f"Reply ACK {cid} to confirm."
    )


def _format_voice_script(summary: dict) -> str:
    hazard = (summary["hazard_type"] or "emergency").replace("_", " ")
    area = summary["assembly"] or "unknown area"
    count = summary["unique_sender_count"]
    return (
        f"Alert for your MP office. Possible {hazard} reported in {area}. "
        f"{count} unique reports received in the last 15 minutes. "
        f"Please open your dashboard immediately. "
        f"This is an automated alert. Repeat: possible {hazard} in {area}."
    )


def _send_wa(phone: str, message: str, phone_number_id):
    """Send WhatsApp alert to PA. Return True on success."""
    if not phone:
        logger.warning("PA phone not configured — cannot send WhatsApp alert")
        return False
    try:
        from modules.whatsapp import send_whatsapp_message

        send_whatsapp_message(phone, message, phone_number_id)
        logger.info("PA WhatsApp alert sent to %s", phone[-4:])
        return True
    except Exception as exc:
        logger.error("PA WhatsApp alert failed for %s: %s", phone[-4:], exc)
        return False


def _trigger_exotel_call(to_phone: str, tts_script: str) -> bool:
    """
    Initiate an outbound Exotel call. Returns True on success.

    If env vars are missing, logs a warning and returns False without raising.
    """
    applet_url = os.getenv("EXOTEL_APPLET_URL", "")
    if not all([_EXOTEL_API_KEY, _EXOTEL_API_TOKEN, _EXOTEL_SID, _EXOTEL_CALLER_ID, applet_url]):
        logger.warning(
            "Exotel call skipped — missing env vars. "
            "Set EXOTEL_API_KEY, EXOTEL_API_TOKEN, EXOTEL_SID, EXOTEL_CALLER_ID, EXOTEL_APPLET_URL."
        )
        return False
    if not to_phone:
        logger.warning("Exotel call skipped — no PA phone number configured")
        return False

    phone = to_phone.strip()
    if phone.startswith("91") and len(phone) == 12:
        phone = "0" + phone[2:]
    elif not phone.startswith("0") and not phone.startswith("+"):
        phone = "0" + phone

    try:
        import requests

        url = f"https://{_EXOTEL_API_HOST}/v1/Accounts/{_EXOTEL_SID}/Calls/connect.json"
        creds = base64.b64encode(f"{_EXOTEL_API_KEY}:{_EXOTEL_API_TOKEN}".encode()).decode()
        resp = requests.post(
            url,
            headers={"Authorization": f"Basic {creds}"},
            data={
                "From": phone,
                "To": phone,
                "CallerId": _EXOTEL_CALLER_ID,
                "Url": applet_url,
                "CustomField": tts_script[:200],
            },
            timeout=10,
        )
        if resp.status_code in (200, 201):
            logger.info("Exotel call initiated to %s", phone[-4:])
            return True
        logger.error("Exotel call failed: status=%s body=%s", resp.status_code, resp.text[:200])
        return False
    except Exception as exc:
        logger.error("Exotel call exception: %s", exc)
        return False


def dispatch_t1_alert(cluster_id: int, summary: dict, tenant_config: dict, phone_number_id) -> None:
    """T1: WhatsApp only. State advanced only on successful delivery."""
    from modules.incident_cluster import record_alert_sent

    pa_phone = tenant_config.get("pa_phone")
    if not pa_phone:
        logger.warning("T1 alert skipped — pa_phone not configured for tenant")
        return

    wa_sent = _send_wa(pa_phone, _format_wa_t1(summary), phone_number_id)
    if wa_sent:
        record_alert_sent(cluster_id, "t1")
        logger.info("T1 alert dispatched for cluster %s", cluster_id)
    else:
        logger.warning("T1 alert delivery failed for cluster %s; state unchanged", cluster_id)


def dispatch_t2_alert(cluster_id: int, summary: dict, tenant_config: dict, phone_number_id) -> None:
    """T2: WhatsApp + Exotel call. State advanced if WhatsApp succeeds."""
    from modules.incident_cluster import record_alert_sent

    pa_phone = tenant_config.get("pa_phone")
    if not pa_phone:
        logger.warning("T2 alert skipped — pa_phone not configured for tenant")
        return

    wa_sent = _send_wa(pa_phone, _format_wa_t2(summary), phone_number_id)
    _trigger_exotel_call(pa_phone, _format_voice_script(summary))

    if wa_sent:
        record_alert_sent(cluster_id, "t2", increment_call_attempt=True)
        logger.info("T2 alert dispatched for cluster %s", cluster_id)
    else:
        logger.warning("T2 alert delivery failed for cluster %s; state unchanged", cluster_id)


def dispatch_t3_alert(cluster_id: int, summary: dict, tenant_config: dict, phone_number_id) -> None:
    """T3: WhatsApp to backup PA + Exotel retry. Marks unacknowledged when attempts exhaust."""
    from modules.incident_cluster import record_alert_sent, get_cluster_by_id, mark_unacknowledged

    pa_phone = tenant_config.get("pa_phone")
    backup_phone = tenant_config.get("backup_pa_phone")
    max_attempts = tenant_config.get("max_call_attempts", 3)

    cluster = get_cluster_by_id(cluster_id)
    if not cluster:
        return

    attempts = cluster.call_attempt_count or 0
    if attempts >= max_attempts:
        mark_unacknowledged(cluster_id)
        logger.warning("Cluster %s marked UNACKNOWLEDGED after %d call attempts", cluster_id, attempts)
        return

    summary = {**summary, "call_attempt_count": attempts + 1}
    script = _format_voice_script(summary)

    backup_wa_sent = False
    if backup_phone:
        backup_wa_sent = _send_wa(backup_phone, _format_wa_t3(summary), phone_number_id)

    primary_call_ok = False
    if pa_phone:
        primary_call_ok = _trigger_exotel_call(pa_phone, script)

    backup_call_ok = False
    if backup_phone and backup_phone != pa_phone:
        backup_call_ok = _trigger_exotel_call(backup_phone, script)

    if backup_wa_sent or primary_call_ok or backup_call_ok:
        record_alert_sent(cluster_id, "t3", increment_call_attempt=True)
        logger.info("T3 alert dispatched for cluster %s (attempt %d)", cluster_id, attempts + 1)
    else:
        logger.warning("T3 alert delivery failed for cluster %s; state unchanged", cluster_id)
