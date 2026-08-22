"""
modules/govt_sync/adapters — one adapter per portal type, common interface.

get_adapter() is the only thing callers (api_router.py, poller.py) need —
it hides which adapter class backs a given govt_portals row so adding a new
state is "write one adapter + point portal_type at it," not "touch the
pipeline."
"""
from .base import GovtPortalAdapter, StatusResult, SubmissionResult
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
# fallback for the (default) manual-assisted case.
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


__all__ = ["GovtPortalAdapter", "StatusResult", "SubmissionResult", "get_adapter"]
