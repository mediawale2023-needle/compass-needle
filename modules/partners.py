"""
Partner layer — political consultancies that resell Needle seats to their clients.

A *partner* is a consultancy. It owns any number of *seats* (no cap); each seat
is one client (an aspirant / MLA / MP tenant). Partners never get case-level or
citizen-level data: they see aggregate metrics and a white-labelled report per client.

Attribution: every tenant created through Needle onboarding gets one
`tenant_attributions` row (channel = direct | partner). For partner tenants the
`partner_seats` row is the *access* link (active | paused | revoked) and is created
in the same transaction as the tenant. Pausing a seat never changes attribution.

Isolation rules (do not weaken):
  * Tenant ids are ONLY ever derived from `partner_seats` rows owned by the
    authenticated partner — never from request input.
  * Partner JWTs are signed with a key derived from JWT_SECRET, so they fail
    signature checks on every MP/admin endpoint (and vice versa).
  * No citizen phone numbers, raw messages or names leave this module.

Schema changes are expand/contract: startup only ADDS (tables, backfill) and the retired seat_cap column is dropped
separately in phase 2 (`contract_seat_cap`, scripts/partner_drop_seat_cap.py).
"""
import hashlib
import hmac
import html
import logging
import os
import re
import math
from datetime import datetime, timedelta

from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint,
)

from sansadx_backend.db import Base
from core.db_helpers import _q
from modules.synthetic_cases import sql_is_live

SEAT_TYPES = ("mp", "mla")
# Seat status vocabulary. "requested"/"rejected" are LEGACY (the partner seat-request
# workflow was removed; old rows are kept as history). "revoked" = attribution moved away.
PORTFOLIO_STATUSES = ("active", "paused")  # what a partner can see in its portfolio
CHANNEL_DIRECT = "direct"
CHANNEL_PARTNER = "partner"
logger = logging.getLogger("needle.partner")
RESOLVED_STATUSES = ("resolved", "completed")
DEFAULT_BRAND_COLOR = "#1F3A5F"


# ─────────────────────────────────────────
# MODELS
# ─────────────────────────────────────────
class PartnerOrg(Base):
    __tablename__ = "partners"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, index=True, nullable=False)
    brand_name = Column(String, nullable=False)
    brand_color = Column(String, default=DEFAULT_BRAND_COLOR)
    brand_logo_url = Column(String, nullable=True)  # https only
    show_powered_by = Column(Boolean, default=True)
    contact_email = Column(String, nullable=True)
    wholesale_price_inr = Column(Integer, default=0)  # per active client / month, billed manually
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class PartnerUser(Base):
    __tablename__ = "partner_users"

    id = Column(Integer, primary_key=True, index=True)
    partner_id = Column(Integer, ForeignKey("partners.id"), index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)  # stored lowercase
    display_name = Column(String, nullable=True)
    password_hash = Column(String, nullable=False)
    must_change_password = Column(Boolean, default=True)
    password_changed_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class PartnerSeat(Base):
    __tablename__ = "partner_seats"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_partner_seats_tenant"),)

    id = Column(Integer, primary_key=True, index=True)
    partner_id = Column(Integer, ForeignKey("partners.id"), index=True, nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True)  # set when Needle provisions
    client_label = Column(String, nullable=False)  # partner's own name for the client
    constituency = Column(String, nullable=True)
    seat_type = Column(String, default="mp")
    notes = Column(Text, nullable=True)
    status = Column(String, default="active")  # active | paused | revoked  (legacy: requested | rejected)
    created_at = Column(DateTime, default=datetime.utcnow)
    activated_at = Column(DateTime, nullable=True)


class TenantAttribution(Base):
    """How a tenant came to Needle. One row per tenant; the backend is the only writer."""
    __tablename__ = "tenant_attributions"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_tenant_attributions_tenant"),
        CheckConstraint(
            "(channel = 'direct' AND partner_id IS NULL) OR (channel = 'partner' AND partner_id IS NOT NULL)",
            name="ck_tenant_attributions_channel_partner",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    channel = Column(String, nullable=False, default=CHANNEL_DIRECT)  # direct | partner
    partner_id = Column(Integer, ForeignKey("partners.id"), index=True, nullable=True)
    attributed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    attributed_by = Column(String, nullable=True)  # Needle admin username (from the verified token, never the request)
    attributed_by_user_id = Column(Integer, nullable=True)


class TenantAttributionEvent(Base):
    """Append-only history: onboarding, reassignments, migration. Survives tenant deletion."""
    __tablename__ = "tenant_attribution_events"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, index=True, nullable=False)  # deliberately no FK: audit outlives the tenant
    event = Column(String, nullable=False)  # onboarded | reassigned | migrated | legacy_request_activated
    from_channel = Column(String, nullable=True)
    from_partner_id = Column(Integer, nullable=True)
    to_channel = Column(String, nullable=False)
    to_partner_id = Column(Integer, nullable=True)
    reason = Column(Text, nullable=True)
    changed_by = Column(String, nullable=True)
    changed_by_user_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# ─────────────────────────────────────────
# TOKENS (derived key — see module docstring)
# ─────────────────────────────────────────
def partner_jwt_key() -> str:
    secret = os.getenv("JWT_SECRET", "")
    if len(secret) < 32:
        raise ValueError("JWT_SECRET must be set and at least 32 characters long.")
    return hmac.new(secret.encode(), b"needle-partner-v1", hashlib.sha256).hexdigest()


# ─────────────────────────────────────────
# VALIDATION HELPERS
# ─────────────────────────────────────────
_SLUG_RE = re.compile(r"[^a-z0-9]+")
_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def make_slug(value: str) -> str:
    slug = _SLUG_RE.sub("-", (value or "").lower()).strip("-")
    return slug[:48]


def clean_color(value: str | None) -> str:
    return value if value and _COLOR_RE.match(value) else DEFAULT_BRAND_COLOR


def clean_logo_url(value: str | None) -> str | None:
    value = (value or "").strip()
    if not value:
        return None
    if not value.lower().startswith("https://") or len(value) > 500:
        raise ValueError("brand_logo_url must be an https:// URL")
    return value


# ─────────────────────────────────────────
# METRICS (aggregate only)
# ─────────────────────────────────────────
def _as_dt(value) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


