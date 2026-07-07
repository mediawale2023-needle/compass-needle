import hashlib
import hmac
import json
import os
import sys
from datetime import datetime, timedelta

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
TEST_META_APP_SECRET = "test-meta-app-secret"
TEST_DB_URL = "sqlite:///./test_whatsapp_inbound_ledger.db"

os.environ["JWT_SECRET"] = TEST_JWT_SECRET
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["ENV"] = "test"
os.environ["OPENAI_API_KEY"] = "sk-test-fake-key-for-testing"
os.environ["META_APP_SECRET"] = TEST_META_APP_SECRET

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
import api_router
import core.db_helpers as db_helpers
import main
import sansadx_backend.db as dbmod
from sansadx_backend.db import Base, hash_password


test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False)

dbmod.engine = test_engine
dbmod.SessionLocal = TestSession
db_helpers.engine = test_engine
main.engine = test_engine
api_router.engine = test_engine
admin_api.engine = test_engine
api_router.JWT_SECRET = TEST_JWT_SECRET
admin_api.JWT_SECRET = TEST_JWT_SECRET

Base.metadata.create_all(bind=test_engine)
client = TestClient(main.app, raise_server_exceptions=False)


def _utcnow():
    return datetime.utcnow()


def _seed_database():
    with test_engine.begin() as conn:
        for table_name in (
            "admin_audit_log",
            "case_media",
            "wa_inbound_messages",
            "wa_message_dedup",
            "cases",
            "tenant_overrides",
            "token_blocklist",
            "users",
            "tenant_profiles",
            "tenants",
        ):
            conn.execute(text(f"DELETE FROM {table_name}"))  # nosec B608

        now = _utcnow()

        conn.execute(
            text(
                """
                INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active, created_at)
                VALUES (1, 'Arun Kumar', 'Bangalore North', '+15551636821', 'Pro', 1, :now)
                """
            ),
            {"now": now},
        )
        conn.execute(
            text(
                """
                INSERT INTO users (tenant_id, username, password_hash, role, constituency, house, is_active)
                VALUES
                    (1, 'mp_arun', :mp_hash, 'mp', 'Bangalore North', 'Lok Sabha', 1),
                    (1, 'sysadmin', :admin_hash, 'sysadmin', 'India', 'Lok Sabha', 1)
                """
            ),
            {
                "mp_hash": hash_password("ValidPass1!"),
                "admin_hash": hash_password("AdminPass1!"),
            },
        )
        conn.execute(
            text(
                """
                INSERT INTO tenant_overrides (tenant_id, override_type, key, value, created_at)
                VALUES
                    (1, 'phone_mapping', '+15551636821', '1', :now),
                    (1, 'phone_mapping', '15551636821', '1', :now)
                """
            ),
            {"now": now},
        )

    if hasattr(main, "_tenant_config_cache"):
        main._tenant_config_cache.clear()


def _make_admin_headers():
    now = _utcnow()
    token = jwt.encode(
        {
            "sub": "sysadmin",
            "tid": 1,
            "role": "sysadmin",
            "iat": now.timestamp(),
            "exp": now + timedelta(hours=8),
        },
        TEST_JWT_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def _make_webhook_payload(message_id="wamid.test.001", body="Water problem in Whitefield", sender="919999111222"):
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "value": {
                    "metadata": {"display_phone_number": "15551636821"},
                    "messages": [{
                        "id": message_id,
                        "from": sender,
                        "type": "text",
                        "text": {"body": body},
                    }],
                }
            }]
        }],
    }


def _make_batched_webhook_payload(messages):
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "value": {
                    "metadata": {"display_phone_number": "15551636821"},
                    "messages": [
                        {
                            "id": message_id,
                            "from": sender,
                            "type": "text",
                            "text": {"body": body},
                        }
                        for message_id, sender, body in messages
                    ],
                }
            }]
        }],
    }


