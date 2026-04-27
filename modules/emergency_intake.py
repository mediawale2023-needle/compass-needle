"""
emergency_intake.py — Entry point for emergency case routing.

Called from main.py after AI classification. The call site in main.py already
gates on (AI emergency flag OR keyword match), so this function can trust that
at least one signal is present. The internal check remains as a safety net.

No reply is sent to the citizen here. Policy:
  T0: silent storage, no alert
  T1: PA WhatsApp alert only
  T2: PA WhatsApp + Exotel call
  T3: backup PA + retry call (via periodic escalation checker)

T0-IM (single-message alert) is explicitly NOT implemented.
"""
import logging
from datetime import datetime, timedelta

logger = logging.getLogger("needle.emergency_intake")


def process_emergency_case(
    *,
    case_id: int,
    tenant_id: int,
    message_body: str,
    sender_phone: str,
    assembly: str,
    ward=None,
    category: str = "",
    problem_domain: str = "",
    status: str = "",
) -> None:
    """
    Route an emergency-classified case into the incident cluster pipeline.

    Qualifies on: AI status='emergency' OR is_critical=True OR keyword match.
    This function is fire-and-forget — never raises.
    """
    try:
        from modules.emergency_keywords import detect_emergency_severity, classify_hazard_type
        from modules.incident_cluster import (
            get_emergency_config,
            upsert_cluster,
            build_alert_summary,
            get_cluster_by_id,
        )
        from modules.pa_alerter import dispatch_t1_alert, dispatch_t2_alert
        from sansadx_backend.db import get_tenant_phone_number_id

        is_emergency_status = status == "emergency"
        is_keyword_match = detect_emergency_severity(message_body)

        if not is_emergency_status and not is_keyword_match:
            return

        config = get_emergency_config(tenant_id)

        hazard_type = classify_hazard_type(
            message=message_body,
            status=status,
            category=category,
            problem_domain=problem_domain,
        )

        cluster_id, old_level, new_level = upsert_cluster(
            tenant_id=tenant_id,
            case_id=case_id,
            sender_phone=sender_phone,
            message_text=message_body,
            assembly=assembly or "Unknown",
            ward=ward,
            hazard_type=hazard_type,
            config=config,
        )

        cluster = get_cluster_by_id(cluster_id)
        if not cluster:
            return

        summary = build_alert_summary(cluster)
        phone_number_id = get_tenant_phone_number_id(tenant_id)

        # Only dispatch when level just crossed a threshold on this message
        if new_level == "t1" and old_level == "t0":
            dispatch_t1_alert(cluster_id, summary, config, phone_number_id)
        elif new_level == "t2" and old_level in ("t0", "t1"):
            dispatch_t2_alert(cluster_id, summary, config, phone_number_id)

    except Exception as exc:
        logger.error(
            "process_emergency_case failed (non-blocking) tenant=%s case=%s: %s",
            tenant_id, case_id, exc,
        )


def escalate_pending_clusters() -> None:
    """
    Fix 4: Periodic escalation checker.

    Selects T2 AND T3 clusters (previously only T2, so first T3 dispatch
    broke the retry loop). Respects each tenant's escalation_wait_minutes
    instead of hardcoding 5 minutes.
    """
    try:
        from modules.incident_cluster import (
            get_unacknowledged_escalation_clusters,
            get_emergency_config,
            build_alert_summary,
        )
        from modules.pa_alerter import dispatch_t3_alert
        from sansadx_backend.db import get_tenant_phone_number_id

        clusters = get_unacknowledged_escalation_clusters()
        if not clusters:
            return

        logger.info("Escalation check: %d unacknowledged T2/T3 clusters", len(clusters))
        now = datetime.utcnow()

        for cluster in clusters:
            try:
                config = get_emergency_config(cluster.tenant_id)
                wait_secs = config.get("escalation_wait_minutes", 5) * 60

                # Fix 4: use per-tenant wait, not hardcoded 5 minutes
                if cluster.last_alert_at is None:
                    continue
                elapsed = (now - cluster.last_alert_at).total_seconds()
                if elapsed < wait_secs:
                    continue  # not time yet for this tenant

                summary = build_alert_summary(cluster)
                phone_number_id = get_tenant_phone_number_id(cluster.tenant_id)
                dispatch_t3_alert(cluster.id, summary, config, phone_number_id)

            except Exception as exc:
                logger.error("T3 escalation failed for cluster %s: %s", cluster.id, exc)

    except Exception as exc:
        logger.error("escalate_pending_clusters failed: %s", exc)


def handle_pa_acknowledgment(sender_phone: str, tenant_id: int, message_body: str) -> bool:
    """
    Check if a PA message is an ACK command. Returns True if handled.
    Formats: "ACK 42"  or bare "ACK"
    """
    import re
    stripped = message_body.strip()
    match = re.match(r"^ack\s+(\d+)$", stripped, re.IGNORECASE)
    if match:
        cluster_id = int(match.group(1))
        try:
            from modules.incident_cluster import mark_acknowledged, get_cluster_by_id
            cluster = get_cluster_by_id(cluster_id)
            if cluster and cluster.tenant_id == tenant_id:
                mark_acknowledged(cluster_id)
                logger.info(
                    "Cluster %s acknowledged by PA %s (tenant %s)",
                    cluster_id, sender_phone[-4:], tenant_id,
                )
                return True
        except Exception as exc:
            logger.error("PA acknowledgment failed: %s", exc)
        return False

    if re.match(r"^ack$", stripped, re.IGNORECASE):
        return _acknowledge_latest_cluster(tenant_id)

    return False


def _acknowledge_latest_cluster(tenant_id: int) -> bool:
    try:
        from sansadx_backend.db import SessionLocal, IncidentCluster
        db = SessionLocal()
        try:
            cluster = (
                db.query(IncidentCluster)
                .filter(
                    IncidentCluster.tenant_id == tenant_id,
                    IncidentCluster.alert_acknowledged == False,  # noqa: E712
                    IncidentCluster.alert_level.in_(["t1", "t2", "t3"]),
                )
                .order_by(IncidentCluster.updated_at.desc())
                .first()
            )
            if cluster:
                cluster.alert_acknowledged = True
                db.commit()
                logger.info("Latest cluster %s acknowledged for tenant %s", cluster.id, tenant_id)
                return True
        finally:
            db.close()
    except Exception as exc:
        logger.error("_acknowledge_latest_cluster failed: %s", exc)
    return False
