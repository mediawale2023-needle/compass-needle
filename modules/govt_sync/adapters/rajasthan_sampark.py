"""
modules/govt_sync/adapters/rajasthan_sampark.py — real status-check API for
Rajasthan Sampark, replacing the generic HTML-scrape ManualAssistedAdapter
uses for every other portal.

BACKGROUND — why this exists: Rajasthan Sampark's status page
(Admin/Grievance_Status.aspx) is a client-side-rendered React SPA. The
status text only ever appears after JavaScript runs and calls the portal's
own backend; a plain `requests.get()` (what ManualAssistedAdapter does) only
ever sees the empty HTML shell and can never see a real status, for any
reference number, real or fake. This was confirmed directly: reproduced
network calls the live page itself makes and mapped the full flow (2026-08-21
investigation, staff-supplied real OTPs against real, Needle-filed
grievances — no code changed, no citizen data touched beyond what those
grievances already returned to their own filer).

THE REAL API: everything is a POST to
`https://sampark.rajasthan.gov.in/gateway/api/GatewayService/GetList`, a
generic JSON-RPC-style gateway (one endpoint, `ApiKey` field names the
action) with no cookie/bearer-token auth — the entire "session" is two GUIDs
(`TransactionNumber`, `SessionId`) carried explicitly in the request body.
This is why `requests.post()` can drive it directly with no browser.

THE ONE THING THAT DOES need staff: an OTP, sent by SMS to the mobile number
a grievance is registered under. Critically, verification is scoped to the
MOBILE NUMBER, not to any one grievance or even to the specific
Transaction/Session pair that completed `ValidateOTP` — confirmed valid for
at least ~28 minutes across multiple different grievances registered to the
same mobile, with a fresh never-validated pair for that mobile accepted too.
So ONE staff-entered OTP unlocks status checks for every grievance Needle
has filed under that tenant's own `portal_contact_number` for a good while
afterward — not one OTP per grievance. See modules/govt_sync/__init__.py and
PROJECT_MEMORY.md for the operating model this produces (staff verifies
once or twice a day; Needle polls silently in between).

PII DISCIPLINE: `GetGrievanceDetailByGrivIdAndMobileNo` returns ~130 fields
per grievance, including a full complainant PII block (name, phone, email,
address). Needle only ever extracts status/department/subject/dates from
it — the complainant PII fields are never read into a variable, never
persisted, never logged, even for audit. `TransactionNumber`/`SessionId`
are treated as sensitive short-lived portal-issued credentials (cached in
`govt_otp_sessions`, never exposed to the frontend beyond a verified
yes/no). The raw OTP code itself is never persisted anywhere, not even
transiently.

SCOPE: this only replaces check_status(). Filing itself (prepare_submission)
is unchanged — staff still open the real portal via a live session (already
supported for Rajasthan) and file for real themselves; this module has
nothing to do with submission.

NOTE ON SECURITY FINDINGS: two endpoints touched during the investigation
have no authentication at all — GetDetailByGrievanceNo (returns a citizen's
unmasked mobile number from just a grievance number) and
GetActionIntegratedHistoryListCitizen (returns another citizen's grievance
history from a guessable sequential internal ID). Neither is called by this
module (Phase 1 deliberately skips both — see design notes below) and
neither was exploited beyond confirming they exist. This is a real
vulnerability in Rajasthan Sampark's own backend, independent of anything
Needle does with it — flagged for responsible disclosure to RISL separately
from this feature, not something this module relies on or should ever be
extended to use.

DESIGN NOTE: Phase 1 deliberately skips GetDetailByGrievanceNo (resolve
grievance -> mobile) because Needle always already knows the mobile number
for its own filed cases (it's the tenant's own portal_contact_number, the
same number entered as the applicant mobile at filing time) — no need to
ask the portal for something we already have. It also skips
GetActionIntegratedHistoryListCitizen (full history timeline) because
Needle's dashboard only needs the current status, not a full history view;
see PROJECT_MEMORY.md for that scoping decision.
"""
import logging
import uuid
from datetime import datetime, timezone

from .base import GovtPortalAdapter, StatusResult, normalize_status_keywords
from .manual import ManualAssistedAdapter

logger = logging.getLogger("needle.govt_sync.adapter.rajasthan_sampark")

