"""
tests/test_govt_portal_contact_number.py — MP-facing government portal
contact-number flow (PATCH /api/govt-portal/contact-number).

Covers tenant isolation, authorization against the existing account/role
model, number normalization/validation, safe-update behaviour, the
/api/govt-portal read-back, OTP integration at a mocked portal boundary,
and the masked-audit/no-plaintext-logging guarantees.

PHONE NUMBERS IN THIS FILE ARE SYNTHETIC. No real tenant's government
portal contact number appears here (or anywhere else in the repo/CI) —
the numbers below only need the *shape* of a valid Indian mobile to
exercise normalization, so obviously-fake sequential digits are used.
"""
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
TEST_DB_URL = "sqlite:///./test_govt_portal_contact_number.db"

os.environ["JWT_SECRET"] = TEST_JWT_SECRET
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["ENV"] = "test"
os.environ["OPENAI_API_KEY"] = "sk-test-fake-key-for-testing"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Synthetic test numbers — never a real tenant's.
SYNTHETIC = "9876543210"          # valid: 10 digits, mobile prefix 9
SYNTHETIC_ALT = "8123456780"      # valid: mobile prefix 8, used for "replace"
PRE_EXISTING = "7012345678"       # valid: seeded as an already-set number


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@event.listens_for(Engine, "connect")
def _sqlite_register_pg_lock_functions(dbapi_connection, connection_record):
    try:
        dbapi_connection.create_function("pg_try_advisory_lock", 1, lambda _key: 1)
        dbapi_connection.create_function("pg_advisory_unlock", 1, lambda _key: 1)
        dbapi_connection.create_function("pg_try_advisory_xact_lock", 1, lambda _key: 1)
    except Exception:
        pass


import api_router
import core.db_helpers as db_helpers
import main
import sansadx_backend.db as dbmod
from sansadx_backend.db import Base

test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False)
client = TestClient(main.app, raise_server_exceptions=False)

ENDPOINT = "/api/govt-portal/contact-number"


def _bind_engines():
    dbmod.engine = test_engine
    dbmod.SessionLocal = TestSession
    db_helpers.engine = test_engine
    main.engine = test_engine
    api_router.engine = test_engine
    api_router.JWT_SECRET = TEST_JWT_SECRET


