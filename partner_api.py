"""
Partner (consultancy) API.

Mounted in main.py as:
    app.include_router(partner_router, prefix="/api/partner")
    app.include_router(partner_admin_router, prefix="/api/admin/partners")

Partner-facing routes authenticate with partner-only JWTs (derived signing key,
see modules/partners.py). Admin routes reuse the existing admin auth.
"""
import logging
import re
from datetime import date, datetime, timedelta, timezone

import bcrypt
import jwt
from jwt.exceptions import PyJWTError as JWTError
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

import api_router
import sansadx_backend.db as dbmod
from sansadx_backend.db import Tenant, validate_password
from admin_api import (
    _audit, generate_temporary_password, get_admin_user, hash_password, require_super_admin, verify_password,
)
from modules.dashboard_overview import build_partner_overview
from modules.partners import (
    AttributionError, PORTFOLIO_STATUSES, PartnerOrg, PartnerSeat, PartnerUser,
    billing_summary, clean_color, clean_logo_url, get_tenant_attribution, link_legacy_request,
    list_attribution_events, make_slug, partner_jwt_key, reassign_tenant, render_client_report, tenant_summary,
    MAX_WINDOW_DAYS, ReportWindow, WindowError, bucket_days_for, first_case_at, resolve_window,
)

try:
    from core.rate_limiter import limiter, RATE_LOGIN
    _limit_login = limiter.limit(RATE_LOGIN)
except Exception:  # pragma: no cover
    def _limit_login(f):
        return f

try:
    from core.security_logger import log_security_event
except ImportError:  # pragma: no cover
    log_security_event = None

logger = logging.getLogger("needle.partner")

router = APIRouter()
admin_router = APIRouter()

JWT_ALGORITHM = "HS256"
PARTNER_TOKEN_HOURS = 8
_bearer = HTTPBearer()
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Compared against when the email is unknown so login timing does not reveal valid emails.
_DUMMY_HASH = bcrypt.hashpw(b"not-a-real-password", bcrypt.gensalt()).decode()


def _now_ts() -> float:
    return datetime.now(timezone.utc).timestamp()


def _as_ts(value: datetime | None) -> float:
    if value is None:
        return 0.0
    return value.replace(tzinfo=timezone.utc).timestamp()


def _create_partner_token(user: PartnerUser) -> str:
    payload = {
        "sub": str(user.id),
        "typ": "partner",
        "pid": user.partner_id,
        "iat": _now_ts(),
        "exp": datetime.now(timezone.utc) + timedelta(hours=PARTNER_TOKEN_HOURS),
    }
    return jwt.encode(payload, partner_jwt_key(), algorithm=JWT_ALGORITHM)


def _brand_dict(p: PartnerOrg) -> dict:
    return {
        "id": p.id, "name": p.name, "slug": p.slug, "brand_name": p.brand_name,
        "brand_color": clean_color(p.brand_color), "brand_logo_url": p.brand_logo_url,
        "show_powered_by": bool(p.show_powered_by),
    }


def _seat_dict(s: PartnerSeat) -> dict:
    return {
        "id": s.id, "client_label": s.client_label, "constituency": s.constituency,
        "seat_type": s.seat_type, "status": s.status, "notes": s.notes,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "activated_at": s.activated_at.isoformat() if s.activated_at else None,
    }


# ─────────────────────────────────────────
# AUTH DEPENDENCIES
# ─────────────────────────────────────────
def _resolve_partner_user(credentials: HTTPAuthorizationCredentials, allow_pending_password: bool) -> dict:
    try:
        payload = jwt.decode(credentials.credentials, partner_jwt_key(), algorithms=[JWT_ALGORITHM])
        user_id = int(payload.get("sub"))
    except (JWTError, TypeError, ValueError):
        raise HTTPException(401, "Invalid or expired token")
    if payload.get("typ") != "partner":
        raise HTTPException(401, "Invalid or expired token")

    db = dbmod.SessionLocal()
    try:
        user = db.query(PartnerUser).filter(PartnerUser.id == user_id).first()
        partner = db.query(PartnerOrg).filter(PartnerOrg.id == user.partner_id).first() if user else None
        if not user or not partner or not user.is_active or not partner.is_active:
            raise HTTPException(401, "Invalid or expired token")
        if payload.get("iat", 0) < _as_ts(user.password_changed_at):
            raise HTTPException(401, "Token has been revoked. Please login again.")
        if user.must_change_password and not allow_pending_password:
            raise HTTPException(403, "Password change required")
        return {
            "user_id": user.id, "partner_id": partner.id, "email": user.email,
            "display_name": user.display_name, "must_change_password": bool(user.must_change_password),
            "partner": _brand_dict(partner),
        }
    finally:
        db.close()


