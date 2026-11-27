"""Staff Overview: Issue Pressure insight, Office To-do counts and Local Signals tagging.

Run on its own (``rm -f *.db`` first): the JWT secret is frozen at first import.
"""
import json
import os
import sys
from datetime import datetime, timedelta

TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
TEST_DB_URL = "sqlite:///./test_overview_insight.db"
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
import modules.news_intel as news_intel  # noqa: E402
from main import app  # noqa: E402
from modules.overview_insight import annotate_local_signals, quadrant  # noqa: E402

test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(bind=test_engine)
NOW = datetime.utcnow()
_next_id = [100]


@event.listens_for(Engine, "connect")
def _sqlite_pg_lock_shims(dbapi_connection, connection_record):
    try:
        dbapi_connection.create_function("pg_try_advisory_lock", 1, lambda _k: 1)
        dbapi_connection.create_function("pg_advisory_unlock", 1, lambda _k: 1)
        dbapi_connection.create_function("pg_try_advisory_xact_lock", 1, lambda _k: 1)
    except Exception:
        pass


def _case(conn, *, tid=1, cat="Roads & Bridges", loc=None, ago=5, phone=None, status="new", msg="Road is broken near the school",
          lang="mr", assigned=None, govt_status=None, dept=None, govt_updated_ago=None, told_ago=None):
    _next_id[0] += 1
    cid = _next_id[0]
    meta = {"detected_language": lang}
    if loc:
        meta["matched_value"] = loc
    conn.execute(text(
        "INSERT INTO cases (id, tenant_id, user_phone, case_ref, category, raw_message, status, case_metadata, is_critical, "
        "is_deleted, created_at, assigned_to, govt_status, govt_department, govt_status_updated_at, "
        "govt_last_forwarded_to_citizen_at) VALUES (:id, :tid, :ph, :ref, :cat, :msg, :st, :meta, 0, 0, :c, :as, :gs, :dept, :gu, :told)"),
        {"id": cid, "tid": tid, "ph": phone if phone is not None else f"+9198000{cid:05d}", "ref": f"CN-{cid}", "cat": cat,
         "msg": msg, "st": status, "meta": json.dumps(meta), "c": NOW - timedelta(days=ago), "as": assigned, "gs": govt_status,
         "dept": dept, "gu": NOW - timedelta(days=govt_updated_ago) if govt_updated_ago is not None else None,
         "told": NOW - timedelta(days=told_ago) if told_ago is not None else None})
    return cid


