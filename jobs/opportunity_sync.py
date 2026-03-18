"""
jobs/opportunity_sync.py — Populate the csr_opportunities table from live grievance clusters.

This job:
  1. Queries all active tenants
  2. Calls get_grievance_clusters() for each tenant
  3. Computes opportunity scores with velocity
  4. Upserts results into csr_opportunities table
  5. Transitions status: emerging → monitoring → ready

Schedule: Every 6 hours (or on-demand via POST /api/csr/opportunities/sync)

Usage:
    python -m jobs.opportunity_sync
"""
import sys
import os
import json
import logging
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger("needle.jobs.opportunity_sync")


def run():
    try:
        from sansadx_backend.db import engine
        from sqlalchemy import text
        from modules.csr_pipeline import get_grievance_clusters, CATEGORY_SECTOR_MAP, CSR_MONITOR_THRESHOLD
        from core.db_helpers import _q
    except ImportError as e:
        logger.error(f"Import failed: {e}")
        return

    now = datetime.utcnow()
    cutoff_7d = now - timedelta(days=7)
    cutoff_30d = now - timedelta(days=30)

    # Load all active tenants with their constituency
    try:
        tenants = _q("SELECT id, constituency FROM tenants WHERE is_active = true OR is_active = 1")
    except Exception as e:
        logger.error(f"Failed to load tenants: {e}")
        return

    total_upserted = 0

    for tenant in tenants:
        tid = tenant["id"]
        constituency = tenant.get("constituency") or ""

        try:
            clusters = get_grievance_clusters(tid, CSR_MONITOR_THRESHOLD)
        except Exception as e:
            logger.warning(f"Cluster fetch failed for tenant {tid}: {e}")
            continue

        for cluster in clusters:
            category = cluster["category"]
            volume = cluster["volume"]
            affected_areas_json = json.dumps(cluster.get("affected_areas", []))

            # Compute velocities (category-level, across all areas)
            try:
                with engine.connect() as conn:
                    v7 = conn.execute(text("""
                        SELECT COUNT(*) as cnt FROM cases
                        WHERE tenant_id = :tid AND category = :cat
                          AND status NOT IN ('irrelevant', 'offensive')
                          AND created_at >= :cutoff
                    """), {"tid": tid, "cat": category, "cutoff": cutoff_7d}).fetchone()[0] or 0

                    v30 = conn.execute(text("""
                        SELECT COUNT(*) as cnt FROM cases
                        WHERE tenant_id = :tid AND category = :cat
                          AND status NOT IN ('irrelevant', 'offensive')
                          AND created_at >= :cutoff
                    """), {"tid": tid, "cat": category, "cutoff": cutoff_30d}).fetchone()[0] or 0
            except Exception:
                v7, v30 = 0, 0

            # Compute opportunity score
            from api_router import _compute_opportunity_score
            try:
                score = _compute_opportunity_score(volume, v7, 3)
            except Exception:
                vol_s = min(40.0, (volume / 500.0) * 40.0)
                vel_s = min(30.0, (v7 / 50.0) * 30.0)
                score = round(vol_s + vel_s + 6.0 + 10.0, 1)

            # Status lifecycle
            if volume >= 500:
                status = "ready"
            elif volume >= 200:
                status = "monitoring"
            else:
                status = "emerging"

            # Upsert — keyed on (tenant_id, category) only; one row per issue type
            try:
                with engine.begin() as conn:
                    existing = conn.execute(text("""
                        SELECT id FROM csr_opportunities
                        WHERE tenant_id = :tid AND category = :cat
                    """), {"tid": tid, "cat": category}).fetchone()

                    if existing:
                        conn.execute(text("""
                            UPDATE csr_opportunities
                            SET complaint_count = :vol,
                                velocity_7d = :v7,
                                velocity_30d = :v30,
                                opportunity_score = :score,
                                status = :status,
                                location = :loc,
                                affected_areas = :areas,
                                last_scored_at = :now
                            WHERE id = :id
                        """), {
                            "vol": volume, "v7": v7, "v30": v30,
                            "score": score, "status": status,
                            "loc": constituency, "areas": affected_areas_json,
                            "now": now, "id": existing[0]
                        })
                    else:
                        conn.execute(text("""
                            INSERT INTO csr_opportunities
                                (tenant_id, category, location, affected_areas,
                                 complaint_count, velocity_7d, velocity_30d,
                                 opportunity_score, status, detected_at, last_scored_at)
                            VALUES
                                (:tid, :cat, :loc, :areas,
                                 :vol, :v7, :v30, :score,
                                 :status, :now, :now)
                        """), {
                            "tid": tid, "cat": category,
                            "loc": constituency, "areas": affected_areas_json,
                            "vol": volume, "v7": v7, "v30": v30,
                            "score": score, "status": status, "now": now
                        })
                    total_upserted += 1
            except Exception as e:
                logger.warning(f"Upsert failed for {category} tenant {tid}: {e}")

    logger.info(f"Opportunity sync complete — {total_upserted} opportunities upserted across {len(tenants)} tenants")
    return {"upserted": total_upserted, "tenants": len(tenants)}


if __name__ == "__main__":
    run()