def get_partner_user(credentials: HTTPAuthorizationCredentials = Depends(_bearer)) -> dict:
    return _resolve_partner_user(credentials, allow_pending_password=False)


def get_partner_user_pending_ok(credentials: HTTPAuthorizationCredentials = Depends(_bearer)) -> dict:
    return _resolve_partner_user(credentials, allow_pending_password=True)


# ─────────────────────────────────────────
# PARTNER: AUTH
# ─────────────────────────────────────────
class PartnerLoginRequest(BaseModel):
    email: str = Field(max_length=200)
    password: str = Field(max_length=200)


class PartnerChangePasswordRequest(BaseModel):
    current_password: str = Field(max_length=200)
    new_password: str = Field(max_length=200)


@router.post("/auth/login")
@_limit_login
def partner_login(req: PartnerLoginRequest, request: Request):
    email = req.email.strip().lower()
    db = dbmod.SessionLocal()
    try:
        user = db.query(PartnerUser).filter(PartnerUser.email == email).first()
        partner = db.query(PartnerOrg).filter(PartnerOrg.id == user.partner_id).first() if user else None
        stored = user.password_hash if user else _DUMMY_HASH
        ok = verify_password(req.password, stored)
        if not (user and partner and ok and user.is_active and partner.is_active):
            if log_security_event:
                log_security_event("auth_failed", f"Partner login failed for '{email}'", severity="medium",
                                   user_id=email, ip_address=request.client.host if request.client else None)
            raise HTTPException(401, "Invalid credentials")
        return {
            "token": _create_partner_token(user),
            "must_change_password": bool(user.must_change_password),
            "partner": _brand_dict(partner),
        }
    finally:
        db.close()


@router.post("/auth/change-password")
def partner_change_password(req: PartnerChangePasswordRequest, me: dict = Depends(get_partner_user_pending_ok)):
    err = validate_password(req.new_password)
    if err:
        raise HTTPException(400, err)
    db = dbmod.SessionLocal()
    try:
        user = db.query(PartnerUser).filter(PartnerUser.id == me["user_id"]).first()
        if not user or not verify_password(req.current_password, user.password_hash):
            raise HTTPException(401, "Current password is incorrect")
        user.password_hash = hash_password(req.new_password)
        user.must_change_password = False
        user.password_changed_at = datetime.utcnow()
        db.commit()
        return {"success": True, "token": _create_partner_token(user)}
    finally:
        db.close()


@router.get("/me")
def partner_me(me: dict = Depends(get_partner_user)):
    return {k: me[k] for k in ("email", "display_name", "partner")}


# ─────────────────────────────────────────
# PARTNER: CLIENTS
# ─────────────────────────────────────────
_HEADLINE_KEYS = ("total", "resolved", "open", "critical", "resolution_rate", "avg_resolution_days")


def _owned_seat(db, partner_id: int, seat_id: int, require_active: bool = True) -> PartnerSeat:
    """The ONLY way partner routes resolve a seat: scoped by partner_id."""
    seat = db.query(PartnerSeat).filter(PartnerSeat.id == seat_id, PartnerSeat.partner_id == partner_id).first()
    # Revoked (reassigned-away) and legacy request rows are invisible to the partner: 404, not 409.
    if not seat or seat.status not in PORTFOLIO_STATUSES:
        raise HTTPException(404, "Client not found")
    if require_active and (seat.status != "active" or not seat.tenant_id):
        raise HTTPException(409, "Access to this client is paused")
    return seat


