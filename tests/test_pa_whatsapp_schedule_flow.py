import os
import re
import sys
from datetime import datetime

from sqlalchemy import create_engine, text, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
TEST_DB_URL = "sqlite:///./test_pa_schedule_flow.db"

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


test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(bind=test_engine)


@event.listens_for(Engine, "connect")
def _sqlite_register_helpers(dbapi_connection, connection_record):
    try:
        dbapi_connection.create_function("pg_try_advisory_lock", 1, lambda _key: 1)
        dbapi_connection.create_function("pg_advisory_unlock", 1, lambda _key: 1)
        dbapi_connection.create_function("pg_try_advisory_xact_lock", 1, lambda _key: 1)
        dbapi_connection.create_function(
            "regexp_replace",
            4,
            lambda value, pattern, repl, flags=None: re.sub(pattern, repl, value or ""),
        )
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
        conn.execute(text("DELETE FROM dashboard_engagements"))
        conn.execute(text("DELETE FROM users"))
        conn.execute(text("DELETE FROM tenants"))

        conn.execute(text("""
            INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active, created_at, seat_type, account_stage)
            VALUES (1, 'Test MP', 'Belagavi', '+919000000001', 'Pro', 1, :now, 'mp', 'elected')
        """), {"now": datetime.utcnow()})

        conn.execute(text("""
            INSERT INTO users (
                tenant_id, username, password_hash, role, constituency, house, phone, display_name, failed_login_attempts
            )
            VALUES (
                1, 'pa_user', :ph, 'user', 'Belagavi', 'Lok Sabha', '919876543210', 'PA Desk', 0
            )
        """), {"ph": hash_password("ValidPass1!")})


def test_staff_whatsapp_schedule_message_creates_dashboard_engagement(monkeypatch):
    _seed_database()
    sent_messages = []

    monkeypatch.setattr(main, "parse_staff_schedule_message", lambda _message: {
        "entry_type": "schedule",
        "title": "Meeting with Chief Minister",
        "notes": "Bring irrigation brief",
        "location": "Vidhana Soudha",
        "scheduled_for": "2026-06-10",
        "start_time": "17:00",
        "end_time": None,
        "is_all_day": False,
        "calendar_url": None,
        "confidence": "high",
    })
    monkeypatch.setattr(main, "_get_registered_staff_sender", lambda _sender, _tenant_id: {
        "id": 1,
        "username": "pa_user",
        "display_name": "PA Desk",
        "phone": "919876543210",
    })
    monkeypatch.setattr(main, "send_whatsapp_message", lambda to, body, phone_id=None: sent_messages.append((to, body, phone_id)) or True)
    monkeypatch.setattr(main, "parse_query", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("case query fallback should not run")))

    main._process_incoming_message(
        sender="919876543210",
        message_body="Meeting with Chief Minister on Wednesday at 5 PM",
        receiver_number="+919000000001",
        msg_id="wamid.schedule.1",
    )

    with test_engine.connect() as conn:
        saved = conn.execute(text("SELECT entry_type, title, location, created_by FROM dashboard_engagements")).fetchone()

    assert saved is not None
    assert saved[0] == "schedule"
    assert saved[1] == "Meeting with Chief Minister"
    assert saved[2] == "Vidhana Soudha"
    assert saved[3] == "pa_user"
    assert sent_messages
    assert "Saved to schedule" in sent_messages[0][1]
