import os
import sys
from datetime import datetime, timedelta

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
TEST_DB_URL = "sqlite:///./test_case_buckets_api.db"

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

    Base.metadata.create_all(bind=test_engine)

    with test_engine.begin() as conn:
        for table_name in ("cases", "users", "tenants"):
            conn.execute(text(f"DELETE FROM {table_name}"))  # nosec B608

        now = datetime.utcnow()
        conn.execute(
            text(
                """
                INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active, created_at)
                VALUES (1, 'Arun Kumar', 'Bangalore North', '+919000000001', 'Pro', 1, :now)
                """
            ),
            {"now": now},
        )
        conn.execute(
            text(
                """
                INSERT INTO users (tenant_id, username, password_hash, role, constituency, house, is_active)
                VALUES (1, 'mp_arun', :password_hash, 'mp', 'Bangalore North', 'Lok Sabha', 1)
                """
            ),
            {"password_hash": hash_password("ValidPass1!")},
        )

        rows = [
            (101, "Infrastructure & Utilities", "new", "No water supply in Whitefield"),
            (102, "Spam (Offensive)", "offensive", "fuck you"),
            (103, "Spam", "new", "fake complaint flood"),
            (104, "Request", "new", "Please call me back"),
            (105, "General", "irrelevant", "hello sir good morning"),
            (106, "Infrastructure & Utilities", "resolved", "Streetlight fixed"),
        ]
        for case_id, category, status, raw_message in rows:
            conn.execute(
                text(
                    """
                    INSERT INTO cases
                        (id, tenant_id, user_phone, raw_message, category, status, case_metadata, is_critical, created_at)
                    VALUES
                        (:id, 1, :phone, :msg, :cat, :status, :meta, false, :created_at)
                    """
                ),
                {
                    "id": case_id,
                    "phone": f"919900000{case_id}",
                    "msg": raw_message,
                    "cat": category,
                    "status": status,
                    "meta": "{}",
                    "created_at": now - timedelta(minutes=case_id % 10),
                },
            )


def _auth_headers():
    token = jwt.encode(
        {"sub": "mp_arun", "tid": 1, "role": "mp", "exp": datetime.utcnow() + timedelta(hours=8)},
        TEST_JWT_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def test_all_cases_excludes_other_bucket_and_other_bucket_includes_moderation_rows():
    _seed_database()
    headers = _auth_headers()

    all_resp = client.get(
        "/api/cases?exclude_status=resolved,closed,offensive,irrelevant&exclude_categories=Request,Greetings,Spam,Spam%20(Offensive)",
        headers=headers,
    )
    assert all_resp.status_code == 200, all_resp.text
    all_cases = all_resp.json()["cases"]
    assert [case["id"] for case in all_cases] == [101]

    other_resp = client.get("/api/cases?bucket=other", headers=headers)
    assert other_resp.status_code == 200, other_resp.text
    other_ids = {case["id"] for case in other_resp.json()["cases"]}
    assert other_ids == {102, 103, 104, 105}
