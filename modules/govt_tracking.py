"""Staff Overview: Government Tracking card.

Government portals do not push updates, so this card is built to work with what the
office records itself:

  check        filed complaints not finally closed whose status nobody has checked in
               CHECK_EVERY_DAYS days (oldest filing first), plus how many filings were
               checked recently. A check is a 'status_polled' row in govt_submission_log —
               the same record an automatic portal check writes.
  departments  every filed complaint by department: filed, waiting, resolved, oldest wait.
  resolved     resolved by government in the last 30 days vs the 30 before, average days
               from filing to resolution, and how many citizens have not been told.

Tenant-scoped; the filing time is the first 'staff_submitted' log row (falling back to
the last status change, then the case's creation).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

from core.db_helpers import _q
from modules.partners import _FILED_SQL, _NOT_NOISE_SQL, _as_dt
from modules.synthetic_cases import sql_is_live

CHECK_EVERY_DAYS = 14
RESOLVED_WINDOW_DAYS = 30
MAX_ITEMS = 50
FINAL_STATUSES = {"resolved", "disposed", "rejected"}
RESOLVED_STATUSES = {"resolved", "disposed"}
NO_DEPARTMENT = "Department not recorded"

# Staff check outcome -> government status recorded on the case.
CHECK_OUTCOMES = {
    "still_pending": (None, "Still pending (checked by staff)"),
    "resolved": ("resolved", "Resolved (checked by staff)"),
    "closed_without_fix": ("rejected", "Closed without a fix (checked by staff)"),
    "more_info": ("under_review", "Department asked for more information (checked by staff)"),
}


def _days(later: datetime | None, earlier: datetime | None) -> int | None:
    if not later or not earlier:
        return None
    return max(int((later - earlier).total_seconds() // 86400), 0)


def _filed_rows(tid: int) -> list[dict]:
    return _q(
        "SELECT c.id, c.case_ref, c.raw_message, c.category, c.govt_status, c.govt_reference_number, "
        "c.govt_department, c.govt_status_updated_at, c.govt_last_forwarded_to_citizen_at, c.created_at, "
        "f.filed_at, k.checked_at "
        "FROM cases c "
        "LEFT JOIN (SELECT case_id, MIN(created_at) AS filed_at FROM govt_submission_log "
        "           WHERE tenant_id = :tid AND action = 'staff_submitted' GROUP BY case_id) f ON f.case_id = c.id "
        "LEFT JOIN (SELECT case_id, MAX(created_at) AS checked_at FROM govt_submission_log "
        "           WHERE tenant_id = :tid AND action = 'status_polled' GROUP BY case_id) k ON k.case_id = c.id "
        "WHERE c.tenant_id = :tid AND COALESCE(c.is_deleted, FALSE) = FALSE "
        f"AND {sql_is_live('c')} AND {_NOT_NOISE_SQL} AND {_FILED_SQL} "
        "ORDER BY c.id LIMIT 5000",
        {"tid": tid},
    )


def _title(raw: str | None) -> str:
    text = " ".join(str(raw or "").split())
    return (text[:110] + "…") if len(text) > 110 else text


def govt_tracking(tid: int, portal: dict | None = None, now: datetime | None = None) -> dict:
    now = now or datetime.utcnow()
    rows = []
    for r in _filed_rows(tid):
        status = str(r.get("govt_status") or "").strip().lower()
        updated = _as_dt(r.get("govt_status_updated_at"))
        filed = _as_dt(r.get("filed_at")) or updated or _as_dt(r.get("created_at"))
        rows.append({
            "id": r["id"], "case_ref": r.get("case_ref") or f"#{r['id']}", "title": _title(r.get("raw_message")),
            "department": (r.get("govt_department") or "").strip() or NO_DEPARTMENT,
            "reference": r.get("govt_reference_number") or "",
            "status": status, "filed": filed, "updated": updated,
            "checked": _as_dt(r.get("checked_at")),
            "told": _as_dt(r.get("govt_last_forwarded_to_citizen_at")),
        })

    open_rows = [r for r in rows if r["status"] not in FINAL_STATUSES]
    cutoff = now - timedelta(days=CHECK_EVERY_DAYS)
    due = [r for r in open_rows if not r["checked"] or r["checked"] < cutoff]
    due.sort(key=lambda r: (r["filed"] or now, r["id"]))
    checked_recently = len(open_rows) - len(due)

    depts: dict[str, dict] = {}
    for r in rows:
        d = depts.setdefault(r["department"], {"name": r["department"], "filed": 0, "waiting": 0, "resolved": 0, "oldest_wait_days": None})
        d["filed"] += 1
        if r["status"] in RESOLVED_STATUSES:
            d["resolved"] += 1
        elif r["status"] not in FINAL_STATUSES:
            d["waiting"] += 1
            wait = _days(now, r["filed"])
            if wait is not None and (d["oldest_wait_days"] is None or wait > d["oldest_wait_days"]):
                d["oldest_wait_days"] = wait
    dept_rows = sorted(depts.values(), key=lambda d: (-d["filed"], d["name"]))
    slow = [d for d in dept_rows if d["waiting"] and d["name"] != NO_DEPARTMENT]
    slowest = max(slow, key=lambda d: (d["oldest_wait_days"] or 0, d["waiting"]))["name"] if slow else None

    w_start = now - timedelta(days=RESOLVED_WINDOW_DAYS)
    p_start = w_start - timedelta(days=RESOLVED_WINDOW_DAYS)
    resolved = [r for r in rows if r["status"] in RESOLVED_STATUSES and r["updated"]]
    current = sorted((r for r in resolved if r["updated"] >= w_start), key=lambda r: r["updated"], reverse=True)
    previous = [r for r in resolved if p_start <= r["updated"] < w_start]
    spans = [d for d in (_days(r["updated"], r["filed"]) for r in current) if d is not None]
    told = lambda r: bool(r["told"] and r["told"] >= r["updated"])  # noqa: E731

    def item(r: dict) -> dict:
        return {"id": r["id"], "case_ref": r["case_ref"], "title": r["title"], "department": r["department"],
                "reference": r["reference"], "filed_days": _days(now, r["filed"]),
                "last_checked_days": _days(now, r["checked"])}

    return {
        "portal": ({"name": portal.get("portal_name"), "url": portal.get("status_check_url") or portal.get("base_url")}
                   if portal else None),
        "check_every_days": CHECK_EVERY_DAYS,
        "check": {
            "due": len(due),
            "open_filed": len(open_rows),
            "checked_recently_pct": round(checked_recently / len(open_rows) * 100) if open_rows else None,
            "oldest_filed_days": _days(now, due[0]["filed"]) if due else None,
            "items": [item(r) for r in due[:MAX_ITEMS]],
        },
        "departments": {
            "filed": len(rows),
            "waiting": len(open_rows),
            "slowest": slowest,
            "rows": dept_rows,
        },
        "resolved": {
            "window_days": RESOLVED_WINDOW_DAYS,
            "count": len(current),
            "previous": len(previous),
            "avg_days": round(sum(spans) / len(spans)) if spans else None,
            "not_told": sum(1 for r in current if not told(r)),
            "items": [{"id": r["id"], "case_ref": r["case_ref"], "title": r["title"], "department": r["department"],
                       "days_to_resolve": _days(r["updated"], r["filed"]), "citizen_told": told(r)}
                      for r in current[:MAX_ITEMS]],
        },
    }


def record_check(tid: int, case_id: int, outcome: str, actor: str | None) -> dict:
    """Record what staff found when they checked a filing on the portal.

    Writes through the same persistence path as an automatic portal check, so the
    status change, audit row ('status_polled' = checked now) and lifecycle rules match.
    """
    from modules.govt_sync.orchestrator import persist_successful_status_result

    if outcome not in CHECK_OUTCOMES:
        raise ValueError("Unknown outcome")
    rows = _q(
        "SELECT c.id, c.govt_status, c.govt_reference_number FROM cases c "
        f"WHERE c.id = :cid AND c.tenant_id = :tid AND COALESCE(c.is_deleted, FALSE) = FALSE AND {_FILED_SQL}",
        {"cid": int(case_id), "tid": int(tid)},
    )
    if not rows:
        raise LookupError("Filed complaint not found")
    case = rows[0]
    new_status, label = CHECK_OUTCOMES[outcome]
    status = new_status or str(case.get("govt_status") or "").strip().lower() or "submitted"
    result = SimpleNamespace(status=status, raw_portal_status=label, checked=True, partial=False,
                             portal_detail={"source": "staff_check", "outcome": outcome}, raw_capture=None, fields=[])
    changed = persist_successful_status_result(tenant_id=int(tid), case_id=int(case_id), case_row=case,
                                               result=result, actor_username=actor)
    return {"success": True, "case_id": int(case_id), "outcome": outcome, "govt_status": status, "changed": changed}