def report_window(
    days: int | None = Query(None, ge=1, le=MAX_WINDOW_DAYS, description="Last N days, ending now"),
    range_: str | None = Query(None, alias="range", pattern="^all$", description="'all' = complete history"),
    from_: date | None = Query(None, alias="from", description="Custom range start (inclusive, YYYY-MM-DD)"),
    to: date | None = Query(None, description="Custom range end (inclusive, YYYY-MM-DD)"),
) -> ReportWindow:
    """The period a partner metric covers. Defaults to the last 30 days; never unbounded rows (SQL aggregates)."""
    try:
        return resolve_window(days=days, range_=range_, from_=from_, to=to)
    except WindowError as exc:
        raise HTTPException(422, str(exc))


@router.get("/clients")
def partner_clients(window: ReportWindow = Depends(report_window), me: dict = Depends(get_partner_user)):
    db = dbmod.SessionLocal()
    try:
        # Portfolio = active + paused attributed clients only. Legacy requested/rejected rows
        # and revoked (reassigned-away) rows are never shown to the partner.
        seats = (db.query(PartnerSeat)
                 .filter(PartnerSeat.partner_id == me["partner_id"], PartnerSeat.status.in_(PORTFOLIO_STATUSES))
                 .order_by(PartnerSeat.id).all())
        live = [s for s in seats if s.status == "active" and s.tenant_id]
        # One shared window (all time = from the earliest case across this partner's clients) so every
        # client's trend uses identical buckets and the portfolio trend is a straight sum.
        if window.start is None:
            window = window.bounded(first_case_at([s.tenant_id for s in live]))
        clients, totals = [], {k: 0 for k in ("total", "resolved", "open", "critical")}
        trend: list[dict] | None = None
        for seat in seats:
            item = _seat_dict(seat)
            item["summary"] = None
            if seat in live:
                full = tenant_summary(seat.tenant_id, window)
                item["summary"] = {k: full[k] for k in _HEADLINE_KEYS}
                item["summary"]["trend"] = full["trend"]
                for k in totals:
                    totals[k] += full[k]
                if trend is None:
                    trend = [{**b, "received": 0, "resolved": 0} for b in full["trend"]]
                for agg, b in zip(trend, full["trend"]):
                    agg["received"] += b["received"]
                    agg["resolved"] += b["resolved"]
            clients.append(item)
        totals["trend"] = trend or []
        totals["bucket_days"] = bucket_days_for(window.span_days)
        return {
            "window": window.describe(), "days": window.describe()["days"],
            "active_clients": len(live), "portfolio": totals, "clients": clients,
        }
    finally:
        db.close()


@router.get("/clients/{seat_id}/summary")
def partner_client_summary(seat_id: int, window: ReportWindow = Depends(report_window), me: dict = Depends(get_partner_user)):
    db = dbmod.SessionLocal()
    try:
        seat = _owned_seat(db, me["partner_id"], seat_id)
        return {"client": _seat_dict(seat), "summary": tenant_summary(seat.tenant_id, window)}
    finally:
        db.close()


@router.get("/clients/{seat_id}/dashboard/overview")
def partner_client_dashboard_overview(seat_id: int, me: dict = Depends(get_partner_user)):
    """Counts-only Overview for one attributed client (partner view of the MP Overview).

    The tenant comes ONLY from the partner's own seat (`_owned_seat`): foreign or revoked seats are 404, paused
    seats 409. There is no tenant parameter, and the response is built by the separate partner-mode builder
    (minimal-column queries, no case rows, no citizen data), never by the MP builder.
    """
    db = dbmod.SessionLocal()
    try:
        seat = _owned_seat(db, me["partner_id"], seat_id)
        tenant_id = seat.tenant_id
        client = _seat_dict(seat)
    finally:
        db.close()
    try:
        overview = build_partner_overview(tenant_id, api_router._overview_deps())
    except Exception:
        # Log internally; return a controlled 500. An unhandled exception escapes the CORS middleware, so the
        # browser would report an opaque "could not reach the server" instead of a status.
        logger.exception("partner overview failed seat=%s tenant=%s", seat_id, tenant_id)
        raise HTTPException(status_code=500, detail="The overview could not be built. Please try again shortly.")
    return {"client": client, "overview": overview}


