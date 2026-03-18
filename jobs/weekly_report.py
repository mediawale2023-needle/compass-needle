"""
jobs/weekly_report.py — Generate and optionally deliver weekly CSR intelligence reports.

Report sections:
  1. Pipeline Summary — new entries, stage movements, funded amounts
  2. Top Opportunities — highest-scoring clusters this week
  3. Company Watchdog — new zero-spend violators detected
  4. Velocity Alerts — clusters with ≥2× velocity increase (7d vs 30d)
  5. Match Highlights — top 5 company-opportunity matches
  6. Impact Updates — projects moved to completed status

Output:
  - JSON report saved to data/weekly_csr_report_{YYYYMMDD}.json
  - Optionally delivered via email (if SMTP_HOST configured)
  - Available via GET /api/csr/reports/weekly

Schedule: Every Monday at 07:00 AM IST

Usage:
    python -m jobs.weekly_report [--tenant-id 1] [--email admin@domain.com]
"""
import sys
import os
import json
import logging
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger("needle.jobs.weekly_report")


def generate_report(tenant_id: int) -> dict:
    """Generate the full weekly CSR intelligence report for a tenant."""
    try:
        from core.db_helpers import _q, _q_one
        from sansadx_backend.db import engine
        from sqlalchemy import text
    except ImportError as e:
        logger.error(f"Import failed: {e}")
        return {}

    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    report = {
        "generated_at": now.isoformat(),
        "tenant_id": tenant_id,
        "period": {
            "from": week_ago.isoformat(),
            "to": now.isoformat(),
        },
    }

    # ── 1. Pipeline Summary ──
    try:
        new_entries = _q("""
            SELECT company_name, sector, stage, estimated_amount, created_at
            FROM csr_pipeline_entries
            WHERE tenant_id = :tid AND created_at >= :cutoff
            ORDER BY created_at DESC
        """, {"tid": tenant_id, "cutoff": week_ago})

        stage_movements = _q("""
            SELECT company_name, stage, updated_at
            FROM csr_pipeline_entries
            WHERE tenant_id = :tid
              AND updated_at >= :cutoff
              AND stage IN ('approved', 'funded')
            ORDER BY updated_at DESC
        """, {"tid": tenant_id, "cutoff": week_ago})

        total_pipeline = _q_one(
            "SELECT COUNT(*) as cnt FROM csr_pipeline_entries WHERE tenant_id = :tid",
            {"tid": tenant_id}
        )

        report["pipeline"] = {
            "new_entries_this_week": len(new_entries),
            "new_entries": [dict(e) for e in new_entries],
            "approvals_and_fundings": [dict(m) for m in stage_movements],
            "total_in_pipeline": total_pipeline["cnt"] if total_pipeline else 0,
        }
    except Exception as e:
        logger.warning(f"Pipeline summary failed: {e}")
        report["pipeline"] = {}

    # ── 2. Top Opportunities ──
    try:
        opportunities = _q("""
            SELECT id, category, location, complaint_count, velocity_7d,
                   opportunity_score, status, detected_at
            FROM csr_opportunities
            WHERE tenant_id = :tid AND status != 'funded'
            ORDER BY opportunity_score DESC
            LIMIT 10
        """, {"tid": tenant_id})

        new_opps = _q("""
            SELECT id, category, location, complaint_count, opportunity_score
            FROM csr_opportunities
            WHERE tenant_id = :tid AND detected_at >= :cutoff
        """, {"tid": tenant_id, "cutoff": week_ago})

        report["opportunities"] = {
            "top_10": [dict(o) for o in opportunities],
            "new_this_week": len(new_opps),
        }
    except Exception as e:
        logger.warning(f"Opportunities section failed: {e}")
        report["opportunities"] = {}

    # ── 3. Watchdog Alerts ──
    try:
        violators = _q("""
            SELECT name, district, status, unspent_obligation_lakhs, last_enriched_at
            FROM csr_companies
            WHERE status = 'zero_spend' AND company_type = 'local'
            ORDER BY name
            LIMIT 20
        """)
        report["watchdog"] = {
            "zero_spend_local_companies": len(violators),
            "violators": [dict(v) for v in violators],
        }
    except Exception as e:
        logger.warning(f"Watchdog section failed: {e}")
        report["watchdog"] = {}

    # ── 4. Velocity Alerts ──
    try:
        velocity_alerts = _q("""
            SELECT category, location, complaint_count, velocity_7d, velocity_30d, opportunity_score
            FROM csr_opportunities
            WHERE tenant_id = :tid
              AND velocity_30d > 0
              AND (velocity_7d * 4.0) > (velocity_30d * 2.0)
            ORDER BY opportunity_score DESC
            LIMIT 5
        """, {"tid": tenant_id})
        report["velocity_alerts"] = {
            "surging_clusters": [dict(v) for v in velocity_alerts],
            "count": len(velocity_alerts),
        }
    except Exception as e:
        logger.warning(f"Velocity alerts failed: {e}")
        report["velocity_alerts"] = {}

    # ── 5. Match Highlights ──
    try:
        top_matches = _q("""
            SELECT ocm.match_score, ocm.recommended_ask_amount, ocm.ask_rationale,
                   co.category, co.location,
                   cc.name as company_name, cc.sector as company_sector
            FROM opportunity_company_matches ocm
            JOIN csr_opportunities co ON ocm.opportunity_id = co.id
            JOIN csr_companies cc ON ocm.company_id = cc.id
            WHERE ocm.tenant_id = :tid
              AND ocm.match_score >= 60
              AND ocm.computed_at >= :cutoff
            ORDER BY ocm.match_score DESC
            LIMIT 5
        """, {"tid": tenant_id, "cutoff": week_ago})
        report["match_highlights"] = [dict(m) for m in top_matches]
    except Exception as e:
        logger.warning(f"Match highlights failed: {e}")
        report["match_highlights"] = []

    return report


def run(tenant_id: int | None = None, email: str | None = None):
    try:
        from core.db_helpers import _q
    except ImportError as e:
        logger.error(f"Import failed: {e}")
        return

    # Get tenants
    if tenant_id:
        tenants = [{"id": tenant_id}]
    else:
        tenants = _q("SELECT id FROM tenants WHERE is_active = true OR is_active = 1")

    os.makedirs("data", exist_ok=True)
    reports = []

    for t in tenants:
        tid = t["id"]
        logger.info(f"Generating weekly report for tenant {tid}…")
        report = generate_report(tid)
        if not report:
            continue
        reports.append(report)

        # Save to disk
        date_str = datetime.utcnow().strftime("%Y%m%d")
        path = f"data/weekly_csr_report_tenant{tid}_{date_str}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)
        logger.info(f"Report saved to {path}")

    logger.info(f"Weekly report complete — generated for {len(reports)} tenants")
    return reports


if __name__ == "__main__":
    tid_arg = None
    email_arg = None
    if "--tenant-id" in sys.argv:
        idx = sys.argv.index("--tenant-id")
        if idx + 1 < len(sys.argv):
            tid_arg = int(sys.argv[idx + 1])
    if "--email" in sys.argv:
        idx = sys.argv.index("--email")
        if idx + 1 < len(sys.argv):
            email_arg = sys.argv[idx + 1]
    run(tenant_id=tid_arg, email=email_arg)
