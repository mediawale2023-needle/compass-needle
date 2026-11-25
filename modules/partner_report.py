"""White-label client report for partners (consultancies).

Three editions, chosen from the tenant itself — never from the request:
  * mla       — sitting MLA: defend the record, prove delivery.
  * mp        — sitting MP: the same, plus an assembly-segment comparison.
  * aspirant  — not in office: presence, pressure applied, issues to own.

Everything here is tenant-scoped GROUP BY aggregates over live grievances. No case rows,
message text, phone numbers, portal reference numbers or free-text addresses are read
into the output; people are only ever COUNTED (COUNT DISTINCT), never listed. Small
locality counts are suppressed. Every interpolated string in the HTML is escaped.
"""
from __future__ import annotations

import html
import math
from datetime import datetime, timedelta

from core.db_helpers import _q
from modules.partners import (
    _CATEGORY_SQL, _FILED_SQL, _GOVT_RESOLVED_SQL, _LOCALITY_SQL, _NOT_NOISE_SQL, _OTHER_ACTION_SQL,
    ReportWindow, _as_dt, _bucket_sql, _case_scope_sql, _dialect, clean_color, client_briefing, first_case_at,
)
from modules.synthetic_cases import sql_is_live

SMALL_COUNT = 3                 # locality / people counts below this print as "<3"
OFFICE_CLOSED_STATUSES = ("resolved", "completed", "closed")
WEEKS = 8
PRESENCE_STRONG, PRESENCE_GROWING = 10, 3
MAX_REPORT_ROWS = 10
FLANK_TAG = '<span class="tagx plank">Weak flank</span>'

_LANG_NAMES = {
    "en": "English", "english": "English", "hi": "Hindi", "hindi": "Hindi", "hinglish": "Hinglish",
    "mr": "Marathi", "marathi": "Marathi", "kn": "Kannada", "kannada": "Kannada", "ta": "Tamil", "tamil": "Tamil",
    "te": "Telugu", "telugu": "Telugu", "ml": "Malayalam", "malayalam": "Malayalam", "bn": "Bengali",
    "bengali": "Bengali", "gu": "Gujarati", "gujarati": "Gujarati", "pa": "Punjabi", "punjabi": "Punjabi",
    "or": "Odia", "odia": "Odia", "as": "Assamese", "assamese": "Assamese", "ur": "Urdu", "urdu": "Urdu",
}


# ─────────────────────────────────────────
# EDITION
# ─────────────────────────────────────────
def report_edition(tenant, seat_type: str | None) -> str:
    from sansadx_backend.db import derive_account_stage, derive_seat_type

    if tenant is not None and derive_account_stage(tenant) == "aspirant":
        return "aspirant"
    st = (seat_type or (derive_seat_type(tenant) if tenant is not None else "mp") or "mp").lower()
    return "mla" if st == "mla" else "mp"


# ─────────────────────────────────────────
# AGGREGATES
# ─────────────────────────────────────────
def _base_where() -> str:
    return (
        "FROM cases c WHERE c.tenant_id = :tid AND COALESCE(c.is_deleted, FALSE) = FALSE "
        f"AND {sql_is_live('c')} AND {_NOT_NOISE_SQL}"
    )


def _open_sql() -> str:
    closed = ", ".join(f"'{s}'" for s in OFFICE_CLOSED_STATUSES)
    return f"(LOWER(COALESCE(c.status, '')) NOT IN ({closed}) AND NOT ({_FILED_SQL} AND {_GOVT_RESOLVED_SQL}))"


def _days_sql(later: str, earlier: str) -> str:
    if _dialect() == "postgresql":
        return f"GREATEST(EXTRACT(EPOCH FROM ({later} - {earlier})) / 86400.0, 0)"
    return f"MAX(julianday({later}) - julianday({earlier}), 0)"


def _sup(n: int) -> str:
    return f"<{SMALL_COUNT}" if 0 < n < SMALL_COUNT else str(n)


def _reach(tid: int, start, end) -> dict:
    """People counted (never listed): distinct senders in the window, split first-time / returning."""
    row = _q(
        "SELECT COUNT(*) AS people, COALESCE(SUM(CASE WHEN first_at >= :start THEN 1 ELSE 0 END), 0) AS first_time "
        "FROM (SELECT c.user_phone AS k, MIN(c.created_at) AS first_at "
        f"{_base_where()} AND c.created_at < :end AND NULLIF(TRIM(COALESCE(c.user_phone, '')), '') IS NOT NULL "
        "GROUP BY c.user_phone HAVING MAX(c.created_at) >= :start) t",
        {"tid": tid, "start": start, "end": end},
    )[0]
    people, first = int(row["people"] or 0), int(row["first_time"] or 0)
    return {"people": people, "first_time": first, "returning": people - first}


def _languages(tid: int, window: ReportWindow) -> list[dict]:
    rows = _q(
        "SELECT LOWER(TRIM(COALESCE(CAST(c.case_metadata->>'detected_language' AS TEXT), "
        "CAST(c.case_metadata->>'language' AS TEXT), ''))) AS lang, COUNT(*) AS n "
        f"{_case_scope_sql()} GROUP BY 1",
        {"tid": tid, "start": window.start, "end": window.end},
    )
    counts: dict[str, int] = {}
    for r in rows:
        name = _LANG_NAMES.get((r["lang"] or "").strip())
        if name:
            counts[name] = counts.get(name, 0) + int(r["n"] or 0)
    total = sum(counts.values())
    if not total:
        return []
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    top = [{"name": n, "share": round(c / total * 100)} for n, c in ranked[:4]]
    rest = sum(c for _, c in ranked[4:])
    if rest:
        top.append({"name": "Other", "share": round(rest / total * 100)})
    return top


def _weekly_trend(tid: int, end: datetime) -> dict:
    start = end - timedelta(days=7 * WEEKS)
    p = {"tid": tid, "start": start, "end": end, "bucket": 7}
    rows = _q(f"SELECT {_CATEGORY_SQL} AS name, {_bucket_sql()} AS b, COUNT(*) AS n {_case_scope_sql()} GROUP BY 1, 2", p)
    totals: dict[str, int] = {}
    for r in rows:
        totals[r["name"]] = totals.get(r["name"], 0) + int(r["n"] or 0)
    top = [n for n, _ in sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))[:3]]
    series = {n: [0] * WEEKS for n in top}
    other = [0] * WEEKS
    for r in rows:
        if r["b"] is None:
            continue
        pos = WEEKS - 1 - int(r["b"])
        if not 0 <= pos < WEEKS:
            continue
        (series[r["name"]] if r["name"] in series else other)[pos] += int(r["n"] or 0)
    out = [{"name": n, "values": series[n]} for n in top]
    if any(other):
        out.append({"name": "Other", "values": other})
    labels = [(start + timedelta(days=7 * i)).strftime("%d %b") for i in range(WEEKS)]
    return {"labels": labels, "series": out}


def _departments(tid: int, window: ReportWindow) -> list[dict]:
    resolved = f"{_FILED_SQL} AND {_GOVT_RESOLVED_SQL}"
    rows = _q(
        "SELECT COALESCE(NULLIF(TRIM(c.govt_department), ''), 'Department not recorded') AS name, "
        f"COUNT(*) AS filed, COALESCE(SUM(CASE WHEN {resolved} THEN 1 ELSE 0 END), 0) AS resolved, "
        f"AVG(CASE WHEN {resolved} THEN {_days_sql('COALESCE(c.govt_status_updated_at, c.resolved_at)', 'c.created_at')} END) AS avg_days "
        f"{_case_scope_sql()} AND {_FILED_SQL} GROUP BY 1",
        {"tid": tid, "start": window.start, "end": window.end},
    )
    cats = _q(
        "SELECT COALESCE(NULLIF(TRIM(c.govt_department), ''), 'Department not recorded') AS name, "
        f"{_CATEGORY_SQL} AS cat, COUNT(*) AS n {_case_scope_sql()} AND {_FILED_SQL} GROUP BY 1, 2",
        {"tid": tid, "start": window.start, "end": window.end},
    )
    main: dict[str, tuple[int, str]] = {}
    for r in cats:
        n = int(r["n"] or 0)
        if r["name"] not in main or n > main[r["name"]][0]:
            main[r["name"]] = (n, r["cat"])
    out = [{
        "name": r["name"], "filed": int(r["filed"] or 0), "resolved": int(r["resolved"] or 0),
        "avg_days": round(float(r["avg_days"])) if r["avg_days"] is not None else None,
        "main_issue": main.get(r["name"], (0, ""))[1],
    } for r in rows]
    out.sort(key=lambda d: (-d["filed"], d["name"]))
    return out[:MAX_REPORT_ROWS]


