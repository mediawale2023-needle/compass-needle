"""
case_query_formatter.py — WhatsApp-optimised response formatter for case queries.

Converts query engine results into human-readable, emoji-formatted messages
suitable for WhatsApp delivery. No raw JSON, no dashboards — pure chat.
"""
from datetime import datetime, timezone

# Max cases to list in the message body (summary always included regardless)
_MAX_LISTED = 10

# Emoji map for common issue categories
_CATEGORY_EMOJI = {
    "water":         "💧",
    "road":          "🚧",
    "electricity":   "⚡",
    "health":        "🏥",
    "sanitation":    "🚽",
    "drainage":      "🚽",
    "housing":       "🏠",
    "land":          "🌾",
    "education":     "📚",
    "school":        "📚",
    "tree":          "🌳",
    "noise":         "📢",
    "general":       "📋",
    "spam":          "🚫",
    "emergency":     "🚨",
}

_STATUS_EMOJI = {
    "pending":     "🔁",
    "new":         "🆕",
    "in_progress": "⏳",
    "completed":   "✅",
    "resolved":    "✅",
    "emergency":   "🚨",
}

_DEFAULT_CATEGORY_EMOJI = "📋"
_DEFAULT_STATUS_EMOJI   = "🔁"


def _cat_emoji(category: str) -> str:
    return _CATEGORY_EMOJI.get((category or "").lower().split()[0], _DEFAULT_CATEGORY_EMOJI)


def _status_emoji(status: str) -> str:
    return _STATUS_EMOJI.get((status or "").lower(), _DEFAULT_STATUS_EMOJI)


def _fmt_date(dt) -> str:
    """Format a datetime to a short human-readable string e.g. '12 Mar'."""
    if dt is None:
        return "—"
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except ValueError:
            return dt[:10]
    try:
        return dt.strftime("%-d %b")
    except ValueError:
        return str(dt)[:10]


def _header(filters: dict, total: int) -> str:
    """Build the header line summarising what was queried."""
    parts = []

    constituency = (filters.get("constituency") or "").strip()
    location     = (filters.get("location") or "").strip()
    issue_type   = (filters.get("issue_type") or "").strip()
    days         = int(filters.get("days", 7))
    status       = (filters.get("status") or "").strip()

    if constituency:
        parts.append(f"{constituency} Assembly")
    if location:
        parts.append(location)
    if issue_type:
        parts.append(issue_type)

    location_str = " · ".join(parts) if parts else "All Areas"

    if days == 1:
        time_str = "Today"
    elif days == 7:
        time_str = "Last 7 Days"
    elif days == 30:
        time_str = "Last 30 Days"
    else:
        time_str = f"Last {days} Days"

    status_str = f" · {status.replace('_', ' ').title()}" if status else ""

    return f"📍 {location_str} – {time_str}{status_str}"


def format_cases_for_whatsapp(result: dict) -> str:
    """
    Format a query engine result dict into a WhatsApp-ready text message.

    Handles:
    - No results → clarifying message
    - Results → header + case list (capped at _MAX_LISTED) + summary stats
    - result["error"] → friendly error message
    """
    if result.get("error"):
        return (
            "⚠️ Sorry, I couldn't fetch the cases right now. "
            "Please try again in a moment."
        )

    filters  = result.get("filters_applied", {})
    cases    = result.get("cases", [])
    total    = result.get("total", 0)

    # ── No results ────────────────────────────────────────────────────────────
    if total == 0:
        location = (filters.get("location") or filters.get("constituency") or "").strip()
        area_str = f" in *{location}*" if location else ""
        return (
            f"🔍 No cases found{area_str} for the selected filters.\n\n"
            "Try:\n"
            "• Removing the status filter\n"
            "• Checking the spelling of the area\n"
            "• Expanding the time range (e.g. \"last 30 days\")"
        )

    # ── No filters given (ambiguous query) ──────────────────────────────────
    location     = (filters.get("location") or "").strip()
    constituency = (filters.get("constituency") or "").strip()
    if not location and not constituency:
        # Still show results but prepend a note
        pass  # proceed to normal output

    lines = []

    # Header
    lines.append(_header(filters, total))
    lines.append(f"\n*Total Cases: {total}*")

    if total > _MAX_LISTED:
        lines.append(f"_(Showing top {_MAX_LISTED} of {total})_")

    lines.append("")

    # Case list
    listed = cases[:_MAX_LISTED]
    for i, case in enumerate(listed, start=1):
        cat      = case.get("category", "General")
        status   = case.get("status", "")
        loc      = case.get("location") or case.get("assembly") or case.get("ward") or "—"
        date_str = _fmt_date(case.get("created_at"))
        ref      = case.get("case_ref", "")
        priority_flag = " 🚨" if case.get("is_critical") else ""

        line = (
            f"{i}. {_cat_emoji(cat)} {cat} – {loc}{priority_flag}\n"
            f"   📅 {date_str}  {_status_emoji(status)} {status.replace('_', ' ').title()}"
        )
        if ref:
            line += f"  #{ref}"
        lines.append(line)

    # Summary stats block
    lines.append("")
    lines.append("─────────────────")

    high_priority = result.get("high_priority", 0)
    if high_priority:
        lines.append(f"🚨 High Priority: {high_priority}")

    top_issue = result.get("top_issue", "")
    if top_issue:
        # Count how many cases have this category
        top_count = sum(1 for c in cases if (c.get("category") or "") == top_issue)
        lines.append(f"📊 Top Issue: {top_issue} ({top_count} cases)")

    top_loc = result.get("top_location", "")
    if top_loc:
        lines.append(f"📍 Most Affected: {top_loc}")

    # Status breakdown (only if no status filter was applied)
    if not filters.get("status"):
        pending_count  = sum(1 for c in cases if c.get("status") in ("pending", "new"))
        resolved_count = sum(1 for c in cases if c.get("status") in ("completed", "resolved"))
        if pending_count or resolved_count:
            breakdown_parts = []
            if pending_count:
                breakdown_parts.append(f"🔁 Pending: {pending_count}")
            if resolved_count:
                breakdown_parts.append(f"✅ Resolved: {resolved_count}")
            lines.append("  ".join(breakdown_parts))

    return "\n".join(lines)


def format_clarification_request() -> str:
    """Message to send when query has neither location nor constituency."""
    return (
        "🔍 Please specify a location or constituency.\n\n"
        "Examples:\n"
        "• *Cases in Tilakwadi*\n"
        "• *Water complaints last 30 days*\n"
        "• *Pending cases in Vikhroli assembly*\n"
        "• *Road issues in Ward 5 this week*"
    )
