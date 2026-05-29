import os
import sys
import json
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
TEST_DB_URL = "sqlite:///./test_constituency_case_seed_api.db"

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


import main
import admin_api
import api_router
import core.db_helpers as db_helpers
import sansadx_backend.db as dbmod
from sansadx_backend.db import Base, build_geography_key


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
        conn.execute(
            text(
                """
                INSERT INTO tenants (
                    id, name, constituency, whatsapp_number, subscription_plan,
                    tenant_type, account_stage, seat_type, is_active, created_at
                )
                VALUES
                    (1, 'System Admin', 'India', '+910000000001', 'System', 'mp', 'elected', 'mp', 1, :now),
                    (2, 'Sanket Aspirant', 'Belagavi', '+910000000002', 'Pro', 'aspirant', 'aspirant', 'mp', 1, :now)
                """
            ),
            {"now": now},
        )
        conn.execute(
            text(
                """
                INSERT INTO users (
                    id, tenant_id, username, password_hash, role, constituency,
                    house, display_name, is_active
                )
                VALUES
                    (1, 1, 'sysadmin', :admin_hash, 'sysadmin', 'India', 'Lok Sabha', 'System Admin', 1),
                    (2, 2, 'Jadhav', :owner_hash, 'owner', 'Belagavi', 'Lok Sabha', 'Sanket', 1)
                """
            ),
            {
                "admin_hash": admin_api.hash_password("AdminPass1!"),
                "owner_hash": admin_api.hash_password("OwnerPass1!"),
            },
        )
        conn.execute(
            text(
                """
                INSERT INTO tenant_profiles (
                    tenant_id, mp_name, constituency, state, house, party, profile_data, created_at
                )
                VALUES
                    (2, 'Sanket', 'Belagavi', 'Karnataka', 'Lok Sabha', 'Independent', '{}', :now)
                """
            ),
            {"now": now},
        )
        conn.execute(
            text(
                """
                INSERT INTO tenant_overrides (
                    tenant_id, override_type, key, value, created_at
                ) VALUES
                    (NULL, 'geography_data', :key1, :value1, :now),
                    (NULL, 'geography_data', :key2, :value2, :now)
                """
            ),
            {
                "key1": build_geography_key("mp", "Belagavi", "Belagavi North"),
                "value1": json.dumps([
                    {"station_number": "1", "locality": "Tilakwadi", "building_name": "Tilakwadi"},
                    {"station_number": "2", "locality": "Hanuman Nagar", "building_name": "Hanuman Nagar"},
                ]),
                "key2": build_geography_key("mp", "Belagavi", "Belagavi South"),
                "value2": json.dumps([
                    {"station_number": "1", "locality": "Shahapur", "building_name": "Shahapur"},
                    {"station_number": "2", "locality": "Camp", "building_name": "Camp"},
                ]),
                "now": now,
            },
        )


def _admin_headers():
    resp = client.post("/api/admin/auth/login", json={"username": "sysadmin", "password": "AdminPass1!"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['token']}"}


def test_seed_constituency_cases_uses_shared_geography():
    _seed_database()
    headers = _admin_headers()

    resp = client.post(
        "/api/admin/seed-constituency-cases",
        json={"username": "Jadhav", "count": 120, "seed": 11},
        headers=headers,
    )

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["status"] == "seeded"
    assert payload["inserted"] == 120
    assert payload["used_fallback_localities"] is False
    assert payload["locality_count"] == 4

    with test_engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT COUNT(*), MIN(location), MAX(location)
                FROM cases
                WHERE tenant_id = 2
                """
            )
        ).fetchone()
        assert rows[0] == 120

        sample_meta = conn.execute(
            text("SELECT case_metadata, assembly, location, status FROM cases WHERE tenant_id = 2 ORDER BY id LIMIT 5")
        ).fetchall()
        allowed_localities = {"Tilakwadi", "Hanuman Nagar", "Shahapur", "Camp"}
        allowed_assemblies = {"Belagavi North", "Belagavi South"}
        allowed_statuses = {"new", "in_progress", "resolved"}
        for meta_raw, assembly, location, status in sample_meta:
            meta = json.loads(meta_raw) if isinstance(meta_raw, str) else meta_raw
            assert meta["synthetic_seed"] is True
            assert meta["seeded_for"] == "demo"
            assert location in allowed_localities
            assert assembly in allowed_assemblies
            assert status in allowed_statuses


def test_seed_constituency_cases_replaces_only_prior_synthetic_cases():
    _seed_database()
    headers = _admin_headers()

    first = client.post(
        "/api/admin/seed-constituency-cases",
        json={"tenant_id": 2, "count": 30, "seed": 1},
        headers=headers,
    )
    assert first.status_code == 200, first.text

    with test_engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO cases (
                    tenant_id, user_phone, raw_message, category, status, location, assembly,
                    case_metadata, created_at
                ) VALUES (
                    2, '+919999999999', 'Real grievance', 'Water', 'new', 'Tilakwadi',
                    'Belagavi North', '{}', :now
                )
                """
            ),
            {"now": datetime.utcnow()},
        )

    second = client.post(
        "/api/admin/seed-constituency-cases",
        json={"tenant_id": 2, "count": 40, "seed": 2},
        headers=headers,
    )
    assert second.status_code == 200, second.text
    payload = second.json()
    assert payload["deleted_existing_seeded"] == 30
    assert payload["inserted"] == 40

    with test_engine.begin() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM cases WHERE tenant_id = 2")).scalar()
        synthetic = conn.execute(
            text("SELECT COUNT(*) FROM cases WHERE tenant_id = 2 AND case_metadata LIKE '%synthetic_seed%'")
        ).scalar()
        assert total == 41
        assert synthetic == 40
