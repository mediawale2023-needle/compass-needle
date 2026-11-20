"""
Partner layer — political consultancies that resell Needle seats to their clients.

A *partner* is a consultancy. It owns many *seats*; each seat is one client
(an aspirant / MLA / MP tenant). Partners never get case-level or citizen-level
data: they see aggregate metrics and a white-labelled report per client.

Isolation rules (do not weaken):
  * Tenant ids are ONLY ever derived from `partner_seats` rows owned by the
    authenticated partner — never from request input.
  * Partner JWTs are signed with a key derived from JWT_SECRET, so they fail
    signature checks on every MP/admin endpoint (and vice versa).
  * No citizen phone numbers, raw messages or names leave this module.

Schema is additive: three new tables, no changes to existing tables.
"""
import hashlib
import hmac
import html
import os
import re
from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint,
)

from sansadx_backend.db import Base
from core.db_helpers import _q

SEAT_TYPES = ("mp", "mla")
SEAT_ACTIVE_STATUSES = ("requested", "active")  # count against seat_cap
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
    seat_cap = Column(Integer, default=5)
    wholesale_price_inr = Column(Integer, default=0)  # per seat / month, billed manually
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
    status = Column(String, default="requested")  # requested | active | paused | rejected
    created_at = Column(DateTime, default=datetime.utcnow)
    activated_at = Column(DateTime, nullable=True)


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