def _post_signed_webhook(payload):
    body = json.dumps(payload).encode("utf-8")
    signature = "sha256=" + hmac.new(TEST_META_APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return client.post(
        "/whatsapp/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )


def setup_function():
    _seed_database()


def test_webhook_persists_inbound_row_and_processes(monkeypatch):
    calls = []

    def fake_process(sender, message_body, wa_phone_id, msg_id, inbound_ledger_id=None, existing_case_id=None, **kwargs):
        calls.append(
            {
                "sender": sender,
                "message_body": message_body,
                "wa_phone_id": wa_phone_id,
                "msg_id": msg_id,
                "inbound_ledger_id": inbound_ledger_id,
                "existing_case_id": existing_case_id,
            }
        )

    monkeypatch.setattr(main, "_process_incoming_message", fake_process)

    resp = _post_signed_webhook(_make_webhook_payload())
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "received"

    with test_engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT meta_message_id, tenant_id, sender_phone, receiver_number, message_type, status
                FROM wa_inbound_messages
                WHERE meta_message_id = :msg_id
                """
            ),
            {"msg_id": "wamid.test.001"},
        ).mappings().first()

    assert row is not None
    assert row["tenant_id"] == 1
    assert row["sender_phone"] == "919999111222"
    assert row["receiver_number"] == "+15551636821"
    assert row["message_type"] == "text"
    assert row["status"] == "processed"
    assert len(calls) == 1
    assert calls[0]["inbound_ledger_id"] is not None


def test_webhook_has_no_shared_slowapi_limit(monkeypatch):
    calls = []

    def fake_process(sender, message_body, wa_phone_id, msg_id, inbound_ledger_id=None, existing_case_id=None, **kwargs):
        calls.append((sender, msg_id, inbound_ledger_id))

    monkeypatch.setattr(main, "_process_incoming_message", fake_process)

    for idx in range(25):
        resp = _post_signed_webhook(
            _make_webhook_payload(
                message_id=f"wamid.burst.{idx}",
                body=f"Water problem {idx}",
                sender=f"91999912{idx:04d}",
            )
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "received"

    with test_engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM wa_inbound_messages")).scalar()

    assert count == 25
    assert len(calls) == 25


def test_webhook_persists_every_message_in_meta_batch(monkeypatch):
    calls = []

    def fake_process(sender, message_body, wa_phone_id, msg_id, inbound_ledger_id=None, existing_case_id=None, **kwargs):
        calls.append((sender, message_body, msg_id, inbound_ledger_id))

    monkeypatch.setattr(main, "_process_incoming_message", fake_process)

    payload = _make_batched_webhook_payload(
        [
            ("wamid.batch.001", "919999111001", "Water issue"),
            ("wamid.batch.002", "919999111002", "Road issue"),
            ("wamid.batch.003", "919999111003", "Garbage issue"),
        ]
    )
    resp = _post_signed_webhook(payload)
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"status": "received", "received_count": 3}

    with test_engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT meta_message_id, sender_phone, status
                FROM wa_inbound_messages
                ORDER BY meta_message_id ASC
                """
            )
        ).mappings().all()

    assert [row["meta_message_id"] for row in rows] == ["wamid.batch.001", "wamid.batch.002", "wamid.batch.003"]
    assert [row["sender_phone"] for row in rows] == ["919999111001", "919999111002", "919999111003"]
    assert all(row["status"] == "processed" for row in rows)
    assert len(calls) == 3


