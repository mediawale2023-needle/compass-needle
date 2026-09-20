"""Attention Queue ordering regression tests.

The Operations Dashboard Attention Queue must always lead with the case or
thread holding the most recently received *inbound citizen* message. It must
not be ordered by bucket priority, status, creation time or case id — the
previous implementation sorted by (bucket, created_at ASC), which put the
oldest case in the highest-priority bucket on top.
"""

import json
import os
import sys
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
TEST_DB_URL = "sqlite:///./test_dashboard_attention_queue.db"

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

# Anchored to the real clock: _dashboard_time_ago compares against utcnow(),
# so a hardcoded date would make the rendered "age" meaningless.
NOW = datetime.utcnow().replace(microsecond=0)


@event.listens_for(Engine, "connect")
def _sqlite_register_pg_lock_functions(dbapi_connection, connection_record):
    try:
        dbapi_connection.create_function("pg_try_advisory_lock", 1, lambda _key: 1)
        dbapi_connection.create_function("pg_advisory_unlock", 1, lambda _key: 1)
        dbapi_connection.create_function("pg_try_advisory_xact_lock", 1, lambda _key: 1)
    except Exception:
        pass


def _reset_database():
    FAKE_SYNC_MAP.clear()
    dbmod.engine = test_engine
    dbmod.SessionLocal = TestSession
    db_helpers.engine = test_engine
    main.engine = test_engine
    api_router.engine = test_engine
    api_router.JWT_SECRET = TEST_JWT_SECRET

    Base.metadata.create_all(bind=test_engine)

    with test_engine.begin() as conn:
        conn.execute(text("DELETE FROM token_blocklist"))
        conn.execute(text("DELETE FROM wa_inbound_messages"))
        conn.execute(text("DELETE FROM cases"))
        conn.execute(text("DELETE FROM users"))
        conn.execute(text("DELETE FROM tenants"))

        for tid, name, number in (
            (1, "Test MP", "+919000000001"),
            (2, "Other MP", "+919000000002"),
        ):
            conn.execute(
                text(
                    "INSERT INTO tenants (id, name, constituency, whatsapp_number, "
                    "subscription_plan, is_active, created_at, seat_type, account_stage) "
                    "VALUES (:tid, :name, 'Belagavi', :number, 'Pro', 1, :now, 'mp', 'elected')"
                ),
                {"tid": tid, "name": name, "number": number, "now": NOW},
            )

        conn.execute(
            text(
                "INSERT INTO users (tenant_id, username, password_hash, role, constituency, "
                "house, failed_login_attempts) "
                "VALUES (1, 'mp_test', :ph, 'mp', 'Belagavi', 'Lok Sabha', 0)"
            ),
            {"ph": hash_password("ValidPass1!")},
        )
        conn.execute(
            text(
                "INSERT INTO users (tenant_id, username, password_hash, role, constituency, "
                "house, failed_login_attempts) "
                "VALUES (2, 'mp_other', :ph, 'mp', 'Hubli', 'Lok Sabha', 0)"
            ),
            {"ph": hash_password("ValidPass1!")},
        )


def _add_case(case_id, tenant_id=1, created_at=None, status="new", phone="+919650787758",
              message="Water supply problem", thread_id=None):
    meta = {}
    if thread_id:
        meta["contact_thread_id"] = thread_id
    with test_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO cases (id, tenant_id, user_phone, category, raw_message, status, "
                "case_metadata, is_critical, is_deleted, created_at, updated_at) "
                "VALUES (:id, :tid, :phone, 'Uncategorised', :msg, :status, :meta, 0, 0, :created, :created)"
            ),
            {
                "id": case_id, "tid": tenant_id, "phone": phone, "msg": message,
                "status": status, "meta": json.dumps(meta) if meta else None,
                "created": created_at or NOW,
            },
        )
    return case_id


def _add_inbound(case_id, received_at, tenant_id=1, meta_id=None):
    """Insert one inbound citizen ledger row linked to a case."""
    with test_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO wa_inbound_messages (meta_message_id, tenant_id, sender_phone, "
                "receiver_number, message_type, status, delivery_attempts, retry_count, "
                "case_id, raw_payload, created_at, updated_at, last_received_at) "
                "VALUES (:mid, :tid, '+919650787758', '+919000000001', 'text', 'processed', "
                "1, 0, :cid, '{}', :ts, :ts, :ts)"
            ),
            {
                "mid": meta_id or f"wamid.test.{case_id}.{received_at.isoformat()}",
                "tid": tenant_id, "cid": case_id, "ts": received_at,
            },
        )


