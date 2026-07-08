"""
Burst-scenario tests for the citizen WhatsApp text buffer.

Covers the debounced aggregation pipeline: fragments of one grievance sent in
rapid succession are combined and processed once; distinct grievances in one
burst become separate cases; staff messages and emergencies bypass the buffer;
buffering failures fall back to immediate processing; throttled ledger rows
are retried once the throttle window passes.
"""

import json
import os
import sys
from datetime import datetime, timedelta

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine

TEST_DB_URL = "sqlite:///./test_whatsapp_text_buffer.db"

os.environ["JWT_SECRET"] = "test-secret-key-32-characters-minimum-ok"
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["ENV"] = "test"
os.environ["OPENAI_API_KEY"] = "sk-test-fake-key-for-testing"
os.environ["META_APP_SECRET"] = "test-meta-app-secret"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@event.listens_for(Engine, "connect")
def _sqlite_register_pg_lock_functions(dbapi_connection, connection_record):
    try:
        dbapi_connection.create_function("pg_try_advisory_lock", 1, lambda _key: 1)
        dbapi_connection.create_function("pg_advisory_unlock", 1, lambda _key: 1)
        dbapi_connection.create_function("pg_try_advisory_xact_lock", 1, lambda _key: 1)
    except Exception:
        pass


import pytest  # noqa: E402

import main  # noqa: E402
import sansadx_backend.ai_engine as ai_engine  # noqa: E402
import sansadx_backend.db as dbmod  # noqa: E402
from sansadx_backend.db import Base  # noqa: E402

test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
dbmod.engine = test_engine
main.engine = test_engine


@pytest.fixture(autouse=True)
def _bind_test_engine(monkeypatch):
    # Other test modules reassign main.engine at import time; rebind (and
    # auto-restore) per test so this module is order-independent in full runs.
    monkeypatch.setattr(main, "engine", test_engine)
    monkeypatch.setattr(dbmod, "engine", test_engine)
    yield

Base.metadata.create_all(bind=test_engine)

with test_engine.begin() as _conn:
    _conn.execute(text("DROP TABLE IF EXISTS wa_text_buffer"))
    _conn.execute(text("""
        CREATE TABLE wa_text_buffer (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id        INTEGER NOT NULL,
            sender_phone     VARCHAR NOT NULL,
            receiver_number  VARCHAR NOT NULL DEFAULT '',
            messages         TEXT NOT NULL DEFAULT '[]',
            status           VARCHAR NOT NULL DEFAULT 'pending',
            first_message_at TIMESTAMP,
            last_message_at  TIMESTAMP,
            created_at       TIMESTAMP
        )
    """))


TENANT_ID = 1
RECEIVER = "+911234567890"


def _utcnow():
    return datetime.utcnow()


def _reset_state():
    with test_engine.begin() as conn:
        conn.execute(text("DELETE FROM wa_text_buffer"))
        conn.execute(text("DELETE FROM wa_inbound_messages"))
        conn.execute(text("DELETE FROM users"))
        conn.execute(text("DELETE FROM cases"))
        conn.execute(text("DELETE FROM tenants"))
        conn.execute(text("""
            INSERT INTO tenants (id, name, is_active) VALUES (1, 'Test MP', 1)
        """))
    with main._text_buffer_timer_lock:
        for timer in main._text_buffer_timers.values():
            timer.cancel()
        main._text_buffer_timers.clear()


def _ledger_row(sender: str, body: str, *, row_id: int = 1, msg_id: str = "wamid.test.1") -> dict:
    payload = {
        "entry_metadata": {"display_phone_number": RECEIVER},
        "message": {"id": msg_id, "type": "text", "from": sender, "text": {"body": body}},
    }
    return {
        "id": row_id,
        "meta_message_id": msg_id,
        "tenant_id": TENANT_ID,
        "sender_phone": sender,
        "receiver_number": RECEIVER,
        "message_type": "text",
        "raw_payload": json.dumps(payload),
        "case_id": None,
    }


