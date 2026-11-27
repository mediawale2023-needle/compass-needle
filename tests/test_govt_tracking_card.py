"""Staff Overview Government Tracking card: checks due, departments, resolved; recording a check.

Run on its own (``rm -f *.db`` first): the JWT secret is frozen at first import.
"""
import json
import os
import sys
from datetime import datetime, timedelta

TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
TEST_DB_URL = "sqlite:///./test_govt_tracking.db"
os.environ.setdefault("JWT_SECRET", TEST_JWT_SECRET)
os.environ.setdefault("DATABASE_URL", TEST_DB_URL)
os.environ.setdefault("ENV", "test")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-testing")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event, text  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from sansadx_backend.db import Base, hash_password  # noqa: E402
import sansadx_backend.db as dbmod  # noqa: E402
import core.db_helpers as db_helpers  # noqa: E402
import api_router  # noqa: E402
import main  # noqa: E402
from main import app  # noqa: E402

test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(bind=test_engine)
NOW = datetime.utcnow()


@event.listens_for(Engine, "connect")
def _sqlite_pg_lock_shims(dbapi_connection, connection_record):
    try:
        dbapi_connection.create_function("pg_try_advisory_lock", 1, lambda _k: 1)
        dbapi_connection.create_function("pg_advisory_unlock", 1, lambda _k: 1)
        dbapi_connection.create_function("pg_try_advisory_xact_lock", 1, lambda _k: 1)
    except Exception:
        pass


def _filed(conn, cid, *, tid=1, status="submitted", dept="Public Works Dept", filed_ago=40, checked_ago=None,
           updated_ago=None, told_ago=None, msg="Road broken near school"):
    conn.execute(text(
        "INSERT INTO cases (id, tenant_id, user_phone, case_ref, category, raw_message, status, case_metadata, is_critical, "
        "is_deleted, created_at, govt_status, govt_reference_number, govt_department, govt_status_updated_at, "
        "govt_last_forwarded_to_citizen_at) VALUES (:id, :tid, '+919800000001', :ref, 'Roads', :msg, 'in_progress', '{}', 0, 0, "
        ":c, :gs, :gref, :dept, :up, :told)"),
        {"id": cid, "tid": tid, "ref": f"CN-{cid}", "msg": msg, "c": NOW - timedelta(days=filed_ago + 1), "gs": status,
         "gref": f"G{cid}", "dept": dept, "up": NOW - timedelta(days=updated_ago) if updated_ago is not None else None,
         "told": NOW - timedelta(days=told_ago) if told_ago is not None else None})
    conn.execute(text("INSERT INTO govt_submission_log (tenant_id, case_id, action, actor_username, payload, created_at) "
                      "VALUES (:tid, :cid, 'staff_submitted', 'staff', '{}', :t)"),
                 {"tid": tid, "cid": cid, "t": NOW - timedelta(days=filed_ago)})
    if checked_ago is not None:
        conn.execute(text("INSERT INTO govt_submission_log (tenant_id, case_id, action, actor_username, payload, created_at) "
                          "VALUES (:tid, :cid, 'status_polled', 'staff', '{}', :t)"),
                     {"tid": tid, "cid": cid, "t": NOW - timedelta(days=checked_ago)})


def seed():
    Base.metadata.create_all(bind=test_engine)
    with test_engine.begin() as conn:
        for tbl in ("token_blocklist", "govt_submission_log", "cases", "users", "tenants"):
            conn.execute(text(f"DELETE FROM {tbl}"))
        for tid in (1, 2):
            conn.execute(text(
                "INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active, created_at, "
                "seat_type, account_stage) VALUES (:t, :n, 'Belgaum Dakshin', :w, 'Pro', 1, :now, 'mla', 'elected')"),
                {"t": tid, "n": f"T{tid}", "w": f"+91900000000{tid}", "now": NOW - timedelta(days=400)})
            conn.execute(text(
                "INSERT INTO users (tenant_id, username, password_hash, role, constituency, house, failed_login_attempts) "
                "VALUES (:t, :u, :p, 'mp', 'Belgaum Dakshin', 'Vidhan Sabha', 0)"),
                {"t": tid, "u": f"staff{tid}", "p": hash_password("ValidPass1!")})
        _filed(conn, 1, filed_ago=58)                                   # never checked -> due (oldest)
        _filed(conn, 2, filed_ago=30, checked_ago=20)                   # checked 20 days ago -> due
        _filed(conn, 3, filed_ago=25, checked_ago=3, dept="HESCOM")    # checked recently -> not due
        _filed(conn, 4, status="resolved", filed_ago=40, updated_ago=10, told_ago=5, dept="City Water Board")
        _filed(conn, 5, status="resolved", filed_ago=20, updated_ago=4, dept="City Water Board")      # citizen not told
        _filed(conn, 6, status="disposed", filed_ago=90, updated_ago=45, dept="HESCOM")              # previous window
        _filed(conn, 7, status="rejected", filed_ago=60, updated_ago=20, dept="")                    # closed, no dept
        _filed(conn, 8, tid=2, filed_ago=70)                                                          # other tenant
        conn.execute(text(
            "INSERT INTO cases (id, tenant_id, user_phone, case_ref, category, raw_message, status, case_metadata, is_critical, "
            "is_deleted, created_at, govt_status) VALUES (9, 1, '+91980', 'CN-9', 'Roads', 'not filed', 'new', '{}', 0, 0, :c, 'not_forwarded')"),
            {"c": NOW - timedelta(days=5)})


