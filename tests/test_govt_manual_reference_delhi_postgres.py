"""
tests/test_govt_manual_reference_delhi_postgres.py — real-PostgreSQL race
verification of POST /api/cases/{id}/govt/manual-reference.

Opt-in: runs only when NEEDLE_PG_TEST_URL points at a DISPOSABLE PostgreSQL
database (its tables are created and the rows touched here are deleted). It
never falls back to SQLite - without the variable the module is skipped.

Run:  NEEDLE_PG_TEST_URL=postgresql://user@host/throwaway_db \
      python -m pytest tests/test_govt_manual_reference_delhi_postgres.py
"""
import json
import os
import sys
import threading
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

PG_URL = os.environ.get("NEEDLE_PG_TEST_URL", "")
if not PG_URL.startswith("postgresql"):
    pytest.skip("NEEDLE_PG_TEST_URL not set to a PostgreSQL URL", allow_module_level=True)

TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
os.environ.setdefault("DATABASE_URL", PG_URL)
os.environ.setdefault("ENV", "test")
os.environ.setdefault("JWT_SECRET", TEST_JWT_SECRET)
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-testing")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import jwt
from tests.auth_token_claims import identity_claims
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text

import admin_api
import api_router
import core.db_helpers as db_helpers
import main
import sansadx_backend.db as dbmod
from sansadx_backend.db import Base, hash_password

