"""
modules/govt_sync/adapters/maharashtra_aaplesarkar.py — Maharashtra Aaple
Sarkar interactive status-check adapter (InteractiveStatusCheckMixin), NOT
OtpGatedStatusMixin.

BACKGROUND: unlike Karnataka's single CAPTCHA-gated round trip, Maharashtra's
real status lookup is a genuine THREE-STAGE flow — CAPTCHA, then a real SMS
OTP + a second CAPTCHA, then a third CAPTCHA to actually retrieve the
result. This was confirmed via a live, human-assisted trace against
https://grievances.maharashtra.gov.in (CAPTCHA/OTP entered by a human,
never solved/OCR'd/bypassed by Claude) combined with reading the portal's
own real page markup directly. See PROJECT_MEMORY.md's reference-
architecture entries for the full evidence classification
(CONFIRMED/OBSERVED/INFERRED/UNKNOWN) — this module only implements what
was CONFIRMED or is a narrow, explicitly-flagged extrapolation from it.

THE REAL CONTRACT (mixed CONFIRMED/OBSERVED — see docstrings per function):

  Stage 0 — identity + CAPTCHA #1
    GET  /mr/pg-portal-grievance/track-grievance-verification
         native HTML form (id="anonymous-verify-frm"), fields present:
         _method, _csrfToken, verification_id, registration_no (hidden,
         d-none, still submitted by a real browser), securitycode.
    GET  /mr/citizens/captcha?type=image&field=securitycode&width=100
         &height=42&theme=default&length=6
    POST (same URL) {_method, _csrfToken, verification_id, registration_no,
         securitycode} — application/x-www-form-urlencoded (native form, no
         enctype override).
    On success: PRG redirect to the SAME path with a `?token=<32-char hex>`
         query param — CONFIRMED via live trace. This response IS the
         stage-1 (OTP) page.

  Stage 1 — OTP + CAPTCHA #2
    Same token-bearing URL. Confirmed fields: _method, _csrfToken,
    verification_id, otp, securitycode, registration_no (still hidden).
    `otp` is the CONFIRMED field name — not inferred, not guessed. `cid` is
    NOT present at this stage. A fresh CAPTCHA is issued at the same
    endpoint. OTP is portal-stated to expire in ~2 minutes; there is no
    resend control. The exact network frame for this POST was not
    packet-captured (browser tooling limitation during the trace) — the
    field set is "structurally confirmed" (read from the live DOM), not
    confirmed at the byte level. Treated identically to stage 0's POST
    (form-urlencoded) per explicit instruction, since no enctype override
    exists on this form either.
    On success: reaches /mr/pg-portal-grievance/track-grievance (a
    DIFFERENT path, no token param) — CONFIRMED via live trace.

  Stage 2 — CAPTCHA #3 + result
    /mr/pg-portal-grievance/track-grievance. Confirmed fields on this page:
    registration_no (now the active field), securitycode, cid (hidden,
    7 chars observed, exact value not retained), _csrfToken, _method.
    registration_no's label is "Registration No / Token / CPGRAM Reg No." —
    same identifier concept as every other adapter's `reference_number`
    (Rajasthan's GrievanceNo, Karnataka's GrievanceId), so it is populated
    from Needle's own case.govt_reference_number, exactly like those two —
    NOT asked of staff. This is the one place this module extrapolates
    beyond the literal evidence (the evidence never proved
    registration_no == govt_reference_number end-to-end, since the OTP
    step could not be completed reliably during the trace — see "NOT YET
    LIVE-VALIDATED" below) but it follows the exact same established
    convention as every other portal in this codebase.
    On success: result renders as server-rendered HTML on the SAME page —
    no distinct URL/marker. CONFIRMED field VALUES from one real successful
    lookup (District, Status, Source, Grievance token, Department,
    Registration No., Office, Officer, Contact, Documents) — but the exact
    HTML/label markup producing them was never captured (explicitly
    downgraded to UNKNOWN in the evidence: "no stable DOM ids/classes").
    Only `Status` is parsed here — see PII/scope discipline below.

TAXONOMY GAP — FIXED (2026-08-24, `db3c08ee`): the one real CONFIRMED
status value for Maharashtra is literally "Submitted". `base.py`'s
`STATUS_KEYWORDS`'s "submitted" bucket now explicitly includes the literal
keyword "submitted" (added after this exact gap was found via testing),
so this real value normalizes correctly today instead of falling through
to `checked=False`. This section previously described the gap as still
open; it was left stale after the shared fix landed. Kept here, corrected,
so a future reader isn't misled into re-discovering or re-"fixing" an
already-closed gap.

CSRF: `_csrfToken` is re-scraped fresh from each HTML response before the
next POST — never reused from an earlier stage. This is a defensive
default (CakePHP's `_csrfToken`/`_method` naming convention commonly
rotates these per render), not something specifically proven to be
required, but it costs nothing extra and is strictly safer than assuming
reuse — see modules/govt_sync/adapters/__init__.py's "Unknown is a valid
state" principle; this is the same discipline applied to an implementation
default, not a protocol claim.

WHY InteractiveStatusCheckMixin, NOT OtpGatedStatusMixin: Maharashtra's OTP
is part of the live lookup itself, not a persisted, reusable, cross-lookup
verified session the way Rajasthan's govt_otp_sessions-cached OTP is.
Nothing here uses, imports, or touches govt_otp_sessions or
OtpGatedStatusMixin — see status_flow.py's module docstring for the fuller
reasoning (unchanged by this module).

NOT YET LIVE-VALIDATED: the OTP step (stage 1) and the final result parser
(stage 2's HTML->Status extraction) have NOT been exercised against a real,
complete, successful live run in this implementation pass — OTP delivery
was unreliable during the trace that produced the evidence above, and no
further live test was performed to avoid working around that unreliability.
Both are implemented from CONFIRMED/OBSERVED evidence and unit-tested with
mocked HTTP + a constructed (not captured) result-page fixture — but the
first real end-to-end run through all three stages, live, is still
outstanding. See this package's test file for exactly what is and isn't
covered by mocks.

PRODUCTION CONNECTIVITY (updated 2026-09-03 — do not trust the sentence
below this one without checking the date on any future edit): the EC2
backend was network-blocked from grievances.maharashtra.gov.in as
recently as 2026-08-26 (TCP 80/443 timed out; DNS resolved) — confirmed
multiple times up to and including that date. A fresh, live, read-only
reachability check run 2026-09-03 directly from the production EC2 host
(diagnose-portal-reachability.yml, no CAPTCHA/OTP/portal interaction, DNS
+ TCP connect + HTTPS HEAD only) found the block NO LONGER PRESENT: DNS
resolves, TCP connects on both 80 and 443, HTTPS HEAD returns a normal
302 with a verified SSL certificate. This directly un-blocks THIS
adapter's own status-check HTTP calls (plain `requests`, same client
shape as the successful check). It does NOT by itself prove the 3-stage
CAPTCHA+OTP+CAPTCHA flow completes successfully end-to-end — that still
requires a real staff-assisted run, not yet re-performed since 2026-08-24
— and it does NOT prove the separate live-browser/Playwright filing path
works (different client, not re-tested; see
modules/data/govt_portals.json's `live_session_supported`, deliberately
left false pending that separate check). See that file's source_note for
this portal for the full, dated evidence trail.

PERSISTENCE (updated — Karnataka/Maharashtra _attempts -> Postgres
migration): attempt state (a genuine three-human-step flow, tracked across
up to 3 advance() calls) lives in `govt_status_check_attempts` via
modules/govt_sync/status_attempts.py — NOT a process-local dict anymore.
This was previously an in-memory-only `_attempts` dict (same precedent as
karnataka_ipgrs.py's own, and further back, browser_session.py's
`_sessions`), which required start() and every advance() for the same
attempt to land on the same backend worker — true only under
browser_session.py's single-worker `backend_govt_live` routing. Moving this
state to Postgres removes that requirement without changing the CAPTCHA/OTP
flow, CSRF handling, the portal request/response contract, or any
externally observable behavior. TTL is still tracked from LAST activity,
not creation (a genuine three-human-step flow needs more real wall-clock
time than Karnataka's single step) — a stalled/abandoned attempt is simply
invisible past its TTL (see _ATTEMPT_TTL_SECONDS), not swept by a
background loop. A failure at any stage still clears the attempt; staff
still starts over from stage 0.

SECURITY / DATA HANDLING: CAPTCHA text, CAPTCHA images (incl. base64), OTP
codes, session cookies, and the portal contact number are never logged,
anywhere in this module, under any code path. The OTP's human-facing
description shown to staff never includes the mobile/email it was sent to.
Only the case reference number and generic failure descriptions appear in
log lines. Cookies/csrf/token/cid never appear in any API response — they
exist only in govt_status_check_attempts, addressed by an opaque
attempt_id, with the same never-exposed/never-logged discipline
modules/govt_sync/otp_sessions.py already established for Rajasthan's
govt_otp_sessions.

NOT EXTRACTED FROM THE RESULT PAGE: District, Source, Grievance token
(portal's own, not Needle's reference), Department, Office, Officer,
Contact, Documents — all present in the one real successful lookup, none
of them read here. Only `Status` is parsed (for raw_portal_status /
normalization), same discipline as Karnataka. StatusResult is not modified
to carry the rest, per explicit instruction.
"""
import base64
import logging
import re
import uuid
from urllib.parse import parse_qs, urlparse

