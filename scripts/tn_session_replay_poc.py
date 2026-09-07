"""
scripts/tn_session_replay_poc.py — ONE-TIME, READ-ONLY proof-of-concept.

Answers exactly one question: can an already-authenticated Tamil Nadu CM
Helpline ("Mudhalvarin Mugavari") Help Center browser session, already open
as a live Needle govt-sync session (modules.govt_sync.browser_session), be
transferred into a plain server-side HTTP client and used to fetch the same
authenticated, already-known pages a staff member is already looking at?

Tests ONLY the two already-observed, already-authorized URLs:
    GET /portal/ta/myarea
    GET /portal/ta/ticket/<existing record id for grievance #18968314>

NOT wired into the application. Not imported by api_router.py, main.py, or
any other production module. Not registered as an API route. Not part of
the pytest suite (tests/test_tamil_nadu_status.py explicitly mocks every
Playwright call and never contacts a real portal — this script is the
opposite of that, on purpose, and must never be added there). Standalone,
manually invoked, disposable.

DOES NOT:
  - open a new browser session or perform a new login (uses
    modules.govt_sync.browser_session.get_live_session(), which only ever
    returns a session someone else already opened through the existing,
    unmodified live-session flow)
  - create a grievance, submit, edit, reply, or upload anything
  - touch modules/govt_sync/status/tamil_nadu.py, browser_session.py, or
    any other adapter — it only *reads* from an object
    (LiveSession.context) that browser_session.py already exposes today
    via get_live_session(), the same accessor status/tamil_nadu.py's own
    API route already uses
  - request or create any Zoho OAuth credential or API key
  - probe any endpoint beyond the two named above
  - persist anything to Postgres, disk, or any file
  - enable unattended/background TN polling

CREDENTIAL HANDLING — read this before touching this file:
  The cookies read via Playwright's own `await context.cookies()` exist
  ONLY as local variables inside `_export_cookie_jar()` and
  `tn_session_replay_experiment()`, for the duration of one function call,
  inside whatever process actually executes this code. They are:
    * never printed (no cookie/header value ever passed to print/logging)
    * never logged (see `_log()` below — it only ever receives short,
      hand-written, non-credential strings)
    * never returned from any function in this file — every function here
      returns only a plain classification string, never response objects,
      headers, or cookie data
    * never written to disk, environment variables, or any database
    * never included in an exception message — every `except` block below
      reports only the exception's TYPE NAME (e.g. "ConnectionError"),
      never `str(exception)`, which for an HTTP client can sometimes
      embed response/request context
    * never included in this script's stdout/return value beyond the
      sanitized classification enums this module defines
  The requests.Session() built from those cookies is explicitly closed
  (`http.close()`) and its local reference goes out of scope at the end of
  every code path — nothing here is designed to outlive one function call.

WHAT THIS SCRIPT CANNOT DO ON ITS OWN — read before trying to run it:
  get_live_session() reads modules.govt_sync.browser_session's
  module-level `_sessions` dict, which is process-local, in-memory state
  populated only by whatever process actually called start_session() (the
  real Needle backend process). Running `python scripts/tn_session_replay_poc.py`
  as its own, separate OS process gives that process its own, EMPTY copy
  of `_sessions` — get_live_session() would return None every time,
  regardless of whether a real session is open elsewhere, and this script
  would always report REPLAY_INCONCLUSIVE. This is not a bug to work
  around here — it means this script can only produce a meaningful result
  if it is executed *inside* the same running backend process that holds
  the live session (e.g. pasted into a REPL/console attached to that
  process, or invoked through some other in-process mechanism) — not
  invoked as a standalone subprocess. See the accompanying report for the
  options this implies; this file intentionally does not decide that for
  you.
"""
import logging

logger = logging.getLogger("needle.govt_sync.poc.tn_session_replay")

# ─── Sanitized result values — the ONLY strings this module ever returns ───

REPLAY_SUCCESS = "REPLAY_SUCCESS"
REPLAY_ANONYMOUS = "REPLAY_ANONYMOUS"
REPLAY_REDIRECTED_TO_LOGIN = "REPLAY_REDIRECTED_TO_LOGIN"
REPLAY_FAILED = "REPLAY_FAILED"
REPLAY_INCONCLUSIVE = "REPLAY_INCONCLUSIVE"

