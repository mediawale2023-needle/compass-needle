"""
modules/govt_sync/tamil_nadu_constants.py — Tamil Nadu constants shared by
BOTH the live-Playwright status reader and the cookie-session HTTP adapter,
in a module that imports nothing from either of them.

WHY THIS EXISTS: `modules/govt_sync/adapters/tamil_nadu_http.py` needed
`_ACTION_TAKEN_UNAVAILABLE`, which lived in
`modules/govt_sync/status/tamil_nadu.py`. That created a real import cycle:

    modules.govt_sync.status.tamil_nadu
        -> modules.govt_sync.adapters.base        (normalize_status_keywords)
           -> modules.govt_sync.adapters.__init__  (package init)
              -> modules.govt_sync.adapters.tamil_nadu_http
                 -> modules.govt_sync.status.tamil_nadu   (back to the start)

Importing anything under `modules.govt_sync.status.*` FIRST (before the
adapters package had been loaded) therefore blew up with:

    ImportError: cannot import name '_ACTION_TAKEN_UNAVAILABLE' from
    partially initialized module 'modules.govt_sync.status.tamil_nadu'
    (most likely due to a circular import)

...while importing the adapters package first happened to work, making the
failure depend entirely on import/test-collection order. Reproduced on
production baseline 52c69b00, so it predates the Phase 2A work in PR #131.

This module breaks that cycle structurally rather than hiding it behind a
function-local (lazy) import: it has NO imports of its own, so both
consumers can depend on it and neither has to depend on the other.

SCOPE: deliberately only the constant(s) needed to break that specific
dependency edge. This is not a general-purpose Tamil Nadu dumping ground —
do not move unrelated TN selectors, regexes, or helpers here just because
a shared module now exists. Anything that genuinely belongs to one side of
the status/adapters split should stay on that side.
"""

# The exact sentinel string the live-Playwright TN status reader returns for
# `action_taken_report` when the ATR iframe exists but its contents cannot be
# read (see status/tamil_nadu.py's _extract_action_taken_report_from_frames),
# and that the HTTP adapter mirrors when the ticket payload signals the same
# condition (see adapters/tamil_nadu_http.py's _parse_ticket_payload).
#
# Value is load-bearing and must not be reworded: it is stored verbatim in
# govt_status_snapshots/govt_submission_log payloads and surfaced to staff.
_ACTION_TAKEN_UNAVAILABLE = "Action Taken Report iframe not accessible"
