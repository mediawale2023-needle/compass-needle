"""
tests/test_govt_status_poll_orchestration_characterization.py — Phase 0
characterization tests for the government-status-poll orchestration
extraction (docs/GOVERNMENT_PORTAL_ARCHITECTURE_AUDIT.md, Part P Phase 1).

Purpose: lock down CURRENT `main` behavior for both polling paths —

  A. on-demand   — POST /cases/{id}/govt/poll         (api_router.py)
  B. background  — modules/govt_sync/poller.py::poll_all_pending()

BEFORE any production code is extracted, so the refactor cannot silently
unify behaviors that currently differ. Every assertion here describes what
`main` actually does today (as read from the source), not what the
refactor SHOULD do. Where the two paths differ, both shapes are asserted
explicitly, side by side, so a future accidental unification fails a test
immediately.

`poll_all_pending()`'s own SELECT uses Postgres-only `= ANY(:statuses)`
syntax (pre-existing, unrelated to this change — see
tests/test_govt_sync_poller.py's own note on this same limitation) and
cannot run against this suite's SQLite engine. Exactly like every other
govt-sync test file that needs to exercise poll_all_pending()'s row-
processing logic, this file patches `modules.govt_sync.poller._q` to
supply canned rows directly, bypassing that one incompatible SELECT only —
every other line of poll_all_pending() (adapter dispatch, DB writes,
skip_pairs, exception handling, counters) executes for real, against a
real (SQLite) engine.

CONFIRMED BEHAVIORAL DIFFERENCES BETWEEN THE TWO PATHS (discovered by
reading api_router.py::govt_poll_case and modules/govt_sync/poller.py::
poll_all_pending() side by side before writing any test):

  1. Inconclusive/needs-verification audit payload shape differs: the
     on-demand path logs {"portal", "raw_portal_status"} (2 keys); the
     background path logs {"portal", "raw_portal_status",
     "govt_status_at_time"} (3 keys) — via poller.py's own
     _inconclusive_payload(), never used by api_router.py.
  2. actor_username on the 'status_polled' audit row and the persisted
     snapshot's created_by: on-demand passes the real authenticated
     username; background always passes None (no human triggered it).
  3. Adapter-exception handling: on-demand lets the exception propagate
     uncaught out of the route handler (no try/except around the
     `result = adapter.check_status(...)` call other than logging then
     `raise`); background catches it, logs a warning, and `continue`s to
     the next row — one case's exception never aborts the batch.
  4. supports_unattended_status_check: background skips a case's adapter
     call ENTIRELY (structural `continue`, adapter never invoked) when
     False; on-demand has NO such check at all and calls check_status()
     regardless — this is a genuine, real asymmetry, not an oversight
     this test suite should paper over.
  5. skip_pairs optimization: background remembers which (tenant_id,
     portal_id) pairs already came back needs_verification THIS run and
     skips every subsequent case sharing that pair without calling the
     adapter or writing any log row for the skipped case. On-demand has
     no equivalent (it only ever processes one case per call).
  6. Reference-number prerequisite: on-demand treats a missing
     govt_reference_number as an explicit error (400, before touching the
     adapter). Background's SELECT filters `govt_reference_number IS NOT
     NULL` at the SQL level — such a case is simply never selected into
     the batch in the first place, never an error state. (Not exercised
     via a mocked-row test here, since simulating it would mean feeding
     poll_all_pending() a row real production SQL could never produce —
     the enforcement point is the SQL text itself, which this extraction
     does not touch.)
  7. UPDATE + audit-log-INSERT transactional grouping: background wraps
     the `cases` UPDATE (when changed) and the `govt_submission_log`
     INSERT for a successful check in ONE `engine.begin()` transaction;
     on-demand currently uses TWO separate transactions (one for the
     UPDATE via a bare `with engine.begin()`, a second opened inside
     `_log_govt_action()`). Not independently observable by any caller in
     the non-crash case (both writes still happen, in the same order,
     with the same final values) — noted here for completeness, not
     asserted directly (SQLite's `engine.begin()` boundaries aren't
     something a black-box test can observe without instrumenting the
     connection itself).

Everything else (govt_status update conditions, 'status_polled' log
column values, snapshot persistence on success only — never on
inconclusive/needs_verification — normalize-status-derived `changed`
computation) is IDENTICAL between the two paths and is asserted as such.
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
TEST_DB_URL = "sqlite:///./test_govt_status_poll_orchestration_characterization.db"

os.environ["JWT_SECRET"] = TEST_JWT_SECRET
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["ENV"] = "test"
os.environ["OPENAI_API_KEY"] = "sk-test-fake-key-for-testing"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@event.listens_for(Engine, "connect")
def _sqlite_register_pg_lock_functions(dbapi_connection, connection_record):
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
from sansadx_backend.db import Base

from modules.govt_sync.adapters.base import StatusFailureKind, StatusResult
from modules.govt_sync import poller as poller_mod

test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False)
client = TestClient(main.app, raise_server_exceptions=False)


def _bind_engines():
    dbmod.engine = test_engine
    dbmod.SessionLocal = TestSession
    db_helpers.engine = test_engine
    main.engine = test_engine
    api_router.engine = test_engine
    poller_mod.engine = test_engine
    api_router.JWT_SECRET = TEST_JWT_SECRET


def _auth_headers(username: str = "mp_priya") -> dict[str, str]:
    token = jwt.encode(
        {"sub": username, "exp": _utcnow() + timedelta(hours=8), "iat": _utcnow().timestamp()},
        TEST_JWT_SECRET, algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def _seed_database():
    _bind_engines()
    Base.metadata.create_all(bind=test_engine)
    now = _utcnow()
    with test_engine.begin() as conn:
        for table_name in (
            "govt_status_snapshot_events", "govt_status_snapshot_fields", "govt_status_snapshots",
            "govt_submission_log", "cases", "govt_portals", "users", "tenants",
        ):
            conn.execute(text(f"DELETE FROM {table_name}"))  # nosec B608

        # Tenant 1 / case 40 — the primary fixture for most scenarios.
        conn.execute(text(
            "INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active, created_at) "
            "VALUES (1, 'Priya Sharma', 'Test Constituency', '+919000000001', 'Pro', 1, :now)"
        ), {"now": now})
        conn.execute(text(
            "INSERT INTO users (tenant_id, username, password_hash, role, constituency, house, display_name, is_active) "
            "VALUES (1, 'mp_priya', 'x', 'mp', 'Test Constituency', 'Lok Sabha', 'Priya MP', 1)"
        ))
        conn.execute(text(
            "INSERT INTO govt_portals (id, state, portal_name, portal_type, base_url, status_check_url, "
            "status_check_mode, department_taxonomy, field_schema, otp_bound, active, is_primary, "
            "verification_status, live_session_supported, status_check_adapter) VALUES "
            "(1, 'TestState', 'Test Portal', 'state_branded', 'https://example.test', 'https://example.test/status', "
            "'login_required', :taxonomy, :schema, 0, 1, 1, 'confirmed', 0, NULL)"
        ), {"taxonomy": json.dumps({}), "schema": json.dumps({})})
        conn.execute(text(
            "INSERT INTO cases (id, tenant_id, user_phone, raw_message, category, status, created_at, "
            "govt_portal_id, govt_status, govt_reference_number, govt_status_updated_at, is_deleted) VALUES "
            "(40, 1, '+919111111140', 'Test grievance', 'Infrastructure & Utilities', 'in_progress', :now, "
            "1, 'submitted', 'REF/TEST/0001', NULL, 0)"
        ), {"now": now})

        # A second portal whose status_check_adapter is the TN cookie
        # adapter's registered key — used only to characterize the
        # adapter-specific needs_verification note text branch.
        conn.execute(text(
            "INSERT INTO govt_portals (id, state, portal_name, portal_type, base_url, status_check_url, "
            "status_check_mode, department_taxonomy, field_schema, otp_bound, active, is_primary, "
            "verification_status, live_session_supported, status_check_adapter) VALUES "
            "(2, 'Tamil Nadu', 'TN Test Portal', 'state_branded', 'https://tn.example.test', NULL, "
            "'login_required', :taxonomy, :schema, 0, 1, 1, 'confirmed', 1, 'tamil_nadu_http_api')"
        ), {"taxonomy": json.dumps({}), "schema": json.dumps({})})
        conn.execute(text(
            "INSERT INTO cases (id, tenant_id, user_phone, raw_message, category, status, created_at, "
            "govt_portal_id, govt_status, govt_reference_number, govt_status_updated_at, is_deleted) VALUES "
            "(41, 1, '+919111111141', 'TN grievance', 'Infrastructure & Utilities', 'in_progress', :now, "
            "2, 'submitted', 'TN/REF/0002', NULL, 0)"
        ), {"now": now})

        # A case with no adapter registered under 2 sharing the SAME portal
        # 2 (tenant 1) — used for the background skip_pairs characterization.
        conn.execute(text(
            "INSERT INTO cases (id, tenant_id, user_phone, raw_message, category, status, created_at, "
            "govt_portal_id, govt_status, govt_reference_number, govt_status_updated_at, is_deleted) VALUES "
            "(42, 1, '+919111111142', 'TN grievance 2', 'Infrastructure & Utilities', 'in_progress', :now, "
            "2, 'submitted', 'TN/REF/0003', NULL, 0)"
        ), {"now": now})

        # Tenant 2 / case 43 — cross-tenant isolation fixture.
        conn.execute(text(
            "INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active, created_at) "
            "VALUES (2, 'Other MP', 'Other Seat', '+919000000002', 'Pro', 1, :now)"
        ), {"now": now})
        conn.execute(text(
            "INSERT INTO users (tenant_id, username, password_hash, role, constituency, house, display_name, is_active) "
            "VALUES (2, 'mp_other', 'x', 'mp', 'Other Seat', 'Lok Sabha', 'Other MP', 1)"
        ))
        conn.execute(text(
            "INSERT INTO cases (id, tenant_id, user_phone, raw_message, category, status, created_at, "
            "govt_portal_id, govt_status, govt_reference_number, govt_status_updated_at, is_deleted) VALUES "
            "(43, 2, '+919222222143', 'Other tenant grievance', 'Infrastructure & Utilities', 'in_progress', :now, "
            "1, 'submitted', 'REF/OTHER/0001', NULL, 0)"
        ), {"now": now})


def _log_rows(action: str | None = None):
    with test_engine.connect() as conn:
        q = "SELECT tenant_id, case_id, action, actor_username, payload FROM govt_submission_log"
        params = {}
        if action:
            q += " WHERE action = :action"
            params = {"action": action}
        q += " ORDER BY id"
        return [dict(r._mapping) for r in conn.execute(text(q), params)]


def _case_row(case_id: int) -> dict:
    with test_engine.connect() as conn:
        row = conn.execute(
            text("SELECT id, tenant_id, govt_status, govt_status_updated_at, govt_reference_number FROM cases WHERE id = :cid"),
            {"cid": case_id},
        ).first()
        return dict(row._mapping) if row else {}


def _snapshot_rows(case_id: int):
    with test_engine.connect() as conn:
        return [
            dict(r._mapping) for r in conn.execute(
                text("SELECT * FROM govt_status_snapshots WHERE case_id = :cid ORDER BY id"), {"cid": case_id},
            )
        ]


def _snapshot_field_rows(snapshot_id: int):
    with test_engine.connect() as conn:
        return [
            dict(r._mapping) for r in conn.execute(
                text("SELECT * FROM govt_status_snapshot_fields WHERE snapshot_id = :sid ORDER BY id"), {"sid": snapshot_id},
            )
        ]


def _snapshot_event_rows(case_id: int):
    with test_engine.connect() as conn:
        return [
            dict(r._mapping) for r in conn.execute(
                text("SELECT * FROM govt_status_snapshot_events WHERE case_id = :cid ORDER BY id"), {"cid": case_id},
            )
        ]


class _FakeAdapter:
    supports_unattended_status_check = True

    def __init__(self, result=None, exc: Exception | None = None):
        self._result = result
        self._exc = exc
        self.calls: list[tuple[str, int | None]] = []

    def check_status(self, reference_number, tenant_id=None):
        self.calls.append((reference_number, tenant_id))
        if self._exc is not None:
            raise self._exc
        return self._result


def _poller_row(case_id: int, tenant_id: int, portal_id: int, govt_status: str, reference: str,
                 status_check_adapter: str | None = None, portal_name: str = "Test Portal") -> dict:
    """Matches poll_all_pending()'s own SELECT column shape exactly."""
    return {
        "case_id": case_id, "tenant_id": tenant_id, "govt_status": govt_status,
        "govt_reference_number": reference, "govt_portal_id": portal_id, "portal_id": portal_id,
        "state": "TestState", "portal_name": portal_name, "portal_type": "state_branded",
        "base_url": "https://example.test", "status_check_url": "https://example.test/status",
        "status_check_mode": "login_required", "otp_bound": False,
        "status_check_adapter": status_check_adapter,
    }


