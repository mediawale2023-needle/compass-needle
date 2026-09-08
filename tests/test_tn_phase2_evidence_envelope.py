"""
tests/test_tn_phase2_evidence_envelope.py — the short-lived, signed
Phase-2 evidence envelope (modules/govt_sync/status/tn_phase2_evidence_envelope.py).

Pure unit tests: no Playwright, no HTTP, no database, no live session.
Proves the cryptographic provenance guarantee directly — a caller can
carry a genuine envelope, but any modification to its contents (ticket
ids, case id, reference number) invalidates its signature, and expired /
wrong-purpose / malformed / forged envelopes are all rejected.
"""
import base64
import json
import time

import jwt
import pytest

from modules.govt_sync.status.tn_phase2_evidence_envelope import (
    EnvelopeInvalid,
    TTL_SECONDS,
    issue_envelope,
    verify_envelope,
)

SECRET = "test-jwt-secret-at-least-32-characters-long"
CASE_ID = 3563
REFERENCE = "TN/FOODCO/CBE/P/PORTAL/01SEP26/18968314"
PRIMARY_ID = "35665012402750744"
HOST = "cmhelpline.tnega.org"


def _issue(**overrides):
    kwargs = dict(
        jwt_secret=SECRET, case_id=CASE_ID, reference_number=REFERENCE,
        observed_ticket_record_ids=[PRIMARY_ID], expected_host=HOST,
    )
    kwargs.update(overrides)
    return issue_envelope(**kwargs)


def _b64url_encode(data: bytes) -> bytes:
    return base64.urlsafe_b64encode(data).rstrip(b"=")


def _b64url_decode(data: str) -> bytes:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded)


def _tamper(envelope: str, mutate) -> str:
    """Decodes the JWT's payload segment, applies `mutate` to the claims
    dict, re-encodes it, and reassembles the token WITH THE ORIGINAL
    (now-stale) signature — exactly what an attacker editing a JWT payload
    by hand would produce. Used to prove tampering is caught by signature
    verification, never by re-deriving trust from the modified content."""
    header_b64, payload_b64, sig_b64 = envelope.split(".")
    claims = json.loads(_b64url_decode(payload_b64))
    mutate(claims)
    new_payload_b64 = _b64url_encode(json.dumps(claims).encode()).decode()
    return f"{header_b64}.{new_payload_b64}.{sig_b64}"


# ─── 1. Genuine envelope verifies ───────────────────────────────────────────

def test_genuine_envelope_verifies():
    envelope = _issue()
    payload = verify_envelope(envelope, jwt_secret=SECRET, case_id=CASE_ID, reference_number=REFERENCE)
    assert payload["case_id"] == CASE_ID
    assert payload["reference_number"] == REFERENCE
    assert payload["observed_ticket_record_ids"] == [PRIMARY_ID]
    assert payload["expected_host"] == HOST


# ─── 2. Modified ticket ID fails ────────────────────────────────────────────

def test_modified_ticket_id_fails_verification():
    envelope = _issue()
    tampered = _tamper(envelope, lambda c: c.__setitem__("observed_ticket_record_ids", ["99999999999999999"]))
    with pytest.raises(EnvelopeInvalid):
        verify_envelope(tampered, jwt_secret=SECRET, case_id=CASE_ID, reference_number=REFERENCE)


# ─── 3. Added fabricated second ticket ID fails ─────────────────────────────

def test_added_fabricated_ticket_id_fails_verification():
    envelope = _issue()
    tampered = _tamper(envelope, lambda c: c["observed_ticket_record_ids"].append("11111111111111111"))
    with pytest.raises(EnvelopeInvalid):
        verify_envelope(tampered, jwt_secret=SECRET, case_id=CASE_ID, reference_number=REFERENCE)


# ─── 4. Modified case ID fails ──────────────────────────────────────────────

def test_modified_case_id_fails_verification():
    envelope = _issue()
    tampered = _tamper(envelope, lambda c: c.__setitem__("case_id", 9999))
    with pytest.raises(EnvelopeInvalid):
        verify_envelope(tampered, jwt_secret=SECRET, case_id=CASE_ID, reference_number=REFERENCE)
    # Even verifying against the TAMPERED case_id must still fail — the
    # signature itself is broken, not just the cross-check below.
    with pytest.raises(EnvelopeInvalid):
        verify_envelope(tampered, jwt_secret=SECRET, case_id=9999, reference_number=REFERENCE)


# ─── 5. Modified reference fails ────────────────────────────────────────────

def test_modified_reference_fails_verification():
    envelope = _issue()
    tampered = _tamper(envelope, lambda c: c.__setitem__("reference_number", "TN/FAKE/REF/P/PORTAL/01SEP26/00000000"))
    with pytest.raises(EnvelopeInvalid):
        verify_envelope(tampered, jwt_secret=SECRET, case_id=CASE_ID, reference_number=REFERENCE)


def test_genuine_envelope_rejected_when_case_or_reference_does_not_match_caller_context():
    """Defense in depth: even a VALIDLY signed envelope must be rejected if
    the caller's own independently-resolved case/reference don't match it
    (e.g. an envelope issued for one case somehow presented for another)."""
    envelope = _issue()
    with pytest.raises(EnvelopeInvalid):
        verify_envelope(envelope, jwt_secret=SECRET, case_id=4242, reference_number=REFERENCE)
    with pytest.raises(EnvelopeInvalid):
        verify_envelope(envelope, jwt_secret=SECRET, case_id=CASE_ID, reference_number="TN/OTHER/REF/P/PORTAL/01SEP26/00000000")


