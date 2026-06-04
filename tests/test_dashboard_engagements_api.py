import os
import sys
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
TEST_DB_URL = "sqlite:///./test_dashboard_engagements.db"

os.environ.setdefault("JWT_SECRET", TEST_JWT_SECRET)
os.environ.setdefault("DATABASE_URL", TEST_DB_URL)
os.environ.setdefault("ENV", "test")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-testing")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sansadx_backend.db import Base, hash_password  # noqa: E402
import sansadx_backend.db as dbmod  # noqa: E402
import core.db_helpers as db_helpers  # noqa: E402
import api_router  # noqa: E402
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

    Base.metadata.create_all(bind=test_engine)

    with test_engine.begin() as conn:
        conn.execute(text("DELETE FROM token_blocklist"))
        conn.execute(text("DELETE FROM dashboard_engagements"))
        conn.execute(text("DELETE FROM users"))
        conn.execute(text("DELETE FROM tenants"))

        conn.execute(text("""
            INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active, created_at, seat_type, account_stage)
            VALUES (1, 'Test MP', 'Belagavi', '+919000000001', 'Pro', 1, :now, 'mp', 'elected')
        """), {"now": datetime.utcnow()})

        conn.execute(text("""
            INSERT INTO users (
                tenant_id, username, password_hash, role, constituency, house, failed_login_attempts
            )
            VALUES (
                1, 'mp_test', :ph, 'mp', 'Belagavi', 'Lok Sabha', 0
            )
        """), {"ph": hash_password("ValidPass1!")})


_seed_database()
client = TestClient(app, raise_server_exceptions=False)


def _user_headers(password="ValidPass1!"):
    login = client.post("/api/auth/login", json={"username": "mp_test", "password": password})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['token']}"}


def test_create_list_and_delete_dashboard_engagement():
    _seed_database()
    headers = _user_headers()

    create = client.post(
        "/api/dashboard/engagements",
        headers=headers,
        json={
            "entry_type": "calendar",
            "title": "District review",
            "notes": "Bring scheme note",
            "location": "Collector Office",
            "scheduled_for": "2026-06-04",
            "start_time": "11:30",
            "end_time": "12:15",
            "calendar_url": "https://calendar.example.com/meet/123",
        },
    )
    assert create.status_code == 200
    created_item = create.json()["item"]
    assert created_item["entry_type"] == "calendar"
    assert created_item["calendar_url"] == "https://calendar.example.com/meet/123"

    listing = client.get("/api/dashboard/engagements?date=2026-06-04", headers=headers)
    assert listing.status_code == 200
    items = listing.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "District review"

    delete = client.delete(f"/api/dashboard/engagements/{created_item['id']}", headers=headers)
    assert delete.status_code == 200

    listing_after_delete = client.get("/api/dashboard/engagements?date=2026-06-04", headers=headers)
    assert listing_after_delete.status_code == 200
    assert listing_after_delete.json()["items"] == []


def test_schedule_item_requires_start_time_or_all_day():
    _seed_database()
    headers = _user_headers()

    create = client.post(
        "/api/dashboard/engagements",
        headers=headers,
        json={
            "entry_type": "schedule",
            "title": "Office hours",
            "scheduled_for": "2026-06-04",
        },
    )
    assert create.status_code == 400
    assert create.json()["detail"] == "Schedule items need a start time or all-day mode"
