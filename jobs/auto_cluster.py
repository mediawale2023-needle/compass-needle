"""
Auto-clustering job: Groups similar grievance cases by category + location.
Runs nightly via cron or manual trigger.

Uses simple grouping (not ML) — clusters by (category, location) pairs.
Future: Add embeddings-based semantic clustering.
"""
import logging
import json
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger("needle.cluster")


def run_clustering(tenant_id=None):
    """
    Cluster cases from the last 30 days by (category, location).
    Returns a list of clusters with case IDs.
    """
    try:
        return _run_clustering(tenant_id)
    except Exception as e:
        logger.error("Clustering failed for tenant %s: %s", tenant_id, e, exc_info=True)
        return []


def _run_clustering(tenant_id=None):
    from sansadx_backend.db import engine
    from sqlalchemy import text

    conditions = ["(c.is_deleted = false OR c.is_deleted IS NULL)"]
    params = {}

    if tenant_id:
        conditions.append("c.tenant_id = :tid")
        params["tid"] = tenant_id

    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    conditions.append("c.created_at >= :since")
    params["since"] = thirty_days_ago

    where = " AND ".join(conditions)

    with engine.connect() as conn:
        rows = conn.execute(text(f"""
            SELECT c.id, c.tenant_id, c.category, c.status, c.raw_message,
                   c.case_metadata, c.created_at
            FROM cases c
            WHERE {where}
            ORDER BY c.created_at DESC
        """), params).mappings().all()

    # Group by (tenant_id, category, location)
    clusters = defaultdict(list)
    for row in rows:
        meta = row.get("case_metadata")
        location = ""
        if meta:
            if isinstance(meta, dict):
                location = meta.get("matched_value", "")
            elif isinstance(meta, str):
                try:
                    m = json.loads(meta)
                    location = m.get("matched_value", "")
                except (json.JSONDecodeError, AttributeError) as json_err:
                    logger.debug("Could not parse case_metadata JSON for case %s: %s", row.get("id"), json_err)

        key = (row["tenant_id"], row["category"] or "General", location or "Unknown")
        clusters[key].append({
            "id": row["id"],
            "status": row["status"],
            "message_preview": (row["raw_message"] or "")[:100],
            "created_at": row["created_at"].isoformat() if row.get("created_at") and hasattr(row["created_at"], "isoformat") else str(row.get("created_at", "")),
        })

    # Only return clusters with 2+ cases
    result = []
    for (tid, category, location), case_list in clusters.items():
        if len(case_list) >= 2:
            result.append({
                "tenant_id": tid,
                "category": category,
                "location": location,
                "count": len(case_list),
                "cases": case_list[:20],  # Limit to 20 per cluster
                "statuses": dict(defaultdict(int, {c["status"]: sum(1 for x in case_list if x["status"] == c["status"]) for c in case_list})),
            })

    result.sort(key=lambda x: x["count"], reverse=True)
    logger.info(f"Clustering complete: {len(result)} clusters from {len(rows)} cases")
    return result


if __name__ == "__main__":
    import sys
    tid = int(sys.argv[1]) if len(sys.argv) > 1 else None
    clusters = run_clustering(tid)
    for c in clusters[:10]:
        print(f"[{c['count']} cases] {c['category']} — {c['location']}")
