"""
modules/govt_sync/adapters/karnataka_ipgrs.py — Karnataka iPGRS interactive
status-check adapter (InteractiveStatusCheckMixin), NOT OtpGatedStatusMixin.

BACKGROUND: unlike Rajasthan Sampark, Karnataka's real status-check endpoint
is gated by a CAPTCHA that must be solved live, by a human, on every single
lookup — there is no reusable, cacheable "verify once, check many times"
session the way Rajasthan's mobile-scoped OTP provides. This was confirmed
directly: a real, legitimately-filed Karnataka grievance was looked up live
(CAPTCHA entered by a human in the browser, never solved/OCR'd/bypassed by
Claude), and the exact request/response contract below was additionally
confirmed by reading the portal's own real, un-obfuscated inline JavaScript
on https://ipgrs.karnataka.gov.in/Grievance/GetGrievanceStatus — not
inferred from selector names, not guessed.

THE REAL CONTRACT (confirmed from source):
    GET  /Grievance/GetGrievanceStatus            establishes the session
    GET  /Home/GetGrievanceStatusCaptchaImage      session-bound CAPTCHA image
    POST /Grievance/VerifyGrievanceStatus          application/x-www-form-urlencoded
         data: {GrievanceId, MobileOrEmail, Captcha}
         response: {"success": bool, "message": str, "data": {..., "Status": str}}
No CSRF token is sent by the real page's own client code for this specific
call (confirmed from source — the visible __RequestVerificationToken field
exists in the page markup but this handler never reads it), so none is sent
here either. Nothing about server-side enforcement of that token was probed
or tested — only what the real browser flow actually sends is implemented.

SCOPE: this only implements check_status() (via InteractiveStatusCheckMixin).
Filing is untouched — prepare_submission() still comes from
ManualAssistedAdapter, staff still file for real on the real portal
(browser_session.py already drives Karnataka's live filing session, forces
English via its _ensure_english() heuristic — unrelated to this module).

WHY InteractiveStatusCheckMixin, NOT OtpGatedStatusMixin: Karnataka's CAPTCHA
must be solved fresh on every lookup — there is no persisted, reusable,
cross-lookup verified session to cache the way govt_otp_sessions caches
Rajasthan's. Mixing this with OtpGatedStatusMixin, or storing anything here
in govt_otp_sessions, would misrepresent that. See status_flow.py's module
docstring and modules/govt_sync/adapters/__init__.py's investigation map for
the full reasoning — this module does not use, import, or touch
govt_otp_sessions or OtpGatedStatusMixin.

PERSISTENCE: attempts (a requests.Session()'s cookie jar, reduced to a plain
dict, plus a few bookkeeping fields) live ONLY in the process-local
`_attempts` dict below — the same precedent already established by
modules/govt_sync/browser_session.py's `_sessions` dict for live filing
sessions. No DB table, no Redis, no govt_otp_sessions. This means an
in-flight attempt (staff has seen the CAPTCHA but not yet submitted an
answer) DOES NOT SURVIVE a backend restart or process replacement — staff
would need to click "Check status" again and get a fresh CAPTCHA. This is
an accepted, deliberate limitation, not an oversight: building anything more
durable for a single-shot, minutes-lived, non-reusable CAPTCHA prompt would
be exactly the kind of workflow-engine over-engineering this design was
told to avoid.

SECURITY / DATA HANDLING: CAPTCHA text, the CAPTCHA image (including its
base64 form), session cookies, and the portal contact number are never
logged, anywhere in this module, under any code path — only the case
reference number (already logged elsewhere throughout govt_sync) and
generic failure descriptions appear in log lines. Session cookies are never
returned through any API response — they exist only inside the process-local
_attempts dict, addressed by an opaque attempt_id.

NOT EXTRACTED FROM THE PORTAL RESPONSE: Department, Category, Description,
PendencyDetails, DateOfRegistration — all present in the real response
payload, none of them read here. Only `Status` (for raw_portal_status /
normalization) and a success/failure check are used. StatusResult is not
modified to carry these, per explicit instruction — this is a deliberate
narrowing, not an oversight.
"""
import base64
import logging
import time
import uuid
from dataclasses import dataclass, field

