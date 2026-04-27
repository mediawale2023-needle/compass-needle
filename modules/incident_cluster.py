"""
incident_cluster.py — Rolling incident window clustering for emergency surge detection.

Each incoming emergency case is checked against open clusters. A cluster is
"open" if its window_start is within the configured rolling window.

Cluster key: (tenant_id, hazard_type, assembly, ward)
  - ward=None clusters only match other ward=None clusters
  - ward-tagged clusters match only within that ward

Deduplication:
  - repeated messages from the same sender do not count twice
  - near-identical forwarded text from different senders does not count twice

Alert levels:
  t0  — 1+ reports, silent storage, no PA alert
  t1  — >= t1_count unique senders within t1_window_minutes → WhatsApp to PA
  t2  — >= t2_count unique senders within t2_window_minutes → call + WhatsApp
  t3  — T2/T3 unacknowledged after escalation_wait_minutes → backup PA retry
  unacknowledged — all retry attempts exhausted, stop calling
"""
import logging
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
    text = (text or "").lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _normalise_phone(phone: str | None, fallback_case_id: int | None = None) -> str:
    phone = re.sub(r"\D+", "", phone or "")
    if phone:
        return phone
    if fallback_case_id is not None:
        return f"case:{fallback_case_id}"
    return ""


def _parse_event_ts(value) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            return None
    return None


def _coerce_sender_events(cluster) -> list[dict]:
    """
    Normalise sender event storage.

    Older clusters may have no sender_events column data yet. For those, create
    synthetic placeholder events so threshold logic does not undercount the
    already-recorded sender total after deployment.
    """
    events = []
    for event in cluster.sender_events or []:
        if not isinstance(event, dict):
            continue
        phone = str(event.get("phone") or "").strip()
        ts = _parse_event_ts(event.get("ts"))
        if phone and ts:
            events.append({"phone": phone, "ts": ts.isoformat()})

    if events:
        return events

    legacy_count = max(int(cluster.unique_sender_count or 0), 0)
    if legacy_count <= 0:
        return []

    anchor = (
        cluster.window_start
        or getattr(cluster, "updated_at", None)
        or getattr(cluster, "created_at", None)
        or datetime.utcnow()
    )
    return [
        {"phone": f"legacy:{cluster.id}:{idx}", "ts": anchor.isoformat()}
        for idx in range(legacy_count)
    ]


def _unique_sender_count_from_events(events: list[dict]) -> int:
    return len({str(event.get("phone") or "").strip() for event in events if event.get("phone")})


def _recent_unique_sender_count(cluster, window_minutes: int) -> int:
    cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)
    phones = set()
    for event in _coerce_sender_events(cluster):
        ts = _parse_event_ts(event.get("ts"))
        phone = str(event.get("phone") or "").strip()
        if phone and ts and ts >= cutoff:
            phones.add(phone)
    return len(phones)


def _jaccard_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    tokens_a = set(a.split())
    tokens_b = set(b.split())
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def _is_forward_duplicate(message_text: str, existing_fingerprints: list, threshold: float = 0.82) -> bool:
    """Return True if message_text is a near-identical forward of an existing cluster message."""
    normalised = _normalise_text(message_text)
    if not normalised:
        return False
    for fp in existing_fingerprints:
        if _jaccard_similarity(normalised, fp) >= threshold:
            return True
    return False


def _find_open_cluster(db, tenant_id: int, hazard_type: str, assembly: str, ward, window_minutes: int):
    """Find the most recent open cluster for this (tenant, hazard, assembly, ward) key."""
    from sansadx_backend.db import IncidentCluster

    window_start = datetime.utcnow() - timedelta(minutes=window_minutes)
    query = (
        db.query(IncidentCluster)
        .filter(
            IncidentCluster.tenant_id == tenant_id,
            IncidentCluster.hazard_type == hazard_type,
            IncidentCluster.assembly == assembly,
            IncidentCluster.alert_level.notin_(["unacknowledged"]),
            IncidentCluster.window_start >= window_start,
        )
    )

    if ward is None:
        query = query.filter(IncidentCluster.ward.is_(None))
    else:
        query = query.filter(IncidentCluster.ward == ward)

    return query.order_by(IncidentCluster.window_start.desc()).first()


