"""Case-status lifecycle: evidence-based transitions (modules/case_lifecycle.py).

Pins the approved lifecycle:
  * only verified external evidence (a recorded government filing, or a
    successful portal check returning an open, in-flight status) moves an
    eligible case to in_progress automatically — on every check path;
  * triage, assignment, AI worksheet preparation and viewing never do;
  * terminal/lane states are never moved, transitions are atomic,
    idempotent, tenant-scoped and audited;
  * a portal-reported resolution never resolves a case — it raises the
    derived resolution_verification flag, per resolution round.
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from tests.auth_token_claims import identity_claims


TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
TEST_DB_URL = "sqlite:///./test_case_status_lifecycle.db"

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


import admin_api
import api_router
import core.db_helpers as db_helpers
import main
import sansadx_backend.db as dbmod
from sansadx_backend.db import Base, hash_password

from modules import case_lifecycle
from modules.govt_sync import poller as poller_mod
from modules.govt_sync.adapters.base import StatusResult
from modules.govt_sync.adapters.status_flow import StatusCheckAttemptState
from modules.govt_sync.status.base import StatusCheckResult, StatusCheckState


test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False)
client = TestClient(main.app, raise_server_exceptions=False)

ELIGIBLE = sorted(case_lifecycle.AUTO_PROGRESS_ELIGIBLE)
PROTECTED = ["resolved", "completed", "closed", "irrelevant", "offensive", "case_comment"]


def _bind_engines():
    dbmod.engine = test_engine
    dbmod.SessionLocal = TestSession
    db_helpers.engine = test_engine
    main.engine = test_engine
    api_router.engine = test_engine
    admin_api.engine = test_engine
    poller_mod.engine = test_engine
    api_router.JWT_SECRET = TEST_JWT_SECRET
    admin_api.JWT_SECRET = TEST_JWT_SECRET


def _auth(username: str = "mp_arun") -> dict:
    token = jwt.encode(
        {
            "sub": username, **identity_claims(test_engine, username),
            "exp": _utcnow() + timedelta(hours=8),
            "iat": _utcnow().timestamp(),
        },
        TEST_JWT_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def seeded():
    _bind_engines()
    Base.metadata.create_all(bind=test_engine)
    now = _utcnow()
    with test_engine.begin() as conn:
        for table_name in (
            "govt_submission_log", "case_activity_log", "case_media", "cases", "govt_portals",
            "tenant_overrides", "token_blocklist", "users", "tenant_profiles", "tenants",
        ):
            conn.execute(text(f"DELETE FROM {table_name}"))  # nosec B608
        for tid, name, constituency, state, username in (
            (1, "Arun Kumar", "Bangalore North", "Karnataka", "mp_arun"),
            (2, "Priya Sharma", "Kalyan Dombivli", "Maharashtra", "mp_priya"),
        ):
            conn.execute(text(
                "INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active, created_at) "
                "VALUES (:id, :name, :c, :wa, 'Pro', 1, :now)"
            ), {"id": tid, "name": name, "c": constituency, "wa": f"+91900000000{tid}", "now": now})
            conn.execute(text(
                "INSERT INTO tenant_profiles (tenant_id, mp_name, constituency, state, house, created_at) "
                "VALUES (:id, :name, :c, :state, 'Lok Sabha', :now)"
            ), {"id": tid, "name": name, "c": constituency, "state": state, "now": now})
            conn.execute(text(
                "INSERT INTO users (tenant_id, username, password_hash, role, constituency, house, display_name, is_active) "
                "VALUES (:id, :u, :pw, 'mp', :c, 'Lok Sabha', :u, 1)"
            ), {"id": tid, "u": username, "pw": hash_password("Password1"), "c": constituency})
        conn.execute(text(
            "INSERT INTO govt_portals (id, state, portal_name, portal_type, base_url, status_check_mode, "
            "department_taxonomy, field_schema, otp_bound, active, is_primary, verification_status, "
            "live_session_supported) VALUES (1, 'Karnataka', 'Karnataka iPGRS', 'state_branded', "
            "'https://example.portal/file', 'login_required', :tax, :schema, 0, 1, 1, 'confirmed', 1)"
        ), {"tax": json.dumps({"Water": "Water"}), "schema": json.dumps({})})
    yield


def _case(case_id, *, tenant_id=1, status="new", govt_status="not_forwarded", ref=None, portal=1,
          is_critical=False, priority="standard", category="Infrastructure & Utilities",
          govt_status_updated_at=None):
    with test_engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO cases (id, tenant_id, user_phone, raw_message, category, status, created_at, "
            "govt_portal_id, govt_status, govt_reference_number, govt_submission_worksheet, is_deleted, "
            "is_critical, priority, govt_status_updated_at) VALUES (:id, :tid, :phone, 'No water for days', "
            ":cat, :st, :now, :portal, :gs, :ref, :ws, 0, :crit, :prio, :gsu)"
        ), {
            "id": case_id, "tid": tenant_id, "phone": f"+91911111{case_id:04d}", "cat": category,
            "st": status, "now": _utcnow(), "portal": portal, "gs": govt_status, "ref": ref,
            "ws": json.dumps({"department": "BBMP"}), "crit": is_critical, "prio": priority,
            "gsu": govt_status_updated_at,
        })


def _row(case_id):
    with test_engine.connect() as conn:
        return dict(conn.execute(text(
            "SELECT status, govt_status, govt_reference_number, is_critical, priority, category "
            "FROM cases WHERE id = :cid"
        ), {"cid": case_id}).mappings().one())


def _status_changes(case_id):
    with test_engine.connect() as conn:
        return [dict(r) for r in conn.execute(text(
            "SELECT username, old_value, new_value, details FROM case_activity_log "
            "WHERE case_id = :cid AND action = 'status_change' ORDER BY id"
        ), {"cid": case_id}).mappings()]


class _PollAdapter:
    supports_unattended_status_check = True

    def __init__(self, result):
        self._result = result

    def check_status(self, reference_number, tenant_id=None):
        return self._result


class _InteractiveAdapter:
    def __init__(self, result):
        self._result = result

    def advance(self, attempt, answers):
        attempt.state = StatusCheckAttemptState.COMPLETE
        attempt.result = self._result
        return attempt


def _poll(case_id, govt_status, checked=True):
    result = StatusResult(status=govt_status, checked=checked, raw_portal_status=govt_status or "?")
    with patch("modules.govt_sync.adapters.get_adapter", return_value=_PollAdapter(result)):
        return client.post(f"/api/cases/{case_id}/govt/poll", headers=_auth())


# ── 4. Non-progress actions never move status ──────────────────────────────

def test_viewing_assigning_categorising_following_and_worksheet_prep_never_start_progress():
    _case(1, status="new", category="Uncategorised")
    headers = _auth()

    assert client.get("/api/cases/1", headers=headers).status_code == 200
    assert client.get("/api/cases", headers=headers).status_code == 200
    assert client.get("/api/cases/filter-options", headers=headers).status_code == 200
    assert client.patch("/api/cases/1", headers=headers, json={"assigned_to": "mp_arun"}).status_code == 200
    assert client.patch(
        "/api/cases/1", headers=headers, json={"problem_domain": "Infrastructure & Utilities"}
    ).status_code == 200
    assert client.post("/api/cases/1/follow", headers=headers).status_code == 200
    with patch("modules.govt_sync.translator.translate_for_portal",
               return_value={"department": "Water", "subject": "Water", "description": "No water"}):
        assert client.post("/api/cases/1/govt/translate", headers=headers).status_code == 200

    row = _row(1)
    assert row["status"] == "new"
    assert row["govt_status"] == "pending_staff_submit"  # prepared, NOT filed
    assert _status_changes(1) == []


# ── 5. Recorded filing starts progress for every eligible status ───────────

@pytest.mark.parametrize("status", ELIGIBLE)
def test_recorded_filing_moves_each_eligible_status_to_in_progress(status):
    _case(2, status=status, govt_status="pending_staff_submit")

    resp = client.post("/api/cases/2/govt/submit", headers=_auth(), json={"reference_number": "KA-1001"})

    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "in_progress"
    row = _row(2)
    assert row["status"] == "in_progress"
    assert row["govt_status"] == "submitted"
    changes = _status_changes(2)
    assert len(changes) == 1
    assert changes[0]["username"] == "system:govt_filing_recorded"
    assert changes[0]["old_value"] == status
    assert json.loads(changes[0]["details"])["evidence"] == "govt_filing_recorded"


def test_emergency_case_keeps_priority_and_critical_flag_when_filing_starts_progress():
    _case(3, status="emergency", govt_status="pending_staff_submit", is_critical=True,
          priority="critical", category="Emergency")

    resp = client.post("/api/cases/3/govt/submit", headers=_auth(), json={"reference_number": "KA-EMG-1"})

    assert resp.status_code == 200, resp.text
    row = _row(3)
    assert row["status"] == "in_progress"
    assert row["is_critical"] in (True, 1)
    assert row["priority"] == "critical"
    assert row["category"] == "Emergency"


def test_repeated_evidence_is_idempotent():
    _case(4, status="new", govt_status="pending_staff_submit")
    headers = _auth()
    assert client.post("/api/cases/4/govt/submit", headers=headers, json={"reference_number": "KA-9"}).status_code == 200
    again = client.post("/api/cases/4/govt/submit", headers=headers, json={"reference_number": "KA-9"})
    assert again.status_code == 200 and again.json().get("idempotent") is True
    assert _poll(4, "under_review").status_code == 200

    assert _row(4)["status"] == "in_progress"
    assert len(_status_changes(4)) == 1


# ── 6. Failed filing / failed or inconclusive checks change nothing ────────

def test_failed_filing_attempts_never_start_progress():
    _case(5, status="new", govt_status="pending_staff_submit")
    _case(6, status="new", govt_status="not_forwarded", portal=None)
    _case(7, status="new", govt_status="submitted", ref="KEEP-ME")
    headers = _auth()

    assert client.post("/api/cases/5/govt/submit", headers=headers, json={"reference_number": "  "}).status_code == 400
    assert client.post("/api/cases/6/govt/submit", headers=headers, json={"reference_number": "X-1"}).status_code == 400
    assert client.post("/api/cases/7/govt/submit", headers=headers, json={"reference_number": "OTHER"}).status_code == 409

    for case_id in (5, 6, 7):
        assert _row(case_id)["status"] == "new"
        assert _status_changes(case_id) == []
    assert _row(5)["govt_status"] == "pending_staff_submit"


def test_inconclusive_portal_check_never_starts_progress():
    _case(8, status="new", govt_status="submitted", ref="KA-8")

    resp = _poll(8, "", checked=False)

    assert resp.status_code == 200, resp.text
    assert _row(8)["status"] == "new"
    assert _status_changes(8) == []


# ── 7. Successful portal checks: same rule on every path ───────────────────

@pytest.mark.parametrize("govt_status, moves", [
    ("submitted", True), ("under_review", True),
    ("resolved", False), ("disposed", False), ("rejected", False),
])
def test_on_demand_poll_applies_portal_confirmation_rule(govt_status, moves):
    _case(9, status="new", govt_status="submitted", ref="KA-9")

    assert _poll(9, govt_status).status_code == 200

    assert _row(9)["status"] == ("in_progress" if moves else "new")
    changes = _status_changes(9)
    assert len(changes) == (1 if moves else 0)
    if moves:
        assert changes[0]["username"] == "system:govt_portal_confirmed"


@pytest.mark.parametrize("govt_status, moves", [("under_review", True), ("resolved", False)])
def test_interactive_status_check_applies_portal_confirmation_rule(govt_status, moves):
    _case(10, status="awaiting_location", govt_status="submitted", ref="KA-10")
    adapter = _InteractiveAdapter(StatusResult(status=govt_status, checked=True, raw_portal_status=govt_status))

    with patch("modules.govt_sync.adapters.get_adapter", return_value=adapter):
        resp = client.post("/api/cases/10/govt/status-check/att-1/advance", headers=_auth(), json={"captcha": "AB12"})

    assert resp.status_code == 200, resp.text
    assert _row(10)["status"] == ("in_progress" if moves else "awaiting_location")
    assert len(_status_changes(10)) == (1 if moves else 0)


@pytest.mark.parametrize("normalized, moves", [("under_review", True), ("resolved", False)])
def test_tamil_nadu_live_check_applies_portal_confirmation_rule(normalized, moves):
    _case(11, status="pending_review", govt_status="submitted", ref="TN-11")
    case_row = {"id": 11, "govt_status": "submitted", "govt_reference_number": "TN-11", "portal_name": "TN"}

    class _TNAdapter:
        async def check_status_on_page(self, page, reference_number):
            return StatusCheckResult(state=StatusCheckState.STATUS_CHECKED, normalized_status=normalized,
                                     raw_detail_status=normalized)

    session = SimpleNamespace(portal={"portal_name": "TN"}, page=None)
    with patch.object(api_router, "_get_tamil_nadu_live_status_context",
                      return_value=(1, session, case_row, _TNAdapter(), "TN-11")):
        resp = client.post("/api/cases/11/govt/session/s-1/tamil-nadu/check-status", headers=_auth())

    assert resp.status_code == 200, resp.text
    assert _row(11)["status"] == ("in_progress" if moves else "pending_review")
    assert len(_status_changes(11)) == (1 if moves else 0)


def test_every_portal_status_write_applies_the_shared_evidence_rule():
    """Structural guard: any code path that writes cases.govt_status from a
    portal check must apply apply_portal_confirmation in the same block."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for rel in ("api_router.py", "modules/govt_sync/orchestrator.py"):
        lines = open(os.path.join(root, rel), encoding="utf-8").read().splitlines()
        for i, line in enumerate(lines):
            if "UPDATE cases SET govt_status = :status" in line:
                window = "\n".join(lines[i: i + 25])
                assert "apply_portal_confirmation" in window, f"{rel}:{i + 1} skips the evidence rule"


