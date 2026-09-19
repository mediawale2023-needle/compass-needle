import json
import hashlib
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
TEST_DB_URL = "sqlite:///./test_govt_portal_history.db"
os.environ["JWT_SECRET"] = TEST_JWT_SECRET
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["ENV"] = "test"
os.environ["OPENAI_API_KEY"] = "sk-test-fake-key-for-testing"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@event.listens_for(Engine, "connect")
def _sqlite_pg_lock_stubs(dbapi_connection, _connection_record):
    try:
        dbapi_connection.create_function("pg_try_advisory_lock", 1, lambda _key: 1)
        dbapi_connection.create_function("pg_advisory_unlock", 1, lambda _key: 1)
        dbapi_connection.create_function("pg_try_advisory_xact_lock", 1, lambda _key: 1)
    except Exception:
        pass


import api_router
import core.db_helpers as db_helpers
import main
import sansadx_backend.db as dbmod
from modules.govt_sync.adapters.base import StatusResult
from modules.govt_sync.adapters.manual import ManualAssistedAdapter
from modules.govt_sync.adapters.rajasthan_history_mapping import map_rajasthan_history
from modules.govt_sync.adapters.rajasthan_sampark import RajasthanSamparkAPIAdapter
from modules.govt_sync.orchestrator import persist_successful_sync_result, persist_successful_status_result
from modules.govt_sync.identity import communication_identity
from modules.govt_sync.portal_history import (
    HistoryAvailability,
    HistoryCapability,
    PortalHistoryDocument,
    PortalHistoryEvent,
    PortalHistoryResult,
    persist_portal_history_events,
)
from sansadx_backend.db import Base, hash_password

