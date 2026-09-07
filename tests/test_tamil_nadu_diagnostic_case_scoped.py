"""
tests/test_tamil_nadu_diagnostic_case_scoped.py — case-scoped TN
HTTP-diagnostic invocation, added so the diagnostic can be run for a known
case WITHOUT the raw session_id ever crossing an HTTP boundary.

Covers:
  - browser_session.find_live_session_for_case() — the one new resolver,
    exercised against REAL LiveSession objects inserted directly into
    browser_session._sessions (not mocks), since this function's whole job
    is reading that real module-level state.
  - api_router.govt_tamil_nadu_diagnostic_run_for_case() — the new
    endpoint, with capture_tn_diagnostic() mocked (no real Playwright, no
    real HTTP request, no real government portal).

Explicit security proof throughout: session_id must never appear in any
response body, govt_submission_log payload, or exception message this
endpoint produces.
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
TEST_DB_URL = "sqlite:///./test_tamil_nadu_diagnostic_case_scoped.db"

os.environ["JWT_SECRET"] = TEST_JWT_SECRET
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["ENV"] = "test"
os.environ["OPENAI_API_KEY"] = "sk-test-fake-key-for-testing"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


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
from sansadx_backend.db import Base, hash_password

from modules.govt_sync.browser_session import LiveSession, _sessions, find_live_session_for_case
from tests.test_tamil_nadu_status import REF, _tn_portal

test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False)
client = TestClient(main.app, raise_server_exceptions=False)

OTHER_REF = "TN/OTHER/CASE/P/PORTAL/01SEP26/99999999"


def _bind_engines():
    dbmod.engine = test_engine
    dbmod.SessionLocal = TestSession
    db_helpers.engine = test_engine
    main.engine = test_engine
    api_router.engine = test_engine
    api_router.JWT_SECRET = TEST_JWT_SECRET


def _auth_headers(username: str = "mp_priya") -> dict[str, str]:
    token = jwt.encode(
        {"sub": username, "exp": _utcnow() + timedelta(hours=8), "iat": _utcnow().timestamp()},
        TEST_JWT_SECRET, algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def _seed_database():
    _bind_engines()
    Base.metadata.create_all(bind=test_engine)
    now = _utcnow()
    with test_engine.begin() as conn:
        for table_name in ("govt_submission_log", "case_activity_log", "cases", "govt_portals",
                            "tenant_overrides", "token_blocklist", "users", "tenant_profiles", "tenants"):
            conn.execute(text(f"DELETE FROM {table_name}"))  # nosec B608
        conn.execute(text(
            "INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active, created_at) "
            "VALUES (1, 'Priya Sharma', 'Kalyan Dombivli', '+919000000002', 'Pro', 1, :now)"
        ), {"now": now})
        conn.execute(text(
            "INSERT INTO tenant_profiles (tenant_id, mp_name, constituency, state, house, created_at) "
            "VALUES (1, 'Shri Priya Sharma', 'Kalyan Dombivli', 'Tamil Nadu', 'Lok Sabha', :now)"
        ), {"now": now})
        conn.execute(text(
            "INSERT INTO users (tenant_id, username, password_hash, role, constituency, house, display_name, is_active) "
            "VALUES (1, 'mp_priya', :password_hash, 'mp', 'Kalyan Dombivli', 'Lok Sabha', 'Priya MP', 1)"
        ), {"password_hash": hash_password("Password1")})
        conn.execute(text(
            "INSERT INTO govt_portals (id, state, portal_name, portal_type, base_url, status_check_mode, "
            "department_taxonomy, field_schema, otp_bound, active, is_primary, verification_status, "
            "live_session_supported) VALUES "
            "(1, 'Tamil Nadu', 'Tamil Nadu CM Helpline (Mudhalvarin Mugavari)', 'state_branded', "
            "'https://cmhelpline.tnega.org', 'login_required', '{}', '{}', 0, 1, 1, 'confirmed', 1)"
        ), {})
        conn.execute(text(
            "INSERT INTO cases (id, tenant_id, user_phone, raw_message, category, status, created_at, "
            "govt_portal_id, govt_status, govt_reference_number, is_deleted) VALUES "
            f"(3563, 1, '+919111111140', 'No food ration', 'Infrastructure & Utilities', 'in_progress', :now, "
            f"1, 'submitted', '{REF}', 0)"
        ), {"now": now})
        # A case with a reference outside the authorized grievance, same tenant.
        conn.execute(text(
            "INSERT INTO cases (id, tenant_id, user_phone, raw_message, category, status, created_at, "
            "govt_portal_id, govt_status, govt_reference_number, is_deleted) VALUES "
            f"(3564, 1, '+919111111141', 'Other grievance', 'Infrastructure & Utilities', 'in_progress', :now, "
            f"1, 'submitted', '{OTHER_REF}', 0)"
        ), {"now": now})
        # A second tenant/case pair for cross-tenant fail-closed tests.
        conn.execute(text(
            "INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active, created_at) "
            "VALUES (2, 'Other MP', 'Other Seat', '+919000000003', 'Pro', 1, :now)"
        ), {"now": now})
        conn.execute(text(
            "INSERT INTO tenant_profiles (tenant_id, mp_name, constituency, state, house, created_at) "
            "VALUES (2, 'Other MP', 'Other Seat', 'Tamil Nadu', 'Lok Sabha', :now)"
        ), {"now": now})
        conn.execute(text(
            "INSERT INTO users (tenant_id, username, password_hash, role, constituency, house, display_name, is_active) "
            "VALUES (2, 'mp_other', :password_hash, 'mp', 'Other Seat', 'Lok Sabha', 'Other MP', 1)"
        ), {"password_hash": hash_password("Password1")})
        conn.execute(text(
            "INSERT INTO cases (id, tenant_id, user_phone, raw_message, category, status, created_at, "
            "govt_portal_id, govt_status, govt_reference_number, is_deleted) VALUES "
            f"(3999, 2, '+919111111142', 'Other tenant case', 'Infrastructure & Utilities', 'in_progress', :now, "
            f"1, 'submitted', '{REF}', 0)"
        ), {"now": now})


def _fake_live_session(session_id, tenant_id, case_id, portal=None):
    return LiveSession(
        session_id=session_id, tenant_id=tenant_id, case_id=case_id,
        portal=portal if portal is not None else _tn_portal(),
        context=MagicMock(), page=MagicMock(), cdp=MagicMock(),
    )


def setup_function(_fn):
    # _sessions is real, process-local, module-level state — clear it
    # between tests so one test's fake session never leaks into another.
    _sessions.clear()


def teardown_function(_fn):
    _sessions.clear()


# ─── find_live_session_for_case() — real _sessions dict, no mocks ─────────

def test_resolver_finds_exact_tenant_and_case_match():
    _sessions["s1"] = _fake_live_session("s1", tenant_id=12, case_id=3563)
    found = find_live_session_for_case(12, 3563)
    assert found is not None
    assert found.session_id == "s1"


def test_resolver_does_not_cross_tenants():
    _sessions["s1"] = _fake_live_session("s1", tenant_id=12, case_id=3563)
    assert find_live_session_for_case(999, 3563) is None


def test_resolver_does_not_cross_cases():
    _sessions["s1"] = _fake_live_session("s1", tenant_id=12, case_id=3563)
    assert find_live_session_for_case(12, 999) is None


def test_resolver_returns_none_when_no_session_exists():
    assert find_live_session_for_case(12, 3563) is None


def test_resolver_fails_closed_on_multiple_matches():
    _sessions["s1"] = _fake_live_session("s1", tenant_id=12, case_id=3563)
    _sessions["s2"] = _fake_live_session("s2", tenant_id=12, case_id=3563)
    # Two sessions somehow open for the same tenant+case — must not pick
    # either one arbitrarily.
    assert find_live_session_for_case(12, 3563) is None


def test_resolver_is_read_only_never_mutates_or_closes():
    session = _fake_live_session("s1", tenant_id=12, case_id=3563)
    _sessions["s1"] = session
    with patch("modules.govt_sync.browser_session.close_session", new_callable=AsyncMock) as mock_close:
        found = find_live_session_for_case(12, 3563)
        assert found is session  # same object, untouched
        assert found.context is session.context  # nothing swapped out
        mock_close.assert_not_called()
    # Session is still present afterward — resolver never pops/removes it.
    assert "s1" in _sessions


# ─── Endpoint: /cases/{case_id}/govt/tamil-nadu/diagnostic/run ────────────

def test_endpoint_rejects_wrong_tenant_ownership():
    """Session exists, but for a DIFFERENT tenant than the caller's own —
    must 404, never reveal that a session exists for someone else."""
    _seed_database()
    _sessions["s1"] = _fake_live_session("s1", tenant_id=2, case_id=3999)  # tenant 2's own session
    resp = client.post("/api/cases/3999/govt/tamil-nadu/diagnostic/run", headers=_auth_headers())  # mp_priya is tenant 1
    assert resp.status_code == 404
    assert "s1" not in resp.text


def test_endpoint_rejects_case_belonging_to_different_tenant_even_with_a_live_session():
    _seed_database()
    _sessions["s1"] = _fake_live_session("s1", tenant_id=1, case_id=3999)  # wrong tenant/case pairing vs DB row
    resp = client.post("/api/cases/3999/govt/tamil-nadu/diagnostic/run", headers=_auth_headers())
    assert resp.status_code == 404


def test_endpoint_404s_when_no_matching_live_session_exists():
    _seed_database()
    resp = client.post("/api/cases/3563/govt/tamil-nadu/diagnostic/run", headers=_auth_headers())
    assert resp.status_code == 404


def test_endpoint_rejects_non_tamil_nadu_portal():
    _seed_database()
    non_tn_portal = {**_tn_portal(), "state": "Karnataka", "portal_name": "Karnataka Janaspandana (iPGRS)"}
    _sessions["s1"] = _fake_live_session("s1", tenant_id=1, case_id=3563, portal=non_tn_portal)
    resp = client.post("/api/cases/3563/govt/tamil-nadu/diagnostic/run", headers=_auth_headers())
    assert resp.status_code == 400


def test_endpoint_rejects_reference_outside_authorized_grievance():
    _seed_database()
    _sessions["s1"] = _fake_live_session("s1", tenant_id=1, case_id=3564)  # case 3564 has OTHER_REF, not 18968314
    resp = client.post("/api/cases/3564/govt/tamil-nadu/diagnostic/run", headers=_auth_headers())
    assert resp.status_code == 403


def test_endpoint_invokes_diagnostic_harness_with_resolved_session():
    _seed_database()
    fake_session = _fake_live_session("s1", tenant_id=1, case_id=3563)
    _sessions["s1"] = fake_session
    fake_report = MagicMock()
    fake_report.outcome = "HTTP_SUCCESS"
    fake_report.to_safe_dict.return_value = {"outcome": "HTTP_SUCCESS"}
    with patch("modules.govt_sync.status.tn_network_diagnostic.capture_tn_diagnostic", new_callable=AsyncMock) as mock_capture:
        mock_capture.return_value = fake_report
        resp = client.post("/api/cases/3563/govt/tamil-nadu/diagnostic/run", headers=_auth_headers())
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"outcome": "HTTP_SUCCESS"}
    mock_capture.assert_awaited_once()
    called_session, called_ref = mock_capture.await_args.args
    assert called_session is fake_session  # the internally-resolved session, not a new one
    assert called_ref == REF


def test_endpoint_never_arms_or_consumes_the_runtime_gate():
    """This endpoint must bypass tn_diagnostic_runtime_gate.py entirely —
    it re-verifies ownership fresh every call, so there is nothing for the
    arm/consume gate to protect here."""
    _seed_database()
    _sessions["s1"] = _fake_live_session("s1", tenant_id=1, case_id=3563)
    fake_report = MagicMock()
    fake_report.outcome = "HTTP_SUCCESS"
    fake_report.to_safe_dict.return_value = {"outcome": "HTTP_SUCCESS"}
    with patch("modules.govt_sync.status.tn_network_diagnostic.capture_tn_diagnostic", new_callable=AsyncMock) as mock_capture, \
         patch("modules.govt_sync.status.tn_diagnostic_runtime_gate.arm", new_callable=AsyncMock) as mock_arm, \
         patch("modules.govt_sync.status.tn_diagnostic_runtime_gate.consume_if_armed", new_callable=AsyncMock) as mock_consume:
        mock_capture.return_value = fake_report
        resp = client.post("/api/cases/3563/govt/tamil-nadu/diagnostic/run", headers=_auth_headers())
    assert resp.status_code == 200, resp.text
    mock_arm.assert_not_called()
    mock_consume.assert_not_called()


def test_endpoint_can_be_called_again_after_a_successful_run_unlike_the_gated_endpoint():
    """No single-use consumption here by design — ownership is re-verified
    fresh every call, so a second call with the same live session still
    open must succeed again (contrast with the session-ID-based endpoint's
    single-use grant)."""
    _seed_database()
    _sessions["s1"] = _fake_live_session("s1", tenant_id=1, case_id=3563)
    fake_report = MagicMock()
    fake_report.outcome = "HTTP_SUCCESS"
    fake_report.to_safe_dict.return_value = {"outcome": "HTTP_SUCCESS"}
    with patch("modules.govt_sync.status.tn_network_diagnostic.capture_tn_diagnostic", new_callable=AsyncMock) as mock_capture:
        mock_capture.return_value = fake_report
        first = client.post("/api/cases/3563/govt/tamil-nadu/diagnostic/run", headers=_auth_headers())
        second = client.post("/api/cases/3563/govt/tamil-nadu/diagnostic/run", headers=_auth_headers())
    assert first.status_code == 200
    assert second.status_code == 200
    assert mock_capture.await_count == 2


# ─── Security: session_id must never surface anywhere ──────────────────────

def test_session_id_never_appears_in_successful_response_body():
    _seed_database()
    _sessions["a-very-distinctive-session-id-12345"] = _fake_live_session(
        "a-very-distinctive-session-id-12345", tenant_id=1, case_id=3563,
    )
    fake_report = MagicMock()
    fake_report.outcome = "HTTP_SUCCESS"
    fake_report.to_safe_dict.return_value = {"outcome": "HTTP_SUCCESS"}
    with patch("modules.govt_sync.status.tn_network_diagnostic.capture_tn_diagnostic", new_callable=AsyncMock) as mock_capture:
        mock_capture.return_value = fake_report
        resp = client.post("/api/cases/3563/govt/tamil-nadu/diagnostic/run", headers=_auth_headers())
    assert "a-very-distinctive-session-id-12345" not in resp.text


def test_session_id_never_appears_in_error_responses():
    _seed_database()
    _sessions["a-very-distinctive-session-id-12345"] = _fake_live_session(
        "a-very-distinctive-session-id-12345", tenant_id=2, case_id=3999,  # wrong tenant vs caller
    )
    resp = client.post("/api/cases/3999/govt/tamil-nadu/diagnostic/run", headers=_auth_headers())
    assert resp.status_code == 404
    assert "a-very-distinctive-session-id-12345" not in resp.text


def test_session_id_never_appears_in_audit_log_payload():
    _seed_database()
    _sessions["a-very-distinctive-session-id-12345"] = _fake_live_session(
        "a-very-distinctive-session-id-12345", tenant_id=1, case_id=3563,
    )
    fake_report = MagicMock()
    fake_report.outcome = "HTTP_SUCCESS"
    fake_report.to_safe_dict.return_value = {"outcome": "HTTP_SUCCESS"}
    with patch("modules.govt_sync.status.tn_network_diagnostic.capture_tn_diagnostic", new_callable=AsyncMock) as mock_capture:
        mock_capture.return_value = fake_report
        client.post("/api/cases/3563/govt/tamil-nadu/diagnostic/run", headers=_auth_headers())
    with test_engine.connect() as conn:
        rows = list(conn.execute(
            text("SELECT action, payload FROM govt_submission_log WHERE case_id = 3563 ORDER BY id")
        ))
    assert len(rows) == 1
    assert rows[0][0] == "TN_HTTP_DIAGNOSTIC_RUN"
    assert "a-very-distinctive-session-id-12345" not in str(rows[0][1])
    assert "session_id" not in str(rows[0][1])  # not even the key name is present for this invocation path


def test_resolver_source_never_logs_session_id():
    """Static, defense-in-depth proof: find_live_session_for_case's own
    source contains no logging call at all — it cannot log session_id
    because it never calls logger.* in the first place."""
    import inspect

    from modules.govt_sync import browser_session
    source = inspect.getsource(browser_session.find_live_session_for_case)
    assert "logger." not in source
    assert "print(" not in source