_GATEWAY_URL = "https://sampark.rajasthan.gov.in/gateway/api/GatewayService/GetList"
_REQUEST_TIMEOUT_SECONDS = 15


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _gateway_call(api_key: str, module: str, path: str, api_params: dict) -> dict:
    """One POST to Sampark's generic gateway. Raises on transport failure —
    callers decide what a failure means (never silently swallowed here)."""
    import requests

    body = {
        "ApiKey": api_key, "OrgId": 0, "ApiParams": api_params,
        "Module": module, "Path": path, "ResponseId": 0, "UserId": 0,
        "UserDetails": None, "UserSessionModel": None, "FormAction": None,
    }
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json; charset=UTF-8",
        "X-Request-ID": str(uuid.uuid4()),
        "FormURL": "/",
        "User-Agent": "Mozilla/5.0 (compatible; NeedleGovtSync/1.0)",
    }
    resp = requests.post(_GATEWAY_URL, json=body, headers=headers, timeout=_REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()
    return resp.json()


# ─── Raw Sampark API calls ─────────────────────────────────────────

def send_otp(mobile_no: str, grievance_no: str) -> dict:
    """Triggers a fresh OTP SMS to `mobile_no`. `grievance_no` just anchors
    the request (Sampark's API requires one) — the resulting verification
    covers every grievance on that mobile, not just this one. Returns
    {"transaction_number", "session_id"}. Raises RuntimeError with a
    user-facing message on failure."""
    data = _gateway_call(
        "SendOtpToGrievanceMobileNo", "GRVNC", "Grievance/SendOtpToGrievanceMobileNo",
        {"GrievanceNo": grievance_no, "SendOn": mobile_no, "SendOnType": "Mobile", "ModuleId": 22, "SourceId": 5},
    )
    obj = data.get("CustomObject") or {}
    if not obj.get("IsSent") or not obj.get("TransactionNumber"):
        raise RuntimeError(data.get("Message") or "Rajasthan Sampark did not send an OTP — try again in a moment.")
    return {"transaction_number": obj["TransactionNumber"], "session_id": obj["SessionId"]}


def validate_otp(otp: str, transaction_number: str, session_id: str) -> bool:
    """True on a genuine successful validation. "OTP Verified Already"
    (Status=1 but that specific message) means this mobile already has an
    active verified state from a prior validation — also treated as
    success, not a failure; only a real "Invalid OTP" etc. returns False."""
    data = _gateway_call(
        "ValidateOTP", "UPM", "UserAuthenticate/ValidateOTP",
        {"OTP": otp, "TransactionNumber": transaction_number, "SessionId": session_id},
    )
    if data.get("Status") == 2:
        return True
    message = (data.get("Message") or "").strip().lower()
    return "verified already" in message


def check_grievance_detail(mobile_no: str, grievance_no: str, transaction_number: str, session_id: str) -> dict | None:
    """Returns a trimmed, PII-free detail dict on success. Returns None if
    the session is no longer accepted (expired/invalid) — the caller's job
    to decide that means "ask staff to re-verify", not "grievance doesn't
    exist" (this module can't cheaply tell those apart)."""
    data = _gateway_call(
        "GetGrievanceDetailByGrivIdAndMobileNo", "GRVNC", "Grievance/GetGrievanceDetailByGrivIdAndMobileNo",
        {
            "GrievanceNo": grievance_no, "MobileNo": mobile_no,
            "TransactionNumber": transaction_number, "SessionId": session_id, "IsRequired": "Y",
        },
    )
    if data.get("Status") != 2 or not data.get("CustomObject"):
        return None
    obj = data["CustomObject"]
    # Deliberately not extracting ConplainantName/ComplainantMobileNo/
    # ComplainantEmail/address fields — see module docstring. Only what the
    # dashboard status pill actually needs.
    return {
        "status_text": obj.get("Status") or "",
        "sub_status_text": obj.get("SubStatusName") or "",
        "department_name": obj.get("DepartmentName"),
        "subject": obj.get("Subject"),
        "grievance_date": obj.get("GrievanceDate"),
        "last_action_date": obj.get("LastActionDate"),
        "disposed_date": obj.get("DisposedDate"),
    }


# ─── Per-tenant session cache (govt_otp_sessions) ──────────────────
# Deliberately owned by this module, not threaded through the generic
# adapter interface — every other adapter is stateless w.r.t. the DB, and
# giving all of them a DB dependency for this one portal's needs would be a
# much bigger, unjustified refactor. This is the one adapter that needs it.

def _get_cached_session(tenant_id: int, portal_id: int) -> dict | None:
    from core.db_helpers import _q_one
    return _q_one(
        "SELECT id, mobile_no, transaction_number, session_id, verified_at, last_check_failed "
        "FROM govt_otp_sessions WHERE tenant_id = :tid AND portal_id = :pid",
        {"tid": tenant_id, "pid": portal_id},
    )


def _upsert_session(tenant_id: int, portal_id: int, mobile_no: str, transaction_number: str,
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


def _mark_session_failed(tenant_id: int, portal_id: int) -> None:
    from sansadx_backend.db import engine
    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE govt_otp_sessions SET last_check_failed = true WHERE tenant_id = :tid AND portal_id = :pid"),
            {"tid": tenant_id, "pid": portal_id},
        )


def _touch_session_used(tenant_id: int, portal_id: int) -> None:
    from sansadx_backend.db import engine
    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE govt_otp_sessions SET last_used_at = :now WHERE tenant_id = :tid AND portal_id = :pid"),
            {"tid": tenant_id, "pid": portal_id, "now": _utcnow()},
        )


