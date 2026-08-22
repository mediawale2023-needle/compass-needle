"""
modules/govt_sync/adapters/base.py — common adapter interface.

Every portal adapter implements the same two operations, so the rest of
the pipeline (api_router.py, poller.py) never branches on which portal
it's talking to.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


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
    ("submitted", ["registered", "received", "acknowledged", "प्राप्त", "दर्ज"]),
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
    checked: bool = True     # False when the check itself couldn't run (e.g. login-gated)
    # True when checked=False specifically because a portal-scoped OTP
    # verification is missing/expired — distinct from "portal doesn't
    # support automated checks at all" or a transient network failure, so
    # callers can prompt staff to (re-)verify instead of showing a generic
    # "inconclusive" dead end. Only ever set by adapters that use
    # tenant_id (currently rajasthan_sampark.py); every other adapter
    # leaves this False.
    needs_verification: bool = False


class GovtPortalAdapter(ABC):
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
