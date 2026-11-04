"""
modules/govt_sync/adapters/delhi_cm_jan_sunwai.py — Delhi CM Jan Sunwai.

THIS IS NOT A STATUS ADAPTER. It is an explicit "staff-assisted, no automation" adapter, and it
exists so Delhi is structurally excluded from automatic polling instead of silently logging an
"inconclusive" audit row for every Delhi case on every sweep.

Why there is no automation (VERIFIED 2026-10-31, DELHI_CM_JAN_SUNWAI_CAPABILITY_MAP.md):
  * the portal's status lookup (/ComplaintTracker) needs an image CAPTCHA and an SMS/e-mail OTP
    in the SAME form, on every lookup; nothing seen suggests one verification can be reused;
  * the page a successful lookup returns (fullCompDetailsOfUser) is server-rendered HTML whose
    layout, status wording, department/officer/comment/disposal fields were never observed —
    it sits behind an OTP, and no real complaint may be created to see it.
A Delhi status adapter built on those unknowns would be invented. Add one only after a supervised,
authorised session has captured the real post-OTP pages; until then:
    supports_unattended_status_check = False   (the poller never calls it)
    check_status()                             (never contacts the portal; never claims a check)
Filing, reminders and feedback are staff tasks on the official portal; see
modules/govt_sync/delhi_portal.py for the verified pages and inputs.
"""
from .base import StatusResult
from .manual import ManualAssistedAdapter


class DelhiStaffAssistedAdapter(ManualAssistedAdapter):
    supports_unattended_status_check = False

    def check_status(self, reference_number: str, tenant_id: int | None = None) -> StatusResult:
        # No request of any kind. checked=False is the contract's "nothing was read" answer.
        return StatusResult(status="", checked=False)