test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False, "timeout": 20})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False)
client = TestClient(main.app, raise_server_exceptions=False)


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _headers(username="owner_one"):
    token = jwt.encode(
        {"sub": username, "exp": _utcnow() + timedelta(hours=8), "iat": _utcnow().timestamp()},
        TEST_JWT_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def _seed():
    dbmod.engine = test_engine
    dbmod.SessionLocal = TestSession
    db_helpers.engine = test_engine
    main.engine = test_engine
    api_router.engine = test_engine
    api_router.JWT_SECRET = TEST_JWT_SECRET
    Base.metadata.create_all(bind=test_engine)
    now = _utcnow()
    with test_engine.begin() as conn:
        for table in (
            "govt_portal_history_events", "govt_submission_log", "govt_status_snapshot_events",
            "govt_status_snapshot_fields", "govt_status_snapshots", "case_activity_log", "cases",
            "govt_portals", "users", "tenant_profiles", "tenants",
        ):
            conn.execute(text(f"DELETE FROM {table}"))  # nosec B608
        for tenant_id, username in ((1, "owner_one"), (2, "owner_two")):
            conn.execute(text(
                "INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active, created_at) "
                "VALUES (:id, :name, :seat, :phone, 'Pro', 1, :now)"
            ), {"id": tenant_id, "name": username, "seat": f"Seat {tenant_id}", "phone": f"+91900000000{tenant_id}", "now": now})
            conn.execute(text(
                "INSERT INTO tenant_profiles (tenant_id, mp_name, constituency, state, house, created_at) "
                "VALUES (:id, :name, :seat, 'Rajasthan', 'Lok Sabha', :now)"
            ), {"id": tenant_id, "name": username, "seat": f"Seat {tenant_id}", "now": now})
            conn.execute(text(
                "INSERT INTO users (tenant_id, username, password_hash, role, constituency, house, display_name, is_active) "
                "VALUES (:id, :username, :password, 'owner', :seat, 'Lok Sabha', :username, 1)"
            ), {"id": tenant_id, "username": username, "password": hash_password("Password1"), "seat": f"Seat {tenant_id}"})
        conn.execute(text(
            "INSERT INTO govt_portals (id, state, portal_name, portal_type, base_url, status_check_url, "
            "status_check_mode, department_taxonomy, field_schema, otp_bound, active, is_primary, "
            "verification_status, live_session_supported, status_check_adapter) VALUES "
            "(10, 'Rajasthan', 'Rajasthan Sampark', 'state_branded', 'https://example.invalid', "
            "'https://example.invalid/status', 'login_required', '{}', '{}', 1, 1, 1, 'confirmed', 0, 'rajasthan_sampark_api')"
        ))
        for case_id, tenant_id, reference in ((40, 1, "RJ/ONE/40"), (41, 2, "RJ/TWO/41")):
            conn.execute(text(
                "INSERT INTO cases (id, tenant_id, user_phone, raw_message, category, status, created_at, "
                "govt_portal_id, govt_status, govt_reference_number, govt_status_updated_at, is_deleted) "
                "VALUES (:id, :tenant_id, '+919111111111', 'Road complaint', 'Infrastructure & Utilities', "
                "'in_progress', :now, 10, 'under_review', :reference, :now, 0)"
            ), {"id": case_id, "tenant_id": tenant_id, "reference": reference, "now": now})


def _event(comment="Work has been completed.", *, status="under_review", source_event_id=None):
    return PortalHistoryEvent(
        occurred_at=datetime(2026, 9, 12, 16, 15),
        event_type="department_remark",
        status=status,
        raw_status="Under Process",
        from_display="Public Works Department",
        to_display="Urban Improvement Trust",
        comment=comment,
        documents=(PortalHistoryDocument(source_document_id="7812"),),
        source="fixture_portal",
        source_event_id=source_event_id,
    )


def test_rajasthan_fixture_mapper_preserves_comment_and_document_metadata():
    fixture = json.loads((Path(__file__).parent / "fixtures" / "rajasthan_history.json").read_text())
    events = map_rajasthan_history(fixture)
    assert len(events) == 3
    assert events[0].comment == "  Necessary action has been taken.  "
    assert events[0].status == "resolved"
    assert events[0].event_type == "resolution"
    assert [doc.source_document_id for doc in events[0].documents] == ["7812", "7813"]
    assert events[1].event_type == "routing_update"
    assert events[2].occurred_at is None
    assert events[2].comment is None


def test_rajasthan_mapper_handles_comment_only_and_missing_fields_without_guessing():
    event = map_rajasthan_history([{"Remarks": "Original wording", "DocId": None}])[0]
    assert event.event_type == "department_remark"
    assert event.comment == "Original wording"
    assert event.occurred_at is None
    assert event.status is None
    assert event.from_department is None
    assert event.to_department is None


def test_rajasthan_security_blocked_history_performs_zero_network_calls():
    adapter = RajasthanSamparkAPIAdapter({"id": 10, "portal_name": "Rajasthan Sampark"})
    assert adapter.history_capability is HistoryCapability.SECURITY_BLOCKED
    assert adapter.supports_history is False
    with patch("requests.post") as post:
        result = adapter.fetch_history("RJ/ONE/40", tenant_id=1)
    post.assert_not_called()
    assert result.availability is HistoryAvailability.UNAVAILABLE
    assert result.events == ()


def test_rajasthan_existing_status_fetch_path_is_unchanged():
    adapter = RajasthanSamparkAPIAdapter({"id": 10, "portal_name": "Rajasthan Sampark"})
    expected = {"status_text": "Under Process", "department_name": "UIT"}
    with patch(
        "modules.govt_sync.adapters.rajasthan_sampark.check_grievance_detail",
        return_value=expected,
    ) as current_status_fetch:
        result = adapter._fetch_status("919999999999", "RJ/ONE/40", "transaction", "session")
    assert result == expected
    current_status_fetch.assert_called_once_with("919999999999", "RJ/ONE/40", "transaction", "session")


def test_snapshot_communication_identity_retains_legacy_hash_contract():
    item = {"author": " अधिकारी ", "posted_at": " 19 Sep 2026 ", "text": " काम  पूर्ण "}
    normalized = {"author": "अधिकारी", "posted_at": "19 Sep 2026", "text": "काम पूर्ण"}
    expected = hashlib.sha256(
        json.dumps(normalized, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
    assert communication_identity(item) == {
        "identity": f"derived:{expected}",
        "identity_quality": "derived",
    }


def test_no_history_adapter_defaults_to_not_supported_and_zero_io():
    adapter = ManualAssistedAdapter({"id": 10, "portal_name": "Manual Portal"})
    assert adapter.history_capability is HistoryCapability.NOT_SUPPORTED
    assert adapter.supports_history is False
    with patch("requests.post") as post:
        result = adapter.fetch_history("REF-1", tenant_id=1)
    post.assert_not_called()
    assert result.availability is HistoryAvailability.UNAVAILABLE


def test_persistence_deduplicates_identical_and_nonconsecutive_events():
    _seed()
    first = persist_portal_history_events(tenant_id=1, case_id=40, portal_id=10, reference_number="RJ/ONE/40", events=[_event()])
    persist_portal_history_events(tenant_id=1, case_id=40, portal_id=10, reference_number="RJ/ONE/40", events=[_event("Another remark")])
    repeated = persist_portal_history_events(tenant_id=1, case_id=40, portal_id=10, reference_number="RJ/ONE/40", events=[_event()])
    assert len(first.inserted_event_ids) == 1
    assert repeated.inserted_event_ids == ()
    with test_engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM govt_portal_history_events WHERE case_id = 40")).scalar() == 2


def test_database_unique_identity_is_concurrency_safe():
    _seed()
    kwargs = dict(tenant_id=1, case_id=40, portal_id=10, reference_number="RJ/ONE/40", events=[_event(source_event_id="stable-9")])
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _index: persist_portal_history_events(**kwargs), range(2)))
    assert sum(len(result.inserted_event_ids) for result in results) == 1
    with test_engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM govt_portal_history_events WHERE source_event_id = 'stable-9'")).scalar() == 1


def test_same_status_new_comment_is_meaningful_but_repeat_is_not():
    _seed()
    status = StatusResult(status="under_review", raw_portal_status="Under Process")
    case = {"govt_status": "under_review", "portal_id": 10, "govt_reference_number": "RJ/ONE/40", "portal_name": "Fixture"}
    history = PortalHistoryResult(availability=HistoryAvailability.AVAILABLE, events=(_event(),))
    first = persist_successful_sync_result(tenant_id=1, case_id=40, case_row=case, result=status, history_result=history)
    second = persist_successful_sync_result(tenant_id=1, case_id=40, case_row=case, result=status, history_result=history)
    assert first.changed is True
    assert first.status_changed is False
    assert first.change_types == ("portal_history_event_added", "government_remark_added", "routing_changed")
    assert second.changed is False
    assert second.change_types == ()


def test_status_transition_and_resolution_are_distinct_meaningful_signals():
    _seed()
    case = {"govt_status": "under_review", "portal_id": 10, "govt_reference_number": "RJ/ONE/40", "portal_name": "Fixture"}
    result = persist_successful_sync_result(
        tenant_id=1, case_id=40, case_row=case,
        result=StatusResult(status="resolved", raw_portal_status="Disposed"),
        history_result=PortalHistoryResult(availability=HistoryAvailability.AVAILABLE, events=()),
    )
    assert result.changed is True
    assert result.status_changed is True
    assert result.change_types == ("status_changed", "resolution_reported")


def test_temporarily_unavailable_history_does_not_create_false_change():
    _seed()
    case = {"govt_status": "under_review", "portal_id": 10, "govt_reference_number": "RJ/ONE/40", "portal_name": "Fixture"}
    result = persist_successful_sync_result(
        tenant_id=1, case_id=40, case_row=case,
        result=StatusResult(status="under_review", raw_portal_status="Under Process"),
        history_result=PortalHistoryResult(
            availability=HistoryAvailability.TEMPORARILY_UNAVAILABLE,
            diagnostic_code="upstream_timeout",
        ),
    )
    assert result.changed is False
    with test_engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM govt_portal_history_events")).scalar() == 0


def test_legacy_orchestrator_wrapper_remains_status_change_boolean():
    _seed()
    case = {"govt_status": "under_review", "portal_id": 10, "govt_reference_number": "RJ/ONE/40", "portal_name": "Fixture"}
    assert persist_successful_status_result(
        tenant_id=1, case_id=40, case_row=case,
        result=StatusResult(status="under_review", raw_portal_status="Under Process"),
    ) is False
    assert persist_successful_status_result(
        tenant_id=1, case_id=40, case_row=case,
        result=StatusResult(status="resolved", raw_portal_status="Disposed"),
    ) is True


def test_portal_history_api_is_newest_first_and_strictly_tenant_scoped():
    _seed()
    older = _event("Older remark")
    newer = PortalHistoryEvent(**{**older.__dict__, "occurred_at": datetime(2026, 9, 19), "comment": "Newest remark"})
    persist_portal_history_events(tenant_id=1, case_id=40, portal_id=10, reference_number="RJ/ONE/40", events=[older, newer])
    response = client.get("/api/cases/40/govt/portal-history", headers=_headers("owner_one"))
    assert response.status_code == 200, response.text
    assert [event["comment"] for event in response.json()["events"]] == ["Newest remark", "Older remark"]
    denied = client.get("/api/cases/40/govt/portal-history", headers=_headers("owner_two"))
    assert denied.status_code == 404


def test_portal_history_api_omits_internal_source_metadata():
    _seed()
    event = PortalHistoryEvent(
        occurred_at=datetime(2026, 9, 19),
        event_type="department_remark",
        comment="Public government wording",
        source="fixture_portal",
        source_metadata={"regional_status": "internal mapping context", "raw_payload": {"secret": True}},
        documents=(PortalHistoryDocument(
            source_document_id="7812",
            retrieval_state="metadata_only",
            source_metadata={"internal_locator": "must-not-leak"},
        ),),
    )
    persist_portal_history_events(
        tenant_id=1, case_id=40, portal_id=10,
        reference_number="RJ/ONE/40", events=[event],
    )
    response = client.get("/api/cases/40/govt/portal-history", headers=_headers())
    assert response.status_code == 200
    public_event = response.json()["events"][0]
    assert "source_metadata" not in public_event
    assert public_event["documents"] == [{
        "source_document_id": "7812",
        "retrieval_state": "metadata_only",
    }]


def test_portal_history_isolated_by_portal_and_reference_even_with_same_case_scope():
    _seed()
    persist_portal_history_events(tenant_id=1, case_id=40, portal_id=10, reference_number="OLD/REF", events=[_event("Old reference")])
    persist_portal_history_events(tenant_id=1, case_id=40, portal_id=10, reference_number="RJ/ONE/40", events=[_event("Current reference")])
    response = client.get("/api/cases/40/govt/portal-history", headers=_headers())
    assert response.status_code == 200
    assert [event["comment"] for event in response.json()["events"]] == ["Current reference"]


def test_portal_history_keyset_pagination_is_stable_for_equal_and_missing_dates():
    _seed()
    same_time = datetime(2026, 9, 19, 10, 30)
    events = [
        PortalHistoryEvent(
            occurred_at=same_time,
            event_type="department_remark",
            comment=f"Dated update {number}",
            source="fixture_portal",
            source_event_id=f"dated-{number}",
        )
        for number in range(3)
    ]
    events.append(PortalHistoryEvent(
        event_type="department_remark",
        comment="Undated update",
        source="fixture_portal",
        source_event_id="undated",
    ))
    persist_portal_history_events(
        tenant_id=1, case_id=40, portal_id=10,
        reference_number="RJ/ONE/40", events=events,
    )

    first = client.get(
        "/api/cases/40/govt/portal-history?limit=2",
        headers=_headers(),
    ).json()
    assert len(first["events"]) == 2
    assert first["pagination"]["has_more"] is True
    second = client.get(
        f"/api/cases/40/govt/portal-history?limit=2&before_id={first['pagination']['next_before_id']}",
        headers=_headers(),
    ).json()
    assert len(second["events"]) == 2
    assert second["events"][-1]["comment"] == "Undated update"
    assert {event["id"] for event in first["events"]}.isdisjoint(
        event["id"] for event in second["events"]
    )
    assert second["pagination"]["has_more"] is False


def test_latest_terminal_remark_enters_resolution_review_context_without_closing_case():
    _seed()
    with test_engine.begin() as conn:
        conn.execute(text("UPDATE cases SET govt_status = 'resolved' WHERE id = 40"))
    terminal = PortalHistoryEvent(
        occurred_at=datetime(2026, 9, 19), event_type="resolution", status="resolved",
        raw_status="Disposed", comment="Necessary action has been taken.", source="fixture_portal",
    )
    inserted = persist_portal_history_events(tenant_id=1, case_id=40, portal_id=10, reference_number="RJ/ONE/40", events=[terminal])
    state = client.get("/api/cases/40/govt", headers=_headers())
    assert state.status_code == 200, state.text
    assert state.json()["latest_terminal_portal_history_event"]["comment"] == "Necessary action has been taken."
    review = client.post("/api/cases/40/govt/resolution-review", headers=_headers(), json={"decision": "continue_follow_up"})
    assert review.status_code == 200, review.text
    assert review.json()["portal_history_event_id"] == inserted.inserted_event_ids[0]
    with test_engine.connect() as conn:
        assert conn.execute(text("SELECT status FROM cases WHERE id = 40")).scalar() == "in_progress"


def test_missing_and_malformed_history_are_safe():
    _seed()
    empty = persist_portal_history_events(
        tenant_id=1, case_id=40, portal_id=10, reference_number="RJ/ONE/40",
        events=[PortalHistoryEvent(source="fixture_portal", source_metadata={"ignored": "safe"})],
    )
    assert empty.inserted_event_ids == ()
    response = client.get("/api/cases/40/govt/portal-history", headers=_headers())
    assert response.status_code == 200
    assert response.json()["availability"] == "unavailable"
    assert response.json()["events"] == []


def test_schema_creation_is_idempotent_for_clean_and_existing_databases():
    _seed()
    persist_portal_history_events(
        tenant_id=1, case_id=40, portal_id=10, reference_number="RJ/ONE/40", events=[_event()],
    )
    Base.metadata.create_all(bind=test_engine)
    with test_engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM govt_portal_history_events")).scalar() == 1
    schema = inspect(test_engine)
    unique_names = {item["name"] for item in schema.get_unique_constraints("govt_portal_history_events")}
    index_names = {item["name"] for item in schema.get_indexes("govt_portal_history_events")}
    assert "uq_govt_portal_history_event_identity" in unique_names
    assert "idx_govt_portal_history_case" in index_names
