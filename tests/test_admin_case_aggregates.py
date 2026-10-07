import os
import sys
from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
TEST_DB_URL = "sqlite:///./test_admin_case_aggregates.db"

os.environ["JWT_SECRET"] = TEST_JWT_SECRET
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["ENV"] = "test"
os.environ["OPENAI_API_KEY"] = "sk-test-fake-key-for-testing"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@event.listens_for(Engine, "connect")
def _sqlite_register_pg_lock_functions(dbapi_connection, connection_record):
    try:
        dbapi_connection.create_function("pg_try_advisory_lock", 1, lambda _key: 1)
        dbapi_connection.create_function("pg_advisory_unlock", 1, lambda _key: 1)
        dbapi_connection.create_function("pg_try_advisory_xact_lock", 1, lambda _key: 1)
    except Exception:
        pass


import admin_api
import core.db_helpers as db_helpers
import main
import sansadx_backend.db as dbmod
from sansadx_backend.db import Base, hash_password


test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False)
client = TestClient(main.app, raise_server_exceptions=False)


def _utcnow():
    return datetime.now(timezone.utc)


def _admin_headers():
    token = jwt.encode(
        {"sub": "sysadmin", "tenant_id": 1, "role": "sysadmin", "iat": _utcnow().timestamp(), "exp": _utcnow().timestamp() + 3600},
        TEST_JWT_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def _seed(cases):
    dbmod.engine = test_engine
    dbmod.SessionLocal = TestSession
    db_helpers.engine = test_engine
    main.engine = test_engine
    admin_api.engine = test_engine
    admin_api.JWT_SECRET = TEST_JWT_SECRET
    admin_api.ADMIN_JWT_SECRET = TEST_JWT_SECRET
    Base.metadata.create_all(bind=test_engine)
    with test_engine.begin() as conn:
        for table_name in ("token_blocklist", "users", "tenants", "cases"):
            conn.execute(text(f"DELETE FROM {table_name}"))  # nosec B608
        now = datetime.utcnow()
        for tid in (1, 2, 3):
            conn.execute(
                text("INSERT INTO tenants (id, name, constituency, subscription_plan, is_active, created_at, config) VALUES (:id, :n, 'X', 'Pro', 1, :now, '{}')"),
                {"id": tid, "n": f"Tenant {tid}", "now": now},
            )
        conn.execute(
            text("INSERT INTO users (tenant_id, username, password_hash, role, constituency, house, display_name, is_active) VALUES (1, 'sysadmin', :pw, 'sysadmin', 'X', 'Lok Sabha', 'System Admin', true)"),
            {"pw": hash_password("AdminPass1!")},
        )
        for case in cases:
            conn.execute(
                text("INSERT INTO cases (tenant_id, user_phone, raw_message, status, created_at, resolved_at, is_deleted) VALUES (:tid, '+910000000000', 'm', :status, :created, :resolved, :deleted)"),
                {"tid": case.get("tenant_id", 2), "status": case["status"], "created": case["created_at"], "resolved": case.get("resolved_at"), "deleted": case.get("deleted", False)},
            )


NOW = datetime(2026, 10, 7, 10, 0, 0)  # a Wednesday


def _rows(*specs):
    return [{"status": s, "created_at": c, "resolved_at": r} for s, c, r in specs]


def test_definitions_and_buckets_are_deterministic():
    rows = _rows(
        ("new", NOW - timedelta(days=1), None),            # 0–3
        ("in_progress", NOW - timedelta(days=5), None),     # 4–7
        ("pending_review", NOW - timedelta(days=14), None), # 8–14
        ("awaiting_location", NOW - timedelta(days=20), None),  # 15–30
        ("pending", NOW - timedelta(days=45), None),        # >30
        ("resolved", NOW - timedelta(days=10), NOW - timedelta(days=2)),
        ("completed", NOW - timedelta(days=3), NOW - timedelta(days=1)),
        ("offensive", NOW - timedelta(days=1), None),        # not a grievance status: ignored
        ("closed", NOW - timedelta(days=1), None),           # not in either family: ignored
    )
    result = admin_api.compute_case_aggregates(rows, NOW, 12)
    assert result["open_now"] == 5
    assert [b["count"] for b in result["ageing"]] == [1, 1, 1, 1, 1]
    assert result["definitions"]["open_statuses"] == ["new", "pending", "pending_review", "awaiting_location", "in_progress"]
    assert "sla" not in str(result).lower()


def test_weekly_new_resolved_and_open_trend_end_at_current_open():
    rows = _rows(
        ("new", NOW - timedelta(days=1), None),
        ("resolved", NOW - timedelta(days=15), NOW - timedelta(days=8)),
        ("in_progress", NOW - timedelta(days=100), None),  # created before the window, still open
    )
    result = admin_api.compute_case_aggregates(rows, NOW, 4)
    weekly = result["weekly"]
    assert len(weekly) == 4
    assert weekly[0]["week_start"] == "2026-09-14"
    assert weekly[-1]["week_start"] == "2026-10-05"
    assert sum(w["new"] for w in weekly) == 2  # the 100-day-old case is outside the window
    assert sum(w["resolved"] for w in weekly) == 1
    assert weekly[-1]["open_at_end"] == result["open_now"] == 2
    # The resolved case was open at the end of the week it was created in.
    assert weekly[1]["open_at_end"] == 2
    assert result["resolution"] == {"resolved_in_window": 1, "median_hours": 168.0}


def test_weeks_are_clamped():
    assert admin_api.compute_case_aggregates([], NOW, 999)["weeks"] == 52
    assert admin_api.compute_case_aggregates([], NOW, 0)["weeks"] == 1
    empty = admin_api.compute_case_aggregates([], NOW, 6)
    assert empty["open_now"] == 0 and empty["resolution"]["median_hours"] is None


def test_endpoint_requires_admin():
    _seed([])
    assert client.get("/api/admin/cases/aggregates").status_code in (401, 403)


def test_endpoint_is_read_only_and_tenant_scoped():
    now = datetime.utcnow()
    _seed([
        {"tenant_id": 2, "status": "new", "created_at": now - timedelta(days=2)},
        {"tenant_id": 2, "status": "in_progress", "created_at": now - timedelta(days=40)},
        {"tenant_id": 3, "status": "new", "created_at": now - timedelta(days=1)},
        {"tenant_id": 3, "status": "new", "created_at": now - timedelta(days=1), "deleted": True},
        {"tenant_id": 2, "status": "resolved", "created_at": now - timedelta(days=6), "resolved_at": now - timedelta(days=1)},
    ])
    with test_engine.connect() as conn:
        before = conn.execute(text("SELECT COUNT(*), GROUP_CONCAT(status) FROM cases")).fetchone()

    allr = client.get("/api/admin/cases/aggregates?weeks=8", headers=_admin_headers())
    assert allr.status_code == 200
    body = allr.json()
    assert body["open_now"] == 3  # deleted case excluded
    assert body["tenant_id"] is None
    assert len(body["weekly"]) == 8
    assert body["open_by_tenant"] == {"2": {"open": 2, "open_over_14_days": 1}, "3": {"open": 1, "open_over_14_days": 0}}

    scoped = client.get("/api/admin/cases/aggregates?weeks=8&tenant_id=3", headers=_admin_headers()).json()
    assert scoped["open_now"] == 1 and scoped["tenant_id"] == 3

    assert client.get("/api/admin/cases/aggregates?weeks=0", headers=_admin_headers()).status_code == 422
    assert client.post("/api/admin/cases/aggregates", headers=_admin_headers()).status_code == 405

    with test_engine.connect() as conn:
        after = conn.execute(text("SELECT COUNT(*), GROUP_CONCAT(status) FROM cases")).fetchone()
    assert tuple(before) == tuple(after)
