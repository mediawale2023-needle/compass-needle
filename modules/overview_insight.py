"""Staff Overview: Issue Pressure (campaign insight), Office To-do and Local Signals tagging.

issue_insight   every issue the office heard about in the period, placed on a 2x2 of how
                widespread it is (localities) and how fast it is rising (vs the period
                before), with what a brief needs: people, localities, growth, open over 30
                days, the department and its filings, languages and two citizen quotes.
office_todo     four counts the office acts on, each with its oldest age.
annotate_local_signals
                tags local news with the tenant's localities and issues, and links a story to
                the office's own complaints on the same issue.

All queries are tenant-scoped. An issue is the case's category (the same value the
Briefcase category filter uses); a locality is the gazetteer match, never free text.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timedelta

from core.db_helpers import _q
from modules.partners import _FILED_SQL, _NOT_NOISE_SQL, _as_dt
from modules.partner_report import _LANG_NAMES
from modules.synthetic_cases import sql_is_live

PERIODS = (30, 90)
MAX_ISSUES = 6
MAX_LOCALITIES = 8
TREND_BUCKETS = 8
STALE_DAYS = 30
WIDE_LOCALITIES = 4          # an issue in this many localities or more is widespread
RISING_GROWTH = 0.30         # +30% on the previous period counts as rising
RISING_MIN_COMPLAINTS = 3    # ... but never on fewer than this many complaints
QUOTE_MIN, QUOTE_MAX = 12, 160
OPEN_STATUSES = ("new", "pending", "pending_review", "awaiting_location", "in_progress")
CLOSED_STATUSES = ("resolved", "completed", "closed")
GOVT_RESOLVED = ("resolved", "disposed")
UNCATEGORISED = "Uncategorised"

_ISSUE_SQL = "COALESCE(NULLIF(TRIM(c.category), ''), 'Uncategorised')"
_LOC_SQL = "NULLIF(TRIM(CAST(c.case_metadata->>'matched_value' AS TEXT)), '')"
_LANG_SQL = ("LOWER(TRIM(COALESCE(CAST(c.case_metadata->>'detected_language' AS TEXT), "
             "CAST(c.case_metadata->>'language' AS TEXT), '')))")
_SCOPE = (f"FROM cases c WHERE c.tenant_id = :tid AND COALESCE(c.is_deleted, FALSE) = FALSE "
          f"AND {sql_is_live('c')} AND {_NOT_NOISE_SQL} ")


def _days(later: datetime | None, earlier: datetime | None) -> int | None:
    if not later or not earlier:
        return None
    return max(int((later - earlier).total_seconds() // 86400), 0)


def quadrant(count: int, previous: int, localities: int) -> str:
    """plank = widespread and rising, flash = rising in few places, chronic = widespread
    and steady, watch = small and steady."""
    if previous:
        rising = count >= RISING_MIN_COMPLAINTS and (count - previous) / previous >= RISING_GROWTH
    else:
        rising = count >= RISING_MIN_COMPLAINTS
    wide = localities >= WIDE_LOCALITIES
    if wide and rising:
        return "plank"
    if rising:
        return "flash"
    if wide:
        return "chronic"
    return "watch"


def _quote(text: str | None) -> str | None:
    t = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(t) < QUOTE_MIN:
        return None
    if len(t) > QUOTE_MAX:
        t = t[:QUOTE_MAX - 1].rsplit(" ", 1)[0].rstrip(",.;:") + "…"
    return t


def issue_insight(tenant_id: int, days: int = 90, now: datetime | None = None) -> dict:
    days = days if days in PERIODS else 90
    now = now or datetime.utcnow()
    start, prev_start = now - timedelta(days=days), now - timedelta(days=2 * days)
    p = {"tid": tenant_id, "prev": prev_start, "start": start, "end": now}

    rows = _q(
        f"SELECT c.id, c.user_phone, c.status, c.created_at, c.raw_message, c.govt_status, c.govt_department, "
        f"{_ISSUE_SQL} AS issue, {_LOC_SQL} AS loc, {_LANG_SQL} AS lang, "
        f"CASE WHEN {_FILED_SQL} THEN 1 ELSE 0 END AS filed "
        f"{_SCOPE} AND c.created_at >= :prev AND c.created_at < :end",
        p,
    )
    cur: dict[str, list[dict]] = {}
    prev: Counter = Counter()
    for r in rows:
        created = _as_dt(r.get("created_at"))
        if created is None:
            continue
        r["created_at"] = created
        if created >= start:
            cur.setdefault(r["issue"], []).append(r)
        else:
            prev[r["issue"]] += 1

    # Open for more than STALE_DAYS, at any age: what people are still waiting on.
    stale_rows = _q(
        f"SELECT {_ISSUE_SQL} AS issue, COUNT(*) AS n, MIN(c.created_at) AS oldest "
        f"{_SCOPE} AND c.created_at < :cut AND LOWER(COALESCE(c.status, '')) NOT IN "
        "(" + ", ".join(f"'{s}'" for s in CLOSED_STATUSES) + ") GROUP BY 1",
        {"tid": tenant_id, "cut": now - timedelta(days=STALE_DAYS)},
    )
    stale = {r["issue"]: (int(r["n"] or 0), _days(now, _as_dt(r.get("oldest")))) for r in stale_rows}

    span = (now - start) / TREND_BUCKETS
    ranked = sorted(cur.items(), key=lambda kv: (kv[0] == UNCATEGORISED, -len(kv[1]), kv[0]))
    issues = []
    for name, items in ranked[:MAX_ISSUES]:
        count = len(items)
        phones = {str(i.get("user_phone") or "").strip() for i in items}
        phones.discard("")
        anonymous = sum(1 for i in items if not str(i.get("user_phone") or "").strip())
        locs = Counter(i["loc"] for i in items if i.get("loc"))
        trend = [0] * TREND_BUCKETS
        for i in items:
            trend[min(int((i["created_at"] - start) / span), TREND_BUCKETS - 1)] += 1
        langs = Counter(_LANG_NAMES.get((i.get("lang") or "").strip()) for i in items)
        langs.pop(None, None)
        lang_total = sum(langs.values())
        filed = [i for i in items if int(i.get("filed") or 0)]
        depts = Counter(str(i.get("govt_department") or "").strip() for i in filed)
        depts.pop("", None)
        top_locs = [l for l, _ in locs.most_common(3)]
        quotes, seen = [], set()
        for i in sorted(items, key=lambda x: (x.get("loc") not in top_locs, -x["created_at"].timestamp())):
            q = _quote(i.get("raw_message"))
            if not q or q.lower() in seen:
                continue
            seen.add(q.lower())
            quotes.append({"text": q, "locality": i.get("loc"), "locality_complaints": locs.get(i.get("loc"), 0)})
            if len(quotes) == 2:
                break
        n_stale, oldest = stale.get(name, (0, None))
        previous = int(prev.get(name, 0))
        issues.append({
            "issue": name,
            "complaints": count,
            "previous": previous,
            "people": len(phones) + anonymous,
            "localities": [{"name": l, "complaints": n} for l, n in sorted(locs.items(), key=lambda kv: (-kv[1], kv[0]))[:MAX_LOCALITIES]],
            "locality_count": len(locs),
            "quadrant": quadrant(count, previous, len(locs)),
            "open_over_30_days": n_stale,
            "oldest_open_days": oldest,
            "trend": trend,
            "languages": [{"name": n, "share": round(c / lang_total * 100)} for n, c in langs.most_common(2)] if lang_total else [],
            "department": depts.most_common(1)[0][0] if depts else None,
            "filed": len(filed),
            "filed_resolved": sum(1 for i in filed if str(i.get("govt_status") or "").lower() in GOVT_RESOLVED),
            "quotes": quotes,
        })
    return {"period_days": days, "issues": issues}


def office_todo(tenant_id: int, now: datetime | None = None) -> dict:
    now = now or datetime.utcnow()
    p = {"tid": tenant_id}
    unassigned = _q(
        f"SELECT COUNT(*) AS n, MIN(c.created_at) AS oldest {_SCOPE} "
        "AND NULLIF(TRIM(CAST(c.assigned_to AS TEXT)), '') IS NULL AND LOWER(COALESCE(c.status, '')) IN ("
        + ", ".join(f"'{s}'" for s in OPEN_STATUSES) + ")", p)
    letters = _q(
        "SELECT COUNT(*) AS n, MIN(created_at) AS oldest FROM letterbox WHERE tenant_id = :tid AND direction = 'inbox' "
        "AND status IN ('new', 'needs_review', 'processing') AND COALESCE(is_deleted, FALSE) = FALSE", p)
    drafts = _q(
        "SELECT COUNT(*) AS n, MIN(created_at) AS oldest FROM letterbox WHERE tenant_id = :tid AND direction = 'outbox' "
        "AND status = 'drafted' AND COALESCE(is_deleted, FALSE) = FALSE", p)
    untold = _q(
        f"SELECT COUNT(*) AS n, MIN(c.govt_status_updated_at) AS oldest {_SCOPE} "
        "AND LOWER(COALESCE(c.govt_status, '')) IN (" + ", ".join(f"'{s}'" for s in GOVT_RESOLVED) + ") "
        "AND (c.govt_last_forwarded_to_citizen_at IS NULL OR c.govt_status_updated_at IS NULL "
        "OR c.govt_last_forwarded_to_citizen_at < c.govt_status_updated_at)", p)

    def item(key, rows):
        r = rows[0] if rows else {}
        n = int(r.get("n") or 0)
        return {"key": key, "count": n, "oldest_days": _days(now, _as_dt(r.get("oldest"))) if n else None}

    return {"items": [item("unassigned", unassigned), item("letters", letters),
                      item("drafts", drafts), item("citizens_to_update", untold)]}


# ── Local Signals tagging ────────────────────────────────────────────────────
# Keyword groups -> words that identify a tenant's category by name, and a label used
# when the story's issue matches no category the office has complaints in.
ISSUE_KEYWORDS = (
    ("Law & order", ("police", "theft", "thief", "robbery", "murder", "assault", "crime", "arrest", "detention",
                     "detained", "stabb", "chain snatch", "fraud", "booked", "molest", "kidnap", "riot"),
     ("theft", "crime", "safety", "police", "law", "assault")),
    ("Roads", ("road", "pothole", "bridge", "flyover", "footpath", "traffic", "highway", "resurfac"),
     ("road", "bridge", "traffic")),
    ("Water", ("water", "pipeline", "tanker", "borewell", "jal "), ("water",)),
    ("Drainage", ("drain", "sewage", "sewer", "flood", "waterlogg", "nala"), ("drain", "sewage", "sewer", "flood")),
    ("Power", ("power cut", "electricity", "hescom", "bescom", "transformer", "streetlight", "street light", "outage"),
     ("power", "electric", "light")),
    ("Health", ("hospital", "health", "doctor", "phc", "dengue", "medical", "ambulance"), ("health", "hospital", "medical")),
    ("Sanitation", ("garbage", "waste", "sanitation", "dump", "stray dog"), ("garbage", "waste", "sanitation", "clean")),
    ("Education", ("school", "college", "teacher", "student"), ("school", "education", "college")),
)


def _story_issue(title: str, categories: dict[str, int]) -> tuple[str | None, str | None]:
    """(label, tenant category) for a headline; the category is None when the office has none for it."""
    low = f" {title.lower()} "
    for label, words, stems in ISSUE_KEYWORDS:
        if not any(w in low for w in words):
            continue
        matches = [c for c in categories if any(s in c.lower() for s in stems)]
        if matches:
            best = max(matches, key=lambda c: (categories[c], c))
            return best, best
        return label, None
    return None, None


def annotate_local_signals(tenant_id: int, articles: list[dict], now: datetime | None = None) -> list[dict]:
    """Add localities, issue, a line linking the story to the office's complaints, and relevance
    (3 linked to complaints, 2 local place or issue, 0 only the city) — most relevant first."""
    now = now or datetime.utcnow()
    cut, prev_cut = now - timedelta(days=30), now - timedelta(days=60)
    rows = _q(
        f"SELECT {_ISSUE_SQL} AS issue, {_LOC_SQL} AS loc, "
        "SUM(CASE WHEN c.created_at >= :cut THEN 1 ELSE 0 END) AS n, "
        "SUM(CASE WHEN c.created_at < :cut THEN 1 ELSE 0 END) AS p "
        f"{_SCOPE} AND c.created_at >= :prev GROUP BY 1, 2",
        {"tid": tenant_id, "cut": cut, "prev": prev_cut},
    )
    cat_now: Counter = Counter()
    cat_prev: Counter = Counter()
    by_loc_cat: Counter = Counter()
    locs: set[str] = set()
    for r in rows:
        n, pv = int(r.get("n") or 0), int(r.get("p") or 0)
        if r["issue"] != UNCATEGORISED:
            cat_now[r["issue"]] += n
            cat_prev[r["issue"]] += pv
        if r.get("loc"):
            locs.add(r["loc"])
            by_loc_cat[(r["loc"], r["issue"])] += n
    categories = {c: n for c, n in cat_now.items() if n}
    # longest names first so "Kunti Nagar Khasbag" wins over "Khasbag"
    loc_terms = sorted((l for l in locs if len(l) >= 4), key=len, reverse=True)

    out = []
    for idx, a in enumerate(articles or []):
        title = str(a.get("title") or "")
        low = title.lower()
        found: list[str] = []
        for l in loc_terms:
            if re.search(rf"(?<!\w){re.escape(l.lower())}(?!\w)", low) and not any(l.lower() in f.lower() for f in found):
                found.append(l)
        label, category = _story_issue(title, categories)
        link = None
        if category:
            in_loc = [(l, by_loc_cat[(l, category)]) for l in found if by_loc_cat[(l, category)]]
            if in_loc:
                l, n = in_loc[0]
                link = f"{n} {category} complaint{'s' if n != 1 else ''} from {l} in the last 30 days"
            else:
                n, pv = categories[category], cat_prev.get(category, 0)
                link = f"{n} {category} complaint{'s' if n != 1 else ''} in the last 30 days" + (
                    f", up from {pv}" if n > pv else "")
        relevance = 3 if link else (2 if (found or label) else 0)
        out.append({**a, "localities": found[:3], "issue": label, "linked": link, "relevance": relevance, "_i": idx})
    out.sort(key=lambda a: (-a["relevance"], a["_i"]))
    for a in out:
        a.pop("_i", None)
    return out