@pytest.fixture()
def client():
    dbmod.engine = test_engine
    dbmod.SessionLocal = TestSession
    db_helpers.engine = test_engine
    main.engine = test_engine
    api_router.engine = test_engine
    api_router.JWT_SECRET = TEST_JWT_SECRET
    seed()
    yield TestClient(app, raise_server_exceptions=False)


def _h(client, u="staff1"):
    r = client.post("/api/auth/login", json={"username": u, "password": "ValidPass1!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _card(client, h):
    r = client.get("/api/dashboard/overview/govt-tracking", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def test_card_sections(client):
    card = _card(client, _h(client))
    chk = card["check"]
    assert (chk["due"], chk["open_filed"], chk["checked_recently_pct"], chk["oldest_filed_days"]) == (2, 3, 33, 58)
    assert [i["id"] for i in chk["items"]] == [1, 2]
    assert chk["items"][1]["last_checked_days"] == 20 and chk["items"][0]["last_checked_days"] is None
    dep = {d["name"]: d for d in card["departments"]["rows"]}
    assert card["departments"]["filed"] == 7 and card["departments"]["waiting"] == 3
    assert (dep["Public Works Dept"]["filed"], dep["Public Works Dept"]["waiting"], dep["Public Works Dept"]["oldest_wait_days"]) == (2, 2, 58)
    assert (dep["City Water Board"]["resolved"], dep["HESCOM"]["resolved"], dep["Department not recorded"]["filed"]) == (2, 1, 1)
    assert card["departments"]["slowest"] == "Public Works Dept"
    res = card["resolved"]
    assert (res["count"], res["previous"], res["not_told"]) == (2, 1, 1)
    assert res["avg_days"] == 23                          # (40-10 + 20-4) / 2
    assert [(i["id"], i["citizen_told"]) for i in res["items"]] == [(5, False), (4, True)]


def test_recording_a_check_updates_status_and_clears_it_from_due(client):
    h = _h(client)
    r = client.post("/api/cases/1/govt/check", json={"outcome": "still_pending"}, headers=h)
    assert r.status_code == 200 and r.json()["changed"] is False and r.json()["govt_status"] == "submitted"
    assert [i["id"] for i in _card(client, h)["check"]["items"]] == [2]
    r = client.post("/api/cases/2/govt/check", json={"outcome": "resolved"}, headers=h)
    assert r.json() == {"success": True, "case_id": 2, "outcome": "resolved", "govt_status": "resolved", "changed": True}
    card = _card(client, h)
    assert card["check"]["due"] == 0 and card["resolved"]["count"] == 3
    r = client.post("/api/cases/3/govt/check", json={"outcome": "closed_without_fix"}, headers=h)
    assert r.json()["govt_status"] == "rejected"
    r = client.post("/api/cases/3/govt/check", json={"outcome": "more_info"}, headers=h)
    assert r.json()["govt_status"] == "under_review"
    with test_engine.begin() as conn:
        n = conn.execute(text("SELECT COUNT(*) FROM govt_submission_log WHERE case_id IN (1,2,3) AND action = 'status_polled'")).scalar()
    assert n == 2 + 4                                     # earlier checks on cases 2 and 3 + four recorded now


def test_check_validation_and_tenant_isolation(client):
    h = _h(client)
    assert client.post("/api/cases/1/govt/check", json={"outcome": "maybe"}, headers=h).status_code == 400
    assert client.post("/api/cases/9/govt/check", json={"outcome": "resolved"}, headers=h).status_code == 404   # not filed
    assert client.post("/api/cases/8/govt/check", json={"outcome": "resolved"}, headers=h).status_code == 404   # other tenant
    assert client.post("/api/cases/1/govt/check", json={"outcome": "resolved"}).status_code in (401, 403)
    other = _card(client, _h(client, "staff2"))
    assert [i["id"] for i in other["check"]["items"]] == [8] and other["departments"]["filed"] == 1
