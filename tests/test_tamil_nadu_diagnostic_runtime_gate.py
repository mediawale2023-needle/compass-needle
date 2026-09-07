"""
tests/test_tamil_nadu_diagnostic_runtime_gate.py — process-local, single-use
runtime gate for the TN HTTP-diagnostic proof
(modules/govt_sync/status/tn_diagnostic_runtime_gate.py), added so the
diagnostic can be enabled for exactly one controlled run WITHOUT recreating
backend_govt_live (which would destroy the in-memory Playwright LiveSession
the diagnostic needs to observe).

Everything here is mocked: no real Playwright browser, no real HTTP request,
no real government portal, and — the property this file exists specifically
to prove — no interaction whatsoever with browser_session.py's LiveSession
state. This file only proves the gate's own mechanics and the two endpoints
built on it; it never runs a real diagnostic proof.
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
TEST_DB_URL = "sqlite:///./test_tamil_nadu_diagnostic_runtime_gate.db"

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

from modules.govt_sync.status import tn_diagnostic_runtime_gate as gate
from tests.test_tamil_nadu_status import REF, _tn_portal

test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False)
client = TestClient(main.app, raise_server_exceptions=False)


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
            f"(40, 1, '+919111111140', 'No food ration', 'Infrastructure & Utilities', 'in_progress', :now, "
            f"1, 'submitted', '{REF}', 0)"
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
            f"(41, 2, '+919111111141', 'Other case', 'Infrastructure & Utilities', 'in_progress', :now, "
            f"1, 'submitted', 'TN/OTHER/CASE/P/PORTAL/01SEP26/99999999', 0)"
        ), {"now": now})


def setup_function(_fn):
    # The gate's module-level dict is process-local by design — clear it
    # between tests so one test's grant can never leak into another.
    gate._grants.clear()


# ─── Gate module — pure mechanics, no Playwright, no browser_session ───────

def test_arm_then_consume_exact_match_succeeds_once():
    async def run():
        await gate.arm(tenant_id=1, case_id=40, session_id="sess-1", reference_number=REF)
        first = await gate.consume_if_armed(tenant_id=1, case_id=40, session_id="sess-1", reference_number=REF)
        second = await gate.consume_if_armed(tenant_id=1, case_id=40, session_id="sess-1", reference_number=REF)
        return first, second
    first, second = asyncio.run(run())
    assert first is True
    assert second is False  # already consumed


def test_consume_fails_on_tenant_mismatch():
    async def run():
        await gate.arm(tenant_id=1, case_id=40, session_id="sess-1", reference_number=REF)
        return await gate.consume_if_armed(tenant_id=999, case_id=40, session_id="sess-1", reference_number=REF)
    assert asyncio.run(run()) is False


def test_consume_fails_on_case_mismatch():
    async def run():
        await gate.arm(tenant_id=1, case_id=40, session_id="sess-1", reference_number=REF)
        return await gate.consume_if_armed(tenant_id=1, case_id=999, session_id="sess-1", reference_number=REF)
    assert asyncio.run(run()) is False


def test_consume_fails_on_session_mismatch():
    async def run():
        await gate.arm(tenant_id=1, case_id=40, session_id="sess-1", reference_number=REF)
        return await gate.consume_if_armed(tenant_id=1, case_id=40, session_id="sess-other", reference_number=REF)
    assert asyncio.run(run()) is False


def test_consume_fails_on_reference_mismatch():
    async def run():
        await gate.arm(tenant_id=1, case_id=40, session_id="sess-1", reference_number=REF)
        return await gate.consume_if_armed(tenant_id=1, case_id=40, session_id="sess-1", reference_number="TN/OTHER/CASE/P/PORTAL/01SEP26/99999999")
    assert asyncio.run(run()) is False


def test_consume_fails_when_never_armed():
    async def run():
        return await gate.consume_if_armed(tenant_id=1, case_id=40, session_id="never-armed", reference_number=REF)
    assert asyncio.run(run()) is False


def test_grant_expires_after_ttl():
    async def run():
        await gate.arm(tenant_id=1, case_id=40, session_id="sess-1", reference_number=REF)
        with patch("time.monotonic", return_value=__import__("time").monotonic() + gate.TTL_SECONDS + 1):
            return await gate.consume_if_armed(tenant_id=1, case_id=40, session_id="sess-1", reference_number=REF)
    assert asyncio.run(run()) is False


def test_grant_still_valid_just_under_ttl():
    async def run():
        await gate.arm(tenant_id=1, case_id=40, session_id="sess-1", reference_number=REF)
        with patch("time.monotonic", return_value=__import__("time").monotonic() + gate.TTL_SECONDS - 5):
            return await gate.consume_if_armed(tenant_id=1, case_id=40, session_id="sess-1", reference_number=REF)
    assert asyncio.run(run()) is True


def test_disarm_prevents_subsequent_consume():
    async def run():
        await gate.arm(tenant_id=1, case_id=40, session_id="sess-1", reference_number=REF)
        await gate.disarm(session_id="sess-1")
        return await gate.consume_if_armed(tenant_id=1, case_id=40, session_id="sess-1", reference_number=REF)
    assert asyncio.run(run()) is False


def test_disarm_is_idempotent_and_never_raises():
    async def run():
        await gate.disarm(session_id="never-armed")
        await gate.disarm(session_id="never-armed")
    asyncio.run(run())  # must not raise


def test_has_pending_grant_reflects_presence_only_not_validity():
    async def run():
        assert gate.has_pending_grant("sess-1") is False
        await gate.arm(tenant_id=1, case_id=40, session_id="sess-1", reference_number=REF)
        assert gate.has_pending_grant("sess-1") is True
        # Presence is true even for a tenant/case that would NOT match on
        # a real consume — has_pending_grant is a cheap pre-check only,
        # never an authorization decision by itself.
        assert gate.has_pending_grant("sess-1") is True
        await gate.disarm(session_id="sess-1")
        assert gate.has_pending_grant("sess-1") is False
    asyncio.run(run())


def test_concurrent_consume_exactly_one_succeeds():
    async def run():
        await gate.arm(tenant_id=1, case_id=40, session_id="sess-1", reference_number=REF)
        results = await asyncio.gather(
            gate.consume_if_armed(tenant_id=1, case_id=40, session_id="sess-1", reference_number=REF),
            gate.consume_if_armed(tenant_id=1, case_id=40, session_id="sess-1", reference_number=REF),
        )
        return results
    results = asyncio.run(run())
    assert sorted(results) == [False, True]


def test_arming_a_second_time_replaces_the_prior_grant():
    async def run():
        await gate.arm(tenant_id=1, case_id=40, session_id="sess-1", reference_number=REF)
        await gate.arm(tenant_id=1, case_id=40, session_id="sess-1", reference_number=REF)  # re-arm
        first = await gate.consume_if_armed(tenant_id=1, case_id=40, session_id="sess-1", reference_number=REF)
        second = await gate.consume_if_armed(tenant_id=1, case_id=40, session_id="sess-1", reference_number=REF)
        return first, second
    first, second = asyncio.run(run())
    assert first is True
    assert second is False  # re-arming did not create a second, separately-consumable grant


def test_gate_never_touches_browser_session_state():
    """The core safety property: arming, consuming, and disarming a grant
    must never read or mutate anything in modules.govt_sync.browser_session
    — no LiveSession lookup, no _sessions access, no close_session call."""
    with patch("modules.govt_sync.browser_session.get_live_session") as mock_get, \
         patch("modules.govt_sync.browser_session.close_session") as mock_close, \
         patch("modules.govt_sync.browser_session.get_session_meta") as mock_meta:
        async def run():
            await gate.arm(tenant_id=1, case_id=40, session_id="sess-1", reference_number=REF)
            await gate.consume_if_armed(tenant_id=1, case_id=40, session_id="sess-1", reference_number=REF)
            await gate.arm(tenant_id=1, case_id=40, session_id="sess-2", reference_number=REF)
            await gate.disarm(session_id="sess-2")
            gate.has_pending_grant("sess-3")
        asyncio.run(run())
    mock_get.assert_not_called()
    mock_close.assert_not_called()
    mock_meta.assert_not_called()


def test_gate_module_has_no_import_of_browser_session():
    """Defense-in-depth, static proof alongside the behavioral one above:
    the gate module's own source never contains an import statement
    referencing browser_session (mentioning it in prose/comments is fine —
    this checks actual import/from nodes only, via the AST, not a raw
    substring match)."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(gate))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "browser_session" not in alias.name
        elif isinstance(node, ast.ImportFrom):
            assert not (node.module and "browser_session" in node.module)