# ─── 1. Successful check, NO status transition ──────────────────────────────

def test_A_on_demand_success_no_transition():
    _seed_database()
    result = StatusResult(status="submitted", checked=True, raw_portal_status="Registered")
    with patch("modules.govt_sync.adapters.get_adapter", return_value=_FakeAdapter(result)):
        resp = client.post("/api/cases/40/govt/poll", headers=_auth_headers())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["changed"] is False
    assert body["govt_status"] == "submitted"

    case = _case_row(40)
    assert case["govt_status"] == "submitted"
    assert case["govt_status_updated_at"] is None  # never touched when unchanged

    rows = _log_rows()
    assert len(rows) == 1
    assert rows[0]["action"] == "status_polled"
    assert rows[0]["actor_username"] == "mp_priya"  # real actor on the on-demand path
    payload = json.loads(rows[0]["payload"])
    assert payload == {
        "old_status": "submitted", "new_status": "submitted", "raw_portal_status": "Registered",
        "portal_detail": {}, "portal": "Test Portal", "changed": False,
    }

    snaps = _snapshot_rows(40)
    assert len(snaps) == 1  # snapshot persisted even when unchanged
    assert snaps[0]["normalized_status"] == "submitted"
    assert snaps[0]["created_by"] == "mp_priya"


