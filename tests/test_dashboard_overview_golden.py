"""Golden regression: the MP ``GET /api/dashboard/overview`` response must not change.

The fixture ``tests/golden/dashboard_overview_mp.json`` was captured from the
unmodified handler (before the builder was extracted into
``modules/dashboard_overview.py``) against the deterministic data seeded below,
with the clock frozen. Any byte-level drift in the MP response fails this test.

Regenerate ONLY for an intentional MP-visible change:
    UPDATE_GOLDEN=1 python -m pytest tests/test_dashboard_overview_golden.py

Run this file on its own (``rm -f *.db`` first): the JWT secret is frozen at
first import, so mixing it with other dashboard test modules is order-dependent.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
TEST_DB_URL = "sqlite:///./test_dashboard_overview_golden.db"
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

GOLDEN_PATH = Path(__file__).parent / "golden" / "dashboard_overview_mp.json"
FROZEN_NOW = datetime(2026, 3, 10, 12, 0, 0)

test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(bind=test_engine)


@event.listens_for(Engine, "connect")
def _sqlite_pg_lock_shims(dbapi_connection, connection_record):
    try:
        dbapi_connection.create_function("pg_try_advisory_lock", 1, lambda _k: 1)
        dbapi_connection.create_function("pg_advisory_unlock", 1, lambda _k: 1)
        dbapi_connection.create_function("pg_try_advisory_xact_lock", 1, lambda _k: 1)
    except Exception:
        pass


# DISTINCT ON is Postgres-only, so the govt sync lookup is stubbed with a fixed
# map (same approach as test_dashboard_attention_queue_ordering.py). The stub is
# installed on api_router, which is where the route resolves it at call time.
SYNC = {
    306: {"govt_sync_state": "failed", "govt_changed": False},
    307: {"govt_sync_state": "changed", "govt_changed": True},
}


def _stub_sync_map(tenant_id, case_ids):
    return {cid: SYNC[cid] for cid in case_ids if cid in SYNC}


def _ts(day, hour=9, minute=0):
    return datetime(2026, 3, day, hour, minute, 0)


def _case(conn, cid, *, tid=1, status="new", created, thread=None, phone="+919650787758",
          msg="Water supply problem", location=None, assembly=None, domain=None,
          subdomain=None, category="Uncategorised", critical=0, govt_status=None,
          govt_ref=None, assigned=None, deleted=0):
    meta = {"contact_thread_id": thread} if thread else None
    conn.execute(
        text(
            "INSERT INTO cases (id, tenant_id, user_phone, case_ref, category, problem_domain, "
            "problem_subdomain, raw_message, status, location, assembly, case_metadata, "
            "is_critical, is_deleted, created_at, updated_at, govt_status, "
            "govt_reference_number, assigned_to) VALUES (:id, :tid, :phone, :ref, :cat, :dom, "
            ":sub, :msg, :status, :loc, :asm, :meta, :crit, :del, :c, :c, :gs, :gref, :asg)"
        ),
        {"id": cid, "tid": tid, "phone": phone, "ref": f"CN-{cid}", "cat": category,
         "dom": domain, "sub": subdomain, "msg": msg, "status": status, "loc": location,
         "asm": assembly, "meta": json.dumps(meta) if meta else None, "crit": critical,
         "del": deleted, "c": created, "gs": govt_status, "gref": govt_ref, "asg": assigned},
    )


def seed():
    Base.metadata.create_all(bind=test_engine)
    with test_engine.begin() as conn:
        for tbl in ("token_blocklist", "wa_inbound_messages", "cases", "letterbox",
                    "activity_history", "users", "tenants"):
            conn.execute(text(f"DELETE FROM {tbl}"))
        for tid, name, number in ((1, "Test MP", "+919000000001"), (2, "Other MP", "+919000000002")):
            conn.execute(text(
                "INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, "
                "is_active, created_at, seat_type, account_stage) VALUES "
                "(:t, :n, 'Belagavi', :w, 'Pro', 1, :now, 'mp', 'elected')"),
                {"t": tid, "n": name, "w": number, "now": _ts(1)})
            conn.execute(text(
                "INSERT INTO users (tenant_id, username, password_hash, role, constituency, house, "
                "failed_login_attempts) VALUES (:t, :u, :p, 'mp', 'Belagavi', 'Lok Sabha', 0)"),
                {"t": tid, "u": f"mp{tid}", "p": hash_password("ValidPass1!")})

        _case(conn, 301, status="pending_review", created=_ts(9, 8), thread="T-A",
              location="Tilakwadi", assembly="Belagavi Dakshin", domain="Water", subdomain="Supply", critical=1)
        _case(conn, 302, status="new", created=_ts(8, 8), thread="T-A", location="Tilakwadi",
              assembly="Belagavi Dakshin", domain="Water", subdomain="Supply")
        _case(conn, 303, status="awaiting_location", created=_ts(9, 10), location="Ward 5",
              domain="Roads", subdomain="Potholes")
        _case(conn, 304, status="new", created=_ts(9, 11), govt_status="pending_staff_submit",
              location="Tilakwadi", assembly="Belagavi Dakshin", domain="Roads", subdomain="Potholes")
        _case(conn, 305, status="pending", created=_ts(9, 12), location="Ward 5",
              domain="Water", subdomain="Supply", assigned="Asha")
        _case(conn, 306, status="in_progress", created=_ts(7, 9), govt_status="registered",
              govt_ref="GOV-306", location="Vadgaon", assembly="Belagavi Dakshin", domain="Power")
        _case(conn, 307, status="in_progress", created=_ts(7, 10), govt_status="forwarded",
              govt_ref="GOV-307", location="Vadgaon", assembly="Belagavi Dakshin", domain="Power")
        _case(conn, 308, status="resolved", created=_ts(5), govt_status="resolved",
              govt_ref="GOV-308", location="Tilakwadi", assembly="Belagavi Dakshin", domain="Water", subdomain="Supply")
        _case(conn, 309, status="closed", created=_ts(5, 10), govt_status="rejected",
              govt_ref="GOV-309", location="Ward 5", domain="Roads")
        _case(conn, 310, status="in_progress", created=_ts(6), govt_status="under_review",
              govt_ref="GOV-310", location="Ward 5", domain="Roads", assigned="Ramesh")
        _case(conn, 311, status="new", created=_ts(9, 13), deleted=1)
        _case(conn, 312, tid=2, status="pending_review", created=_ts(9, 14), location="Hubli")
        _case(conn, 313, status="new", created=_ts(4), category="Request")

        for cid, ts in ((301, _ts(10, 9, 30)), (305, _ts(10, 11, 15)), (303, _ts(9, 10, 5))):
            conn.execute(text(
                "INSERT INTO wa_inbound_messages (meta_message_id, tenant_id, sender_phone, "
                "receiver_number, message_type, status, delivery_attempts, retry_count, case_id, "
                "raw_payload, created_at, updated_at, last_received_at) VALUES (:m, 1, "
                "'+919650787758', '+919000000001', 'text', 'processed', 1, 0, :c, '{}', :t, :t, :t)"),
                {"m": f"wamid.golden.{cid}", "c": cid, "t": ts})

        for i, (direction, status) in enumerate((("inbox", "new"), ("inbox", "needs_review"),
                                                  ("inbox", "done"), ("outbox", "drafted"))):
            conn.execute(text(
                "INSERT INTO letterbox (tenant_id, direction, status, is_deleted, created_at) "
                "VALUES (1, :d, :s, 0, :t)"), {"d": direction, "s": status, "t": _ts(9, i)})

        for i, (atype, title, meta) in enumerate((
                ("draft_letter", "Drafted letter to Collector", {"href": "/dashboard/archives/1"}),
                ("note", "Visited ward", {"href": "https://evil.example/x"}),
                ("draft_question", None, {}))):
            conn.execute(text(
                "INSERT INTO activity_history (tenant_id, username, activity_type, title, metadata, "
                "created_at) VALUES (1, 'mp1', :a, :ti, :m, :t)"),
                {"a": atype, "ti": title, "m": json.dumps(meta), "t": _ts(10, 8 + i)})
        # Research-chat activity is the leader's own research, not constituency movement: it must
        # never appear in Recent Movement even when newest (the golden fixture stays unchanged).
        for i, atype in enumerate(("copilot_chat", "analysis", "research_note")):
            conn.execute(text(
                "INSERT INTO activity_history (tenant_id, username, activity_type, title, metadata, "
                "created_at) VALUES (1, 'mp1', :a, :ti, '{}', :t)"),
                {"a": atype, "ti": "What are the three biggest political risks here? — Research Chat", "t": _ts(10, 20 + i)})


@pytest.fixture()
def client(monkeypatch):
    dbmod.engine = test_engine
    dbmod.SessionLocal = TestSession
    db_helpers.engine = test_engine
    main.engine = test_engine
    api_router.engine = test_engine
    api_router.JWT_SECRET = TEST_JWT_SECRET
    monkeypatch.setattr(api_router, "_dashboard_govt_sync_map", _stub_sync_map)
    seed()
    c = TestClient(app, raise_server_exceptions=False)
    yield c


def _headers(client, username="mp1"):
    r = client.post("/api/auth/login", json={"username": username, "password": "ValidPass1!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _fetch(client, monkeypatch, username="mp1"):
    headers = _headers(client, username)  # login must not be affected by the frozen clock
    with monkeypatch.context() as m:
        m.setattr(api_router, "_utcnow", lambda: FROZEN_NOW)
        r = client.get("/api/dashboard/overview", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_mp_overview_matches_golden(client, monkeypatch):
    body = _fetch(client, monkeypatch)
    rendered = json.dumps(body, indent=2, sort_keys=False, ensure_ascii=False) + "\n"
    if os.environ.get("UPDATE_GOLDEN") == "1":
        GOLDEN_PATH.write_text(rendered)
    assert GOLDEN_PATH.exists(), "golden fixture missing"
    assert rendered == GOLDEN_PATH.read_text(), "MP overview response drifted from golden"


def test_mp_overview_is_tenant_scoped(client, monkeypatch):
    mine = _fetch(client, monkeypatch, "mp1")
    other = _fetch(client, monkeypatch, "mp2")
    assert 312 not in {row["id"] for row in mine["attention_queue"]}
    assert [row["id"] for row in other["attention_queue"]] == [312]
    assert mine["validation"]["thread_count"] != other["validation"]["thread_count"]


def test_recent_movement_excludes_research_chat(client, monkeypatch):
    body = _fetch(client, monkeypatch)
    assert body["recent_movement"], "seeded movement should still show"
    assert not any("Research Chat" in (m["item"] or "") for m in body["recent_movement"])


def test_mp_overview_key_order_and_shape(client, monkeypatch):
    body = _fetch(client, monkeypatch)
    assert list(body.keys()) == [
        "seat", "date_label", "attention_counts", "attention_queue", "government_tracking",
        "constituency_pressure", "issue_pressure", "office_pending", "recent_movement", "validation",
    ]