from ..status_attempts import create_attempt, delete_attempt, load_attempt, update_attempt_stage
from .base import StatusResult, normalize_status_keywords
from .manual import ManualAssistedAdapter
from .status_flow import (
    HumanVerificationRequirement,
    InteractiveStatusCheckMixin,
    PortalUnavailableError,
    SessionRequirement,
    StatusCheckAttempt,
    StatusCheckAttemptState,
    StatusCheckFlow,
    StatusCheckStage,
    TransportKind,
)

logger = logging.getLogger("needle.govt_sync.adapter.maharashtra_aaplesarkar")

_BASE_URL = "https://grievances.maharashtra.gov.in"
_VERIFY_PATH = "/mr/pg-portal-grievance/track-grievance-verification"
_TRACK_PATH = "/mr/pg-portal-grievance/track-grievance"
_CAPTCHA_PATH = "/mr/citizens/captcha?type=image&field=securitycode&width=100&height=42&theme=default&length=6"
_REQUEST_TIMEOUT_SECONDS = 15
_USER_AGENT = "Mozilla/5.0 (compatible; NeedleGovtSync/1.0)"

# A real three-human-step flow (CAPTCHA, wait for + enter a real SMS OTP,
# CAPTCHA again) genuinely needs more wall-clock time than Karnataka's
# single round trip — tracked from LAST activity so slow-but-steady
# progress through the stages isn't cut off mid-flow, unlike Karnataka's
# simpler creation-based TTL.
_ATTEMPT_TTL_SECONDS = 600

