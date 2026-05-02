import io
import os
import sys
from datetime import datetime, timedelta

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
TEST_DB_URL = "sqlite:///./test_letterbox_workflow.db"

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


def _ensure_letterbox_columns():
    alter_statements = [
        "ALTER TABLE users ADD COLUMN phone VARCHAR",
        "ALTER TABLE letterbox ADD COLUMN image_data BLOB",
        "ALTER TABLE letterbox ADD COLUMN image_mime VARCHAR",
        "ALTER TABLE letterbox ADD COLUMN category VARCHAR",
        "ALTER TABLE letterbox ADD COLUMN ocr_text TEXT",
        "ALTER TABLE letterbox ADD COLUMN document_text TEXT",
        "ALTER TABLE letterbox ADD COLUMN diary_number VARCHAR",
        "ALTER TABLE letterbox ADD COLUMN source VARCHAR DEFAULT 'upload'",
        "ALTER TABLE letterbox ADD COLUMN sender_phone VARCHAR",
        "ALTER TABLE letterbox ADD COLUMN assigned_to VARCHAR",
        "ALTER TABLE letterbox ADD COLUMN date_of_letter DATE",
        "ALTER TABLE letterbox ADD COLUMN notes TEXT",
        "ALTER TABLE letterbox ADD COLUMN linked_letterbox_id INTEGER",
        "ALTER TABLE letterbox ADD COLUMN is_deleted BOOLEAN DEFAULT false",
        "ALTER TABLE letterbox ADD COLUMN page_count INTEGER DEFAULT 1",
    ]
    with test_engine.begin() as conn:
        for stmt in alter_statements:
            try:
                conn.execute(text(stmt))
            except Exception:
                pass


def _seed_database():
    dbmod.engine = test_engine
    dbmod.SessionLocal = TestSession
    db_helpers.engine = test_engine
    main.engine = test_engine
    api_router.engine = test_engine

    Base.metadata.create_all(bind=test_engine)
    _ensure_letterbox_columns()

    with test_engine.begin() as conn:
        for table_name in ("letterbox", "users", "tenants", "token_blocklist"):
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
                INSERT INTO users (tenant_id, username, password_hash, role, constituency, house, is_active, phone, display_name)
                VALUES (1, 'mp_arun', :password_hash, 'mp', 'Bangalore North', 'Lok Sabha', 1, '919000000010', 'Arun PA')
                """
            ),
            {"password_hash": hash_password("ValidPass1!")},
        )
        conn.execute(
            text(
                """
                INSERT INTO letterbox (
                    id, tenant_id, direction, citizen_name, village, issue_summary,
                    urgency_level, status, created_at, category, diary_number, source,
                    is_deleted, page_count
                ) VALUES (
                    55, 1, 'inbox', 'Ramesh Kumar', 'Whitefield', 'Water issue letter',
                    'Normal', 'new', :now, 'Water & Sanitation', 'MP/2026/0055', 'upload',
                    false, 1
                )
                """
            ),
            {"now": now},
        )


def _auth_headers():
    token = jwt.encode(
        {"sub": "mp_arun", "tid": 1, "role": "mp", "exp": datetime.utcnow() + timedelta(hours=8)},
        TEST_JWT_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def test_save_to_outbox_creates_drafted_outbox_record():
    _seed_database()
    headers = _auth_headers()

    resp = client.post(
        "/api/letterbox/outbox",
        json={
            "recipient_name": "Secretary, BWSSB",
            "subject": "Re: Water issue in Whitefield",
            "content": "Please address the water disruption urgently.",
            "reference": "MP/2026/0055",
            "ministry": "BWSSB",
            "linked_letterbox_id": 55,
        },
        headers=headers,
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["status"] == "drafted"
    assert body["data"]["source"] == "drafter"

    with test_engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT direction, citizen_name, issue_summary, document_text, status, source, linked_letterbox_id
                FROM letterbox
                WHERE id = :id
                """
            ),
            {"id": body["data"]["id"]},
        ).mappings().first()

    assert row is not None
    assert row["direction"] == "outbox"
    assert row["citizen_name"] == "Secretary, BWSSB"
    assert row["issue_summary"] == "Re: Water issue in Whitefield"
    assert row["document_text"] == "Please address the water disruption urgently."
    assert row["status"] == "drafted"
    assert row["source"] == "drafter"
    assert row["linked_letterbox_id"] == 55


