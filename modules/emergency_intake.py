"""
emergency_intake.py — Entry point for emergency case routing.

Called from main.py's _process_incoming_message() after a case is saved
and AI-classified. Decides whether to cluster the case and dispatch PA alerts.

No reply is sent to the citizen here. The policy is:
  - T0: silent storage, no reply, no alert
  - T1: PA WhatsApp alert only
  - T2: PA WhatsApp + Exotel call
  - T3: Backup PA + retry call (triggered by periodic escalation checker)

T0-IM (single message alert) is explicitly NOT implemented per design decision.
"""
import logging
from datetime import datetime

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

    Conditions for routing:
      - AI returned status='emergency' OR is_critical=True
      - OR keyword scan detects severity signal (fallback for language gaps)

    This function is fire-and-forget. All exceptions are caught and logged.
    Never raises — a failure here must never crash the main message handler.
    """
    try:
        from modules.emergency_keywords import detect_emergency_severity, classify_hazard_type
        from modules.incident_cluster import (
            get_emergency_config,
            upsert_cluster,
            build_alert_summary,
        )
        from modules.pa_alerter import dispatch_t1_alert, dispatch_t2_alert
        from sansadx_backend.db import get_tenant_phone_number_id

        # Confirm this case qualifies
        is_emergency_status = status == "emergency"
        is_keyword_match = detect_emergency_severity(message_body)

        if not is_emergency_status and not is_keyword_match:
            return  # Not an emergency — nothing to do

        # Load per-tenant config
        config = get_emergency_config(tenant_id)

        # Classify hazard type for cluster key
        hazard_type = classify_hazard_type(
            message=message_body,
            status=status,
            category=category,
            problem_domain=problem_domain,
        )

        # Upsert into cluster
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

        # Build summary for alert messages
        from modules.incident_cluster import get_cluster_by_id
        cluster = get_cluster_by_id(cluster_id)
        if not cluster:
            return

        summary = build_alert_summary(cluster)
        phone_number_id = get_tenant_phone_number_id(tenant_id)

        # Dispatch alert only if level just crossed a threshold
        if new_level == "t1" and old_level == "t0":
            dispatch_t1_alert(cluster_id, summary, config, phone_number_id)

        elif new_level == "t2" and old_level in ("t0", "t1"):
            dispatch_t2_alert(cluster_id, summary, config, phone_number_id)

        # t3 is handled by the periodic escalation checker, not here

    except Exception as exc:
        logger.error(
            "emergency_intake.process_emergency_case failed (non-blocking) "
            "tenant=%s case=%s: %s", tenant_id, case_id, exc
        )


def escalate_pending_clusters() -> None:
    """
    Periodic escalation checker: promotes T2 → T3 for unacknowledged clusters.

    Called every 5 minutes by a background thread in main.py.
    Dispatches T3 alert for each cluster that has been at T2 longer than
    escalation_wait_minutes without acknowledgment.
    """
    try:
        from modules.incident_cluster import (
            get_unacknowledged_t2_clusters,
            get_emergency_config,
            build_alert_summary,
        )
        from modules.pa_alerter import dispatch_t3_alert
        from sansadx_backend.db import get_tenant_phone_number_id

        clusters = get_unacknowledged_t2_clusters(escalation_wait_minutes=5)
        if not clusters:
            return

        logger.info("Escalation check: %d unacknowledged T2 clusters found", len(clusters))

        for cluster in clusters:
            try:
                config = get_emergency_config(cluster.tenant_id)
                summary = build_alert_summary(cluster)
                phone_number_id = get_tenant_phone_number_id(cluster.tenant_id)
                dispatch_t3_alert(cluster.id, summary, config, phone_number_id)
            except Exception as exc:
                logger.error(
                    "T3 escalation failed for cluster %s: %s", cluster.id, exc
                )

    except Exception as exc:
        logger.error("escalate_pending_clusters failed: %s", exc)


def handle_pa_acknowledgment(sender_phone: str, tenant_id: int, message_body: str) -> bool:
    """
    Check if a PA message is an acknowledgment command (ACK <cluster_id>).
    If so, mark the cluster acknowledged and return True.
    Returns False if the message is not an ACK command.

    Called from main.py's staff query routing path.
    """
    import re
    stripped = message_body.strip()
    match = re.match(r"^ack\s+(\d+)$", stripped, re.IGNORECASE)
    if not match:
        # Also accept bare "ACK" — acknowledges the most recent active cluster
        if re.match(r"^ack$", stripped, re.IGNORECASE):
            return _acknowledge_latest_cluster(tenant_id)
        return False

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


def _acknowledge_latest_cluster(tenant_id: int) -> bool:
    """Acknowledge the most recent unacknowledged cluster for this tenant."""
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