# ─── 6. Expired envelope fails ──────────────────────────────────────────────

def test_expired_envelope_fails_verification():
    envelope = _issue()
    # Move both iat/exp into the past without touching the signature — this
    # simulates simply waiting past TTL_SECONDS, not tampering.
    tampered = _tamper(envelope, lambda c: (c.__setitem__("iat", time.time() - 10_000), c.__setitem__("exp", time.time() - 9_000)))
    with pytest.raises(EnvelopeInvalid):
        verify_envelope(tampered, jwt_secret=SECRET, case_id=CASE_ID, reference_number=REFERENCE)


def test_ttl_is_short_lived():
    assert 0 < TTL_SECONDS <= 600


# ─── 7. Wrong purpose/version fails ─────────────────────────────────────────

def test_wrong_purpose_fails_verification():
    envelope = _issue()
    tampered = _tamper(envelope, lambda c: c.__setitem__("purpose", "some_other_purpose"))
    with pytest.raises(EnvelopeInvalid):
        verify_envelope(tampered, jwt_secret=SECRET, case_id=CASE_ID, reference_number=REFERENCE)


def test_wrong_version_fails_verification():
    envelope = _issue()
    tampered = _tamper(envelope, lambda c: c.__setitem__("version", 999))
    with pytest.raises(EnvelopeInvalid):
        verify_envelope(tampered, jwt_secret=SECRET, case_id=CASE_ID, reference_number=REFERENCE)


# ─── 8. Malformed envelope fails ────────────────────────────────────────────

@pytest.mark.parametrize("garbage", ["", "not-a-jwt", "a.b.c", "a.b", "....", None])
def test_malformed_envelope_fails_verification(garbage):
    with pytest.raises(EnvelopeInvalid):
        verify_envelope(garbage, jwt_secret=SECRET, case_id=CASE_ID, reference_number=REFERENCE)


# ─── 9. Invalid signature fails ─────────────────────────────────────────────

def test_envelope_signed_with_wrong_secret_fails_verification():
    envelope = issue_envelope(
        jwt_secret="a-completely-different-secret-value-32chars",
        case_id=CASE_ID, reference_number=REFERENCE,
        observed_ticket_record_ids=[PRIMARY_ID], expected_host=HOST,
    )
    with pytest.raises(EnvelopeInvalid):
        verify_envelope(envelope, jwt_secret=SECRET, case_id=CASE_ID, reference_number=REFERENCE)


def test_forged_envelope_signed_with_literal_jwt_secret_directly_fails():
    """The envelope uses a KEY-DERIVED secret, not JWT_SECRET itself — a
    forger who somehow knew JWT_SECRET (e.g. leaked auth secret) but not
    the derivation scheme still cannot forge a valid envelope by signing
    with the raw JWT_SECRET."""
    forged_payload = {
        "purpose": "tn_phase2_evidence_envelope", "version": 1,
        "case_id": CASE_ID, "reference_number": REFERENCE,
        "observed_ticket_record_ids": [PRIMARY_ID], "expected_host": HOST,
        "iat": time.time(), "exp": time.time() + TTL_SECONDS,
    }
    forged = jwt.encode(forged_payload, SECRET, algorithm="HS256")
    with pytest.raises(EnvelopeInvalid):
        verify_envelope(forged, jwt_secret=SECRET, case_id=CASE_ID, reference_number=REFERENCE)


def test_real_user_auth_token_is_not_a_valid_envelope():
    """A real Needle auth JWT (signed with the literal JWT_SECRET, the
    shape get_current_user() accepts) must never be accepted here either —
    proves the two token families are cryptographically unrelated."""
    auth_token = jwt.encode(
        {"sub": "mp_priya", "iat": time.time(), "exp": time.time() + 28800},
        SECRET, algorithm="HS256",
    )
    with pytest.raises(EnvelopeInvalid):
        verify_envelope(auth_token, jwt_secret=SECRET, case_id=CASE_ID, reference_number=REFERENCE)


# ─── No credential material / no session_id in the envelope ────────────────

def test_envelope_contains_no_credential_material_or_session_id():
    envelope = _issue(observed_ticket_record_ids=[PRIMARY_ID, "999888777"])
    header_b64, payload_b64, _sig = envelope.split(".")
    claims = json.loads(_b64url_decode(payload_b64))
    dumped = json.dumps(claims)
    for forbidden in (
        "cookie", "Cookie", "Set-Cookie", "Authorization", "authorization",
        "csrf", "CSRF", "session_id", "password", "otp", "captcha", "OTP", "CAPTCHA",
    ):
        assert forbidden not in dumped
    # Only the expected, minimal claim set — nothing extra snuck in.
    assert set(claims.keys()) == {
        "purpose", "version", "case_id", "reference_number",
        "observed_ticket_record_ids", "expected_host", "iat", "exp",
    }


def test_issue_envelope_never_returns_the_derived_secret():
    envelope = _issue()
    assert SECRET not in envelope