def _backlog(tid: int, now: datetime) -> dict:
    p = {"tid": tid, "now": now, "t7": now - timedelta(days=7), "t30": now - timedelta(days=30), "t90": now - timedelta(days=90)}
    row = _q(
        "SELECT COUNT(*) AS total, "
        "COALESCE(SUM(CASE WHEN c.created_at >= :t7 THEN 1 ELSE 0 END), 0) AS a, "
        "COALESCE(SUM(CASE WHEN c.created_at < :t7 AND c.created_at >= :t30 THEN 1 ELSE 0 END), 0) AS b, "
        "COALESCE(SUM(CASE WHEN c.created_at < :t30 AND c.created_at >= :t90 THEN 1 ELSE 0 END), 0) AS c3, "
        "COALESCE(SUM(CASE WHEN c.created_at < :t90 THEN 1 ELSE 0 END), 0) AS d "
        f"{_base_where()} AND c.created_at < :now AND {_open_sql()}", p,
    )[0]
    stale = _q(
        f"SELECT {_CATEGORY_SQL} AS name, COUNT(*) AS n {_base_where()} AND c.created_at < :t30 AND {_open_sql()} "
        "GROUP BY 1", p,
    )
    return {
        "total": int(row["total"] or 0),
        "buckets": [["0–7 days", int(row["a"] or 0)], ["8–30 days", int(row["b"] or 0)],
                    ["31–90 days", int(row["c3"] or 0)], ["Over 90 days", int(row["d"] or 0)]],
        "over_30_by_issue": {r["name"]: int(r["n"] or 0) for r in stale},
    }