@router.get("/clients/{seat_id}/report", response_class=HTMLResponse)
def partner_client_report(seat_id: int, window: ReportWindow = Depends(report_window), me: dict = Depends(get_partner_user)):
    db = dbmod.SessionLocal()
    try:
        seat = _owned_seat(db, me["partner_id"], seat_id)
        partner = db.query(PartnerOrg).filter(PartnerOrg.id == me["partner_id"]).first()
        html_doc = render_client_report(
            _brand_dict(partner), _seat_dict(seat), tenant_summary(seat.tenant_id, window)
        )
        return HTMLResponse(html_doc, headers={"Cache-Control": "no-store"})
    finally:
        db.close()


# ─────────────────────────────────────────
# ADMIN: PARTNER MANAGEMENT (Needle staff only)
# ─────────────────────────────────────────
class CreatePartnerRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    brand_name: str | None = Field(default=None, max_length=120)
    brand_color: str | None = None
    brand_logo_url: str | None = None
    show_powered_by: bool = True
    contact_email: str | None = Field(default=None, max_length=200)
    wholesale_price_inr: int = Field(default=0, ge=0, le=10_000_000)


class UpdatePartnerRequest(BaseModel):
    brand_name: str | None = Field(default=None, max_length=120)
    brand_color: str | None = None
    brand_logo_url: str | None = None
    show_powered_by: bool | None = None
    contact_email: str | None = Field(default=None, max_length=200)
    wholesale_price_inr: int | None = Field(default=None, ge=0, le=10_000_000)
    is_active: bool | None = None


class CreatePartnerUserRequest(BaseModel):
    email: str = Field(max_length=200)
    display_name: str | None = Field(default=None, max_length=120)


class ActivateSeatRequest(BaseModel):
    tenant_id: int


class SeatStatusRequest(BaseModel):
    status: str  # "active" | "paused"


def _admin_partner_dict(db, p: PartnerOrg) -> dict:
    counts = {
        status: db.query(PartnerSeat).filter(PartnerSeat.partner_id == p.id, PartnerSeat.status == status).count()
        for status in ("active", "paused", "requested")
    }
    return {**_brand_dict(p), "contact_email": p.contact_email, "wholesale_price_inr": p.wholesale_price_inr,
            "is_active": p.is_active, "clients_active": counts["active"], "clients_paused": counts["paused"],
            "legacy_requests": counts["requested"], **billing_summary(db, p),
            "users_count": db.query(PartnerUser).filter(PartnerUser.partner_id == p.id).count(),
            "created_at": p.created_at.isoformat() if p.created_at else None}


def _get_partner_or_404(db, partner_id: int) -> PartnerOrg:
    partner = db.query(PartnerOrg).filter(PartnerOrg.id == partner_id).first()
    if not partner:
        raise HTTPException(404, "Partner not found")
    return partner


@admin_router.post("")
def admin_create_partner(req: CreatePartnerRequest, admin_user=Depends(get_admin_user)):
    try:
        logo = clean_logo_url(req.brand_logo_url)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    base_slug = make_slug(req.name)
    if not base_slug:
        raise HTTPException(400, "Partner name must contain letters or digits")
    db = dbmod.SessionLocal()
    try:
        slug, n = base_slug, 1
        while db.query(PartnerOrg).filter(PartnerOrg.slug == slug).first():
            n += 1
            slug = f"{base_slug}-{n}"
        partner = PartnerOrg(
            name=req.name.strip(), slug=slug, brand_name=(req.brand_name or req.name).strip(),
            brand_color=clean_color(req.brand_color), brand_logo_url=logo,
            show_powered_by=req.show_powered_by, contact_email=req.contact_email,
            wholesale_price_inr=req.wholesale_price_inr,
        )
        db.add(partner)
        db.commit()
        _audit(admin_user, "create_partner", "partner", partner.name, f"wholesale_price_inr={partner.wholesale_price_inr}")
        return {"success": True, "partner": _admin_partner_dict(db, partner)}
    finally:
        db.close()


@admin_router.get("")
def admin_list_partners(_=Depends(get_admin_user)):
    db = dbmod.SessionLocal()
    try:
        return {"partners": [_admin_partner_dict(db, p) for p in db.query(PartnerOrg).order_by(PartnerOrg.id).all()]}
    finally:
        db.close()


