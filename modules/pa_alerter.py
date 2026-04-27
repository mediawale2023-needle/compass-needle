"""
pa_alerter.py — PA alert dispatch for emergency surge events.

Two channels:
  1. WhatsApp (always attempted; uses existing whatsapp.py)
  2. Exotel outbound voice call (requires EXOTEL_* env vars; skipped if absent)

Fix 6: record_alert_sent() is called only when at least one delivery channel
succeeded. A total delivery failure does not advance the cluster state, so the
next escalation cycle will retry rather than silently exhausting retries.
"""
import os
import logging
import base64

logger = logging.getLogger("needle.pa_alerter")

_EXOTEL_API_KEY   = os.getenv("EXOTEL_API_KEY", "")
_EXOTEL_API_TOKEN = os.getenv("EXOTEL_API_TOKEN", "")
_EXOTEL_SID       = os.getenv("EXOTEL_SID", "")
_EXOTEL_CALLER_ID = os.getenv("EXOTEL_CALLER_ID", "")
_EXOTEL_API_HOST  = os.getenv("EXOTEL_API_HOST", "api.exotel.com")


# ── Message templates ─────────────────────────────────────────────────────────

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
        f"Alert for your MP office. "
        f"Possible {hazard} reported in {area}. "
        f"{count} unique reports received in the last 15 minutes. "
        f"Please open your dashboard immediately."
    )


# ── Channel helpers ───────────────────────────────────────────────────────────

def _send_wa(phone: str, message: str, phone_number_id) -> bool:
    if not phone:
        logger.warning("PA phone not configured — WhatsApp alert skipped")
        return False
    try:
        from modules.whatsapp import send_whatsapp_message
        send_whatsapp_message(phone, message, phone_number_id)
        logger.info("PA WhatsApp alert sent to ...%s", phone[-4:])
        return True
    except Exception as exc:
        logger.error("PA WhatsApp alert failed for ...%s: %s", phone[-4:], exc)
        return False


def _trigger_exotel_call(to_phone: str, tts_script: str) -> bool:
    """
    Outbound call via Exotel. Requires env vars:
      EXOTEL_API_KEY, EXOTEL_API_TOKEN, EXOTEL_SID,
      EXOTEL_CALLER_ID, EXOTEL_APPLET_URL
    Skips gracefully if any are missing.
    """
    applet_url = os.getenv("EXOTEL_APPLET_URL", "")
    if not all([_EXOTEL_API_KEY, _EXOTEL_API_TOKEN, _EXOTEL_SID, _EXOTEL_CALLER_ID, applet_url]):
        logger.warning(
            "Exotel call skipped — set EXOTEL_API_KEY, EXOTEL_API_TOKEN, "
            "EXOTEL_SID, EXOTEL_CALLER_ID, EXOTEL_APPLET_URL to enable voice alerts."
        )
        return False
    if not to_phone:
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
            logger.info("Exotel call initiated to ...%s", phone[-4:])
            return True
        logger.error("Exotel call failed: status=%s body=%s", resp.status_code, resp.text[:200])
        return False
    except Exception as exc:
        logger.error("Exotel call exception: %s", exc)
        return False


# ── Public dispatch functions ─────────────────────────────────────────────────

def dispatch_t1_alert(cluster_id: int, summary: dict, tenant_config: dict, phone_number_id) -> None:
    """T1: WhatsApp only. State advanced only on successful delivery."""
    from modules.incident_cluster import record_alert_sent
    pa_phone = tenant_config.get("pa_phone")
    if not pa_phone:
        logger.warning("T1 alert skipped — pa_phone not configured for tenant")
        return

    delivered = _send_wa(pa_phone, _format_wa_t1(summary), phone_number_id)

    # Fix 6: only advance state when delivery succeeded
    if delivered:
        record_alert_sent(cluster_id, "t1")
        logger.info("T1 alert state recorded for cluster %s", cluster_id)
    else:
        logger.warning("T1 alert delivery failed — cluster %s state NOT advanced", cluster_id)


def dispatch_t2_alert(cluster_id: int, summary: dict, tenant_config: dict, phone_number_id) -> None:
    """T2: WhatsApp + Exotel call. State advanced if WhatsApp succeeds."""
    from modules.incident_cluster import record_alert_sent
    pa_phone = tenant_config.get("pa_phone")
    if not pa_phone:
        logger.warning("T2 alert skipped — pa_phone not configured for tenant")
        return

    wa_ok = _send_wa(pa_phone, _format_wa_t2(summary), phone_number_id)
    # Voice call is best-effort; WA delivery is the primary success criterion
    _trigger_exotel_call(pa_phone, _format_voice_script(summary))

    # Fix 6: advance state only when WhatsApp was delivered
    if wa_ok:
        record_alert_sent(cluster_id, "t2")
        logger.info("T2 alert state recorded for cluster %s", cluster_id)
    else:
        logger.warning("T2 WA delivery failed — cluster %s state NOT advanced (will retry)", cluster_id)


def dispatch_t3_alert(cluster_id: int, summary: dict, tenant_config: dict, phone_number_id) -> None:
    """T3: WhatsApp to backup + Exotel retry. Marks unacknowledged when attempts exhausted."""
    from modules.incident_cluster import record_alert_sent, get_cluster_by_id
    from sansadx_backend.db import SessionLocal, IncidentCluster

    pa_phone = tenant_config.get("pa_phone")
    backup_phone = tenant_config.get("backup_pa_phone")
    max_attempts = tenant_config.get("max_call_attempts", 3)

    cluster = get_cluster_by_id(cluster_id)
    if not cluster:
        return

    attempts = cluster.call_attempt_count or 0

    if attempts >= max_attempts:
        db = SessionLocal()
        try:
            c = db.query(IncidentCluster).filter(IncidentCluster.id == cluster_id).first()
            if c:
                c.alert_level = "unacknowledged"
                db.commit()
            logger.warning("Cluster %s: UNACKNOWLEDGED after %d call attempts", cluster_id, attempts)
        except Exception:
            db.rollback()
        finally:
            db.close()
        return

    any_delivered = False

    if backup_phone:
        ok = _send_wa(backup_phone, _format_wa_t3(summary), phone_number_id)
        any_delivered = any_delivered or ok

    if pa_phone:
        _trigger_exotel_call(pa_phone, _format_voice_script(summary))

    if backup_phone and backup_phone != pa_phone:
        _trigger_exotel_call(backup_phone, _format_voice_script(summary))

    # Fix 6: advance state only when at least one delivery channel succeeded
    if any_delivered:
        record_alert_sent(cluster_id, "t3")
        logger.info("T3 alert state recorded for cluster %s (attempt %d)", cluster_id, attempts + 1)
    else:
        logger.warning("T3 delivery failed — cluster %s state NOT advanced (will retry)", cluster_id)