# ── 8. Portal resolution never resolves; verification is per round ────────

def test_portal_resolution_raises_verification_without_resolving_across_rounds():
    _case(12, status="in_progress", govt_status="submitted", ref="KA-12")
    headers = _auth()

    assert _poll(12, "resolved").status_code == 200
    detail = client.get("/api/cases/12", headers=headers).json()
    assert detail["status"] == "in_progress"
    assert detail["resolution_verification"] == "pending"
    assert client.get("/api/cases/filter-options", headers=headers).json()["resolution_verification_pending"] == 1

    review = client.post("/api/cases/12/govt/resolution-review", headers=headers,
                         json={"decision": "continue_follow_up"})
    assert review.status_code == 200, review.text
    assert client.get("/api/cases/12", headers=headers).json()["resolution_verification"] == "reviewed"
    listed = next(c for c in client.get("/api/cases", headers=headers).json()["cases"] if c["id"] == 12)
    assert listed["resolution_verification"] == "reviewed"
    assert client.get("/api/cases/filter-options", headers=headers).json()["resolution_verification_pending"] == 0

    # Portal re-opens, then resolves again: a NEW round needs verification again.
    assert _poll(12, "under_review").status_code == 200
    assert client.get("/api/cases/12", headers=headers).json()["resolution_verification"] is None
    with test_engine.begin() as conn:  # distinct cycle marker for the new round
        conn.execute(text("UPDATE cases SET govt_status_updated_at = :t WHERE id = 12"),
                     {"t": _utcnow() - timedelta(seconds=5)})
    assert _poll(12, "resolved").status_code == 200
    detail = client.get("/api/cases/12", headers=headers).json()
    assert detail["resolution_verification"] == "pending"
    assert detail["status"] == "in_progress"
    assert all(c["new_value"] != "resolved" for c in _status_changes(12))

    # Staff resolving the case clears the flag.
    assert client.patch("/api/cases/12/status", headers=headers, json={"status": "resolved"}).status_code == 200
    assert client.get("/api/cases/12", headers=headers).json()["resolution_verification"] is None


