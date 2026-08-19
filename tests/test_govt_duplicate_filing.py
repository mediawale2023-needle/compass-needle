import json
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
TEST_DB_URL = "sqlite:///./test_govt_duplicate_filing.db"

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


import admin_api
import api_router
import core.db_helpers as db_helpers
import main
import sansadx_backend.db as dbmod
from sansadx_backend.db import Base, hash_password


test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False)
client = TestClient(main.app, raise_server_exceptions=False)


def _bind_engines():
    dbmod.engine = test_engine
    dbmod.SessionLocal = TestSession
    db_helpers.engine = test_engine
    main.engine = test_engine
    api_router.engine = test_engine
    admin_api.engine = test_engine
    api_router.JWT_SECRET = TEST_JWT_SECRET
    admin_api.JWT_SECRET = TEST_JWT_SECRET


def _auth_headers(username: str = "mp_arun") -> dict[str, str]:
    token = jwt.encode(
        {
            "sub": username,
            "exp": _utcnow() + timedelta(hours=8),
            "iat": _utcnow().timestamp(),
        },
        TEST_JWT_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def _seed_database():
    _bind_engines()
    Base.metadata.create_all(bind=test_engine)
    now = _utcnow()
    worksheet = json.dumps({"department": "BBMP", "subject": "Water", "description": "No water"})

    with test_engine.begin() as conn:
        for table_name in (
            "govt_submission_log",
            "case_activity_log",
            "cases",
            "govt_portals",
            "tenant_overrides",
            "token_blocklist",
            "users",
            "tenant_profiles",
            "tenants",
        ):
            conn.execute(text(f"DELETE FROM {table_name}"))  # nosec B608

        conn.execute(
            text(
                """
                INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active, created_at)
                VALUES (1, 'Arun Kumar', 'Bangalore North', '+919000000001', 'Pro', 1, :now)
                """
            ),
            {"now": now},
        )
        conn.execute(
            text(
                """
                INSERT INTO tenant_profiles (tenant_id, mp_name, constituency, state, house, created_at)
                VALUES (1, 'Shri Arun Kumar', 'Bangalore North', 'Karnataka', 'Lok Sabha', :now)
                """
            ),
            {"now": now},
        )
        conn.execute(
            text(
                """
                INSERT INTO users (tenant_id, username, password_hash, role, constituency, house, display_name, is_active)
                VALUES (1, 'mp_arun', :password_hash, 'mp', 'Bangalore North', 'Lok Sabha', 'Arun MP', 1)
                """
            ),
            {"password_hash": hash_password("Password1")},
        )
        conn.execute(
            text(
                """
                INSERT INTO govt_portals (
                    id, state, portal_name, portal_type, base_url, status_check_mode,
                    department_taxonomy, field_schema, otp_bound, active, is_primary, verification_status,
                    live_session_supported
                ) VALUES (
                    1, 'Karnataka', 'Karnataka iPGRS', 'state_branded', 'https://example.portal/file',
                    'login_required', :taxonomy, :schema, 1, 1, 1, 'unverified', 1
                )
                """
            ),
            {"taxonomy": json.dumps({"Water": "Water"}), "schema": json.dumps({})},
        )
        conn.execute(
            text(
                """
                INSERT INTO cases (
                    id, tenant_id, user_phone, raw_message, category, status, created_at,
                    govt_portal_id, govt_status, govt_reference_number, govt_submission_worksheet, is_deleted
                ) VALUES
                    (10, 1, '+919111111111', 'Already filed', 'Infrastructure & Utilities', 'in_progress', :now,
                     1, 'submitted', 'PORTAL-111', :ws, 0),
                    (11, 1, '+919111111112', 'Submitted keep ref', 'Infrastructure & Utilities', 'in_progress', :now,
                     1, 'submitted', 'KEEP-ME', :ws, 0),
                    (12, 1, '+919111111113', 'Ready to file', 'Infrastructure & Utilities', 'new', :now,
                     1, 'pending_staff_submit', NULL, :ws, 0)
                """
            ),
            {"now": now, "ws": worksheet},
        )

        # A second tenant/portal pair for the live_session_supported=false path —
        # tenant 1's state (Karnataka) always resolves to portal 1, so this needs
        # its own tenant/state to resolve to a manual-only portal.
        conn.execute(
            text(
                """
                INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active, created_at)
                VALUES (2, 'Priya Sharma', 'Kalyan Dombivli', '+919000000002', 'Pro', 1, :now)
                """
            ),
            {"now": now},
        )
        conn.execute(
            text(
                """
                INSERT INTO tenant_profiles (tenant_id, mp_name, constituency, state, house, created_at)
                VALUES (2, 'Shri Priya Sharma', 'Kalyan Dombivli', 'Maharashtra', 'Lok Sabha', :now)
                """
            ),
            {"now": now},
        )
        conn.execute(
            text(
                """
                INSERT INTO users (tenant_id, username, password_hash, role, constituency, house, display_name, is_active)
                VALUES (2, 'mp_priya', :password_hash, 'mp', 'Kalyan Dombivli', 'Lok Sabha', 'Priya MP', 1)
                """
            ),
            {"password_hash": hash_password("Password1")},
        )
        conn.execute(
            text(
                """
                INSERT INTO govt_portals (
                    id, state, portal_name, portal_type, base_url, status_check_mode,
                    department_taxonomy, field_schema, otp_bound, active, is_primary, verification_status,
                    live_session_supported
                ) VALUES (
                    2, 'Maharashtra', 'Maharashtra Aaple Sarkar Grievance Redressal', 'state_branded',
                    'https://grievances.maharashtra.gov.in', 'login_required', :taxonomy, :schema, 1, 1, 1,
                    'confirmed', 0
                )
                """
            ),
            {"taxonomy": json.dumps({"Water": "Public Works Department"}), "schema": json.dumps({"entry_path": None})},
        )
        conn.execute(
            text(
                """
                INSERT INTO cases (
                    id, tenant_id, user_phone, raw_message, category, status, created_at,
                    govt_portal_id, govt_status, govt_reference_number, govt_submission_worksheet, is_deleted
                ) VALUES
                    (13, 2, '+919111111114', 'Manual-only portal case', 'Infrastructure & Utilities', 'new', :now,
                     NULL, 'not_forwarded', NULL, NULL, 0)
                """
            ),
            {"now": now},
        )


def test_session_start_409_when_submitted_with_reference():
    _seed_database()
    with patch("modules.govt_sync.browser_session.start_session", new_callable=AsyncMock) as start_session:
        resp = client.post("/api/cases/10/govt/session/start", headers=_auth_headers(), json={})
    assert resp.status_code == 409, resp.text
    assert "PORTAL-111" in resp.json()["detail"]
    start_session.assert_not_called()


def test_submit_same_reference_is_noop():
    _seed_database()
    resp = client.post(
        "/api/cases/11/govt/submit",
        headers=_auth_headers(),
        json={"reference_number": "KEEP-ME"},
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["success"] is True
    assert payload["govt_reference_number"] == "KEEP-ME"
    assert payload.get("idempotent") is True

    with test_engine.begin() as conn:
        row = conn.execute(
            text("SELECT govt_reference_number, govt_status FROM cases WHERE id = 11")
        ).mappings().one()
    assert row["govt_reference_number"] == "KEEP-ME"
    assert row["govt_status"] == "submitted"


def test_submit_different_reference_conflicts():
    _seed_database()
    resp = client.post(
        "/api/cases/11/govt/submit",
        headers=_auth_headers(),
        json={"reference_number": "OTHER-REF"},
    )
    assert resp.status_code == 409, resp.text
    assert "KEEP-ME" in resp.json()["detail"]

    with test_engine.begin() as conn:
        stored = conn.execute(
            text("SELECT govt_reference_number FROM cases WHERE id = 11")
        ).scalar_one()
    assert stored == "KEEP-ME"


def test_session_start_allowed_by_default_when_pending_without_reference():
    # No GOVT_LIVE_AUTOMATION_ENABLED set — must default to on. Live sessions
    # (open the portal, stream it, auto-navigate post-login) are the intended
    # default behavior; only autofilling grievance fields was removed, not
    # opening the session itself. start_session() no longer takes worksheet/
    # contact/filer args — nothing is auto-filled, so nothing to pass in.
    _seed_database()
    os.environ.pop("GOVT_LIVE_AUTOMATION_ENABLED", None)
    fake = MagicMock()
    fake.session_id = "sess-pending"
    with patch("modules.govt_sync.browser_session.start_session", new_callable=AsyncMock, return_value=fake) as start_session, \
            patch("api_router._log_govt_action"):
        resp = client.post("/api/cases/12/govt/session/start", headers=_auth_headers(), json={})
    assert resp.status_code == 200, resp.text
    assert resp.json()["session_id"] == "sess-pending"
    start_session.assert_awaited_once()
    # Confirms no worksheet/PII data is threaded into the browser session —
    # start_session(tid, case_id, portal) is the entire call signature now.
    assert len(start_session.await_args.args) == 3


def test_session_start_403_when_automation_explicitly_disabled():
    # Emergency off switch — e.g. a specific portal starts blocking the
    # shared EC2 IP. Does not require redeploying, just flipping the env var.
    _seed_database()
    with patch.dict(os.environ, {"GOVT_LIVE_AUTOMATION_ENABLED": "false"}), \
            patch("modules.govt_sync.browser_session.start_session", new_callable=AsyncMock) as start_session:
        resp = client.post("/api/cases/12/govt/session/start", headers=_auth_headers(), json={})
    assert resp.status_code == 403, resp.text
    start_session.assert_not_called()


def test_govt_portal_reports_live_automation_flag():
    _seed_database()
    os.environ.pop("GOVT_LIVE_AUTOMATION_ENABLED", None)
    resp = client.get("/api/govt-portal", headers=_auth_headers())
    assert resp.status_code == 200, resp.text
    assert resp.json()["live_automation_enabled"] is True

    with patch.dict(os.environ, {"GOVT_LIVE_AUTOMATION_ENABLED": "false"}):
        resp = client.get("/api/govt-portal", headers=_auth_headers())
    assert resp.status_code == 200, resp.text
    assert resp.json()["live_automation_enabled"] is False


def test_already_filed_409_takes_priority_over_automation_disabled():
    # Case 10 already has a reference on record. Even with the emergency
    # switch off, staff must see the "already filed" detail (with the
    # reference), not a generic "automation is off" message that hides the
    # more important fact.
    _seed_database()
    with patch.dict(os.environ, {"GOVT_LIVE_AUTOMATION_ENABLED": "false"}):
        resp = client.post("/api/cases/10/govt/session/start", headers=_auth_headers(), json={})
    assert resp.status_code == 409, resp.text
    assert "PORTAL-111" in resp.json()["detail"]


def _fake_live_session(session_id, tenant_id, case_id, portal_name="Test portal"):
    from modules.govt_sync import browser_session
    session = browser_session.LiveSession(
        session_id=session_id,
        tenant_id=tenant_id,
        case_id=case_id,
        portal={"portal_name": portal_name},
        context=MagicMock(),
        page=MagicMock(),
        cdp=MagicMock(),
    )
    session.cdp.send = AsyncMock()
    session.context.close = AsyncMock()
    return session


def test_govt_sessions_list_is_empty_without_live_browsers():
    _seed_database()
    resp = client.get("/api/govt/sessions", headers=_auth_headers())
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["sessions"] == []
    assert payload["tenant_count"] == 0
    assert payload["max_concurrent"] >= 1


def test_govt_sessions_list_and_close_are_tenant_scoped():
    _seed_database()
    from modules.govt_sync import browser_session
    mine = _fake_live_session("sess-mine", 1, 12)
    other = _fake_live_session("sess-other", 99, 1)
    browser_session._sessions.clear()
    browser_session._sessions["sess-mine"] = mine
    browser_session._sessions["sess-other"] = other
    try:
        listed = client.get("/api/govt/sessions", headers=_auth_headers())
        assert listed.status_code == 200, listed.text
        ids = {row["session_id"] for row in listed.json()["sessions"]}
        assert ids == {"sess-mine"}

        other_close = client.post("/api/govt/sessions/sess-other/close", headers=_auth_headers())
        assert other_close.status_code == 200
        assert "sess-other" in browser_session._sessions

        mine_close = client.post("/api/govt/sessions/sess-mine/close", headers=_auth_headers())
        assert mine_close.status_code == 200
        assert "sess-mine" not in browser_session._sessions
        assert "sess-other" in browser_session._sessions
    finally:
        browser_session._sessions.clear()


def test_govt_sessions_close_all_only_this_tenant():
    _seed_database()
    from modules.govt_sync import browser_session
    browser_session._sessions.clear()
    browser_session._sessions["a"] = _fake_live_session("a", 1, 12)
    browser_session._sessions["b"] = _fake_live_session("b", 1, 11)
    browser_session._sessions["c"] = _fake_live_session("c", 99, 1)
    try:
        resp = client.post("/api/govt/sessions/close-all", headers=_auth_headers())
        assert resp.status_code == 200, resp.text
        assert resp.json()["closed"] == 2
        assert set(browser_session._sessions) == {"c"}
    finally:
        browser_session._sessions.clear()


def test_session_start_403_when_portal_does_not_support_live_sessions():
    # Portal 2 (Maharashtra) is live_session_supported=0 — a confirmed
    # network-level block on our EC2 IP, not the global automation switch.
    # Must 403 even with automation explicitly on, and never reach start_session.
    _seed_database()
    with patch.dict(os.environ, {"GOVT_LIVE_AUTOMATION_ENABLED": "true"}), \
            patch("modules.govt_sync.browser_session.start_session", new_callable=AsyncMock) as start_session:
        resp = client.post("/api/cases/13/govt/session/start", headers=_auth_headers("mp_priya"), json={})
    assert resp.status_code == 403, resp.text
    assert "Maharashtra Aaple Sarkar Grievance Redressal" in resp.json()["detail"]
    start_session.assert_not_called()


def test_govt_portal_reports_live_session_supported_and_entry_url():
    _seed_database()
    resp = client.get("/api/govt-portal", headers=_auth_headers("mp_priya"))
    assert resp.status_code == 200, resp.text
    portal = resp.json()["portal"]
    assert portal["live_session_supported"] is False
    assert portal["entry_url"] == "https://grievances.maharashtra.gov.in"

    # Contrast: tenant 1's Karnataka portal supports live sessions.
    resp2 = client.get("/api/govt-portal", headers=_auth_headers())
    assert resp2.status_code == 200, resp2.text
    assert resp2.json()["portal"]["live_session_supported"] is True

