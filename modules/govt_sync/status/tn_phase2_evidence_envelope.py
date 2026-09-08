"""
modules/govt_sync/status/tn_phase2_evidence_envelope.py — short-lived,
signed evidence envelope binding Phase-1 network evidence to the Phase-2
HTTP-replay diagnostic, so a caller can carry Phase-1's own sanitized
result between the two endpoints WITHOUT being able to modify it.

BACKGROUND: a static review of the Phase-2 endpoint (POST /cases/{case_id}
/govt/tamil-nadu/http-replay-diagnostic, api_router.py, commit 4c414173)
found that accepting `network_evidence` directly as a free-form
request-body field made "previously observed ticket ID" caller-
controlled: the Phase-2 harness itself correctly only ever replays ids
PRESENT in whatever evidence it's given, but "present in the evidence" is
not a security property if the evidence itself can be edited before
submission. This module makes the evidence a server-signed, tamper-
evident envelope instead — 4c414173 is not approved for deployment until
the endpoint is switched to require this envelope in place of a raw
evidence field.

EXISTING SIGNING PRIMITIVE REUSED, NO NEW SECRET: PyJWT + the existing
`JWT_SECRET` env var — the SAME secret every Needle auth token is already
signed with (api_router.py's create_token()/get_current_user(),
JWT_SECRET, HS256; enforced ≥32 chars at startup). No new secret is added
to source code, configuration, or environment.

KEY SEPARATION (deliberate, so the two token families can never be
confused): the envelope is signed with a DERIVED key —
sha256(JWT_SECRET + "|" + purpose_and_version) — never the literal
JWT_SECRET. This means:
  - an envelope can never be decoded successfully as a real user auth
    token (get_current_user() calls jwt.decode(..., JWT_SECRET, ...) —
    an envelope signed with the derived key fails that check outright);
  - a real user auth token can never be decoded as a valid envelope
    (verify_envelope() below uses the derived key, not JWT_SECRET);
  - the derived key itself is never persisted, logged, printed, or
    returned anywhere — it exists only as a local variable for the
    duration of one issue_envelope()/verify_envelope() call, computed
    fresh from JWT_SECRET (already in process memory) every time.

WHAT THE ENVELOPE CONTAINS — deliberately the minimum: the approved case
id, the approved reference number, the canonical ticket record ids
ALREADY discovered from Phase-1's own real observed evidence (via
tn_network_diagnostic.discover_all_ticket_record_ids() — never
caller-supplied, never guessed), and the portal host those ids were
observed against — enough for Phase 2 to reconstruct the exact canonical
URL shape discover_all_ticket_record_ids() would find in the original
evidence, and nothing else. A purpose/version marker plus a short
issued-at/expiry window complete the envelope.

WHAT IT NEVER CONTAINS: cookies, cookie values, session_id, JWTs (other
than the envelope's own outer signature), Authorization headers, CSRF
tokens, passwords, OTP/CAPTCHA material, raw response bodies, raw request
headers, or any other credential. It never embeds the raw
`network_evidence` list either — only the already-reduced ticket ids
derived from it, which is strictly less information.

NOT PERSISTED ANYWHERE: no database table, no Redis, no module-level
cache, no file. The envelope's signature and `exp` claim are its ONLY
integrity/lifetime mechanism — verification is purely a function of the
envelope string itself plus JWT_SECRET (already resident in process
memory as a module-level constant elsewhere), never any stored state
this module adds.
"""
from __future__ import annotations

import hashlib
import time

import jwt

_PURPOSE = "tn_phase2_evidence_envelope"
_VERSION = 1
# Short-lived by design — matches tn_diagnostic_runtime_gate.py's own
# TTL_SECONDS convention for a one-controlled-run investigation artifact.
TTL_SECONDS = 300
_ALGORITHM = "HS256"


class EnvelopeInvalid(Exception):
    """Raised for ANY envelope that fails to verify — expired, tampered,
    malformed, wrong purpose/version, or a case/reference mismatch. All
    reported identically by design (callers should map this to one
    uniform 4xx, never a distinct message per failure reason, so nothing
    here helps an attacker iterate toward a valid forgery)."""


def _derived_secret(jwt_secret: str) -> str:
    """Never returned, logged, or persisted — a fresh local value on
    every call, derived from JWT_SECRET (already required to exist and be
    ≥32 chars by api_router.py's own startup check)."""
    return hashlib.sha256(f"{jwt_secret}|{_PURPOSE}_v{_VERSION}".encode()).hexdigest()


def issue_envelope(
    *,
    jwt_secret: str,
    case_id: int,
    reference_number: str,
    observed_ticket_record_ids: list,
    expected_host: str | None,
) -> str:
    """Signs and returns a short-lived envelope binding exactly these
    already-server-derived values.

    `observed_ticket_record_ids` MUST already be the output of
    tn_network_diagnostic.discover_all_ticket_record_ids() run against
    REAL Phase-1 network evidence this process itself just collected —
    this function does not discover, validate, sanitize, or second-guess
    ids itself; it only signs whatever it is given. Callers remain
    responsible for only ever calling this with server-derived values,
    never anything sourced from a request body."""
    now = time.time()
    payload = {
        "purpose": _PURPOSE,
        "version": _VERSION,
        "case_id": case_id,
        "reference_number": reference_number,
        "observed_ticket_record_ids": list(observed_ticket_record_ids or []),
        "expected_host": expected_host,
        "iat": now,
        "exp": now + TTL_SECONDS,
    }
    return jwt.encode(payload, _derived_secret(jwt_secret), algorithm=_ALGORITHM)


def verify_envelope(envelope: str, *, jwt_secret: str, case_id: int, reference_number: str) -> dict:
    """Verifies signature + expiry (PyJWT enforces `exp` automatically),
    THEN checks purpose/version, THEN checks the envelope's own
    case_id/reference_number against the ones the caller's already-
    authenticated request independently resolved — defense in depth, so
    an envelope for a DIFFERENT case or reference is never accepted here
    even if it is otherwise validly signed (e.g. accidentally or
    deliberately replayed across cases).

    Returns the verified payload dict on success — including the
    server-derived `observed_ticket_record_ids` and `expected_host`,
    which the caller (api_router.py) uses to reconstruct a trusted
    network_evidence list for the unmodified Phase-2 harness.

    Raises EnvelopeInvalid on ANY failure. Must be called, and must
    succeed, BEFORE any HTTP replay is ever attempted — this function
    performs no I/O, no session access, and no replay itself; it is pure
    signature/claim verification."""
    try:
        payload = jwt.decode(envelope, _derived_secret(jwt_secret), algorithms=[_ALGORITHM])
    except jwt.PyJWTError:
        raise EnvelopeInvalid("Invalid or expired evidence envelope.")

    if payload.get("purpose") != _PURPOSE or payload.get("version") != _VERSION:
        raise EnvelopeInvalid("Evidence envelope was issued for a different purpose/version.")
    if payload.get("case_id") != case_id:
        raise EnvelopeInvalid("Evidence envelope does not match the requested case.")
    if payload.get("reference_number") != reference_number:
        raise EnvelopeInvalid("Evidence envelope does not match the approved reference number.")
    return payload