# ── 9. Protected states never move ─────────────────────────────────────────

@pytest.mark.parametrize("status", PROTECTED)
def test_evidence_never_moves_protected_statuses(status):
    _case(13, status=status, govt_status="pending_staff_submit")

    assert client.post("/api/cases/13/govt/submit", headers=_auth(), json={"reference_number": "KA-13"}).status_code == 200
    assert _poll(13, "under_review").status_code == 200

    row = _row(13)
    assert row["status"] == status
    assert row["govt_reference_number"] == "KA-13"  # filing itself still recorded
    assert _status_changes(13) == []


# ── 10. Concurrency: compare-and-set never overwrites a newer status ───────

def test_evidence_does_not_overwrite_a_concurrent_staff_resolution():
    """Simulates the race deterministically: the evidence path observed 'new',
    but staff resolved the case before its conditional UPDATE ran."""
    _case(14, status="new", govt_status="submitted", ref="KA-14")

    class _StaleReadConn:
        def __init__(self, conn):
            self._conn = conn
            self._first = True

        def execute(self, statement, params=None):
            if self._first:
                self._first = False
                result = self._conn.execute(statement, params)
                self._conn.execute(text("UPDATE cases SET status = 'resolved' WHERE id = 14"))
                return result
            return self._conn.execute(statement, params)

    with test_engine.begin() as conn:
        moved = case_lifecycle.apply_external_evidence(
            _StaleReadConn(conn), tenant_id=1, case_id=14,
            evidence=case_lifecycle.EVIDENCE_GOVT_PORTAL_CONFIRMED,
        )

    assert moved is False
    assert _row(14)["status"] == "resolved"
    assert _status_changes(14) == []