def test_sender_throttle_happens_after_ledger_persistence(monkeypatch):
    calls = []

    def fake_process(sender, message_body, wa_phone_id, msg_id, inbound_ledger_id=None, existing_case_id=None, **kwargs):
        calls.append((sender, msg_id, inbound_ledger_id))

    monkeypatch.setattr(main, "_process_incoming_message", fake_process)

    sender = "919999222333"
    payload = _make_batched_webhook_payload(
        [
            (f"wamid.sender-throttle.{idx}", sender, f"Repeated issue {idx}")
            for idx in range(12)
        ]
    )
    resp = _post_signed_webhook(payload)
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"status": "received", "received_count": 12}

    with test_engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT status, COUNT(*) AS count
                FROM wa_inbound_messages
                WHERE sender_phone = :sender
                GROUP BY status
                """
            ),
            {"sender": sender},
        ).mappings().all()

    status_counts = {row["status"]: row["count"] for row in rows}
    assert status_counts == {"processed": 10, "throttled": 2}
    assert len(calls) == 10


def test_inbound_retry_endpoint_queues_processing(monkeypatch):
    with test_engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO wa_inbound_messages (
                    meta_message_id, tenant_id, sender_phone, receiver_number, message_type,
                    status, delivery_attempts, retry_count, raw_payload, created_at, updated_at, last_received_at
                ) VALUES (
                    'wamid.failed.001', 1, '919999111222', '+15551636821', 'text',
                    'failed', 1, 1, '{}', :now, :now, :now
                )
                """
            ),
            {"now": _utcnow()},
        )
    with test_engine.connect() as conn:
        inbound_row = conn.execute(
            text("SELECT id FROM wa_inbound_messages WHERE meta_message_id = 'wamid.failed.001'")
        ).mappings().first()
    inbound_id = int(inbound_row["id"])

    retried = []

    def fake_retry(inbound_id):
        retried.append(inbound_id)

    monkeypatch.setattr(admin_api, "_retry_inbound_whatsapp_row", fake_retry)

    resp = client.post(f"/api/admin/whatsapp/inbound/{inbound_id}/retry", headers=_make_admin_headers(), json={})
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True
    assert retried == [inbound_id]


def test_inbound_sweeper_rescues_stale_received_rows(monkeypatch):
    payload = {
        "entry_metadata": {"display_phone_number": "15551636821"},
        "message": {
            "id": "wamid.stale.001",
            "from": "919999111222",
            "type": "text",
            "text": {"body": "Drainage problem"},
        },
    }
    with test_engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO wa_inbound_messages (
                    meta_message_id, tenant_id, sender_phone, receiver_number, message_type,
                    status, delivery_attempts, retry_count, raw_payload,
                    created_at, updated_at, last_received_at
                ) VALUES (
                    'wamid.stale.001', 1, '919999111222', '+15551636821', 'text',
                    'received', 1, 0, :raw_payload,
                    :created_at, :updated_at, :last_received_at
                )
                """
            ),
            {
                "raw_payload": json.dumps(payload),
                "created_at": _utcnow() - timedelta(minutes=10),
                "updated_at": _utcnow() - timedelta(minutes=10),
                "last_received_at": _utcnow() - timedelta(minutes=10),
            },
        )
    with test_engine.connect() as conn:
        inbound_row = conn.execute(
            text("SELECT id FROM wa_inbound_messages WHERE meta_message_id = 'wamid.stale.001'")
        ).mappings().first()
    inbound_id = int(inbound_row["id"])

    calls = []

    def fake_process(sender, message_body, wa_phone_id, msg_id, inbound_ledger_id=None, existing_case_id=None, **kwargs):
        calls.append((sender, message_body, inbound_ledger_id))

    monkeypatch.setattr(main, "_process_incoming_message", fake_process)

    rescued = main._sweep_pending_inbound_ledger_rows(limit=10)
    assert rescued == 1
    assert len(calls) == 1

    with test_engine.connect() as conn:
        row = conn.execute(
            text("SELECT status FROM wa_inbound_messages WHERE id = :inbound_id"),
            {"inbound_id": inbound_id},
        ).mappings().first()
    assert row["status"] == "processed"


def test_system_health_uses_inbound_ledger():
    with test_engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO wa_inbound_messages (
                    meta_message_id, tenant_id, sender_phone, receiver_number, message_type,
                    status, delivery_attempts, retry_count, raw_payload,
                    created_at, updated_at, last_received_at
                ) VALUES (
                    'wamid.health.001', 1, '919999111222', '+15551636821', 'text',
                    'failed', 1, 0, '{}',
                    :now, :now, :now
                )
                """
            ),
            {"now": _utcnow()},
        )

    resp = client.get("/api/admin/system-health", headers=_make_admin_headers())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    inbound_queue = body["whatsapp"]["webhook"]["inbound_queue"]
    assert inbound_queue["failed_count"] == 1
    assert inbound_queue["last_webhook"] is not None