_OTP_HUMAN_DESCRIPTION = "OTP sent to the portal contact number on file — enter it within about 2 minutes."


class _MaharashtraStageFailure(Exception):
    """Internal control-flow only — never escapes advance().

    preserve_attempt=True marks the specific case where update_attempt_stage()
    returned False because a concurrent advance() already won the race and
    moved the row past the stage this call expected — NOT a genuine terminal
    failure. The dispatcher's except-handler must not delete_attempt() in
    that case: the row it would delete is the concurrent winner's freshly-
    advanced state, not this (losing) call's own — deleting it unconditionally
    would corrupt the winner's persisted progress rather than just failing
    this caller cleanly."""
    def __init__(self, note: str, preserve_attempt: bool = False):
        super().__init__(note)
        self.note = note
        self.preserve_attempt = preserve_attempt


def _extract_hidden_field(html: str, name: str) -> str | None:
    """CONFIRMED-shape helper: every stage's form carries its state as a
    plain hidden <input>. Re-scraped fresh from each response — see module
    docstring's CSRF note."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("input", {"name": name})
    return tag.get("value") if tag else None


def _extract_token_from_url(url: str) -> str | None:
    """CONFIRMED via live trace: successful stage-0 submission redirects to
    the same path with `?token=<32-char hex>`."""
    query = parse_qs(urlparse(url).query)
    values = query.get("token")
    return values[0] if values else None


def _extract_label_value(text: str, labels: list[str]) -> str | None:
    """Best-effort text-scan extraction, NOT a confirmed selector-based
    parse — the evidence explicitly downgraded "stable DOM ids/classes" to
    UNKNOWN for this result page. Finds the first matching label in the
    page's flattened text and returns whatever immediately follows it,
    whether that's on the same line (label : value) or the next one (a
    typical result of BeautifulSoup's get_text("\\n") on a label/value pair
    rendered as sibling elements, e.g. <span>Label</span><span>Value</span>
    — confirmed empirically to land on separate lines after flattening, not
    assumed). See this module's "NOT YET LIVE-VALIDATED" note — this
    function is tested against a constructed fixture, not a captured one."""
    for label in labels:
        idx = text.find(label)
        if idx == -1:
            continue
        after = re.sub(r"^[\s:：]+", "", text[idx + len(label):])
        if not after:
            continue
        candidate = re.split(r"\n|\s{2,}", after, maxsplit=1)[0].strip()
        if candidate:
            return candidate
    return None


def _extract_table_field(soup, labels: list[str]) -> str | None:
    """CONFIRMED-shape helper against a real captured result page
    (2026-08-25): the #customers table pairs a <th>Label</th> with the
    very next <td> sibling holding its value. Exact label match only (not
    substring) so "कार्यालय" (Office) never matches "कार्यालय संपर्क"
    (Office Contact)."""
    for th in soup.find_all("th"):
        if th.get_text(strip=True) in labels:
            td = th.find_next_sibling("td")
            if td:
                value = re.sub(r"\s+", " ", td.get_text(" ", strip=True)).strip()
                return value or None
    return None


def _parse_result_html(html: str) -> dict | None:
    """Returns a dict with `status_text` plus any additional detail fields
    confirmed present on a real captured result page (2026-08-25):
    district/department/office/officer/office_contact/office_email — all
    read from the #customers table's <th>/<td> pairs. Uploaded-document and
    complaint-image cells are deliberately never extracted, even when
    populated, to keep this PII-trimmed the same way Rajasthan/Karnataka's
    portal_detail is. Returns None if Status itself can't be found (treated
    as a failed attempt, not a crash — see advance())."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)
    status = _extract_label_value(text, ["स्थिती", "Status"])
    if status is None:
        return None
    result = {"status_text": status}
    district = _extract_label_value(text, ["जिल्हा", "District"])
    if district:
        result["district"] = district
    for key, labels in (
        ("department", ["Current Department"]),
        ("office", ["कार्यालय"]),
        ("officer", ["अधिकारी"]),
        ("office_contact", ["कार्यालय संपर्क"]),
        ("office_email", ["ऑफिस ईमेल"]),
    ):
        value = _extract_table_field(soup, labels)
        if value:
            result[key] = value
    return result