def test_unknown_evidence_type_is_rejected():
    _case(15, status="new")
    with test_engine.begin() as conn:
        with pytest.raises(ValueError):
            case_lifecycle.apply_external_evidence(conn, tenant_id=1, case_id=15, evidence="ai_classified")
    assert _row(15)["status"] == "new"


# ── 11. Tenant isolation ───────────────────────────────────────────────────

def test_cross_tenant_status_and_evidence_writes_change_nothing():
    _case(16, status="new", govt_status="pending_staff_submit")
    other = _auth("mp_priya")

    assert client.patch("/api/cases/16/status", headers=other, json={"status": "in_progress"}).status_code == 404
    assert client.post("/api/cases/16/govt/submit", headers=other, json={"reference_number": "X"}).status_code == 404
    with test_engine.begin() as conn:
        assert case_lifecycle.apply_external_evidence(
            conn, tenant_id=2, case_id=16, evidence=case_lifecycle.EVIDENCE_GOVT_FILING_RECORDED
        ) is False

    row = _row(16)
    assert row["status"] == "new" and row["govt_reference_number"] is None
    assert _status_changes(16) == []


# ── 12. Manual and bulk corrections share one validation ───────────────────

def test_manual_and_bulk_status_changes_are_validated_and_audited():
    for case_id in (17, 18, 19):
        _case(case_id, status="in_progress")
    headers = _auth()

    # Bulk = the same endpoint per selected case (frontend bulkStatusChange).
    for case_id in (17, 18):
        assert client.patch(f"/api/cases/{case_id}/status", headers=headers, json={"status": "new"}).status_code == 200
    assert client.patch("/api/cases/19/status", headers=headers, json={"status": "escalated"}).status_code == 200
    for bad in ("bogus", "contact_buffered", ""):
        assert client.patch("/api/cases/19/status", headers=headers, json={"status": bad}).status_code == 400

    assert _row(17)["status"] == "new" and _row(18)["status"] == "new"
    assert _row(19)["status"] == "in_progress"  # escalated alias normalized
    change = _status_changes(17)[-1]
    assert change["username"] == "mp_arun" and change["new_value"] == "new"
    assert _status_changes(19) == []  # alias to the same value is not a change


