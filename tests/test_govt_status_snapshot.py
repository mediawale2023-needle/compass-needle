import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy import create_engine, text

TEST_DB_URL = "sqlite:///./test_govt_status_snapshot.db"
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["ENV"] = "test"
os.environ["JWT_SECRET"] = "test-secret-key-32-characters-minimum-ok"
os.environ["OPENAI_API_KEY"] = "sk-test-fake-key-for-testing"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import api_router
import core.db_helpers as db_helpers
import sansadx_backend.db as dbmod
from modules.govt_sync.adapters.base import StatusResult
from modules.govt_sync.status_snapshot import (
    AVAILABILITY_EXPLICITLY_EMPTY,
    AVAILABILITY_PRESENT,
    AVAILABILITY_REDACTED,
    AVAILABILITY_UNAVAILABLE,
    GovtStatusField,
    GovtStatusSnapshotResult,
    diff_snapshot_fields,
    persist_status_snapshot,
    status_result_to_snapshot_result,
)
from sansadx_backend.db import Base

test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _bind_engine():
    dbmod.engine = test_engine
    db_helpers.engine = test_engine
    api_router.engine = test_engine


def _reset_db():
    _bind_engine()
    Base.metadata.create_all(bind=test_engine)
    with test_engine.begin() as conn:
        for table in (
            "govt_submission_log",
            "govt_status_snapshot_events",
            "govt_status_snapshot_fields",
            "govt_status_snapshots",
            "cases",
            "govt_portals",
            "users",
            "tenant_profiles",
            "tenants",
        ):
            conn.execute(text(f"DELETE FROM {table}"))  # nosec B608
        conn.execute(text(
            "INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active, created_at) "
            "VALUES (1, 'Snapshot Tenant', 'Test Constituency', '+919000000001', 'Pro', 1, :now)"
        ), {"now": _utcnow()})
        conn.execute(text(
            "INSERT INTO govt_portals (id, state, portal_name, portal_type, base_url, status_check_url, "
            "status_check_mode, department_taxonomy, field_schema, otp_bound, active, is_primary, "
            "verification_status, live_session_supported, status_check_adapter) "
            "VALUES (10, 'TestState', 'Snapshot Portal', 'state_branded', 'https://example.test', "
            "'https://example.test/status', 'login_required', :taxonomy, :schema, 0, 1, 1, "
            "'confirmed', 0, 'manual')"
        ), {"taxonomy": json.dumps({}), "schema": json.dumps({})})
        conn.execute(text(
            "INSERT INTO cases (id, tenant_id, user_phone, raw_message, category, status, created_at, "
            "govt_portal_id, govt_status, govt_reference_number, is_deleted) VALUES "
            "(40, 1, '+919111111140', 'Test grievance', 'Infrastructure & Utilities', 'in_progress', :now, "
            "10, 'submitted', 'REF/TEST/0001', 0)"
        ), {"now": _utcnow()})


def _snapshot_count() -> int:
    with test_engine.connect() as conn:
        return conn.execute(text("SELECT COUNT(*) FROM govt_status_snapshots")).scalar()


def _event_rows():
    with test_engine.connect() as conn:
        return [dict(row) for row in conn.execute(text(
            "SELECT field_key, event_type, old_value_text, new_value_text, old_value_json, new_value_json "
            "FROM govt_status_snapshot_events ORDER BY id"
        )).mappings().all()]


def _field_rows(snapshot_id: int):
    with test_engine.connect() as conn:
        return [dict(row) for row in conn.execute(text(
            "SELECT field_key, value_text, availability FROM govt_status_snapshot_fields "
            "WHERE snapshot_id = :snapshot_id ORDER BY id"
        ), {"snapshot_id": snapshot_id}).mappings().all()]


def test_status_result_maps_known_portal_detail_fields():
    result = StatusResult(
        status="under_review",
        raw_portal_status="Registered & Sent for Scrutiny",
        portal_detail={
            "department_name": "Food Department",
            "pendency_details": "Officer A",
            "action_taken_report": "",
            "documents": [{"name": "ATR.pdf"}],
        },
    )

    snapshot = status_result_to_snapshot_result(result)
    by_key = {field.field_key: field for field in snapshot.fields}

    assert snapshot.normalized_status == "under_review"
    assert by_key["status"].value_text == "under_review"
    assert by_key["department"].value_text == "Food Department"
    assert by_key["current_position"].value_text == "Officer A"
    assert by_key["action_taken_report"].availability == AVAILABILITY_EXPLICITLY_EMPTY
    assert by_key["document"].value_json == [{"name": "ATR.pdf"}]