def test_B_background_success_no_transition():
    _seed_database()
    result = StatusResult(status="submitted", checked=True, raw_portal_status="Registered")
    adapter = _FakeAdapter(result)
    row = _poller_row(40, 1, 1, "submitted", "REF/TEST/0001")
    with patch("modules.govt_sync.poller._q", return_value=[row]), \
         patch("modules.govt_sync.poller.get_adapter", return_value=adapter):
        summary = poller_mod.poll_all_pending()

    assert summary == {"pending": 1, "checked": 1, "changed": 0}
    case = _case_row(40)
    assert case["govt_status"] == "submitted"
    assert case["govt_status_updated_at"] is None

    rows = _log_rows()
    assert len(rows) == 1
    assert rows[0]["action"] == "status_polled"
    assert rows[0]["actor_username"] is None  # background never has a human actor
    payload = json.loads(rows[0]["payload"])
    assert payload == {
        "old_status": "submitted", "new_status": "submitted", "raw_portal_status": "Registered",
        "portal_detail": {}, "portal": "Test Portal", "changed": False,
    }

    snaps = _snapshot_rows(40)
    assert len(snaps) == 1
    assert snaps[0]["created_by"] is None


# ─── 2. Successful check, WITH status transition ────────────────────────────

def test_A_on_demand_success_with_transition():
    _seed_database()
    result = StatusResult(status="under_review", checked=True, raw_portal_status="Under review")
    with patch("modules.govt_sync.adapters.get_adapter", return_value=_FakeAdapter(result)):
        resp = client.post("/api/cases/40/govt/poll", headers=_auth_headers())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["changed"] is True
    assert body["govt_status"] == "under_review"

    case = _case_row(40)
    assert case["govt_status"] == "under_review"
    assert case["govt_status_updated_at"] is not None

    rows = _log_rows()
    assert len(rows) == 1 and rows[0]["action"] == "status_polled"
    payload = json.loads(rows[0]["payload"])
    assert payload["old_status"] == "submitted"
    assert payload["new_status"] == "under_review"
    assert payload["changed"] is True

    snaps = _snapshot_rows(40)
    assert len(snaps) == 1
    assert snaps[0]["normalized_status"] == "under_review"
    # First-ever snapshot for this case/portal/reference — no prior snapshot
    # to diff against, so no status_changed event yet (nothing to compare to).
    assert _snapshot_event_rows(40) == []


