import os
import sys
from datetime import datetime, timezone

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
TEST_DB_URL = "sqlite:///./test_admin_whatsapp_operations.db"

os.environ["JWT_SECRET"] = TEST_JWT_SECRET
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["ENV"] = "test"
os.environ["OPENAI_API_KEY"] = "sk-test-fake-key-for-testing"
os.environ["META_ACCESS_TOKEN"] = "meta-test-token"
os.environ["WHATSAPP_PHONE_NUMBER_ID"] = "1234567890"
os.environ["META_APP_SECRET"] = "meta-app-secret"
os.environ["META_VERIFY_TOKEN"] = "meta-verify-token"

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
from modules import whatsapp as whatsapp_module
from sansadx_backend.db import Base, hash_password


test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False)
client = TestClient(main.app, raise_server_exceptions=False)


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _admin_headers():
    token = jwt.encode(
        {
            "username": "sysadmin",
            "tenant_id": 1,
            "role": "sysadmin",
            "iat": _utcnow().timestamp(),
            "exp": _utcnow().timestamp() + 3600,
        },
        TEST_JWT_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def _seed_database():
    dbmod.engine = test_engine
    dbmod.SessionLocal = TestSession
    db_helpers.engine = test_engine
    main.engine = test_engine
    admin_api.engine = test_engine
    admin_api.JWT_SECRET = TEST_JWT_SECRET
    whatsapp_module.SessionLocal = TestSession

    Base.metadata.create_all(bind=test_engine)

    with test_engine.begin() as conn:
        for table_name in ("wa_outbound_messages", "token_blocklist", "users", "tenants", "cases"):
            conn.execute(text(f"DELETE FROM {table_name}"))  # nosec B608

        now = _utcnow()
        conn.execute(
            text(
                """
                INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active, created_at, config)
                VALUES (1, 'Needle Test Tenant', 'Belagavi', '+919000000001', 'Pro', 1, :now, '{}')
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
                    (1, 'sysadmin', :password_hash, 'sysadmin', 'Belagavi', 'Lok Sabha', 'System Admin', true)
                """
            ),
            {"password_hash": hash_password("AdminPass1!")},
        )


def test_send_logging_and_admin_retry(monkeypatch):
    _seed_database()

    class FailingResponse:
        ok = False
        status_code = 500
        text = '{"error":"boom"}'

        def json(self):
            return {"error": {"message": "boom"}}

    monkeypatch.setattr(whatsapp_module.http_requests, "post", lambda *args, **kwargs: FailingResponse())

    try:
        whatsapp_module.send_whatsapp_message(
            "+919811112223",
            "Test failed send",
            tenant_id=1,
            case_id=42,
            initiated_by="unit-test",
            initiated_via="unit_test",
        )
    except RuntimeError:
        pass

    list_resp = client.get("/api/admin/whatsapp/outbound?status=failed", headers=_admin_headers())
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert len(items) == 1
    assert items[0]["tenant_id"] == 1
    assert items[0]["case_id"] == 42
    assert items[0]["status"] == "failed"
    assert items[0]["attempt_count"] == 1

    class SuccessResponse:
        ok = True

        def json(self):
            return {"messages": [{"id": "wamid.retry-success"}]}

    monkeypatch.setattr(whatsapp_module.http_requests, "post", lambda *args, **kwargs: SuccessResponse())
    monkeypatch.setattr(
        admin_api.http_requests,
        "get",
        lambda *args, **kwargs: type("TokenResp", (), {"ok": True, "json": lambda self: {"name": "Needle Meta App"}})(),
    )

    retry_resp = client.post(f"/api/admin/whatsapp/outbound/{items[0]['id']}/retry", json={}, headers=_admin_headers())
    assert retry_resp.status_code == 200
    payload = retry_resp.json()["item"]
    assert payload["status"] == "sent"
    assert payload["attempt_count"] == 2
    assert payload["meta_message_id"] == "wamid.retry-success"

    health_resp = client.get("/api/admin/system-health", headers=_admin_headers())
    assert health_resp.status_code == 200
    health = health_resp.json()["whatsapp"]
    assert health["meta_token"]["status"] == "green"
    assert health["outbound"]["last_outbound_attempt"] is not None
    assert health["outbound"]["last_outbound_success"] is not None
    assert health["outbound"]["sent_outbound_24h"] >= 1
    assert health["routing"]["configured_tenants"] >= 1