def test_diff_only_compares_present_and_explicitly_empty_values():
    previous = [
        GovtStatusField("officer", "Officer", value_text="Officer A", availability=AVAILABILITY_PRESENT),
        GovtStatusField("department", "Department", value_text="Dept A", availability=AVAILABILITY_PRESENT),
        GovtStatusField("reply", "Reply", value_text="", availability=AVAILABILITY_EXPLICITLY_EMPTY),
    ]
    current = [
        GovtStatusField("officer", "Officer", availability=AVAILABILITY_UNAVAILABLE),
        GovtStatusField("department", "Department", value_text="Dept B", availability=AVAILABILITY_PRESENT),
        GovtStatusField("reply", "Reply", value_text="Received", availability=AVAILABILITY_PRESENT),
    ]

    changes = diff_snapshot_fields(previous, current)

    assert [(c.field_key, c.event_type) for c in changes] == [
        ("department", "department_changed"),
        ("reply", "reply_added"),
    ]


def test_partial_snapshot_persists_partial_and_unavailable_fields():
    _reset_db()
    snapshot_id = persist_status_snapshot(
        tenant_id=1,
        case_id=40,
        portal_id=10,
        reference_number="REF/TEST/0001",
        adapter_key="test",
        result=GovtStatusSnapshotResult(
            normalized_status="under_review",
            partial=True,
            fields=[
                GovtStatusField("status", "Status", value_text="under_review"),
                GovtStatusField("officer", "Officer", availability=AVAILABILITY_UNAVAILABLE),
            ],
        ),
    )

    with test_engine.connect() as conn:
        snapshot_status = conn.execute(text(
            "SELECT snapshot_status FROM govt_status_snapshots WHERE id = :id"
        ), {"id": snapshot_id}).scalar()

    assert snapshot_status == "partial"
    fields = _field_rows(snapshot_id)
    officer = next(field for field in fields if field["field_key"] == "officer")
    assert officer["availability"] == AVAILABILITY_UNAVAILABLE
    assert officer["availability"] != AVAILABILITY_EXPLICITLY_EMPTY


def test_redacted_fields_are_not_comparable_changes():
    changes = diff_snapshot_fields(
        [GovtStatusField("reply", "Reply", value_text="Sensitive", availability=AVAILABILITY_PRESENT)],
        [GovtStatusField("reply", "Reply", availability=AVAILABILITY_REDACTED)],
    )
    assert changes == []


def test_present_to_explicitly_empty_generates_change():
    changes = diff_snapshot_fields(
        [GovtStatusField("department", "Department", value_text="Revenue", availability=AVAILABILITY_PRESENT)],
        [GovtStatusField("department", "Department", availability=AVAILABILITY_EXPLICITLY_EMPTY)],
    )
    assert [(c.field_key, c.event_type, c.old_value_text, c.new_value_text) for c in changes] == [
        ("department", "department_changed", "Revenue", None)
    ]


def test_explicitly_empty_to_present_generates_change():
    changes = diff_snapshot_fields(
        [GovtStatusField("department", "Department", availability=AVAILABILITY_EXPLICITLY_EMPTY)],
        [GovtStatusField("department", "Department", value_text="Revenue", availability=AVAILABILITY_PRESENT)],
    )
    assert [(c.field_key, c.event_type, c.old_value_text, c.new_value_text) for c in changes] == [
        ("department", "department_changed", None, "Revenue")
    ]


def test_explicitly_empty_to_explicitly_empty_is_not_a_change():
    changes = diff_snapshot_fields(
        [GovtStatusField("department", "Department", availability=AVAILABILITY_EXPLICITLY_EMPTY)],
        [GovtStatusField("department", "Department", availability=AVAILABILITY_EXPLICITLY_EMPTY)],
    )
    assert changes == []


