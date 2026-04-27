"""
incident_cluster.py — Rolling incident window clustering for emergency surge detection.

Each incoming emergency case is checked against open clusters. A cluster is
'open' if its window_start is within the configured rolling window.

Cluster key: (tenant_id, hazard_type, assembly, ward_or_UNKNOWN)

Deduplication: forward-chain WhatsApp messages (near-identical text from
multiple senders) are detected via Jaccard token similarity and NOT counted
as unique senders.

Alert levels:
  t0  — 1 report, silent storage only
  t1  — >= t1_count unique senders within t1_window → WhatsApp alert to PA
  t2  — >= t2_count unique senders within t2_window → call + WhatsApp to PA
  t3  — T2 unacknowledged after escalation_wait_minutes → call backup PA
  unacknowledged — all retry attempts exhausted
"""
import logging
import difflib
import re
from datetime import datetime, timedelta

logger = logging.getLogger("needle.incident_cluster")

DEFAULT_EMERGENCY_CONFIG = {
    "t1_count": 3,
    "t1_window_minutes": 10,
    "t2_count": 8,
    "t2_window_minutes": 15,
    "escalation_wait_minutes": 5,
    "max_call_attempts": 3,
    "cluster_geo_level": "ward",
    "pa_phone": None,
    "backup_pa_phone": None,
    "similarity_dedup_threshold": 0.82,
    "morning_digest_enabled": True,
    "morning_digest_hour_ist": 7,
}


def get_emergency_config(tenant_id: int) -> dict:
    """Load emergency config from Tenant.config JSON, falling back to defaults."""
    config = dict(DEFAULT_EMERGENCY_CONFIG)
    try:
        from sansadx_backend.db import SessionLocal, Tenant
        db = SessionLocal()
        try:
            tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
            if tenant and tenant.config:
                cfg = tenant.config if isinstance(tenant.config, dict) else {}
                emergency_cfg = cfg.get("emergency", {})
                config.update({k: v for k, v in emergency_cfg.items() if v is not None})
        finally:
            db.close()
    except Exception as exc:
        logger.warning("Failed to load emergency config for tenant %s: %s", tenant_id, exc)
    return config


