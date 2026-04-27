"""
emergency_intake.py — Entry point for emergency case routing.

Called from main.py after a case is saved and AI-classified. Decides whether to
cluster the case and dispatch PA alerts. No citizen reply is sent here.
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
    """Route an emergency-classified or keyword-matched case into the cluster pipeline."""
    try:
        from modules.emergency_keywords import detect_emergency_severity, classify_hazard_type
        from modules.incident_cluster import get_emergency_config, upsert_cluster, build_alert_summary, get_cluster_by_id
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
    """Promote pending T2/T3 clusters to the next T3 retry when tenant wait has elapsed."""
    try:
        from modules.incident_cluster import get_pending_escalation_clusters, get_emergency_config, build_alert_summary
        from modules.pa_alerter import dispatch_t3_alert
        from sansadx_backend.db import get_tenant_phone_number_id

        clusters = get_pending_escalation_clusters()
        if not clusters:
            return

        logger.info("Escalation check: %d pending emergency clusters found", len(clusters))

        for cluster in clusters:
            try:
                config = get_emergency_config(cluster.tenant_id)
                wait_minutes = int(config.get("escalation_wait_minutes", 5) or 5)
                cutoff = datetime.utcnow() - timedelta(minutes=wait_minutes)
                if not cluster.last_alert_at or cluster.last_alert_at > cutoff:
                    continue
                summary = build_alert_summary(cluster)
                phone_number_id = get_tenant_phone_number_id(cluster.tenant_id)
                dispatch_t3_alert(cluster.id, summary, config, phone_number_id)
            except Exception as exc:
                logger.error("T3 escalation failed for cluster %s: %s", cluster.id, exc)
    except Exception as exc:
        logger.error("escalate_pending_clusters failed: %s", exc)


def handle_pa_acknowledgment(sender_phone: str, tenant_id: int, message_body: str) -> bool:
    """Check if a PA message is an acknowledgment command. Returns True if handled."""
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