def test_manual_outbox_upload_defaults_to_sent(monkeypatch):
    _seed_database()
    headers = _auth_headers()

    monkeypatch.setattr(
        api_router,
        "extract_letter_fields",
        lambda *_args, **_kwargs: {
            "sender_name": "District Collector",
            "phone_number": "[NOT FOUND]",
            "village": "Bengaluru",
            "subject": "Forwarding action taken report",
            "priority": "Normal",
            "ocr_text": "Forwarding action taken report",
            "category": "Municipal Services",
        },
    )

    files = {"file": ("reply.jpg", io.BytesIO(b"fake-image-bytes"), "image/jpeg")}
    resp = client.post(
        "/api/letterbox/upload",
        data={"direction": "outbox"},
        files=files,
        headers=headers,
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["status"] == "sent"

    list_resp = client.get("/api/letterbox?direction=outbox&status=sent", headers=headers)
    assert list_resp.status_code == 200, list_resp.text
    assert any(item["id"] == body["data"]["id"] for item in list_resp.json()["items"])


def test_pa_pdf_whatsapp_intake_creates_letterbox_record(monkeypatch):
    _seed_database()

    sent_messages = []

    monkeypatch.setattr(main, "send_whatsapp_message", lambda phone, text, _pid=None: sent_messages.append((phone, text)))

    import modules.letterbox as letterbox_module

    monkeypatch.setattr(letterbox_module, "download_meta_media", lambda _media_id: (b"%PDF-1.4 fake pdf bytes", "application/pdf"))
    monkeypatch.setattr(letterbox_module, "count_pdf_pages", lambda _pdf_bytes: 3)
    monkeypatch.setattr(
        letterbox_module,
        "extract_letter_fields",
        lambda *_args, **_kwargs: {
            "direction": "outbox",
            "sender_name": "Chief Engineer, BWSSB",
            "phone_number": "[NOT FOUND]",
            "village": "Bengaluru",
            "subject": "Forwarding signed response on water issue",
            "priority": "Normal",
            "ocr_text": "Signed response on water issue",
            "category": "Water & Sanitation",
            "date_of_letter": "2026-05-02",
        },
    )

    main._process_pa_letter_pdf(
        sender="919000000010",
        media_id="wamedia-pdf-123",
        mime_type="application/pdf",
        receiver_number="+919000000001",
        caption="OUT signed response",
    )

    with test_engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT id, direction, image_mime, issue_summary, status, source, sender_phone, page_count, citizen_name
                FROM letterbox
                WHERE source = 'whatsapp' AND sender_phone = :phone
                ORDER BY id DESC
                LIMIT 1
                """
            ),
            {"phone": "919000000010"},
        ).mappings().first()

    assert row is not None
    assert row["direction"] == "outbox"
    assert row["image_mime"] == "application/pdf"
    assert row["issue_summary"] == "Forwarding signed response on water issue"
    assert row["status"] == "sent"
    assert row["source"] == "whatsapp"
    assert row["page_count"] == 3
    assert row["citizen_name"] == "Chief Engineer, BWSSB"
    assert sent_messages
    assert "Saved PDF to OUTBOX" in sent_messages[-1][1]

    pdf_resp = client.get(f"/api/letterbox/{row['id']}/image", headers=_auth_headers())
    assert pdf_resp.status_code == 200, pdf_resp.text
    assert pdf_resp.headers["content-type"].startswith("application/pdf")