# ─── Endpoint-level tests (TestClient, fully mocked live session) ──────────

def _fake_session(*, tenant_id=1, case_id=40, portal=None):
    return MagicMock(tenant_id=tenant_id, case_id=case_id, portal=portal or _tn_portal())


def test_arm_endpoint_succeeds_for_owned_session_and_allowed_reference():
    _seed_database()
    with patch("modules.govt_sync.browser_session.get_live_session", return_value=_fake_session()):
        resp = client.post(
            "/api/cases/40/govt/session/real-session-id/tamil-nadu/diagnostic/arm",
            json={"action": "arm"}, headers=_auth_headers(),
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["armed"] is True
    assert body["expires_in_seconds"] == gate.TTL_SECONDS
    assert gate.has_pending_grant("real-session-id") is True


def test_arm_endpoint_rejects_reference_outside_authorized_grievance():
    _seed_database()
    with test_engine.begin() as conn:
        conn.execute(text(
            "UPDATE cases SET govt_reference_number = 'TN/OTHER/CASE/P/PORTAL/01SEP26/99999999' WHERE id = 40"
        ))
    with patch("modules.govt_sync.browser_session.get_live_session", return_value=_fake_session()):
        resp = client.post(
            "/api/cases/40/govt/session/real-session-id/tamil-nadu/diagnostic/arm",
            json={"action": "arm"}, headers=_auth_headers(),
        )
    assert resp.status_code == 403
    assert gate.has_pending_grant("real-session-id") is False


def test_arm_endpoint_rejects_session_not_owned_by_caller_tenant():
    _seed_database()
    with patch("modules.govt_sync.browser_session.get_live_session", return_value=_fake_session(tenant_id=2, case_id=41)):
        resp = client.post(
            "/api/cases/40/govt/session/real-session-id/tamil-nadu/diagnostic/arm",
            json={"action": "arm"}, headers=_auth_headers(),  # mp_priya is tenant 1, session belongs to tenant 2
        )
    assert resp.status_code == 404
    assert gate.has_pending_grant("real-session-id") is False


def test_arm_endpoint_rejects_invalid_action():
    _seed_database()
    with patch("modules.govt_sync.browser_session.get_live_session", return_value=_fake_session()):
        resp = client.post(
            "/api/cases/40/govt/session/real-session-id/tamil-nadu/diagnostic/arm",
            json={"action": "detonate"}, headers=_auth_headers(),
        )
    assert resp.status_code == 400


def test_disarm_endpoint_clears_a_grant():
    _seed_database()
    with patch("modules.govt_sync.browser_session.get_live_session", return_value=_fake_session()):
        client.post(
            "/api/cases/40/govt/session/real-session-id/tamil-nadu/diagnostic/arm",
            json={"action": "arm"}, headers=_auth_headers(),
        )
        assert gate.has_pending_grant("real-session-id") is True
        resp = client.post(
            "/api/cases/40/govt/session/real-session-id/tamil-nadu/diagnostic/arm",
            json={"action": "disarm"}, headers=_auth_headers(),
        )
    assert resp.status_code == 200
    assert resp.json() == {"armed": False}
    assert gate.has_pending_grant("real-session-id") is False


# ─── Diagnostic endpoint gate-integration tests ────────────────────────────

def test_diagnostic_endpoint_with_no_flag_and_no_grant_still_404s():
    """Regression pin: the pre-existing 'disabled -> 404 for everyone'
    behavior must be byte-for-byte unchanged for the overwhelming common
    case of no grant existing at all."""
    _seed_database()
    os.environ.pop("GOVT_SYNC_TN_HTTP_DIAGNOSTIC_ENABLED", None)
    with patch("modules.govt_sync.browser_session.get_live_session", return_value=_fake_session()):
        resp = client.post(
            "/api/cases/40/govt/session/real-session-id/tamil-nadu/diagnostic/http-replay-proof",
            headers=_auth_headers(),
        )
    assert resp.status_code == 404


def test_diagnostic_endpoint_runs_once_with_a_valid_grant_then_404s_again():
    _seed_database()
    fake_report = MagicMock()
    fake_report.outcome = "HTTP_SUCCESS"
    fake_report.to_safe_dict.return_value = {"outcome": "HTTP_SUCCESS"}
    with patch("modules.govt_sync.browser_session.get_live_session", return_value=_fake_session()), \
         patch("modules.govt_sync.status.tn_network_diagnostic.capture_tn_diagnostic", new_callable=AsyncMock) as mock_capture:
        mock_capture.return_value = fake_report
        client.post(
            "/api/cases/40/govt/session/real-session-id/tamil-nadu/diagnostic/arm",
            json={"action": "arm"}, headers=_auth_headers(),
        )
        first = client.post(
            "/api/cases/40/govt/session/real-session-id/tamil-nadu/diagnostic/http-replay-proof",
            headers=_auth_headers(),
        )
        second = client.post(
            "/api/cases/40/govt/session/real-session-id/tamil-nadu/diagnostic/http-replay-proof",
            headers=_auth_headers(),
        )
    assert first.status_code == 200, first.text
    assert first.json()["outcome"] == "HTTP_SUCCESS"
    mock_capture.assert_awaited_once()
    assert second.status_code == 404  # grant already consumed by the first call


def test_diagnostic_endpoint_with_flag_on_is_unaffected_by_gate():
    """Existing behavior when the deployment flag is ON must be preserved
    exactly — the runtime gate is purely additive and never interferes."""
    _seed_database()
    fake_report = MagicMock()
    fake_report.outcome = "HTTP_SUCCESS"
    fake_report.to_safe_dict.return_value = {"outcome": "HTTP_SUCCESS"}
    with patch.dict(os.environ, {"GOVT_SYNC_TN_HTTP_DIAGNOSTIC_ENABLED": "true"}), \
         patch("modules.govt_sync.browser_session.get_live_session", return_value=_fake_session()), \
         patch("modules.govt_sync.status.tn_network_diagnostic.capture_tn_diagnostic", new_callable=AsyncMock) as mock_capture:
        mock_capture.return_value = fake_report
        resp = client.post(
            "/api/cases/40/govt/session/real-session-id/tamil-nadu/diagnostic/http-replay-proof",
            headers=_auth_headers(),
        )
    assert resp.status_code == 200, resp.text
    assert gate.has_pending_grant("real-session-id") is False  # never touched — flag path bypasses the gate entirely


def test_diagnostic_endpoint_never_reachable_via_grant_for_a_different_session():
    """A grant armed for one session_id must not let a DIFFERENT session_id
    (even for the same tenant/case) run the diagnostic."""
    _seed_database()
    with patch("modules.govt_sync.browser_session.get_live_session", return_value=_fake_session()):
        client.post(
            "/api/cases/40/govt/session/real-session-id/tamil-nadu/diagnostic/arm",
            json={"action": "arm"}, headers=_auth_headers(),
        )
        resp = client.post(
            "/api/cases/40/govt/session/a-different-session-id/tamil-nadu/diagnostic/http-replay-proof",
            headers=_auth_headers(),
        )
    assert resp.status_code == 404
