"""Staff Overview top strip: six period metrics and the rows behind each (tenant-scoped).

Run on its own (``rm -f *.db`` first): the JWT secret is frozen at first import.
"""
import json
import os
import sys
from datetime import datetime, timedelta

TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
TEST_DB_URL = "sqlite:///./test_overview_metrics.db"
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


def _case(conn, cid, ago, *, tid=1, phone="+919800000001", status="new", gs=None, ref=None, loc="", msg="Road broken"):
    conn.execute(text(
        "INSERT INTO cases (id, tenant_id, user_phone, case_ref, category, raw_message, status, case_metadata, "
        "is_critical, is_deleted, created_at, govt_status, govt_reference_number) VALUES "
        "(:id, :tid, :ph, :ref, 'Roads', :msg, :st, :meta, 0, 0, :c, :gs, :gref)"),
        {"id": cid, "tid": tid, "ph": phone, "ref": f"CN-{cid}", "msg": msg, "st": status,
         "meta": json.dumps({"matched_value": loc}), "c": NOW - timedelta(days=ago), "gs": gs, "gref": ref})


def seed():
    Base.metadata.create_all(bind=test_engine)
    with test_engine.begin() as conn:
        for tbl in ("token_blocklist", "cases", "contacts", "users", "tenants"):
            conn.execute(text(f"DELETE FROM {tbl}"))
        for tid in (1, 2):
            conn.execute(text(
                "INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active, created_at, "
                "seat_type, account_stage) VALUES (:t, :n, 'Belgaum Dakshin', :w, 'Pro', 1, :now, 'mla', 'aspirant')"),
                {"t": tid, "n": f"T{tid}", "w": f"+91900000000{tid}", "now": NOW - timedelta(days=400)})
            conn.execute(text(
                "INSERT INTO users (tenant_id, username, password_hash, role, constituency, house, failed_login_attempts) "
                "VALUES (:t, :u, :p, 'mp', 'Belgaum Dakshin', 'Vidhan Sabha', 0)"),
                {"t": tid, "u": f"staff{tid}", "p": hash_password("ValidPass1!")})
        A, B, C, D = "+919800000001", "+919800000002", "+919800000003", "+919800001234"
        _case(conn, 1, 45, phone=A)                                                      # A first wrote before the window
        _case(conn, 2, 3, phone=A, status="in_progress", gs="submitted", ref="G1", loc="Tilakwadi")   # filed
        _case(conn, 3, 4, phone=B, status="in_progress", gs="resolved", ref="G2", loc="Shahapur")     # filed + resolved
        _case(conn, 4, 5, phone=B, status="closed", loc="Shahapur")                    # other action
        _case(conn, 5, 6, phone=C, status="new", loc="Khasbag", msg="Water not coming for 3 days")  # pending
        _case(conn, 6, 7, phone=D, status="new")                                        # pending, new contact
        _case(conn, 7, 8, phone=D, status="irrelevant")                                 # spam: never counted
        _case(conn, 8, 2, tid=2, phone="+919899999999")                                 # other tenant
        conn.execute(text("INSERT INTO contacts (tenant_id, phone, display_name, created_at) VALUES (1, :p, 'Asha Patil', :c)"),
                     {"p": B, "c": NOW})


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


def test_six_metrics_with_previous_period(client):
    r = client.get("/api/dashboard/overview/metrics?days=30", headers=_h(client))
    assert r.status_code == 200, r.text
    m = {x["key"]: x for x in r.json()["metrics"]}
    assert list(m) == ["complaints", "filed", "resolved", "other_actions", "pending", "new_contacts"]
    assert {k: v["value"] for k, v in m.items()} == {
        "complaints": 5, "filed": 2, "resolved": 1, "other_actions": 1, "pending": 2, "new_contacts": 3}
    assert m["complaints"]["previous"] == 1                    # case 1, 45 days ago
    assert m["complaints"]["value"] == m["filed"]["value"] + m["other_actions"]["value"] + m["pending"]["value"]
    # defaults to the last 30 days
    assert client.get("/api/dashboard/overview/metrics", headers=_h(client)).json()["window"]["days"] == 30
    allt = {x["key"]: x for x in client.get("/api/dashboard/overview/metrics?range=all", headers=_h(client)).json()["metrics"]}
    assert allt["complaints"]["value"] == 6 and allt["complaints"]["previous"] is None


def test_each_number_opens_exactly_its_cases(client):
    h = _h(client)
    for key, ids in (("complaints", [2, 3, 4, 5, 6]), ("filed", [2, 3]), ("resolved", [3]),
                     ("other_actions", [4]), ("pending", [5, 6])):
        body = client.get(f"/api/dashboard/overview/metrics/{key}?days=30", headers=h).json()
        assert sorted(c["id"] for c in body["cases"]) == ids, key
        assert body["total"] == len(ids)
    pending = client.get("/api/dashboard/overview/metrics/pending?days=30", headers=h).json()["cases"]
    water = next(c for c in pending if c["id"] == 5)
    assert water["preview"] == "Water not coming for 3 days" and water["locality"] == "Khasbag" and water["age_days"] == 6


def test_new_contacts_lists_people_with_their_mobile_numbers_and_cases(client):
    body = client.get("/api/dashboard/overview/metrics/new_contacts?days=30", headers=_h(client)).json()
    assert body["total"] == 3
    people = {c["phone"]: c for c in body["contacts"]}
    assert set(people) == {"+91 98000 00002", "+91 98000 00003", "+91 98000 01234"}   # A first wrote 45 days ago
    assert people["+91 98000 00002"]["name"] == "Asha Patil" and people["+91 98000 00003"]["name"] == ""
    assert sorted(c["id"] for c in people["+91 98000 00002"]["cases"]) == [3, 4]
    assert [c["id"] for c in people["+91 98000 01234"]["cases"]] == [6]          # spam case 7 left out


def test_tenant_isolation_validation_and_auth(client):
    other = client.get("/api/dashboard/overview/metrics/complaints?days=30", headers=_h(client, "staff2")).json()
    assert [c["id"] for c in other["cases"]] == [8]
    h = _h(client)
    assert client.get("/api/dashboard/overview/metrics/nope?days=30", headers=h).status_code == 404
    assert client.get("/api/dashboard/overview/metrics?days=0", headers=h).status_code == 422
    assert client.get("/api/dashboard/overview/metrics?days=30").status_code in (401, 403)


def test_phone_formatting():
    from modules.overview_metrics import format_phone
    assert format_phone("+919876543210") == "+91 98765 43210"
    assert format_phone("919876543210") == "+91 98765 43210"
    assert format_phone("9876543210") == "+91 98765 43210"
    assert format_phone("+4420 7946 0958") == "+4420 7946 0958"
    assert format_phone(None) == ""
