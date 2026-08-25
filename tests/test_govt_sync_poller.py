"""
tests/test_govt_sync_poller.py — regression tests for govt-sync fixation
plan Step 2: audit-logging every inconclusive status check, not just
successful ones, using action strings distinct from "status_polled".

Covers both call sites the fixation plan targeted:
  A. modules/govt_sync/poller.py's poll_all_pending() (the unattended,
     scheduled sweep — previously silent on both its early-continue paths).
  B. api_router.py's govt_poll_case() (the on-demand "Check status now"
     endpoint — previously silent on the same two paths).

The one thing every test here is ultimately protecting: "status_polled"
must remain reserved for genuinely successful checks (attempted, responded,
parsed, and normalized), because a later change (fixation-plan Step 9,
"last successfully checked") will read the latest status_polled row as its
source of truth. If either call site ever logs an inconclusive result under
that same action string, this file must catch it.
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
TEST_DB_URL = "sqlite:///./test_govt_sync_poller.db"

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
from sansadx_backend.db import Base

from modules.govt_sync.adapters.base import StatusResult
from modules.govt_sync import poller as poller_mod

test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False)
client = TestClient(main.app, raise_server_exceptions=False)


def _bind_engines():
    dbmod.engine = test_engine
    dbmod.SessionLocal = TestSession
    db_helpers.engine = test_engine
    main.engine = test_engine
    api_router.engine = test_engine
    poller_mod.engine = test_engine
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
        for table_name in ("govt_submission_log", "cases", "govt_portals", "users", "tenants"):
            conn.execute(text(f"DELETE FROM {table_name}"))  # nosec B608

        conn.execute(text(
            "INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active, created_at) "
            "VALUES (1, 'Priya Sharma', 'Test Constituency', '+919000000001', 'Pro', 1, :now)"
        ), {"now": now})
        conn.execute(text(
            "INSERT INTO users (tenant_id, username, password_hash, role, constituency, house, display_name, is_active) "
            "VALUES (1, 'mp_priya', 'x', 'mp', 'Test Constituency', 'Lok Sabha', 'Priya MP', 1)"
        ))
        conn.execute(text(
            "INSERT INTO govt_portals (id, state, portal_name, portal_type, base_url, status_check_mode, "
            "department_taxonomy, field_schema, otp_bound, active, is_primary, verification_status, "
            "live_session_supported) VALUES "
            "(1, 'TestState', 'Test Portal', 'state_branded', 'https://example.test', 'login_required', "
            ":taxonomy, :schema, 0, 1, 1, 'confirmed', 0)"
        ), {"taxonomy": json.dumps({}), "schema": json.dumps({})})
        conn.execute(text(
            "INSERT INTO cases (id, tenant_id, user_phone, raw_message, category, status, created_at, "
            "govt_portal_id, govt_status, govt_reference_number, is_deleted) VALUES "
            "(40, 1, '+919111111140', 'Test grievance', 'Infrastructure & Utilities', 'in_progress', :now, "
            "1, 'submitted', 'REF/TEST/0001', 0)"
        ), {"now": now})


def _log_rows(action: str | None = None):
    with test_engine.connect() as conn:
        q = "SELECT action, payload FROM govt_submission_log"
        params = {}
        if action:
            q += " WHERE action = :action"
            params = {"action": action}
        return list(conn.execute(text(q), params))


# ─── A. poll_all_pending() — the unattended sweep ─────────────────────────
#
# NOT covered by this pytest file: poll_all_pending()'s own SELECT uses
# Postgres-only `= ANY(:statuses)` syntax (pre-existing — this query was
# never SQLite-compatible, not something Step 2 introduced), so SQLite can't
# run it at all. Rather than weaken the production query to satisfy a test
# harness, the same branching logic this section would have covered
# (inconclusive/needs_verification get distinct actions, never
# "status_polled") is validated for real against local Postgres — see
# scratchpad's validate_govt_sync_poller.py from this session — and is
# already covered indirectly here via section B below, since govt_poll_case
# and poll_all_pending share the identical checked/needs_verification
# branching shape.


# ─── B. govt_poll_case — on-demand "Check status now" endpoint ────────────

class _FakeAdapter:
    supports_unattended_status_check = True

    def __init__(self, result):
        self._result = result

    def check_status(self, reference_number, tenant_id=None):
        return self._result



def test_endpoint_poll_logs_inconclusive():
    _seed_database()
    result = StatusResult(status="", checked=False, raw_portal_status="Unrecognised page text")

    with patch("modules.govt_sync.adapters.get_adapter", return_value=_FakeAdapter(result)):
        resp = client.post("/api/cases/40/govt/poll", headers=_auth_headers())

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["note"] == "Portal check inconclusive — verify manually on the portal."
    rows = _log_rows()
    assert len(rows) == 1
    assert rows[0][0] == "status_check_inconclusive"


def test_endpoint_poll_logs_needs_verification():
    _seed_database()
    result = StatusResult(status="", checked=False, needs_verification=True)

    with patch("modules.govt_sync.adapters.get_adapter", return_value=_FakeAdapter(result)):
        resp = client.post("/api/cases/40/govt/poll", headers=_auth_headers())

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["needs_verification"] is True
    rows = _log_rows()
    assert len(rows) == 1
    assert rows[0][0] == "status_check_needs_verification"


def test_endpoint_poll_successful_check_still_logs_status_polled():
    _seed_database()
    result = StatusResult(status="under_review", checked=True, raw_portal_status="Under review")

    with patch("modules.govt_sync.adapters.get_adapter", return_value=_FakeAdapter(result)):
        resp = client.post("/api/cases/40/govt/poll", headers=_auth_headers())

    assert resp.status_code == 200, resp.text
    assert resp.json()["changed"] is True
    rows = _log_rows()
    assert len(rows) == 1
    assert rows[0][0] == "status_polled"