def _auth_headers(username: str) -> dict[str, str]:
    token = jwt.encode(
        {"sub": username, "exp": _utcnow() + timedelta(hours=8), "iat": _utcnow().timestamp()},
        TEST_JWT_SECRET, algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def _seed():
    _bind_engines()
    Base.metadata.create_all(bind=test_engine)
    now = _utcnow()
    with test_engine.begin() as conn:
        # Mirrors main.py's migration — govt_otp_sessions' upsert relies on
        # this unique index, which create_all() does not build because it is
        # declared as raw SQL in the migration rather than on the model.
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_govt_otp_sessions_tenant_portal "
            "ON govt_otp_sessions (tenant_id, portal_id)"
        ))
        for t in ("admin_audit_log", "govt_otp_sessions", "cases", "govt_portals",
                  "users", "tenant_profiles", "tenants"):
            conn.execute(text(f"DELETE FROM {t}"))  # nosec B608

        # Tenant 1 — Rajasthan (OTP-gated portal), no number on file.
        conn.execute(text(
            "INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active, created_at) "
            "VALUES (1, 'Tenant One', 'Seat One', '+919000000001', 'Pro', 1, :now)"
        ), {"now": now})
        conn.execute(text(
            "INSERT INTO tenant_profiles (tenant_id, mp_name, constituency, state, house, created_at) "
            "VALUES (1, 'Rep One', 'Seat One', 'Rajasthan', 'Lok Sabha', :now)"
        ), {"now": now})
        # Tenant 2 — the isolation target, with its own number already set.
        conn.execute(text(
            "INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active, "
            "govt_contact_primary_number, created_at) "
            "VALUES (2, 'Tenant Two', 'Seat Two', '+919000000002', 'Pro', 1, :num, :now)"
        ), {"now": now, "num": PRE_EXISTING})
        conn.execute(text(
            "INSERT INTO tenant_profiles (tenant_id, mp_name, constituency, state, house, created_at) "
            "VALUES (2, 'Rep Two', 'Seat Two', 'Rajasthan', 'Lok Sabha', :now)"
        ), {"now": now})

        for uname, tid, role in [
            ("owner_one", 1, "owner"), ("mp_one", 1, "mp"), ("admin_one", 1, "admin"),
            ("staff_one", 1, "staff"), ("pr_one", 1, "pr"),
            ("owner_two", 2, "owner"),
        ]:
            conn.execute(text(
                "INSERT INTO users (tenant_id, username, password_hash, role, constituency, house, "
                "display_name, is_active) VALUES (:tid, :u, 'x', :r, 'Seat', 'Lok Sabha', :u, 1)"
            ), {"tid": tid, "u": uname, "r": role})

        # Rajasthan Sampark — the OTP-gated portal both tenants resolve to.
        conn.execute(text(
            "INSERT INTO govt_portals (id, state, portal_name, portal_type, base_url, status_check_mode, "
            "department_taxonomy, field_schema, otp_bound, active, is_primary, verification_status, "
            "live_session_supported, status_check_adapter) VALUES "
            "(1, 'Rajasthan', 'Rajasthan Sampark', 'state_branded', 'https://sampark.example.test', "
            "'login_required', :tax, '{}', 1, 1, 1, 'confirmed', 1, 'rajasthan_sampark_api')"
        ), {"tax": json.dumps({"Infrastructure & Utilities": "Urban Development"})})


def _number_for(tenant_id: int):
    with test_engine.connect() as conn:
        return conn.execute(
            text("SELECT govt_contact_primary_number FROM tenants WHERE id = :t"), {"t": tenant_id},
        ).scalar()


def _audit_rows():
    with test_engine.connect() as conn:
        return [dict(r._mapping) for r in conn.execute(text(
            "SELECT admin_username, action, target_type, target_name, change_summary "
            "FROM admin_audit_log ORDER BY id"
        ))]


# ─── 1. Tenant isolation ────────────────────────────────────────────────────

def test_update_only_affects_callers_own_tenant():
    _seed()
    resp = client.patch(ENDPOINT, json={"contact_number": SYNTHETIC}, headers=_auth_headers("owner_one"))
    assert resp.status_code == 200, resp.text
    assert _number_for(1) == SYNTHETIC
    # Tenant 2's number is untouched.
    assert _number_for(2) == PRE_EXISTING


def test_tenant_id_in_request_body_cannot_retarget_another_tenant():
    """The endpoint derives tenant identity ONLY from the authenticated
    token via get_tenant_or_fail — extra body fields are ignored, never
    used to address a different tenant."""
    _seed()
    resp = client.patch(
        ENDPOINT,
        json={"contact_number": SYNTHETIC, "tenant_id": 2, "id": 2, "tid": 2},
        headers=_auth_headers("owner_one"),
    )
    assert resp.status_code == 200, resp.text
    assert _number_for(1) == SYNTHETIC       # caller's own tenant changed
    assert _number_for(2) == PRE_EXISTING    # the targeted tenant did NOT


def test_endpoint_signature_takes_no_client_supplied_tenant_id():
    """Structural guarantee: there is no tenant id parameter to manipulate."""
    import inspect

    params = inspect.signature(api_router.update_govt_portal_contact_number).parameters
    assert set(params) == {"req", "user"}
    assert set(api_router.GovtPortalContactRequest.model_fields) == {"contact_number"}


