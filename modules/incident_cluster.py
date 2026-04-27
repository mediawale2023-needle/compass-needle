"""
incident_cluster.py — Rolling incident window clustering for emergency surge detection.

Each incoming emergency case is checked against open clusters. A cluster is
'open' if its window_start is within the configured rolling window.

Cluster key: (tenant_id, hazard_type, assembly, ward)
  - ward=None clusters only match other ward=None clusters (assembly-level granularity)
  - ward-tagged clusters match only within that ward

Deduplication:
  1. Per-sender dedup: a phone number can only count once per cluster. Multiple
     messages from the same citizen do not inflate unique_sender_count.
  2. Forward-chain dedup: near-identical text (Jaccard ≥ 0.82) from different
     senders is treated as a forwarded message and does not increment count.

Alert levels:
  t0  — 1+ reports, silent storage, no PA alert
  t1  — >= t1_count unique senders within t1_window_minutes → WhatsApp to PA
  t2  — >= t2_count unique senders within t2_window_minutes → call + WhatsApp
  t3  — T2/T3 unacknowledged after escalation_wait_minutes → backup PA call
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


# ── Text utilities ─────────────────────────────────────────────────────────────

def _normalise_text(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _jaccard_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    tokens_a = set(a.split())
    tokens_b = set(b.split())
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def _is_forward_duplicate(message_text: str, existing_fingerprints: list, threshold: float = 0.82) -> bool:
    """
    Return True if message_text is a near-identical forward of an existing
    cluster message. Threshold 0.82 catches copy-paste forwards while allowing
    genuine independent eyewitness accounts (typically 0.3–0.5 similarity).
    """
    normalised = _normalise_text(message_text)
    if not normalised:
        return False
    for fp in existing_fingerprints:
        if _jaccard_similarity(normalised, fp) >= threshold:
            return True
    return False


def _parse_ts(ts_str) -> datetime:
    """Parse ISO timestamp string to datetime. Returns epoch on failure."""
    try:
        return datetime.fromisoformat(str(ts_str))
    except Exception:
        return datetime.utcfromtimestamp(0)


# ── Cluster lookup ─────────────────────────────────────────────────────────────

def _find_open_cluster(db, tenant_id: int, hazard_type: str, assembly: str, ward, window_minutes: int):
    """
    Find the most recent open cluster matching (tenant, hazard, assembly, ward)
    within the rolling window.

    Fix 1: ward is part of the cluster key.
      - ward=None → only matches clusters where ward IS NULL (assembly-level)
      - ward='Ward 5' → only matches clusters with that exact ward
    This prevents unrelated incidents in different wards from collapsing.
    """
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
    if ward is not None:
        query = query.filter(IncidentCluster.ward == ward)
    else:
        query = query.filter(IncidentCluster.ward.is_(None))

    return query.order_by(IncidentCluster.window_start.desc()).first()


# ── Alert level evaluation ─────────────────────────────────────────────────────

def _evaluate_alert_level(cluster, config: dict) -> str:
    """
    Evaluate what alert level the cluster should be at now.

    Fix 3: each threshold uses its own time window. T1 counts unique senders
    within the last t1_window_minutes; T2 within t2_window_minutes. A burst of
    3 reports spread across 20 minutes cannot trip a 10-minute T1 window.

    Fix 2: counts derive from sender_events, which contains one entry per
    unique sender phone. Same sender appearing multiple times only counts once.

    Alert levels never regress.
    """
    level_rank = {"t0": 0, "t1": 1, "t2": 2, "t3": 3, "unacknowledged": 4}
    current_rank = level_rank.get(cluster.alert_level, 0)

    now = datetime.utcnow()
    sender_events = cluster.sender_events or []

    t2_cutoff = now - timedelta(minutes=config["t2_window_minutes"])
    t2_count = sum(1 for e in sender_events if _parse_ts(e.get("ts")) >= t2_cutoff)

    t1_cutoff = now - timedelta(minutes=config["t1_window_minutes"])
    t1_count = sum(1 for e in sender_events if _parse_ts(e.get("ts")) >= t1_cutoff)

    if t2_count >= config["t2_count"] and current_rank < level_rank["t2"]:
        return "t2"
    if t1_count >= config["t1_count"] and current_rank < level_rank["t1"]:
        return "t1"
    return cluster.alert_level


# ── Main upsert ────────────────────────────────────────────────────────────────

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
    Add an emergency case to an open cluster, or create a new one.

    Returns: (cluster_id, old_alert_level, new_alert_level)
    old == new when no threshold was crossed.
    """
    from sansadx_backend.db import SessionLocal, IncidentCluster

    window_minutes = max(config["t1_window_minutes"], config["t2_window_minutes"])
    threshold = config.get("similarity_dedup_threshold", 0.82)
    normalised_msg = _normalise_text(message_text)

    db = SessionLocal()
    try:
        cluster = _find_open_cluster(db, tenant_id, hazard_type, assembly, ward, window_minutes)
        old_level = "t0"

        if cluster:
            old_level = cluster.alert_level

            existing_fps = list(cluster.fingerprint_hashes or [])
            sender_events = list(cluster.sender_events or [])
            existing_phones = {e["phone"] for e in sender_events}

            is_forward = _is_forward_duplicate(message_text, existing_fps, threshold)
            is_new_sender = sender_phone not in existing_phones

            # Update case ID list
            case_ids = list(cluster.raw_case_ids or [])
            if case_id not in case_ids:
                case_ids.append(case_id)
            cluster.raw_case_ids = case_ids

            # Fix 2: only count unique senders; Fix 3: record timestamp for windowed evaluation
            if not is_forward and is_new_sender:
                sender_events.append({"phone": sender_phone, "ts": datetime.utcnow().isoformat()})
                cluster.sender_events = sender_events
                cluster.unique_sender_count = len(sender_events)
                if normalised_msg and normalised_msg not in existing_fps:
                    existing_fps.append(normalised_msg)
                    cluster.fingerprint_hashes = existing_fps
                logger.info(
                    "Cluster %s: new sender (total %d), case %s, tenant %s",
                    cluster.id, cluster.unique_sender_count, case_id, tenant_id,
                )
            elif is_forward:
                logger.info(
                    "Cluster %s: forward duplicate skipped, count stays at %d",
                    cluster.id, cluster.unique_sender_count,
                )
            else:
                logger.info(
                    "Cluster %s: repeat sender %s skipped, count stays at %d",
                    cluster.id, sender_phone[-4:], cluster.unique_sender_count,
                )

            cluster.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(cluster)

        else:
            cluster = IncidentCluster(
                tenant_id=tenant_id,
                hazard_type=hazard_type,
                assembly=assembly or "Unknown",
                ward=ward,
                window_start=datetime.utcnow(),
                unique_sender_count=1,
                raw_case_ids=[case_id],
                fingerprint_hashes=[normalised_msg] if normalised_msg else [],
                sender_events=[{"phone": sender_phone, "ts": datetime.utcnow().isoformat()}],
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
                "New incident cluster: id=%s tenant=%s hazard=%s assembly=%s ward=%s",
                cluster.id, tenant_id, hazard_type, assembly, ward,
            )

        new_level = _evaluate_alert_level(cluster, config)
        if new_level != cluster.alert_level:
            cluster.alert_level = new_level
            db.commit()
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


# ── Cluster accessors ─────────────────────────────────────────────────────────

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
            db.commit()
            logger.info("Cluster %s acknowledged", cluster_id)
    except Exception as exc:
        db.rollback()
        logger.warning("mark_acknowledged failed for cluster %s: %s", cluster_id, exc)
    finally:
        db.close()


def get_unacknowledged_escalation_clusters() -> list:
    """
    Fix 4: Return all T2 AND T3 clusters not yet acknowledged, with last_alert_at set.

    Previously only selected alert_level='t2', so after the first T3 dispatch
    (which sets level to 't3') the cluster was never selected again for retries.
    Now t3 clusters are included so subsequent retries and final unacknowledged
    marking can proceed correctly.
    """
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


def record_alert_sent(cluster_id: int, level: str):
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
