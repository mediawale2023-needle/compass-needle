"""
modules/govt_sync/adapters — one adapter per portal type, common interface.

get_adapter() is the only thing callers (api_router.py, poller.py) need —
it hides which adapter class backs a given govt_portals row so adding a new
state is "write one adapter + point portal_type at it," not "touch the
pipeline."

ADDING A NEW STATE'S REAL STATUS-CHECK ADAPTER (not just the default
manual/scrape one every portal starts with):

1. Confirm there's actually a real backend API worth calling, and what it
   looks like, by tracing real network traffic on a real status check —
   the same way Rajasthan Sampark's was discovered (see
   rajasthan_sampark.py's module docstring). Never assume a portal has one,
   and never assume its auth model matches Rajasthan's just because both
   ask for "mobile + OTP" on the page — trace it.
2. If it turns out to be gated by an OTP that verifies a mobile number
   rather than one grievance, write a new adapter module implementing just
   the three OtpGatedStatusMixin hooks (base.py) —
   _send_otp/_validate_otp/_fetch_status — and mix it in ahead of
   ManualAssistedAdapter (mixin first, so its check_status() wins):
       class SomeStateAPIAdapter(OtpGatedStatusMixin, ManualAssistedAdapter): ...
   If it's gated some other way (plain session cookie, no auth at all,
   CAPTCHA the backend actually enforces, ...), the mixin doesn't apply —
   implement check_status() directly on a GovtPortalAdapter subclass
   instead; don't force-fit a different auth shape into this mixin.
3. Register it below in _STATUS_CHECK_ADAPTERS, keyed by whatever string
   you set on that portal's govt_portals.status_check_adapter column (see
   modules/govt_sync/seed.py + modules/data/govt_portals.json).

No changes needed anywhere else — api_router.py's /govt/otp/* endpoints,
poller.py, and get_resolved_govt_portal's otp_verification field all
dispatch generically off get_adapter()/hasattr() already.
"""
from .base import GovtPortalAdapter, OtpGatedStatusMixin, StatusResult, SubmissionResult
from .manual import ManualAssistedAdapter
from .rajasthan_sampark import RajasthanSamparkAPIAdapter

# portal_type -> adapter class. All current portals (state_branded, cpgrams)
# use the manual-assisted adapter — see modules/govt_sync/__init__.py for why
# this isn't Playwright browser automation on this backend. A future portal
# with a genuine API or a remote-browser-controlled submission flow can add
# its own class here without changing callers.
_ADAPTERS = {
    "state_branded": ManualAssistedAdapter,
    "cpgrams": ManualAssistedAdapter,
}

# govt_portals.status_check_adapter (if set) picks the adapter instead of
# portal_type — this only ever changes check_status() behavior (see each
# adapter's prepare_submission(), which stays the manual-filing note for
# every portal regardless of this). Checked first; portal_type is the
# fallback for the (default) manual-assisted case. See this file's module
# docstring for how to add a new state here.
_STATUS_CHECK_ADAPTERS = {
    "rajasthan_sampark_api": RajasthanSamparkAPIAdapter,
}


def get_adapter(portal_row: dict) -> GovtPortalAdapter:
    portal_row = portal_row or {}
    status_check_adapter = portal_row.get("status_check_adapter")
    if status_check_adapter and status_check_adapter in _STATUS_CHECK_ADAPTERS:
        return _STATUS_CHECK_ADAPTERS[status_check_adapter](portal_row)
    portal_type = portal_row.get("portal_type") or "state_branded"
    adapter_cls = _ADAPTERS.get(portal_type, ManualAssistedAdapter)
    return adapter_cls(portal_row)


__all__ = ["GovtPortalAdapter", "OtpGatedStatusMixin", "StatusResult", "SubmissionResult", "get_adapter"]