# _dashboard_govt_sync_map uses Postgres-only "SELECT DISTINCT ON", which
# sqlite cannot parse, so the overview endpoint is untestable on sqlite without
# this shim. Government sync state is orthogonal to ordering — it only selects
# which attention bucket a row lands in, and ordering must ignore buckets
# entirely. Tests that care about bucket priority set FAKE_SYNC_MAP explicitly.
FAKE_SYNC_MAP: dict = {}


def _stub_govt_sync_map(tenant_id, case_ids):
    return {cid: FAKE_SYNC_MAP[cid] for cid in case_ids if cid in FAKE_SYNC_MAP}


api_router._dashboard_govt_sync_map = _stub_govt_sync_map

_reset_database()
client = TestClient(app, raise_server_exceptions=False)


def _headers(username="mp_test"):
    login = client.post("/api/auth/login", json={"username": username, "password": "ValidPass1!"})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['token']}"}


def _queue_ids(username="mp_test"):
    response = client.get("/api/dashboard/overview", headers=_headers(username))
    assert response.status_code == 200
    return [row["id"] for row in response.json()["attention_queue"]]


def test_newer_citizen_message_ranks_higher():
    """The documented A/B/C example, with bucket priority deliberately inverted.

    Case A is the oldest and sits in the *lowest* priority bucket, yet holds
    the newest citizen message, so it must still lead. This is the exact case
    the previous (bucket, created_at ASC) sort got wrong.
    """
    _reset_database()
    _add_case(101, created_at=NOW - timedelta(days=10), status="new")
    _add_case(102, created_at=NOW - timedelta(hours=2), status="pending_review")
    _add_case(103, created_at=NOW - timedelta(days=1), status="pending_review")

    _add_inbound(101, NOW - timedelta(minutes=20))   # today 15:40
    _add_inbound(102, NOW - timedelta(minutes=30))   # today 15:30
    _add_inbound(103, NOW - timedelta(hours=2))      # today 14:00

    assert _queue_ids() == [101, 102, 103]


def test_old_case_with_new_message_jumps_above_recent_case():
    """A ten-day-old case receiving a fresh WhatsApp message outranks a case
    created minutes ago — without creating a duplicate case row."""
    _reset_database()
    old_case = _add_case(201, created_at=NOW - timedelta(days=10))
    fresh_case = _add_case(202, created_at=NOW - timedelta(minutes=5))

    _add_inbound(old_case, NOW - timedelta(days=10))
    _add_inbound(fresh_case, NOW - timedelta(minutes=5))
    assert _queue_ids() == [fresh_case, old_case]

    # The citizen follows up on the old case. No new case row is created.
    _add_inbound(old_case, NOW - timedelta(seconds=30))

    with test_engine.begin() as conn:
        case_count = conn.execute(text("SELECT COUNT(*) FROM cases WHERE tenant_id = 1")).scalar()
    assert case_count == 2

    assert _queue_ids() == [old_case, fresh_case]


def test_thread_uses_newest_inbound_across_all_members():
    """For a multi-case thread the ordering key is the newest inbound message
    on ANY member, not just the anchor."""
    _reset_database()
    _add_case(301, created_at=NOW - timedelta(days=5), thread_id="ct-1-9650787758-301")
    _add_case(302, created_at=NOW - timedelta(days=4), thread_id="ct-1-9650787758-301")
    _add_case(303, created_at=NOW - timedelta(hours=1), phone="+919888888888")

    _add_inbound(303, NOW - timedelta(minutes=45))
    # Oldest member of the thread carries the newest message.
    _add_inbound(301, NOW - timedelta(minutes=2))
    _add_inbound(302, NOW - timedelta(days=4))

    queue = _queue_ids()
    assert queue[0] in (301, 302), f"thread should lead, got {queue}"
    assert 303 in queue and queue.index(303) > 0


def test_staff_and_outbound_activity_do_not_outrank_citizen_inbound():
    """Staff edits (cases.updated_at) and outbound replies must not reorder."""
    _reset_database()
    quiet_case = _add_case(401, created_at=NOW - timedelta(days=3))
    active_case = _add_case(402, created_at=NOW - timedelta(days=3))

    _add_inbound(quiet_case, NOW - timedelta(hours=6))
    _add_inbound(active_case, NOW - timedelta(minutes=10))
    assert _queue_ids() == [active_case, quiet_case]

    # Staff touches the quiet case long after the citizen last wrote, and an
    # outbound reply goes out on it. Neither is citizen inbound activity.
    with test_engine.begin() as conn:
        conn.execute(
            text("UPDATE cases SET updated_at = :now, notes_for_staff = 'looked at' WHERE id = :cid"),
            {"now": NOW, "cid": quiet_case},
        )
        conn.execute(
            text(
                "INSERT INTO wa_outbound_messages (tenant_id, case_id, to_number, phone_number_id, "
                "message_body, status, attempt_count, created_at, updated_at, sent_at) "
                "VALUES (1, :cid, '+919650787758', '1022081830997226', 'reply', 'sent', 1, :now, :now, :now)"
            ),
            {"cid": quiet_case, "now": NOW},
        )

    assert _queue_ids() == [active_case, quiet_case]