def test_two_tenants_update_independently():
    _seed()
    client.patch(ENDPOINT, json={"contact_number": SYNTHETIC}, headers=_auth_headers("owner_one"))
    client.patch(ENDPOINT, json={"contact_number": SYNTHETIC_ALT}, headers=_auth_headers("owner_two"))
    assert _number_for(1) == SYNTHETIC
    assert _number_for(2) == SYNTHETIC_ALT


# ─── 2. Authorization (existing account/role model) ─────────────────────────

@pytest.mark.parametrize("username", ["owner_one", "mp_one", "admin_one"])
def test_primary_account_roles_may_update(username):
    _seed()
    resp = client.patch(ENDPOINT, json={"contact_number": SYNTHETIC}, headers=_auth_headers(username))
    assert resp.status_code == 200, resp.text
    assert _number_for(1) == SYNTHETIC


@pytest.mark.parametrize("username", ["staff_one", "pr_one"])
def test_non_primary_roles_are_forbidden(username):
    _seed()
    resp = client.patch(ENDPOINT, json={"contact_number": SYNTHETIC}, headers=_auth_headers(username))
    assert resp.status_code == 403
    assert _number_for(1) is None  # no write happened


def test_unauthenticated_request_is_rejected():
    _seed()
    resp = client.patch(ENDPOINT, json={"contact_number": SYNTHETIC})
    assert resp.status_code in (401, 403)
    assert _number_for(1) is None


def test_authorization_reuses_existing_primary_account_model():
    """Guards against a parallel permission system: the endpoint's allowed
    roles must be exactly _is_primary_workspace_user's, not a private list."""
    for role in ("owner", "mp", "admin"):
        assert api_router._is_primary_workspace_user({"role": role}) is True
    for role in ("staff", "pr", "viewer", "", None):
        assert api_router._is_primary_workspace_user({"role": role}) is False


# ─── 3. Normalization and validation ────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("9876543210", "9876543210"),              # already bare
    ("+91 98765 43210", "9876543210"),         # +91 with spaces
    ("0091 9876543210", "9876543210"),         # 0091 country code
    ("09876543210", "9876543210"),             # leading zero
    ("+91-98765-43210", "9876543210"),         # hyphens
    ("+91 (98765) 43210", "9876543210"),       # brackets
    ("  9876543210  ", "9876543210"),          # surrounding whitespace
    ("919876543210", "9876543210"),            # bare country code
    ("6012345678", "6012345678"),              # prefix 6
    ("7012345678", "7012345678"),              # prefix 7
    ("8012345678", "8012345678"),              # prefix 8
])
def test_valid_numbers_normalize_to_bare_ten_digits(raw, expected):
    assert api_router._normalize_govt_contact_number(raw) == expected


@pytest.mark.parametrize("raw", [
    "987654321",            # 9 digits — too short
    "98765432101",          # 11 digits — too long
    "12345",                # far too short
    "5012345678",           # invalid Indian mobile prefix (5)
    "0123456789",           # invalid prefix after zero strip
    "1234567890",           # invalid prefix (1)
    "+1 415 555 0123",      # non-Indian (US) number
    "+44 20 7946 0958",     # non-Indian (UK) number
    "abcdefghij",           # alphabetic garbage
    "not a phone number",   # free text
    "",                     # empty
    "   ",                  # whitespace only
    "+91",                  # country code only
    "0000000000",           # all zeros
])
def test_invalid_numbers_are_rejected(raw):
    assert api_router._normalize_govt_contact_number(raw) is None


def test_endpoint_stores_normalized_bare_ten_digits():
    _seed()
    resp = client.patch(ENDPOINT, json={"contact_number": "+91 98765-43210"},
                        headers=_auth_headers("owner_one"))
    assert resp.status_code == 200, resp.text
    assert resp.json()["contact_number"] == SYNTHETIC
    assert _number_for(1) == SYNTHETIC  # stored bare, as portals expect


@pytest.mark.parametrize("bad", ["12345", "5012345678", "abcdefghij", "+1 415 555 0123"])
def test_endpoint_rejects_invalid_input_with_400(bad):
    _seed()
    resp = client.patch(ENDPOINT, json={"contact_number": bad}, headers=_auth_headers("owner_one"))
    assert resp.status_code == 400
    assert _number_for(1) is None