def test_officer_change_generates_officer_event():
    changes = diff_snapshot_fields(
        [GovtStatusField("officer", "Officer", value_text="Officer A")],
        [GovtStatusField("officer", "Officer", value_text="Officer B")],
    )
    assert len(changes) == 1
    assert changes[0].field_key == "officer"
    assert changes[0].event_type == "officer_changed"
    assert changes[0].old_value_json == {"name": "Officer A", "designation": None, "changed_parts": ["name"]}
    assert changes[0].new_value_json == {"name": "Officer B", "designation": None, "changed_parts": ["name"]}


def test_officer_designation_only_change_generates_one_officer_event():
    changes = diff_snapshot_fields(
        [
            GovtStatusField("officer", "Officer", value_text="Officer A"),
            GovtStatusField("designation", "Designation", value_text="Assistant"),
        ],
        [
            GovtStatusField("officer", "Officer", value_text="Officer A"),
            GovtStatusField("designation", "Designation", value_text="Deputy"),
        ],
    )
    assert len(changes) == 1
    assert changes[0].event_type == "officer_changed"
    assert changes[0].new_value_json["changed_parts"] == ["designation"]


def test_officer_name_and_designation_change_generates_one_officer_event():
    changes = diff_snapshot_fields(
        [
            GovtStatusField("officer", "Officer", value_text="Officer A"),
            GovtStatusField("designation", "Designation", value_text="Assistant"),
        ],
        [
            GovtStatusField("officer", "Officer", value_text="Officer B"),
            GovtStatusField("designation", "Designation", value_text="Deputy"),
        ],
    )
    assert len(changes) == 1
    assert changes[0].event_type == "officer_changed"
    assert changes[0].new_value_json["changed_parts"] == ["name", "designation"]


def test_officer_to_unavailable_is_not_a_change():
    changes = diff_snapshot_fields(
        [GovtStatusField("officer", "Officer", value_text="Officer A")],
        [GovtStatusField("officer", "Officer", availability=AVAILABILITY_UNAVAILABLE)],
    )
    assert changes == []


def test_status_change_generates_status_event():
    changes = diff_snapshot_fields(
        [GovtStatusField("status", "Status", value_text="submitted")],
        [GovtStatusField("status", "Status", value_text="under_review")],
    )
    assert [(c.field_key, c.event_type, c.old_value_text, c.new_value_text) for c in changes] == [
        ("status", "status_changed", "submitted", "under_review")
    ]


def test_first_snapshot_persists_fields_and_no_events():
    _reset_db()
    snapshot_id = persist_status_snapshot(
        tenant_id=1,
        case_id=40,
        portal_id=10,
        reference_number="REF/TEST/0001",
        adapter_key="test",
        result=GovtStatusSnapshotResult(
            normalized_status="submitted",
            fields=[
                GovtStatusField("status", "Status", value_text="submitted"),
                GovtStatusField("department", "Department", value_text="Food Department"),
            ],
        ),
    )

    assert snapshot_id is not None
    assert len(_field_rows(snapshot_id)) == 2
    assert _event_rows() == []


def test_multiple_simultaneous_changes_emit_independent_events():
    previous = [
        GovtStatusField("status", "Status", value_text="submitted"),
        GovtStatusField("department", "Department", value_text="Food"),
        GovtStatusField("officer", "Officer", value_text="Officer A"),
        GovtStatusField("current_position", "Current position", value_text="Desk A"),
    ]
    current = [
        GovtStatusField("status", "Status", value_text="under_review"),
        GovtStatusField("department", "Department", value_text="Revenue"),
        GovtStatusField("officer", "Officer", value_text="Officer B"),
        GovtStatusField("current_position", "Current position", value_text="Desk B"),
    ]

    assert [(c.field_key, c.event_type) for c in diff_snapshot_fields(previous, current)] == [
        ("officer", "officer_changed"),
        ("status", "status_changed"),
        ("department", "department_changed"),
    ]


def test_json_key_order_does_not_generate_false_change():
    changes = diff_snapshot_fields(
        [GovtStatusField("document", "Document", value_json={"name": "ATR.pdf", "type": "pdf"})],
        [GovtStatusField("document", "Document", value_json={"type": "pdf", "name": "ATR.pdf"})],
    )
    assert changes == []


