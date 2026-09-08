"""
tests/test_tamil_nadu_http_replay_diagnostic_endpoint.py — the TEMPORARY
Phase 2 investigation endpoint, POST /cases/{case_id}/govt/tamil-nadu/
http-replay-diagnostic.

Everything here is mocked: no real Playwright browser, no real HTTP
request, no real government portal. capture_tn_http_replay_diagnostic()
itself (already unit-tested in test_tamil_nadu_http_replay_diagnostic.py)
is mocked here — this file proves the ENDPOINT's own contract: auth,
tenant/case ownership, hard scoping to case 3563 + grievance 18968314,
internal session resolution, primary-ticket-id discovery from
caller-supplied evidence, that the endpoint itself never touches
session.page/session.context or creates a new LiveSession, and that
session_id never surfaces anywhere in a response, error, or log payload.
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
TEST_DB_URL = "sqlite:///./test_tamil_nadu_http_replay_diagnostic_endpoint.db"

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

from modules.govt_sync.browser_session import LiveSession, _sessions
from tests.test_tamil_nadu_status import REF, _tn_portal

test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False)
client = TestClient(main.app, raise_server_exceptions=False)

OTHER_REF = "TN/OTHER/CASE/P/PORTAL/01SEP26/99999999"
_ENDPOINT = "/api/cases/{case_id}/govt/tamil-nadu/http-replay-diagnostic"
_TN_HOST = "cmhelpline.tnega.org"
_PRIMARY_ID = "35665012402750744"


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
        # The one authorized case: 3563, correct reference (contains 18968314).
        conn.execute(text(
            "INSERT INTO cases (id, tenant_id, user_phone, raw_message, category, status, created_at, "
            "govt_portal_id, govt_status, govt_reference_number, is_deleted) VALUES "
            f"(3563, 1, '+919111111140', 'No food ration', 'Infrastructure & Utilities', 'in_progress', :now, "
            f"1, 'submitted', '{REF}', 0)"
        ), {"now": now})
        # Same tenant, different case id, correct reference — proves the
        # case-id gate rejects on id alone, independent of reference.
        conn.execute(text(
            "INSERT INTO cases (id, tenant_id, user_phone, raw_message, category, status, created_at, "
            "govt_portal_id, govt_status, govt_reference_number, is_deleted) VALUES "
            f"(3565, 1, '+919111111143', 'Another grievance', 'Infrastructure & Utilities', 'in_progress', :now, "
            f"1, 'submitted', '{REF}', 0)"
        ), {"now": now})
        # Same tenant, case 3564, reference outside the authorized grievance.
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


def _fake_live_session(session_id, tenant_id, case_id, portal=None):
    return LiveSession(
        session_id=session_id, tenant_id=tenant_id, case_id=case_id,
        portal=portal if portal is not None else _tn_portal(),
        context=MagicMock(), page=MagicMock(), cdp=MagicMock(),
    )


def _evidence(*record_ids):
    return [{"url": f"https://{_TN_HOST}/portal/api/tickets/{rid}"} for rid in record_ids]


def _fake_report(outcome="HTTP_REPLAY_AUTHENTICATED", multiple=False):
    report = MagicMock()
    report.primary_attempt.outcome = outcome
    report.multiple_tickets_observed = multiple
    report.to_safe_dict.return_value = {
        "primary_attempt": {"outcome": outcome, "record_id": _PRIMARY_ID},
        "secondary_attempt": None,
        "multiple_tickets_observed": multiple,
    }
    return report


def setup_function(_fn):
    _sessions.clear()


def teardown_function(_fn):
    _sessions.clear()


def _patched(mock_return=None):
    return patch(
        "modules.govt_sync.status.tn_http_replay_diagnostic.capture_tn_http_replay_diagnostic",
        new_callable=AsyncMock, return_value=mock_return or _fake_report(),
    )


# ─── 1. Authentication required ─────────────────────────────────────────────

def test_authentication_required():
    _seed_database()
    resp = client.post(_ENDPOINT.format(case_id=3563), json={"network_evidence": _evidence(_PRIMARY_ID)})
    assert resp.status_code in (401, 403)


# ─── 2. Tenant ownership required ───────────────────────────────────────────

def test_tenant_ownership_required_rejects_case_from_different_tenant():
    _seed_database()
    # Case 3563 belongs to tenant 1; caller here is tenant 2.
    with _patched():
        resp = client.post(
            _ENDPOINT.format(case_id=3563), json={"network_evidence": _evidence(_PRIMARY_ID)},
            headers=_auth_headers("mp_other"),
        )
    assert resp.status_code == 404


def test_tenant_ownership_required_rejects_live_session_from_different_tenant_even_with_matching_case_row():
    _seed_database()
    # A session exists for (tenant=2, case=3563) — but case 3563 in the DB
    # belongs to tenant 1. The caller (tenant 1) must not see tenant 2's session.
    _sessions["s1"] = _fake_live_session("s1", tenant_id=2, case_id=3563)
    with _patched():
        resp = client.post(
            _ENDPOINT.format(case_id=3563), json={"network_evidence": _evidence(_PRIMARY_ID)},
            headers=_auth_headers("mp_priya"),
        )
    assert resp.status_code == 404


# ─── 3 & 4. Only case 3563 allowed, every other case rejected ──────────────

def test_case_3563_allowed():
    _seed_database()
    _sessions["s1"] = _fake_live_session("s1", tenant_id=1, case_id=3563)
    with _patched() as mock_capture:
        resp = client.post(
            _ENDPOINT.format(case_id=3563), json={"network_evidence": _evidence(_PRIMARY_ID)},
            headers=_auth_headers(),
        )
    assert resp.status_code == 200, resp.text
    mock_capture.assert_awaited_once()


@pytest.mark.parametrize("other_case_id", [3564, 3565, 3999, 1, 424242])
def test_every_other_case_is_rejected(other_case_id):
    _seed_database()
    # Even a case id that doesn't exist in the DB at all (424242) must
    # still 404 — the case-id gate runs BEFORE any DB query is attempted.
    _sessions["s1"] = _fake_live_session("s1", tenant_id=1, case_id=other_case_id)
    with _patched() as mock_capture:
        resp = client.post(
            _ENDPOINT.format(case_id=other_case_id), json={"network_evidence": _evidence(_PRIMARY_ID)},
            headers=_auth_headers(),
        )
    assert resp.status_code == 404
    mock_capture.assert_not_awaited()


# ─── 5. Reference 18968314 required ─────────────────────────────────────────

def test_reference_18968314_required_case_3563_with_wrong_reference_is_rejected():
    _seed_database()
    with test_engine.begin() as conn:
        conn.execute(
            text("UPDATE cases SET govt_reference_number = :ref WHERE id = 3563"),
            {"ref": OTHER_REF},
        )
    _sessions["s1"] = _fake_live_session("s1", tenant_id=1, case_id=3563)
    with _patched() as mock_capture:
        resp = client.post(
            _ENDPOINT.format(case_id=3563), json={"network_evidence": _evidence(_PRIMARY_ID)},
            headers=_auth_headers(),
        )
    assert resp.status_code == 403
    mock_capture.assert_not_awaited()


# ─── 6. Existing LiveSession resolved internally ────────────────────────────

def test_existing_live_session_is_resolved_internally_not_a_new_one():
    _seed_database()
    fake_session = _fake_live_session("s1", tenant_id=1, case_id=3563)
    _sessions["s1"] = fake_session
    with patch("modules.govt_sync.browser_session.start_session", new_callable=AsyncMock) as mock_start, \
         _patched() as mock_capture:
        resp = client.post(
            _ENDPOINT.format(case_id=3563), json={"network_evidence": _evidence(_PRIMARY_ID)},
            headers=_auth_headers(),
        )
    assert resp.status_code == 200, resp.text
    mock_start.assert_not_called()  # 11. no new LiveSession created
    called_session = mock_capture.await_args.args[0]
    assert called_session is fake_session  # the SAME object, not a new one


def test_no_matching_live_session_returns_404_before_invoking_harness():
    _seed_database()
    with _patched() as mock_capture:
        resp = client.post(
            _ENDPOINT.format(case_id=3563), json={"network_evidence": _evidence(_PRIMARY_ID)},
            headers=_auth_headers(),
        )
    assert resp.status_code == 404
    mock_capture.assert_not_awaited()


# ─── 9. Phase-2 harness invoked with the existing session/evidence ─────────

def test_harness_invoked_with_primary_id_discovered_from_supplied_evidence():
    _seed_database()
    fake_session = _fake_live_session("s1", tenant_id=1, case_id=3563)
    _sessions["s1"] = fake_session
    evidence = _evidence(_PRIMARY_ID, "999888777")
    with _patched() as mock_capture:
        resp = client.post(
            _ENDPOINT.format(case_id=3563), json={"network_evidence": evidence, "previous_attempt_at": 1234.5},
            headers=_auth_headers(),
        )
    assert resp.status_code == 200, resp.text
    mock_capture.assert_awaited_once()
    args, kwargs = mock_capture.await_args
    assert args[0] is fake_session
    assert args[1] == evidence
    assert kwargs["primary_record_id"] == _PRIMARY_ID  # first observed id, never guessed
    assert kwargs["previous_attempt_at"] == 1234.5


def test_missing_ticket_id_in_supplied_evidence_is_rejected():
    _seed_database()
    _sessions["s1"] = _fake_live_session("s1", tenant_id=1, case_id=3563)
    with _patched() as mock_capture:
        resp = client.post(
            _ENDPOINT.format(case_id=3563), json={"network_evidence": []},
            headers=_auth_headers(),
        )
    assert resp.status_code == 400
    mock_capture.assert_not_awaited()


# ─── 10. No browser navigation occurs ───────────────────────────────────────

def test_endpoint_never_touches_page_or_context_directly():
    _seed_database()
    fake_session = _fake_live_session("s1", tenant_id=1, case_id=3563)
    _sessions["s1"] = fake_session
    with _patched():
        resp = client.post(
            _ENDPOINT.format(case_id=3563), json={"network_evidence": _evidence(_PRIMARY_ID)},
            headers=_auth_headers(),
        )
    assert resp.status_code == 200, resp.text
    # capture_tn_http_replay_diagnostic is mocked out entirely, so if the
    # endpoint itself ever called .goto/.click/.new_page, it would have to
    # do so directly on these mocks — it never does.
    fake_session.page.goto.assert_not_called()
    fake_session.page.click.assert_not_called()
    fake_session.context.new_page.assert_not_called()
    fake_session.context.cookies.assert_not_called()


# ─── 12 & 13. Response shape — only the safe dict, nothing else ────────────

def test_response_is_exactly_the_safe_dict_nothing_added():
    _seed_database()
    _sessions["s1"] = _fake_live_session("s1", tenant_id=1, case_id=3563)
    fake_report = _fake_report()
    with _patched(fake_report):
        resp = client.post(
            _ENDPOINT.format(case_id=3563), json={"network_evidence": _evidence(_PRIMARY_ID)},
            headers=_auth_headers(),
        )
    assert resp.status_code == 200
    assert resp.json() == fake_report.to_safe_dict.return_value
    for forbidden in ("cookie", "Cookie", "Set-Cookie", "Authorization", "session_id", "csrf", "CSRF", "jwt", "JWT"):
        assert forbidden not in resp.text


# ─── 7 & 8. session_id never surfaces anywhere ──────────────────────────────

def test_session_id_never_appears_in_successful_response_body():
    _seed_database()
    _sessions["a-very-distinctive-session-id-12345"] = _fake_live_session(
        "a-very-distinctive-session-id-12345", tenant_id=1, case_id=3563,
    )
    with _patched():
        resp = client.post(
            _ENDPOINT.format(case_id=3563), json={"network_evidence": _evidence(_PRIMARY_ID)},
            headers=_auth_headers(),
        )
    assert resp.status_code == 200
    assert "a-very-distinctive-session-id-12345" not in resp.text


def test_session_id_never_appears_in_error_responses():
    _seed_database()
    _sessions["a-very-distinctive-session-id-12345"] = _fake_live_session(
        "a-very-distinctive-session-id-12345", tenant_id=2, case_id=3563,  # wrong tenant vs caller
    )
    resp = client.post(
        _ENDPOINT.format(case_id=3563), json={"network_evidence": _evidence(_PRIMARY_ID)},
        headers=_auth_headers("mp_priya"),
    )
    assert resp.status_code == 404
    assert "a-very-distinctive-session-id-12345" not in resp.text


def test_session_id_never_appears_in_audit_log_payload():
    _seed_database()
    _sessions["a-very-distinctive-session-id-12345"] = _fake_live_session(
        "a-very-distinctive-session-id-12345", tenant_id=1, case_id=3563,
    )
    with _patched(), patch("api_router._log_govt_action") as mock_log:
        resp = client.post(
            _ENDPOINT.format(case_id=3563), json={"network_evidence": _evidence(_PRIMARY_ID)},
            headers=_auth_headers(),
        )
    assert resp.status_code == 200, resp.text
    mock_log.assert_called_once()
    logged = str(mock_log.call_args)
    assert "a-very-distinctive-session-id-12345" not in logged
