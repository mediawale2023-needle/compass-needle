"""
modules/govt_sync/adapters/base.py — common adapter interface.

Every portal adapter implements the same two operations, so the rest of
the pipeline (api_router.py, poller.py) never branches on which portal
it's talking to.

Also home to OtpGatedStatusMixin — the reusable framework for portals whose
real status-check API is gated by an OTP verifying a mobile number rather
than one grievance (first confirmed for Rajasthan Sampark). A new state's
adapter only needs to implement three portal-specific hooks
(_send_otp/_validate_otp/_fetch_status) to get the full session-cache +
check_status() behavior for free — see the mixin's own docstring below.
"""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger("needle.govt_sync.adapter")


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Best-effort portal-status-wording -> normalized govt_status keyword map.
# English + Hindi/Hinglish. Ordered so more specific terms are checked before
# generic ones. Shared across adapters that parse free-text portal wording
# (manual.py's HTML scrape) as well as ones that get a structured status
# field back but still need to map arbitrary portal vocabulary onto our
# fixed enum (rajasthan_sampark.py's Status/SubStatusName fields).
STATUS_KEYWORDS = [
    ("resolved", ["resolved", "disposed", "closed", "निस्तारित", "समाधान"]),
    ("rejected", ["rejected", "declined", "अस्वीकृत"]),
    ("under_review", ["under review", "in process", "processing", "प्रक्रियाधीन", "विचाराधीन"]),
    ("submitted", ["registered", "received", "acknowledged", "submitted", "प्राप्त", "दर्ज"]),
]


def normalize_status_keywords(raw_text: str) -> str | None:
    lowered = (raw_text or "").lower()
    for normalized, keywords in STATUS_KEYWORDS:
        for kw in keywords:
            if kw.lower() in lowered:
                return normalized
    return None


@dataclass
class SubmissionResult:
    reference_number: str | None
    requires_staff_action: bool
    staff_action_note: str | None = None


@dataclass
class StatusResult:
    status: str              # normalized to the govt_status enum on cases
    raw_portal_status: str | None = None   # portal's own wording, kept for audit
    portal_detail: dict | None = None      # PII-trimmed portal fields for "where is it now" display
    checked: bool = True     # False when the check itself couldn't run (e.g. login-gated)
    # True when checked=False specifically because a portal-scoped OTP
    # verification is missing/expired — distinct from "portal doesn't
    # support automated checks at all" or a transient network failure, so
    # callers can prompt staff to (re-)verify instead of showing a generic
    # "inconclusive" dead end. Only ever set by adapters that use tenant_id
    # (OtpGatedStatusMixin subclasses, e.g. rajasthan_sampark.py); every
    # other adapter leaves this False.
    needs_verification: bool = False


class GovtPortalAdapter(ABC):
    # True for adapters whose check_status() can complete synchronously,
    # unattended, with no live human input needed (ManualAssistedAdapter,
    # OtpGatedStatusMixin/Rajasthan-shaped portals — their human
    # verification, if any, already happened out of band before
    # check_status() is ever called). False only for
    # InteractiveStatusCheckMixin-based adapters (status_flow.py), whose
    # status lookup itself requires live human input at call time —
    # poller.py checks this BEFORE ever calling check_status(), so an
    # interactive portal is structurally never attempted from an
    # unattended background context. See status_flow.py's module
    # docstring for why that mixin is a different mechanism from
    # OtpGatedStatusMixin, not a variant of it.
    supports_unattended_status_check: bool = True

    def __init__(self, portal_row: dict):
        self.portal = portal_row or {}

    @abstractmethod
    def prepare_submission(self, submission: dict) -> SubmissionResult:
        """Return what staff need to do to file `submission` on this portal.

        `submission` is the AI-translated PortalSubmission dict (department,
        subject, description, priority_category, ...). No reference number
        exists yet — that's produced by the portal itself once staff submit,
        and is recorded via the staff-submit step, not by this method.
        """
        ...

    @abstractmethod
    def check_status(self, reference_number: str, tenant_id: int | None = None) -> StatusResult:
        """Read-only status check. Must not require staff interaction.

        Callers (poller.py) treat `checked=False` as "nothing changed, portal
        needs a manual look" rather than as an error — it's the expected
        outcome for login-gated portals with no public reference-number
        lookup.

        `tenant_id` is optional and unused by most adapters (status checks
        are usually portal-scoped, not tenant-scoped) — it exists for
        adapters like rajasthan_sampark.py that need to look up a
        per-tenant cached OTP session. Always pass it when available;
        adapters that don't need it simply ignore it.
        """
        ...


