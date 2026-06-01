import os
import sys
from datetime import datetime, timedelta

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
TEST_DB_URL = "sqlite:///./test_dashboard_map_manifest_api.db"

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
import main
import api_router
import core.db_helpers as db_helpers
import sansadx_backend.db as dbmod
from sansadx_backend.db import Base, hash_password


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
    api_router.JWT_SECRET = TEST_JWT_SECRET
    admin_api.JWT_SECRET = TEST_JWT_SECRET

    Base.metadata.create_all(bind=test_engine)

    with test_engine.begin() as conn:
        for table_name in ("admin_audit_log", "seat_map_manifests", "users", "tenant_profiles", "tenants"):
            conn.execute(text(f"DELETE FROM {table_name}"))  # nosec B608

        now = datetime.utcnow()
        conn.execute(
            text(
                """
                INSERT INTO tenants
                    (id, name, constituency, seat_type, account_stage, whatsapp_number, subscription_plan, is_active, created_at)
                VALUES
                    (10, 'Sanket', 'Belgaum Dakshin', 'mla', 'aspirant', '+919000001010', 'Pro', 1, :now),
                    (11, 'Arun', 'Unknown Seat', 'mla', 'elected', '+919000001011', 'Pro', 1, :now)
                """
            ),
            {"now": now},
        )
        conn.execute(
            text(
                """
                INSERT INTO users
                    (tenant_id, username, password_hash, role, constituency, house, display_name, is_active)
                VALUES
                    (10, 'sanket', :password_hash, 'owner', 'Belgaum Dakshin', 'Vidhan Sabha', 'Sanket', 1),
                    (11, 'arun', :password_hash, 'owner', 'Unknown Seat', 'Vidhan Sabha', 'Arun', 1),
                    (10, 'sysadmin', :password_hash, 'admin', 'Belgaum Dakshin', 'Vidhan Sabha', 'Sysadmin', 1)
                """
            ),
            {"password_hash": hash_password("ValidPass1!")},
        )


def _auth_headers(username: str, tenant_id: int, role: str = "owner"):
    token = jwt.encode(
        {"sub": username, "tid": tenant_id, "role": role, "exp": datetime.utcnow() + timedelta(hours=8)},
        TEST_JWT_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def test_dashboard_map_manifest_returns_tenant_seat_manifest():
    _seed_database()
    resp = client.get("/api/maps/seat-manifest", headers=_auth_headers("sanket", 10))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["seat_key"] == "mla:belgaum-dakshin"
    assert data["seat_type"] == "mla"
    assert data["asset"]["path"] == "/maps/mla/belgaum-dakshin-outline.svg"
    assert len(data["features"]) > 0


def test_dashboard_map_manifest_404_for_unmapped_seat():
    _seed_database()
    resp = client.get("/api/maps/seat-manifest", headers=_auth_headers("arun", 11))
    assert resp.status_code == 404


def test_admin_seat_map_upsert_overrides_repo_manifest():
    _seed_database()
    admin_headers = _auth_headers("sysadmin", 10, role="admin")

    create_resp = client.post(
        "/api/admin/seat-maps",
        headers=admin_headers,
        json={
            "seat_key": "mla:belgaum-dakshin",
            "seat_type": "mla",
            "seat_name": "Belgaum Dakshin",
            "state": "Karnataka",
            "aliases": ["Belgaum Dakshin", "Belagavi South"],
            "asset": {"type": "svg", "path": "/maps/mla/custom-bd.svg", "aspect_ratio": "4 / 3"},
            "features": [
                {
                    "feature_key": "custom-core",
                    "label": "Custom Core",
                    "aliases": ["nath pai circle"],
                    "anchor": {"x": 50, "y": 50},
                }
            ],
            "fallback_anchors": [{"x": 10, "y": 10}],
            "status": "live",
        },
    )
    assert create_resp.status_code == 200, create_resp.text

    resp = client.get("/api/maps/seat-manifest", headers=_auth_headers("sanket", 10))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["source"] == "admin"
    assert data["asset"]["path"] == "/maps/mla/custom-bd.svg"
    assert data["features"][0]["feature_key"] == "custom-core"
