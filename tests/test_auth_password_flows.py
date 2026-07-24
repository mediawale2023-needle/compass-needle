import os
import sys
from datetime import datetime, timedelta

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
TEST_DB_URL = "sqlite:///./test_auth_flows.db"

os.environ.setdefault("JWT_SECRET", TEST_JWT_SECRET)
os.environ.setdefault("DATABASE_URL", TEST_DB_URL)
os.environ.setdefault("ENV", "test")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-testing")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sansadx_backend.db import Base, hash_password  # noqa: E402
import sansadx_backend.db as dbmod  # noqa: E402
import core.db_helpers as db_helpers  # noqa: E402
import api_router  # noqa: E402
import admin_api  # noqa: E402
import main  # noqa: E402
from main import app  # noqa: E402


test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(bind=test_engine)


@event.listens_for(Engine, "connect")
def _sqlite_register_pg_lock_functions(dbapi_connection, connection_record):
    try:
        dbapi_connection.create_function("pg_try_advisory_lock", 1, lambda _key: 1)
        dbapi_connection.create_function("pg_advisory_unlock", 1, lambda _key: 1)
        dbapi_connection.create_function("pg_try_advisory_xact_lock", 1, lambda _key: 1)
    except Exception:
        pass


def _seed_database():
    dbmod.engine = test_engine
    dbmod.SessionLocal = TestSession
    db_helpers.engine = test_engine
    main.engine = test_engine
    api_router.engine = test_engine
    api_router.JWT_SECRET = TEST_JWT_SECRET
    admin_api.engine = test_engine
    admin_api.SessionLocal = TestSession
    admin_api.JWT_SECRET = TEST_JWT_SECRET

    Base.metadata.create_all(bind=test_engine)

    with test_engine.begin() as conn:
        conn.execute(text("DELETE FROM token_blocklist"))
        conn.execute(text("DELETE FROM users"))
        conn.execute(text("DELETE FROM tenants"))

        conn.execute(text("""
            INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active, created_at, seat_type, account_stage)
            VALUES (1, 'Test MP', 'Belagavi', '+919000000001', 'Pro', 1, :now, 'mp', 'elected')
        """), {"now": datetime.utcnow()})

        conn.execute(text("""
            INSERT INTO users (
                tenant_id, username, password_hash, role, constituency, house,
                must_change_password, failed_login_attempts
            )
            VALUES (
                1, 'mp_test', :ph, 'mp', 'Belagavi', 'Lok Sabha',
                0, 0
            )
        """), {"ph": hash_password("ValidPass1!")})

        conn.execute(text("""
            INSERT INTO users (tenant_id, username, password_hash, role, constituency, house)
            VALUES (1, 'sysadmin', :ph, 'sysadmin', 'India', 'Lok Sabha')
        """), {"ph": hash_password("AdminPass1!")})


_seed_database()
client = TestClient(app, raise_server_exceptions=False)


def _admin_headers():
    login = client.post("/api/admin/auth/login", json={"username": "sysadmin", "password": "AdminPass1!"})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['token']}"}


def _user_login(password="ValidPass1!"):
    return client.post("/api/auth/login", json={"username": "mp_test", "password": password})


def _user_headers(password="ValidPass1!"):
    login = _user_login(password=password)
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['token']}"}


def test_admin_reset_forces_password_change_and_returns_temp_password():
    _seed_database()

    response = client.patch(
        "/api/admin/mps/1/password",
        headers=_admin_headers(),
        json={"generate_temp_password": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["must_change_password"] is True
    assert len(body["temporary_password"]) >= 8

    login = _user_login(password=body["temporary_password"])
    assert login.status_code == 200
    assert login.json()["user"]["must_change_password"] is True
    assert login.json()["user"]["force_password_reason"] == "admin_reset"


def test_forced_reset_blocks_dashboard_until_password_is_changed():
    _seed_database()

    reset = client.patch(
        "/api/admin/mps/1/password",
        headers=_admin_headers(),
        json={"new_password": "TempPass9!"},
    )
    assert reset.status_code == 200

    login = _user_login(password="TempPass9!")
    token = login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    dashboard = client.get("/api/dashboard/summary", headers=headers)
    assert dashboard.status_code == 403
    assert dashboard.json()["detail"] == "Password reset required"

    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["must_change_password"] is True


def test_complete_forced_password_reset_clears_flags_and_allows_dashboard():
    _seed_database()

    reset = client.patch(
        "/api/admin/mps/1/password",
        headers=_admin_headers(),
        json={"new_password": "TempPass9!"},
    )
    assert reset.status_code == 200

    login = _user_login(password="TempPass9!")
    token = login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    complete = client.post(
        "/api/auth/complete-forced-password-reset",
        headers=headers,
        json={"current_password": "TempPass9!", "new_password": "NewStrong9!"},
    )
    assert complete.status_code == 200
    body = complete.json()
    assert body["success"] is True
    assert body["user"]["must_change_password"] is False

    refreshed_headers = {"Authorization": f"Bearer {body['token']}"}
    dashboard = client.get("/api/dashboard/summary", headers=refreshed_headers)
    assert dashboard.status_code == 200


def test_login_attempt_lockout_kicks_in_after_repeated_failures():
    _seed_database()

    for _ in range(5):
        response = _user_login(password="WrongPass9!")
        assert response.status_code in (401, 423)

    # This test targets the DB-backed account lockout (423), but six rapid
    # logins also exhaust SlowAPI's 5/min budget, whose 429 fires first and
    # masks the behavior under test. Clear the rate limiter so the sixth
    # attempt reaches the lockout check.
    from core.rate_limiter import limiter
    limiter.reset()

    locked = _user_login(password="WrongPass9!")
    assert locked.status_code == 423
    assert "Too many failed attempts" in locked.json()["detail"]