def test_B_background_success_with_transition():
    _seed_database()
    result = StatusResult(status="under_review", checked=True, raw_portal_status="Under review")
    row = _poller_row(40, 1, 1, "submitted", "REF/TEST/0001")
    with patch("modules.govt_sync.poller._q", return_value=[row]), \
         patch("modules.govt_sync.poller.get_adapter", return_value=_FakeAdapter(result)):
        summary = poller_mod.poll_all_pending()

    assert summary == {"pending": 1, "checked": 1, "changed": 1}
    case = _case_row(40)
    assert case["govt_status"] == "under_review"
    assert case["govt_status_updated_at"] is not None


def test_status_changed_event_fires_on_second_snapshot_when_status_differs():
    """Characterizes the event-diffing behavior shared by both callers —
    exercised once via the on-demand path (the mechanism is identical
    either way, since both funnel through the same status_snapshot.py)."""
    _seed_database()
    first = StatusResult(status="submitted", checked=True, raw_portal_status="Registered")
    second = StatusResult(status="under_review", checked=True, raw_portal_status="Under review")
    with patch("modules.govt_sync.adapters.get_adapter", return_value=_FakeAdapter(first)):
        client.post("/api/cases/40/govt/poll", headers=_auth_headers())
    with patch("modules.govt_sync.adapters.get_adapter", return_value=_FakeAdapter(second)):
        client.post("/api/cases/40/govt/poll", headers=_auth_headers())

    events = _snapshot_event_rows(40)
    assert len(events) == 1
    assert events[0]["event_type"] == "status_changed"
    assert events[0]["field_key"] == "status"
    assert events[0]["old_value_text"] == "submitted"
    assert events[0]["new_value_text"] == "under_review"