def _buffer_rows():
    with test_engine.connect() as conn:
        return [
            dict(row)
            for row in conn.execute(
                text("SELECT * FROM wa_text_buffer ORDER BY id")
            ).mappings().all()
        ]


# ─────────────────────────────────────────────────────────────────────────────
# Buffering behaviour on dispatch
# ─────────────────────────────────────────────────────────────────────────────

def test_citizen_text_is_buffered_not_processed_immediately(monkeypatch):
    _reset_state()
    processed = []
    monkeypatch.setattr(main, "_process_incoming_message", lambda *a, **kw: processed.append((a, kw)))

    sender = "919888000001"
    main._dispatch_inbound_ledger_row(_ledger_row(sender, "Water problem sir"))

    assert processed == [], "Citizen text must be buffered, not classified immediately"
    rows = _buffer_rows()
    assert len(rows) == 1
    assert rows[0]["status"] == "pending"
    items = json.loads(rows[0]["messages"])
    assert [i["body"] for i in items] == ["Water problem sir"]
    with main._text_buffer_timer_lock:
        assert (sender, TENANT_ID) in main._text_buffer_timers, "Debounce timer must be armed"
    main._cancel_text_buffer_timer(sender, TENANT_ID)


def test_rapid_fragments_accumulate_in_one_buffer(monkeypatch):
    _reset_state()
    monkeypatch.setattr(main, "_process_incoming_message", lambda *a, **kw: None)

    sender = "919888000002"
    for idx, body in enumerate(["Water problem", "ward 5 tilakwadi", "3 din se pani nahi"]):
        main._dispatch_inbound_ledger_row(
            _ledger_row(sender, body, row_id=idx + 1, msg_id=f"wamid.frag.{idx}")
        )

    rows = _buffer_rows()
    assert len(rows) == 1, "All fragments must share one pending buffer"
    items = json.loads(rows[0]["messages"])
    assert [i["body"] for i in items] == ["Water problem", "ward 5 tilakwadi", "3 din se pani nahi"]
    main._cancel_text_buffer_timer(sender, TENANT_ID)