def test_high_priority_bucket_does_not_outrank_newer_citizen_message():
    """A sync-issue row (highest-but-one bucket) with an old message stays
    below a plain ready-to-file row holding a newer message."""
    _reset_database()
    sync_issue_case = _add_case(451, created_at=NOW - timedelta(days=2))
    plain_case = _add_case(452, created_at=NOW - timedelta(days=2))
    FAKE_SYNC_MAP[sync_issue_case] = {"govt_sync_state": "failed"}

    _add_inbound(sync_issue_case, NOW - timedelta(hours=8))
    _add_inbound(plain_case, NOW - timedelta(minutes=3))

    response = client.get("/api/dashboard/overview", headers=_headers())
    assert response.status_code == 200
    rows = response.json()["attention_queue"]

    assert [r["id"] for r in rows] == [plain_case, sync_issue_case]
    # The bucket classification itself is unchanged — only ordering is.
    assert {r["id"]: r["bucket"] for r in rows} == {
        plain_case: "ready_to_file",
        sync_issue_case: "sync_issues",
    }


def test_tenant_isolation_is_preserved():
    """Another tenant's newer inbound messages never leak into this queue."""
    _reset_database()
    _add_case(501, tenant_id=1, created_at=NOW - timedelta(days=2))
    _add_case(502, tenant_id=2, created_at=NOW - timedelta(days=2))

    _add_inbound(501, NOW - timedelta(hours=3), tenant_id=1)
    # Tenant 2 has strictly newer activity.
    _add_inbound(502, NOW - timedelta(minutes=1), tenant_id=2)

    assert _queue_ids("mp_test") == [501]
    assert _queue_ids("mp_other") == [502]


def test_tenant_scoped_inbound_row_does_not_bleed_across_tenants():
    """A ledger row belonging to another tenant must not lift a case, even if
    it references that case id — the lookup is tenant-scoped in SQL."""
    _reset_database()
    _add_case(601, tenant_id=1, created_at=NOW - timedelta(days=9))
    _add_case(602, tenant_id=1, created_at=NOW - timedelta(days=1))

    _add_inbound(601, NOW - timedelta(days=9), tenant_id=1)
    _add_inbound(602, NOW - timedelta(hours=1), tenant_id=1)
    # Mislabelled row: newest timestamp, but scoped to tenant 2.
    _add_inbound(601, NOW, tenant_id=2, meta_id="wamid.crosstenant.601")

    assert _queue_ids() == [602, 601]


def test_case_without_inbound_falls_back_to_created_at():
    """Legacy/imported cases with no ledger rows still appear, ordered by
    creation time against cases that do have inbound messages."""
    _reset_database()
    _add_case(701, created_at=NOW - timedelta(days=4))            # no inbound
    _add_case(702, created_at=NOW - timedelta(minutes=15))        # no inbound
    _add_case(703, created_at=NOW - timedelta(days=30))           # inbound, newest

    _add_inbound(703, NOW - timedelta(minutes=1))

    queue = _queue_ids()
    assert queue == [703, 702, 701], f"got {queue}"
    assert set(queue) == {701, 702, 703}, "legacy cases must not be dropped"


def test_equal_timestamps_order_deterministically():
    """Identical timestamps tie-break on case id descending, and repeated
    calls return the same order."""
    _reset_database()
    same_moment = NOW - timedelta(minutes=5)
    for case_id in (801, 802, 803):
        _add_case(case_id, created_at=NOW - timedelta(days=1))
        _add_inbound(case_id, same_moment)

    first = _queue_ids()
    assert first == [803, 802, 801], f"got {first}"
    assert first == _queue_ids() == _queue_ids()


def test_queue_reports_latest_citizen_message_timestamp():
    """The row exposes the timestamp it was ordered by, and the displayed age
    reflects latest citizen activity rather than original case age."""
    _reset_database()
    _add_case(901, created_at=NOW - timedelta(days=10))
    _add_inbound(901, NOW - timedelta(minutes=5))

    response = client.get("/api/dashboard/overview", headers=_headers())
    assert response.status_code == 200
    row = response.json()["attention_queue"][0]

    assert row["id"] == 901
    assert row["has_inbound_citizen_message"] is True

    reported = api_router._naive_utc(row["latest_citizen_message_at"])
    assert reported is not None
    assert abs((reported - (NOW - timedelta(minutes=5))).total_seconds()) < 2

    # Age must reflect the 5-minute-old message, not the 10-day case age.
    assert row["recency"].endswith("m"), f"recency showed case age: {row['recency']}"
    assert "d" not in row["recency"]
