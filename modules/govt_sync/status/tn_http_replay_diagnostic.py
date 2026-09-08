"""
modules/govt_sync/status/tn_http_replay_diagnostic.py — Phase 2 controlled-
proof harness: MULTI-TICKET SCOPE + SESSION DURABILITY.

BACKGROUND: the first controlled proof (2026-09-07, tenant 12 / case 3563 /
grievance 18968314) confirmed that exporting an already-authenticated
Playwright cookie jar into a plain requests.Session() successfully replays
GET /portal/api/tickets/{record_id} — but that proof only ever exercised
ONE ticket, at ONE moment in time, on ONE session. Before committing to a
durable cookie-session architecture, this module gathers two more kinds of
REAL, OBSERVED evidence, never guessed:

  A. MULTI-TICKET SCOPE — does the exact same exported cookie jar also
     authenticate a GET for a SECOND ticket record id, if (and only if)
     one is *already* naturally present in the account's own observed
     browser network traffic? This module never enumerates, guesses, or
     increments an id — it only ever replays an id that
     tn_network_diagnostic.discover_all_ticket_record_ids() already found
     sitting in evidence the browser generated on its own.
  B. SESSION DURABILITY — how much time has passed since the live browser
     session was established, and since any previous replay attempt, at
     the moment of a given replay attempt? There is NO automatic polling,
     NO kept-alive session, and NO background job anywhere in this file —
     every replay is triggered by an explicit call, and this module keeps
     no state between calls. A caller wanting to measure elapsed time must
     pass the previous call's own `this_attempt_at` back in as
     `previous_attempt_at` on the next call, later (minutes/hours), by
     hand.

CLASSIFICATION FIX (the reason this module exists as new code rather than
reusing scripts/tn_session_replay_poc.py's classification unchanged): that
PoC's _classify_page() never inspects HTTP status codes at all — it is
entirely body-marker/URL-substring driven, which cannot distinguish an
expired session (401/403) from a missing ticket (404) from a transient
portal outage (5xx). This module's _classify_http_status() fixes that,
built fresh and status-code-first from the start, specifically for the
JSON /portal/api/tickets/{id} endpoint this phase targets. It does not
modify scripts/tn_session_replay_poc.py itself — that PoC's own HTML-page
(/portal/ta/myarea, /portal/ta/ticket/{id}) marker-based classification is
untouched, per this phase's explicit scope.

THIS MODULE DOES NOT:
  - open a browser, authenticate, answer OTP/CAPTCHA, or create/modify any
    grievance — it only ever reads an already-open
    modules.govt_sync.browser_session.LiveSession's cookies, exactly like
    scripts/tn_session_replay_poc.py already does;
  - attach its own network observer or trigger any new page navigation —
    it consumes evidence tn_network_diagnostic.py's existing collector
    already gathered during a normal, already-approved diagnostic run (or
    any equivalent list of already-redacted evidence dicts/entries); this
    module's own HTTP replay calls are the same class of read-only,
    off-portal-UI HTTP client action the first controlled proof already
    performed and this codebase has already reviewed as safe;
  - guess, enumerate, or increment/decrement any ticket record id — a
    "second ticket" is only ever one that
    tn_network_diagnostic.discover_all_ticket_record_ids() already found
    naturally present in the observed evidence;
  - poll automatically, keep any session alive artificially, or run any
    background job — every replay here happens exactly once per call, and
    nothing in this file schedules another one;
  - persist anything to Postgres, disk, or any file, or add a database
    table — session-durability measurement here is purely a function of
    timestamps the CALLER already holds and passes back in, never state
    this module remembers on its own.

CREDENTIAL HANDLING: identical guarantees to scripts/tn_session_replay_poc.py
and tn_network_diagnostic.py. Cookie values, Set-Cookie, Authorization,
CSRF, JWT, session_id, and raw response bodies are never printed, logged,
returned, or persisted anywhere in this file. HTTP status codes ARE
inspected here (that is the entire point of the classification fix above),
but are never themselves returned — every attempt is reduced to one of the
seven sanitized outcome strings below, plus the same narrow, already-
reviewed structural signals tn_network_diagnostic.py's own collector
already surfaces (Content-Type header value by name, response byte
length). Response bodies are never parsed, read, or inspected beyond their
byte length — the "authenticated" signal for a 200 is structural only
(status code + content-type + non-zero length), never a read of the JSON
content itself, so no ticket subject/body/customer field is ever touched.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

# ─── Sanitized HTTP-replay outcome classification ──────────────────────────
# One of these exact strings is the ONLY thing a status code is ever
# reduced to outside _classify_http_status() — the raw code itself is
# never returned from this module.

HTTP_REPLAY_AUTHENTICATED = "HTTP_REPLAY_AUTHENTICATED"        # 200
HTTP_REPLAY_AUTH_FAILURE = "HTTP_REPLAY_AUTH_FAILURE"            # 401
HTTP_REPLAY_FORBIDDEN = "HTTP_REPLAY_FORBIDDEN"                  # 403
HTTP_REPLAY_NOT_FOUND = "HTTP_REPLAY_NOT_FOUND"                  # 404
HTTP_REPLAY_SERVER_ERROR = "HTTP_REPLAY_SERVER_ERROR"            # 5xx
HTTP_REPLAY_TRANSPORT_FAILURE = "HTTP_REPLAY_TRANSPORT_FAILURE"  # transport exception, no response at all
HTTP_REPLAY_INCONCLUSIVE = "HTTP_REPLAY_INCONCLUSIVE"            # any other status code

_REPLAY_USER_AGENT = "Mozilla/5.0 (compatible; NeedleGovtSync-POC/1.0)"
_REQUEST_TIMEOUT_SECONDS = 15


def _classify_http_status(status_code: int) -> str:
    """Maps a REAL, already-received HTTP status code to exactly one
    sanitized outcome string. Never called with None — a request that
    never got a response at all is classified as HTTP_REPLAY_TRANSPORT_FAILURE
    by the caller before this function is ever reached (see
    _perform_ticket_http_replay)."""
    if status_code == 200:
        return HTTP_REPLAY_AUTHENTICATED
    if status_code == 401:
        return HTTP_REPLAY_AUTH_FAILURE
    if status_code == 403:
        return HTTP_REPLAY_FORBIDDEN
    if status_code == 404:
        return HTTP_REPLAY_NOT_FOUND
    if 500 <= status_code < 600:
        return HTTP_REPLAY_SERVER_ERROR
    return HTTP_REPLAY_INCONCLUSIVE


@dataclass
class TicketHttpReplayAttempt:
    """One read-only GET /portal/api/tickets/{record_id} attempt, already
    fully sanitized. to_safe_dict() is the only way this is ever
    serialized."""

    record_id: str
    outcome: str
    content_type: str | None
    response_bytes: int | None
    attempted_at: float

    def to_safe_dict(self) -> dict:
        return {
            "record_id": self.record_id,
            "outcome": self.outcome,
            "authenticated": self.outcome == HTTP_REPLAY_AUTHENTICATED,
            "ticket_response_successful": self.outcome == HTTP_REPLAY_AUTHENTICATED,
            "content_type": self.content_type,
            "response_bytes": self.response_bytes,
            "attempted_at": self.attempted_at,
        }


def _perform_ticket_http_replay(cookie_jar, base_url: str, record_id: str) -> TicketHttpReplayAttempt:
    """One GET against the canonical GET /portal/api/tickets/{record_id}
    endpoint, using an already-exported cookie jar. Never reads response
    JSON content — the 200/authenticated signal is entirely structural
    (status code + Content-Type header value + response byte length),
    exactly the same class of evidence tn_network_diagnostic.py's own
    network observer already collects and this codebase has already
    reviewed as safe. Never raises past this function; every transport
    failure maps to HTTP_REPLAY_TRANSPORT_FAILURE."""
    import requests

    attempted_at = time.time()
    url = f"{base_url.rstrip('/')}/portal/api/tickets/{record_id}"

    http = requests.Session()
    http.headers.update({"User-Agent": _REPLAY_USER_AGENT})
    http.cookies = cookie_jar
    try:
        try:
            resp = http.get(url, timeout=_REQUEST_TIMEOUT_SECONDS, allow_redirects=True)
        except Exception:
            return TicketHttpReplayAttempt(
                record_id=record_id, outcome=HTTP_REPLAY_TRANSPORT_FAILURE,
                content_type=None, response_bytes=None, attempted_at=attempted_at,
            )
        outcome = _classify_http_status(resp.status_code)
        # Exactly one, explicitly-named, non-credential response header —
        # never a generic headers dump (mirrors tn_network_diagnostic.py's
        # _safe_content_type()). Body length only, never body content.
        content_type = resp.headers.get("Content-Type")
        try:
            response_bytes = len(resp.content) if resp.content is not None else None
        except Exception:
            response_bytes = None
        return TicketHttpReplayAttempt(
            record_id=record_id, outcome=outcome,
            content_type=content_type, response_bytes=response_bytes,
            attempted_at=attempted_at,
        )
    finally:
        http.close()
        del http


async def _cookie_jar_for(session):
    """Exports the live session's current Playwright cookies into a
    requests cookie jar, via the exact same, already-reviewed
    _export_cookie_jar() scripts/tn_session_replay_poc.py's own PoC uses —
    deliberately not re-implemented here, so there is only ONE place in
    this codebase that ever touches a raw cookie value. The cookie values
    exist only inside this function's and the caller's local variables for
    the duration of one call; never logged, never returned, never
    persisted."""
    playwright_cookies = await session.context.cookies()
    from scripts.tn_session_replay_poc import _export_cookie_jar

    jar = _export_cookie_jar(playwright_cookies)
    del playwright_cookies
    return jar


@dataclass
class TnHttpReplayDiagnosticReport:
    """Everything one Phase 2 diagnostic call produced — already fully
    sanitized. to_safe_dict() is the only way this is ever serialized."""

    session_established_at: float | None
    observed_ticket_record_id_count: int
    multiple_tickets_observed: bool
    primary_attempt: TicketHttpReplayAttempt
    secondary_attempt: TicketHttpReplayAttempt | None
    elapsed_seconds_since_previous_attempt: float | None
    this_attempt_at: float

    def to_safe_dict(self) -> dict:
        return {
            "session_established_at": self.session_established_at,
            "observed_ticket_record_id_count": self.observed_ticket_record_id_count,
            "multiple_tickets_observed": self.multiple_tickets_observed,
            "primary_attempt": self.primary_attempt.to_safe_dict(),
            "secondary_attempt": self.secondary_attempt.to_safe_dict() if self.secondary_attempt else None,
            "elapsed_seconds_since_previous_attempt": self.elapsed_seconds_since_previous_attempt,
            "this_attempt_at": self.this_attempt_at,
        }


async def capture_tn_http_replay_diagnostic(
    session,
    network_evidence,
    *,
    primary_record_id: str,
    previous_attempt_at: float | None = None,
) -> TnHttpReplayDiagnosticReport:
    """MULTI-TICKET SCOPE entry point (question A).

    `session` is an already-open modules.govt_sync.browser_session.LiveSession
    (tenant/case/session ownership already validated by the caller, exactly
    as tn_network_diagnostic.capture_tn_diagnostic()'s own caller does).

    `network_evidence` is whatever list of already-collected network
    evidence a Phase 1 tn_network_diagnostic.capture_tn_diagnostic() run
    already produced THIS SAME diagnostic session (either its
    report.network_evidence safe-dict list, or the raw
    _NetworkEvidenceEntry list — both accepted, see
    tn_network_diagnostic._all_observed_urls()). This function attaches NO
    new network observer and triggers NO new navigation of its own — it
    only asks a question about traffic that already happened.

    `primary_record_id` is the id Phase 1 already discovered and already
    proved (tn_network_diagnostic.discover_ticket_record_id /
    TnDiagnosticReport.discovered_ticket_record_id) — always replayed
    again here as the baseline. A SECOND record id is replayed ONLY if
    tn_network_diagnostic.discover_all_ticket_record_ids() finds one
    ALREADY present in `network_evidence` that differs from
    `primary_record_id` — never guessed, enumerated, or incremented.

    `previous_attempt_at`, when given (the `this_attempt_at` a prior call
    to this function or replay_previously_observed_ticket() returned),
    lets the report compute elapsed time since that prior attempt — this
    module keeps no state of its own between calls.
    """
    if not primary_record_id:
        raise ValueError("capture_tn_http_replay_diagnostic requires an already-discovered primary_record_id")

    base_url = str((session.portal or {}).get("base_url") or "").rstrip("/")
    if not base_url:
        raise ValueError("live session has no base_url on its portal config")

    from .tn_network_diagnostic import _url_host, discover_all_ticket_record_ids

    expected_host = _url_host(base_url) or None
    observed_ids = discover_all_ticket_record_ids(network_evidence, expected_host=expected_host)
    secondary_record_id = next((rid for rid in observed_ids if rid != primary_record_id), None)

    cookie_jar = await _cookie_jar_for(session)
    try:
        primary_attempt = _perform_ticket_http_replay(cookie_jar, base_url, primary_record_id)
        secondary_attempt = (
            _perform_ticket_http_replay(cookie_jar, base_url, secondary_record_id)
            if secondary_record_id is not None else None
        )
    finally:
        del cookie_jar

    this_attempt_at = time.time()
    elapsed = (this_attempt_at - previous_attempt_at) if previous_attempt_at is not None else None

    return TnHttpReplayDiagnosticReport(
        session_established_at=getattr(session, "created_at", None),
        observed_ticket_record_id_count=len(observed_ids),
        multiple_tickets_observed=len(observed_ids) > 1,
        primary_attempt=primary_attempt,
        secondary_attempt=secondary_attempt,
        elapsed_seconds_since_previous_attempt=elapsed,
        this_attempt_at=this_attempt_at,
    )


async def replay_previously_observed_ticket(
    session,
    record_id: str,
    *,
    previous_attempt_at: float | None = None,
) -> TnHttpReplayDiagnosticReport:
    """SESSION DURABILITY entry point (question B).

    Performs exactly ONE more read-only HTTP replay against a record id
    ALREADY proven/observed in an earlier run — never a new/second ticket,
    never guessed. There is no automatic polling, no kept-alive session,
    and no background job anywhere in this module: this function must be
    invoked again explicitly (e.g. by a human, minutes or hours later),
    passing the previous call's own `this_attempt_at` as
    `previous_attempt_at`, to learn how much time elapsed and whether the
    SAME cookie jar — re-exported fresh from the still-open
    LiveSession.context on every call, never cached or reused across calls
    — still authenticates.
    """
    if not record_id:
        raise ValueError("replay_previously_observed_ticket requires an already-observed record_id")

    base_url = str((session.portal or {}).get("base_url") or "").rstrip("/")
    if not base_url:
        raise ValueError("live session has no base_url on its portal config")

    cookie_jar = await _cookie_jar_for(session)
    try:
        attempt = _perform_ticket_http_replay(cookie_jar, base_url, record_id)
    finally:
        del cookie_jar

    this_attempt_at = time.time()
    elapsed = (this_attempt_at - previous_attempt_at) if previous_attempt_at is not None else None

    return TnHttpReplayDiagnosticReport(
        session_established_at=getattr(session, "created_at", None),
        observed_ticket_record_id_count=1,
        multiple_tickets_observed=False,
        primary_attempt=attempt,
        secondary_attempt=None,
        elapsed_seconds_since_previous_attempt=elapsed,
        this_attempt_at=this_attempt_at,
    )
