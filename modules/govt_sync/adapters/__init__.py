"""
modules/govt_sync/adapters — one adapter per portal type, common interface.

get_adapter() is the only thing callers (api_router.py, poller.py) need —
it hides which adapter class backs a given govt_portals row so adding a new
state is "write one adapter + point portal_type at it," not "touch the
pipeline."
"""
from .base import GovtPortalAdapter, StatusResult, SubmissionResult
from .manual import ManualAssistedAdapter

# portal_type -> adapter class. All current portals (state_branded, cpgrams)
# use the manual-assisted adapter — see modules/govt_sync/__init__.py for why
# this isn't Playwright browser automation on this backend. A future portal
# with a genuine API or a remote-browser-controlled submission flow can add
# its own class here without changing callers.
_ADAPTERS = {
    "state_branded": ManualAssistedAdapter,
    "cpgrams": ManualAssistedAdapter,
}


def get_adapter(portal_row: dict) -> GovtPortalAdapter:
    portal_type = (portal_row or {}).get("portal_type") or "state_branded"
    adapter_cls = _ADAPTERS.get(portal_type, ManualAssistedAdapter)
    return adapter_cls(portal_row)


__all__ = ["GovtPortalAdapter", "StatusResult", "SubmissionResult", "get_adapter"]