from .base import StatusResult, normalize_status_keywords
from .manual import ManualAssistedAdapter
from .status_flow import (
    HumanVerificationRequirement,
    InteractiveStatusCheckMixin,
    SessionRequirement,
    StatusCheckAttempt,
    StatusCheckAttemptState,
    StatusCheckFlow,
    StatusCheckStage,
    TransportKind,
)

logger = logging.getLogger("needle.govt_sync.adapter.karnataka_ipgrs")

_BASE_URL = "https://ipgrs.karnataka.gov.in"
_STATUS_PAGE_PATH = "/Grievance/GetGrievanceStatus"
_CAPTCHA_IMAGE_PATH = "/Home/GetGrievanceStatusCaptchaImage"
_VERIFY_PATH = "/Grievance/VerifyGrievanceStatus"
_REQUEST_TIMEOUT_SECONDS = 15
_USER_AGENT = "Mozilla/5.0 (compatible; NeedleGovtSync/1.0)"

# An abandoned CAPTCHA prompt (staff never came back to answer it) expires
# rather than living in the process-local store forever. Lookup-lazy check,
# no background sweep — the smallest reasonable mechanism, matching
# browser_session.py's SESSION_IDLE_SECONDS precedent in spirit, not in code.
_ATTEMPT_TTL_SECONDS = 300


@dataclass
class _KarnatakaAttemptSession:
    """Process-local only — never serialized, never returned through any API
    response, never logged. Holds exactly what advance() needs to replay the
    same session the CAPTCHA image was issued on."""
    attempt_id: str
    case_id: int
    tenant_id: int
    reference_number: str
    mobile_or_email: str
    cookies: dict
    created_at: float = field(default_factory=time.time)


# Process-local, in-memory only — same precedent as
# modules/govt_sync/browser_session.py's `_sessions` dict. NOT govt_otp_sessions,
# not a DB table, not Redis. Does not survive a backend restart/process
# replacement — an in-flight attempt is simply lost; staff starts over.
_attempts: dict[str, _KarnatakaAttemptSession] = {}


def _gc_expired() -> None:
    now = time.time()
    expired = [aid for aid, a in _attempts.items() if now - a.created_at > _ATTEMPT_TTL_SECONDS]
    for aid in expired:
        del _attempts[aid]