# ── 13. Background poller starts progress without staff ────────────────────

def test_background_poller_moves_filed_eligible_case_without_staff():
    _case(20, status="new", govt_status="submitted", ref="KA-20")
    _case(21, status="closed", govt_status="submitted", ref="KA-21")
    rows = [
        {"case_id": cid, "tenant_id": 1, "govt_status": "submitted", "govt_reference_number": ref,
         "govt_portal_id": 1, "portal_id": 1, "state": "Karnataka", "portal_name": "Karnataka iPGRS",
         "portal_type": "state_branded", "base_url": "https://example.portal/file",
         "status_check_url": None, "status_check_mode": "login_required", "otp_bound": 0,
         "status_check_adapter": None}
        for cid, ref in ((20, "KA-20"), (21, "KA-21"))
    ]
    result = StatusResult(status="under_review", checked=True, raw_portal_status="Under review")

    # Only the Postgres-only selection query is stubbed; adapter dispatch,
    # persistence and the evidence rule run for real.
    with patch.object(poller_mod, "_q", return_value=rows), \
            patch.object(poller_mod, "get_adapter", return_value=_PollAdapter(result)):
        summary = poller_mod.poll_all_pending()

    assert summary["checked"] == 2
    assert _row(20)["status"] == "in_progress"
    assert _row(21)["status"] == "closed"
    change = _status_changes(20)
    assert len(change) == 1 and change[0]["username"] == "system:govt_portal_confirmed"
    assert json.loads(change[0]["details"])["actor"] == "background_poller"