def test_staff_sender_bypasses_buffer(monkeypatch):
    _reset_state()
    with test_engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO users (tenant_id, username, password_hash, phone, is_active)
            VALUES (1, 'pa_test', 'x', '919888000003', 1)
        """))
    processed = []
    monkeypatch.setattr(main, "_process_incoming_message", lambda *a, **kw: processed.append(a))

    main._dispatch_inbound_ledger_row(_ledger_row("919888000003", "Pending water cases this week"))

    assert len(processed) == 1, "Staff queries must be processed immediately"
    assert _buffer_rows() == []


def test_emergency_text_bypasses_buffer(monkeypatch):
    _reset_state()
    processed = []
    monkeypatch.setattr(main, "_process_incoming_message", lambda *a, **kw: processed.append(a))

    main._dispatch_inbound_ledger_row(_ledger_row("919888000004", "Ghar me aag lag gayi hai, help!"))

    assert len(processed) == 1, "Emergency messages must not wait out the debounce window"
    assert _buffer_rows() == []


def test_buffer_failure_falls_back_to_immediate_processing(monkeypatch):
    _reset_state()
    processed = []
    monkeypatch.setattr(main, "_process_incoming_message", lambda *a, **kw: processed.append(a))
    monkeypatch.setattr(
        main, "_add_to_text_buffer",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("buffer table unavailable")),
    )

    main._dispatch_inbound_ledger_row(_ledger_row("919888000005", "Road repair needed in my area"))

    assert len(processed) == 1, "Buffering failure must never drop a citizen message"


# ─────────────────────────────────────────────────────────────────────────────
# Flush behaviour
# ─────────────────────────────────────────────────────────────────────────────

def test_flush_combines_fragments_into_single_processing_call(monkeypatch):
    _reset_state()
    processed = []
    monkeypatch.setattr(
        main, "_process_incoming_message",
        lambda sender, body, *a, **kw: processed.append((sender, body, kw)),
    )
    monkeypatch.setattr(main, "segment_citizen_messages", lambda bodies, **kw: ["\n".join(bodies)])

    sender = "919888000006"
    for idx, body in enumerate(["Water problem", "ward 5 tilakwadi"]):
        main._add_to_text_buffer(TENANT_ID, sender, RECEIVER, body, f"wamid.f{idx}", idx + 1)

    main._flush_text_buffer(sender, TENANT_ID, RECEIVER)

    assert len(processed) == 1, "One fragmented grievance must produce exactly one processing run"
    assert processed[0][1] == "Water problem\nward 5 tilakwadi"
    assert processed[0][2].get("inbound_ledger_id") == 1
    rows = _buffer_rows()
    assert rows[0]["status"] == "done"


def test_flush_splits_distinct_queries_into_separate_processing_calls(monkeypatch):
    _reset_state()
    processed = []
    monkeypatch.setattr(
        main, "_process_incoming_message",
        lambda sender, body, *a, **kw: processed.append(body),
    )
    monkeypatch.setattr(
        main, "segment_citizen_messages",
        lambda bodies, **kw: ["Water problem in ward 5", "Road broken near school"],
    )

    sender = "919888000007"
    main._add_to_text_buffer(TENANT_ID, sender, RECEIVER, "Water problem in ward 5", "wamid.a", 1)
    main._add_to_text_buffer(TENANT_ID, sender, RECEIVER, "Road broken near school", "wamid.b", 2)

    main._flush_text_buffer(sender, TENANT_ID, RECEIVER)

    assert processed == ["Water problem in ward 5", "Road broken near school"]
    assert _buffer_rows()[0]["status"] == "done"


def test_flush_single_message_skips_segmentation(monkeypatch):
    _reset_state()
    processed = []
    monkeypatch.setattr(main, "_process_incoming_message", lambda s, body, *a, **kw: processed.append(body))
    monkeypatch.setattr(
        main, "segment_citizen_messages",
        lambda bodies, **kw: (_ for _ in ()).throw(AssertionError("segmentation must not run for one message")),
    )

    sender = "919888000008"
    main._add_to_text_buffer(TENANT_ID, sender, RECEIVER, "Single complete complaint", "wamid.s", 1)
    main._flush_text_buffer(sender, TENANT_ID, RECEIVER)

    assert processed == ["Single complete complaint"]


def test_flush_marks_buffer_failed_when_processing_raises(monkeypatch):
    _reset_state()
    monkeypatch.setattr(
        main, "_process_incoming_message",
        lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("AI down")),
    )

    sender = "919888000009"
    main._add_to_text_buffer(TENANT_ID, sender, RECEIVER, "Some complaint", "wamid.x", 1)
    main._flush_text_buffer(sender, TENANT_ID, RECEIVER)

    rows = _buffer_rows()
    assert rows[0]["status"] == "failed", "Failed flush must stay visible for the sweeper"


def test_flush_is_idempotent_when_buffer_already_claimed(monkeypatch):
    _reset_state()
    processed = []
    monkeypatch.setattr(main, "_process_incoming_message", lambda *a, **kw: processed.append(a))

    sender = "919888000010"
    main._add_to_text_buffer(TENANT_ID, sender, RECEIVER, "Complaint", "wamid.y", 1)
    main._flush_text_buffer(sender, TENANT_ID, RECEIVER)
    main._flush_text_buffer(sender, TENANT_ID, RECEIVER)  # second call must no-op

    assert len(processed) == 1


def test_sweep_flushes_stale_pending_buffer(monkeypatch):
    _reset_state()
    processed = []
    monkeypatch.setattr(main, "_process_incoming_message", lambda s, body, *a, **kw: processed.append(body))

    sender = "919888000011"
    stale = _utcnow() - timedelta(seconds=main._TEXT_BUFFER_FLUSH_SECONDS + 60)
    with test_engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO wa_text_buffer
                    (tenant_id, sender_phone, receiver_number, messages, status,
                     first_message_at, last_message_at, created_at)
                VALUES (:tid, :phone, :recv, :msgs, 'pending', :ts, :ts, :ts)
            """),
            {
                "tid": TENANT_ID, "phone": sender, "recv": RECEIVER,
                "msgs": json.dumps([{"body": "Orphaned by deploy", "msg_id": "wamid.z", "inbound_ledger_id": 1}]),
                "ts": stale,
            },
        )

    flushed = main._sweep_stale_text_buffers()

    assert flushed == 1
    assert processed == ["Orphaned by deploy"]
    assert _buffer_rows()[0]["status"] == "done"


