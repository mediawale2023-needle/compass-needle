"""
Human-assisted filing adapters.

This package is deliberately separate from modules.govt_sync.adapters, whose
current responsibility is status checking plus the legacy manual worksheet
contract. Filing adapters drive an already-open Playwright page only when a
portal has been specifically approved for that workflow.
"""

from .base import (
    FilingActionResult,
    FilingState,
    HumanCheckpoint,
    PortalValidationError,
)
from .tamil_nadu import TamilNaduFilingAdapter


_FILING_ADAPTERS_BY_STATE = {
    "tamil nadu": TamilNaduFilingAdapter,
}


def get_filing_adapter(portal_row: dict):
    portal_row = portal_row or {}
    state = str(portal_row.get("state") or "").strip().lower()
    adapter_cls = _FILING_ADAPTERS_BY_STATE.get(state)
    if not adapter_cls:
        return None
    return adapter_cls(portal_row)


__all__ = [
    "FilingActionResult",
    "FilingState",
    "HumanCheckpoint",
    "PortalValidationError",
    "TamilNaduFilingAdapter",
    "get_filing_adapter",
]