def test_comment_deduplication_with_stable_portal_id():
    previous = [GovtStatusField("comment", "Comment", value_json=[{"id": "c1", "text": "Seen"}])]
    current = [GovtStatusField("comment", "Comment", value_json=[
        {"id": "c1", "text": "Seen"},
        {"id": "c2", "text": "Forwarded"},
    ])]

    changes = diff_snapshot_fields(previous, current)

    assert len(changes) == 1
    assert changes[0].event_type == "comment_added"
    assert changes[0].new_value_json["identity_quality"] == "stable"
    assert changes[0].new_value_json["identity"] == "stable:c2"


def test_persisted_comment_event_not_repeated_when_item_reappears_later():
    _reset_db()
    first_at = _utcnow() - timedelta(minutes=3)
    second_at = _utcnow() - timedelta(minutes=2)
    third_at = _utcnow() - timedelta(minutes=1)
    fourth_at = _utcnow()

    persist_status_snapshot(
        tenant_id=1,
        case_id=40,
        portal_id=10,
        reference_number="REF/TEST/0001",
        adapter_key="test",
        captured_at=first_at,
        result=GovtStatusSnapshotResult(fields=[GovtStatusField("comment", "Comment", value_json=[])]),
    )
    persist_status_snapshot(
        tenant_id=1,
        case_id=40,
        portal_id=10,
        reference_number="REF/TEST/0001",
        adapter_key="test",
        captured_at=second_at,
        result=GovtStatusSnapshotResult(fields=[GovtStatusField("comment", "Comment", value_json=[{"id": "c1", "text": "Seen"}])]),
    )
    persist_status_snapshot(
        tenant_id=1,
        case_id=40,
        portal_id=10,
        reference_number="REF/TEST/0001",
        adapter_key="test",
        captured_at=third_at,
        result=GovtStatusSnapshotResult(fields=[GovtStatusField("comment", "Comment", value_json=[])]),
    )
    persist_status_snapshot(
        tenant_id=1,
        case_id=40,
        portal_id=10,
        reference_number="REF/TEST/0001",
        adapter_key="test",
        captured_at=fourth_at,
        result=GovtStatusSnapshotResult(fields=[GovtStatusField("comment", "Comment", value_json=[{"id": "c1", "text": "Seen"}])]),
    )

    events = _event_rows()
    assert len(events) == 1
    assert events[0]["event_type"] == "comment_added"


def test_derived_communication_identity_uses_author_timestamp_text():
    previous = [GovtStatusField("reply", "Reply", value_json=[])]
    current = [GovtStatusField("reply", "Reply", value_json=[
        {"author": "Officer", "posted_at": "2026-09-03T10:00:00Z", "text": "Action initiated"}
    ])]

    changes = diff_snapshot_fields(previous, current)

    assert len(changes) == 1
    assert changes[0].event_type == "reply_added"
    assert changes[0].new_value_json["identity_quality"] == "derived"
    assert changes[0].new_value_json["identity"].startswith("derived:")


def test_weak_communication_identity_is_marked_weak_not_guaranteed():
    previous = [GovtStatusField("reply", "Reply", value_json=[])]
    current = [GovtStatusField("reply", "Reply", value_json=[{"text": "Free text only"}])]

    changes = diff_snapshot_fields(previous, current)

    assert len(changes) == 1
    assert changes[0].event_type == "reply_added"
    assert changes[0].new_value_json["identity_quality"] == "weak"
    assert changes[0].new_value_json["identity"].startswith("weak:")


