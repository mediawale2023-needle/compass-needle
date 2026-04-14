"""
case_query_engine.py — Query builder and executor for MP/PA case queries.

Takes structured filters from case_query_parser and runs them against the
cases table. Returns cases + summary statistics for the formatter.

All queries are tenant-scoped and use parameterized SQL (no injection risk).
"""
import logging
from datetime import datetime, timedelta
from core.db_helpers import _q, _q_one, _parse_meta

logger = logging.getLogger("needle.case_query_engine")

# Maximum cases to return in a single query response
_RESULT_LIMIT = 20

# Status values that are considered "pending/open"
_OPEN_STATUSES = {"pending", "new", "in_progress"}


def query_cases(filters: dict, tenant_id: int) -> dict:
    """
    Execute a case query against the DB using the given filters.

    filters keys: location, constituency, days, issue_type, status

    Returns:
        {
            "cases": [...],          # up to _RESULT_LIMIT case dicts
            "total": int,            # total matching rows (before limit)
            "high_priority": int,    # count of is_critical=true cases
            "top_issue": str,        # most frequent category
            "top_location": str,     # most frequent matched_value (location)
            "filters_applied": dict, # echo of filters for formatter
        }
    """
    where_clauses = [
        "c.tenant_id = :tid",
        "(c.is_deleted = false OR c.is_deleted IS NULL)",
        # Exclude meta-statuses that are system states, not staff-visible
        "c.status NOT IN ('awaiting_location', 'Spam', 'Spam (Offensive)')",
        "c.created_at >= :since",
    ]
    params: dict = {
        "tid":   tenant_id,
        "since": datetime.utcnow() - timedelta(days=int(filters.get("days", 7))),
        "lim":   _RESULT_LIMIT,
    }

    def _ilike_escape(s: str) -> str:
        """Escape ILIKE wildcard characters so user input matches literally."""
        return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    # ── Location filter ──────────────────────────────────────────────────────
    # Search both the raw `location` column and `case_metadata->matched_value`
    # using ILIKE for fuzzy spelling tolerance.
    location = (filters.get("location") or "").strip()
    if location:
        loc_escaped = _ilike_escape(location)
        where_clauses.append(
            "(c.location ILIKE :loc ESCAPE '\\' OR c.case_metadata::text ILIKE :loc_meta ESCAPE '\\')"
        )
        params["loc"]      = f"%{loc_escaped}%"
        params["loc_meta"] = f"%{loc_escaped}%"

    # ── Constituency / assembly filter ───────────────────────────────────────
    constituency = (filters.get("constituency") or "").strip()
    if constituency:
        cons_escaped = _ilike_escape(constituency)
        where_clauses.append(
            "(c.assembly ILIKE :assembly ESCAPE '\\' OR c.case_metadata::text ILIKE :assembly_meta ESCAPE '\\')"
        )
        params["assembly"]      = f"%{cons_escaped}%"
        params["assembly_meta"] = f"%{cons_escaped}%"

    # ── Issue type / category filter ─────────────────────────────────────────
    issue_type = (filters.get("issue_type") or "").strip()
    if issue_type:
        issue_escaped = _ilike_escape(issue_type)
        where_clauses.append("c.category ILIKE :cat ESCAPE '\\'")
        params["cat"] = f"%{issue_escaped}%"

    # ── Status filter ────────────────────────────────────────────────────────
    status = (filters.get("status") or "").strip().lower()
    if status:
        # Map query-engine status names to DB status values
        _status_db_map = {
            "pending":     ("pending", "new"),
            "new":         ("new",),
            "resolved":    ("completed", "resolved"),
            "in_progress": ("in_progress",),
        }
        db_statuses = _status_db_map.get(status, (status,))
        placeholders = ", ".join(f":st{i}" for i in range(len(db_statuses)))
        where_clauses.append(f"c.status IN ({placeholders})")
        for i, s in enumerate(db_statuses):
            params[f"st{i}"] = s

    where_sql = " AND ".join(where_clauses)

    # ── Main case query ──────────────────────────────────────────────────────
    cases_sql = f"""
        SELECT
            c.id,
            c.user_phone,
            c.category,
            c.status,
            c.raw_message,
            c.location,
            c.assembly,
            c.ward,
            c.is_critical,
            c.created_at,
            c.case_metadata,
            c.case_ref
        FROM cases c
        WHERE {where_sql}
        ORDER BY c.is_critical DESC, c.created_at DESC
        LIMIT :lim
    """

    # ── Count query (total matching, ignoring LIMIT) ─────────────────────────
    count_sql = f"SELECT COUNT(*) AS total FROM cases c WHERE {where_sql}"

    # ── Aggregation: top issue + top location (last N days, same filters) ────
    top_issue_sql = f"""
        SELECT c.category, COUNT(*) AS cnt
        FROM cases c
        WHERE {where_sql}
        GROUP BY c.category
        ORDER BY cnt DESC
        LIMIT 1
    """

    top_location_sql = f"""
        SELECT
            COALESCE(c.location, c.case_metadata->>'matched_value') AS loc,
            COUNT(*) AS cnt
        FROM cases c
        WHERE {where_sql}
          AND (c.location IS NOT NULL OR c.case_metadata->>'matched_value' IS NOT NULL)
        GROUP BY loc
        ORDER BY cnt DESC
        LIMIT 1
    """

    try:
        raw_cases   = _q(cases_sql, params)
        count_row   = _q_one(count_sql, {k: v for k, v in params.items() if k != "lim"})
        issue_row   = _q_one(top_issue_sql, {k: v for k, v in params.items() if k != "lim"})
        loc_row     = _q_one(top_location_sql, {k: v for k, v in params.items() if k != "lim"})
    except Exception as exc:
        logger.error("case_query_engine DB error: %s", exc)
        return {
            "cases": [],
            "total": 0,
            "high_priority": 0,
            "top_issue": "",
            "top_location": "",
            "filters_applied": filters,
            "error": "DB query failed",
        }

    total = count_row["total"] if count_row else 0

    # ── Enrich each case with metadata fields ────────────────────────────────
    enriched = []
    high_priority_count = 0
    for row in raw_cases:
        meta = _parse_meta(row.get("case_metadata"))
        location_display = (
            row.get("location")
            or meta.get("matched_value")
            or meta.get("assembly_constituency")
            or row.get("assembly")
            or ""
        )
        assembly_display = (
            row.get("assembly")
            or meta.get("assembly_constituency")
            or ""
        )
        if row.get("is_critical"):
            high_priority_count += 1

        enriched.append({
            "id":         row["id"],
            "phone":      row.get("user_phone", ""),
            "category":   row.get("category", "General"),
            "status":     row.get("status", ""),
            "message":    row.get("raw_message", ""),
            "location":   location_display,
            "assembly":   assembly_display,
            "ward":       row.get("ward", ""),
            "is_critical": bool(row.get("is_critical")),
            "created_at": row["created_at"],
            "case_ref":   row.get("case_ref", ""),
        })

    return {
        "cases":           enriched,
        "total":           total,
        "high_priority":   high_priority_count,
        "top_issue":       issue_row["category"] if issue_row else "",
        "top_location":    loc_row["loc"] if loc_row and loc_row.get("loc") else "",
        "filters_applied": filters,
    }