def _critical(tid: int, window: ReportWindow, now: datetime) -> dict:
    p = {"tid": tid, "start": window.start, "end": window.end, "now": now}
    crit = "COALESCE(c.is_critical, FALSE) = TRUE"
    row = _q(
        "SELECT COUNT(*) AS open_n, MIN(c.created_at) AS oldest "
        f"{_base_where()} AND {crit} AND c.created_at < :now AND {_open_sql()}", p,
    )[0]
    received = _q(f"SELECT COUNT(*) AS n {_case_scope_sql()} AND {crit}", p)[0]["n"]
    closed = _q(
        f"SELECT COUNT(*) AS n {_base_where()} AND {crit} AND c.resolved_at >= :start AND c.resolved_at < :end", p,
    )[0]["n"]
    oldest = _as_dt(row["oldest"])
    return {
        "open": int(row["open_n"] or 0), "received": int(received or 0), "closed": int(closed or 0),
        "oldest_days": max(int((now - oldest).total_seconds() // 86400), 0) if oldest else None,
    }


def _quality(tid: int, window: ReportWindow, received: int) -> dict:
    if not received:
        return {"mapped": None, "categorised": None, "office_resolved": None}
    row = _q(
        f"SELECT COALESCE(SUM(CASE WHEN {_LOCALITY_SQL} IS NOT NULL THEN 1 ELSE 0 END), 0) AS mapped, "
        "COALESCE(SUM(CASE WHEN NULLIF(TRIM(COALESCE(c.problem_domain, '')), '') IS NOT NULL THEN 1 ELSE 0 END), 0) AS cat, "
        "COALESCE(SUM(CASE WHEN LOWER(COALESCE(c.status, '')) IN ("
        + ", ".join(f"'{s}'" for s in OFFICE_CLOSED_STATUSES) + ") THEN 1 ELSE 0 END), 0) AS done "
        f"{_case_scope_sql()}", {"tid": tid, "start": window.start, "end": window.end},
    )[0]
    pct = lambda v: round(int(v or 0) / received * 100)  # noqa: E731
    return {"mapped": pct(row["mapped"]), "categorised": pct(row["cat"]), "office_resolved": pct(row["done"])}


def _gazetteer_localities(tenant) -> list[str]:
    from sansadx_backend.db import derive_seat_type

    if tenant is None or not (tenant.constituency or "").strip():
        return []
    rows = _q(
        "SELECT DISTINCT canonical_name AS name FROM geo_places WHERE seat_type = :st AND seat_name = :sn "
        "AND status = 'verified' AND place_type IN ('locality', 'ward', 'sub_locality')",
        {"st": derive_seat_type(tenant) or "mp", "sn": tenant.constituency.strip()},
    )
    return sorted({r["name"] for r in rows if r["name"]})


def _presence(tid: int, window: ReportWindow, prev: tuple | None, tenant) -> dict:
    def contacts(start, end):
        rows = _q(
            f"SELECT {_LOCALITY_SQL} AS loc, COUNT(DISTINCT c.user_phone) AS people, COUNT(*) AS n "
            f"{_case_scope_sql()} GROUP BY 1", {"tid": tid, "start": start, "end": end},
        )
        return {r["loc"]: (int(r["people"] or 0), int(r["n"] or 0)) for r in rows if r["loc"]}

    now_c = contacts(window.start, window.end)
    prev_c = contacts(*prev) if prev else None
    known = _gazetteer_localities(tenant)
    names = sorted(set(known) | set(now_c))

    def status(people: int) -> str:
        if people >= PRESENCE_STRONG:
            return "strong"
        if people >= PRESENCE_GROWING:
            return "growing"
        return "thin" if people else "none"

    rows = [{"name": n, "people": now_c.get(n, (0, 0))[0], "complaints": now_c.get(n, (0, 0))[1],
             "status": status(now_c.get(n, (0, 0))[0])} for n in names]
    rows.sort(key=lambda r: (-r["people"], -r["complaints"], r["name"]))
    return {
        "rows": rows,
        "with_presence": sum(1 for r in rows if r["people"]),
        "with_presence_prev": (sum(1 for v in prev_c.values() if v[0]) if prev_c is not None else None),
        "total": len(names),
        "gazetteer_known": bool(known),
        "none": [r["name"] for r in rows if not r["people"]],
    }


def _segments(tid: int, window: ReportWindow, prev: tuple | None) -> list[dict]:
    seg = "COALESCE(NULLIF(TRIM(c.assembly), ''), '')"
    p = {"tid": tid, "start": window.start, "end": window.end,
         "pstart": prev[0] if prev else window.start, "pend": prev[1] if prev else window.start}
    rows = _q(
        f"SELECT {seg} AS seg, COUNT(*) AS received, "
        f"COALESCE(SUM(CASE WHEN {_FILED_SQL} THEN 1 ELSE 0 END), 0) AS filed, "
        f"COALESCE(SUM(CASE WHEN {_FILED_SQL} AND {_GOVT_RESOLVED_SQL} THEN 1 ELSE 0 END), 0) AS gov, "
        f"COALESCE(SUM(CASE WHEN {_OTHER_ACTION_SQL} THEN 1 ELSE 0 END), 0) AS other {_case_scope_sql()} GROUP BY 1", p,
    )
    prev_rows = {r["seg"]: int(r["n"] or 0) for r in _q(
        f"SELECT {seg} AS seg, COUNT(*) AS n {_case_scope_sql('pstart', 'pend')} GROUP BY 1", p)} if prev else {}
    tops: dict[str, tuple[int, str]] = {}
    for r in _q(f"SELECT {seg} AS seg, {_CATEGORY_SQL} AS cat, COUNT(*) AS n {_case_scope_sql()} GROUP BY 1, 2", p):
        n = int(r["n"] or 0)
        if r["seg"] not in tops or n > tops[r["seg"]][0]:
            tops[r["seg"]] = (n, r["cat"])
    out = []
    for r in rows:
        if not r["seg"]:
            continue
        rec, fil, oth = int(r["received"] or 0), int(r["filed"] or 0), int(r["other"] or 0)
        out.append({"name": r["seg"], "received": rec, "previous": prev_rows.get(r["seg"], 0) if prev else None,
                    "top_issue": tops.get(r["seg"], (0, ""))[1], "filed": fil, "resolved_by_government": int(r["gov"] or 0),
                    "pending": max(rec - fil - oth, 0), "acted_share": round((fil + oth) / rec * 100) if rec else 0})
    out.sort(key=lambda s: (-s["received"], s["name"]))
    total = sum(s["received"] for s in out)
    # Weak flank: lowest share acted on among segments carrying at least a tenth of the load.
    eligible = [s for s in out if total and s["received"] >= max(10, total * 0.1)]
    if eligible:
        weakest = min(eligible, key=lambda s: (s["acted_share"], -s["received"]))
        weakest["weak_flank"] = True
    return out


def build_report_data(tenant_id: int, window: ReportWindow, edition: str, tenant=None, now: datetime | None = None) -> dict:
    now = now or datetime.utcnow()
    resolved_window = window.bounded(first_case_at([tenant_id]) if window.start is None else None)
    b = client_briefing(tenant_id, resolved_window, now)
    if window.start is None:  # keep the all-time label and no comparison period
        b["window"] = window.bounded(resolved_window.start).describe()
    prev = None
    if b["compare"]:
        span = resolved_window.end - resolved_window.start
        prev = (resolved_window.start - span, resolved_window.start)

    data = {
        "edition": edition, "briefing": b,
        "weekly": _weekly_trend(tenant_id, resolved_window.end),
        "departments": _departments(tenant_id, resolved_window),
        "backlog": _backlog(tenant_id, now),
        "critical": _critical(tenant_id, resolved_window, now),
        "reach": _reach(tenant_id, resolved_window.start, resolved_window.end),
        "reach_prev": _reach(tenant_id, *prev) if prev else None,
        "languages": _languages(tenant_id, resolved_window),
        "quality": _quality(tenant_id, resolved_window, b["momentum"]["received"]["now"]),
    }
    if edition == "aspirant":
        data["presence"] = _presence(tenant_id, resolved_window, prev, tenant)
    if edition == "mp":
        data["segments"] = _segments(tenant_id, resolved_window, prev)
    return data


# ─────────────────────────────────────────
# WORDS (deterministic templates over counts)
# ─────────────────────────────────────────
def _change(now: int, prev: int | None) -> float | None:
    if prev is None or not prev:
        return None
    return (now - prev) / prev


def _join(names: list[str]) -> str:
    names = [n for n in names if n]
    if len(names) <= 1:
        return names[0] if names else ""
    return ", ".join(names[:-1]) + " and " + names[-1]


def _lower(s: str) -> str:
    return s[:1].lower() + s[1:] if s else s


def _rise_words(issue: dict) -> str:
    c, p = issue["count"], issue["previous"]
    if not p:
        return f"rose from none to {c}"
    r = c / p
    if r >= 2.5:
        return f"rose {round(r)}-fold"
    if r >= 1.9:
        return "doubled"
    return f"rose {round((r - 1) * 100)}%"


def _riser(issues: list[dict], exclude=None, min_count: int = 3) -> dict | None:
    cands = [i for i in issues if i is not exclude and i.get("previous") is not None and i["count"] >= max(3, min_count)
             and i["count"] > i["previous"] and (i["previous"] == 0 or (i["count"] - i["previous"]) / i["previous"] >= 0.25)]
    cands.sort(key=lambda i: (-((i["count"] - i["previous"]) / i["previous"] if i["previous"] else i["count"]), -i["count"]))
    return cands[0] if cands else None


def _locs(issue: dict | None, n: int = 2) -> list[str]:
    return [l["name"] for l in (issue or {}).get("top_localities", [])[:n]]


def _pct_words(now: int, prev: int | None) -> str:
    c = _change(now, prev)
    if c is None or abs(c) < 0.005:
        return ""
    return f"{'up' if c > 0 else 'down'} {round(abs(c) * 100)}%"


def office_story(d: dict) -> dict:
    """Verdict, takeaways and recommended actions for a sitting MLA / MP."""
    b = d["briefing"]
    m, f = b["momentum"], b["funnel"]
    issues = [i for i in b["issues"] if i["count"]]
    rec = m["received"]["now"]
    if not rec or not issues:
        return {"verdict": ("No grievances were received in this period.", ""), "takeaways": [], "actions": []}
    top = issues[0]
    riser = _riser(issues, top, min_count=round(rec * 0.05))
    rc = _change(rec, m["received"]["previous"])
    fc = _change(m["filed"]["now"], m["filed"]["previous"])
    lead = (f"Complaints {'rose' if rc > 0 else 'fell'} {round(abs(rc) * 100)}%, led by {_lower(top['name'])}"
            if rc is not None and abs(rc) >= 0.005 else f"{top['name']} led {rec} complaints")
    segs = d.get("segments") or []
    flank = next((s for s in segs if s.get("weak_flank")), None)
    if flank:
        lead += f" — {flank['name']} is the weakest segment"
    elif riser:
        where = _locs(riser)
        lead += f" and {_lower(riser['name'])} complaints {_rise_words(riser)}{' in ' + _join(where) if where else ''}"
    emph = ""
    if fc is not None and fc <= -0.2:
        emph = f"while filings to government fell by {round(abs(fc) * 100)}%."
    elif m["pending"]["now"] / rec > 0.5:
        emph = f"while {m['pending']['now']} of {rec} grievances still have no action."
    elif m["resolved_by_government"]["now"]:
        emph = f"and government resolved {m['resolved_by_government']['now']}."
    lead = lead + (" —" if emph else ".")

    take = []
    share = round(top["count"] / rec * 100)
    locs = _locs(top)
    up = _pct_words(top["count"], top["previous"])
    take.append(("crit", f"{top['name']} is {share}% of all complaints",
                 f"{', ' + up if up else ''}{'; most from ' + _join(locs) if locs else ''}."))
    if flank:
        take.append(("crit", f"{flank['name']} is the weak flank:",
                     f" {flank['received']} complaints and only {flank['acted_share']}% acted on."))
    if riser:
        take.append(("crit", f"{riser['name']} complaints {_rise_words(riser)}",
                      f" ({riser['previous']} → {riser['count']}){', concentrated in ' + _join(_locs(riser)) if _locs(riser) else ''}."))
    prev_f = m["filed"]["previous"]
    take.append(("warn", f"{m['filed']['now']} grievances were filed with government",
                 (f", against {prev_f} the period before" if prev_f is not None else "")
                 + (f"; {f['ready_to_file']} prepared filings are waiting" if f["ready_to_file"] else "") + "."))
    if m["resolved_by_government"]["now"]:
        w = b["wins"][0] if b["wins"] else None
        take.append(("go", f"{m['resolved_by_government']['now']} grievances were resolved by government",
                     f", led by {_lower(w['name'])}{' in ' + _join(w['localities']) if w and w['localities'] else ''}." if w else "."))

    acts = []
    if flank:
        acts.append(("Strengthen " + flank["name"] + " first.",
                     f"{flank['received']} complaints, {flank['acted_share']}% acted on and {flank['pending']} pending — the weakest segment carrying real load.",
                     "Office"))
    if f["ready_to_file"]:
        acts.append(("Clear the filing backlog this week.",
                     f"{f['ready_to_file']} grievances are prepared but not submitted"
                     + (f", the oldest for {f['oldest_ready_days']} days" if f["oldest_ready_days"] else "")
                     + ". Nothing reaches government until it is filed.", "Office"))
    elif m["pending"]["now"] / rec > 0.5:
        acts.append(("Act on pending grievances.",
                     f"{m['pending']['now']} of {rec} grievances received this period have no action yet.", "Office"))
    if riser:
        where = _locs(riser)
        acts.append((f"Be seen on {_lower(riser['name'])}{' in ' + _join(where) if where else ''}.",
                     f"The fastest-rising issue ({riser['previous']} → {riser['count']}). Visit, and meet the department responsible, before it becomes the story of the month.",
                     "Representative"))
    slow = [x for x in d["departments"] if x["filed"] >= 3 and x["name"] != "Department not recorded"]
    if slow:
        worst = min(slow, key=lambda x: (x["resolved"] / x["filed"], -(x["avg_days"] or 0)))
        if worst["resolved"] / worst["filed"] < 0.75:
            acts.append((f"Escalate with {worst['name']}.",
                         f"{worst['filed']} grievances filed, {worst['resolved']} resolved"
                         + (f", {worst['avg_days']} days average" if worst["avg_days"] is not None else "")
                         + " — the slowest department this period.", "Representative"))
    if b["wins"]:
        w = b["wins"][0]
        acts.append((f"Publicise the {_lower(w['name'])} wins.",
                      f"{w['count']} resolved by government{' in ' + _join(w['localities']) if w['localities'] else ''} — proof of delivery, by locality.",
                      "Communications"))
    elif d["backlog"]["buckets"][3][1]:
        acts.append(("Close out the oldest grievances.",
                     f"{d['backlog']['buckets'][3][1]} grievances have been open for over 90 days — the ones citizens remember.", "Office"))
    return {"verdict": (lead, emph), "takeaways": take[:4], "actions": acts[:4]}


def aspirant_story(d: dict) -> dict:
    b = d["briefing"]
    issues = [i for i in b["issues"] if i["count"]]
    pres, reach = d["presence"], d["reach"]
    stale = d["backlog"]["over_30_by_issue"]
    if not issues:
        return {"verdict": ("No issues were raised with you in this period.", ""), "takeaways": [], "actions": [], "planks": set()}
    received = b["momentum"]["received"]["now"]
    planks = {i["name"] for i in issues if i.get("previous") and i["count"] >= i["previous"] * 1.1
              and stale.get(i["name"], 0) >= 5}
    plank = max(issues, key=lambda i: (stale.get(i["name"], 0), i["count"]))
    riser = _riser(issues, None, min_count=round(received * 0.05))
    lead = f"{plank['name']} is the constituency's biggest failure"
    if stale.get(plank["name"]):
        lead += f" — {stale[plank['name']]} complaints unresolved for over a month —"
    emph = (f"and you now reach {pres['with_presence']} of {pres['total']} localities." if pres["gazetteer_known"]
            else f"and {reach['people']} people came to you.")

    take = []
    up = _pct_words(plank["count"], plank["previous"])
    take.append(("crit", f"{plank['name']} is the issue to own:",
                 f" {plank['count']} complaints{', ' + up if up else ''}, and the largest pile left unresolved."))
    if riser and riser is not plank:
        take.append(("crit", f"{riser['name']} complaints {_rise_words(riser)}"
                     + (f" in {_join(_locs(riser))}" if _locs(riser) else ""), " — an issue nobody owns yet."))
    rp = d["reach_prev"]
    gw = _pct_words(reach["people"], rp["people"] if rp else None)
    take.append(("info", f"{reach['people']} people came to you",
                 f"{' (' + gw + ')' if gw else ''}, {reach['first_time']} of them for the first time."))
    if pres["gazetteer_known"] and pres["none"]:
        take.append(("warn", f"{len(pres['none'])} localities have no contact with you yet",
                     f", including {_join(pres['none'][:2])}."))

    acts = [(f"Own the {_lower(plank['name'])} issue publicly.",
             f"{stale.get(plank['name'], 0)} complaints are over a month old with no fix. A public hearing and a written memorandum to the department, with the numbers.",
             "Aspirant")]
    if riser and riser is not plank:
        where = _locs(riser, 1)
        acts.append((f"Hold a meeting on {_lower(riser['name'])}{' in ' + where[0] if where else ''}.",
                     f"Complaints {_rise_words(riser)} ({riser['previous']} → {riser['count']}). Show up where the anger is building.",
                     "Aspirant"))
    if pres["gazetteer_known"] and pres["none"]:
        acts.append((f"Build presence in {_join(pres['none'][:3])}.",
                     f"{len(pres['none'])} of {pres['total']} localities have no contact with you yet. A help desk or a door-to-door round is the cheapest way in.",
                     "Field team"))
    gov = b["momentum"]["resolved_by_government"]["now"]
    if gov:
        acts.append((f"Tell the story of the {gov} outcome{'s' if gov != 1 else ''}.",
                     "Each came after you took the issue up. Credit the residents and the persistence — never say you resolved it.",
                     "Communications"))
    return {"verdict": (lead, emph), "takeaways": take[:4], "actions": acts[:4], "planks": planks}


# ─────────────────────────────────────────
# HTML
# ─────────────────────────────────────────
def _fg_for(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return "#ffffff"
    lum = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
    L = 0.2126 * lum(r) + 0.7152 * lum(g) + 0.0722 * lum(b)
    return "#17181C" if L > 0.45 else "#ffffff"


def _heat(v: int, mx: int) -> str:
    t = v / mx if mx else 0
    a, b = (247, 240, 234), (158, 50, 24)
    return "rgb(" + ",".join(str(round(x + (y - x) * t * 0.92)) for x, y in zip(a, b)) + ")"


def _chg_html(now: int, prev: int | None, good: str) -> str:
    if prev is None:
        return ""
    if now == prev:
        return '<span class="flat">no change</span>'
    if not prev:
        return '<span class="flat">new</span>'
    c = (now - prev) / prev
    up = c > 0
    cls = "good" if up == (good == "up") else "bad"
    return f'<span class="{cls}">{"↑" if up else "↓"} {round(abs(c) * 100)}%</span>'


_COLORS = ["#23496B", "#6F8FB0", "#B5482A", "#C9CDD4"]


def _line_chart(series: list[dict], labels: list[str], aria: str) -> str:
    esc = html.escape
    if not series:
        return '<p class="sub">Not enough data for a trend yet.</p>'
    W, H, L, R, T, B = 330, 150, 26, 8, 8, 20
    mx = max([v for s in series for v in s["values"]] + [1])
    step = max(1, math.ceil(mx / 4))
    mx = step * 4
    n = len(labels)
    x = lambda i: L + i * (W - L - R) / max(n - 1, 1)  # noqa: E731
    y = lambda v: H - B - (v / mx) * (H - T - B)  # noqa: E731
    g = []
    for t in range(0, mx + 1, step):
        g.append(f'<line x1="{L}" x2="{W - R}" y1="{y(t):.1f}" y2="{y(t):.1f}" stroke="#ECEBE6"/>'
                 f'<text x="{L - 5}" y="{y(t) + 3:.1f}" font-size="9" fill="#8A8E96" text-anchor="end">{t}</text>')
    for i, lab in enumerate(labels):
        if i % 2 == 0 or i == n - 1:
            g.append(f'<text x="{x(i):.1f}" y="{H - 5}" font-size="8.5" fill="#8A8E96" text-anchor="middle">{esc(lab)}</text>')
    for k, s in enumerate(series):
        c = _COLORS[k % len(_COLORS)] if s["name"] != "Other" else "#C9CDD4"
        path = "".join(("L" if i else "M") + f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(s["values"]))
        g.append(f'<path d="{path}" fill="none" stroke="{c}" stroke-width="2"/>')
    legend = "".join(
        f'<span><i style="background:{(_COLORS[k % 4] if s["name"] != "Other" else "#C9CDD4")}"></i>{esc(s["name"])}</span>'
        for k, s in enumerate(series))
    return f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="{esc(aria)}">{"".join(g)}</svg><div class="legend">{legend}</div>'


_CSS = """
*{box-sizing:border-box}
html,body{margin:0;background:#E9E8E3;color:#17181C;font:13px/1.45 -apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;-webkit-font-smoothing:antialiased}
.num{font-variant-numeric:tabular-nums}
.pages{padding:28px 16px 60px;display:flex;flex-direction:column;align-items:center;gap:24px}
.page{width:210mm;min-height:297mm;background:#fff;box-shadow:0 1px 2px rgba(0,0,0,.08),0 8px 28px rgba(0,0,0,.08);padding:16mm 16mm 14mm;display:flex;flex-direction:column}
.ph{display:flex;justify-content:space-between;align-items:center;gap:12px;padding-bottom:9px;border-bottom:1px solid #E3E1DA;margin-bottom:18px;font-size:11px;color:#5F636C}
.ph .b{display:flex;gap:8px;align-items:center;color:#17181C;font-weight:600}
.logo{max-height:26px;max-width:140px}
.pf{margin-top:auto;padding-top:10px;border-top:1px solid #E3E1DA;display:flex;justify-content:space-between;gap:12px;font-size:10px;color:#8A8E96}
.eyebrow{font:500 10px ui-monospace,"SF Mono",Menlo,monospace;letter-spacing:.14em;text-transform:uppercase;color:#5F636C}
.serif,h1,h2,.verdict{font-family:Georgia,"Times New Roman",serif}
h1{font-weight:500;font-size:32px;line-height:1.05;letter-spacing:-.02em;margin:6px 0}
h2{font-weight:500;font-size:20px;line-height:1.15;margin:0 0 4px}
h3{font-size:13px;font-weight:600;margin:0 0 2px}
.sub{color:#5F636C;font-size:11.5px}
.sec{margin-top:16px}
.sh{display:flex;justify-content:space-between;align-items:flex-end;gap:10px;margin-bottom:10px}
.cover{background:var(--brand);color:var(--brand-fg);margin:-16mm -16mm 0;padding:12mm 16mm 9mm}
.cover .eyebrow{color:inherit;opacity:.8}
.cover .meta{display:flex;gap:16px;flex-wrap:wrap;font-size:12px;opacity:.88;margin-top:6px}
.cover .brandrow{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:9mm;font:600 15px Georgia,serif}
.cover .logo{max-height:32px;background:#fff;padding:3px;border-radius:3px}
.verdict{font-weight:500;font-size:21px;line-height:1.25;margin:14px 0 12px}
.verdict em{color:#9E3218}
.take{list-style:none;margin:0;padding:0;display:grid;gap:8px}
.take li{display:grid;grid-template-columns:14px 1fr;gap:8px;color:#3A3D45}
.take b{color:#17181C}
.dot{width:7px;height:7px;border-radius:50%;margin-top:6px}
.dot.crit{background:#9E3218}.dot.warn{background:#B98118}.dot.go{background:#1F6B4F}.dot.info{background:#23496B}
.score{display:grid;grid-template-columns:repeat(5,1fr);border:1px solid #E3E1DA;border-radius:6px;overflow:hidden}
.score>div{padding:11px 12px;border-left:1px solid #E3E1DA}
.score>div:first-child{border-left:0}
.score .l{font-size:11px;color:#5F636C;font-weight:500;min-height:28px}
.score .v{font-size:25px;font-weight:600;letter-spacing:-.025em;line-height:1.05;margin-top:2px}
.score .c{font-size:11px;margin-top:4px}
.good{color:#1F6B4F;font-weight:600}.bad{color:#9E3218;font-weight:600}.flat{color:#5F636C}
.actions{display:grid;gap:8px}
.act{display:grid;grid-template-columns:26px 1fr auto;gap:10px;align-items:start;border:1px solid #E3E1DA;border-radius:6px;padding:10px 12px}
.act .n{width:22px;height:22px;border-radius:50%;background:var(--brand);color:var(--brand-fg);display:grid;place-items:center;font-weight:600;font-size:11.5px}
.act b{display:block;font-size:13px}
.act .d{color:#5F636C;font-size:11.5px}
.own{font:500 9.5px ui-monospace,Menlo,monospace;letter-spacing:.06em;text-transform:uppercase;padding:2px 6px;border-radius:2px;background:#F3F2EE;color:#3A3D45;white-space:nowrap}
table.t{width:100%;border-collapse:collapse;font-size:12px}
table.t th{text-align:left;color:#5F636C;font-weight:500;font-size:10.5px;padding:6px 8px;border-bottom:1px solid #CFCCC2;white-space:nowrap}
table.t td{padding:7px 8px;border-bottom:1px solid #E3E1DA;vertical-align:middle}
table.t .r{text-align:right}
table.t tr.flank td{background:#FBF1EC}
.share{display:inline-block;height:7px;background:#23496B;border-radius:1px;vertical-align:middle}
.tagx{font:500 9px ui-monospace,Menlo,monospace;letter-spacing:.06em;text-transform:uppercase;margin-left:6px;white-space:nowrap}
.tagx.spike{color:#9E3218}
.tagx.plank{color:#fff;background:#9E3218;padding:2px 5px;border-radius:2px}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.grid32{display:grid;grid-template-columns:1.25fr 1fr;gap:16px}
.box{border:1px solid #E3E1DA;border-radius:6px;padding:12px 14px}
.heat{display:grid;gap:2px;font-size:11px}
.heat .h{color:#5F636C;font-size:10px;font-weight:500;text-align:center;padding:2px;align-self:end;line-height:1.2;overflow-wrap:anywhere}
.heat .rh{display:flex;align-items:center;color:#3A3D45;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.heat .c{height:24px;border-radius:2px;display:grid;place-items:center;font-weight:600}
.heat .tot{display:grid;place-items:center end;font-weight:600;padding-right:2px}
.fr{display:grid;grid-template-columns:150px 1fr 40px;gap:10px;align-items:center;font-size:12px;margin-bottom:6px}
.fr .bar{height:18px;background:#F3F2EE;border-radius:2px;overflow:hidden}
.fr .bar b{display:block;height:100%;background:#23496B}
.fr.stuck .bar b{background:#B98118}
.fr .v{text-align:right;font-weight:600}
.callout{border:1px solid #E7CF9E;background:#FBF4E4;color:#4E3A10;border-radius:6px;padding:9px 12px;font-size:11.5px;margin-top:8px}
.callout.go{border-color:#B9D6C6;background:#EEF6F1;color:#1C4F3B}
.age{display:flex;height:22px;border-radius:3px;overflow:hidden;margin:8px 0 6px;background:#F3F2EE}
.age span{display:grid;place-items:center;color:#fff;font-size:10.5px;font-weight:600;min-width:0}
.legend{display:flex;gap:12px;flex-wrap:wrap;font-size:10.5px;color:#5F636C}
.legend i{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:4px;vertical-align:-1px}
.wins{list-style:none;margin:0;padding:0}
.wins li{display:grid;grid-template-columns:34px 1fr;gap:10px;padding:8px 0;border-top:1px solid #E3E1DA}
.wins li:first-child{border-top:0}
.wins .n{font-size:19px;font-weight:600;color:#1F6B4F;text-align:right}
.kv{display:grid;grid-template-columns:1fr auto;font-size:12px}
.kv div{padding:6px 0;border-top:1px solid #E3E1DA}
.kv div:nth-child(-n+2){border-top:0}
.kv .v{text-align:right;font-weight:600}
.meter{height:8px;background:#F3F2EE;border-radius:4px;overflow:hidden;margin:6px 0 4px}
.meter b{display:block;height:100%;border-radius:4px}
.st{font:500 9.5px ui-monospace,Menlo,monospace;letter-spacing:.05em;text-transform:uppercase;padding:2px 6px;border-radius:2px;white-space:nowrap}
.st.strong{background:#DDEBE3;color:#1F6B4F}.st.growing{background:#E2E8F1;color:#23496B}.st.thin{background:#F5E9CC;color:#7A5410}.st.none{background:#F7E3DC;color:#9E3218}
.warnnote{border-left:3px solid #B98118;background:#FBF4E4;padding:8px 12px;font-size:11.5px;color:#4E3A10;border-radius:0 6px 6px 0}
.defs{display:grid;grid-template-columns:150px 1fr;gap:6px 14px;font-size:11.5px;margin:6px 0 0}
.defs dt{font-weight:600}.defs dd{margin:0;color:#3A3D45}
.empty{color:#5F636C;font-size:12px;padding:8px 0}
@media (max-width:860px){
  .pages{padding:12px 0 40px;gap:12px}
  .page{width:100%;min-height:0;padding:20px 16px}
  .cover{margin:-20px -16px 0;padding:22px 16px 18px}
  .score{grid-template-columns:repeat(2,1fr)}.score>div{border-top:1px solid #E3E1DA}.score>div:nth-child(odd){border-left:0}.score>div:last-child{grid-column:1/-1}
  .grid2,.grid32{grid-template-columns:1fr}
  .fr{grid-template-columns:110px 1fr 34px}
  .hide-sm{display:none}
  table.t{font-size:11.5px;display:block;overflow-x:auto}
  .heat{overflow-x:auto}
}
@media print{
  @page{size:A4;margin:0}
  html,body{background:#fff}
  .pages{padding:0;gap:0}
  .page{box-shadow:none;break-after:page;width:210mm;min-height:0;height:296.8mm;overflow:hidden}
  .page:last-child{break-after:auto}
  *{-webkit-print-color-adjust:exact;print-color-adjust:exact}
}
"""


def render_report(partner: dict, seat: dict, data: dict, generated_at: datetime | None = None) -> str:
    esc = html.escape
    generated_at = generated_at or datetime.utcnow()
    edition = data["edition"]
    b = data["briefing"]
    m, fun = b["momentum"], b["funnel"]
    color = clean_color(partner.get("brand_color"))
    fg = _fg_for(color)
    brand = esc(partner.get("brand_name") or "")
    logo = partner.get("brand_logo_url")
    logo_html = f'<img src="{esc(logo, quote=True)}" alt="" class="logo">' if logo else ""
    client = esc(seat.get("client_label") or "")
    house = "Lok Sabha" if (seat.get("seat_type") or "mp") == "mp" else "Vidhan Sabha"
    seat_name = esc(f"{seat.get('constituency') or ''} {house}".strip())
    role = {"aspirant": "Aspirant", "mla": "MLA", "mp": "MP"}[edition]
    kind = "Monthly ground report" if edition == "aspirant" else "Constituency report"

    win = b["window"]
    if win["kind"] == "all":
        period = f"All time (since {win['from']})" if win.get("from") else "All time"
    elif win["kind"] == "days":
        period = f"Last {win['days']} days ({win['from']} to {win['to']})"
    else:
        period = f"{win['from']} to {win['to']}"
    compare = f"Compared with {b['compare']['from']} to {b['compare']['to']}" if b["compare"] else "No comparison period"
    powered = "Intelligence by Compass Needle" if partner.get("show_powered_by") else ""
    total_pages = 4

    def head(title: str) -> str:
        return (f'<div class="ph"><span class="b">{logo_html}{brand}</span>'
                f'<span>{seat_name} · {esc(title)}</span></div>')

    def foot(n: int) -> str:
        extra = f" {esc(powered)}." if powered else ""
        return (f'<div class="pf"><span>Prepared by {brand} for {client}. Aggregate figures only; no citizen details are '
                f'included.{extra}</span><span>{n} / {total_pages}</span></div>')

    def take_html(items) -> str:
        return '<ul class="take">' + "".join(
            f'<li><span class="dot {t}"></span><span><b>{esc(bold)}</b>{esc(rest)}</span></li>' for t, bold, rest in items) + "</ul>"

    def kv(rows) -> str:
        return '<div class="kv">' + "".join(f'<div>{esc(str(k))}</div><div class="v num">{esc(str(v))}</div>' for k, v in rows) + "</div>"

    def score(cards, sub) -> str:
        parts = []
        for l, now, prev, good, crit in cards:
            style = ' style="color:#9E3218"' if crit and now else ""
            vs = f' <span class="flat">vs {prev}</span>' if prev is not None else ""
            parts.append(f'<div><div class="l">{esc(l)}</div><div class="v num"{style}>{now}</div>'
                         f'<div class="c">{_chg_html(now, prev, good)}{vs}</div></div>')
        cells = "".join(parts)
        return (f'<div class="sec"><div class="sh"><div><h3>Scorecard</h3><div class="sub">{esc(sub)}</div></div></div>'
                f'<div class="score">{cells}</div></div>')

    def actions_html(acts) -> str:
        if not acts:
            return ""
        rows = "".join(
            f'<div class="act"><span class="n">{i}</span><span><b>{esc(t)}</b><span class="d">{esc(d)}</span></span>'
            f'<span class="own">{esc(o)}</span></div>' for i, (t, d, o) in enumerate(acts, 1))
        return ('<div class="sec"><div class="sh"><div><h3>Recommended actions for the next 30 days</h3>'
                '<div class="sub">Where attention will change the numbers most</div></div></div>'
                f'<div class="actions">{rows}</div></div>')

    def issues_table(unresolved: dict | None = None, planks: set | None = None, max_issues: int = 8) -> str:
        issues = [i for i in b["issues"] if i["count"] or i["previous"]][:max_issues]
        if not issues:
            return '<p class="empty">No complaints in this period.</p>'
        total = sum(i["count"] for i in issues) or 1
        has_prev = b["compare"] is not None
        head_cells = ('<th>Issue</th><th class="r">Now</th>' + ('<th class="r">Before</th><th class="r">Change</th>' if has_prev else "")
                      + ('<th class="r">Unresolved &gt;30 days</th>' if unresolved is not None else "<th>Share</th>")
                      + '<th class="hide-sm">Most affected</th>')
        rows = []
        for i in issues:
            c = _change(i["count"], i["previous"])
            tag = ""
            if planks and i["name"] in planks:
                tag = '<span class="tagx plank">Campaign plank</span>'
            elif has_prev and i["count"] >= 3 and ((c is not None and c >= 0.5) or i["previous"] == 0):
                tag = '<span class="tagx spike">Spike</span>'
            cells = [f'<td><b>{esc(i["name"])}</b>{tag}</td>', f'<td class="r num"><b>{i["count"]}</b></td>']
            if has_prev:
                cells += [f'<td class="r num flat">{i["previous"]}</td>', f'<td class="r">{_chg_html(i["count"], i["previous"], "down")}</td>']
            if unresolved is not None:
                cells.append(f'<td class="r num"><b>{unresolved.get(i["name"], 0)}</b></td>')
            else:
                cells.append(f'<td><span class="share" style="width:{round(i["count"] / total * 90)}px"></span> '
                             f'<span class="num flat">{round(i["count"] / total * 100)}%</span></td>')
            cells.append(f'<td class="hide-sm">{esc(_join(_locs(i)))}</td>')
            rows.append("<tr>" + "".join(cells) + "</tr>")
        return f'<table class="t"><thead><tr>{head_cells}</tr></thead><tbody>{"".join(rows)}</tbody></table>'

    def trend_box(reading: list) -> str:
        w = data["weekly"]
        return (f'<div class="grid32 sec"><div class="box"><h3>Weekly trend, last {WEEKS} weeks</h3>'
                f'{_line_chart(w["series"], w["labels"], "Weekly complaints by issue")}</div>'
                f'<div class="box"><h3>What to read from this</h3><div style="margin-top:8px;font-size:12px">{take_html(reading)}</div></div></div>')

    def trend_reading() -> list:
        out = []
        for s in data["weekly"]["series"]:
            if s["name"] == "Other":
                continue
            v = s["values"]
            first, last = sum(v[:2]) / 2, sum(v[-2:]) / 2
            if first and last >= first * 2:
                out.append(("crit", f"{s['name']} more than doubled", f" over {WEEKS} weeks."))
            elif last > first * 1.25:
                out.append(("crit", f"{s['name']} is climbing", " — a sustained rise, not a one-off spike."))
            elif first and last < first * 0.8:
                out.append(("go", f"{s['name']} is easing", f" over the last {WEEKS} weeks."))
            else:
                out.append(("info", f"{s['name']} is steady", " — a chronic issue, not a crisis."))
        return out[:3] or [("info", "Not enough history yet", " to read a trend.")]

    def heat_grid() -> str:
        hot = b["hotspots"]
        rows = hot["localities"][:MAX_REPORT_ROWS]
        if not rows or not hot["columns"]:
            return '<p class="empty">No complaints with a mapped locality in this period.</p>'
        mx = max([v for r in rows for v in r["counts"]] + [1])
        cols = hot["columns"]
        cells = ['<span class="h" style="text-align:left">Locality</span>'] + [f'<span class="h">{esc(c)}</span>' for c in cols] + ['<span class="h" style="text-align:right">Total</span>']
        for r in rows:
            cells.append(f'<span class="rh">{esc(r["name"])}</span>')
            for v in r["counts"]:
                fgc = "#fff" if v / mx > 0.55 else "#17181C"
                cells.append(f'<span class="c num" style="background:{_heat(v, mx)};color:{fgc}">{_sup(v)}</span>')
            cells.append(f'<span class="tot num">{_sup(r["total"])}</span>')
        return (f'<div class="heat" style="grid-template-columns:120px repeat({len(cols)},1fr) 50px">{"".join(cells)}</div>')

    def funnel_html(stages, stuck_idx) -> str:
        mx = max(stages[0][1], 1)
        return "".join(
            f'<div class="fr{" stuck" if i == stuck_idx else ""}"><span>{esc(l)}</span><span class="bar"><b style="width:{v / mx * 100:.0f}%"></b></span>'
            f'<span class="v num">{v}</span></div>' for i, (l, v) in enumerate(stages))

    def dept_table(cols=("Filed", "Resolved")) -> str:
        rows = data["departments"]
        if not rows:
            return '<p class="empty">No grievances were filed with government in this period.</p>'
        body = "".join(
            f'<tr><td><b>{esc(d["name"])}</b></td><td class="hide-sm">{esc(d["main_issue"])}</td><td class="r num">{d["filed"]}</td>'
            f'<td class="r num">{d["resolved"]}</td><td class="r num {"bad" if d["resolved"] / d["filed"] < 0.5 else "good"}">{round(d["resolved"] / d["filed"] * 100)}%</td>'
            f'<td class="r num {"bad" if (d["avg_days"] or 0) > 14 else ""}">{"—" if d["avg_days"] is None else d["avg_days"]}</td></tr>'
            for d in rows)
        return (f'<table class="t"><thead><tr><th>Department</th><th class="hide-sm">Main issue</th><th class="r">{cols[0]}</th>'
                f'<th class="r">{cols[1]}</th><th class="r">Rate</th><th class="r">Avg. days</th></tr></thead><tbody>{body}</tbody></table>')

    def dept_callout() -> str:
        rows = [d for d in data["departments"] if d["filed"] >= 3 and d["name"] != "Department not recorded"]
        if not rows:
            return ""
        worst = min(rows, key=lambda x: (x["resolved"] / x["filed"], -(x["avg_days"] or 0)))
        if worst["resolved"] / worst["filed"] >= 0.75:
            return '<div class="callout go"><b>Departments are responding.</b> Every department with three or more filings resolved most of them.</div>'
        return (f'<div class="callout"><b>{esc(worst["name"])} is the bottleneck.</b> {worst["filed"]} filed, {worst["resolved"]} resolved'
                + (f', {worst["avg_days"]} days average' if worst["avg_days"] is not None else "") + ".</div>")

    def backlog_box(title: str, note: str) -> str:
        bl = data["backlog"]
        colors = ["#A9B4C2", "#6F8FB0", "#B98118", "#9E3218"]
        old = bl["buckets"][2][1] + bl["buckets"][3][1]
        bar = "".join(f'<span style="flex:{v};background:{c}">{v if v else ""}</span>' for (l, v), c in zip(bl["buckets"], colors) if v)
        legend = "".join(f'<span><i style="background:{c}"></i>{esc(l)}</span>' for (l, v), c in zip(bl["buckets"], colors))
        return (f'<div class="box"><h3>{esc(title)}</h3><div class="sub">All grievances still open, received at any time</div>'
                f'<div style="font-size:24px;font-weight:600;margin-top:6px" class="num">{bl["total"]} <span class="sub" style="font-weight:500">open</span></div>'
                f'<div class="age">{bar}</div><div class="legend">{legend}</div>'
                f'<div class="sub" style="margin-top:8px"><b class="bad">{old} have waited over a month.</b> {esc(note)}</div></div>')

    def quality_box(label: str, value, color_: str, note: str) -> str:
        v = "—" if value is None else f"{value}%"
        w = 0 if value is None else value
        return (f'<div class="box"><div style="display:flex;justify-content:space-between;gap:8px"><b style="font-size:12px">{esc(label)}</b>'
                f'<b class="num">{v}</b></div><div class="meter"><b style="width:{w}%;background:{color_}"></b></div><div class="sub">{esc(note)}</div></div>')

    def langs_html() -> str:
        if not data["languages"]:
            return '<p class="empty">No language information recorded.</p>'
        return "".join(
            f'<div style="display:grid;grid-template-columns:70px 1fr 34px;gap:8px;align-items:center;font-size:12px;margin-top:5px">'
            f'<span>{esc(l["name"])}</span><span class="meter" style="margin:0"><b style="width:{l["share"]}%;background:#23496B"></b></span>'
            f'<span class="num" style="text-align:right">{l["share"]}%</span></div>' for l in data["languages"])

    privacy = ('<div class="box"><b style="font-size:12px">Privacy</b><div class="sub" style="margin-top:4px">Counts only. No names, '
               'contact numbers, complaint text or addresses are included. Locality counts under '
               f'{SMALL_COUNT} are shown as “&lt;{SMALL_COUNT}”.</div></div>')

    cover = (f'<div class="cover"><div class="brandrow"><span>{logo_html} {brand}</span><span class="eyebrow">{esc(kind)}</span></div>'
             f'<div class="eyebrow">Prepared for {client} · {role}</div><h1>{seat_name}</h1>'
             f'<div class="meta"><span>{esc(period)}</span><span>{esc(compare)}</span><span>Issued {generated_at:%d %b %Y}</span></div></div>')

    reach, rp = data["reach"], data["reach_prev"]
    q = data["quality"]

    if edition == "aspirant":
        story = aspirant_story(data)
        pres = data["presence"]
        lead, emph = story["verdict"]
        p1 = (f'<section class="page" aria-label="Summary">{cover}<div class="sec"><div class="eyebrow">The month in one line</div>'
              f'<p class="verdict">{esc(lead)} <em>{esc(emph)}</em></p>{take_html(story["takeaways"])}</div>'
              + score([
                  ("People reached", reach["people"], rp["people"] if rp else None, "up", False),
                  ("New contacts", reach["first_time"], rp["first_time"] if rp else None, "up", False),
                  ("Localities with presence", pres["with_presence"], pres["with_presence_prev"], "up", False),
                  ("Issues followed up", fun["action_taken"], (m["filed"]["previous"] + m["other_actions"]["previous"]) if m["filed"]["previous"] is not None else None, "up", False),
                  ("Outcomes after follow-up", m["resolved_by_government"]["now"], m["resolved_by_government"]["previous"], "up", False),
              ], "Your presence and pressure this period, against the previous period")
              + actions_html(story["actions"]) + foot(1) + "</section>")

        stmap = {"strong": "Strong", "growing": "Growing", "thin": "Thin", "none": "No presence"}
        cap = 8
        prow = pres["rows"][:cap]
        if pres["gazetteer_known"] and pres["none"]:
            # Always show some of the localities with no contact: they are the point of the table.
            shown = [r for r in prow if r["people"]][:cap - min(3, len(pres["none"]))]
            prow = shown + [r for r in pres["rows"] if not r["people"]][: cap - len(shown)]
        mxp = max([r["people"] for r in prow] + [1])
        ptable = ('<p class="empty">No mapped localities yet.</p>' if not prow else
                  '<table class="t"><thead><tr><th>Locality</th><th class="r">People in touch</th><th class="r">Complaints</th><th>Reach</th><th>Status</th></tr></thead><tbody>'
                  + "".join(
                      f'<tr><td><b>{esc(r["name"])}</b></td><td class="r num">{_sup(r["people"])}</td><td class="r num">{_sup(r["complaints"])}</td>'
                      f'<td><span class="meter" style="display:inline-block;width:110px;margin:0;vertical-align:middle"><b style="width:{r["people"] / mxp * 100:.0f}%;'
                      f'background:{"#9E3218" if r["status"] == "none" else "#B98118" if r["status"] == "thin" else "#23496B"}"></b></span></td>'
                      f'<td><span class="st {r["status"]}">{stmap[r["status"]]}</span></td></tr>' for r in prow)
                  + "</tbody></table>")
        pnote = (f'{pres["with_presence"]} of {pres["total"]} localities in the constituency have at least one person in touch with you. '
                 f'Strong = {PRESENCE_STRONG}+ people, growing = {PRESENCE_GROWING}–{PRESENCE_STRONG - 1}, thin = 1–{PRESENCE_GROWING - 1}.'
                 if pres["gazetteer_known"] else
                 "The constituency's locality list is not set up yet, so localities with no contact cannot be shown.")
        p2 = (f'<section class="page" aria-label="Issues and presence">{head("Issues and presence")}'
              '<h2>Where the current administration is failing</h2><div class="sub">Complaints by issue, and how many are still unresolved '
              'after a month. Rising and unresolved = campaign plank.</div>'
              f'<div class="sec">{issues_table(data["backlog"]["over_30_by_issue"], story["planks"], 6)}</div>'
              '<div class="sec"><div class="sh"><div><h3>Presence map: where you are known</h3><div class="sub">People in touch with you, '
              f'by locality</div></div></div>{ptable}<div class="sub" style="margin-top:8px">{esc(pnote)}</div></div>'
              + trend_box(trend_reading()) + foot(2) + "</section>")

        no_fu = max(m["received"]["now"] - fun["action_taken"], 0)
        p3 = (f'<section class="page" aria-label="Pressure applied">{head("Pressure applied")}'
              "<h2>What you did with the complaints</h2><div class=\"sub\">You can't resolve grievances — you can make sure the system hears them</div>"
              '<div class="grid32 sec" style="align-items:start"><div>'
              + funnel_html([("Complaints received", m["received"]["now"]), ("Followed up", fun["action_taken"]),
                             ("Raised with government", fun["filed"]), ("Outcome after follow-up", fun["resolved_by_government"])], 1)
              + (f'<div class="callout"><b>{no_fu} complaints got no follow-up yet.</b> More follow-ups means more outcomes to talk about.</div>' if no_fu else "")
              + '</div><div class="box"><h3>How issues were followed up</h3><div style="margin-top:6px">'
              + kv([("Raised with a government department", fun["filed"]), ("Taken up another way", m["other_actions"]["now"]),
                    ("Not yet followed up", no_fu)])
              + '</div><div class="sub" style="margin-top:6px">Record the type of each follow-up (letter, RTI, petition, meeting) to see this in detail.</div></div></div>'
              '<div class="sec"><div class="sh"><div><h3>How government departments respond</h3><div class="sub">To issues raised with them this period</div></div></div>'
              + dept_table(("Raised", "Outcome")) + dept_callout() + "</div>"
              '<div class="grid2 sec">' + backlog_box("Left unresolved", "Over-a-month-old complaints are the evidence of a failing system.")
              + '<div class="box"><h3>Left unresolved, by issue</h3><div class="sub">Open for over a month — issue-level counts only</div><div style="margin-top:8px">'
              + kv(sorted(data["backlog"]["over_30_by_issue"].items(), key=lambda kv_: -kv_[1])[:6] or [("None", 0)]) + "</div></div></div>"
              + foot(3) + "</section>")

        wins = b["wins"]
        wins_html = ('<p class="empty">No outcomes after follow-up in this period yet.</p>' if not wins else
                     '<ul class="wins">' + "".join(
                         f'<li><span class="n num">{w["count"]}</span><span><b>{esc(w["name"])}</b>'
                         f'<div class="sub">{esc(_join(w["localities"]) or "Locality not recorded")}</div></span></li>' for w in wins) + "</ul>")
        p4 = (f'<section class="page" aria-label="Network, outcomes and data notes">{head("Network, outcomes and data notes")}'
              '<div class="grid2"><div><h2>Your network</h2><div class="sub">People counted, never listed</div><div style="margin-top:10px">'
              + kv([("People who came to you this period", reach["people"]), ("First-time contacts", reach["first_time"]),
                    ("Came back with another issue", reach["returning"])])
              + f'</div><h3 style="margin-top:14px">Languages used</h3>{langs_html()}<div class="sub" style="margin-top:6px">Use this mix for outreach and posters.</div></div>'
              f'<div><h2>Outcomes after follow-up</h2><div class="sub">Acted on by government after you raised them</div><div style="margin-top:8px">{wins_html}</div>'
              '<div class="warnnote" style="margin-top:8px">Say <b>“taken up by”</b> or <b>“after follow-up by”</b> — never “resolved by”. '
              'The department did the work; the credit is for persistence.</div></div></div>'
              '<div class="sec"><h2>Data notes</h2><div class="grid2" style="margin-top:10px">'
              + quality_box("Complaints with a mapped locality", q["mapped"], "#23496B", "The rest count in totals only.")
              + quality_box("Complaints given an issue category by staff", q["categorised"], "#23496B", "Others use the automatic category.")
              + privacy
              + '<div class="box"><b style="font-size:12px">Campaign use</b><div class="sub" style="margin-top:4px">People contacted you for help, '
              "not for campaigning. Use these figures in strategy and speeches; don't send campaign messages to them without their consent, "
              "and keep the help desk separate once the model code of conduct applies.</div></div></div></div>"
              '<div class="sec"><h3>Definitions</h3><dl class="defs">'
              "<dt>People reached</dt><dd>Distinct people who raised an issue with you in the period. Counted, never listed.</dd>"
              "<dt>Followed up</dt><dd>Raised with a government department, or taken up another way.</dd>"
              "<dt>Outcome after follow-up</dt><dd>A department reported the issue resolved after it was raised.</dd>"
              "<dt>Unresolved</dt><dd>Still open more than 30 days after the complaint.</dd></dl></div>"
              + foot(4) + "</section>")
        pages = p1 + p2 + p3 + p4
    else:
        story = office_story(data)
        lead, emph = story["verdict"]
        p1 = (f'<section class="page" aria-label="Summary">{cover}<div class="sec"><div class="eyebrow">The period in one line</div>'
              f'<p class="verdict">{esc(lead)} <em>{esc(emph)}</em></p>{take_html(story["takeaways"])}</div>'
              + score([
                  ("Complaints received", m["received"]["now"], m["received"]["previous"], "down", False),
                  ("Filed with government", m["filed"]["now"], m["filed"]["previous"], "up", False),
                  ("Resolved by government", m["resolved_by_government"]["now"], m["resolved_by_government"]["previous"], "up", False),
                  ("Other actions taken", m["other_actions"]["now"], m["other_actions"]["previous"], "up", False),
                  ("Pending", m["pending"]["now"], m["pending"]["previous"], "down", True),
              ], "Grievances received this period and where they stand now, against the previous period")
              + actions_html(story["actions"]) + foot(1) + "</section>")

        if edition == "mp":
            segs = data.get("segments") or []
            seg_html = ('<p class="empty">Grievances are not yet tagged to assembly segments.</p>' if not segs else
                        '<table class="t"><thead><tr><th>Segment</th><th class="r">Complaints</th>'
                        + ('<th class="r">Change</th>' if b["compare"] else "")
                        + '<th class="hide-sm">Top issue</th><th class="r">Filed</th><th class="r">Resolved by govt</th><th class="r">Pending</th><th class="r">Acted on</th></tr></thead><tbody>'
                        + "".join(
                            f'<tr class="{"flank" if s.get("weak_flank") else ""}"><td><b>{esc(s["name"])}</b>'
                            f'{FLANK_TAG if s.get("weak_flank") else ""}</td>'
                            f'<td class="r num"><b>{s["received"]}</b></td>'
                            + (f'<td class="r">{_chg_html(s["received"], s["previous"], "down")}</td>' if b["compare"] else "")
                            + f'<td class="hide-sm">{esc(s["top_issue"])}</td><td class="r num">{s["filed"]}</td><td class="r num">{s["resolved_by_government"]}</td>'
                            f'<td class="r num">{s["pending"]}</td><td class="r num {"bad" if s["acted_share"] < 30 else ""}">{s["acted_share"]}%</td></tr>'
                            for s in segs[:MAX_REPORT_ROWS]) + "</tbody></table>"
                        + '<div class="sub" style="margin-top:6px">Weak flank: the lowest share acted on among segments carrying at least a tenth of complaints.</div>')
            p2 = (f'<section class="page" aria-label="Segments and issues">{head("Segments and issues")}'
                  '<h2>Assembly segments compared</h2><div class="sub">Where the MP is strong and where the flank is exposed</div>'
                  f'<div class="sec">{seg_html}</div>'
                  '<div class="sec"><h3>What people are complaining about</h3><div class="sub" style="margin-bottom:8px">Across the seat, this period against the previous one</div>'
                  f'{issues_table()}</div>'
                  '<div class="sec"><div class="sh"><div><h3>Hotspots: complaints by locality and issue</h3>'
                  f'<div class="sub">Top {MAX_REPORT_ROWS} localities. Counts under {SMALL_COUNT} are shown as “&lt;{SMALL_COUNT}”.</div></div></div>{heat_grid()}</div>'
                  + foot(2) + "</section>")
        else:
            unm = b["hotspots"]["unmapped"]
            p2 = (f'<section class="page" aria-label="Issues and places">{head("Issues and places")}'
                  '<h2>What people are complaining about</h2><div class="sub">Complaints by issue, this period against the previous one</div>'
                  f'<div class="sec">{issues_table()}</div>' + trend_box(trend_reading())
                  + '<div class="sec"><div class="sh"><div><h3>Hotspots: complaints by locality and issue</h3>'
                  f'<div class="sub">Top {MAX_REPORT_ROWS} of {b["hotspots"]["total_localities"]} localities. Counts under {SMALL_COUNT} are shown as “&lt;{SMALL_COUNT}”.</div></div></div>'
                  + heat_grid()
                  + (f'<div class="sub" style="margin-top:8px">{unm} complaints had no mapped locality — see Data notes.</div>' if unm else "")
                  + "</div>" + foot(2) + "</section>")

        stuck = 2 if fun["ready_to_file"] else -1
        callout = (f'<div class="callout"><b>The drop is at filing.</b> {fun["action_taken"]} grievances saw action but only {fun["filed"]} were filed with government; '
                   f'{fun["ready_to_file"]} prepared filings are waiting.</div>' if fun["ready_to_file"] else
                   (f'<div class="callout"><b>Most grievances have no action yet.</b> {fun["pending"]} of {fun["received"]} are still pending.</div>'
                    if fun["received"] and fun["pending"] / fun["received"] > 0.5 else
                    (f'<div class="callout go"><b>Grievances are moving.</b> {fun["action_taken"]} of {fun["received"]} have seen action.</div>' if fun["received"] else "")))
        cr = data["critical"]
        p3 = (f'<section class="page" aria-label="Delivery">{head("Delivery")}'
              '<h2>From complaint to government action</h2><div class="sub">Grievances received this period and how far they have got</div>'
              '<div class="grid32 sec" style="align-items:start"><div>'
              + funnel_html([("Received", fun["received"]), ("Action taken", fun["action_taken"]), ("Filed with government", fun["filed"]),
                             ("Resolved by government", fun["resolved_by_government"])], stuck)
              + callout + '</div><div class="box"><h3>What “action” means here</h3><div style="margin-top:6px">'
              + kv([("Filed with government", fun["filed"]), ("Handled by the office another way", m["other_actions"]["now"]), ("No action yet", fun["pending"])])
              + '</div><div class="sub" style="margin-top:6px">Other actions: a letter to an official, a referral, a local fix or information given.</div></div></div>'
              '<div class="sec"><div class="sh"><div><h3>Government departments</h3><div class="sub">Filed this period, by the department responsible</div></div></div>'
              + dept_table() + dept_callout() + "</div>"
              '<div class="grid2 sec">' + backlog_box("Open backlog, by age", "Old grievances are the ones citizens remember at election time.")
              + '<div class="box"><h3>Critical grievances</h3><div class="sub">Flagged urgent by the office</div>'
              f'<div style="font-size:24px;font-weight:600;margin-top:6px" class="num {"bad" if cr["open"] else ""}">{cr["open"]} <span class="sub" style="font-weight:500">open</span></div>'
              '<div style="margin-top:8px">'
              + kv([("Oldest open critical grievance", "—" if cr["oldest_days"] is None else f'{cr["oldest_days"]} days'),
                    ("Critical received this period", cr["received"]), ("Critical closed this period", cr["closed"])])
              + "</div></div></div>" + foot(3) + "</section>")

        wins = b["wins"]
        wins_html = ('<p class="empty">No grievances were resolved by government in this period yet.</p>' if not wins else
                     '<ul class="wins">' + "".join(
                         f'<li><span class="n num">{w["count"]}</span><span><b>{esc(w["name"])}</b>'
                         f'<div class="sub">{esc(_join(w["localities"]) or "Locality not recorded")}</div></span></li>' for w in wins) + "</ul>")
        p4 = (f'<section class="page" aria-label="Wins, reach and data notes">{head("Wins, reach and data notes")}'
              f'<div class="grid2"><div><h2>Wins to publicise</h2><div class="sub">Resolved by government this period</div><div style="margin-top:8px">{wins_html}</div>'
              + kv([("Total resolved by government", b["wins_total"])])
              + '</div><div><h2>Reach</h2><div class="sub">How many people the office is hearing from — counted, never listed</div><div style="margin-top:10px">'
              + kv([("People who raised a grievance", reach["people"]), ("First-time contacts", reach["first_time"]),
                    ("Came back with another grievance", reach["returning"])])
              + f'</div><h3 style="margin-top:14px">Languages used</h3>{langs_html()}<div class="sub" style="margin-top:6px">Use this mix for outreach and posters.</div></div></div>'
              '<div class="sec"><h2>Data notes</h2><div class="sub">How complete the underlying records are — read the numbers in this light</div><div class="grid2" style="margin-top:10px">'
              + quality_box("Grievances with a mapped locality", q["mapped"], "#23496B", "The rest could not be matched to a locality and appear only in totals.")
              + quality_box("Grievances categorised by staff", q["categorised"], "#23496B", "The rest use the automatic category.")
              + quality_box("Grievances the office marked resolved", q["office_resolved"], "#9E3218",
                            "Often under-recorded when staff don't close cases. This report uses government-reported resolution instead.")
              + privacy + "</div></div>"
              '<div class="sec"><h3>Definitions</h3><dl class="defs">'
              "<dt>Complaints received</dt><dd>Grievances received in the period. Spam, abuse and comments on other grievances are excluded.</dd>"
              "<dt>Filed with government</dt><dd>Submitted to a government grievance portal or department.</dd>"
              "<dt>Resolved by government</dt><dd>Reported resolved or disposed by the portal or department.</dd>"
              "<dt>Other actions taken</dt><dd>Handled by the office without a government filing: a letter to an official, a referral, a local fix or information given.</dd>"
              "<dt>Pending</dt><dd>Received in the period with no action yet.</dd></dl></div>"
              + foot(4) + "</section>")
        pages = p1 + p2 + p3 + p4

    title = f"{seat.get('client_label') or ''} — {kind}"
    return (f'<!DOCTYPE html><html lang="en-IN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{esc(title)}</title><style>:root{{--brand:{color};--brand-fg:{fg}}}{_CSS}</style></head>'
            f'<body><div class="pages">{pages}</div></body></html>')