def _normalise_text(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    text = (text or "").lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _jaccard_similarity(a: str, b: str) -> float:
    """Token-level Jaccard similarity between two strings."""
    if not a or not b:
        return 0.0
    tokens_a = set(a.split())
    tokens_b = set(b.split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def _is_forward_duplicate(
    message_text: str,
    existing_fingerprints: list,
    threshold: float = 0.82,
) -> bool:
    """
    Return True if message_text is a near-identical forward of an existing
    cluster message. Uses Jaccard similarity on word tokens.

    Threshold 0.82 catches copy-paste forwards while allowing genuine
    independent eyewitness accounts (typically 0.3–0.5 similarity).
    """
    normalised = _normalise_text(message_text)
    if not normalised:
        return False
    for fp in existing_fingerprints:
        if _jaccard_similarity(normalised, fp) >= threshold:
            return True
    return False


def _find_open_cluster(db, tenant_id: int, hazard_type: str, assembly: str, ward, window_minutes: int):
    """
    Find the most recent open cluster for this (tenant, hazard, geo) key
    within the rolling window. Returns ORM object or None.
    """
    from sansadx_backend.db import IncidentCluster
    window_start = datetime.utcnow() - timedelta(minutes=window_minutes)
    return (
        db.query(IncidentCluster)
        .filter(
            IncidentCluster.tenant_id == tenant_id,
            IncidentCluster.hazard_type == hazard_type,
            IncidentCluster.assembly == assembly,
            IncidentCluster.alert_level.notin_(["unacknowledged"]),
            IncidentCluster.window_start >= window_start,
        )
        .order_by(IncidentCluster.window_start.desc())
        .first()
    )


def upsert_cluster(
    tenant_id: int,
    case_id: int,
    sender_phone: str,
    message_text: str,
    assembly: str,
    ward,
    hazard_type: str,
    config: dict,
) -> tuple:
    """
    Add an emergency case to an existing open cluster, or create a new one.

    Returns:
        (cluster_id: int, old_alert_level: str, new_alert_level: str)
        old and new are the same when the threshold was not crossed.
    """
    from sansadx_backend.db import SessionLocal, IncidentCluster

    # Use the larger window for initial cluster lookup so we capture messages
    # that arrive near the T2 boundary.
    window_minutes = max(config["t1_window_minutes"], config["t2_window_minutes"])
    threshold = config.get("similarity_dedup_threshold", 0.82)
    normalised_msg = _normalise_text(message_text)

    db = SessionLocal()
    try:
        cluster = _find_open_cluster(db, tenant_id, hazard_type, assembly, ward, window_minutes)
        old_level = "t0"

        if cluster:
            old_level = cluster.alert_level

            # Dedup: check if this is a forwarded message
            existing_fps = list(cluster.fingerprint_hashes or [])
            is_dup = _is_forward_duplicate(message_text, existing_fps, threshold)

            # Update case IDs list
            case_ids = list(cluster.raw_case_ids or [])
            if case_id not in case_ids:
                case_ids.append(case_id)
            cluster.raw_case_ids = case_ids

            if not is_dup:
                cluster.unique_sender_count += 1
                if normalised_msg and normalised_msg not in existing_fps:
                    existing_fps.append(normalised_msg)
                    cluster.fingerprint_hashes = existing_fps
                logger.info(
                    "Cluster %s: +1 unique sender (total %d), case %s, tenant %s",
                    cluster.id, cluster.unique_sender_count, case_id, tenant_id,
                )
            else:
                logger.info(
                    "Cluster %s: forward duplicate detected, sender count stays at %d",
                    cluster.id, cluster.unique_sender_count,
                )

            cluster.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(cluster)

        else:
            # Create new cluster at T0
            cluster = IncidentCluster(
                tenant_id=tenant_id,
                hazard_type=hazard_type,
                assembly=assembly or "Unknown",
                ward=ward,
                window_start=datetime.utcnow(),
                unique_sender_count=1,
                raw_case_ids=[case_id],
                fingerprint_hashes=[normalised_msg] if normalised_msg else [],
                alert_level="t0",
                alert_acknowledged=False,
                call_attempt_count=0,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(cluster)
            db.commit()
            db.refresh(cluster)
            logger.info(
                "New incident cluster created: id=%s tenant=%s hazard=%s assembly=%s",
                cluster.id, tenant_id, hazard_type, assembly,
            )

        # Evaluate new alert level
        new_level = _evaluate_alert_level(cluster, config)
        if new_level != cluster.alert_level:
            cluster.alert_level = new_level
            db.commit()
            logger.info(
                "Cluster %s alert level: %s → %s (senders=%d)",
                cluster.id, old_level, new_level, cluster.unique_sender_count,
            )

        return cluster.id, old_level, new_level

    except Exception as exc:
        db.rollback()
        logger.error("upsert_cluster failed: %s", exc)
        raise
    finally:
        db.close()


def _evaluate_alert_level(cluster, config: dict) -> str:
    """
    Determine what alert level this cluster should be at based on current
    unique_sender_count and config thresholds. Never regresses a level.
    """
    count = cluster.unique_sender_count
    current = cluster.alert_level

    # Never downgrade
    level_rank = {"t0": 0, "t1": 1, "t2": 2, "t3": 3, "unacknowledged": 4}
    current_rank = level_rank.get(current, 0)

    if count >= config["t2_count"] and current_rank < level_rank["t2"]:
        return "t2"
    if count >= config["t1_count"] and current_rank < level_rank["t1"]:
        return "t1"
    return current


def get_cluster_by_id(cluster_id: int):
    """Return IncidentCluster ORM object by ID, or None."""
    from sansadx_backend.db import SessionLocal, IncidentCluster
    db = SessionLocal()
    try:
        return db.query(IncidentCluster).filter(IncidentCluster.id == cluster_id).first()
    finally:
        db.close()


def mark_acknowledged(cluster_id: int):
    """Mark cluster as acknowledged by PA. Stops further escalation."""
    from sansadx_backend.db import SessionLocal, IncidentCluster
    db = SessionLocal()
    try:
        cluster = db.query(IncidentCluster).filter(IncidentCluster.id == cluster_id).first()
        if cluster:
            cluster.alert_acknowledged = True
            db.commit()
            logger.info("Cluster %s acknowledged by PA", cluster_id)
    except Exception as exc:
        db.rollback()
        logger.warning("mark_acknowledged failed for cluster %s: %s", cluster_id, exc)
    finally:
        db.close()


def get_unacknowledged_t2_clusters(escalation_wait_minutes: int = 5) -> list:
    """
    Return all T2 clusters that have not been acknowledged and whose last
    alert was sent more than escalation_wait_minutes ago.
    Called by the periodic escalation checker in main.py.
    """
    from sansadx_backend.db import SessionLocal, IncidentCluster
    cutoff = datetime.utcnow() - timedelta(minutes=escalation_wait_minutes)
    db = SessionLocal()
    try:
        return (
            db.query(IncidentCluster)
            .filter(
                IncidentCluster.alert_level == "t2",
                IncidentCluster.alert_acknowledged == False,  # noqa: E712
                IncidentCluster.last_alert_at <= cutoff,
                IncidentCluster.last_alert_at.isnot(None),
            )
            .all()
        )
    finally:
        db.close()


def record_alert_sent(cluster_id: int, level: str):
    """Update cluster after an alert is dispatched."""
    from sansadx_backend.db import SessionLocal, IncidentCluster
    db = SessionLocal()
    try:
        cluster = db.query(IncidentCluster).filter(IncidentCluster.id == cluster_id).first()
        if cluster:
            cluster.last_alert_at = datetime.utcnow()
            cluster.alert_level = level
            if level in ("t2", "t3"):
                cluster.call_attempt_count = (cluster.call_attempt_count or 0) + 1
            db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("record_alert_sent failed for cluster %s: %s", cluster_id, exc)
    finally:
        db.close()


def build_alert_summary(cluster) -> dict:
    """Build a structured summary dict for PA alert messages."""
    return {
        "cluster_id": cluster.id,
        "hazard_type": cluster.hazard_type or "emergency",
        "assembly": cluster.assembly or "Unknown area",
        "ward": cluster.ward,
        "unique_sender_count": cluster.unique_sender_count,
        "window_start": cluster.window_start,
        "alert_level": cluster.alert_level,
        "call_attempt_count": cluster.call_attempt_count or 0,
    }