# Per-request classification (internal only — never itself a final result,
# always mapped down into one of the five REPLAY_* values above before
# being surfaced from tn_session_replay_experiment()).
_PAGE_AUTHENTICATED = "PAGE_AUTHENTICATED"
_PAGE_ANONYMOUS_OR_LOGIN = "PAGE_ANONYMOUS_OR_LOGIN"
_PAGE_UNEXPECTED_HTML = "PAGE_UNEXPECTED_HTML"
_PAGE_ERROR = "PAGE_ERROR"

# Known short ID for the one existing, already-filed grievance this PoC is
# scoped to (TN/FOODCO/CBE/P/PORTAL/01SEP26/18968314) — not a secret, this
# is the same reference number already used throughout this investigation.
_KNOWN_SHORT_ID = "18968314"

# Stable authenticated-page markers, confirmed this session against the
# real, live, authenticated DOM — NOT guessed selectors. Checked as plain
# substrings of the response body text, deliberately not via a DOM parser
# (BeautifulSoup or otherwise) — this PoC exists to answer one yes/no
# transport question, not to build the production parser.
_MYAREA_MARKERS = (
    "TicketListLeftContainer1__boxView",
    "TicketListItem__container",
)
_TICKET_DETAIL_MARKERS = (
    "TicketDetailLeftContainer__wrapper",
    'data-id="ticket_status_value"',
)

# A generic, secondary signal ONLY — used to distinguish REPLAY_ANONYMOUS
# from REPLAY_REDIRECTED_TO_LOGIN once the marker-based check has already
# decided the page is NOT authenticated. Never used, on its own, to decide
# whether a page IS authenticated — that decision is marker-based only,
# per explicit instruction not to rely on a URL/"login" substring check as
# the sole authentication signal.
_LOGIN_URL_HINTS = ("signin", "login", "accounts.zohoportal")


def _log(message: str) -> None:
    """The only logging path in this file. `message` must always be a
    short, hand-written, non-credential string — never an exception's
    str(), never a header, never anything derived from response content."""
    logger.info(f"tn_session_replay_poc: {message}")


def _classify_page(status_code, final_url: str, body_text: str, markers: tuple) -> str:
    """Marker-first classification. Never inspects headers or cookies —
    only the response body text and the final URL path, neither of which
    carries credential material."""
    marker_hits = sum(1 for m in markers if m in body_text)
    reference_present = _KNOWN_SHORT_ID in body_text

    if marker_hits >= 1 and reference_present:
        return _PAGE_AUTHENTICATED

    looks_like_login = any(hint in (final_url or "").lower() for hint in _LOGIN_URL_HINTS)
    if marker_hits == 0 and not reference_present:
        return _PAGE_ANONYMOUS_OR_LOGIN if looks_like_login or True else _PAGE_UNEXPECTED_HTML
        # (looks_like_login `or True` intentionally collapses to "no markers,
        # no reference" => anonymous/login bucket regardless of URL shape —
        # a 200 response with neither the authenticated structure nor the
        # citizen's own grievance reference is not a page this session can
        # do anything useful with either way. The URL hint is kept above
        # only to later distinguish ANONYMOUS vs REDIRECTED_TO_LOGIN, not
        # to gate this branch.)

    # Something in between: a real page, some but not conclusive signal
    # (e.g. the reference number appears somewhere but neither expected
    # container class does, or vice versa) — reported honestly as unknown
    # rather than forced into either bucket.
    return _PAGE_UNEXPECTED_HTML


def _map_non_authenticated(final_url: str) -> str:
    looks_like_login = any(hint in (final_url or "").lower() for hint in _LOGIN_URL_HINTS)
    return REPLAY_REDIRECTED_TO_LOGIN if looks_like_login else REPLAY_ANONYMOUS


def _export_cookie_jar(playwright_cookies: list) -> "requests.cookies.RequestsCookieJar":
    """Builds a requests cookie jar from Playwright's own context.cookies()
    output. The cookie values pass through this function's local variables
    only — never logged, never returned in any other form, never written
    anywhere."""
    import requests

    jar = requests.cookies.RequestsCookieJar()
    for c in playwright_cookies:
        try:
            jar.set(
                c["name"], c["value"],
                domain=c.get("domain") or "",
                path=c.get("path") or "/",
            )
        except Exception:
            # A single cookie whose attributes requests/Playwright disagree
            # on should not abort the whole export — never logs the
            # offending cookie's name or value, only that a skip happened.
            _log("skipped one cookie during export (attribute mismatch)")
            continue
    return jar