class ReportWindow:
    """The date range a partner metric covers: [start, end) in UTC. start=None means all time.

    Built only from validated query parameters (see resolve_window); never from free text.
    """

    def __init__(self, start: datetime | None, end: datetime, kind: str):
        self.start, self.end, self.kind = start, end, kind  # kind: days | custom | all

    def bounded(self, first_case: datetime | None) -> "ReportWindow":
        """All-time windows start at the earliest case, so trend buckets have a real span."""
        if self.start is not None:
            return self
        start = first_case or (self.end - timedelta(days=30))
        return ReportWindow(min(start, self.end - timedelta(days=1)), self.end, self.kind)

    @property
    def span_days(self) -> float:
        return max((self.end - (self.start or self.end)).total_seconds() / 86400, 0)

    def describe(self) -> dict:
        return {
            "kind": self.kind,
            "from": self.start.date().isoformat() if self.start else None,
            "to": (self.end - timedelta(microseconds=1)).date().isoformat(),
            "days": max(round(self.span_days), 1) if self.start else None,
        }


MAX_WINDOW_DAYS = 3650


class WindowError(ValueError):
    pass


def resolve_window(days=None, range_=None, from_=None, to=None, now: datetime | None = None) -> ReportWindow:
    """One of: days=N (1..3650, ending now), range='all', or from/to calendar dates (inclusive)."""
    now = now or datetime.utcnow()
    if range_ not in (None, "", "all"):
        raise WindowError("range must be 'all'")
    if range_ == "all":
        if days is not None or from_ or to:
            raise WindowError("range=all cannot be combined with days or from/to")
        return ReportWindow(None, now, "all")
    if from_ or to:
        if days is not None:
            raise WindowError("Use either days or from/to, not both")
        if not (from_ and to):
            raise WindowError("from and to must be given together")
        if from_ > to:
            raise WindowError("from must be on or before to")
        start = datetime.combine(from_, datetime.min.time())
        end = datetime.combine(to, datetime.min.time()) + timedelta(days=1)
        if (end - start).days > MAX_WINDOW_DAYS:
            raise WindowError(f"A custom range can cover at most {MAX_WINDOW_DAYS} days; use range=all for everything")
        return ReportWindow(start, end, "custom")
    days = 30 if days is None else int(days)
    if not 1 <= days <= MAX_WINDOW_DAYS:
        raise WindowError(f"days must be between 1 and {MAX_WINDOW_DAYS}")
    return ReportWindow(now - timedelta(days=days), now, "days")


# Trend bucket sizes in days; the smallest one that keeps the chart at <= 14 points.
_BUCKETS = (1, 7, 14, 30, 91, 182, 365)


def bucket_days_for(span_days: float) -> int:
    for b in _BUCKETS:
        if span_days / b <= 14:
            return b
    return _BUCKETS[-1] * max(1, math.ceil(span_days / (14 * _BUCKETS[-1])))


def _dialect() -> str:
    import core.db_helpers as dbh  # read at call time so tests' engine swap is honoured
    return dbh.engine.dialect.name


# Statuses that are not grievances (spam, abuse, comments on another case, intake buffers). They are
# never counted as complaints in partner views.
NON_GRIEVANCE_STATUSES = ("irrelevant", "offensive", "case_comment", "contact_buffered")
_NOT_NOISE_SQL = "LOWER(COALESCE(c.status, '')) NOT IN (" + ", ".join(f"'{s}'" for s in NON_GRIEVANCE_STATUSES) + ")"


def _case_scope_sql(start_param: str = "start", end_param: str = "end") -> str:
    # Aggregate-safe columns only are ever read below: no phone, no message text.
    return (
        "FROM cases c WHERE c.tenant_id = :tid AND COALESCE(c.is_deleted, FALSE) = FALSE "
        f"AND {sql_is_live('c')} AND {_NOT_NOISE_SQL} "
        f"AND c.created_at >= :{start_param} AND c.created_at < :{end_param}"
    )


def _bucket_sql() -> str:
    """Bucket index of a case, counted back from :end in steps of :bucket days (0 = the latest bucket)."""
    if _dialect() == "postgresql":
        return "CAST(FLOOR((EXTRACT(EPOCH FROM (CAST(:end AS timestamp) - c.created_at)) / 86400.0) / :bucket) AS INTEGER)"
    return "CAST((julianday(:end) - julianday(c.created_at)) / :bucket AS INTEGER)"


def _bucket_bounds(window: "ReportWindow", bucket: int) -> list[tuple[datetime, datetime]]:
    """[(start, end)] oldest first, bucket 0 ending at window.end."""
    n = max(1, math.ceil(window.span_days / bucket))
    out = []
    for i in range(n - 1, -1, -1):
        b_end = window.end - timedelta(days=bucket * i)
        b_start = max(b_end - timedelta(days=bucket), window.start) if window.start else b_end - timedelta(days=bucket)
        out.append((b_start, b_end))
    return out


def first_case_at(tenant_ids: list[int]) -> datetime | None:
    """Earliest live case across the given tenants (one indexed MIN per tenant set)."""
    ids = [int(t) for t in tenant_ids if t]
    if not ids:
        return None
    params = {f"t{i}": t for i, t in enumerate(ids)}
    row = _q(
        f"SELECT MIN(c.created_at) AS first FROM cases c WHERE c.tenant_id IN ({', '.join(':' + k for k in params)}) "
        f"AND COALESCE(c.is_deleted, FALSE) = FALSE AND {sql_is_live('c')}",
        params,
    )
    return _as_dt(row[0]["first"]) if row else None


