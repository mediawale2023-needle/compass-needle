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
from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint,
)

from sansadx_backend.db import Base
from core.db_helpers import _q

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


def _fetch_case_rows(tenant_id: int, since: datetime) -> list[dict]:
    # Columns are aggregate-safe only: no phone, no raw message.
    return _q(
        "SELECT status, category, ward, assembly, is_critical, created_at, resolved_at "
        "FROM cases WHERE tenant_id = :tid AND COALESCE(is_deleted, FALSE) = FALSE "
        "AND created_at >= :since",
        {"tid": int(tenant_id), "since": since},
    )


def summarize_cases(rows: list[dict], days: int, now: datetime | None = None) -> dict:
    now = now or datetime.utcnow()
    window_start = now - timedelta(days=days)
    in_window = []
    for r in rows:
        created = _as_dt(r.get("created_at"))
        if created and created >= window_start:
            in_window.append({**r, "_created": created})

    def is_resolved(r) -> bool:
        return str(r.get("status") or "").lower() in RESOLVED_STATUSES

    total = len(in_window)
    resolved = [r for r in in_window if is_resolved(r)]
    critical = sum(1 for r in in_window if r.get("is_critical"))

    durations = []
    for r in resolved:
        done = _as_dt(r.get("resolved_at"))
        if done:
            durations.append(max((done - r["_created"]).total_seconds() / 86400, 0))

    categories = Counter((r.get("category") or "Uncategorised") for r in in_window)
    places = Counter((r.get("ward") or r.get("assembly") or "Unmapped") for r in in_window)

    weekly = []
    for i in range(7, -1, -1):  # 8 weeks, oldest first
        end = now - timedelta(days=7 * i)
        start = end - timedelta(days=7)
        received = resolved_n = 0
        for r in rows:
            created = _as_dt(r.get("created_at"))
            if created and start < created <= end:
                received += 1
                if is_resolved(r):
                    resolved_n += 1
        weekly.append({"week_ending": end.date().isoformat(), "received": received, "resolved": resolved_n})

    return {
        "days": days,
        "total": total,
        "resolved": len(resolved),
        "open": total - len(resolved),
        "critical": critical,
        "resolution_rate": round(len(resolved) / total, 3) if total else None,
        "avg_resolution_days": round(sum(durations) / len(durations), 1) if durations else None,
        "top_categories": [{"name": k, "count": v} for k, v in categories.most_common(5)],
        "top_locations": [{"name": k, "count": v} for k, v in places.most_common(5)],
        "weekly": weekly,
    }


def tenant_summary(tenant_id: int, days: int = 30, now: datetime | None = None) -> dict:
    now = now or datetime.utcnow()
    horizon = max(days, 56)  # 56 days feeds the 8-week trend
    rows = _fetch_case_rows(tenant_id, now - timedelta(days=horizon))
    return summarize_cases(rows, days, now)


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
    weekly_max = max([w["received"] for w in summary["weekly"]] + [1])
    bars = "".join(
        f'<div class="bar" title="{esc(w["week_ending"])}: {w["received"]} received" '
        f'style="height:{max(round(w["received"] / weekly_max * 100), 2)}%"></div>'
        for w in summary["weekly"]
    )
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
<span class="muted">{esc(seat.get("constituency") or "")} · last {summary["days"]} days · {generated_at:%d %b %Y}</span></div>
{logo_html}</header>
<div class="kpis">
<div class="kpi"><b>{summary["total"]}</b>Grievances received</div>
<div class="kpi"><b>{_pct(summary["resolution_rate"])}</b>Resolved</div>
<div class="kpi"><b>{summary["open"]}</b>Still open</div>
<div class="kpi"><b>{summary["critical"]}</b>Critical</div>
<div class="kpi"><b>{"—" if avg is None else f"{avg}d"}</b>Avg. time to resolve</div>
</div>
<h2>Weekly volume (last 8 weeks)</h2><div class="chart">{bars}</div>
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