class KarnatakaAPIAdapter(InteractiveStatusCheckMixin, ManualAssistedAdapter):
    """Mixin first, same MRO convention as Rajasthan — check_status() from
    InteractiveStatusCheckMixin wins (always checked=False, honestly, since
    an interactive lookup can't complete inside one synchronous call);
    prepare_submission() from ManualAssistedAdapter is untouched, filing
    stays a real human on the real portal."""

    def describe_flow(self) -> StatusCheckFlow:
        return StatusCheckFlow(stages=[
            StatusCheckStage(
                name="verify_and_fetch",
                # grievance_id and mobile_or_email are both already known to
                # Needle (the case's own govt_reference_number and the
                # tenant's configured portal contact number) — neither is a
                # real staff-typed input. CAPTCHA is represented separately,
                # through human_verification, not as a normal stage input.
                inputs=["grievance_id", "mobile_or_email"],
                produced_values=[],
                human_verification=[HumanVerificationRequirement(kind="captcha")],
                transport=TransportKind.AJAX_FORM,
                session_requirement=SessionRequirement.NONE,
            ),
        ])

    def start(self, reference_number: str, tenant_id: int, initial_inputs: dict) -> StatusCheckAttempt:
        initial_inputs = initial_inputs or {}
        mobile_or_email = initial_inputs.get("mobile_or_email")
        case_id = int(initial_inputs.get("case_id") or 0)
        if not mobile_or_email:
            raise RuntimeError("No portal contact number on file for this tenant — set one before checking status.")

        import requests

        session = requests.Session()
        session.headers.update({"User-Agent": _USER_AGENT})
        try:
            # Establishes the session cookie the same way a real page load
            # does — confirmed necessary: the CAPTCHA image and the verify
            # POST must share this session for the CAPTCHA answer to be
            # checked against the right challenge.
            session.get(_BASE_URL + _STATUS_PAGE_PATH, timeout=_REQUEST_TIMEOUT_SECONDS)
            captcha_resp = session.get(_BASE_URL + _CAPTCHA_IMAGE_PATH, timeout=_REQUEST_TIMEOUT_SECONDS)
            captcha_resp.raise_for_status()
        except Exception as e:
            logger.warning(f"Karnataka iPGRS status-check start failed for ref={reference_number}: {e}")
            raise RuntimeError("Could not reach the Karnataka portal — try again in a moment.")

        content_type = captcha_resp.headers.get("Content-Type", "image/png")
        challenge_uri = f"data:{content_type};base64,{base64.b64encode(captcha_resp.content).decode('ascii')}"

        _gc_expired()
        attempt_id = uuid.uuid4().hex
        _attempts[attempt_id] = _KarnatakaAttemptSession(
            attempt_id=attempt_id,
            case_id=case_id,
            tenant_id=tenant_id,
            reference_number=reference_number,
            mobile_or_email=mobile_or_email,
            cookies=dict(session.cookies.get_dict()),
        )

        return StatusCheckAttempt(
            attempt_id=attempt_id,
            case_id=case_id,
            tenant_id=tenant_id,
            reference_number=reference_number,
            state=StatusCheckAttemptState.AWAITING_HUMAN_INPUT,
            pending_human_verification=[HumanVerificationRequirement(kind="captcha", challenge=challenge_uri)],
        )

    def advance(self, attempt: StatusCheckAttempt, verification_answers: dict,
                next_inputs: dict | None = None) -> StatusCheckAttempt:
        _gc_expired()
        stored = _attempts.get(attempt.attempt_id)
        # Tenant/case scoping, same discipline as every other tenant-scoped
        # lookup in this codebase — an unrecognised or mismatched attempt_id
        # is indistinguishable from an expired one, never leaks which case
        # it belonged to.
        if not stored or stored.tenant_id != attempt.tenant_id or stored.case_id != attempt.case_id:
            attempt.state = StatusCheckAttemptState.FAILED
            attempt.result = StatusResult(
                status="", checked=False,
                raw_portal_status="Status check expired or not found — start again.",
            )
            return attempt

        captcha_text = ((verification_answers or {}).get("captcha") or "").strip()
        if not captcha_text:
            # Nothing to submit yet — leave the attempt (and its stored
            # session) exactly as-is so the same CAPTCHA can still be
            # answered; this is a caller-side validation gap (empty input),
            # not a portal failure.
            attempt.state = StatusCheckAttemptState.AWAITING_HUMAN_INPUT
            return attempt

        import requests

        session = requests.Session()
        session.headers.update({"User-Agent": _USER_AGENT})
        session.cookies.update(stored.cookies)

        try:
            resp = session.post(
                _BASE_URL + _VERIFY_PATH,
                data={
                    "GrievanceId": stored.reference_number,
                    "MobileOrEmail": stored.mobile_or_email,
                    "Captcha": captcha_text,
                },
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            payload = resp.json()
        except Exception as e:
            logger.warning(f"Karnataka iPGRS status-check advance failed for ref={stored.reference_number}: {e}")
            del _attempts[attempt.attempt_id]
            attempt.state = StatusCheckAttemptState.FAILED
            attempt.result = StatusResult(status="", checked=False, raw_portal_status="Portal check failed — try again.")
            return attempt

        # Single-use regardless of outcome — the real portal issues a fresh
        # CAPTCHA on every attempt (see refreshCaptchaImage() in its own
        # page), so a failed attempt is not silently retryable with the same
        # challenge; staff starts over via start() for a new one.
        del _attempts[attempt.attempt_id]

        if not payload.get("success"):
            attempt.state = StatusCheckAttemptState.FAILED
            attempt.result = StatusResult(
                status="", checked=False,
                raw_portal_status=payload.get("message") or "Verification failed.",
            )
            return attempt

        raw_status = (payload.get("data") or {}).get("Status") or ""
        normalized = normalize_status_keywords(raw_status)

        attempt.state = StatusCheckAttemptState.COMPLETE
        attempt.result = StatusResult(
            status=normalized or "",
            raw_portal_status=raw_status,
            checked=bool(normalized),
            needs_verification=False,
        )
        return attempt