def test_persist_snapshot_uses_full_identity_for_previous_selection():
    _reset_db()
    first_at = _utcnow() - timedelta(minutes=5)
    second_at = _utcnow()

    persist_status_snapshot(
        tenant_id=1,
        case_id=40,
        portal_id=10,
        reference_number="REF/TEST/OTHER",
        adapter_key="test",
        captured_at=first_at,
        result=GovtStatusSnapshotResult(
            normalized_status="submitted",
            fields=[GovtStatusField("department", "Department", value_text="Wrong Reference Dept")],
        ),
    )
    persist_status_snapshot(
        tenant_id=1,
        case_id=40,
        portal_id=10,
        reference_number="REF/TEST/0001",
        adapter_key="test",
        captured_at=first_at,
        result=GovtStatusSnapshotResult(
            normalized_status="submitted",
            fields=[GovtStatusField("department", "Department", value_text="Food Department")],
        ),
    )
    persist_status_snapshot(
        tenant_id=1,
        case_id=40,
        portal_id=10,
        reference_number="REF/TEST/0001",
        adapter_key="test",
        captured_at=second_at,
        result=GovtStatusSnapshotResult(
            normalized_status="submitted",
            fields=[GovtStatusField("department", "Department", value_text="Revenue Department")],
        ),
    )

    with test_engine.connect() as conn:
        events = conn.execute(text(
            "SELECT field_key, event_type, old_value_text, new_value_text "
            "FROM govt_status_snapshot_events ORDER BY id"
        )).mappings().all()

    assert [dict(row) for row in events] == [{
        "field_key": "department",
        "event_type": "department_changed",
        "old_value_text": "Food Department",
        "new_value_text": "Revenue Department",
    }]


def test_repeated_identical_successful_reads_create_snapshots_without_events():
    _reset_db()
    result = GovtStatusSnapshotResult(
        normalized_status="submitted",
        fields=[
            GovtStatusField("status", "Status", value_text="submitted"),
            GovtStatusField("department", "Department", value_text="Food Department"),
        ],
    )

    first_id = persist_status_snapshot(
        tenant_id=1,
        case_id=40,
        portal_id=10,
        reference_number="REF/TEST/0001",
        adapter_key="test",
        result=result,
        captured_at=_utcnow() - timedelta(seconds=1),
    )
    second_id = persist_status_snapshot(
        tenant_id=1,
        case_id=40,
        portal_id=10,
        reference_number="REF/TEST/0001",
        adapter_key="test",
        result=result,
        captured_at=_utcnow(),
    )

    assert first_id != second_id
    assert _snapshot_count() == 2
    assert _event_rows() == []


class _FakeAdapter:
    supports_unattended_status_check = True

    def __init__(self, result):
        self._result = result

    def check_status(self, reference_number, tenant_id=None):
        return self._result


def test_successful_snapshot_persistence_keeps_current_state_and_log_semantics():
    _reset_db()
    result = StatusResult(
        status="under_review",
        raw_portal_status="Registered & Sent for Scrutiny",
        portal_detail={"department_name": "Food Department"},
    )

    with patch("modules.govt_sync.adapters.get_adapter", return_value=_FakeAdapter(result)):
        response = api_router.govt_poll_case(40, user={"tenant_id": 1, "username": "mp_snapshot"})

    assert response["success"] is True
    assert response["changed"] is True
    with test_engine.connect() as conn:
        case = conn.execute(text(
            "SELECT govt_status, govt_status_updated_at FROM cases WHERE id = 40"
        )).mappings().first()
        log = conn.execute(text(
            "SELECT action, payload FROM govt_submission_log WHERE case_id = 40 ORDER BY id"
        )).mappings().one()

    assert case["govt_status"] == "under_review"
    assert case["govt_status_updated_at"] is not None
    assert log["action"] == "status_polled"
    assert json.loads(log["payload"])["changed"] is True
    assert _snapshot_count() == 1


def test_api_observer_helper_is_non_fatal(monkeypatch):
    def _raise(**kwargs):
        raise RuntimeError("snapshot store offline")

    monkeypatch.setattr("modules.govt_sync.status_snapshot.persist_status_snapshot", _raise)

    api_router._observe_govt_status_snapshot(
        1,
        40,
        {"portal_id": 10, "govt_reference_number": "REF/TEST/0001"},
        StatusResult(status="submitted"),
    )


def test_status_check_succeeds_when_snapshot_persistence_fails(monkeypatch, caplog):
    _reset_db()
    result = StatusResult(status="under_review", raw_portal_status="Portal says under review")

    def _raise(**kwargs):
        raise RuntimeError("snapshot store offline")

    monkeypatch.setattr("modules.govt_sync.status_snapshot.persist_status_snapshot", _raise)

    with caplog.at_level(logging.ERROR, logger="needle.api"):
        with patch("modules.govt_sync.adapters.get_adapter", return_value=_FakeAdapter(result)):
            response = api_router.govt_poll_case(40, user={"tenant_id": 1, "username": "mp_snapshot"})

    assert response["success"] is True
    assert response["changed"] is True
    with test_engine.connect() as conn:
        case = conn.execute(text(
            "SELECT govt_status, govt_status_updated_at FROM cases WHERE id = 40"
        )).mappings().first()
        log_count = conn.execute(text(
            "SELECT COUNT(*) FROM govt_submission_log WHERE case_id = 40 AND action = 'status_polled'"
        )).scalar()

    assert case["govt_status"] == "under_review"
    assert case["govt_status_updated_at"] is not None
    assert log_count == 1
    assert _snapshot_count() == 0
    assert "Govt status snapshot observer failed tenant=1 case=40" in caplog.text