def _fetch_captcha_b64(session, cookies_source=None) -> str:
    resp = session.get(_BASE_URL + _CAPTCHA_PATH, timeout=_REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()
    content_type = resp.headers.get("Content-Type", "image/png")
    return f"data:{content_type};base64,{base64.b64encode(resp.content).decode('ascii')}"


class MaharashtraAapleSarkarAdapter(InteractiveStatusCheckMixin, ManualAssistedAdapter):
    """Mixin first, same MRO convention as Karnataka/Rajasthan —
    check_status() from InteractiveStatusCheckMixin wins (always
    checked=False, honestly); prepare_submission() from ManualAssistedAdapter
    is untouched, filing stays a real human on the real portal (unaffected —
    Maharashtra's live filing session was already marked
    live_session_supported=false well before this module existed, for an
    unrelated reason: the same EC2 connectivity block documented above)."""

    def describe_flow(self) -> StatusCheckFlow:
        return StatusCheckFlow(stages=[
            StatusCheckStage(
                name="verify_identity",
                inputs=["mobile_or_email"],
                produced_values=["token"],
                human_verification=[HumanVerificationRequirement(kind="captcha")],
                transport=TransportKind.HTML_FORM_POST,
                session_requirement=SessionRequirement.NONE,
            ),
            StatusCheckStage(
                name="verify_otp",
                inputs=[],
                produced_values=["cid"],
                human_verification=[
                    HumanVerificationRequirement(kind="otp"),
                    HumanVerificationRequirement(kind="captcha"),
                ],
                transport=TransportKind.HTML_FORM_POST,
                session_requirement=SessionRequirement.FRESH_THIS_FLOW,  # needs stage 0's token
            ),
            StatusCheckStage(
                name="submit_and_fetch",
                inputs=["reference_number"],  # Needle-known (govt_reference_number), not staff-typed — see module docstring
                produced_values=[],
                human_verification=[HumanVerificationRequirement(kind="captcha")],
                transport=TransportKind.HTML_FORM_POST,
                session_requirement=SessionRequirement.FRESH_THIS_FLOW,  # needs stage 1's cid
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
            page_resp = session.get(_BASE_URL + _VERIFY_PATH, timeout=_REQUEST_TIMEOUT_SECONDS)
            page_resp.raise_for_status()
            csrf = _extract_hidden_field(page_resp.text, "_csrfToken")
            challenge_uri = _fetch_captcha_b64(session)
        except Exception as e:
            logger.warning(f"Maharashtra Aaple Sarkar status-check start failed for ref={reference_number}: {e}")
            # Not an ordinary transient blip — this is the exact, diagnosed
            # network-level condition documented at the top of this module
            # (EC2 cannot reach grievances.maharashtra.gov.in at all,
            # confirmed multiple times: TCP 80/443 time out, DNS resolves).
            # A distinct exception type so api_router.py can tell staff the
            # real reason instead of a generic "try again in a moment" for
            # something retrying can never fix (production-readiness
            # review, K3, 2026-08-26).
            raise PortalUnavailableError(
                "Maharashtra Aaple Sarkar cannot currently be reached from the government-sync server — "
                "status checking for this portal is temporarily unavailable. This is a known issue, not "
                "something retrying will fix; contact support if it persists."
            )

        if not csrf:
            logger.warning(f"Maharashtra Aaple Sarkar: no _csrfToken found on entry page for ref={reference_number}")
            raise RuntimeError("Could not reach the Maharashtra portal — try again in a moment.")

        attempt_id = uuid.uuid4().hex
        create_attempt(
            attempt_id=attempt_id,
            tenant_id=tenant_id,
            case_id=case_id,
            adapter_key="maharashtra_aaplesarkar",
            reference_number=reference_number,
            mobile_or_email=mobile_or_email,
            cookies=dict(session.cookies.get_dict()),
            csrf_token=csrf,
            stage=0,
        )

        return StatusCheckAttempt(
            attempt_id=attempt_id,
            case_id=case_id,
            tenant_id=tenant_id,
            reference_number=reference_number,
            current_stage_index=0,
            state=StatusCheckAttemptState.AWAITING_HUMAN_INPUT,
            pending_human_verification=[HumanVerificationRequirement(kind="captcha", challenge=challenge_uri)],
        )

    def advance(self, attempt: StatusCheckAttempt, verification_answers: dict,
                next_inputs: dict | None = None) -> StatusCheckAttempt:
        # Tenant/case scoping enforced inside load_attempt()'s own WHERE
        # clause, same discipline as every other tenant-scoped lookup in
        # this codebase — an unrecognised, mismatched, or expired attempt_id
        # all return None identically.
        stored = load_attempt(attempt.attempt_id, attempt.tenant_id, attempt.case_id, _ATTEMPT_TTL_SECONDS)
        if not stored:
            attempt.state = StatusCheckAttemptState.FAILED
            attempt.result = StatusResult(
                status="", checked=False,
                raw_portal_status="Status check expired or not found — start again.",
            )
            return attempt

        try:
            if stored["stage"] == 0:
                return self._advance_stage0(attempt, stored, verification_answers or {})
            if stored["stage"] == 1:
                return self._advance_stage1(attempt, stored, verification_answers or {})
            return self._advance_stage2(attempt, stored, verification_answers or {})
        except _MaharashtraStageFailure as fail:
            if not fail.preserve_attempt:
                delete_attempt(attempt.attempt_id)
            attempt.state = StatusCheckAttemptState.FAILED
            attempt.result = StatusResult(status="", checked=False, raw_portal_status=fail.note)
            return attempt

    # ─── Stage transitions — each POSTs, re-scrapes fresh state, and
    # either advances to the next AWAITING_HUMAN_INPUT or completes ───

    def _advance_stage0(self, attempt: StatusCheckAttempt, stored: dict,
                         verification_answers: dict) -> StatusCheckAttempt:
        captcha_text = (verification_answers.get("captcha") or "").strip()
        if not captcha_text:
            attempt.state = StatusCheckAttemptState.AWAITING_HUMAN_INPUT
            return attempt

        import requests

        session = requests.Session()
        session.headers.update({"User-Agent": _USER_AGENT})
        session.cookies.update(stored["cookies"])

        try:
            resp = session.post(
                _BASE_URL + _VERIFY_PATH,
                data={
                    "_method": "POST",
                    "_csrfToken": stored["csrf_token"],
                    "verification_id": stored["mobile_or_email"],
                    "registration_no": "",  # hidden (d-none) at this stage but a real browser still submits it
                    "securitycode": captcha_text,
                },
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
        except Exception as e:
            logger.warning(f"Maharashtra Aaple Sarkar stage-0 submit failed for ref={stored['reference_number']}: {e}")
            raise _MaharashtraStageFailure("Portal check failed — try again.")

        token = _extract_token_from_url(resp.url)
        if not token:
            # No token in the landed URL — CONFIRMED signal of success is a
            # PRG redirect carrying ?token=; its absence means the portal
            # rejected the CAPTCHA or mobile/email, not an infrastructure
            # failure. Fail closed, single-use, same discipline as Karnataka.
            raise _MaharashtraStageFailure("Verification failed — check the CAPTCHA and try again from the start.")

        fresh_csrf = _extract_hidden_field(resp.text, "_csrfToken")
        if not fresh_csrf:
            raise _MaharashtraStageFailure("Portal check failed — try again.")

        try:
            challenge_uri = _fetch_captcha_b64(session)
        except Exception as e:
            logger.warning(f"Maharashtra Aaple Sarkar stage-1 captcha fetch failed for ref={stored['reference_number']}: {e}")
            raise _MaharashtraStageFailure("Portal check failed — try again.")

        advanced = update_attempt_stage(
            attempt.attempt_id,
            expected_stage=0,
            stage=1,
            cookies=dict(session.cookies.get_dict()),
            csrf_token=fresh_csrf,
            token=token,
        )
        if not advanced:
            # Someone else (a concurrent duplicate advance()) already moved
            # this attempt past stage 0 — fail closed rather than presenting
            # a CAPTCHA challenge for a stage that's no longer current.
            # preserve_attempt=True: the row now holds that concurrent
            # winner's state, not this call's — must not be deleted here.
            raise _MaharashtraStageFailure("Status check expired or not found — start again.", preserve_attempt=True)

        attempt.current_stage_index = 1
        attempt.collected_values["token"] = token
        attempt.state = StatusCheckAttemptState.AWAITING_HUMAN_INPUT
        attempt.pending_human_verification = [
            HumanVerificationRequirement(kind="otp", challenge=_OTP_HUMAN_DESCRIPTION),
            HumanVerificationRequirement(kind="captcha", challenge=challenge_uri),
        ]
        return attempt

    def _advance_stage1(self, attempt: StatusCheckAttempt, stored: dict,
                         verification_answers: dict) -> StatusCheckAttempt:
        otp_text = (verification_answers.get("otp") or "").strip()
        captcha_text = (verification_answers.get("captcha") or "").strip()
        if not otp_text or not captcha_text:
            attempt.state = StatusCheckAttemptState.AWAITING_HUMAN_INPUT
            return attempt

        import requests

        session = requests.Session()
        session.headers.update({"User-Agent": _USER_AGENT})
        session.cookies.update(stored["cookies"])

        try:
            resp = session.post(
                f"{_BASE_URL}{_VERIFY_PATH}?token={stored['token']}",
                data={
                    "_method": "POST",
                    "_csrfToken": stored["csrf_token"],
                    "verification_id": stored["mobile_or_email"],
                    "otp": otp_text,
                    "registration_no": "",  # still hidden at this stage
                    "securitycode": captcha_text,
                },
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
        except Exception as e:
            logger.warning(f"Maharashtra Aaple Sarkar stage-1 submit failed for ref={stored['reference_number']}: {e}")
            raise _MaharashtraStageFailure("Portal check failed — try again.")

        # CONFIRMED via live trace: success lands on /track-grievance (a
        # different path, no token param). Anything else — still on the
        # token-bearing verify URL, an error page — means wrong OTP,
        # expired OTP (~2 min per the portal), or wrong CAPTCHA. Not
        # distinguishable from this response alone; fail closed uniformly,
        # same as every other verification failure in this module.
        if _TRACK_PATH not in urlparse(resp.url).path:
            raise _MaharashtraStageFailure("OTP or CAPTCHA verification failed — try again from the start.")

        cid = _extract_hidden_field(resp.text, "cid")
        fresh_csrf = _extract_hidden_field(resp.text, "_csrfToken")
        if not cid or not fresh_csrf:
            raise _MaharashtraStageFailure("Portal check failed — try again.")

        try:
            challenge_uri = _fetch_captcha_b64(session)
        except Exception as e:
            logger.warning(f"Maharashtra Aaple Sarkar stage-2 captcha fetch failed for ref={stored['reference_number']}: {e}")
            raise _MaharashtraStageFailure("Portal check failed — try again.")

        advanced = update_attempt_stage(
            attempt.attempt_id,
            expected_stage=1,
            stage=2,
            cookies=dict(session.cookies.get_dict()),
            csrf_token=fresh_csrf,
            cid=cid,
        )
        if not advanced:
            # Same concurrent-loss case as stage 0's guard above —
            # preserve_attempt=True so the winner's stage-2 state survives.
            raise _MaharashtraStageFailure("Status check expired or not found — start again.", preserve_attempt=True)

        attempt.current_stage_index = 2
        attempt.collected_values["cid"] = cid
        attempt.state = StatusCheckAttemptState.AWAITING_HUMAN_INPUT
        attempt.pending_human_verification = [HumanVerificationRequirement(kind="captcha", challenge=challenge_uri)]
        return attempt

    def _advance_stage2(self, attempt: StatusCheckAttempt, stored: dict,
                         verification_answers: dict) -> StatusCheckAttempt:
        captcha_text = (verification_answers.get("captcha") or "").strip()
        if not captcha_text:
            attempt.state = StatusCheckAttemptState.AWAITING_HUMAN_INPUT
            return attempt

        import requests

        session = requests.Session()
        session.headers.update({"User-Agent": _USER_AGENT})
        session.cookies.update(stored["cookies"])

        try:
            resp = session.post(
                _BASE_URL + _TRACK_PATH,
                data={
                    "_method": "POST",
                    "_csrfToken": stored["csrf_token"],
                    "registration_no": stored["reference_number"],  # Needle-known, never asked of staff — see module docstring
                    "securitycode": captcha_text,
                    "cid": stored["cid"],
                },
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
        except Exception as e:
            logger.warning(f"Maharashtra Aaple Sarkar stage-2 submit failed for ref={stored['reference_number']}: {e}")
            raise _MaharashtraStageFailure("Portal check failed — try again.")

        parsed = _parse_result_html(resp.text)
        if parsed is None:
            raise _MaharashtraStageFailure("Verification failed — check the CAPTCHA and try again from the start.")

        delete_attempt(attempt.attempt_id)

        raw_status = parsed["status_text"]
        normalized = normalize_status_keywords(raw_status)

        portal_detail = {
            k: parsed[k] for k in
            ("district", "department", "office", "officer", "office_contact", "office_email")
            if parsed.get(k)
        } or None

        attempt.state = StatusCheckAttemptState.COMPLETE
        attempt.result = StatusResult(
            status=normalized or "",
            raw_portal_status=raw_status,
            checked=bool(normalized),
            needs_verification=False,
            portal_detail=portal_detail,
        )
        return attempt