# ─── 3. Terminal transition ──────────────────────────────────────────────────

def test_A_on_demand_terminal_transition_to_resolved():
    _seed_database()
    with test_engine.begin() as conn:
        conn.execute(text("UPDATE cases SET govt_status = 'under_review' WHERE id = 40"))
    result = StatusResult(status="resolved", checked=True, raw_portal_status="Disposed")
    with patch("modules.govt_sync.adapters.get_adapter", return_value=_FakeAdapter(result)):
        resp = client.post("/api/cases/40/govt/poll", headers=_auth_headers())
    assert resp.status_code == 200
    assert resp.json()["changed"] is True
    assert resp.json()["govt_status"] == "resolved"
    assert _case_row(40)["govt_status"] == "resolved"
    # Resolution-review is a SEPARATE, staff-triggered endpoint — polling
    # a case to 'resolved' never itself writes a case_activity_log row or
    # touches cases.status. Not exercised further here; out of scope for
    # this extraction (resolution-review is explicitly excluded from
    # orchestrator.py's responsibilities).


def test_B_background_terminal_transition_to_resolved():
    _seed_database()
    with test_engine.begin() as conn:
        conn.execute(text("UPDATE cases SET govt_status = 'under_review' WHERE id = 40"))
    result = StatusResult(status="resolved", checked=True, raw_portal_status="Disposed")
    row = _poller_row(40, 1, 1, "under_review", "REF/TEST/0001")
    with patch("modules.govt_sync.poller._q", return_value=[row]), \
         patch("modules.govt_sync.poller.get_adapter", return_value=_FakeAdapter(result)):
        summary = poller_mod.poll_all_pending()
    assert summary["changed"] == 1
    assert _case_row(40)["govt_status"] == "resolved"


# ─── 4. checked=False (inconclusive) ────────────────────────────────────────