class OtpGatedStatusMixin:
    """Reusable framework for any portal whose real status-check API is
    gated by an OTP that verifies a MOBILE NUMBER for a stretch of time,
    not one grievance — first confirmed for Rajasthan Sampark (see
    modules/govt_sync/adapters/rajasthan_sampark.py's module docstring for
    how that was discovered by tracing real traffic). Never assume a new
    portal behaves the same way without doing that same tracing — some
    portals' "enter mobile + OTP" flows may turn out to be scoped per
    grievance, or gated by a CAPTCHA the backend actually enforces, or
    something else entirely. This mixin is the reusable *shape* once you
    know a portal fits it; it is not a reason to assume a portal fits it.

    Mix this into a concrete GovtPortalAdapter subclass (order matters —
    put this mixin FIRST so its check_status() wins over whatever the other
    base provides, e.g. ManualAssistedAdapter's HTML-scrape check_status):

        class SomeStateAPIAdapter(OtpGatedStatusMixin, ManualAssistedAdapter):
            def _send_otp(self, mobile_no, anchor_reference): ...
            def _validate_otp(self, otp, transaction_number, session_id): ...
            def _fetch_status(self, mobile_no, reference_number, transaction_number, session_id): ...

    Implement exactly those three portal-specific hooks (the actual HTTP
    calls to that portal's real backend) and this mixin provides, for free:
    the govt_otp_sessions cache (via modules/govt_sync/otp_sessions.py),
    start_verification()/complete_verification()/verification_state() (what
    api_router.py's /govt/otp/send + /verify endpoints call), and a
    check_status() that looks up the cached session, calls _fetch_status(),
    normalizes the result through STATUS_KEYWORDS, and reports
    needs_verification when the session is missing/expired.

    prepare_submission() is deliberately NOT provided here — filing still
    goes through whatever the portal's own base adapter does (normally
    ManualAssistedAdapter, unchanged).
    """

    def _portal_id(self) -> int:
        # Different callers alias this differently (a clean portal-cols
        # SELECT uses "id"; a cases-JOIN-govt_portals row needs "portal_id"
        # to avoid colliding with the case's own "id") — accept either.
        return self.portal.get("portal_id") or self.portal.get("id")

    # ─── Portal-specific hooks — implement these three in the subclass ───

    def _send_otp(self, mobile_no: str, anchor_reference: str) -> dict:
        """Triggers a fresh OTP SMS to `mobile_no`. `anchor_reference` is
        whatever reference-number-shaped value the portal's own send-OTP
        call needs to anchor to (Rajasthan Sampark requires one even though
        the resulting verification covers every grievance on that mobile —
        other portals may not need one at all; accept and ignore it if so).
        Must return {"transaction_number", "session_id"} (or whatever two
        opaque tokens the portal issues — the keys are fixed so the cache
        table has one shape across portals). Raise RuntimeError with a
        user-facing message on failure."""
        raise NotImplementedError

    def _validate_otp(self, otp: str, transaction_number: str, session_id: str) -> bool:
        """True on genuine success. Treat a "this mobile is already
        verified" response as success too if the portal has that concept
        (Rajasthan Sampark does) — only a real wrong-OTP-style response
        should return False."""
        raise NotImplementedError

    def _fetch_status(self, mobile_no: str, reference_number: str, transaction_number: str, session_id: str) -> dict | None:
        """Returns a dict with either a combined `raw_status_text`, or
        `status_text` (+ optional `sub_status_text`) that check_status()
        joins itself — whichever shape fits the portal's real response.
        Returns None specifically when the session is no longer accepted
        (expired/invalid) — check_status() treats that as "ask staff to
        re-verify", not "grievance doesn't exist" (this hook usually can't
        cheaply tell those apart, same as Rajasthan Sampark)."""
        raise NotImplementedError

    # ─── Provided for free — do not override ──────────────────────────

    def start_verification(self, tenant_id: int, mobile_no: str, anchor_reference: str) -> None:
        """Sends a fresh OTP and stores the pending (unverified) session."""
        from modules.govt_sync import otp_sessions
        result = self._send_otp(mobile_no, anchor_reference)
        otp_sessions.upsert_session(
            tenant_id, self._portal_id(), mobile_no,
            result["transaction_number"], result["session_id"], verified_at=None,
        )

    def complete_verification(self, tenant_id: int, otp_code: str) -> bool:
        """Validates the OTP against the pending session. Returns True on
        success (session marked verified for reuse). Returns False on a
        genuinely wrong OTP (session stays pending, staff can retry). Raises
        RuntimeError if there's no pending session at all."""
        from modules.govt_sync import otp_sessions
        portal_id = self._portal_id()
        session = otp_sessions.get_cached_session(tenant_id, portal_id)
        if not session:
            raise RuntimeError("No pending verification — send an OTP first.")
        ok = self._validate_otp(otp_code, session["transaction_number"], session["session_id"])
        if ok:
            otp_sessions.upsert_session(
                tenant_id, portal_id, session["mobile_no"],
                session["transaction_number"], session["session_id"],
                verified_at=_utcnow(),
            )
        return ok

    def verification_state(self, tenant_id: int) -> dict:
        """{'status': 'verified'|'pending'|'expired'|'not_started', 'mobile_no', 'verified_at'}"""
        from modules.govt_sync import otp_sessions
        return otp_sessions.verification_state(tenant_id, self._portal_id())

    def check_status(self, reference_number: str, tenant_id: int | None = None) -> StatusResult:
        from modules.govt_sync import otp_sessions

        if not tenant_id:
            # Shouldn't happen in practice (callers always pass it for an
            # OTP-gated adapter) — fail closed rather than guess whose
            # session to use.
            return StatusResult(status="", checked=False)

        portal_id = self._portal_id()
        session = otp_sessions.get_cached_session(tenant_id, portal_id)
        if not session or not session.get("verified_at"):
            return StatusResult(status="", checked=False, needs_verification=True)

        portal_name = self.portal.get("portal_name", "this portal")
        try:
            detail = self._fetch_status(
                session["mobile_no"], reference_number,
                session["transaction_number"], session["session_id"],
            )
        except Exception as e:
            logger.warning(f"{portal_name} status check failed for ref={reference_number}: {e}")
            return StatusResult(status="", checked=False)

        if detail is None:
            otp_sessions.mark_session_failed(tenant_id, portal_id)
            return StatusResult(status="", checked=False, needs_verification=True)

        otp_sessions.touch_session_used(tenant_id, portal_id)
        raw_status = detail.get("raw_status_text")
        if raw_status is None:
            raw_status = " / ".join(
                v for v in (detail.get("status_text"), detail.get("sub_status_text")) if v
            ).strip(" /")
        normalized = normalize_status_keywords(raw_status)
        if not normalized:
            logger.info(f"{portal_name} status '{raw_status}' unrecognised for ref={reference_number} — needs manual look")
            return StatusResult(status="", raw_portal_status=raw_status, checked=False)

        return StatusResult(
            status=normalized,
            raw_portal_status=raw_status,
            portal_detail=detail,
            checked=True,
        )