@admin_router.patch("/{partner_id}")
def admin_update_partner(partner_id: int, req: UpdatePartnerRequest, admin_user=Depends(get_admin_user)):
    db = dbmod.SessionLocal()
    try:
        partner = _get_partner_or_404(db, partner_id)
        data = req.model_dump(exclude_unset=True) if hasattr(req, "model_dump") else req.dict(exclude_unset=True)
        if "brand_logo_url" in data:
            try:
                data["brand_logo_url"] = clean_logo_url(data["brand_logo_url"])
            except ValueError as exc:
                raise HTTPException(400, str(exc))
        if "brand_color" in data:
            data["brand_color"] = clean_color(data["brand_color"])
        for key, value in data.items():
            setattr(partner, key, value)
        db.commit()
        _audit(admin_user, "update_partner", "partner", partner.name, ", ".join(sorted(data)))
        return {"success": True, "partner": _admin_partner_dict(db, partner)}
    finally:
        db.close()


@admin_router.post("/{partner_id}/users")
def admin_create_partner_user(partner_id: int, req: CreatePartnerUserRequest, admin_user=Depends(get_admin_user)):
    email = req.email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(400, "Invalid email")
    db = dbmod.SessionLocal()
    try:
        partner = _get_partner_or_404(db, partner_id)
        if db.query(PartnerUser).filter(PartnerUser.email == email).first():
            raise HTTPException(400, "A partner user with this email already exists")
        temp_password = generate_temporary_password()
        db.add(PartnerUser(
            partner_id=partner.id, email=email, display_name=req.display_name,
            password_hash=hash_password(temp_password), must_change_password=True,
        ))
        db.commit()
        _audit(admin_user, "create_partner_user", "partner", partner.name, email)
        # Shown once; the user is forced to change it on first login.
        return {"success": True, "email": email, "temporary_password": temp_password}
    finally:
        db.close()


@admin_router.get("/available-tenants")
def admin_available_tenants(_=Depends(get_admin_user)):
    """Active customer accounts that are not yet linked to any partner seat (candidates for activation)."""
    from admin_api import ADMIN_ROLES
    from sansadx_backend.db import User
    db = dbmod.SessionLocal()
    try:
        linked = {row[0] for row in db.query(PartnerSeat.tenant_id).filter(PartnerSeat.tenant_id.isnot(None)).all()}
        admin_tenants = {row[0] for row in db.query(User.tenant_id).filter(User.role.in_(ADMIN_ROLES)).all()}
        customer_tenants = {row[0] for row in db.query(User.tenant_id).filter(User.role.in_(("mp", "owner"))).all()}
        rows = db.query(Tenant).filter(Tenant.is_active.is_(True)).order_by(Tenant.id).all()
        return {"tenants": [
            {"tenant_id": t.id, "name": t.name, "constituency": t.constituency,
             "account_stage": t.account_stage, "seat_type": t.seat_type}
            for t in rows if t.id in customer_tenants and t.id not in linked and t.id not in admin_tenants
        ]}
    finally:
        db.close()


@admin_router.get("/selectable")
def admin_selectable_partners(_=Depends(get_admin_user)):
    """Active partners offered in the onboarding dropdown. Inactive partners are never listed."""
    db = dbmod.SessionLocal()
    try:
        rows = db.query(PartnerOrg).filter(PartnerOrg.is_active.is_(True)).order_by(PartnerOrg.name).all()
        return {"partners": [{"id": p.id, "name": p.name} for p in rows]}
    finally:
        db.close()


class ReassignAttributionRequest(BaseModel):
    partner_id: int | None = None  # None = move the tenant to Direct (Needle)
    reason: str = Field(default="", max_length=1000)


@admin_router.get("/tenants/{tenant_id}/attribution")
def admin_get_tenant_attribution(tenant_id: int, _=Depends(get_admin_user)):
    db = dbmod.SessionLocal()
    try:
        if not db.query(Tenant).filter(Tenant.id == tenant_id).first():
            raise HTTPException(404, "Tenant not found")
        return {"attribution": get_tenant_attribution(db, tenant_id), "history": list_attribution_events(db, tenant_id)}
    finally:
        db.close()