# ── 14. Counts reflect stored status; derived count is consistent ──────────

def test_briefcase_counts_match_database_and_derived_flag():
    _case(22, status="new")
    _case(23, status="new")
    _case(24, status="in_progress", govt_status="resolved", ref="KA-24",
          govt_status_updated_at=_utcnow())
    _case(25, status="resolved", govt_status="resolved", ref="KA-25",
          govt_status_updated_at=_utcnow())
    _case(26, tenant_id=2, status="in_progress", govt_status="resolved", ref="MH-26", portal=None,
          govt_status_updated_at=_utcnow())

    payload = client.get("/api/cases/filter-options", headers=_auth()).json()

    with test_engine.connect() as conn:
        expected = {r[0]: r[1] for r in conn.execute(text(
            "SELECT status, COUNT(*) FROM cases WHERE tenant_id = 1 GROUP BY status"
        ))}
    assert {s["value"]: s["count"] for s in payload["statuses"]} == expected
    assert payload["resolution_verification_pending"] == 1  # 24 only; 25 resolved, 26 other tenant


# ── module-level rule checks ───────────────────────────────────────────────

def test_resolution_verification_rules():
    filed = {"govt_reference_number": "R", "govt_status": "resolved", "status": "in_progress",
             "govt_status_updated_at": "2026-10-01T10:00:00"}
    marker = case_lifecycle.cycle_marker(filed["govt_status_updated_at"])
    assert case_lifecycle.resolution_verification(filed) == "pending"
    assert case_lifecycle.resolution_verification(filed, {marker}) == "reviewed"
    assert case_lifecycle.resolution_verification(filed, {"2026-09-01T00:00:00Z"}) == "pending"
    assert case_lifecycle.resolution_verification({**filed, "status": "closed"}) is None
    assert case_lifecycle.resolution_verification({**filed, "govt_status": "rejected"}) is None
    assert case_lifecycle.resolution_verification(
        {"govt_status": "pending_staff_submit", "status": "new"}
    ) is None
    assert case_lifecycle.cycle_marker(datetime(2026, 10, 1, 10, 0)) == marker