def _evaluate_alert_level(cluster, config: dict) -> str:
    """Determine the highest non-regressing level justified by recent sender events."""
    current = cluster.alert_level
    level_rank = {"t0": 0, "t1": 1, "t2": 2, "t3": 3, "unacknowledged": 4}
    current_rank = level_rank.get(current, 0)

    recent_t2_count = _recent_unique_sender_count(cluster, int(config["t2_window_minutes"]))
    recent_t1_count = _recent_unique_sender_count(cluster, int(config["t1_window_minutes"]))

    if recent_t2_count >= int(config["t2_count"]) and current_rank < level_rank["t2"]:
        return "t2"
    if recent_t1_count >= int(config["t1_count"]) and current_rank < level_rank["t1"]:
        return "t1"
    return current


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
        (cluster_id, old_alert_level, new_alert_level)
    """
    from sansadx_backend.db import SessionLocal, IncidentCluster

    window_minutes = max(config["t1_window_minutes"], config["t2_window_minutes"])
    threshold = config.get("similarity_dedup_threshold", 0.82)
    normalised_msg = _normalise_text(message_text)
    normalised_phone = _normalise_phone(sender_phone, case_id)
    now = datetime.utcnow()

    db = SessionLocal()
    try:
        cluster = _find_open_cluster(db, tenant_id, hazard_type, assembly, ward, window_minutes)
        old_level = "t0"

        if cluster:
            old_level = cluster.alert_level
            existing_fps = list(cluster.fingerprint_hashes or [])
            sender_events = _coerce_sender_events(cluster)
            existing_phones = {event["phone"] for event in sender_events if event.get("phone")}
            is_dup = _is_forward_duplicate(message_text, existing_fps, threshold)

            case_ids = list(cluster.raw_case_ids or [])
            if case_id not in case_ids:
                case_ids.append(case_id)
            cluster.raw_case_ids = case_ids

            if not is_dup and normalised_phone not in existing_phones:
                sender_events.append({"phone": normalised_phone, "ts": now.isoformat()})
                cluster.sender_events = sender_events
                cluster.unique_sender_count = _unique_sender_count_from_events(sender_events)
                if normalised_msg and normalised_msg not in existing_fps:
                    existing_fps.append(normalised_msg)
                    cluster.fingerprint_hashes = existing_fps
                logger.info(
                    "Cluster %s: new sender (total %d), case %s, tenant %s",
                    cluster.id, cluster.unique_sender_count, case_id, tenant_id,
                )
            else:
                cluster.sender_events = sender_events
                cluster.unique_sender_count = _unique_sender_count_from_events(sender_events)
                if is_dup:
                    logger.info(
                        "Cluster %s: forward duplicate detected, count stays at %d",
                        cluster.id, cluster.unique_sender_count,
                    )
                else:
                    logger.info(
                        "Cluster %s: repeat sender %s skipped, count stays at %d",
                        cluster.id, normalised_phone[-4:] if normalised_phone else "unknown", cluster.unique_sender_count,
                    )

            cluster.updated_at = now
            db.commit()
            db.refresh(cluster)
        else:
            sender_events = [{"phone": normalised_phone, "ts": now.isoformat()}] if normalised_phone else []
            cluster = IncidentCluster(
                tenant_id=tenant_id,
                hazard_type=hazard_type,
                assembly=assembly or "Unknown",
                ward=ward,
                window_start=now,
                unique_sender_count=_unique_sender_count_from_events(sender_events) or 1,
                raw_case_ids=[case_id],
                fingerprint_hashes=[normalised_msg] if normalised_msg else [],
                sender_events=sender_events,
                alert_level="t0",
                alert_acknowledged=False,
                call_attempt_count=0,
                created_at=now,
                updated_at=now,
            )
            db.add(cluster)
            db.commit()
            db.refresh(cluster)
            logger.info(
                "New incident cluster created: id=%s tenant=%s hazard=%s assembly=%s ward=%s",
                cluster.id, tenant_id, hazard_type, assembly, ward,
            )

        new_level = _evaluate_alert_level(cluster, config)
        if new_level != cluster.alert_level:
            cluster.alert_level = new_level
            cluster.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(cluster)
            logger.info(
                "Cluster %s level: %s → %s (senders=%d)",
                cluster.id, old_level, new_level, cluster.unique_sender_count,
            )

        return cluster.id, old_level, new_level
    except Exception as exc:
        db.rollback()
        logger.error("upsert_cluster failed: %s", exc)
        raise
    finally:
        db.close()


def get_cluster_by_id(cluster_id: int):
    from sansadx_backend.db import SessionLocal, IncidentCluster

    db = SessionLocal()
    try:
        return db.query(IncidentCluster).filter(IncidentCluster.id == cluster_id).first()
    finally:
        db.close()


def mark_acknowledged(cluster_id: int):
    from sansadx_backend.db import SessionLocal, IncidentCluster

    db = SessionLocal()
    try:
        cluster = db.query(IncidentCluster).filter(IncidentCluster.id == cluster_id).first()
        if cluster:
            cluster.alert_acknowledged = True
            cluster.updated_at = datetime.utcnow()
            db.commit()
            logger.info("Cluster %s acknowledged", cluster_id)
    except Exception as exc:
        db.rollback()
        logger.warning("mark_acknowledged failed for cluster %s: %s", cluster_id, exc)
    finally:
        db.close()


def get_pending_escalation_clusters() -> list:
    """Return all unacknowledged T2/T3 clusters that have previously been alerted."""
    from sansadx_backend.db import SessionLocal, IncidentCluster

    db = SessionLocal()
    try:
        return (
            db.query(IncidentCluster)
            .filter(
                IncidentCluster.alert_level.in_(["t2", "t3"]),
                IncidentCluster.alert_acknowledged == False,  # noqa: E712
                IncidentCluster.last_alert_at.isnot(None),
            )
            .all()
        )
    finally:
        db.close()


def mark_unacknowledged(cluster_id: int):
    """Mark cluster as unacknowledged after retries are exhausted."""
    from sansadx_backend.db import SessionLocal, IncidentCluster

    db = SessionLocal()
    try:
        cluster = db.query(IncidentCluster).filter(IncidentCluster.id == cluster_id).first()
        if cluster:
            cluster.alert_level = "unacknowledged"
            cluster.updated_at = datetime.utcnow()
            db.commit()
            logger.warning("Cluster %s marked UNACKNOWLEDGED", cluster_id)
    except Exception as exc:
        db.rollback()
        logger.warning("mark_unacknowledged failed for cluster %s: %s", cluster_id, exc)
    finally:
        db.close()


def record_alert_sent(cluster_id: int, level: str, *, increment_call_attempt: bool = False):
    """Update cluster after an alert is successfully dispatched."""
    from sansadx_backend.db import SessionLocal, IncidentCluster

    db = SessionLocal()
    try:
        cluster = db.query(IncidentCluster).filter(IncidentCluster.id == cluster_id).first()
        if cluster:
            cluster.last_alert_at = datetime.utcnow()
            cluster.alert_level = level
            cluster.updated_at = datetime.utcnow()
            if increment_call_attempt:
                cluster.call_attempt_count = (cluster.call_attempt_count or 0) + 1
            db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("record_alert_sent failed for cluster %s: %s", cluster_id, exc)
    finally:
        db.close()


def build_alert_summary(cluster) -> dict:
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
