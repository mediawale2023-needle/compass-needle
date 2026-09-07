"""
modules/govt_sync/status/tn_network_diagnostic.py — Phase 1 controlled-proof
harness for the Tamil Nadu (CM Helpline) Playwright-to-HTTP migration
investigation.

BACKGROUND: a Claude Cowork investigation (2026-09-07) classified TN's
current live-Playwright status check as "B — PROBABLY MIGRATABLE, BUT NEEDS
A CONTROLLED PROOF." The existing PoC (scripts/tn_session_replay_poc.py)
already proves the *cookie-plumbing* half of that question is sound, but it
has never been executed, and its core assumption — that
`GET /portal/ta/myarea` / `GET /portal/ta/ticket/{record_id}` carry useful
data in their raw HTTP response bodies, the same way the production adapter
observes them via Playwright's post-JS DOM — is unproven and could be false
if Tamil Nadu populates the ticket list/detail via a separate XHR/fetch/API
call after the initial page load. This module exists to answer that
question with REAL, OBSERVED browser network evidence instead of a guess.

THIS MODULE DOES NOT:
  - authenticate, answer OTP/CAPTCHA, or open a new browser session (it only
    ever operates on an already-open modules.govt_sync.browser_session
    LiveSession, exactly like modules.govt_sync.status.tamil_nadu.py's own
    production status-check code path);
  - submit, create, edit, reply to, or otherwise mutate any grievance;
  - drive any navigation beyond what the PRODUCTION
    TamilNaduStatusAdapter.check_status_on_page() already performs today —
    this module attaches a read-only network observer around that exact,
    unmodified call and reports what it sees, it does not add a second,
    separate navigation sequence;
  - guess, invent, or probe any URL — the only two candidate read-only
    resources it ever requests over plain HTTP are the same two named,
    already-observed URLs scripts/tn_session_replay_poc.py already limits
    itself to (GET /portal/ta/myarea, GET /portal/ta/ticket/{record_id}),
    and the {record_id} used is the one this module actually OBSERVES in
    real captured browser traffic, never a caller-supplied or guessed value;
  - accept a caller-supplied reference number, case, or URL — the reference
    number comes from the case row via the caller's existing tenant/case
    ownership check (mirroring _get_tamil_nadu_live_status_context in
    api_router.py), and this module additionally refuses to run against any
    reference number that does not contain the one grievance short id this
    entire investigation is scoped to (see _ALLOWED_REFERENCE_SUBSTRING);
  - persist anything to Postgres, disk, or any file, or enable any
    unattended/background polling.

CREDENTIAL HANDLING: every function in this file returns only sanitized
classification strings and structural metadata (HTTP status codes, redacted
URLs, Playwright resource_type strings, the Content-Type header value,
response byte length). Cookie values, Set-Cookie headers, Authorization
headers, and full header dumps are never read, never captured, never
logged, and never included in any return value. See _redact_url() and
_safe_response_metadata() below for the only two places any request/
response data is ever touched.

WHY THIS EXISTS AS A GATED API ENDPOINT (api_router.py) RATHER THAN A
STANDALONE SCRIPT: the live Playwright session this module needs to observe
lives in modules.govt_sync.browser_session's process-local `_sessions`
dict, inside whichever single-worker backend_govt_live process actually
opened it (see that module's own docstring on this exact limitation, and
scripts/tn_session_replay_poc.py's docstring for why a separate `python`
invocation cannot see it). There is no other existing in-process invocation
mechanism in this codebase — no console, no signal handler, no RPC — so the
only way to run code inside that specific running worker is through a real
request that worker itself serves. Every other safety property (tenant/
case/session ownership, Tamil-Nadu-only, single-grievance-only, disabled by
default) is enforced at the api_router.py call site — see
govt_tamil_nadu_http_replay_diagnostic() there.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

logger = logging.getLogger("needle.govt_sync.tn_diagnostic")

# Hard safety scope, per the approved Phase 1 authorization — this module
# must never run against any grievance other than the one this entire
# investigation was scoped to. Checked again here (belt-and-suspenders)
# even though the api_router.py call site checks it first.
_ALLOWED_REFERENCE_SUBSTRING = "18968314"

# Bounded so a long-running page (or an unexpectedly chatty SPA) can't grow
# this list without limit — this is a diagnostic snapshot of one
# check_status_on_page() run, not a general-purpose network logger.
_MAX_EVIDENCE_ENTRIES = 200

# Playwright's own request.resource_type() values that indicate "this was
# not the initial document navigation" — i.e., the browser fetched this
# some other way after the page itself loaded. This is the signal Phase 2's
# "API_REQUIRED" / "SPA_SHELL" classification is built on.
_NON_DOCUMENT_RESOURCE_TYPES = frozenset({"xhr", "fetch"})

_TICKET_DETAIL_PATH_RE = re.compile(r"/portal/ta/ticket/([^/?#]+)")


def _redact_url(url: str) -> str:
    """Keeps scheme/host/path and query PARAMETER NAMES only — strips every
    query value. Never returns a fragment (fragments can carry SPA router
    state that isn't a credential but also isn't needed here)."""
    try:
        parts = urlsplit(url or "")
        redacted_query = urlencode({k: "<redacted>" for k, _ in parse_qsl(parts.query, keep_blank_values=True)})
        return urlunsplit((parts.scheme, parts.netloc, parts.path, redacted_query, ""))
    except Exception:
        return "<unparseable-url>"


async def _safe_content_type(response) -> str | None:
    """Reads exactly one, explicitly-named, non-credential response header.
    Never calls response.headers()/all_headers() (which would include
    Set-Cookie and any other header verbatim)."""
    try:
        return await response.header_value("content-type")
    except Exception:
        return None


@dataclass
class _NetworkEvidenceEntry:
    method: str
    url: str  # already redacted before storage
    resource_type: str
    status: int | None = None
    content_type: str | None = None
    response_bytes: int | None = None

    def to_safe_dict(self) -> dict:
        return {
            "method": self.method,
            "url": self.url,
            "resource_type": self.resource_type,
            "status": self.status,
            "content_type": self.content_type,
            "response_bytes": self.response_bytes,
        }


class _NetworkEvidenceCollector:
    """Attaches to a Playwright BrowserContext's request/response events for
    the duration of one diagnostic run. Every entry it stores has already
    passed through _redact_url()/_safe_content_type() — nothing unsafe is
    ever held, even transiently, past those two functions."""

    def __init__(self):
        self.entries: list[_NetworkEvidenceEntry] = []
        self._by_request = {}
        self._context = None

    def attach(self, context):
        self._context = context
        context.on("request", self._on_request)
        context.on("response", self._on_response)

    def detach(self):
        if self._context is None:
            return
        try:
            self._context.remove_listener("request", self._on_request)
            self._context.remove_listener("response", self._on_response)
        except Exception:
            pass  # nosec B110 — best-effort cleanup only
        self._context = None

    def _on_request(self, request):
        if len(self.entries) >= _MAX_EVIDENCE_ENTRIES:
            return
        try:
            entry = _NetworkEvidenceEntry(
                method=request.method,
                url=_redact_url(request.url),
                resource_type=getattr(request, "resource_type", "") or "",
            )
        except Exception:
            return
        self.entries.append(entry)
        self._by_request[id(request)] = entry

    def _on_response(self, response):
        try:
            entry = self._by_request.get(id(response.request))
        except Exception:
            entry = None
        if entry is None:
            return
        try:
            entry.status = response.status
        except Exception:
            pass
        import asyncio

        asyncio.create_task(self._fill_content_metadata(entry, response))

    async def _fill_content_metadata(self, entry: _NetworkEvidenceEntry, response) -> None:
        entry.content_type = await _safe_content_type(response)
        try:
            body = await response.body()
            entry.response_bytes = len(body) if body is not None else None
        except Exception:
            entry.response_bytes = None


def _discover_ticket_record_id(evidence: list[_NetworkEvidenceEntry]) -> str | None:
    """Looks for a captured request whose (already-redacted) URL path
    matches /portal/ta/ticket/{id} — the shape scripts/tn_session_replay_poc.py's
    second candidate URL expects. Returns the id segment straight from the
    URL PATH (a resource identifier the portal itself put in a URL it sent
    the browser to, not a credential) or None if no such request was
    observed. Never guesses; a None here is a legitimate, reportable result
    (RECORD_ID_UNRESOLVED, see _classify_outcome)."""
    for entry in evidence:
        match = _TICKET_DETAIL_PATH_RE.search(entry.url)
        if match:
            return match.group(1)
    return None


def _non_document_evidence(evidence: list[_NetworkEvidenceEntry]) -> list[_NetworkEvidenceEntry]:
    return [e for e in evidence if e.resource_type in _NON_DOCUMENT_RESOURCE_TYPES]


# ─── Phase 4 outcome classification ────────────────────────────────────────
# One of these exact strings, chosen only from actually-observed evidence —
# never overstated. See the Phase-1 authorization brief for the meaning of
# each; UNDETERMINED is used whenever the evidence doesn't clearly support
# any of the named outcomes, rather than forcing a guess into one bucket.

OUTCOME_HTTP_SUCCESS = "HTTP_SUCCESS"
OUTCOME_AUTH_FAILURE = "AUTH_FAILURE"
OUTCOME_REDIRECT_TO_LOGIN = "REDIRECT_TO_LOGIN"
OUTCOME_SPA_SHELL = "SPA_SHELL"
OUTCOME_API_REQUIRED = "API_REQUIRED"
OUTCOME_RECORD_ID_UNRESOLVED = "RECORD_ID_UNRESOLVED"
OUTCOME_UNDETERMINED = "UNDETERMINED"


def _classify_outcome(*, replay_result: str | None, record_id: str | None, non_document_count: int) -> str:
    if record_id is None:
        return OUTCOME_RECORD_ID_UNRESOLVED
    if replay_result is None:
        # HTTP replay was never attempted (e.g. record_id resolved too late
        # to bother, or the caller only wants network evidence). Distinct
        # from an actual failed replay attempt.
        return OUTCOME_UNDETERMINED
    # Imported lazily — see capture_tn_diagnostic() for why this module
    # never imports scripts.tn_session_replay_poc at module load time.
    from scripts.tn_session_replay_poc import (
        REPLAY_ANONYMOUS,
        REPLAY_FAILED,
        REPLAY_INCONCLUSIVE,
        REPLAY_REDIRECTED_TO_LOGIN,
        REPLAY_SUCCESS,
    )

    if replay_result == REPLAY_SUCCESS:
        return OUTCOME_HTTP_SUCCESS
    if replay_result == REPLAY_REDIRECTED_TO_LOGIN:
        return OUTCOME_REDIRECT_TO_LOGIN
    if replay_result == REPLAY_ANONYMOUS:
        # Cookies didn't produce an authenticated page. If the browser's own
        # flow used XHR/fetch calls we didn't replay, that's the more likely
        # explanation than the cookies themselves being rejected outright —
        # report the more specific, evidence-backed outcome when we can.
        return OUTCOME_API_REQUIRED if non_document_count > 0 else OUTCOME_AUTH_FAILURE
    if replay_result == REPLAY_FAILED:
        return OUTCOME_UNDETERMINED
    if replay_result == REPLAY_INCONCLUSIVE:
        # The page loaded but matched neither the authenticated markers nor
        # the login markers — exactly the SPA-shell-with-no-markers shape
        # the Cowork report worried about, IF the browser's own flow shows
        # additional XHR/fetch calls for the same data.
        return OUTCOME_SPA_SHELL if non_document_count > 0 else OUTCOME_UNDETERMINED
    return OUTCOME_UNDETERMINED


@dataclass
class TnDiagnosticReport:
    """Everything this diagnostic run produced — already fully sanitized.
    to_safe_dict() is the ONLY way this is ever serialized; no other
    attribute access path should be exposed to a caller outside this
    module."""

    playwright_result: dict  # StatusCheckResult.to_dict() — the same shape production already returns to staff
    network_evidence: list[dict]
    non_document_request_count: int
    discovered_ticket_record_id: str | None
    http_replay_result: str | None
    outcome: str

    def to_safe_dict(self) -> dict:
        return {
            "playwright_result": self.playwright_result,
            "network_evidence": self.network_evidence,
            "non_document_request_count": self.non_document_request_count,
            "discovered_ticket_record_id": self.discovered_ticket_record_id,
            "http_replay_result": self.http_replay_result,
            "outcome": self.outcome,
        }


async def capture_tn_diagnostic(session, reference_number: str) -> TnDiagnosticReport:
    """The single entry point. `session` is a modules.govt_sync.browser_session.LiveSession
    already validated (tenant/case/session ownership, Tamil-Nadu-adapter-only)
    by the caller — see govt_tamil_nadu_http_replay_diagnostic() in
    api_router.py, the only intended caller.

    Drives the SAME production TamilNaduStatusAdapter.check_status_on_page()
    call the normal "Check Tamil Nadu status" button already performs today
    — no separate navigation sequence — with a read-only network observer
    attached around it, then attempts the existing, already-written HTTP
    replay PoC using whatever ticket record id that observation actually
    discovered (never a guessed or caller-supplied one).
    """
    reference_number = (reference_number or "").strip()
    if _ALLOWED_REFERENCE_SUBSTRING not in reference_number:
        raise ValueError("tn_network_diagnostic is scoped to one pre-approved grievance only")

    from .tamil_nadu import TamilNaduStatusAdapter

    collector = _NetworkEvidenceCollector()
    collector.attach(session.context)
    try:
        adapter = TamilNaduStatusAdapter(session.portal)
        result = await adapter.check_status_on_page(session.page, reference_number)
        # Response bodies/content-types are filled in by background tasks
        # scheduled from the "response" event handler — give them a brief
        # moment to complete before reading the collected evidence back.
        import asyncio

        await asyncio.sleep(0.5)
    finally:
        collector.detach()

    evidence = collector.entries
    non_document = _non_document_evidence(evidence)
    record_id = _discover_ticket_record_id(evidence)

    replay_result = None
    if record_id is not None:
        # Deferred import: scripts/ is not a normal package dependency of
        # production code, and this keeps that boundary explicit — this is
        # the one place a Phase-1 diagnostic reaches into the untracked PoC,
        # not a new permanent import path for anything else in this module.
        from scripts.tn_session_replay_poc import tn_session_replay_experiment

        replay_result = await tn_session_replay_experiment(session.session_id, record_id)

    outcome = _classify_outcome(
        replay_result=replay_result, record_id=record_id, non_document_count=len(non_document),
    )

    return TnDiagnosticReport(
        playwright_result=result.to_dict(),
        network_evidence=[e.to_safe_dict() for e in evidence],
        non_document_request_count=len(non_document),
        discovered_ticket_record_id=record_id,
        http_replay_result=replay_result,
        outcome=outcome,
    )