@admin_router.post("/tenants/{tenant_id}/attribution/reassign")
def admin_reassign_tenant_attribution(tenant_id: int, req: ReassignAttributionRequest,
                                      admin_user=Depends(require_super_admin)):
    """Super-admin only. Requires a reason; audited; old partner loses access in the same commit."""
    db = dbmod.SessionLocal()
    try:
        try:
            result = reassign_tenant(db, tenant_id, req.partner_id, req.reason, admin_user)
            db.commit()
        except AttributionError as exc:
            db.rollback()
            raise HTTPException(exc.status_code, exc.message)
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "Attribution changed concurrently; reload and try again")
        _audit(admin_user, "reassign_tenant_attribution", "tenant", f"tenant_id={tenant_id}",
               f"from={result['from_channel']}:{result['from_partner_id']} to={result['to_channel']}:{result['to_partner_id']} "
               f"reason={req.reason.strip()[:200]}")
        return {"success": True, **result, "attribution": get_tenant_attribution(db, tenant_id)}
    finally:
        db.close()


def _partner_user_dict(u: PartnerUser) -> dict:
    return {"id": u.id, "email": u.email, "display_name": u.display_name, "is_active": bool(u.is_active),
            "must_change_password": bool(u.must_change_password),
            "created_at": u.created_at.isoformat() if u.created_at else None}


class SetUserActiveRequest(BaseModel):
    is_active: bool


@admin_router.get("/{partner_id}/users")
def admin_list_partner_users(partner_id: int, _=Depends(get_admin_user)):
    db = dbmod.SessionLocal()
    try:
        _get_partner_or_404(db, partner_id)
        users = db.query(PartnerUser).filter(PartnerUser.partner_id == partner_id).order_by(PartnerUser.id).all()
        return {"users": [_partner_user_dict(u) for u in users]}
    finally:
        db.close()


@admin_router.post("/{partner_id}/users/{user_id}/reset-password")
def admin_reset_partner_user_password(partner_id: int, user_id: int, admin_user=Depends(get_admin_user)):
    """Issue a new one-time temporary password. Existing sessions are revoked immediately."""
    db = dbmod.SessionLocal()
    try:
        partner = _get_partner_or_404(db, partner_id)
        user = db.query(PartnerUser).filter(PartnerUser.id == user_id, PartnerUser.partner_id == partner_id).first()
        if not user:
            raise HTTPException(404, "Partner user not found")
        temp_password = generate_temporary_password()
        user.password_hash = hash_password(temp_password)
        user.must_change_password = True
        user.password_changed_at = datetime.utcnow()
        db.commit()
        _audit(admin_user, "reset_partner_user_password", "partner", partner.name, user.email)
        return {"success": True, "email": user.email, "temporary_password": temp_password}
    finally:
        db.close()


@admin_router.post("/{partner_id}/users/{user_id}/active")
def admin_set_partner_user_active(partner_id: int, user_id: int, req: SetUserActiveRequest, admin_user=Depends(get_admin_user)):
    db = dbmod.SessionLocal()
    try:
        partner = _get_partner_or_404(db, partner_id)
        user = db.query(PartnerUser).filter(PartnerUser.id == user_id, PartnerUser.partner_id == partner_id).first()
        if not user:
            raise HTTPException(404, "Partner user not found")
        user.is_active = req.is_active
        db.commit()
        _audit(admin_user, "set_partner_user_active", "partner", partner.name, f"{user.email} -> {req.is_active}")
        return {"success": True, "user": _partner_user_dict(user)}
    finally:
        db.close()


@admin_router.get("/requests/pending")
def admin_pending_requests(_=Depends(get_admin_user)):
    db = dbmod.SessionLocal()
    try:
        rows = (db.query(PartnerSeat, PartnerOrg).join(PartnerOrg, PartnerOrg.id == PartnerSeat.partner_id)
                .filter(PartnerSeat.status == "requested").order_by(PartnerSeat.id).all())
        return {"requests": [{**_seat_dict(s), "partner_id": p.id, "partner_name": p.name} for s, p in rows]}
    finally:
        db.close()


