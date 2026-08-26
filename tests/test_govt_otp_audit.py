"""
tests/test_govt_otp_audit.py — audit logging for Rajasthan Sampark's
portal-access OTP endpoints (production-readiness review, K4).

/govt/otp/send and /govt/otp/verify previously called _log_govt_action
nowhere at all — a send/verify attempt (success or failure) left zero
durable trail, the same class of silent gap Step 3 closed for interactive
CAPTCHA/OTP attempts. Both endpoints now log via the SAME _log_govt_action
mechanism every other govt_submission_log row in this codebase uses — no
second logging mechanism, no schema change. Since neither endpoint is
case-scoped in its own request (an OTP verifies a MOBILE NUMBER, good for
every case on that portal) but govt_submission_log.case_id is NOT NULL,
both endpoints log against the same "anchor" case (any one of this
tenant's own filed references on the portal) they already need/can cheaply
look up — exactly the convention documented at the call sites.

Two layers, matching the project's established pattern: TestClient + SQLite
harness (see tests/test_karnataka_status_check.py), with
rajasthan_sampark.py's real requests.post gateway call mocked — never a
live network call.
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
TEST_DB_URL = "sqlite:///./test_govt_otp_audit.db"

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


def _auth_headers(username: str = "mp_kavita") -> dict[str, str]:
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
        # The ORM model alone doesn't declare this — real production DDL
        # adds it separately (main.py's govt_otp_sessions migration).
        # otp_sessions.upsert_session()'s ON CONFLICT (tenant_id, portal_id)
        # needs a real unique constraint to target, same as production.
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_govt_otp_sessions_tenant_portal "
            "ON govt_otp_sessions (tenant_id, portal_id)"
        ))
        for table_name in ("govt_submission_log", "govt_otp_sessions", "case_activity_log", "cases",
                           "govt_portals", "tenant_overrides", "token_blocklist", "users",
                           "tenant_profiles", "tenants"):
            conn.execute(text(f"DELETE FROM {table_name}"))  # nosec B608

        conn.execute(text(
            "INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active, "
            "created_at, govt_contact_primary_number) VALUES "
            "(1, 'Kavita Rao', 'Jaipur Rural', '+919000000003', 'Pro', 1, :now, '919000011111')"
        ), {"now": now})
        conn.execute(text(
            "INSERT INTO tenant_profiles (tenant_id, mp_name, constituency, state, house, created_at) "
            "VALUES (1, 'Shrimati Kavita Rao', 'Jaipur Rural', 'Rajasthan', 'Lok Sabha', :now)"
        ), {"now": now})
        conn.execute(text(
            "INSERT INTO users (tenant_id, username, password_hash, role, constituency, house, display_name, is_active) "
            "VALUES (1, 'mp_kavita', :password_hash, 'mp', 'Jaipur Rural', 'Lok Sabha', 'Kavita MP', 1)"
        ), {"password_hash": hash_password("Password1")})
        conn.execute(text(
            "INSERT INTO govt_portals (id, state, portal_name, portal_type, base_url, status_check_mode, "
            "department_taxonomy, field_schema, otp_bound, active, is_primary, verification_status, "
            "live_session_supported, status_check_adapter) VALUES "
            "(1, 'Rajasthan', 'Rajasthan Sampark', 'state_branded', 'https://sampark.rajasthan.gov.in', "
            "'public_reference', :taxonomy, :schema, 1, 1, 1, 'confirmed', 1, 'rajasthan_sampark_api')"
        ), {"taxonomy": json.dumps({"Infrastructure & Utilities": "PWD"}), "schema": json.dumps({})})
        conn.execute(text(
            "INSERT INTO cases (id, tenant_id, user_phone, raw_message, category, status, created_at, "
            "govt_portal_id, govt_status, govt_reference_number, is_deleted) VALUES "
            "(40, 1, '+919111111140', 'Broken handpump', 'Infrastructure & Utilities', 'in_progress', :now, "
            "1, 'submitted', 'RJ/2026/00099887', 0)"
        ), {"now": now})


def _gateway_response(payload):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value=payload)
    return resp


_SEND_OTP_SUCCESS = {"CustomObject": {"IsSent": True, "TransactionNumber": "TXN-001", "SessionId": "SESS-001"}}
_SEND_OTP_FAILURE = {"CustomObject": {"IsSent": False}, "Message": "Mobile number not registered with any grievance."}
_VALIDATE_OTP_SUCCESS = {"Status": 2}
_VALIDATE_OTP_WRONG = {"Status": 1, "Message": "Invalid OTP entered."}


def _log_rows(action=None):
    with test_engine.connect() as conn:
        q = "SELECT tenant_id, case_id, action, actor_username, payload FROM govt_submission_log"
        params = {}
        if action:
            q += " WHERE action = :action"
            params["action"] = action
        rows = list(conn.execute(text(q), params))
    return rows


# ─── /govt/otp/send ─────────────────────────────────────────────────────

@patch("requests.post")
def test_otp_send_success_is_audit_logged(mock_post):
    _seed_database()
    mock_post.return_value = _gateway_response(_SEND_OTP_SUCCESS)

    resp = client.post("/api/govt/otp/send", headers=_auth_headers())
    assert resp.status_code == 200, resp.text

    rows = _log_rows("otp_send_succeeded")
    assert len(rows) == 1
    tid, case_id, action, actor, payload = rows[0]
    assert tid == 1
    assert case_id == 40  # the anchor case — this endpoint isn't case-scoped itself
    assert actor == "mp_kavita"
    parsed = json.loads(payload) if isinstance(payload, str) else payload
    assert parsed == {"portal": "Rajasthan Sampark"}  # no OTP, no mobile number, nothing else


@patch("requests.post")
def test_otp_send_failure_is_audit_logged(mock_post):
    _seed_database()
    mock_post.return_value = _gateway_response(_SEND_OTP_FAILURE)

    resp = client.post("/api/govt/otp/send", headers=_auth_headers())
    assert resp.status_code == 502, resp.text

    rows = _log_rows("otp_send_failed")
    assert len(rows) == 1
    assert _log_rows("otp_send_succeeded") == []
    parsed = json.loads(rows[0][4]) if isinstance(rows[0][4], str) else rows[0][4]
    assert parsed == {"portal": "Rajasthan Sampark"}


# ─── /govt/otp/verify ───────────────────────────────────────────────────

def _seed_pending_otp_session():
    from modules.govt_sync import otp_sessions
    otp_sessions.upsert_session(1, 1, "919000011111", "TXN-001", "SESS-001", verified_at=None)


@patch("requests.post")
def test_otp_verify_success_is_audit_logged(mock_post):
    _seed_database()
    _seed_pending_otp_session()
    mock_post.return_value = _gateway_response(_VALIDATE_OTP_SUCCESS)

    resp = client.post("/api/govt/otp/verify", json={"otp": "482913"}, headers=_auth_headers())
    assert resp.status_code == 200, resp.text

    rows = _log_rows("otp_verify_succeeded")
    assert len(rows) == 1
    tid, case_id, action, actor, payload = rows[0]
    assert case_id == 40
    parsed = json.loads(payload) if isinstance(payload, str) else payload
    assert parsed == {"portal": "Rajasthan Sampark"}
    # The real OTP digits must never appear anywhere in any logged payload.
    for row in _log_rows():
        raw = row[4] if isinstance(row[4], str) else json.dumps(row[4])
        assert "482913" not in raw


@patch("requests.post")
def test_otp_verify_wrong_otp_is_audit_logged(mock_post):
    _seed_database()
    _seed_pending_otp_session()
    mock_post.return_value = _gateway_response(_VALIDATE_OTP_WRONG)

    resp = client.post("/api/govt/otp/verify", json={"otp": "000000"}, headers=_auth_headers())
    assert resp.status_code == 400, resp.text

    rows = _log_rows("otp_verify_failed")
    assert len(rows) == 1
    parsed = json.loads(rows[0][4]) if isinstance(rows[0][4], str) else rows[0][4]
    assert parsed["portal"] == "Rajasthan Sampark"
    assert parsed["note"] == "Invalid OTP"
    assert _log_rows("otp_verify_succeeded") == []
    for row in _log_rows():
        raw = row[4] if isinstance(row[4], str) else json.dumps(row[4])
        assert "000000" not in raw


def test_otp_verify_with_no_pending_session_is_audit_logged():
    _seed_database()
    # No _seed_pending_otp_session() call — complete_verification() raises
    # RuntimeError("No pending verification — send an OTP first.") before
    # any network call is made.
    resp = client.post("/api/govt/otp/verify", json={"otp": "123456"}, headers=_auth_headers())
    assert resp.status_code == 400, resp.text

    rows = _log_rows("otp_verify_failed")
    assert len(rows) == 1
    parsed = json.loads(rows[0][4]) if isinstance(rows[0][4], str) else rows[0][4]
    assert "No pending verification" in parsed["note"]