# ─── 4. Safe update behaviour ───────────────────────────────────────────────

def test_existing_number_can_be_replaced():
    _seed()
    client.patch(ENDPOINT, json={"contact_number": SYNTHETIC}, headers=_auth_headers("owner_one"))
    assert _number_for(1) == SYNTHETIC
    resp = client.patch(ENDPOINT, json={"contact_number": SYNTHETIC_ALT},
                        headers=_auth_headers("owner_one"))
    assert resp.status_code == 200, resp.text
    assert _number_for(1) == SYNTHETIC_ALT


@pytest.mark.parametrize("bad", ["", "12345", "abcdefghij", "5012345678"])
def test_invalid_input_never_overwrites_an_existing_valid_number(bad):
    _seed()
    client.patch(ENDPOINT, json={"contact_number": SYNTHETIC}, headers=_auth_headers("owner_one"))
    resp = client.patch(ENDPOINT, json={"contact_number": bad}, headers=_auth_headers("owner_one"))
    assert resp.status_code == 400
    assert _number_for(1) == SYNTHETIC  # untouched


def test_forbidden_role_cannot_overwrite_an_existing_number():
    _seed()
    client.patch(ENDPOINT, json={"contact_number": SYNTHETIC}, headers=_auth_headers("owner_one"))
    resp = client.patch(ENDPOINT, json={"contact_number": SYNTHETIC_ALT},
                        headers=_auth_headers("staff_one"))
    assert resp.status_code == 403
    assert _number_for(1) == SYNTHETIC


def test_govt_portal_get_returns_newly_stored_number():
    _seed()
    before = client.get("/api/govt-portal", headers=_auth_headers("owner_one"))
    assert before.status_code == 200, before.text
    assert before.json()["portal_contact_number"] is None

    client.patch(ENDPOINT, json={"contact_number": SYNTHETIC}, headers=_auth_headers("owner_one"))

    after = client.get("/api/govt-portal", headers=_auth_headers("owner_one"))
    assert after.status_code == 200, after.text
    assert after.json()["portal_contact_number"] == SYNTHETIC


def test_govt_portal_get_is_tenant_scoped():
    _seed()
    resp = client.get("/api/govt-portal", headers=_auth_headers("owner_two"))
    assert resp.json()["portal_contact_number"] == PRE_EXISTING
    resp_one = client.get("/api/govt-portal", headers=_auth_headers("owner_one"))
    assert resp_one.json()["portal_contact_number"] is None


# ─── 5. OTP integration (external portal boundary mocked) ───────────────────

def test_otp_send_fails_safely_when_no_number_configured():
    """No number on file -> 400 before any portal call is attempted."""
    _seed()
    with patch("modules.govt_sync.adapters.rajasthan_sampark.send_otp") as mock_send:
        resp = client.post("/api/govt/otp/send", json={}, headers=_auth_headers("owner_one"))
    assert resp.status_code == 400
    assert "contact number" in resp.json()["detail"].lower()
    mock_send.assert_not_called()  # external portal never contacted


def test_otp_send_uses_the_saved_number_after_it_is_configured():
    """After saving, the OTP flow resolves and submits exactly that number
    to the (mocked) portal boundary — never a constituent's."""
    _seed()
    now = _utcnow()
    with test_engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO cases (id, tenant_id, user_phone, raw_message, category, status, created_at, "
            "govt_portal_id, govt_status, govt_reference_number, is_deleted) VALUES "
            "(50, 1, '+919111111150', 'Water issue', 'Infrastructure & Utilities', 'in_progress', :now, "
            "1, 'submitted', 'RJ/RE/RURAL/2026/000001', 0)"
        ), {"now": now})

    client.patch(ENDPOINT, json={"contact_number": SYNTHETIC}, headers=_auth_headers("owner_one"))

    with patch(
        "modules.govt_sync.adapters.rajasthan_sampark.send_otp",
        return_value={"transaction_number": "txn-test", "session_id": "sess-test"},
    ) as mock_send:
        resp = client.post("/api/govt/otp/send", json={}, headers=_auth_headers("owner_one"))

    assert resp.status_code == 200, resp.text
    mock_send.assert_called_once()
    # First positional arg is the mobile the portal is told to text.
    assert mock_send.call_args.args[0] == SYNTHETIC


