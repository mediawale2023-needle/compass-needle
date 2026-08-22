"""
modules/govt_sync/otp_sessions.py — generic per-(tenant, portal) OTP session
cache backing `govt_otp_sessions`.

This is the shared data layer for any portal whose real status-check API is
gated by an OTP that verifies a MOBILE NUMBER for a stretch of time rather
than one grievance (confirmed for Rajasthan Sampark; see
modules/govt_sync/adapters/rajasthan_sampark.py for how that was discovered
— never assume a new portal behaves the same way without tracing its real
traffic). modules/govt_sync/adapters/base.py's OtpGatedStatusMixin is what
actually calls this module — portal-specific adapters should not need to
touch govt_otp_sessions directly.

Deliberately its own module rather than folded into adapters/base.py: this
is real DB access, and every other adapter concept in base.py is pure
interface/dataclasses with zero DB dependency. Keeping the DB layer separate
means base.py stays importable without a DB connection unless a portal
actually needs one.
"""
from datetime import datetime, timezone


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_cached_session(tenant_id: int, portal_id: int) -> dict | None:
    from core.db_helpers import _q_one
    return _q_one(
        "SELECT id, mobile_no, transaction_number, session_id, verified_at, last_check_failed "
        "FROM govt_otp_sessions WHERE tenant_id = :tid AND portal_id = :pid",
        {"tid": tenant_id, "pid": portal_id},
    )


def upsert_session(tenant_id: int, portal_id: int, mobile_no: str, transaction_number: str,
                    session_id: str, verified_at=None) -> None:
    from sansadx_backend.db import engine
    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO govt_otp_sessions (
                    tenant_id, portal_id, mobile_no, transaction_number, session_id,
                    requested_at, verified_at, last_check_failed
                ) VALUES (:tid, :pid, :mobile, :txn, :sess, :now, :verified_at, false)
                ON CONFLICT (tenant_id, portal_id) DO UPDATE SET
                    mobile_no = EXCLUDED.mobile_no,
                    transaction_number = EXCLUDED.transaction_number,
                    session_id = EXCLUDED.session_id,
                    requested_at = EXCLUDED.requested_at,
                    verified_at = EXCLUDED.verified_at,
                    last_check_failed = false
                """
            ),
            {
                "tid": tenant_id, "pid": portal_id, "mobile": mobile_no,
                "txn": transaction_number, "sess": session_id,
                "now": _utcnow(), "verified_at": verified_at,
            },
        )


def mark_session_failed(tenant_id: int, portal_id: int) -> None:
    from sansadx_backend.db import engine
    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE govt_otp_sessions SET last_check_failed = true WHERE tenant_id = :tid AND portal_id = :pid"),
            {"tid": tenant_id, "pid": portal_id},
        )


def touch_session_used(tenant_id: int, portal_id: int) -> None:
    from sansadx_backend.db import engine
    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE govt_otp_sessions SET last_used_at = :now WHERE tenant_id = :tid AND portal_id = :pid"),
            {"tid": tenant_id, "pid": portal_id, "now": _utcnow()},
        )


def verification_state(tenant_id: int, portal_id: int) -> dict:
    """{'status': 'verified'|'pending'|'expired'|'not_started', 'mobile_no', 'verified_at'}"""
    session = get_cached_session(tenant_id, portal_id)
    if not session:
        return {"status": "not_started", "mobile_no": None, "verified_at": None}
    if session.get("last_check_failed"):
        return {"status": "expired", "mobile_no": session["mobile_no"], "verified_at": session.get("verified_at")}
    if session.get("verified_at"):
        return {"status": "verified", "mobile_no": session["mobile_no"], "verified_at": session["verified_at"]}
    return {"status": "pending", "mobile_no": session["mobile_no"], "verified_at": None}
