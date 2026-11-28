"""
tests/test_dpdp_erasure_postgres.py — DPDP citizen erasure against real PostgreSQL.

The erasure endpoint runs one transaction across cases, case media, contacts and the
WhatsApp ledgers. It previously referenced a column that does not exist, so every
request rolled back. SQLite cannot run it (`= ANY(:ids)`), so this test needs a
DISPOSABLE PostgreSQL database; without NEEDLE_PG_TEST_URL the module is skipped.

Run:  NEEDLE_PG_TEST_URL=postgresql://user@host/throwaway_db \
      python -m pytest tests/test_dpdp_erasure_postgres.py
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

PG_URL = os.environ.get("NEEDLE_PG_TEST_URL", "")
if not PG_URL.startswith("postgresql"):
    pytest.skip("NEEDLE_PG_TEST_URL not set to a PostgreSQL URL", allow_module_level=True)

TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
# Import-time migrations must run on this PostgreSQL database (CI sets a SQLite DATABASE_URL
# globally), so tables created there, such as wa_text_buffer, exist as in production.
os.environ["DATABASE_URL"] = PG_URL
os.environ.setdefault("ENV", "test")
os.environ.setdefault("JWT_SECRET", TEST_JWT_SECRET)
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-testing")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import jwt  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

import admin_api  # noqa: E402
import api_router  # noqa: E402
import core.db_helpers as db_helpers  # noqa: E402
import main  # noqa: E402
import sansadx_backend.db as dbmod  # noqa: E402
from sansadx_backend.db import Base, hash_password  # noqa: E402
from tests.auth_token_claims import credential_claims  # noqa: E402

pg_engine = create_engine(PG_URL)
client = TestClient(main.app, raise_server_exceptions=False)
CITIZEN = "+919812345678"
OTHER = "+919800000001"


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _admin_headers():
    t = datetime.now(timezone.utc).timestamp()
    token = jwt.encode({**credential_claims(pg_engine, "sysadmin"), "sub": "sysadmin", "tid": 1, "role": "sysadmin",
                        "iat": t, "exp": t + 3600}, TEST_JWT_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def pg():
    dbmod.engine = pg_engine
    for m in (db_helpers, main, api_router, admin_api):
        m.engine = pg_engine
    api_router.JWT_SECRET = admin_api.JWT_SECRET = admin_api.ADMIN_JWT_SECRET = TEST_JWT_SECRET
    Base.metadata.create_all(bind=pg_engine)
    now = _now()
    with pg_engine.begin() as conn:
        for t in ("admin_audit_log", "case_media", "case_activity_log", "wa_text_buffer", "wa_inbound_messages",
                  "wa_outbound_messages", "contacts", "cases", "token_blocklist", "users", "tenant_profiles", "tenants"):
            conn.execute(text(f"DELETE FROM {t}"))  # nosec B608
        conn.execute(text("INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active, created_at) "
                          "VALUES (1, 'T1', 'X', '+919000000001', 'Pro', true, :now)"), {"now": now})
        conn.execute(text("INSERT INTO users (tenant_id, username, password_hash, role, constituency, house, display_name, is_active) "
                          "VALUES (1, 'sysadmin', :pw, 'sysadmin', 'X', 'Lok Sabha', 'Admin', true)"), {"pw": hash_password("Password1")})
        for cid, phone in ((100, CITIZEN), (101, OTHER)):
            conn.execute(text(
                "INSERT INTO cases (id, tenant_id, user_phone, raw_message, category, status, location, created_at, "
                "response_to_citizen, case_metadata, govt_submission_worksheet, is_deleted) "
                "VALUES (:id, 1, :ph, 'Road broken near my house, call me', 'Roads', 'new', 'Tilakwadi', :now, "
                "'We will visit', CAST(:meta AS JSON), CAST(:ws AS JSON), false)"),
                {"id": cid, "ph": phone, "now": now, "meta": json.dumps({"citizen_name": "Ravi"}),
                 "ws": json.dumps({"mobile": phone, "grievance_text": "Road broken"})})
        conn.execute(text("INSERT INTO case_media (tenant_id, case_id, source, media_type, mime_type, file_name, media_data, created_at) "
                          "VALUES (1, 100, 'whatsapp', 'image', 'image/jpeg', 'x.jpg', :b, :now)"), {"b": b"jpeg", "now": now})
        conn.execute(text("INSERT INTO contacts (tenant_id, phone, display_name, created_at, updated_at) "
                          "VALUES (1, :ph, 'Ravi', :now, :now)"), {"ph": CITIZEN, "now": now})
        conn.execute(text("INSERT INTO wa_inbound_messages (meta_message_id, tenant_id, sender_phone, receiver_number, message_type, "
                          "status, raw_payload, last_error, delivery_attempts, retry_count, last_received_at, created_at, updated_at) VALUES "
                          "('wamid.1', 1, '919812345678', '919000000001', 'text', 'processed', :p, 'x', 1, 0, :now, :now, :now), "
                          "('wamid.2', 1, '919800000001', '919000000001', 'text', 'processed', :p, NULL, 1, 0, :now, :now, :now)"),
                     {"p": json.dumps({"text": {"body": "Road broken"}}), "now": now})
        conn.execute(text("INSERT INTO wa_outbound_messages (tenant_id, case_id, to_number, message_body, status, request_payload, "
                          "meta_response, created_at, updated_at) VALUES (1, 100, '919812345678', 'We received your complaint', "
                          "'sent', CAST(:p AS JSON), CAST(:p AS JSON), :now, :now)"), {"p": json.dumps({"to": CITIZEN}), "now": now})
        conn.execute(text("INSERT INTO wa_text_buffer (tenant_id, sender_phone, receiver_number, messages, status) "
                          "VALUES (1, '919812345678', '919000000001', CAST(:m AS JSONB), 'pending')"),
                     {"m": json.dumps([{"text": "also no water"}])})
    yield
    # Leave the shared CI database as other PostgreSQL test files expect it.
    with pg_engine.begin() as conn:
        for t in ("admin_audit_log", "case_media", "case_activity_log", "wa_text_buffer", "wa_inbound_messages",
                  "wa_outbound_messages", "contacts", "cases", "token_blocklist", "users", "tenant_profiles", "tenants"):
            conn.execute(text(f"DELETE FROM {t}"))  # nosec B608


def test_erasure_redacts_everything_for_one_citizen_only():
    r = client.post("/api/admin/dpdp/erase-citizen", json={"phone": "98123 45678", "confirm": True}, headers=_admin_headers())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["phone"] == "******5678"
    assert body["erased"] == {"case_media": 1, "cases": 1, "contacts": 1, "wa_inbound_messages": 1,
                              "wa_text_buffer": 1, "wa_outbound_messages": 1}
    with pg_engine.connect() as conn:
        case = conn.execute(text("SELECT user_phone, raw_message, response_to_citizen, case_metadata, govt_submission_worksheet, "
                                 "category, status, location FROM cases WHERE id = 100")).mappings().one()
        assert case["user_phone"] == "ERASED" and case["raw_message"] == "[erased under DPDP request]"
        assert case["response_to_citizen"] is None and case["case_metadata"] is None and case["govt_submission_worksheet"] is None
        assert (case["category"], case["status"], case["location"]) == ("Roads", "new", "Tilakwadi")   # analytics kept
        inbound = conn.execute(text("SELECT sender_phone, raw_payload, last_error FROM wa_inbound_messages "
                                    "WHERE meta_message_id = 'wamid.1'")).mappings().one()
        assert dict(inbound) == {"sender_phone": "ERASED", "raw_payload": "{}", "last_error": None}   # raw_payload is NOT NULL
        out = conn.execute(text("SELECT to_number, message_body, request_payload FROM wa_outbound_messages")).mappings().one()
        assert (out["to_number"], out["message_body"], out["request_payload"]) == ("ERASED", "[erased]", None)
        assert conn.execute(text("SELECT COUNT(*) FROM case_media")).scalar() == 0
        assert conn.execute(text("SELECT COUNT(*) FROM contacts")).scalar() == 0
        assert conn.execute(text("SELECT COUNT(*) FROM wa_text_buffer")).scalar() == 0
        # The other citizen is untouched.
        assert conn.execute(text("SELECT user_phone FROM cases WHERE id = 101")).scalar() == OTHER
        assert conn.execute(text("SELECT sender_phone FROM wa_inbound_messages WHERE meta_message_id = 'wamid.2'")).scalar() == "919800000001"
        audit = conn.execute(text("SELECT action, target_name FROM admin_audit_log")).mappings().one()
        assert (audit["action"], audit["target_name"]) == ("dpdp_erase_citizen", "******5678")


def test_erasure_requires_confirmation_and_admin():
    r = client.post("/api/admin/dpdp/erase-citizen", json={"phone": "9812345678"}, headers=_admin_headers())
    assert r.status_code == 400
    assert client.post("/api/admin/dpdp/erase-citizen", json={"phone": "9812345678", "confirm": True}).status_code in (401, 403)
    with pg_engine.connect() as conn:
        assert conn.execute(text("SELECT user_phone FROM cases WHERE id = 100")).scalar() == CITIZEN