def seed():
    Base.metadata.create_all(bind=test_engine)
    with test_engine.begin() as conn:
        for tbl in ("token_blocklist", "letterbox", "cases", "users", "tenants"):
            conn.execute(text(f"DELETE FROM {tbl}"))
        for tid, stage in ((1, "aspirant"), (2, "elected")):
            conn.execute(text(
                "INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active, created_at, "
                "seat_type, account_stage) VALUES (:t, :n, 'Belgaum Dakshin', :w, 'Pro', 1, :now, 'mla', :st)"),
                {"t": tid, "n": f"T{tid}", "w": f"+91900000000{tid}", "now": NOW - timedelta(days=400), "st": stage})
            conn.execute(text(
                "INSERT INTO users (tenant_id, username, password_hash, role, constituency, house, failed_login_attempts) "
                "VALUES (:t, :u, :p, 'mp', 'Belgaum Dakshin', 'Vidhan Sabha', 0)"),
                {"t": tid, "u": f"staff{tid}", "p": hash_password("ValidPass1!")})
        # Roads: 6 now in 4 localities (one person twice), 2 in the previous 30 days -> plank
        for loc, ph in (("Tilakwadi", "+911"), ("Tilakwadi", "+911"), ("Khasbag", None), ("Shahapur", None), ("R C Nagar", None)):
            _case(conn, loc=loc, phone=ph)
        _case(conn, loc="Tilakwadi", msg="Tilakwadi madhe rasta kharab aahe, school chi mula padtat", ago=2)
        _case(conn, loc="Tilakwadi", ago=40)
        _case(conn, loc="Khasbag", ago=50, status="in_progress", govt_status="submitted", dept="Public Works Dept")
        # Theft: 4 now in one locality, 1 before -> flash
        for _ in range(4):
            _case(conn, cat="Theft & Safety", loc="Shahapur", msg="Shahapur madhe khup chori hot aahe", lang="hi")
        _case(conn, cat="Theft & Safety", loc="Shahapur", ago=45)
        # Water: 2 now, 2 before, filed and resolved, citizen not told; an old open one
        _case(conn, cat="Water Supply", loc="Vadgaon", govt_status="resolved", dept="City Water Board", govt_updated_ago=3)
        _case(conn, cat="Water Supply", loc="Vadgaon", status="resolved")
        _case(conn, cat="Water Supply", ago=35)
        _case(conn, cat="Water Supply", ago=45)
        _case(conn, cat="Water Supply", ago=150, status="pending", assigned="7")
        # Noise and other tenant never count
        _case(conn, cat="Roads & Bridges", status="irrelevant")
        _case(conn, tid=2, cat="Roads & Bridges", loc="Tilakwadi")
        for direction, status, ago in (("inbox", "new", 3), ("inbox", "needs_review", 1), ("inbox", "filed", 9), ("outbox", "drafted", 2)):
            conn.execute(text(
                "INSERT INTO letterbox (tenant_id, direction, issue_summary, status, is_deleted, created_at) "
                "VALUES (1, :d, 'x', :s, 0, :c)"), {"d": direction, "s": status, "c": NOW - timedelta(days=ago)})


@pytest.fixture()
def client():
    dbmod.engine = test_engine
    dbmod.SessionLocal = TestSession
    db_helpers.engine = test_engine
    main.engine = test_engine
    api_router.engine = test_engine
    api_router.SessionLocal = TestSession
    api_router.JWT_SECRET = TEST_JWT_SECRET
    seed()
    yield TestClient(app, raise_server_exceptions=False)


