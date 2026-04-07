"""
case_query_formatter.py — WhatsApp-optimised response formatter for case queries.

Converts query engine results into human-readable, bold-formatted messages
suitable for WhatsApp delivery. No raw JSON, no dashboards — pure chat.
"""
from datetime import datetime

# Max cases to list in the message body (summary always included regardless)
_MAX_LISTED = 10

# Truncate raw message at this many characters
_MSG_PREVIEW_LEN = 90

_STATUS_EMOJI = {
    "pending":      "🔁",
    "new":          "🆕",
    "in_progress":  "⏳",
    "completed":    "✅",
    "resolved":     "✅",
    "closed":       "🔒",
    "irrelevant":   "❌",
    "spam":         "🚫",
    "emergency":    "🚨",
}
_DEFAULT_STATUS_EMOJI = "🔁"


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


def _fmt_phone(phone: str) -> str:
    """Strip 91 country code prefix for cleaner display."""
    if not phone:
        return "—"
    p = phone.strip()
    if p.startswith("91") and len(p) == 12:
        return p[2:]
    if p.startswith("+91") and len(p) == 13:
        return p[3:]
    return p


def _fmt_message(msg: str) -> str:
    """Trim message to preview length."""
    if not msg:
        return "—"
    msg = msg.strip().replace("\n", " ")
    if len(msg) > _MSG_PREVIEW_LEN:
        return msg[:_MSG_PREVIEW_LEN].rstrip() + "..."
    return msg


def _header(filters: dict) -> str:
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
    return f"📍 *{location_str} – {time_str}{status_str}*"


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

    filters = result.get("filters_applied", {})
    cases   = result.get("cases", [])
    total   = result.get("total", 0)

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

    lines = []

    # ── Header ────────────────────────────────────────────────────────────────
    lines.append(_header(filters))
    count_line = f"*Total: {total} complaint{'s' if total != 1 else ''}*"
    if total > _MAX_LISTED:
        count_line += f"  _({_MAX_LISTED} shown)_"
    lines.append(count_line)

    # ── Case list ─────────────────────────────────────────────────────────────
    listed = cases[:_MAX_LISTED]
    for i, case in enumerate(listed, start=1):
        cat      = case.get("category") or "General"
        status   = case.get("status") or ""
        loc      = case.get("location") or "—"
        assembly = case.get("assembly") or "—"
        phone    = _fmt_phone(case.get("phone", ""))
        message  = _fmt_message(case.get("message", ""))
        date_str = _fmt_date(case.get("created_at"))
        ref      = case.get("case_ref") or ""
        priority = "  🚨 *URGENT*" if case.get("is_critical") else ""

        status_label = status.replace("_", " ").title() if status else "—"
        status_icon  = _status_emoji(status)

        # Blank line before each item (after header block)
        lines.append("")

        # Title line: bold category + location
        title = f"*{i}. {cat} — {loc}*{priority}"
        lines.append(title)

        # Sender phone
        lines.append(f"📞 {phone}")

        # Raw message
        lines.append(f'💬 "{message}"')

        # Location + Assembly
        if loc != "—" or assembly != "—":
            if loc != "—" and assembly != "—" and loc.lower() != assembly.lower():
                lines.append(f"📍 {loc}  →  {assembly} Assembly")
            elif assembly != "—":
                lines.append(f"📍 {assembly} Assembly")
            else:
                lines.append(f"📍 {loc}")

        # Date + Status + Ref
        status_line = f"📅 {date_str}   {status_icon} {status_label}"
        if ref:
            status_line += f"   #{ref}"
        lines.append(status_line)

    # ── Summary stats ─────────────────────────────────────────────────────────
    lines.append("")
    lines.append("─────────────────────")

    high_priority = result.get("high_priority", 0)
    if high_priority:
        lines.append(f"🚨 *Urgent / High Priority: {high_priority}*")

    top_issue = result.get("top_issue", "")
    if top_issue:
        top_count = sum(1 for c in cases if (c.get("category") or "") == top_issue)
        lines.append(f"📊 Top Issue: *{top_issue}* ({top_count} cases)")

    top_loc = result.get("top_location", "")
    if top_loc:
        lines.append(f"📍 Most Affected: *{top_loc}*")

    # Status breakdown (only if no status filter was applied)
    if not filters.get("status"):
        pending_count  = sum(1 for c in cases if c.get("status") in ("pending", "new"))
        active_count   = sum(1 for c in cases if c.get("status") == "in_progress")
        resolved_count = sum(1 for c in cases if c.get("status") in ("completed", "resolved"))
        parts = []
        if pending_count:
            parts.append(f"🔁 Pending: {pending_count}")
        if active_count:
            parts.append(f"⏳ Active: {active_count}")
        if resolved_count:
            parts.append(f"✅ Resolved: {resolved_count}")
        if parts:
            lines.append("  ".join(parts))

    return "\n".join(lines)


def format_clarification_request() -> str:
    """Message to send when query is too vague to be useful."""
    return (
        "🔍 *What would you like to know?*\n\n"
        "Examples:\n"
        "• Cases in Kazimabad\n"
        "• Water complaints last 30 days\n"
        "• Pending cases in Koil assembly\n"
        "• Road issues this week"
    )