def test_history_api_keeps_partial_latest_snapshot_and_previous_latest_known():
    _reset_db()
    first_at = _utcnow() - timedelta(hours=1)
    second_at = _utcnow()
    first_id = persist_status_snapshot(
        tenant_id=1,
        case_id=40,
        portal_id=10,
        reference_number="REF/TEST/0001",
        adapter_key="test",
        captured_at=first_at,
        result=GovtStatusSnapshotResult(
            normalized_status="under_review",
            fields=[
                GovtStatusField("department", "Department", value_text="Revenue"),
                GovtStatusField("officer", "Officer", value_text="Amit"),
            ],
        ),
    )
    second_id = persist_status_snapshot(
        tenant_id=1,
        case_id=40,
        portal_id=10,
        reference_number="REF/TEST/0001",
        adapter_key="test",
        captured_at=second_at,
        result=GovtStatusSnapshotResult(
            normalized_status="under_review",
            partial=True,
            fields=[
                GovtStatusField("department", "Department", availability=AVAILABILITY_UNAVAILABLE),
                GovtStatusField("officer", "Officer", availability=AVAILABILITY_UNAVAILABLE),
            ],
        ),
    )

    response = api_router.get_govt_status_history(40, limit=25, before_snapshot_id=None, user={"tenant_id": 1, "username": "mp_snapshot"})

    assert response["current_state"]["needle_govt_status"] == "submitted"
    assert response["current_state"]["latest_snapshot_id"] == second_id
    assert response["latest_snapshot"]["id"] == second_id
    assert "T" in response["latest_snapshot"]["captured_at"]
    assert response["latest_snapshot"]["captured_at"].endswith("Z")
    assert response["latest_snapshot"]["snapshot_status"] == "partial"
    assert response["latest_snapshot"]["fields"]["department"]["state"] == "unavailable"
    assert response["latest_known"]["department"]["value"] == "Revenue"
    assert response["latest_known"]["department"]["snapshot_id"] == first_id
    assert response["latest_known"]["department"]["last_confirmed_at"] != response["latest_snapshot"]["captured_at"]
    assert response["events"] == []


def test_history_api_ordering_cursor_pagination_and_public_event_shape():
    _reset_db()
    base = _utcnow() - timedelta(hours=3)
    first_id = persist_status_snapshot(
        tenant_id=1,
        case_id=40,
        portal_id=10,
        reference_number="REF/TEST/0001",
        adapter_key="test",
        captured_at=base,
        result=GovtStatusSnapshotResult(
            normalized_status="submitted",
            fields=[
                GovtStatusField("status", "Status", value_text="submitted"),
                GovtStatusField("department", "Department", value_text="Food"),
            ],
        ),
    )
    second_id = persist_status_snapshot(
        tenant_id=1,
        case_id=40,
        portal_id=10,
        reference_number="REF/TEST/0001",
        adapter_key="test",
        captured_at=base + timedelta(hours=1),
        result=GovtStatusSnapshotResult(
            normalized_status="under_review",
            fields=[
                GovtStatusField("status", "Status", value_text="under_review"),
                GovtStatusField("department", "Department", value_text="Food"),
                GovtStatusField("officer", "Officer", value_text="Officer A"),
            ],
        ),
    )
    third_id = persist_status_snapshot(
        tenant_id=1,
        case_id=40,
        portal_id=10,
        reference_number="REF/TEST/0001",
        adapter_key="test",
        captured_at=base + timedelta(hours=2),
        result=GovtStatusSnapshotResult(
            normalized_status="under_review",
            fields=[
                GovtStatusField("status", "Status", value_text="under_review"),
                GovtStatusField("department", "Department", value_text="Revenue"),
                GovtStatusField("officer", "Officer", value_text="Officer B"),
            ],
        ),
    )

    page = api_router.get_govt_status_history(40, limit=2, before_snapshot_id=None, user={"tenant_id": 1, "username": "mp_snapshot"})
    next_page = api_router.get_govt_status_history(
        40,
        limit=2,
        before_snapshot_id=page["pagination"]["next_before_snapshot_id"],
        user={"tenant_id": 1, "username": "mp_snapshot"},
    )

    assert [s["id"] for s in page["snapshots"]] == [third_id, second_id]
    assert page["pagination"]["has_more"] is True
    assert [s["id"] for s in next_page["snapshots"]] == [first_id]
    assert page["events"][0]["type"] in {"department_changed", "officer_changed"}
    assert {event["type"] for event in page["events"]}.issubset({
        "status_changed", "department_changed", "officer_changed", "comment_added", "reply_added"
    })