def tenant_summary(tenant_id: int, window: "ReportWindow | int" = 30, now: datetime | None = None) -> dict:
    """Aggregate figures for one tenant over a window, computed in SQL (bounded result sizes).

    Counts every live, non-deleted case created inside the window exactly once. Resolution is
    "of the grievances received in the window, how many are resolved now" — as before.
    """
    if not isinstance(window, ReportWindow):  # legacy callers: an int number of days
        window = resolve_window(days=int(window), now=now)
    window = window.bounded(first_case_at([tenant_id]) if window.start is None else None)
    p = {"tid": int(tenant_id), "start": window.start, "end": window.end}
    scope = _case_scope_sql()
    resolved_sql = "LOWER(COALESCE(c.status, '')) IN ('resolved', 'completed')"
    if _dialect() == "postgresql":
        duration = "GREATEST(EXTRACT(EPOCH FROM (c.resolved_at - c.created_at)) / 86400.0, 0)"
    else:  # SQLite (tests)
        duration = "MAX(julianday(c.resolved_at) - julianday(c.created_at), 0)"
    bucket_expr = _bucket_sql()

    head = _q(
        f"SELECT COUNT(*) AS total, "
        f"COALESCE(SUM(CASE WHEN {resolved_sql} THEN 1 ELSE 0 END), 0) AS resolved, "
        f"COALESCE(SUM(CASE WHEN c.is_critical THEN 1 ELSE 0 END), 0) AS critical, "
        f"AVG(CASE WHEN {resolved_sql} AND c.resolved_at IS NOT NULL THEN {duration} END) AS avg_days "
        f"{scope}", p,
    )[0]
    total, resolved = int(head["total"] or 0), int(head["resolved"] or 0)
    categories = _q(
        f"SELECT COALESCE(NULLIF(c.category, ''), 'Uncategorised') AS name, COUNT(*) AS count {scope} "
        "GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT 5", p,
    )
    places = _q(
        f"SELECT COALESCE(NULLIF(c.ward, ''), NULLIF(c.assembly, ''), 'Unmapped') AS name, COUNT(*) AS count {scope} "
        "GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT 5", p,
    )

    bucket = bucket_days_for(window.span_days)
    grouped = _q(
        f"SELECT {bucket_expr} AS b, COUNT(*) AS received, "
        f"COALESCE(SUM(CASE WHEN {resolved_sql} THEN 1 ELSE 0 END), 0) AS resolved {scope} GROUP BY 1",
        {**p, "bucket": bucket},
    )
    by_index = {int(r["b"]): r for r in grouped if r["b"] is not None}
    trend = []
    bounds = _bucket_bounds(window, bucket)
    for pos, (b_start, b_end) in enumerate(bounds):  # oldest first; bucket 0 ends at window.end
        r = by_index.get(len(bounds) - 1 - pos, {})
        trend.append({
            "period_start": b_start.date().isoformat(),
            "period_end": (b_end - timedelta(microseconds=1)).date().isoformat(),
            "received": int(r.get("received") or 0),
            "resolved": int(r.get("resolved") or 0),
        })

    avg = head["avg_days"]
    return {
        "window": window.describe(),
        "days": window.describe()["days"],
        "bucket_days": bucket,
        "total": total,
        "resolved": resolved,
        "open": total - resolved,
        "critical": int(head["critical"] or 0),
        "resolution_rate": round(resolved / total, 3) if total else None,
        "avg_resolution_days": round(float(avg), 1) if avg is not None else None,
        "top_categories": [{"name": r["name"], "count": int(r["count"])} for r in categories],
        "top_locations": [{"name": r["name"], "count": int(r["count"])} for r in places],
        "trend": trend,
    }


# ─────────────────────────────────────────
# CLIENT BRIEFING (consultant view) — counts only
# ─────────────────────────────────────────
# Portal statuses that mean a grievance has been filed with government (mirrors modules.case_lifecycle).
GOVT_FILED_STATUSES = ("submitted", "registered", "forwarded", "under_review", "escalated", "resolved", "rejected", "disposed")
GOVT_RESOLVED_STATUSES = ("resolved", "disposed")
# Office statuses that mean the office acted on (or closed) a grievance itself.
OFFICE_ACTION_STATUSES = ("in_progress", "resolved", "completed", "closed")

_FILED_SQL = (
    "(NULLIF(TRIM(COALESCE(c.govt_reference_number, '')), '') IS NOT NULL "
    "OR LOWER(COALESCE(c.govt_status, '')) IN (" + ", ".join(f"'{s}'" for s in GOVT_FILED_STATUSES) + "))"
)
_GOVT_RESOLVED_SQL = "LOWER(COALESCE(c.govt_status, '')) IN (" + ", ".join(f"'{s}'" for s in GOVT_RESOLVED_STATUSES) + ")"
_OTHER_ACTION_SQL = (
    f"(NOT {_FILED_SQL} AND LOWER(COALESCE(c.status, '')) IN ("
    + ", ".join(f"'{s}'" for s in OFFICE_ACTION_STATUSES) + "))"
)
_READY_SQL = f"(NOT {_FILED_SQL} AND LOWER(COALESCE(c.govt_status, '')) = 'pending_staff_submit')"
# The office's mapped locality (gazetteer match). Free-text addresses (c.location) are never read.
_LOCALITY_SQL = "NULLIF(TRIM(CAST(c.case_metadata->>'matched_value' AS TEXT)), '')"
_CATEGORY_SQL = "COALESCE(NULLIF(TRIM(c.category), ''), 'Uncategorised')"

MAX_BRIEFING_ISSUES = 12
MAX_HOTSPOT_COLUMNS = 4
MAX_HOTSPOT_LOCALITIES = 500
MAX_WINS = 5


def _outcome_counts(p: dict, start_param: str, end_param: str) -> dict:
    row = _q(
        "SELECT COUNT(*) AS received, "
        f"COALESCE(SUM(CASE WHEN {_FILED_SQL} THEN 1 ELSE 0 END), 0) AS filed, "
        f"COALESCE(SUM(CASE WHEN {_FILED_SQL} AND {_GOVT_RESOLVED_SQL} THEN 1 ELSE 0 END), 0) AS gov_resolved, "
        f"COALESCE(SUM(CASE WHEN {_OTHER_ACTION_SQL} THEN 1 ELSE 0 END), 0) AS other, "
        f"COALESCE(SUM(CASE WHEN {_READY_SQL} THEN 1 ELSE 0 END), 0) AS ready, "
        f"MIN(CASE WHEN {_READY_SQL} THEN COALESCE(c.govt_status_updated_at, c.created_at) END) AS oldest_ready "
        f"{_case_scope_sql(start_param, end_param)}", p,
    )[0]
    received, filed, other = int(row["received"] or 0), int(row["filed"] or 0), int(row["other"] or 0)
    return {
        "received": received, "filed": filed, "resolved_by_government": int(row["gov_resolved"] or 0),
        "other_actions": other, "pending": max(received - filed - other, 0),
        "ready_to_file": int(row["ready"] or 0), "oldest_ready": _as_dt(row["oldest_ready"]),
    }


