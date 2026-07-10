import json
import os
import sys
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
TEST_DB_URL = "sqlite:///./test_seat_registry.db"

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
from sansadx_backend.db import Base

test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False)
client = TestClient(main.app, raise_server_exceptions=False)


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
            INSERT INTO tenants (
                id, name, constituency, whatsapp_number, subscription_plan,
                tenant_type, account_stage, seat_type, is_active, created_at
            )
            VALUES
                (1, 'System Admin', 'India', '+910000000001', 'System', 'mp', 'elected', 'mp', 1, :now),
                (2, 'Belgaum MLA', 'Belgaum Dakshin', '+910000000002', 'Pro', 'mla', 'elected', 'mla', 1, :now),
                (3, 'Belgaum Rival', 'Belgaum Dakshin', '+910000000003', 'Pro', 'aspirant', 'aspirant', 'mla', 1, :now),
                (4, 'Ghaziabad MP', 'Ghaziabad', '+910000000004', 'Pro', 'mp', 'elected', 'mp', 1, :now)
        """), {"now": now})

        conn.execute(text("""
            INSERT INTO users (tenant_id, username, password_hash, role, constituency, house, display_name, is_active)
            VALUES (1, 'sysadmin', :ph, 'sysadmin', 'India', 'Lok Sabha', 'System Admin', 1)
        """), {"ph": admin_api.hash_password("AdminPass1!")})

        conn.execute(text("""
            INSERT INTO tenant_overrides (tenant_id, override_type, key, value, created_at)
            VALUES
                (NULL, 'geography_data', 'mla:Belgaum Dakshin/Belgaum South', :stations, :now),
                (NULL, 'geo_seat_manual_override', 'mla:Belgaum Dakshin::khasbag', 'Belgaum South', :now),
                (NULL, 'geo_seat_manual_override', 'mla:Belgaum Dakshin::vadagaon', 'Belgaum South', :now),
                (2, 'geo_manual_override', 'teachers colony - khasbag', 'Belgaum South', :now)
        """), {
            "now": now,
            "stations": json.dumps([
                {"station_number": "1", "locality": "Khasbag", "building_name": ""},
                {"station_number": "2", "locality": "Vadagaon", "building_name": ""},
            ]),
        })

        resolved_meta = json.dumps({
            "location_resolved": True,
            "matched_value": "Khasbag",
            "geography_confidence": "boundary",
            "geography_source": "raw_message",
            "geography_diagnostics": {
                "version": 1,
                "tenant_id": 2,
                "message_excerpt": "Khasbag madhe light nahi aahe",
                "attempts": [{
                    "source": "raw_message",
                    "location_resolved": True,
                    "matched_value": "Khasbag",
                    "match_type": "word_boundary",
                }],
                "final": {
                    "location_resolved": True,
                    "matched_value": "Khasbag",
                    "assembly_constituency": "Belgaum South",
                    "geography_confidence": "boundary",
                    "geography_source": "raw_message",
                    "needs_geography_review": False,
                    "review_reason": "",
                },
            },
        })
        unresolved_meta = json.dumps({
            "location_resolved": False,
            "geography_diagnostics": {
                "version": 1,
                "tenant_id": 2,
                "message_excerpt": "Shahapur madhe kachra ahe",
                "attempts": [{
                    "source": "raw_message",
                    "location_resolved": False,
                    "reason": "parent_spans_assemblies",
                }],
                "final": {
                    "location_resolved": False,
                    "needs_geography_review": True,
                    "review_reason": "parent_spans_assemblies",
                },
            },
        })
        conn.execute(text("""
            INSERT INTO cases (tenant_id, user_phone, raw_message, category, status,
                               location, assembly, case_metadata, created_at, is_deleted)
            VALUES
                (2, '+919999990001', 'Khasbag madhe light nahi aahe', 'Infrastructure & Utilities',
                 'new', 'Khasbag', 'Belgaum South', :resolved_meta, :now, 0),
                (2, '+919999990002', 'Shahapur madhe kachra ahe', 'Uncategorised',
                 'awaiting_location', '', '', :unresolved_meta, :now, 0),
                (4, '+919999990003', 'Ghaziabad water issue', 'Infrastructure & Utilities',
                 'new', 'Lohiya Nagar', 'Ghaziabad', NULL, :now, 0)
        """), {"now": now, "resolved_meta": resolved_meta, "unresolved_meta": unresolved_meta})


def _admin_headers():
    # Mint the admin token directly instead of calling /auth/login: the login
    # endpoint is rate-limited to 5/minute per key, and the whole backend test
    # suite runs in one pytest process, so every extra login here would push
    # other admin-API test files over the shared limiter window.
    token = admin_api.create_admin_token({"sub": "sysadmin", "role": "sysadmin"})
    return {"Authorization": f"Bearer {token}"}


def test_seat_registry_aggregates_geography_corrections_and_tenants():
    _seed_database()
    headers = _admin_headers()

    resp = client.get("/api/admin/seats", headers=headers)
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    by_key = {item["seat_key"]: item for item in items}

    seat = by_key.get("mla:Belgaum Dakshin")
    assert seat is not None, f"expected mla:Belgaum Dakshin in {sorted(by_key)}"
    assert seat["tenant_count"] == 2
    assert seat["geography_ready"] is True
    assert seat["assembly_count"] == 1
    assert seat["locality_count"] == 2
    assert seat["manual_correction_count"] == 2
    assert seat["legacy_correction_count"] == 1
    tenant_ids = {t["tenant_id"] for t in seat["tenants"]}
    assert tenant_ids == {2, 3}

    # Registry rows must not carry heavy manifest payloads (inline SVGs).
    for item in items:
        manifest = item.get("manifest")
        assert manifest is None or set(manifest) <= {"status", "source", "version"}


def test_seat_geography_decisions_reads_case_diagnostics():
    _seed_database()
    headers = _admin_headers()

    resp = client.get(
        "/api/admin/seats/geography-decisions",
        params={"seat_key": "mla:Belgaum Dakshin"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["tenant_ids"] == [2] or set(payload["tenant_ids"]) == {2, 3}

    items = payload["items"]
    assert len(items) == 2
    by_message = {item["message_excerpt"]: item for item in items}

    resolved = by_message["Khasbag madhe light nahi aahe"]
    assert resolved["resolved"] is True
    assert resolved["matched_value"] == "Khasbag"
    assert resolved["confidence"] == "boundary"
    assert resolved["has_diagnostics"] is True

    unresolved = by_message["Shahapur madhe kachra ahe"]
    assert unresolved["resolved"] is False
    assert unresolved["needs_review"] is True
    assert unresolved["review_reason"] == "parent_spans_assemblies"

    # Cases from other seats must never leak in.
    assert all(item["tenant_id"] in {2, 3} for item in items)


def test_seat_geography_decisions_rejects_blank_seat():
    _seed_database()
    headers = _admin_headers()
    resp = client.get(
        "/api/admin/seats/geography-decisions",
        params={"seat_key": "mla:"},
        headers=headers,
    )
    assert resp.status_code == 400