# ─────────────────────────────────────────────────────────────────────────────
# Throttled ledger rows are retried after the window
# ─────────────────────────────────────────────────────────────────────────────

def test_throttled_ledger_rows_are_retried_after_window(monkeypatch):
    _reset_state()
    retried = []
    monkeypatch.setattr(main, "_process_inbound_ledger_row", lambda row_id: retried.append(row_id) or True)

    old = _utcnow() - timedelta(seconds=main._INBOUND_SENDER_THROTTLE_WINDOW_SECONDS + 60)
    ancient = _utcnow() - timedelta(hours=main._INBOUND_THROTTLED_RETRY_MAX_AGE_HOURS + 1)
    with test_engine.begin() as conn:
        for row_id, ts in ((101, old), (102, ancient)):
            conn.execute(
                text("""
                    INSERT INTO wa_inbound_messages
                        (id, meta_message_id, tenant_id, sender_phone, receiver_number,
                         message_type, status, delivery_attempts, retry_count,
                         raw_payload, created_at, updated_at, last_received_at)
                    VALUES (:id, :mid, 1, '919888000012', :recv, 'text', 'throttled',
                            1, 0, '{}', :ts, :ts, :ts)
                """),
                {"id": row_id, "mid": f"wamid.throttled.{row_id}", "recv": RECEIVER, "ts": ts},
            )

    rescued = main._sweep_pending_inbound_ledger_rows()

    assert 101 in retried, "Throttled row past the window must be retried"
    assert 102 not in retried, "Rows older than the retry cap must not be replayed"
    assert rescued >= 1


# ─────────────────────────────────────────────────────────────────────────────
# Segmentation fallback + tiered similarity threshold
# ─────────────────────────────────────────────────────────────────────────────

def test_segmentation_returns_single_combined_without_api_client(monkeypatch):
    monkeypatch.setattr(ai_engine, "get_client", lambda: None)
    result = ai_engine.segment_citizen_messages(["Water problem", "ward 5"])
    assert result == ["Water problem\nward 5"]


def test_segmentation_single_message_never_calls_api(monkeypatch):
    monkeypatch.setattr(
        ai_engine, "get_client",
        lambda: (_ for _ in ()).throw(AssertionError("API client must not be created")),
    )
    assert ai_engine.segment_citizen_messages(["One message"]) == ["One message"]


def test_segmentation_empty_input():
    assert ai_engine.segment_citizen_messages([]) == []
    assert ai_engine.segment_citizen_messages(["", "  "]) == []


def test_effective_similarity_threshold_tiers():
    now = _utcnow()
    recent = {"updated_at": now - timedelta(minutes=5), "created_at": now - timedelta(minutes=5)}
    medium = {"updated_at": now - timedelta(minutes=90), "created_at": now - timedelta(minutes=90)}
    old = {"updated_at": now - timedelta(hours=5), "created_at": now - timedelta(hours=5)}

    assert main._effective_similarity_threshold(recent) == main._FOLLOWUP_SIMILARITY_SHORT_WINDOW
    assert main._effective_similarity_threshold(medium) == main._FOLLOWUP_SIMILARITY_MEDIUM_WINDOW
    assert main._effective_similarity_threshold(old) == main._CONTACT_BUFFER_SIMILARITY
    assert main._effective_similarity_threshold(None) == main._CONTACT_BUFFER_SIMILARITY
