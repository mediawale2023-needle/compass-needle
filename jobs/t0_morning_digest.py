"""
t0_morning_digest.py — Daily digest of unescalated T0 emergency intakes.

Catches single-reporter emergencies (domestic violence, personal crisis,
isolated incident) that never reached T1 volume threshold. Sent to the PA
each morning as a manual-review list.

Trigger options:
  1. Railway Cron: POST /internal/morning-digest with X-Digest-Token header
  2. Direct call: run_morning_digest(tenant_id=None) from any context

Design note: This is a 1–12 hour lagged safety net, not a real-time alert.
It does not replace human monitoring. It ensures no single-reporter emergency
is permanently silently buried.
"""
import logging
from datetime import datetime, timedelta

logger = logging.getLogger("needle.morning_digest")


def run_morning_digest(tenant_id: int | None = None) -> dict:
    """
    Find all T0 emergency cases from the last 24 hours that never escalated
    to T1+, and send a WhatsApp summary to each tenant's PA.

    Returns a summary dict for logging/API response.
    """
    from sansadx_backend.db import SessionLocal, Tenant, IncidentCluster
    from sqlalchemy import text

    cutoff = datetime.utcnow() - timedelta(hours=24)
    results = {"tenants_processed": 0, "digests_sent": 0, "errors": []}

    db = SessionLocal()
    try:
        # Get tenants in scope
        tenant_query = db.query(Tenant).filter(Tenant.is_active == True)  # noqa: E712
        if tenant_id:
            tenant_query = tenant_query.filter(Tenant.id == tenant_id)
        tenants = tenant_query.all()

        for tenant in tenants:
            try:
                _run_digest_for_tenant(db, tenant, cutoff, results)
                results["tenants_processed"] += 1
            except Exception as exc:
                err = f"Digest failed for tenant {tenant.id}: {exc}"
                logger.error(err)
                results["errors"].append(err)

    finally:
        db.close()

    logger.info(
        "Morning digest complete: %d tenants, %d digests sent, %d errors",
        results["tenants_processed"], results["digests_sent"], len(results["errors"]),
    )
    return results


def _run_digest_for_tenant(db, tenant, cutoff: datetime, results: dict):
    """Run morning digest for a single tenant."""
    from modules.incident_cluster import get_emergency_config
    from sansadx_backend.db import get_tenant_phone_number_id
    from sqlalchemy import text
    from sansadx_backend.db import engine

    config = get_emergency_config(tenant.id)

    if not config.get("morning_digest_enabled", True):
        return

    pa_phone = config.get("pa_phone")
    if not pa_phone:
        logger.debug("Digest skipped for tenant %s — pa_phone not configured", tenant.id)
        return

    # Find T0 clusters: created in last 24h, never escalated beyond t0
    with engine.connect() as conn:
        t0_clusters = conn.execute(
            text("""
                SELECT id, hazard_type, assembly, ward,
                       unique_sender_count, window_start, raw_case_ids
                FROM incident_clusters
                WHERE tenant_id = :tid
                  AND alert_level = 't0'
                  AND created_at >= :cutoff
                ORDER BY created_at DESC
            """),
            {"tid": tenant.id, "cutoff": cutoff},
        ).mappings().all()

        # Also find is_critical cases that were never clustered at all
        # (single case, emergency status, no cluster assigned)
        unclustered_emergency_cases = conn.execute(
            text("""
                SELECT id, user_phone, location, assembly, ward,
                       category, problem_domain, raw_message, created_at
                FROM cases
                WHERE tenant_id = :tid
                  AND (status = 'emergency' OR is_critical = true)
                  AND created_at >= :cutoff
                  AND (is_deleted = false OR is_deleted IS NULL)
                ORDER BY created_at DESC
                LIMIT 50
            """),
            {"tid": tenant.id, "cutoff": cutoff},
        ).mappings().all()

    if not t0_clusters and not unclustered_emergency_cases:
        return  # Nothing to report

    # Build digest message
    lines = ["📋 *Morning Emergency Digest* — last 24 hours (unverified)\n"]

    if t0_clusters:
        lines.append(f"*Silent clusters (T0 — never escalated): {len(t0_clusters)}*")
        for c in t0_clusters:
            area = c["assembly"] or "unknown area"
            ward = f", {c['ward']}" if c.get("ward") else ""
            hazard = (c["hazard_type"] or "emergency").upper()
            count = c["unique_sender_count"]
            ts = _fmt_time(c["window_start"])
            lines.append(f"• [{ts}] {hazard} — {area}{ward} ({count} report{'s' if count != 1 else ''})")

    if unclustered_emergency_cases:
        lines.append(f"\n*Single-reporter emergencies: {len(unclustered_emergency_cases)}*")
        for c in unclustered_emergency_cases:
            area = c.get("assembly") or c.get("location") or "unknown area"
            cat = c.get("problem_domain") or c.get("category") or "emergency"
            ts = _fmt_time(c["created_at"])
            preview = (c["raw_message"] or "")[:60].replace("\n", " ")
            lines.append(f"• [{ts}] {cat} — {area} | \"{preview}\"")

    lines.append("\n_These were not escalated (single report or below threshold). Manual review recommended._")

    message = "\n".join(lines)

    try:
        from modules.whatsapp import send_whatsapp_message
        phone_number_id = get_tenant_phone_number_id(tenant.id)
        send_whatsapp_message(pa_phone, message, phone_number_id)
        results["digests_sent"] += 1
        logger.info("Morning digest sent to PA for tenant %s (%d items)", tenant.id, len(t0_clusters) + len(unclustered_emergency_cases))
    except Exception as exc:
        raise RuntimeError(f"WhatsApp send failed: {exc}") from exc


def _fmt_time(dt) -> str:
    """Format datetime for digest message. Returns IST time string."""
    if not dt:
        return "unknown time"
    try:
        # Convert UTC → IST (UTC+5:30)
        ist = dt + timedelta(hours=5, minutes=30)
        return ist.strftime("%d %b %H:%M IST")
    except Exception:
        return str(dt)[:16]


if __name__ == "__main__":
    import sys
    tid = int(sys.argv[1]) if len(sys.argv) > 1 else None
    result = run_morning_digest(tid)
    print(result)