@admin_router.get("/{partner_id}/seats")
def admin_list_seats(partner_id: int, _=Depends(get_admin_user)):
    db = dbmod.SessionLocal()
    try:
        _get_partner_or_404(db, partner_id)
        seats = db.query(PartnerSeat).filter(PartnerSeat.partner_id == partner_id).order_by(PartnerSeat.id).all()
        names = {}
        tenant_ids = [s.tenant_id for s in seats if s.tenant_id]
        if tenant_ids:
            names = {t.id: t.name for t in db.query(Tenant).filter(Tenant.id.in_(tenant_ids)).all()}
        return {"seats": [{**_seat_dict(s), "tenant_id": s.tenant_id, "tenant_name": names.get(s.tenant_id)} for s in seats]}
    finally:
        db.close()


@admin_router.post("/{partner_id}/seats/{seat_id}/activate")
def admin_activate_seat(partner_id: int, seat_id: int, req: ActivateSeatRequest, admin_user=Depends(get_admin_user)):
    """LEGACY: resolve an old partner-requested seat by linking it to an existing tenant.

    New partner tenants are attributed during normal onboarding (POST /api/admin/mps) and never
    need this step. The single-association rule is enforced by the same service."""
    db = dbmod.SessionLocal()
    try:
        partner = _get_partner_or_404(db, partner_id)
        seat = db.query(PartnerSeat).filter(PartnerSeat.id == seat_id, PartnerSeat.partner_id == partner_id).first()
        if not seat:
            raise HTTPException(404, "Seat not found")
        if seat.status == "rejected":
            raise HTTPException(409, "Seat was rejected")
        tenant = db.query(Tenant).filter(Tenant.id == req.tenant_id).first()
        if not tenant or not tenant.is_active:
            raise HTTPException(404, "Tenant not found or inactive")
        if seat.status != "requested" or seat.tenant_id:
            raise HTTPException(409, "Only legacy pending requests can be linked this way; "
                                     "new tenants are attributed during onboarding.")
        if not partner.is_active:
            raise HTTPException(409, "Partner is inactive")
        try:
            link_legacy_request(db, seat, tenant, admin_user)
            db.commit()
        except AttributionError as exc:
            db.rollback()
            raise HTTPException(exc.status_code, exc.message)
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "Tenant is already attributed to a partner.")
        _audit(admin_user, "activate_partner_seat", "partner_seat", partner.name, f"seat={seat.id} tenant={tenant.id}")
        return {"success": True, "seat": {**_seat_dict(seat), "tenant_id": seat.tenant_id}}
    finally:
        db.close()


@admin_router.post("/{partner_id}/seats/{seat_id}/reject")
def admin_reject_seat(partner_id: int, seat_id: int, admin_user=Depends(get_admin_user)):
    db = dbmod.SessionLocal()
    try:
        partner = _get_partner_or_404(db, partner_id)
        seat = db.query(PartnerSeat).filter(PartnerSeat.id == seat_id, PartnerSeat.partner_id == partner_id).first()
        if not seat:
            raise HTTPException(404, "Seat not found")
        if seat.status != "requested":
            raise HTTPException(409, "Only legacy pending requests can be rejected")
        seat.status = "rejected"
        db.commit()
        _audit(admin_user, "reject_partner_seat", "partner_seat", partner.name, f"seat={seat.id}")
        return {"success": True}
    finally:
        db.close()


@admin_router.post("/{partner_id}/seats/{seat_id}/status")
def admin_set_seat_status(partner_id: int, seat_id: int, req: SeatStatusRequest, admin_user=Depends(get_admin_user)):
    if req.status not in ("active", "paused"):
        raise HTTPException(400, "status must be 'active' or 'paused'")
    db = dbmod.SessionLocal()
    try:
        partner = _get_partner_or_404(db, partner_id)
        seat = db.query(PartnerSeat).filter(PartnerSeat.id == seat_id, PartnerSeat.partner_id == partner_id).first()
        if not seat:
            raise HTTPException(404, "Seat not found")
        if not seat.tenant_id or seat.status not in PORTFOLIO_STATUSES:
            raise HTTPException(409, "Only an attributed client can be paused or resumed")
        seat.status = req.status
        db.commit()
        _audit(admin_user, "set_partner_seat_status", "partner_seat", partner.name, f"seat={seat.id} -> {req.status}")
        return {"success": True, "status": seat.status}
    finally:
        db.close()