pg_engine = create_engine(PG_URL, pool_size=10, max_overflow=10)
client = TestClient(main.app, raise_server_exceptions=False)
URL = "/api/cases/{}/govt/manual-reference"
DELHI_PID = 1


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _headers():
    token = jwt.encode({"sub": "mp_a", **identity_claims(pg_engine, "mp_a"), "exp": _utcnow() + timedelta(hours=8), "iat": _utcnow().timestamp()},
                       TEST_JWT_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def pg(monkeypatch):
    monkeypatch.setenv("GOVT_DELHI_MANUAL_REFERENCE_ENABLED", "true")
    dbmod.engine = pg_engine
    for m in (db_helpers, main, api_router, admin_api):
        m.engine = pg_engine
    api_router.JWT_SECRET = admin_api.JWT_SECRET = TEST_JWT_SECRET
    Base.metadata.create_all(bind=pg_engine)
    now = _utcnow()
    with pg_engine.begin() as conn:
        for t in ("govt_submission_log", "case_activity_log", "cases", "govt_portals",
                  "token_blocklist", "users", "tenant_profiles", "tenants"):
            conn.execute(text(f"DELETE FROM {t}"))  # nosec B608
        conn.execute(text("INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active, created_at) "
                          "VALUES (1, 'T1', 'X', '+919000000001', 'Pro', true, :now)"), {"now": now})
        conn.execute(text("INSERT INTO tenant_profiles (tenant_id, mp_name, constituency, state, house, created_at) "
                          "VALUES (1, 'MP', 'X', 'Delhi', 'Lok Sabha', :now)"), {"now": now})
        conn.execute(text("INSERT INTO users (tenant_id, username, password_hash, role, constituency, house, display_name, is_active) "
                          "VALUES (1, 'mp_a', :pw, 'mp', 'X', 'Lok Sabha', 'MP', true)"), {"pw": hash_password("Password1")})
        conn.execute(text("INSERT INTO govt_portals (id, state, portal_name, portal_type, base_url, status_check_mode, "
                          "department_taxonomy, field_schema, otp_bound, active, is_primary, verification_status, live_session_supported) "
                          "VALUES (1, 'Delhi', 'Delhi CM Jan Sunwai', 'state_branded', 'https://cmjansunwai.delhi.gov.in/', "
                          "'login_required', CAST(:t AS JSONB), CAST(:s AS JSONB), true, false, true, 'verify', true)"),
                     {"t": "{}", "s": "{}"})
        conn.execute(text("INSERT INTO cases (id, tenant_id, user_phone, raw_message, category, status, created_at, "
                          "govt_portal_id, govt_status, govt_reference_number, is_deleted) "
                          "VALUES (100, 1, '+919111111111', 'msg', 'Health', 'new', :now, NULL, 'not_forwarded', NULL, false)"),
                     {"now": now})
    yield


def _race(refs):
    """Fire len(refs) real concurrent requests. A barrier on the pre-check case
    read forces every request to observe the case as UNFILED before any of
    them reaches the guarded UPDATE. Returns (responses, update_rowcounts,
    precheck_reads)."""
    barrier = threading.Barrier(len(refs), timeout=15)
    real_q_one = api_router._q_one
    reads, rowcounts = [], []
    lock = threading.Lock()

    def gated_q_one(sql, params=None, *a, **k):
        row = real_q_one(sql, params, *a, **k) if params is not None else real_q_one(sql, *a, **k)
        if "govt_portal_id, govt_reference_number, govt_status, status FROM cases" in sql:
            with lock:
                reads.append(dict(row) if row else None)
            barrier.wait()
        return row

    def after_exec(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().startswith("UPDATE cases SET govt_portal_id"):
            with lock:
                rowcounts.append(cursor.rowcount)

    results = [None] * len(refs)

    def worker(i):
        results[i] = client.post(URL.format(100), json={"reference_number": refs[i]}, headers=_headers())

    event.listen(pg_engine, "after_cursor_execute", after_exec)
    try:
        with patch.object(api_router, "_q_one", gated_q_one):
            ts = [threading.Thread(target=worker, args=(i,)) for i in range(len(refs))]
            for t in ts:
                t.start()
            for t in ts:
                t.join(timeout=60)
            assert not any(t.is_alive() for t in ts), "race harness deadlocked"
    finally:
        event.remove(pg_engine, "after_cursor_execute", after_exec)
    return results, rowcounts, reads


def _db_state():
    with pg_engine.connect() as c:
        case = dict(c.execute(text("SELECT status, govt_portal_id, govt_department, govt_status, govt_reference_number "
                                   "FROM cases WHERE id = 100")).mappings().first())
        log = [r[0] for r in c.execute(text("SELECT action FROM govt_submission_log WHERE case_id = 100"))]
        acts = c.execute(text("SELECT COUNT(*) FROM case_activity_log WHERE case_id = 100 AND action = 'govt_submitted'")).scalar()
    return case, log, acts


def test_pg_identical_concurrent_requests_one_update_loser_idempotent():
    assert pg_engine.dialect.name == "postgresql"
    results, rowcounts, reads = _race(["30000000001", "30000000001"])
    assert len(reads) == 2 and all(r["govt_reference_number"] in (None, "") for r in reads)
    assert [r.status_code for r in results] == [200, 200], [r.text for r in results]
    bodies = [r.json() for r in results]
    assert sorted(b.get("idempotent", False) for b in bodies) == [False, True]
    assert all(b["govt_reference_number"] == "30000000001" for b in bodies)
    assert sorted(rowcounts) == [0, 1]            # exactly one request changed a row
    case, log, acts = _db_state()
    assert case["govt_portal_id"] == DELHI_PID and case["govt_reference_number"] == "30000000001"
    assert case["govt_status"] == "submitted" and case["govt_department"] is None and case["status"] == "in_progress"
    assert log == ["staff_submitted"] and acts == 1


def test_pg_different_references_one_wins_other_409():
    results, rowcounts, reads = _race(["30000000002", "30000000003"])
    assert len(reads) == 2
    codes = sorted(r.status_code for r in results)
    assert codes == [200, 409], [r.text for r in results]
    winner = next(r for r in results if r.status_code == 200).json()
    assert "idempotent" not in winner
    assert sorted(rowcounts) == [0, 1]
    case, log, acts = _db_state()
    assert case["govt_reference_number"] == winner["govt_reference_number"]
    assert case["govt_reference_number"] in ("30000000002", "30000000003")
    assert case["govt_portal_id"] == DELHI_PID
    assert log == ["staff_submitted"] and acts == 1