# ─── Orchestration — called by api_router.py's /govt/otp/* endpoints ───

def start_verification(tenant_id: int, portal_id: int, mobile_no: str, anchor_grievance_no: str) -> None:
    """Sends a fresh OTP and stores the pending (unverified) session."""
    result = send_otp(mobile_no, anchor_grievance_no)
    _upsert_session(tenant_id, portal_id, mobile_no, result["transaction_number"], result["session_id"], verified_at=None)


def complete_verification(tenant_id: int, portal_id: int, otp_code: str) -> bool:
    """Validates the OTP against the pending session. Returns True on
    success (session marked verified for reuse). Returns False on a
    genuinely wrong OTP (session stays pending, staff can retry). Raises
    RuntimeError if there's no pending session at all."""
    session = _get_cached_session(tenant_id, portal_id)
    if not session:
        raise RuntimeError("No pending verification — send an OTP first.")
    ok = validate_otp(otp_code, session["transaction_number"], session["session_id"])
    if ok:
        _upsert_session(
            tenant_id, portal_id, session["mobile_no"],
            session["transaction_number"], session["session_id"], verified_at=_utcnow(),
        )
    return ok


def verification_state(tenant_id: int, portal_id: int) -> dict:
    """{'status': 'verified'|'pending'|'expired'|'not_started', 'mobile_no', 'verified_at'}"""
    session = _get_cached_session(tenant_id, portal_id)
    if not session:
        return {"status": "not_started", "mobile_no": None, "verified_at": None}
    if session.get("last_check_failed"):
        return {"status": "expired", "mobile_no": session["mobile_no"], "verified_at": session.get("verified_at")}
    if session.get("verified_at"):
        return {"status": "verified", "mobile_no": session["mobile_no"], "verified_at": session["verified_at"]}
    return {"status": "pending", "mobile_no": session["mobile_no"], "verified_at": None}


# ─── The adapter itself ─────────────────────────────────────────────

class RajasthanSamparkAPIAdapter(ManualAssistedAdapter):
    """Inherits prepare_submission() unchanged from ManualAssistedAdapter —
    filing is still a real human on the real portal. Only check_status()
    is different."""

    def check_status(self, reference_number: str, tenant_id: int | None = None) -> StatusResult:
        if not tenant_id:
            # Shouldn't happen in practice (callers always pass it for this
            # adapter) — fail closed rather than guess whose session to use.
            return StatusResult(status="", checked=False)

        # Different callers alias this differently (a clean portal row uses
        # "id"; a cases-JOIN-govt_portals row needs "portal_id" to avoid
        # colliding with the case's own "id") — accept either.
        portal_id = self.portal.get("portal_id") or self.portal.get("id")
        session = _get_cached_session(tenant_id, portal_id)
        if not session or not session.get("verified_at"):
            return StatusResult(status="", checked=False, needs_verification=True)

        try:
            detail = check_grievance_detail(
                session["mobile_no"], reference_number,
                session["transaction_number"], session["session_id"],
            )
        except Exception as e:
            logger.warning(f"Rajasthan Sampark status check failed for ref={reference_number}: {e}")
            return StatusResult(status="", checked=False)

        if detail is None:
            _mark_session_failed(tenant_id, portal_id)
            return StatusResult(status="", checked=False, needs_verification=True)

        _touch_session_used(tenant_id, portal_id)
        raw_status = f"{detail['status_text']} / {detail['sub_status_text']}".strip(" /")
        normalized = normalize_status_keywords(raw_status)
        if not normalized:
            logger.info(f"Rajasthan Sampark status '{raw_status}' unrecognised for ref={reference_number} — needs manual look")
            return StatusResult(status="", raw_portal_status=raw_status, checked=False)

        return StatusResult(status=normalized, raw_portal_status=raw_status, checked=True)