def _h(client, u="staff1"):
    r = client.post("/api/auth/login", json={"username": u, "password": "ValidPass1!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_quadrant_rules():
    assert quadrant(10, 5, 4) == "plank"
    assert quadrant(9, 2, 3) == "flash"
    assert quadrant(9, 10, 5) == "chronic"
    assert quadrant(2, 1, 1) == "watch"        # +100% on two complaints is not "rising"
    assert quadrant(3, 0, 1) == "flash"


def test_issue_insight_30_days(client):
    r = client.get("/api/dashboard/overview/issue-insight?days=30", headers=_h(client))
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["period_days"] == 30 and d["edition"] == "aspirant"
    by = {i["issue"]: i for i in d["issues"]}
    assert [i["issue"] for i in d["issues"]] == ["Roads & Bridges", "Theft & Safety", "Water Supply"]
    roads = by["Roads & Bridges"]
    assert (roads["complaints"], roads["previous"], roads["people"], roads["locality_count"]) == (6, 2, 5, 4)
    assert roads["quadrant"] == "plank"
    assert roads["localities"][0] == {"name": "Tilakwadi", "complaints": 3}
    assert roads["open_over_30_days"] == 2 and roads["oldest_open_days"] == 50
    assert sum(roads["trend"]) == 6 and len(roads["trend"]) == 8
    assert roads["languages"] == [{"name": "Marathi", "share": 100}]
    assert roads["quotes"][0]["text"].startswith("Tilakwadi madhe") and roads["quotes"][0]["locality_complaints"] == 3
    theft = by["Theft & Safety"]
    assert (theft["complaints"], theft["previous"], theft["quadrant"]) == (4, 1, "flash")
    assert len(theft["quotes"]) == 1                    # identical messages are quoted once
    water = by["Water Supply"]
    assert (water["department"], water["filed"], water["filed_resolved"]) == ("City Water Board", 1, 1)
    assert water["open_over_30_days"] == 3 and water["oldest_open_days"] == 150


def test_issue_insight_period_and_edition(client):
    d = client.get("/api/dashboard/overview/issue-insight?days=90", headers=_h(client)).json()
    assert d["period_days"] == 90
    assert {i["issue"]: i["complaints"] for i in d["issues"]}["Roads & Bridges"] == 8
    assert client.get("/api/dashboard/overview/issue-insight?days=7", headers=_h(client)).json()["period_days"] == 90
    other = client.get("/api/dashboard/overview/issue-insight?days=30", headers=_h(client, "staff2")).json()
    assert other["edition"] == "mla" and [i["complaints"] for i in other["issues"]] == [1]
    assert client.get("/api/dashboard/overview/issue-insight").status_code in (401, 403)


def test_office_todo(client):
    d = client.get("/api/dashboard/overview/office-todo", headers=_h(client)).json()
    items = {i["key"]: i for i in d["items"]}
    assert [i["key"] for i in d["items"]] == ["unassigned", "letters", "drafts", "citizens_to_update"]
    assert (items["unassigned"]["count"], items["unassigned"]["oldest_days"]) == (16, 50)
    assert (items["letters"]["count"], items["letters"]["oldest_days"]) == (2, 3)
    assert (items["drafts"]["count"], items["drafts"]["oldest_days"]) == (1, 2)
    assert (items["citizens_to_update"]["count"], items["citizens_to_update"]["oldest_days"]) == (1, 3)
    other = {i["key"]: i for i in client.get("/api/dashboard/overview/office-todo", headers=_h(client, "staff2")).json()["items"]}
    assert other["unassigned"]["count"] == 1 and other["letters"]["count"] == 0 and other["letters"]["oldest_days"] is None


def test_unassigned_briefcase_filter(client):
    r = client.get("/api/cases?assigned_to=unassigned", headers=_h(client))
    assert r.status_code == 200, r.text
    body = r.json()
    rows = body.get("cases") or body.get("items") or []
    assert rows and all(not str(c.get("assigned_to") or "").strip() for c in rows)


def test_local_signals_tagging(client, monkeypatch):
    articles = [
        {"title": "Belagavi: city corporation meeting on budget", "source": "A", "link": "a", "published": "x"},
        {"title": "Shahapur police arrest two in theft case", "source": "B", "link": "b", "published": "x"},
        {"title": "Tilakwadi residents protest over potholes", "source": "C", "link": "c", "published": "x"},
        {"title": "Belagavi hospital gets new wing", "source": "D", "link": "d", "published": "x"},
    ]
    monkeypatch.setattr(news_intel, "fetch_local_signals", lambda tid, limit=8: [dict(a) for a in articles])
    items = client.get("/api/dashboard/overview/local-signals", headers=_h(client)).json()["items"]
    assert [i["link"] for i in items] == ["b", "c", "d", "a"]
    theft, road, health, generic = items
    assert theft["localities"] == ["Shahapur"] and theft["issue"] == "Theft & Safety"
    assert theft["linked"] == "4 Theft & Safety complaints from Shahapur in the last 30 days"
    assert road["issue"] == "Roads & Bridges" and road["linked"].startswith("3 Roads & Bridges complaints from Tilakwadi")
    assert (health["issue"], health["linked"], health["relevance"]) == ("Health", None, 2)
    assert (generic["issue"], generic["localities"], generic["relevance"]) == (None, [], 0)


def test_local_signals_issue_level_link(client):
    seed()
    db_helpers.engine = test_engine
    items = annotate_local_signals(1, [{"title": "Belagavi road works delayed again", "link": "x"}])
    assert items[0]["linked"] == "6 Roads & Bridges complaints in the last 30 days, up from 2"
