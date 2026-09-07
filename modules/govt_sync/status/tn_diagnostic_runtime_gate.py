"""
modules/govt_sync/status/tn_diagnostic_runtime_gate.py — process-local,
single-use runtime permission for the Tamil Nadu HTTP-diagnostic proof
(modules/govt_sync/status/tn_network_diagnostic.py), added so that gate can
be turned on for exactly one controlled run WITHOUT recreating
backend_govt_live.

WHY THIS EXISTS: GOVT_SYNC_TN_HTTP_DIAGNOSTIC_ENABLED is a process
environment variable — flipping it requires recreating backend_govt_live,
which destroys the process-local, in-memory Playwright LiveSession
(modules.govt_sync.browser_session._sessions) the diagnostic needs to
observe. This module is the alternative: a tiny, in-memory grant that lives
in the SAME already-running process, created and consumed by ordinary
authenticated HTTP requests that process already serves — no environment
change, no container action, no restart, anywhere in the cycle.

WHAT A GRANT IS: exactly one permission to run the diagnostic once, scoped
to one exact (tenant_id, case_id, session_id, reference_number) tuple.
Nothing broader. It is:
  - created only by an authenticated call that has already passed the
    SAME tenant/case/session-ownership check
    (api_router._get_tamil_nadu_live_status_context) the diagnostic
    endpoint itself uses, plus the same hard-coded single-grievance guard
    that endpoint already enforces;
  - single-use — consume_if_armed() atomically pops the grant the moment
    it succeeds, so a second call can never redeem the same grant;
  - short-lived — a grant older than TTL_SECONDS is treated as if it never
    existed (lazy expiry; no background sweep, matching this codebase's
    existing lazy-expiry convention for govt_status_check_attempts);
  - explicitly revocable — disarm() removes a grant immediately, before
    its TTL or before it's ever consumed;
  - destroyed the instant the process restarts for any reason, exactly
    like the LiveSession it corresponds to — this module intentionally
    persists nothing to disk or to Postgres.

WHAT THIS MODULE DOES NOT DO: it never reads, writes, or imports anything
from modules.govt_sync.browser_session — it has no reference to any
LiveSession, no reference to Playwright, and no way to touch
browser_session._sessions. It never sees a cookie, a header, a token, an
OTP, or a CAPTCHA value — every function here takes and returns only
plain identifiers (ints/strings) and booleans. It does not decide WHETHER
the diagnostic is a good idea to run — that authorization (tenant/case/
session ownership, Tamil-Nadu-only, single-grievance-only) happens before
this module is ever called, in api_router.py, exactly as it already did
before this module existed; this module only remembers, for a few minutes,
that authorization already happened once.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

TTL_SECONDS = 300

_lock = asyncio.Lock()


@dataclass
class _Grant:
    tenant_id: int
    case_id: int
    session_id: str
    reference_number: str
    armed_at: float


# Keyed by session_id — a session can hold at most one live grant at a time
# (arming again simply replaces whatever grant existed before, same as
# re-arming an alarm resets it rather than stacking).
_grants: dict[str, _Grant] = {}


def _matches(grant: _Grant, *, tenant_id: int, case_id: int, session_id: str, reference_number: str) -> bool:
    return (
        grant.tenant_id == tenant_id
        and grant.case_id == case_id
        and grant.session_id == session_id
        and grant.reference_number == reference_number
    )


def _is_expired(grant: _Grant, *, now: float) -> bool:
    return (now - grant.armed_at) > TTL_SECONDS


def has_pending_grant(session_id: str) -> bool:
    """Cheap, non-mutating presence check — does NOT validate tenant/case/
    reference/expiry, only whether *some* grant object exists for this
    session_id. Exists so the diagnostic endpoint can preserve its exact
    pre-existing "flag off -> immediate 404, before touching ownership at
    all" behavior for the overwhelming common case (no grant for this
    session_id at all), without needing the real reference_number (which
    would require a DB lookup) just to answer "is there anything to even
    check here." A caller with no legitimate ownership of this session_id
    gains nothing from this returning True — the real consume_if_armed()
    call downstream still requires an exact tenant/case/reference match,
    and the existing ownership check the diagnostic endpoint already runs
    (_get_tamil_nadu_live_status_context) still 404s them regardless."""
    return session_id in _grants


async def arm(*, tenant_id: int, case_id: int, session_id: str, reference_number: str) -> None:
    """Creates (or replaces) a single-use grant for exactly this tuple.
    Caller must have already performed tenant/case/session ownership and
    single-grievance checks — this function trusts its arguments and adds
    no authorization logic of its own; see this module's docstring."""
    async with _lock:
        _grants[session_id] = _Grant(
            tenant_id=tenant_id, case_id=case_id, session_id=session_id,
            reference_number=reference_number, armed_at=time.monotonic(),
        )


async def disarm(*, session_id: str) -> None:
    """Removes any grant for this session_id, regardless of whether it was
    ever consumed or has expired. Idempotent — disarming an already-gone
    grant is a no-op, never an error."""
    async with _lock:
        _grants.pop(session_id, None)


async def consume_if_armed(*, tenant_id: int, case_id: int, session_id: str, reference_number: str) -> bool:
    """Atomically checks for a matching, unexpired grant and removes it in
    the same step if found — so two concurrent callers can never both
    succeed against the same grant. A mismatched tenant/case/reference, an
    unknown session_id, and a genuinely expired grant are all
    indistinguishable: every one of them returns False, never raises, and
    never reveals which case it was (fail-closed, same discipline as
    load_attempt() in modules/govt_sync/status_attempts.py)."""
    now = time.monotonic()
    async with _lock:
        grant = _grants.get(session_id)
        if grant is None:
            return False
        if _is_expired(grant, now=now):
            del _grants[session_id]
            return False
        if not _matches(grant, tenant_id=tenant_id, case_id=case_id, session_id=session_id, reference_number=reference_number):
            return False
        del _grants[session_id]
        return True
