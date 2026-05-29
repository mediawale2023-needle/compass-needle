import os
import sys
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
TEST_DB_URL = "sqlite:///./test_admin_staff_api.db"

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
        for table_name in ("token_blocklist", "users", "tenant_profiles", "tenants"):
            conn.execute(text(f"DELETE FROM {table_name}"))  # nosec B608

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
                    (2, 'Belagavi Aspirant A', 'Belagavi', '+910000000002', 'Pro', 'aspirant', 'aspirant', 'mp', 1, :now),
                    (3, 'Belagavi Elected MP', 'Belagavi', '+910000000003', 'Pro', 'mp', 'elected', 'mp', 1, :now)
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
                    (2, 2, 'asp_a', :owner_hash, 'owner', 'Belagavi', 'Lok Sabha', 'Aspirant A', 1),
                    (3, 3, 'mp_belagavi', :mp_hash, 'mp', 'Belagavi', 'Lok Sabha', 'Belagavi MP', 1),
                    (4, 2, 'pa_one', :staff_hash, 'staff', 'Belagavi', 'Lok Sabha', 'PA One', 1)
                """
            ),
            {
                "admin_hash": admin_api.hash_password("AdminPass1!"),
                "owner_hash": admin_api.hash_password("OwnerPass1!"),
                "mp_hash": admin_api.hash_password("MpPass1!"),
                "staff_hash": admin_api.hash_password("StaffPass1!"),
            },
        )


def _admin_headers():
    resp = client.post("/api/admin/auth/login", json={"username": "sysadmin", "password": "AdminPass1!"})
    assert resp.status_code == 200, resp.text
    token = resp.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_staff_list_excludes_primary_accounts():
    _seed_database()
    headers = _admin_headers()

    resp = client.get("/api/admin/staff", headers=headers)

    assert resp.status_code == 200, resp.text
    usernames = {row["username"] for row in resp.json()["staff"]}
    assert usernames == {"pa_one"}


def test_staff_endpoints_reject_primary_accounts():
    _seed_database()
    headers = _admin_headers()

    suspend_owner = client.patch("/api/admin/staff/2/suspend", headers=headers)
    reassign_mp = client.patch("/api/admin/staff/3/reassign", json={"tenant_id": 2}, headers=headers)

    assert suspend_owner.status_code == 400
    assert reassign_mp.status_code == 404