# ─── 6. Auditability / no plaintext number anywhere ─────────────────────────

def test_masking_helper_keeps_only_the_last_four_digits():
    assert api_router._mask_contact_number("9876543210") == "******3210"
    assert api_router._mask_contact_number(None) is None
    assert api_router._mask_contact_number("") is None


def test_audit_row_written_with_masked_number_only():
    _seed()
    resp = client.patch(ENDPOINT, json={"contact_number": SYNTHETIC}, headers=_auth_headers("owner_one"))
    assert resp.status_code == 200, resp.text

    rows = _audit_rows()
    assert len(rows) == 1
    row = rows[0]
    assert row["admin_username"] == "owner_one"     # who
    assert row["action"] == "updated"
    assert row["target_type"] == "govt_contact"     # same target_type as the admin-side path
    assert row["target_name"] == "tenant_id=1"

    summary = json.loads(row["change_summary"])
    assert summary["contact_number_masked"] == "******3210"
    assert summary["tenant_id"] == 1
    assert summary["replaced_existing"] is False
    assert summary["source"] == "mp_settings"
    # The full number must appear nowhere in the audit row.
    assert SYNTHETIC not in json.dumps(row)


def test_audit_records_replacement_of_an_existing_number():
    _seed()
    client.patch(ENDPOINT, json={"contact_number": SYNTHETIC}, headers=_auth_headers("owner_one"))
    client.patch(ENDPOINT, json={"contact_number": SYNTHETIC_ALT}, headers=_auth_headers("owner_one"))
    rows = _audit_rows()
    assert len(rows) == 2
    assert json.loads(rows[0]["change_summary"])["replaced_existing"] is False
    assert json.loads(rows[1]["change_summary"])["replaced_existing"] is True


def test_no_audit_row_when_the_update_is_rejected():
    _seed()
    client.patch(ENDPOINT, json={"contact_number": "12345"}, headers=_auth_headers("owner_one"))
    client.patch(ENDPOINT, json={"contact_number": SYNTHETIC}, headers=_auth_headers("staff_one"))
    assert _audit_rows() == []


def test_full_number_never_written_to_application_logs(caplog):
    _seed()
    with caplog.at_level(logging.DEBUG):
        resp = client.patch(ENDPOINT, json={"contact_number": SYNTHETIC},
                            headers=_auth_headers("owner_one"))
    assert resp.status_code == 200, resp.text
    assert SYNTHETIC not in caplog.text
    # The actor/tenant ARE recorded, so the change stays attributable.
    assert "owner_one" in caplog.text


def test_full_number_not_logged_when_the_write_fails(caplog):
    _seed()
    with patch("api_router.engine") as mock_engine:
        mock_engine.begin.side_effect = RuntimeError("db down")
        with caplog.at_level(logging.DEBUG):
            resp = client.patch(ENDPOINT, json={"contact_number": SYNTHETIC},
                                headers=_auth_headers("owner_one"))
    assert resp.status_code == 500
    assert SYNTHETIC not in caplog.text
    assert SYNTHETIC not in resp.text  # nor echoed back in the error body


def test_rejection_response_does_not_echo_the_submitted_number():
    _seed()
    resp = client.patch(ENDPOINT, json={"contact_number": "5012345678"},
                        headers=_auth_headers("owner_one"))
    assert resp.status_code == 400
    assert "5012345678" not in resp.text