def test_latest_known_survives_pagination_boundary():
    """department is only ever observed on the OLDEST snapshot; every later
    snapshot reports status only. With limit=5 and 10 total snapshots,
    department falls outside page 1's raw fetch window (limit+1=6 newest
    rows) entirely. latest_known.department must still resolve correctly on
    page 1, and identically on a later page — it must never be computed from
    only the snapshots fetched for the current page."""
    _reset_db()
    base = _utcnow() - timedelta(hours=10)
    first_id = persist_status_snapshot(
        tenant_id=1, case_id=40, portal_id=10, reference_number="REF/TEST/0001", adapter_key="test",
        captured_at=base,
        result=GovtStatusSnapshotResult(fields=[
            GovtStatusField("status", "Status", value_text="submitted"),
            GovtStatusField("department", "Department", value_text="Revenue"),
        ]),
    )
    for i in range(1, 10):
        persist_status_snapshot(
            tenant_id=1, case_id=40, portal_id=10, reference_number="REF/TEST/0001", adapter_key="test",
            captured_at=base + timedelta(hours=i),
            result=GovtStatusSnapshotResult(fields=[GovtStatusField("status", "Status", value_text="under_review")]),
        )

    page1 = api_router.get_govt_status_history(40, limit=5, before_snapshot_id=None, user={"tenant_id": 1, "username": "mp_snapshot"})
    page2 = api_router.get_govt_status_history(
        40, limit=5, before_snapshot_id=page1["pagination"]["next_before_snapshot_id"],
        user={"tenant_id": 1, "username": "mp_snapshot"},
    )

    assert first_id not in [s["id"] for s in page1["snapshots"]]
    assert page1["latest_known"]["department"]["value"] == "Revenue"
    assert page1["latest_known"]["department"]["snapshot_id"] == first_id
    assert page2["latest_known"]["department"] == page1["latest_known"]["department"]


def test_cursor_pagination_ids_and_timestamps_increasing_together():
    _reset_db()
    base = _utcnow() - timedelta(hours=3)
    ids = [
        persist_status_snapshot(
            tenant_id=1, case_id=40, portal_id=10, reference_number="REF/TEST/0001", adapter_key="test",
            captured_at=base + timedelta(hours=i),
            result=GovtStatusSnapshotResult(fields=[GovtStatusField("status", "Status", value_text=f"s{i}")]),
        )
        for i in range(3)
    ]
    page = api_router.get_govt_status_history(40, limit=2, before_snapshot_id=None, user={"tenant_id": 1, "username": "mp_snapshot"})
    next_page = api_router.get_govt_status_history(
        40, limit=2, before_snapshot_id=page["pagination"]["next_before_snapshot_id"],
        user={"tenant_id": 1, "username": "mp_snapshot"},
    )
    assert [s["id"] for s in page["snapshots"]] == [ids[2], ids[1]]
    assert [s["id"] for s in next_page["snapshots"]] == [ids[0]]