async def tn_session_replay_experiment(session_id: str, ticket_record_id: str) -> str:
    """The only entry point. Returns exactly one of REPLAY_SUCCESS /
    REPLAY_ANONYMOUS / REPLAY_REDIRECTED_TO_LOGIN / REPLAY_FAILED /
    REPLAY_INCONCLUSIVE. Never raises past this function; every failure
    mode is caught and mapped to one of the five values above.

    Must be awaited from inside the SAME process that holds the live
    session (see this module's docstring) — get_live_session() will
    return None in any other process, which this function reports as
    REPLAY_INCONCLUSIVE, not REPLAY_FAILED (a missing session is not a
    failed authentication attempt).
    """
    from modules.govt_sync.browser_session import get_live_session

    session = get_live_session(session_id)
    if not session:
        _log("no live session found for the given session_id")
        return REPLAY_INCONCLUSIVE

    try:
        playwright_cookies = await session.context.cookies()
    except Exception as e:
        _log(f"cookie export failed ({type(e).__name__})")
        return REPLAY_INCONCLUSIVE

    if not playwright_cookies:
        _log("live session context returned no cookies")
        return REPLAY_INCONCLUSIVE

    import requests

    http = requests.Session()
    http.headers.update({"User-Agent": "Mozilla/5.0 (compatible; NeedleGovtSync-POC/1.0)"})
    http.cookies = _export_cookie_jar(playwright_cookies)
    # Cookie values now live only inside `http`'s local cookie jar and the
    # (already-consumed) `playwright_cookies` local variable. Nothing above
    # this line has printed, logged, or returned any of it.
    del playwright_cookies

    base_url = (session.portal or {}).get("base_url", "").rstrip("/")
    if not base_url:
        http.close()
        _log("live session has no base_url on its portal config")
        return REPLAY_INCONCLUSIVE

    try:
        try:
            resp1 = http.get(f"{base_url}/portal/ta/myarea", timeout=15, allow_redirects=True)
        except Exception as e:
            _log(f"My Petitions request failed ({type(e).__name__})")
            return REPLAY_FAILED

        myarea_class = _classify_page(resp1.status_code, resp1.url, resp1.text, _MYAREA_MARKERS)
        _log(f"My Petitions classified as {myarea_class}")

        if myarea_class == _PAGE_ERROR:
            return REPLAY_FAILED
        if myarea_class == _PAGE_UNEXPECTED_HTML:
            return REPLAY_INCONCLUSIVE
        if myarea_class == _PAGE_ANONYMOUS_OR_LOGIN:
            return _map_non_authenticated(resp1.url)

        # myarea_class == _PAGE_AUTHENTICATED — proceed to the detail page.
        try:
            resp2 = http.get(
                f"{base_url}/portal/ta/ticket/{ticket_record_id}",
                timeout=15, allow_redirects=True,
            )
        except Exception as e:
            _log(f"ticket detail request failed ({type(e).__name__})")
            return REPLAY_FAILED

        detail_class = _classify_page(resp2.status_code, resp2.url, resp2.text, _TICKET_DETAIL_MARKERS)
        _log(f"Ticket detail classified as {detail_class}")

        if detail_class == _PAGE_AUTHENTICATED:
            return REPLAY_SUCCESS
        if detail_class == _PAGE_ANONYMOUS_OR_LOGIN:
            return _map_non_authenticated(resp2.url)
        if detail_class == _PAGE_UNEXPECTED_HTML:
            return REPLAY_INCONCLUSIVE
        return REPLAY_FAILED
    finally:
        http.close()
        del http


# ─── Manual CLI entry point — NOT invoked automatically, NOT imported by ───
# ─── anything else in this repository.                                   ───
if __name__ == "__main__":
    import argparse
    import asyncio
    import sys

    parser = argparse.ArgumentParser(
        description=(
            "PoC ONLY. Must run inside the same process as the live Needle "
            "backend that holds the target session_id (see module docstring) "
            "— running this as a separate `python` process will always "
            "print REPLAY_INCONCLUSIVE, because it cannot see that process's "
            "in-memory session state."
        )
    )
    parser.add_argument("--session-id", required=True, help="An already-open TN live session_id (govt_sync.browser_session).")
    parser.add_argument(
        "--ticket-record-id", required=True,
        help="The existing TN internal record id for grievance #18968314 (no new lookups are performed).",
    )
    args = parser.parse_args()

    result = asyncio.run(tn_session_replay_experiment(args.session_id, args.ticket_record_id))
    print(result)
    sys.exit(0)
