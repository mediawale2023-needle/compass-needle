"""
modules/govt_sync/status — human-assisted authenticated status-check adapters.

See base.py for why this is separate from modules.govt_sync.adapters and from
modules.govt_sync.adapters.status_flow. get_status_adapter() is the only thing
callers (api_router.py) need; it dispatches on the portal's state, mirroring
modules.govt_sync.filing.get_filing_adapter().
"""
from .base import (
    HUMAN_CHECKPOINT_STATES,
    INCONCLUSIVE_STATES,
    StatusCheckReply,
    StatusCheckResult,
    StatusCheckState,
)
from .tamil_nadu import TamilNaduStatusAdapter


_STATUS_ADAPTERS_BY_STATE = {
    "tamil nadu": TamilNaduStatusAdapter,
}


def get_status_adapter(portal_row: dict):
    portal_row = portal_row or {}
    state = str(portal_row.get("state") or "").strip().lower()
    adapter_cls = _STATUS_ADAPTERS_BY_STATE.get(state)
    if not adapter_cls:
        return None
    return adapter_cls(portal_row)


__all__ = [
    "HUMAN_CHECKPOINT_STATES",
    "INCONCLUSIVE_STATES",
    "StatusCheckReply",
    "StatusCheckResult",
    "StatusCheckState",
    "TamilNaduStatusAdapter",
    "get_status_adapter",
]