def test_cursor_pagination_ids_and_timestamps_out_of_order():
    """A higher id with an EARLIER captured_at than a lower id (e.g. a
    concurrent writer) must still be reachable via cursor pagination — a
    plain `id < cursor` predicate would skip it forever."""
    _reset_db()
    base = _utcnow() - timedelta(hours=3)
    early_id = persist_status_snapshot(
        tenant_id=1, case_id=40, portal_id=10, reference_number="REF/TEST/0001", adapter_key="test",
        captured_at=base,
        result=GovtStatusSnapshotResult(fields=[GovtStatusField("status", "Status", value_text="s0")]),
    )
    # Inserted AFTER (higher id) but observed BEFORE (earlier captured_at).
    out_of_order_id = persist_status_snapshot(
        tenant_id=1, case_id=40, portal_id=10, reference_number="REF/TEST/0001", adapter_key="test",
        captured_at=base - timedelta(hours=1),
        result=GovtStatusSnapshotResult(fields=[GovtStatusField("status", "Status", value_text="s_early")]),
    )
    assert out_of_order_id > early_id

    page1 = api_router.get_govt_status_history(40, limit=1, before_snapshot_id=None, user={"tenant_id": 1, "username": "mp_snapshot"})
    page2 = api_router.get_govt_status_history(
        40, limit=1, before_snapshot_id=page1["pagination"]["next_before_snapshot_id"],
        user={"tenant_id": 1, "username": "mp_snapshot"},
    )
    assert [s["id"] for s in page1["snapshots"]] == [early_id]
    assert [s["id"] for s in page2["snapshots"]] == [out_of_order_id]
    assert page2["pagination"]["has_more"] is False


def test_cursor_pagination_equal_timestamps_different_ids():
    _reset_db()
    same_time = _utcnow() - timedelta(hours=1)
    first_id = persist_status_snapshot(
        tenant_id=1, case_id=40, portal_id=10, reference_number="REF/TEST/0001", adapter_key="test",
        captured_at=same_time,
        result=GovtStatusSnapshotResult(fields=[GovtStatusField("status", "Status", value_text="a")]),
    )
    second_id = persist_status_snapshot(
        tenant_id=1, case_id=40, portal_id=10, reference_number="REF/TEST/0001", adapter_key="test",
        captured_at=same_time,
        result=GovtStatusSnapshotResult(fields=[GovtStatusField("status", "Status", value_text="b")]),
    )
    assert second_id > first_id

    page1 = api_router.get_govt_status_history(40, limit=1, before_snapshot_id=None, user={"tenant_id": 1, "username": "mp_snapshot"})
    page2 = api_router.get_govt_status_history(
        40, limit=1, before_snapshot_id=page1["pagination"]["next_before_snapshot_id"],
        user={"tenant_id": 1, "username": "mp_snapshot"},
    )
    assert [s["id"] for s in page1["snapshots"]] == [second_id]
    assert [s["id"] for s in page2["snapshots"]] == [first_id]


def test_invalid_cursor_treated_as_no_cursor():
    """An unresolvable/foreign before_snapshot_id (not found for this
    tenant/case/portal/reference) falls back to no cursor at all — the same
    result a client gets by omitting it — rather than erroring or inventing
    a new empty-page shape."""
    _reset_db()
    first_id = persist_status_snapshot(
        tenant_id=1, case_id=40, portal_id=10, reference_number="REF/TEST/0001", adapter_key="test",
        result=GovtStatusSnapshotResult(fields=[GovtStatusField("status", "Status", value_text="a")]),
    )

    page_no_cursor = api_router.get_govt_status_history(40, limit=25, before_snapshot_id=None, user={"tenant_id": 1, "username": "mp_snapshot"})
    page_bad_cursor = api_router.get_govt_status_history(40, limit=25, before_snapshot_id=999999, user={"tenant_id": 1, "username": "mp_snapshot"})

    assert [s["id"] for s in page_bad_cursor["snapshots"]] == [s["id"] for s in page_no_cursor["snapshots"]] == [first_id]


def test_omitted_portal_detail_key_is_not_fabricated_as_unavailable():
    """A key entirely absent from StatusResult.portal_detail must stay
    omitted from the mapped fields — never fabricated as an `unavailable`
    field row, since the adapter contract gives no basis to distinguish
    'not applicable to this portal' from 'checked, not found this time'."""
    result = StatusResult(
        status="under_review",
        portal_detail={"department_name": "Food Department"},
    )
    snapshot = status_result_to_snapshot_result(result)
    by_key = {f.field_key: f for f in snapshot.fields}
    assert "officer" not in by_key
    assert "designation" not in by_key