def test_A_on_demand_inconclusive_checked_false():
    _seed_database()
    result = StatusResult(status="", checked=False, raw_portal_status="Unrecognised page text")
    with patch("modules.govt_sync.adapters.get_adapter", return_value=_FakeAdapter(result)):
        resp = client.post("/api/cases/40/govt/poll", headers=_auth_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["changed"] is False
    assert body["govt_status"] == "submitted"  # unchanged, echoes existing
    assert body["note"] == "No status change detected. Please try again later."
    assert _case_row(40)["govt_status"] == "submitted"

    rows = _log_rows()
    assert len(rows) == 1
    assert rows[0]["action"] == "status_check_inconclusive"
    payload = json.loads(rows[0]["payload"])
    assert payload == {"portal": "Test Portal", "raw_portal_status": "Unrecognised page text"}  # exactly 2 keys

    assert _snapshot_rows(40) == []  # no snapshot for an inconclusive check


def test_failure_kinds_do_not_broaden_on_demand_snapshot_creation():
    for failure_kind in (
        StatusFailureKind.TIMEOUT,
        StatusFailureKind.NETWORK_FAILURE,
        StatusFailureKind.SESSION_EXPIRED,
        StatusFailureKind.UNKNOWN,
    ):
        _seed_database()
        result = StatusResult(status="", checked=False, failure_kind=failure_kind)
        with patch("modules.govt_sync.adapters.get_adapter", return_value=_FakeAdapter(result)):
            response = client.post("/api/cases/40/govt/poll", headers=_auth_headers())
        assert response.status_code == 200
        assert _snapshot_rows(40) == []


def test_tamil_nadu_successful_poll_snapshot_has_null_failure_kind():
    _seed_database()
    result = StatusResult(status="under_review", checked=True, raw_portal_status="Under Process")
    with patch("modules.govt_sync.adapters.get_adapter", return_value=_FakeAdapter(result)):
        response = client.post("/api/cases/41/govt/poll", headers=_auth_headers())

    assert response.status_code == 200
    snapshots = _snapshot_rows(41)
    assert len(snapshots) == 1
    assert snapshots[0]["adapter_key"] == "tamil_nadu_http_api"
    assert snapshots[0]["failure_kind"] is None


def test_B_background_inconclusive_checked_false():
    _seed_database()
    result = StatusResult(status="", checked=False, raw_portal_status="Unrecognised page text")
    row = _poller_row(40, 1, 1, "submitted", "REF/TEST/0001")
    with patch("modules.govt_sync.poller._q", return_value=[row]), \
         patch("modules.govt_sync.poller.get_adapter", return_value=_FakeAdapter(result)):
        summary = poller_mod.poll_all_pending()
    assert summary == {"pending": 1, "checked": 1, "changed": 0}
    assert _case_row(40)["govt_status"] == "submitted"

    rows = _log_rows()
    assert len(rows) == 1
    assert rows[0]["action"] == "status_check_inconclusive"
    payload = json.loads(rows[0]["payload"])
    # DIFFERENCE from on-demand: background's inconclusive payload carries
    # an extra govt_status_at_time key.
    assert payload == {
        "portal": "Test Portal", "raw_portal_status": "Unrecognised page text",
        "govt_status_at_time": "submitted",
    }
    assert _snapshot_rows(40) == []


# ─── 5. needs_verification=True ─────────────────────────────────────────────

def test_A_on_demand_needs_verification_rajasthan_note():
    _seed_database()
    result = StatusResult(status="", checked=False, needs_verification=True)
    with patch("modules.govt_sync.adapters.get_adapter", return_value=_FakeAdapter(result)):
        resp = client.post("/api/cases/40/govt/poll", headers=_auth_headers())  # portal 1, no status_check_adapter
    assert resp.status_code == 200
    body = resp.json()
    assert body["needs_verification"] is True
    assert body["changed"] is False
    assert "Rajasthan Sampark" in body["note"]

    rows = _log_rows()
    assert len(rows) == 1 and rows[0]["action"] == "status_check_needs_verification"
    payload = json.loads(rows[0]["payload"])
    assert payload == {"portal": "Test Portal", "raw_portal_status": None}
    assert _snapshot_rows(40) == []


def test_A_on_demand_needs_verification_tamil_nadu_note():
    _seed_database()
    result = StatusResult(status="", checked=False, needs_verification=True)
    with patch("modules.govt_sync.adapters.get_adapter", return_value=_FakeAdapter(result)):
        resp = client.post("/api/cases/41/govt/poll", headers=_auth_headers())  # portal 2 = tamil_nadu_http_api
    assert resp.status_code == 200
    assert "Tamil Nadu" in resp.json()["note"]


def test_B_background_needs_verification_and_skip_pairs():
    _seed_database()
    result = StatusResult(status="", checked=False, needs_verification=True)
    adapter = _FakeAdapter(result)
    # Two DIFFERENT cases (41, 42) sharing the SAME (tenant=1, portal=2) pair.
    row_a = _poller_row(41, 1, 2, "submitted", "TN/REF/0002", status_check_adapter="tamil_nadu_http_api", portal_name="TN Test Portal")
    row_b = _poller_row(42, 1, 2, "submitted", "TN/REF/0003", status_check_adapter="tamil_nadu_http_api", portal_name="TN Test Portal")
    with patch("modules.govt_sync.poller._q", return_value=[row_a, row_b]), \
         patch("modules.govt_sync.poller.get_adapter", return_value=adapter):
        summary = poller_mod.poll_all_pending()

    # Only the FIRST case in the pair actually invokes the adapter; the
    # second is skipped structurally once the pair is known to need
    # verification this run.
    assert len(adapter.calls) == 1
    assert summary["checked"] == 1  # the skipped second case is never counted as "checked"

    rows = _log_rows()
    assert len(rows) == 1  # no log row at all for the skipped second case
    assert rows[0]["action"] == "status_check_needs_verification"
    payload = json.loads(rows[0]["payload"])
    assert payload == {"portal": "TN Test Portal", "raw_portal_status": None, "govt_status_at_time": "submitted"}


# ─── 6. Adapter exception ────────────────────────────────────────────────────

def test_A_on_demand_adapter_exception_propagates():
    _seed_database()
    adapter = _FakeAdapter(exc=RuntimeError("portal is down"))
    with patch("modules.govt_sync.adapters.get_adapter", return_value=adapter):
        resp = client.post("/api/cases/40/govt/poll", headers=_auth_headers())
    # Characterizes CURRENT behavior: the exception is not caught by the
    # route handler (only logged, then re-raised) — FastAPI's default
    # handler turns it into a 500.
    assert resp.status_code == 500
    assert _log_rows() == []  # no audit row written when the adapter itself raised
    assert _snapshot_rows(40) == []
    assert _case_row(40)["govt_status"] == "submitted"  # never fabricated


def test_B_background_adapter_exception_does_not_abort_batch():
    _seed_database()
    failing_adapter = _FakeAdapter(exc=RuntimeError("portal is down"))
    ok_result = StatusResult(status="under_review", checked=True, raw_portal_status="Under review")

    row_fail = _poller_row(40, 1, 1, "submitted", "REF/TEST/0001")
    row_ok = _poller_row(43, 2, 1, "submitted", "REF/OTHER/0001")

    def _pick_adapter(row):
        return failing_adapter if row["case_id"] == 40 else _FakeAdapter(ok_result)

    with patch("modules.govt_sync.poller._q", return_value=[row_fail, row_ok]), \
         patch("modules.govt_sync.poller.get_adapter", side_effect=_pick_adapter):
        summary = poller_mod.poll_all_pending()

    # The failing case does not stop the batch; the second case still
    # gets processed and counted.
    assert summary["pending"] == 2
    assert summary["checked"] == 1  # only the non-raising case counts
    assert summary["changed"] == 1
    assert _case_row(40)["govt_status"] == "submitted"  # untouched, not fabricated
    assert _case_row(43)["govt_status"] == "under_review"
    assert _log_rows() == [r for r in _log_rows() if r["case_id"] == 43]  # only case 43 logged anything


# ─── 7. Unsupported unattended adapter ──────────────────────────────────────

def test_B_background_skips_non_unattended_adapter_structurally():
    _seed_database()
    adapter = _FakeAdapter(StatusResult(status="under_review", checked=True))
    adapter.supports_unattended_status_check = False
    row = _poller_row(40, 1, 1, "submitted", "REF/TEST/0001")
    with patch("modules.govt_sync.poller._q", return_value=[row]), \
         patch("modules.govt_sync.poller.get_adapter", return_value=adapter):
        summary = poller_mod.poll_all_pending()

    assert adapter.calls == []  # check_status() never invoked
    assert summary == {"pending": 1, "checked": 0, "changed": 0}
    assert _log_rows() == []
    assert _case_row(40)["govt_status"] == "submitted"


def test_A_on_demand_calls_adapter_even_when_not_unattended_capable():
    """Genuine, real asymmetry: the on-demand endpoint has no
    supports_unattended_status_check gate at all — a staff-triggered click
    always invokes check_status(), even for an interactive-only adapter."""
    _seed_database()
    adapter = _FakeAdapter(StatusResult(
        status="", checked=False,
        raw_portal_status="This portal needs a live, staff-present interactive check — see status_flow.start().",
    ))
    adapter.supports_unattended_status_check = False
    with patch("modules.govt_sync.adapters.get_adapter", return_value=adapter):
        resp = client.post("/api/cases/40/govt/poll", headers=_auth_headers())
    assert resp.status_code == 200
    assert len(adapter.calls) == 1  # DID call check_status(), unlike the background path
    assert _log_rows()[0]["action"] == "status_check_inconclusive"


# ─── 8. Tenant isolation ─────────────────────────────────────────────────────

def test_A_on_demand_cannot_poll_another_tenants_case():
    _seed_database()
    with patch("modules.govt_sync.adapters.get_adapter", return_value=_FakeAdapter(StatusResult(status="resolved", checked=True))):
        resp = client.post("/api/cases/43/govt/poll", headers=_auth_headers("mp_priya"))  # case 43 belongs to tenant 2
    assert resp.status_code == 404
    assert _case_row(43)["govt_status"] == "submitted"
    assert _log_rows() == []
    assert _snapshot_rows(43) == []


def test_B_background_batch_writes_stay_scoped_to_each_rows_own_tenant():
    _seed_database()
    result_t1 = StatusResult(status="under_review", checked=True, raw_portal_status="Under review")
    result_t2 = StatusResult(status="resolved", checked=True, raw_portal_status="Disposed")
    row_t1 = _poller_row(40, 1, 1, "submitted", "REF/TEST/0001")
    row_t2 = _poller_row(43, 2, 1, "submitted", "REF/OTHER/0001")

    def _pick_result(row):
        return _FakeAdapter(result_t1 if row["tenant_id"] == 1 else result_t2)

    with patch("modules.govt_sync.poller._q", return_value=[row_t1, row_t2]), \
         patch("modules.govt_sync.poller.get_adapter", side_effect=_pick_result):
        summary = poller_mod.poll_all_pending()

    assert summary["changed"] == 2
    assert _case_row(40)["tenant_id"] == 1 and _case_row(40)["govt_status"] == "under_review"
    assert _case_row(43)["tenant_id"] == 2 and _case_row(43)["govt_status"] == "resolved"
    rows = _log_rows()
    assert {r["tenant_id"] for r in rows} == {1, 2}
    assert {r["case_id"]: r["tenant_id"] for r in rows} == {40: 1, 43: 2}


# ─── 9. Reference-number prerequisite ───────────────────────────────────────

def test_A_on_demand_rejects_case_without_reference_number():
    _seed_database()
    with test_engine.begin() as conn:
        conn.execute(text("UPDATE cases SET govt_reference_number = NULL WHERE id = 40"))
    adapter = _FakeAdapter(StatusResult(status="under_review", checked=True))
    with patch("modules.govt_sync.adapters.get_adapter", return_value=adapter):
        resp = client.post("/api/cases/40/govt/poll", headers=_auth_headers())
    assert resp.status_code == 400
    assert "reference number" in resp.json()["detail"].lower()
    assert adapter.calls == []
    assert _log_rows() == []
    # NOTE: background's equivalent enforcement is a SQL WHERE clause
    # (`govt_reference_number IS NOT NULL`) in poll_all_pending()'s own
    # SELECT, not application logic — such a case is simply never selected
    # into the batch, so there is no analogous "reject" branch to exercise
    # via a mocked-row test; the SQL text itself is the enforcement point
    # and is untouched by this extraction.


# ─── 10. Status snapshot payload fidelity ───────────────────────────────────

def test_snapshot_persists_raw_normalized_reference_and_portal_identity_exactly():
    _seed_database()
    result = StatusResult(
        status="under_review", checked=True, raw_portal_status="Under review at department",
        portal_detail={"department_name": "Water Board", "pendency_details": "With field officer"},
    )
    with patch("modules.govt_sync.adapters.get_adapter", return_value=_FakeAdapter(result)):
        resp = client.post("/api/cases/40/govt/poll", headers=_auth_headers())
    assert resp.status_code == 200

    snaps = _snapshot_rows(40)
    assert len(snaps) == 1
    snap = snaps[0]
    assert snap["tenant_id"] == 1
    assert snap["portal_id"] == 1
    assert snap["reference_number"] == "REF/TEST/0001"
    assert snap["raw_status"] == "Under review at department"
    assert snap["normalized_status"] == "under_review"
    assert snap["snapshot_status"] == "complete"

    fields = {f["field_key"]: f for f in _snapshot_field_rows(snap["id"])}
    assert fields["status"]["value_text"] == "under_review"
    assert fields["department"]["value_text"] == "Water Board"
    assert fields["current_position"]["value_text"] == "With field officer"
