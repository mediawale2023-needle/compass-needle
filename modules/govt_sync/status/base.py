"""
modules/govt_sync/status/ — human-assisted AUTHENTICATED status checks.

Deliberately separate from every existing status mechanism:

  * modules.govt_sync.adapters (check_status): unattended / HTTP status checks
    and the legacy manual worksheet contract.
  * modules.govt_sync.adapters.status_flow (InteractiveStatusCheckMixin): a
    per-lookup CAPTCHA/OTP conversation over AJAX — no browser.

This package drives an ALREADY-OPEN, tenant-scoped Playwright live session
(modules.govt_sync.browser_session — the same live-session infra the
non-interactive adapters use to let staff open a portal and sign in) for
portals whose status page is only reachable behind a real human login —
currently the Tamil Nadu CM Helpline. It is strictly read-only:

  * It never signs in, never reads an OTP, never solves a CAPTCHA, never
    scrapes around authentication.
  * It never submits, edits, replies to, or otherwise mutates a grievance.
  * When the portal needs a human (sign-in, OTP, CAPTCHA, an expired
    session) the adapter STOPS and hands control back with an explicit
    state — it does not proceed and does not report a status.
  * It returns STATUS_CHECKED only when the authenticated portal page was
    actually reached, a status was actually read, and that wording mapped
    cleanly onto the govt_status enum. Anything else is a non-success
    state, never a fabricated status.
"""
from dataclasses import dataclass, field


class StatusCheckState:
    # ── Human-checkpoint states — the adapter has stopped; a person must act
    #    in the live browser and then the check is retried. Never persisted as
    #    an inconclusive check, never shown as success.
    AUTH_REQUIRED = "AUTH_REQUIRED"
    OTP_REQUIRED = "OTP_REQUIRED"
    CAPTCHA_REQUIRED = "CAPTCHA_REQUIRED"
    SESSION_EXPIRED = "SESSION_EXPIRED"

    # ── Progress / fail-closed loading states — an expected page or list did
    #    not finish rendering. Not a status; retryable.
    STATUS_FORM_LOADING = "STATUS_FORM_LOADING"
    PETITIONS_LOADING = "PETITIONS_LOADING"

    # ── Terminal, non-success outcomes. Persisted with the existing
    #    status_check_inconclusive audit action (mirrors govt_poll_case's
    #    `not result.checked or not result.status` branch).
    CASE_NOT_FOUND = "CASE_NOT_FOUND"
    AMBIGUOUS_MATCH = "AMBIGUOUS_MATCH"
    STATUS_CHECK_INCONCLUSIVE = "STATUS_CHECK_INCONCLUSIVE"
    PORTAL_ERROR = "PORTAL_ERROR"

    # ── The only success state. Reached authenticated page + read a status +
    #    normalized it cleanly.
    STATUS_CHECKED = "STATUS_CHECKED"


# "A human must act in the live browser, then retry." Never persisted as an
# inconclusive check; never a success.
HUMAN_CHECKPOINT_STATES = frozenset({
    StatusCheckState.AUTH_REQUIRED,
    StatusCheckState.OTP_REQUIRED,
    StatusCheckState.CAPTCHA_REQUIRED,
    StatusCheckState.SESSION_EXPIRED,
})

# Everything that is neither a human checkpoint nor STATUS_CHECKED — persisted
# with the existing `status_check_inconclusive` action so
# get_govt_forward_state's "last successfully checked" stays truthful.
INCONCLUSIVE_STATES = frozenset({
    StatusCheckState.STATUS_FORM_LOADING,
    StatusCheckState.PETITIONS_LOADING,
    StatusCheckState.CASE_NOT_FOUND,
    StatusCheckState.AMBIGUOUS_MATCH,
    StatusCheckState.STATUS_CHECK_INCONCLUSIVE,
    StatusCheckState.PORTAL_ERROR,
})


@dataclass
class StatusCheckReply:
    text: str = ""
    author: str | None = None
    timestamp: str | None = None

    def to_dict(self) -> dict:
        return {"text": self.text, "author": self.author, "timestamp": self.timestamp}


@dataclass
class StatusCheckResult:
    state: str
    note: str | None = None
    # Raw portal wording, preserved verbatim and never conflated. The Tamil
    # Nadu walkthrough saw the My Petitions card and the ticket detail page
    # show DIFFERENT words for the same grievance ("Pending Action" on the
    # list vs "Received" on the detail). Both are carried through untouched;
    # no mapping between them is assumed.
    raw_list_status: str | None = None
    raw_detail_status: str | None = None
    # Set only when raw wording maps cleanly onto the govt_status enum via
    # adapters.base.normalize_status_keywords(). None otherwise (-> the result
    # is inconclusive, not a success).
    normalized_status: str | None = None
    created_at: str | None = None
    last_updated: str | None = None
    department: str | None = None
    action_taken_report: str | None = None
    replies: list = field(default_factory=list)
    reference_number: str | None = None
    short_id: str | None = None
    matched_count: int | None = None
    current_url: str | None = None

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "note": self.note,
            "raw_list_status": self.raw_list_status,
            "raw_detail_status": self.raw_detail_status,
            "normalized_status": self.normalized_status,
            "created_at": self.created_at,
            "last_updated": self.last_updated,
            "department": self.department,
            "action_taken_report": self.action_taken_report,
            "replies": [r.to_dict() if isinstance(r, StatusCheckReply) else r for r in self.replies],
            "reference_number": self.reference_number,
            "short_id": self.short_id,
            "matched_count": self.matched_count,
            "current_url": self.current_url,
        }
