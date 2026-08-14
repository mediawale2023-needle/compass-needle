"""
modules/govt_sync/adapters/base.py — common adapter interface.

Every portal adapter implements the same two operations, so the rest of
the pipeline (api_router.py, poller.py) never branches on which portal
it's talking to.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


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
    def check_status(self, reference_number: str) -> StatusResult:
        """Read-only status check. Must not require staff interaction.

        Callers (poller.py) treat `checked=False` as "nothing changed, portal
        needs a manual look" rather than as an error — it's the expected
        outcome for login-gated portals with no public reference-number
        lookup.
        """
        ...