def client_briefing(tenant_id: int, window: "ReportWindow", now: datetime | None = None) -> dict:
    """Consultant briefing for one tenant: momentum, issues, locality hotspots, delivery and wins.

    Cohort semantics: every figure is about grievances RECEIVED in the window and where they stand now.
    The comparison period is the same length immediately before the window (none for all time).
    All queries are tenant-scoped GROUP BYs with bounded results; no case rows, text, phones or addresses.
    """
    now = now or datetime.utcnow()
    window = window.bounded(first_case_at([tenant_id]) if window.start is None else None)
    prev = None
    if window.kind != "all":
        span = window.end - window.start
        prev = (window.start - span, window.start)
    p = {"tid": int(tenant_id), "start": window.start, "end": window.end,
         "pstart": prev[0] if prev else window.start, "pend": prev[1] if prev else window.start}
    scope = _case_scope_sql()

    cur = _outcome_counts(p, "start", "end")
    before = _outcome_counts(p, "pstart", "pend") if prev else None

    # Trend buckets for the momentum sparklines.
    bucket = bucket_days_for(window.span_days)
    bounds = _bucket_bounds(window, bucket)
    nb = len(bounds)
    bp = {**p, "bucket": bucket}
    bexpr = _bucket_sql()
    rows = _q(
        f"SELECT {bexpr} AS b, COUNT(*) AS received, "
        f"COALESCE(SUM(CASE WHEN {_FILED_SQL} THEN 1 ELSE 0 END), 0) AS filed, "
        f"COALESCE(SUM(CASE WHEN {_FILED_SQL} AND {_GOVT_RESOLVED_SQL} THEN 1 ELSE 0 END), 0) AS gov_resolved, "
        f"COALESCE(SUM(CASE WHEN {_OTHER_ACTION_SQL} THEN 1 ELSE 0 END), 0) AS other {scope} GROUP BY 1", bp,
    )
    series = {k: [0] * nb for k in ("received", "filed", "resolved_by_government", "other_actions", "pending")}
    for r in rows:
        if r["b"] is None:
            continue
        pos = nb - 1 - int(r["b"])
        if not 0 <= pos < nb:
            continue
        rec, fil, oth = int(r["received"] or 0), int(r["filed"] or 0), int(r["other"] or 0)
        series["received"][pos] = rec
        series["filed"][pos] = fil
        series["resolved_by_government"][pos] = int(r["gov_resolved"] or 0)
        series["other_actions"][pos] = oth
        series["pending"][pos] = max(rec - fil - oth, 0)

    momentum = {
        key: {"now": cur[key], "previous": before[key] if before else None, "trend": series[key]}
        for key in ("received", "filed", "resolved_by_government", "other_actions", "pending")
    }

    # Issues: count now vs before, trend, and the localities driving each.
    cat_rows = _q(
        f"SELECT {_CATEGORY_SQL} AS name, "
        "COALESCE(SUM(CASE WHEN c.created_at >= :start THEN 1 ELSE 0 END), 0) AS now_count, "
        "COALESCE(SUM(CASE WHEN c.created_at < :start THEN 1 ELSE 0 END), 0) AS prev_count "
        f"{_case_scope_sql('pstart', 'end')} GROUP BY 1", p,
    )
    cats = sorted(
        ({"name": r["name"], "count": int(r["now_count"] or 0), "previous": int(r["prev_count"] or 0) if prev else None}
         for r in cat_rows),
        key=lambda c: (-c["count"], -(c["previous"] or 0), c["name"]),
    )
    cats = [c for c in cats if c["count"] or c["previous"]][:MAX_BRIEFING_ISSUES]
    names = {c["name"] for c in cats}
    trend_rows = _q(f"SELECT {_CATEGORY_SQL} AS name, {bexpr} AS b, COUNT(*) AS n {scope} GROUP BY 1, 2", bp)
    cat_trend = {c["name"]: [0] * nb for c in cats}
    for r in trend_rows:
        if r["name"] in names and r["b"] is not None and 0 <= nb - 1 - int(r["b"]) < nb:
            cat_trend[r["name"]][nb - 1 - int(r["b"])] = int(r["n"] or 0)

    pair_rows = _q(
        f"SELECT {_LOCALITY_SQL} AS loc, {_CATEGORY_SQL} AS name, COUNT(*) AS n, "
        f"COALESCE(SUM(CASE WHEN {_FILED_SQL} AND {_GOVT_RESOLVED_SQL} THEN 1 ELSE 0 END), 0) AS won "
        f"{scope} GROUP BY 1, 2", p,
    )
    by_loc: dict[str, dict[str, int]] = {}
    cat_locs: dict[str, dict[str, int]] = {}
    win_locs: dict[str, dict[str, int]] = {}
    unmapped = 0
    for r in pair_rows:
        n, loc, name = int(r["n"] or 0), r["loc"], r["name"]
        if not loc:
            unmapped += n
            continue
        by_loc.setdefault(loc, {})[name] = by_loc.get(loc, {}).get(name, 0) + n
        cat_locs.setdefault(name, {})[loc] = n
        if int(r["won"] or 0):
            win_locs.setdefault(name, {})[loc] = int(r["won"])

    def _top(d: dict[str, int], k: int) -> list[dict]:
        return [{"name": n, "count": c} for n, c in sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))[:k]]

    issues = [{**c, "trend": cat_trend.get(c["name"], [0] * nb), "top_localities": _top(cat_locs.get(c["name"], {}), 3)}
              for c in cats]

    columns = [c["name"] for c in cats if c["count"]][:MAX_HOTSPOT_COLUMNS]
    loc_list = sorted(
        ({"name": loc, "total": sum(v.values()), "counts": [v.get(col, 0) for col in columns]} for loc, v in by_loc.items()),
        key=lambda x: (-x["total"], x["name"]),
    )

    # Wins: resolved by government, grouped by issue, with the localities they came from.
    win_rows = _q(
        f"SELECT {_CATEGORY_SQL} AS name, COUNT(*) AS n {scope} AND {_FILED_SQL} AND {_GOVT_RESOLVED_SQL} "
        "GROUP BY 1 ORDER BY 2 DESC, 1", p,
    )
    wins = [{"name": r["name"], "count": int(r["n"] or 0), "localities": [x["name"] for x in _top(win_locs.get(r["name"], {}), 2)]}
            for r in win_rows[:MAX_WINS]]

    oldest = cur["oldest_ready"]
    return {
        "window": window.describe(),
        "compare": ({"from": prev[0].date().isoformat(), "to": (prev[1] - timedelta(microseconds=1)).date().isoformat()}
                    if prev else None),
        "bucket_days": bucket,
        "periods": [{"period_start": a.date().isoformat(), "period_end": (b - timedelta(microseconds=1)).date().isoformat()}
                    for a, b in bounds],
        "momentum": momentum,
        "funnel": {
            "received": cur["received"],
            "action_taken": cur["filed"] + cur["other_actions"],
            "filed": cur["filed"],
            "resolved_by_government": cur["resolved_by_government"],
            "pending": cur["pending"],
            "ready_to_file": cur["ready_to_file"],
            "oldest_ready_days": max(int((now - oldest).total_seconds() // 86400), 0) if oldest else None,
        },
        "issues": issues,
        "hotspots": {
            "columns": columns,
            "localities": loc_list[:MAX_HOTSPOT_LOCALITIES],
            "total_localities": len(loc_list),
            "unmapped": unmapped,
        },
        "wins": wins,
        "wins_total": cur["resolved_by_government"],
    }


# ─────────────────────────────────────────
# WHITE-LABEL REPORT
# ─────────────────────────────────────────
def _pct(value) -> str:
    return "—" if value is None else f"{round(value * 100)}%"


def _rows_html(items: list[dict]) -> str:
    if not items:
        return '<tr><td colspan="2" class="muted">No data in this period</td></tr>'
    return "".join(
        f"<tr><td>{html.escape(str(i['name']))}</td><td class='num'>{i['count']}</td></tr>" for i in items
    )


def render_client_report(partner: dict, seat: dict, summary: dict, generated_at: datetime | None = None) -> str:
    """Self-contained HTML. Every interpolated value is escaped."""
    esc = html.escape
    generated_at = generated_at or datetime.utcnow()
    color = clean_color(partner.get("brand_color"))
    logo = partner.get("brand_logo_url")
    logo_html = f'<img src="{esc(logo, quote=True)}" alt="" class="logo">' if logo else ""
    powered = (
        '<p class="muted">Intelligence by Compass Needle</p>' if partner.get("show_powered_by") else ""
    )
    trend_max = max([w["received"] for w in summary["trend"]] + [1])
    bars = "".join(
        f'<div class="bar" title="{esc(w["period_start"])} to {esc(w["period_end"])}: {w["received"]} received" '
        f'style="height:{max(round(w["received"] / trend_max * 100), 2)}%"></div>'
        for w in summary["trend"]
    )
    win = summary["window"]
    period = "All time" if win["kind"] == "all" else (
        f"last {win['days']} days" if win["kind"] == "days" else f"{win['from']} to {win['to']}")
    if win["kind"] == "all" and win.get("from"):
        period = f"All time (since {win['from']})"
    unit = {1: "day", 7: "week", 14: "fortnight", 30: "month", 91: "quarter", 182: "half-year", 365: "year"}.get(
        summary["bucket_days"], f"{summary['bucket_days']} days")
    avg = summary["avg_resolution_days"]
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(seat["client_label"])} — Constituency Snapshot</title>
<style>
body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;color:#1a1a1a;max-width:860px;margin:0 auto;padding:32px 20px}}
header{{border-bottom:4px solid {color};padding-bottom:16px;margin-bottom:24px;display:flex;justify-content:space-between;align-items:center}}
h1{{font-size:22px;margin:0;color:{color}}} h2{{font-size:15px;margin:28px 0 8px;color:{color}}}
.logo{{max-height:48px}} .muted{{color:#777;font-size:12px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}}
.kpi{{border:1px solid #e3e3e3;border-radius:8px;padding:12px}} .kpi b{{display:block;font-size:26px;color:{color}}}
table{{width:100%;border-collapse:collapse}} td{{padding:6px 4px;border-bottom:1px solid #eee}} .num{{text-align:right}}
.chart{{display:flex;align-items:flex-end;gap:6px;height:90px;border-bottom:1px solid #ccc}} .bar{{flex:1;background:{color};opacity:.85}}
@media print{{body{{padding:0}}}}
</style></head><body>
<header><div><h1>{esc(seat["client_label"])}</h1>
<span class="muted">{esc(seat.get("constituency") or "")} · {esc(period)} · {generated_at:%d %b %Y}</span></div>
{logo_html}</header>
<div class="kpis">
<div class="kpi"><b>{summary["total"]}</b>Grievances received</div>
<div class="kpi"><b>{_pct(summary["resolution_rate"])}</b>Resolved</div>
<div class="kpi"><b>{summary["open"]}</b>Still open</div>
<div class="kpi"><b>{summary["critical"]}</b>Critical</div>
<div class="kpi"><b>{"—" if avg is None else f"{avg}d"}</b>Avg. time to resolve</div>
</div>
<h2>Grievances received, by {esc(unit)}</h2><div class="chart">{bars}</div>
<h2>Top issue categories</h2><table>{_rows_html(summary["top_categories"])}</table>
<h2>Where complaints come from</h2><table>{_rows_html(summary["top_locations"])}</table>
<p class="muted" style="margin-top:32px">Prepared by {esc(partner["brand_name"])}. Aggregate figures only; no citizen details are included.</p>
{powered}
</body></html>"""


# ─────────────────────────────────────────
# ATTRIBUTION (backend is the source of truth)
# ─────────────────────────────────────────
REASON_MIN_LEN = 5
REASON_MAX_LEN = 500


class AttributionError(Exception):
    """Validation / conflict raised by attribution services. Routes map it to an HTTP error."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _admin_identity(admin_user) -> tuple[str | None, int | None]:
    if isinstance(admin_user, dict):
        uid = admin_user.get("id")
        return admin_user.get("username"), uid if isinstance(uid, int) else None
    return (str(admin_user) if admin_user else None), None


def _lock_active_partner(db, partner_id) -> "PartnerOrg":
    """Fetch a partner for NEW attribution. Row-locked (PostgreSQL) so a concurrent
    deactivation cannot slip a tenant in after the active check."""
    if not isinstance(partner_id, int) or isinstance(partner_id, bool):
        raise AttributionError(400, "Select a partner for partner/consultancy acquisition.")
    partner = db.query(PartnerOrg).filter(PartnerOrg.id == partner_id).with_for_update().first()
    if not partner:
        raise AttributionError(400, "Selected partner does not exist.")
    if not partner.is_active:
        raise AttributionError(400, "Selected partner is inactive and cannot receive new tenants.")
    return partner


def _new_seat(partner: "PartnerOrg", tenant) -> "PartnerSeat":
    seat_type = tenant.seat_type if tenant.seat_type in SEAT_TYPES else "mp"
    return PartnerSeat(
        partner_id=partner.id, tenant_id=tenant.id, client_label=tenant.name,
        constituency=tenant.constituency, seat_type=seat_type,
        status="active", activated_at=datetime.utcnow(),
    )


def attribute_new_tenant(db, tenant, channel: str | None, partner_id, admin_user) -> dict:
    """Record acquisition for a tenant created in the SAME session/transaction.

    Does not commit: the caller commits tenant + user + profile + attribution + seat
    together, so a failure anywhere rolls the whole onboarding back.
    """
    channel = (channel or CHANNEL_DIRECT).strip().lower()
    by, by_id = _admin_identity(admin_user)
    if channel not in (CHANNEL_DIRECT, CHANNEL_PARTNER):
        raise AttributionError(400, "acquisition_channel must be 'direct' or 'partner'.")
    if channel == CHANNEL_DIRECT:
        if partner_id not in (None, 0):
            raise AttributionError(400, "A partner can only be set when the acquisition channel is 'partner'.")
        partner = None
    else:
        partner = _lock_active_partner(db, partner_id)

    db.add(TenantAttribution(
        tenant_id=tenant.id, channel=channel, partner_id=partner.id if partner else None,
        attributed_by=by, attributed_by_user_id=by_id,
    ))
    seat = None
    if partner:
        seat = _new_seat(partner, tenant)
        db.add(seat)
    db.add(TenantAttributionEvent(
        tenant_id=tenant.id, event="onboarded", from_channel=None, from_partner_id=None,
        to_channel=channel, to_partner_id=partner.id if partner else None,
        changed_by=by, changed_by_user_id=by_id,
    ))
    db.flush()  # surface uniqueness violations inside the caller's transaction
    return {"channel": channel, "partner_id": partner.id if partner else None, "seat_id": seat.id if seat else None}


def reassign_tenant(db, tenant_id: int, to_partner_id, reason: str, admin_user) -> dict:
    """Move a tenant's acquisition to another active partner, or to direct (to_partner_id=None).

    One transaction (caller commits): old seat is revoked and detached BEFORE the new
    seat is created, so the tenant never has two partner associations, and the previous
    partner loses access at the same commit that grants the new one.
    """
    from sansadx_backend.db import Tenant

    reason = (reason or "").strip()
    if len(reason) < REASON_MIN_LEN:
        raise AttributionError(400, f"A reason of at least {REASON_MIN_LEN} characters is required.")
    if len(reason) > REASON_MAX_LEN:
        raise AttributionError(400, f"Reason must be at most {REASON_MAX_LEN} characters.")
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise AttributionError(404, "Tenant not found.")
    by, by_id = _admin_identity(admin_user)

    attribution = db.query(TenantAttribution).filter(TenantAttribution.tenant_id == tenant_id).with_for_update().first()
    seat = db.query(PartnerSeat).filter(PartnerSeat.tenant_id == tenant_id).with_for_update().first()
    from_partner_id = None
    if attribution and attribution.channel == CHANNEL_PARTNER:
        from_partner_id = attribution.partner_id
    elif seat and seat.status in PORTFOLIO_STATUSES:
        from_partner_id = seat.partner_id
    from_channel = CHANNEL_PARTNER if from_partner_id else CHANNEL_DIRECT

    if to_partner_id is None:
        to_channel, partner = CHANNEL_DIRECT, None
    else:
        to_channel, partner = CHANNEL_PARTNER, _lock_active_partner(db, to_partner_id)
    if (partner.id if partner else None) == from_partner_id:
        raise AttributionError(409, "Tenant is already attributed to this destination.")

    if seat:  # detach the previous association first (unique tenant_id)
        seat.status = "revoked"
        seat.tenant_id = None
        db.flush()
    new_seat = None
    if partner:
        new_seat = _new_seat(partner, tenant)
        db.add(new_seat)
    if attribution:
        attribution.channel = to_channel
        attribution.partner_id = partner.id if partner else None
        attribution.attributed_at = datetime.utcnow()
        attribution.attributed_by = by
        attribution.attributed_by_user_id = by_id
    else:
        db.add(TenantAttribution(
            tenant_id=tenant_id, channel=to_channel, partner_id=partner.id if partner else None,
            attributed_by=by, attributed_by_user_id=by_id,
        ))
    db.add(TenantAttributionEvent(
        tenant_id=tenant_id, event="reassigned", from_channel=from_channel, from_partner_id=from_partner_id,
        to_channel=to_channel, to_partner_id=partner.id if partner else None, reason=reason,
        changed_by=by, changed_by_user_id=by_id,
    ))
    db.flush()
    return {
        "from_channel": from_channel, "from_partner_id": from_partner_id,
        "to_channel": to_channel, "to_partner_id": partner.id if partner else None,
        "seat_id": new_seat.id if new_seat else None,
    }


def link_legacy_request(db, seat: "PartnerSeat", tenant, admin_user) -> None:
    """Admin resolves a LEGACY partner seat request by linking it to a tenant.

    Goes through the same single-association rule as onboarding: a tenant that already
    belongs to a partner cannot be linked again. Caller commits.
    """
    by, by_id = _admin_identity(admin_user)
    attribution = db.query(TenantAttribution).filter(TenantAttribution.tenant_id == tenant.id).with_for_update().first()
    other = db.query(PartnerSeat).filter(PartnerSeat.tenant_id == tenant.id, PartnerSeat.id != seat.id).first()
    if other or (attribution and attribution.channel == CHANNEL_PARTNER):
        raise AttributionError(409, "Tenant is already attributed to a partner.")
    from_channel = attribution.channel if attribution else None
    seat.tenant_id = tenant.id
    seat.status = "active"
    seat.activated_at = datetime.utcnow()
    if attribution:
        attribution.channel, attribution.partner_id = CHANNEL_PARTNER, seat.partner_id
        attribution.attributed_at, attribution.attributed_by, attribution.attributed_by_user_id = datetime.utcnow(), by, by_id
    else:
        db.add(TenantAttribution(tenant_id=tenant.id, channel=CHANNEL_PARTNER, partner_id=seat.partner_id,
                                 attributed_by=by, attributed_by_user_id=by_id))
    db.add(TenantAttributionEvent(
        tenant_id=tenant.id, event="legacy_request_activated", from_channel=from_channel, from_partner_id=None,
        to_channel=CHANNEL_PARTNER, to_partner_id=seat.partner_id, reason="Legacy partner seat request linked by Needle staff",
        changed_by=by, changed_by_user_id=by_id,
    ))
    db.flush()


def get_tenant_attribution(db, tenant_id: int) -> dict:
    """Staff-facing acquisition info for a tenant. Never include this in tenant-facing responses."""
    row = db.query(TenantAttribution).filter(TenantAttribution.tenant_id == tenant_id).first()
    if not row:
        return {"recorded": False, "channel": CHANNEL_DIRECT, "partner_id": None, "partner_name": None,
                "attributed_at": None, "attributed_by": None, "access_status": None}
    partner = db.query(PartnerOrg).filter(PartnerOrg.id == row.partner_id).first() if row.partner_id else None
    seat = (db.query(PartnerSeat).filter(PartnerSeat.tenant_id == tenant_id).first()
            if row.channel == CHANNEL_PARTNER else None)
    return {
        "recorded": True, "channel": row.channel, "partner_id": row.partner_id,
        "partner_name": partner.name if partner else None,
        "attributed_at": row.attributed_at.isoformat() if row.attributed_at else None,
        "attributed_by": row.attributed_by,
        "access_status": seat.status if seat else None,  # active | paused (pausing never changes attribution)
    }


def list_attribution_events(db, tenant_id: int) -> list[dict]:
    rows = (db.query(TenantAttributionEvent).filter(TenantAttributionEvent.tenant_id == tenant_id)
            .order_by(TenantAttributionEvent.id.desc()).all())
    return [{
        "id": e.id, "event": e.event, "from_channel": e.from_channel, "from_partner_id": e.from_partner_id,
        "to_channel": e.to_channel, "to_partner_id": e.to_partner_id, "reason": e.reason,
        "changed_by": e.changed_by, "created_at": e.created_at.isoformat() if e.created_at else None,
    } for e in rows]


# ─────────────────────────────────────────
# BILLING (manual invoicing; this only computes the number)
# ─────────────────────────────────────────
def billing_summary(db, partner: "PartnerOrg") -> dict:
    """Wholesale is per ACTIVE partner-client association. Paused clients are not billed."""
    active = db.query(PartnerSeat).filter(
        PartnerSeat.partner_id == partner.id, PartnerSeat.status == "active", PartnerSeat.tenant_id.isnot(None),
    ).count()
    price = int(partner.wholesale_price_inr or 0)
    return {"billable_clients": active, "wholesale_price_inr": price, "monthly_wholesale_inr": active * price}


# ─────────────────────────────────────────
# MIGRATION (idempotent; called from startup under the migration lock)
# ─────────────────────────────────────────
# ─────────────────────────────────────────
# SCHEMA MIGRATION (expand / contract) + STARTUP GATE
# ─────────────────────────────────────────
# Phase 1 (this release, runs at startup): create the attribution tables, backfill, and STOP
# depending on partners.seat_cap — but leave the column in place so instances still running the
# previous release keep working during a rolling deploy.
# Phase 2 (later, manual): scripts/partner_drop_seat_cap.py drops the column once every instance
# runs this release or newer. See PARTNER_CHANNEL.md ("Deploying").
SCHEMA_LOCK_KEY = 77772024          # same advisory lock main.py holds for every startup migration
LEGACY_SEAT_CAP_DEFAULT = 2147483647  # keeps partners created during the overlap usable by old code

_PARTNER_TABLES = ("partners", "partner_users", "partner_seats", "tenant_attributions", "tenant_attribution_events")


class PartnerMigrationError(RuntimeError):
    """A genuine partner-schema failure (never raised for a benign concurrent-backfill race)."""


def _engine(engine=None):
    import sansadx_backend.db as dbmod
    return engine or dbmod.engine


def _session_factory():
    import sansadx_backend.db as dbmod
    return dbmod.SessionLocal


def partner_schema_status(engine=None) -> dict:
    """Read-only readiness check: tables exist and every active/paused seat has an attribution row."""
    from sqlalchemy import inspect as sa_inspect, text
    engine = _engine(engine)
    problems: list[str] = []
    try:
        insp = sa_inspect(engine)
        missing = [t for t in _PARTNER_TABLES if not insp.has_table(t)]
        if missing:
            problems.append("missing tables: " + ", ".join(missing))
        else:
            with engine.connect() as conn:
                unattributed = conn.execute(text(
                    "SELECT COUNT(*) FROM partner_seats s WHERE s.tenant_id IS NOT NULL "
                    "AND s.status IN ('active','paused') "
                    "AND NOT EXISTS (SELECT 1 FROM tenant_attributions a WHERE a.tenant_id = s.tenant_id)"
                )).scalar()
            if unattributed:
                problems.append(f"{unattributed} partner seat(s) have no attribution record")
    except Exception as exc:  # database unreachable etc.
        problems.append(f"status check failed: {type(exc).__name__}")
        logger.warning("Partner schema status check failed: %s", exc)
    return {"ready": not problems, "problems": problems}


def ensure_partner_schema(engine=None) -> dict:
    """Phase-1 (expand) migration: create/upgrade partner tables and backfill attribution.

    Idempotent and retry-safe. The caller is responsible for holding the startup migration lock
    on PostgreSQL (see `startup_partner_migration`). Raises PartnerMigrationError on any genuine
    failure; a concurrent backfill that loses a uniqueness race is benign and retried once."""
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    engine = _engine(engine)
    try:
        Base.metadata.create_all(bind=engine, tables=[
            PartnerOrg.__table__, PartnerUser.__table__, PartnerSeat.__table__,
            TenantAttribution.__table__, TenantAttributionEvent.__table__,
        ])
        legacy_cap_column = False
        if engine.dialect.name == "postgresql":
            with engine.begin() as conn:
                legacy_cap_column = bool(conn.execute(text(
                    "SELECT 1 FROM information_schema.columns WHERE table_name='partners' AND column_name='seat_cap'"
                )).first())
                if legacy_cap_column:
                    # Expand only: nothing reads or writes seat_cap any more. A default keeps rows inserted by
                    # this release non-NULL for any not-yet-upgraded instance. The column itself is dropped in phase 2.
                    conn.execute(text(f"ALTER TABLE partners ALTER COLUMN seat_cap SET DEFAULT {LEGACY_SEAT_CAP_DEFAULT}"))

        backfilled = 0
        for attempt in (1, 2):
            db = _session_factory()()
            try:
                have = {row[0] for row in db.query(TenantAttribution.tenant_id).all()}
                seats = db.query(PartnerSeat).filter(
                    PartnerSeat.tenant_id.isnot(None), PartnerSeat.status.in_(PORTFOLIO_STATUSES)).all()
                added = 0
                for seat in seats:
                    if seat.tenant_id in have:
                        continue
                    when = seat.activated_at or seat.created_at or datetime.utcnow()
                    db.add(TenantAttribution(tenant_id=seat.tenant_id, channel=CHANNEL_PARTNER, partner_id=seat.partner_id,
                                             attributed_at=when, attributed_by="migration"))
                    db.add(TenantAttributionEvent(tenant_id=seat.tenant_id, event="migrated", to_channel=CHANNEL_PARTNER,
                                                  to_partner_id=seat.partner_id, reason="Backfilled from existing partner seat",
                                                  changed_by="migration"))
                    added += 1
                db.commit()
                backfilled += added
                break
            except IntegrityError:  # another process backfilled the same tenant; re-read and finish on the retry
                db.rollback()
                if attempt == 2:
                    raise
            finally:
                db.close()
    except Exception as exc:
        raise PartnerMigrationError(f"{type(exc).__name__}: {exc}") from exc

    status = partner_schema_status(engine)
    if not status["ready"]:
        raise PartnerMigrationError("schema still incomplete after migration: " + "; ".join(status["problems"]))
    if backfilled or legacy_cap_column:
        logger.info("Partner schema: backfilled %d attribution row(s); legacy seat_cap column retained=%s",
                    backfilled, legacy_cap_column)
    return {"backfilled": backfilled, "legacy_seat_cap_column": legacy_cap_column}


def contract_seat_cap(engine=None, execute: bool = False) -> dict:
    """Phase-2 (contract): drop the retired partners.seat_cap column. PostgreSQL only; dry-run by default.

    Takes the startup migration lock so it cannot overlap a booting instance, and refuses unless the
    phase-1 schema is complete. Only run after EVERY instance runs a release that no longer uses seat_cap."""
    from sqlalchemy import text
    engine = _engine(engine)
    result = {"dialect": engine.dialect.name, "column_present": False, "dropped": False, "executed": execute}
    if engine.dialect.name != "postgresql":
        return result
    status = partner_schema_status(engine)
    if not status["ready"]:
        raise PartnerMigrationError("refusing to drop seat_cap: phase-1 schema is incomplete: " + "; ".join(status["problems"]))
    with engine.connect() as conn:
        result["column_present"] = bool(conn.execute(text(
            "SELECT 1 FROM information_schema.columns WHERE table_name='partners' AND column_name='seat_cap'")).first())
    if not (execute and result["column_present"]):
        return result
    lock_conn = engine.connect()
    try:
        if not lock_conn.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": SCHEMA_LOCK_KEY}).scalar():
            raise PartnerMigrationError("another instance holds the startup migration lock; retry in a minute")
        with engine.begin() as conn:
            conn.execute(text("SET LOCAL lock_timeout = '5s'"))
            conn.execute(text("ALTER TABLE partners DROP COLUMN IF EXISTS seat_cap"))
        result["dropped"] = True
    finally:
        try:
            lock_conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": SCHEMA_LOCK_KEY})
        finally:
            lock_conn.close()
    return result


class PartnerSchemaGate:
    """Process-wide readiness of the partner schema. state: pending | ready | failed."""

    def __init__(self):
        self.state = "pending"
        self.detail = "partner schema migration has not run yet"
        self.attempts = 0
        self._thread = None

    @property
    def ready(self) -> bool:
        return self.state == "ready"

    def set_ready(self):
        self.state, self.detail = "ready", ""

    def set_failed(self, detail: str):
        self.state, self.detail = "failed", detail

    def set_waiting(self, detail: str):
        self.state, self.detail = "pending", detail


SCHEMA_GATE = PartnerSchemaGate()


def _try_acquire_lock(engine):
    """Take the startup migration lock on a dedicated connection. Returns (conn, got). SQLite: always (None, True)."""
    from sqlalchemy import text
    if engine.dialect.name != "postgresql":
        return None, True
    conn = engine.connect()
    try:
        got = bool(conn.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": SCHEMA_LOCK_KEY}).scalar())
    except Exception:
        conn.close()
        raise
    if not got:
        conn.close()
        return None, False
    return conn, True


def _release_lock(conn):
    from sqlalchemy import text
    if conn is None:
        return
    try:
        conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": SCHEMA_LOCK_KEY})
    except Exception as exc:  # the lock also dies with the connection
        logger.warning("Could not release partner migration lock cleanly: %s", exc)
    finally:
        conn.close()


def _migrate_under_lock(engine, gate: PartnerSchemaGate, holds_lock: bool = False) -> None:
    """One attempt: only runs the migration if THIS process holds the lock (`holds_lock` = the caller already
    took it on its own connection, as main.py does for the whole startup sequence). Updates the gate; never raises."""
    gate.attempts += 1
    try:
        conn, got = (None, True) if holds_lock else _try_acquire_lock(engine)
    except Exception as exc:
        gate.set_failed(f"cannot reach the database to take the migration lock ({type(exc).__name__})")
        logger.critical("Partner schema: %s", gate.detail)
        return
    if not got:
        status = partner_schema_status(engine)
        if status["ready"]:
            gate.set_ready()
        else:
            gate.set_waiting("waiting for the instance holding the migration lock to finish partner migration")
            logger.warning("Partner schema: lock held elsewhere and schema not ready (%s); waiting, NOT migrating from this instance",
                           "; ".join(status["problems"]))
        return
    try:
        ensure_partner_schema(engine)
        gate.set_ready()
        logger.info("Partner schema ready (attempt %d)", gate.attempts)
    except PartnerMigrationError as exc:
        gate.set_failed(str(exc))
        logger.critical(
            "PARTNER SCHEMA MIGRATION FAILED — partner, attribution and onboarding endpoints are disabled and /health reports 503. "
            "Cause: %s. Fix the cause (database permissions/connectivity, conflicting data) and the instance retries automatically; "
            "the migration is idempotent so a manual restart is also safe.", exc)
    finally:
        _release_lock(conn)


def startup_partner_migration(engine=None, gate: PartnerSchemaGate | None = None, start_retry_thread: bool = True,
                              retry_seconds: float | None = None, holds_lock: bool = False) -> PartnerSchemaGate:
    """Called once at import time from main.py after init_db(). Never raises; the gate reports the outcome.

    On PostgreSQL ONLY the instance that holds advisory lock 77772024 runs the migration. An instance that
    cannot take the lock does not migrate: it reports not-ready until the schema is complete, and a
    background retry takes over the migration if the lock frees up before anyone finished it.
    `holds_lock=True` means the caller (main.py) already holds the lock on its own session."""
    import threading
    import time

    engine = _engine(engine)
    gate = gate or SCHEMA_GATE
    _migrate_under_lock(engine, gate, holds_lock=holds_lock)
    if gate.ready or not start_retry_thread:
        return gate
    if gate._thread and gate._thread.is_alive():
        return gate
    interval = retry_seconds if retry_seconds is not None else float(os.getenv("PARTNER_SCHEMA_RETRY_SECONDS", "10"))

    def _retry_loop():
        while not gate.ready:
            time.sleep(interval)
            _migrate_under_lock(engine, gate)

    gate._thread = threading.Thread(target=_retry_loop, name="partner-schema-retry", daemon=True)
    gate._thread.start()
    return gate
