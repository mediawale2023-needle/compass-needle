import json
import os
import sys
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
TEST_DB_URL = "sqlite:///./test_geography_hierarchy_edit.db"

os.environ["JWT_SECRET"] = TEST_JWT_SECRET
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["ENV"] = "test"
os.environ["OPENAI_API_KEY"] = "sk-test-fake-key-for-testing"
os.environ["META_APP_SECRET"] = "test-meta-app-secret"
os.environ["META_PHONE_NUMBER_ID"] = "15551636821"
os.environ["META_ACCESS_TOKEN"] = "FAKE_ACCESS_TOKEN"
os.environ["META_VERIFY_TOKEN"] = "test-verify-token-123"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@event.listens_for(Engine, "connect")
def _sqlite_register_pg_lock_functions(dbapi_connection, connection_record):
    try:
        dbapi_connection.create_function("pg_try_advisory_lock", 1, lambda _key: 1)
        dbapi_connection.create_function("pg_advisory_unlock", 1, lambda _key: 1)
        dbapi_connection.create_function("pg_try_advisory_xact_lock", 1, lambda _key: 1)
    except Exception:
        pass


import main
import admin_api
import api_router
import core.db_helpers as db_helpers
import sansadx_backend.db as dbmod
from sansadx_backend.db import Base, build_geography_key

test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False)
client = TestClient(main.app, raise_server_exceptions=False)

PC = "Belagavi"
AC = "Belgaum South"
SEAT_TYPE = "mla"


def _seed_database():
    dbmod.engine = test_engine
    dbmod.SessionLocal = TestSession
    db_helpers.engine = test_engine
    main.engine = test_engine
    api_router.engine = test_engine
    admin_api.engine = test_engine
    admin_api.SessionLocal = TestSession

    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    with test_engine.begin() as conn:
        now = datetime.utcnow()
        conn.execute(text("""
            INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan,
                                 tenant_type, account_stage, seat_type, is_active, created_at)
            VALUES (1, 'System Admin', 'India', '+910000000001', 'System', 'mp', 'elected', 'mp', 1, :now)
        """), {"now": now})
        conn.execute(text("""
            INSERT INTO users (tenant_id, username, password_hash, role, constituency, house, display_name, is_active)
            VALUES (1, 'sysadmin', :ph, 'sysadmin', 'India', 'Lok Sabha', 'System Admin', 1)
        """), {"ph": admin_api.hash_password("AdminPass1!")})

        stations = [
            {"station_number": "1", "locality": "Rajwada Compound, Vadagaon", "building_name": ""},
            {"station_number": "2", "locality": "Yallur Road Vadagaon", "building_name": ""},
            {"station_number": "3", "locality": "Shri Hari Apartment", "building_name": ""},
        ]
        conn.execute(text("""
            INSERT INTO tenant_overrides (tenant_id, override_type, key, value, created_at)
            VALUES (NULL, 'geography_data', :key, :stations, :now)
        """), {
            "now": now,
            "key": build_geography_key(SEAT_TYPE, PC, AC),
            "stations": json.dumps(stations),
        })


def _admin_headers():
    # Mint the token directly: /auth/login is rate-limited 5/minute per key
    # and the backend suite shares one limiter window across test files.
    token = admin_api.create_admin_token({"sub": "sysadmin", "role": "sysadmin"})
    return {"Authorization": f"Bearer {token}"}


def _get_stations():
    resp = client.get(f"/api/admin/geography/{PC}/{AC}", params={"seat_type": SEAT_TYPE}, headers=_admin_headers())
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def test_set_mode_persists_manual_pairing_and_survives_reload():
    _seed_database()
    headers = _admin_headers()

    resp = client.patch(
        f"/api/admin/geography/{PC}/{AC}/hierarchy",
        params={"seat_type": SEAT_TYPE},
        json={
            "locality": "Rajwada Compound, Vadagaon",
            "mode": "set",
            "parent_locality": "Vadagaon",
            "sub_locality": "Rajwada Compound",
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    saved = resp.json()["station"]
    assert saved["parent_locality"] == "Vadagaon"
    assert saved["sub_locality"] == "Rajwada Compound"
    assert saved["hierarchy_source"] == "manual"

    # Reload from DB — the manual pairing must not have been re-derived away.
    stations = _get_stations()
    row = next(s for s in stations if s["locality"] == "Rajwada Compound, Vadagaon")
    assert row["parent_locality"] == "Vadagaon"
    assert row["sub_locality"] == "Rajwada Compound"
    assert row["hierarchy_source"] == "manual"

    # Sibling rows are untouched.
    sibling = next(s for s in stations if s["locality"] == "Yallur Road Vadagaon")
    assert sibling.get("hierarchy_source") != "manual"


def test_set_mode_can_assign_a_brand_new_parent_name():
    _seed_database()
    headers = _admin_headers()

    resp = client.patch(
        f"/api/admin/geography/{PC}/{AC}/hierarchy",
        params={"seat_type": SEAT_TYPE},
        json={
            "locality": "Shri Hari Apartment",
            "mode": "set",
            "parent_locality": "Custom Manual Block",
            "sub_locality": "Shri Hari",
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["station"]["parent_locality"] == "Custom Manual Block"


def test_clear_to_flat_locks_row_as_flat_locality():
    _seed_database()
    headers = _admin_headers()

    resp = client.patch(
        f"/api/admin/geography/{PC}/{AC}/hierarchy",
        params={"seat_type": SEAT_TYPE},
        json={"locality": "Yallur Road Vadagaon", "mode": "clear_to_flat"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    station = resp.json()["station"]
    assert station.get("parent_locality") is None
    assert station.get("sub_locality") is None
    assert station["hierarchy_source"] == "manual"


def test_reset_to_auto_removes_manual_marker_and_resumes_inference():
    _seed_database()
    headers = _admin_headers()

    set_resp = client.patch(
        f"/api/admin/geography/{PC}/{AC}/hierarchy",
        params={"seat_type": SEAT_TYPE},
        json={
            "locality": "Rajwada Compound, Vadagaon",
            "mode": "set",
            "parent_locality": "Something Wrong",
            "sub_locality": "Rajwada Compound",
        },
        headers=headers,
    )
    assert set_resp.status_code == 200, set_resp.text

    reset_resp = client.patch(
        f"/api/admin/geography/{PC}/{AC}/hierarchy",
        params={"seat_type": SEAT_TYPE},
        json={"locality": "Rajwada Compound, Vadagaon", "mode": "reset_to_auto"},
        headers=headers,
    )
    assert reset_resp.status_code == 200, reset_resp.text
    station = reset_resp.json()["station"]
    assert station.get("hierarchy_source") != "manual"
    # Auto-inference resumes: corroborated by the sibling "Yallur Road Vadagaon" row.
    assert station.get("parent_locality") == "Vadagaon"


def test_set_mode_requires_both_parent_and_sub():
    _seed_database()
    headers = _admin_headers()
    resp = client.patch(
        f"/api/admin/geography/{PC}/{AC}/hierarchy",
        params={"seat_type": SEAT_TYPE},
        json={"locality": "Yallur Road Vadagaon", "mode": "set", "parent_locality": "Vadagaon"},
        headers=headers,
    )
    assert resp.status_code == 400


def test_unknown_locality_returns_404():
    _seed_database()
    headers = _admin_headers()
    resp = client.patch(
        f"/api/admin/geography/{PC}/{AC}/hierarchy",
        params={"seat_type": SEAT_TYPE},
        json={"locality": "Nonexistent Row", "mode": "clear_to_flat"},
        headers=headers,
    )
    assert resp.status_code == 404
