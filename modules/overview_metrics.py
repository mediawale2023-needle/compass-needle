"""Staff Overview top strip: six period metrics, each clickable to the rows behind it.

Same definitions as the partner briefing (modules.partners), so the office and its
consultant see the same numbers:

  complaints     grievances received in the period (spam, abuse, comments excluded)
  filed          ... of those, filed with government
  resolved       ... of those, resolved by government (portal resolved / disposed)
  other_actions  ... not filed, but the office acted on or closed them
  pending        ... no action yet  (= complaints - filed - other_actions)
  new_contacts   people whose first-ever grievance falls in the period

Everything is tenant-scoped. This is the office's own data, so the row lists show
case details and contact numbers to staff (the same staff who see them in the Briefcase).
"""
from __future__ import annotations

from datetime import datetime

from core.db_helpers import _q
from modules.partners import (
    _CATEGORY_SQL, _FILED_SQL, _GOVT_RESOLVED_SQL, _LOCALITY_SQL, _OTHER_ACTION_SQL,
    ReportWindow, _as_dt, _case_scope_sql, first_case_at,
)
from modules.partner_report import _base_where, _reach

METRIC_KEYS = ("complaints", "filed", "resolved", "other_actions", "pending", "new_contacts")
MAX_ROWS = 200

_FILTERS = {
    "complaints": "TRUE",
    "filed": _FILED_SQL,
    "resolved": f"({_FILED_SQL} AND {_GOVT_RESOLVED_SQL})",
    "other_actions": _OTHER_ACTION_SQL,
    "pending": f"(NOT {_FILED_SQL} AND NOT {_OTHER_ACTION_SQL})",
}


def _bounded(tenant_id: int, window: ReportWindow) -> ReportWindow:
    return window.bounded(first_case_at([tenant_id]) if window.start is None else None)


def _counts(tid: int, start, end) -> dict:
    row = _q(
        "SELECT COUNT(*) AS complaints, "
        + ", ".join(f"COALESCE(SUM(CASE WHEN {sql} THEN 1 ELSE 0 END), 0) AS {k}"
                    for k, sql in _FILTERS.items() if k != "complaints")
        + f" {_case_scope_sql()}",
        {"tid": tid, "start": start, "end": end},
    )[0]
    out = {k: int(row[k] or 0) for k in _FILTERS}
    out["new_contacts"] = _reach(tid, start, end)["first_time"]
    return out


def overview_metrics(tenant_id: int, window: ReportWindow) -> dict:
    w = _bounded(tenant_id, window)
    now = _counts(tenant_id, w.start, w.end)
    prev = None
    if window.kind != "all":
        span = w.end - w.start
        prev = _counts(tenant_id, w.start - span, w.start)
    return {
        "window": (window.bounded(w.start) if window.start is None else window).describe(),
        "metrics": [{"key": k, "value": now[k], "previous": prev[k] if prev else None} for k in METRIC_KEYS],
    }


def format_phone(phone: str | None) -> str:
    """Indian mobiles as +91 98765 43210; anything else as stored."""
    raw = str(phone or "").strip()
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) == 12 and digits.startswith("91"):
        return f"+91 {digits[2:7]} {digits[7:]}"
    if len(digits) == 10:
        return f"+91 {digits[:5]} {digits[5:]}"
    return raw


def _case_row(r: dict, now: datetime) -> dict:
    created = _as_dt(r.get("created_at"))
    text = " ".join(str(r.get("raw_message") or "").split())
    return {
        "id": r["id"],
        "case_ref": r.get("case_ref") or f"#{r['id']}",
        "preview": (text[:140] + "…") if len(text) > 140 else text,
        "category": r.get("category") or "Uncategorised",
        "locality": r.get("locality") or "",
        "status": r.get("status") or "",
        "govt_status": r.get("govt_status") or "",
        "assigned_to": r.get("assigned_to") or "",
        "created_at": created.isoformat() if created else None,
        "age_days": max(int((now - created).total_seconds() // 86400), 0) if created else None,
    }


_CASE_COLUMNS = (
    f"c.id, c.case_ref, c.raw_message, {_CATEGORY_SQL} AS category, "
    f"COALESCE({_LOCALITY_SQL}, NULLIF(TRIM(c.location), '')) AS locality, "
    "c.status, c.govt_status, c.assigned_to, c.created_at, c.user_phone"
)


def overview_metric_rows(tenant_id: int, window: ReportWindow, key: str, limit: int = MAX_ROWS,
                         now: datetime | None = None) -> dict:
    if key not in METRIC_KEYS:
        raise KeyError(key)
    now = now or datetime.utcnow()
    w = _bounded(tenant_id, window)
    limit = max(1, min(int(limit), MAX_ROWS))
    p = {"tid": tenant_id, "start": w.start, "end": w.end, "lim": limit}

    if key != "new_contacts":
        total = int(_q(f"SELECT COUNT(*) AS n {_case_scope_sql()} AND {_FILTERS[key]}", p)[0]["n"] or 0)
        rows = _q(f"SELECT {_CASE_COLUMNS} {_case_scope_sql()} AND {_FILTERS[key]} "
                  "ORDER BY c.created_at DESC, c.id DESC LIMIT :lim", p)
        return {"key": key, "total": total, "cases": [_case_row(r, now) for r in rows]}

    people = _q(
        "SELECT t.k AS phone, t.first_at, t.n FROM ("
        f"SELECT c.user_phone AS k, MIN(c.created_at) AS first_at, COUNT(*) AS n {_base_where()} "
        "AND c.created_at < :end AND NULLIF(TRIM(COALESCE(c.user_phone, '')), '') IS NOT NULL "
        "GROUP BY c.user_phone) t WHERE t.first_at >= :start ORDER BY t.first_at DESC LIMIT :lim", p,
    )
    total = _reach(tenant_id, w.start, w.end)["first_time"]
    phones = [r["phone"] for r in people]
    if not phones:
        return {"key": key, "total": total, "contacts": []}
    names = {}
    case_rows: dict[str, list] = {}
    # Bound parameters, one per phone (never string-built into SQL).
    marks = ", ".join(f":ph{i}" for i in range(len(phones)))
    ph = {f"ph{i}": v for i, v in enumerate(phones)}
    for r in _q(f"SELECT phone, display_name FROM contacts WHERE tenant_id = :tid AND phone IN ({marks})", {"tid": tenant_id, **ph}):
        names[r["phone"]] = r.get("display_name")
    for r in _q(f"SELECT {_CASE_COLUMNS} {_base_where()} AND c.user_phone IN ({marks}) AND c.created_at < :end "
                "ORDER BY c.created_at DESC, c.id DESC", {"tid": tenant_id, "end": w.end, **ph}):
        case_rows.setdefault(r["user_phone"], []).append(_case_row(r, now))
    contacts = []
    for r in people:
        first = _as_dt(r["first_at"])
        contacts.append({
            "name": (names.get(r["phone"]) or "").strip(),
            "phone": format_phone(r["phone"]),
            "label": (names.get(r["phone"]) or "").strip() or format_phone(r["phone"]),
            "first_contact": first.isoformat() if first else None,
            "case_count": int(r["n"] or 0),
            "cases": case_rows.get(r["phone"], [])[:20],
        })
    return {"key": key, "total": total, "contacts": contacts}
