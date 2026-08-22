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
afterward — not one OTP per grievance. This "mobile-scoped OTP" shape is
what `OtpGatedStatusMixin` (modules/govt_sync/adapters/base.py) generalizes
— this module implements only the three portal-specific hooks the mixin
needs (_send_otp/_validate_otp/_fetch_status), everything else (the
govt_otp_sessions cache, start/complete/verification_state, the
check_status() state machine) lives in the shared mixin now. See
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

WANT TO ADD ANOTHER STATE? Don't copy this whole file. Confirm the target
portal actually has a real backend API worth calling (trace real network
traffic the way this one was discovered — never assume from this file
alone), then write a new adapter module with just that portal's
_send_otp/_validate_otp/_fetch_status (if it turns out to be mobile-scoped
OTP-gated like this one — otherwise implement check_status() directly, no
mixin needed) and register it in
modules/govt_sync/adapters/__init__.py's _STATUS_CHECK_ADAPTERS.
"""
import logging
import uuid

from .base import OtpGatedStatusMixin
from .manual import ManualAssistedAdapter

logger = logging.getLogger("needle.govt_sync.adapter.rajasthan_sampark")

_GATEWAY_URL = "https://sampark.rajasthan.gov.in/gateway/api/GatewayService/GetList"
_REQUEST_TIMEOUT_SECONDS = 15


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


# ─── The adapter itself ─────────────────────────────────────────────

class RajasthanSamparkAPIAdapter(OtpGatedStatusMixin, ManualAssistedAdapter):
    """Mixin first so its check_status() wins over ManualAssistedAdapter's
    HTML-scrape version; prepare_submission() still comes from
    ManualAssistedAdapter unchanged (filing is still a real human on the
    real portal — see module docstring's SCOPE note)."""

    def _send_otp(self, mobile_no: str, anchor_reference: str) -> dict:
        return send_otp(mobile_no, anchor_reference)

    def _validate_otp(self, otp: str, transaction_number: str, session_id: str) -> bool:
        return validate_otp(otp, transaction_number, session_id)

    def _fetch_status(self, mobile_no: str, reference_number: str, transaction_number: str, session_id: str) -> dict | None:
        return check_grievance_detail(mobile_no, reference_number, transaction_number, session_id)
