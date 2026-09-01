"""POST /api/cases/{id}/govt/resolution-review — persists the staff decision
to keep a Needle case open after the government portal marked the grievance
resolved. Must never change cases.status; must be tied to the current
government-resolution cycle (govt_status_updated_at)."""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
TEST_DB_URL = "sqlite:///./test_govt_resolution_review.db"
os.environ["JWT_SECRET"] = TEST_JWT_SECRET
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["ENV"] = "test"
os.environ["OPENAI_API_KEY"] = "sk-test-fake-key-for-testing"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@event.listens_for(Engine, "connect")
def _sqlite_pg_lock_stubs(dbapi_connection, connection_record):
    try:
        dbapi_connection.create_function("pg_try_advisory_lock", 1, lambda _k: 1)
        dbapi_connection.create_function("pg_advisory_unlock", 1, lambda _k: 1)
        dbapi_connection.create_function("pg_try_advisory_xact_lock", 1, lambda _k: 1)
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


def _auth_headers(username="mp_arun"):
    token = jwt.encode(
        {"sub": username, "exp": _utcnow() + timedelta(hours=8), "iat": _utcnow().timestamp()},
        TEST_JWT_SECRET, algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def _seed(govt_status="resolved", govt_updated="2026-08-27 07:00:00"):
    dbmod.engine = test_engine
    dbmod.SessionLocal = TestSession
    db_helpers.engine = test_engine
    main.engine = test_engine
    api_router.engine = test_engine
    api_router.JWT_SECRET = TEST_JWT_SECRET
    Base.metadata.create_all(bind=test_engine)
    now = _utcnow()
    with test_engine.begin() as conn:
        for t in ("govt_submission_log", "case_activity_log", "cases",
                  "users", "tenant_profiles", "tenants"):
            conn.execute(text(f"DELETE FROM {t}"))  # nosec B608
        conn.execute(text(
            "INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active, created_at) "
            "VALUES (1, 'Arun', 'Bangalore North', '+919000000001', 'Pro', 1, :now)"
        ), {"now": now})
        conn.execute(text(
            "INSERT INTO tenant_profiles (tenant_id, mp_name, constituency, state, house, created_at) "
            "VALUES (1, 'Shri Arun', 'Bangalore North', 'Karnataka', 'Lok Sabha', :now)"
        ), {"now": now})
        conn.execute(text(
            "INSERT INTO users (tenant_id, username, password_hash, role, constituency, house, display_name, is_active) "
            "VALUES (1, 'mp_arun', :ph, 'mp', 'Bangalore North', 'Lok Sabha', 'Arun MP', 1)"
        ), {"ph": hash_password("Password1")})
        conn.execute(text(
            "INSERT INTO cases (id, tenant_id, user_phone, raw_message, category, status, created_at, "
            "govt_status, govt_reference_number, govt_status_updated_at, is_deleted) "
            "VALUES (50, 1, '+919111111111', 'Garbage not cleared', 'Health & Sanitation', 'in_progress', :now, "
            ":gs, 'BBMP-2026-4471', :gu, 0)"
        ), {"now": now, "gs": govt_status, "gu": govt_updated})


def _activity_actions(case_id=50):
    r = client.get(f"/api/cases/{case_id}/activity", headers=_auth_headers())
    assert r.status_code == 200, r.text
    return r.json()["activities"]


def _row(case_id=50):
    with test_engine.connect() as conn:
        return conn.execute(
            text("SELECT status, govt_status, govt_status_updated_at FROM cases WHERE id = :c"),
            {"c": case_id},
        ).mappings().first()


# ── happy path ────────────────────────────────────────────────────────

def test_continue_follow_up_persists_activity_without_touching_status():
    _seed()
    before = _row()
    r = client.post("/api/cases/50/govt/resolution-review", headers=_auth_headers(),
                    json={"decision": "continue_follow_up"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["decision"] == "continue_follow_up"
    assert body["govt_status_updated_at"]

    after = _row()
    assert after["status"] == before["status"] == "in_progress"          # Needle status untouched
    assert after["govt_status"] == "resolved"

    acts = _activity_actions()
    review = next(a for a in acts if a["action"] == "govt_resolution_reviewed")
    assert review["new_value"] == "continue_follow_up"
    assert review["username"] == "mp_arun"
    d = json.loads(review["details"])
    assert d["decision"] == "continue_follow_up"
    assert d["govt_reference_number"] == "BBMP-2026-4471"
    assert d["govt_status"] == "resolved"
    # cycle marker matches what the endpoint returned (same underlying column)
    assert d["govt_status_updated_at"] == body["govt_status_updated_at"]


def test_disposed_also_accepted():
    _seed(govt_status="disposed")
    r = client.post("/api/cases/50/govt/resolution-review", headers=_auth_headers(),
                    json={"decision": "continue_follow_up"})
    assert r.status_code == 200, r.text


# ── guards ───────────────────────────────────────────────────────────

def test_rejected_when_govt_not_resolved():
    _seed(govt_status="under_review")
    r = client.post("/api/cases/50/govt/resolution-review", headers=_auth_headers(),
                    json={"decision": "continue_follow_up"})
    assert r.status_code == 409, r.text
    assert not any(a["action"] == "govt_resolution_reviewed" for a in _activity_actions())


def test_unsupported_decision_rejected():
    _seed()
    r = client.post("/api/cases/50/govt/resolution-review", headers=_auth_headers(),
                    json={"decision": "reopen_grievance"})
    assert r.status_code == 400, r.text


def test_unknown_case_404():
    _seed()
    r = client.post("/api/cases/999/govt/resolution-review", headers=_auth_headers(),
                    json={"decision": "continue_follow_up"})
    assert r.status_code == 404, r.text


def test_requires_auth():
    _seed()
    r = client.post("/api/cases/50/govt/resolution-review", json={"decision": "continue_follow_up"})
    assert r.status_code in (401, 403), r.text


# ── stale-cycle marker ───────────────────────────────────────────────

def test_marker_reflects_the_resolution_cycle_it_was_made_against():
    _seed(govt_updated="2026-08-27 07:00:00")
    r1 = client.post("/api/cases/50/govt/resolution-review", headers=_auth_headers(),
                     json={"decision": "continue_follow_up"})
    first_marker = r1.json()["govt_status_updated_at"]

    # government re-opens then re-resolves -> govt_status_updated_at advances
    with test_engine.begin() as conn:
        conn.execute(text(
            "UPDATE cases SET govt_status_updated_at = :gu WHERE id = 50"
        ), {"gu": "2026-09-01 10:00:00"})

    r2 = client.post("/api/cases/50/govt/resolution-review", headers=_auth_headers(),
                     json={"decision": "continue_follow_up"})
    second_marker = r2.json()["govt_status_updated_at"]

    assert first_marker != second_marker
    acts = [a for a in _activity_actions() if a["action"] == "govt_resolution_reviewed"]
    assert len(acts) == 2
    markers = {json.loads(a["details"])["govt_status_updated_at"] for a in acts}
    assert markers == {first_marker, second_marker}


# ── /api/cases/{id} exposes per-complaint govt_status_updated_at ──────

def test_thread_cases_expose_govt_status_updated_at_and_resolved_at():
    _seed(govt_updated="2026-08-27 07:00:00")
    with test_engine.begin() as conn:
        conn.execute(text("UPDATE cases SET status = 'resolved', resolved_at = :ra WHERE id = 50"),
                     {"ra": "2026-08-28 09:00:00"})
    r = client.get("/api/cases/50", headers=_auth_headers())
    assert r.status_code == 200, r.text
    tc = r.json()["thread_cases"]
    anchor = next(c for c in tc if c["id"] == 50)
    assert "govt_status_updated_at" in anchor and anchor["govt_status_updated_at"] is not None
    assert "resolved_at" in anchor and anchor["resolved_at"] is not None
