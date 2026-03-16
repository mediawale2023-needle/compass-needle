"""
jobs/scoring_recompute.py — Recompute multi-dimensional match scores for all opportunities.

This job:
  1. Loads all csr_opportunities that need re-scoring (status != 'funded', or older than 24h)
  2. Loads all CSR companies from the DB
  3. Calls the matching engine for each (opportunity, tenant) pair
  4. Persists ranked matches into opportunity_company_matches

Schedule: Daily at 02:00 AM IST (recommended)

Usage:
    python -m jobs.scoring_recompute [--all]   # --all forces rescore even recent ones
"""
import sys
import os
import logging
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger("needle.jobs.scoring_recompute")


def run(force_all: bool = False):
    try:
        from sansadx_backend.db import engine
        from sqlalchemy import text
        from modules.csr_matching_engine import rank_companies_for_opportunity, persist_matches
        from core.db_helpers import _q
    except ImportError as e:
        logger.error(f"Import failed: {e}")
        return

    now = datetime.utcnow()
    stale_cutoff = now - timedelta(hours=24)

    # Load opportunities that need scoring
    try:
        if force_all:
            opportunities = _q("""
                SELECT id, tenant_id, category, location, complaint_count,
                       velocity_7d, velocity_30d, opportunity_score, status
                FROM csr_opportunities
                WHERE status != 'funded'
            """)
        else:
            opportunities = _q("""
                SELECT id, tenant_id, category, location, complaint_count,
                       velocity_7d, velocity_30d, opportunity_score, status
                FROM csr_opportunities
                WHERE status != 'funded'
                  AND (last_scored_at IS NULL OR last_scored_at < :cutoff)
            """, {"cutoff": stale_cutoff})
    except Exception as e:
        logger.error(f"Failed to load opportunities: {e}")
        return

    if not opportunities:
        logger.info("No opportunities need re-scoring")
        return

    logger.info(f"Re-scoring {len(opportunities)} opportunities…")

    # Load all companies once
    try:
        companies_raw = _q("SELECT * FROM csr_companies ORDER BY name")
        companies = []
        for r in companies_raw:
            companies.append({
                "id": r["id"],
                "Company": r["name"],
                "name": r["name"],
                "slug": r.get("slug", ""),
                "District": r.get("district", ""),
                "district": r.get("district", ""),
                "sector": r.get("sector", ""),
                "Sector": r.get("sector", ""),
                "sector_priorities": r.get("sector_priorities"),
                "company_type": r.get("company_type", "remote"),
                "Type": "Local" if r.get("company_type") == "local" else "Remote",
                "total_3y_lakhs": r.get("total_3y_lakhs"),
                "avg_ticket_size_lakhs": r.get("avg_ticket_size_lakhs"),
            })
    except Exception as e:
        logger.error(f"Failed to load companies: {e}")
        return

    from modules.csr_pipeline import CATEGORY_SECTOR_MAP

    scored = 0
    for opp in opportunities:
        try:
            csr_sector = CATEGORY_SECTOR_MAP.get(opp["category"], "General CSR")
            opp_enriched = {
                "category": opp["category"],
                "area": opp.get("location", ""),
                "volume": opp["complaint_count"],
                "velocity_7d": opp.get("velocity_7d", 0),
                "csr_sector": csr_sector,
            }
            ranked = rank_companies_for_opportunity(
                opportunity=opp_enriched,
                companies=companies,
                tenant_id=opp["tenant_id"],
                top_n=10,
            )
            persist_matches(opp["id"], opp["tenant_id"], ranked)

            # Update last_scored_at on the opportunity
            with engine.begin() as conn:
                conn.execute(text(
                    "UPDATE csr_opportunities SET last_scored_at = :now WHERE id = :id"
                ), {"now": now, "id": opp["id"]})

            scored += 1
        except Exception as e:
            logger.warning(f"Scoring failed for opportunity {opp['id']}: {e}")

    logger.info(f"Scoring recompute complete — {scored}/{len(opportunities)} opportunities scored")
    return {"scored": scored, "total": len(opportunities)}


if __name__ == "__main__":
    force = "--all" in sys.argv
    run(force_all=force)
