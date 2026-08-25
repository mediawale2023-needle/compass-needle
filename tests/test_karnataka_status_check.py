"""
tests/test_karnataka_status_check.py — Karnataka iPGRS interactive
status-check adapter.

Two layers, matching the project's established pattern for govt_sync
adapters (see tests/test_govt_duplicate_filing.py for the same TestClient +
SQLite harness):

  A. Pure adapter unit tests — KarnatakaAPIAdapter.start()/advance() called
     directly, requests.Session mocked. No live network call, ever.
  B. Endpoint-level tests — the real /status-check/start + /advance routes
     through TestClient, same mocking underneath.
  C. Poller-exclusion + registration/MRO sanity.

Never solves/OCRs a real CAPTCHA, never hits the live portal — every HTTP
call in this file is mocked. The exact request field names and response
shape below are the real, confirmed contract (read from
ipgrs.karnataka.gov.in's own inline JavaScript — see
modules/govt_sync/adapters/karnataka_ipgrs.py's module docstring), not
invented for the test.
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
TEST_DB_URL = "sqlite:///./test_karnataka_status_check.db"

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
from sansadx_backend.db import Base, hash_password

from modules.govt_sync.adapters import KarnatakaAPIAdapter, get_adapter
from modules.govt_sync.adapters.base import OtpGatedStatusMixin, StatusResult
from modules.govt_sync.adapters.manual import ManualAssistedAdapter
from modules.govt_sync.adapters.rajasthan_sampark import RajasthanSamparkAPIAdapter
from modules.govt_sync.adapters.status_flow import (
    InteractiveStatusCheckMixin,
    StatusCheckAttempt,
    StatusCheckAttemptState,
    TransportKind,
)

test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False)
client = TestClient(main.app, raise_server_exceptions=False)

_REAL_SUCCESS_PAYLOAD = {
    "success": True,
    "message": None,
    "data": {
        "GrievanceId": "372414",
        "DateOfRegistration": "22-08-2026",
        "Department": "Urban Development Department",
        "Category": "Directorate of Municipal Administration (DMA)",
        "Description": "information not available on webiste",
        "IsClosed": False,
        "PendencyDetails": "S A Mahajan — Municipal Commissioner, Gokak",
        "Status": "Registered & Sent for Scrutiny",
    },
}


def _bind_engines():
    dbmod.engine = test_engine
    dbmod.SessionLocal = TestSession
    db_helpers.engine = test_engine
    main.engine = test_engine
    api_router.engine = test_engine
    api_router.JWT_SECRET = TEST_JWT_SECRET


def _auth_headers(username: str = "mp_arun") -> dict[str, str]:
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
        for table_name in ("govt_submission_log", "case_activity_log", "cases", "govt_portals",
                            "tenant_overrides", "token_blocklist", "users", "tenant_profiles", "tenants"):
            conn.execute(text(f"DELETE FROM {table_name}"))  # nosec B608

        conn.execute(text(
            "INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active, "
            "created_at, govt_contact_primary_number) VALUES "
            "(1, 'Arun Kumar', 'Bangalore North', '+919000000001', 'Pro', 1, :now, '919876500001')"
        ), {"now": now})
        conn.execute(text(
            "INSERT INTO tenant_profiles (tenant_id, mp_name, constituency, state, house, created_at) "
            "VALUES (1, 'Shri Arun Kumar', 'Bangalore North', 'Karnataka', 'Lok Sabha', :now)"
        ), {"now": now})
        conn.execute(text(
            "INSERT INTO users (tenant_id, username, password_hash, role, constituency, house, display_name, is_active) "
            "VALUES (1, 'mp_arun', :password_hash, 'mp', 'Bangalore North', 'Lok Sabha', 'Arun MP', 1)"
        ), {"password_hash": hash_password("Password1")})
        conn.execute(text(
            "INSERT INTO govt_portals (id, state, portal_name, portal_type, base_url, status_check_mode, "
            "department_taxonomy, field_schema, otp_bound, active, is_primary, verification_status, "
            "live_session_supported, status_check_adapter) VALUES "
            "(1, 'Karnataka', 'Karnataka Janaspandana (iPGRS)', 'state_branded', 'https://ipgrs.karnataka.gov.in', "
            "'login_required', :taxonomy, :schema, 1, 1, 1, 'confirmed', 1, 'karnataka_ipgrs_api')"
        ), {"taxonomy": json.dumps({"Infrastructure & Utilities": "Urban Development Department"}), "schema": json.dumps({})})
        conn.execute(text(
            "INSERT INTO cases (id, tenant_id, user_phone, raw_message, category, status, created_at, "
            "govt_portal_id, govt_status, govt_reference_number, is_deleted) VALUES "
            "(20, 1, '+919111111120', 'Pothole outside my house', 'Infrastructure & Utilities', 'in_progress', :now, "
            "1, 'submitted', '372414', 0)"
        ), {"now": now})


def _mock_captcha_response():
    resp = MagicMock()
    resp.headers = {"Content-Type": "image/png"}
    resp.content = b"\x89PNG-fake-bytes"
    resp.raise_for_status = MagicMock()
    return resp


def _mock_verify_response(payload):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value=payload)
    return resp


# ─── A. Pure adapter unit tests ─────────────────────────────────────────

def test_adapter_supports_unattended_status_check_is_false():
    adapter = KarnatakaAPIAdapter({"id": 1, "portal_name": "Karnataka Janaspandana (iPGRS)"})
    assert adapter.supports_unattended_status_check is False


def test_adapter_mro_check_status_from_mixin_prepare_submission_from_manual():
    assert type(KarnatakaAPIAdapter.__mro__[1]) is type
    assert KarnatakaAPIAdapter.check_status.__qualname__.startswith("InteractiveStatusCheckMixin.")
    assert KarnatakaAPIAdapter.prepare_submission.__qualname__.startswith("ManualAssistedAdapter.")
    adapter = KarnatakaAPIAdapter({"id": 1})
    assert isinstance(adapter, InteractiveStatusCheckMixin)
    assert isinstance(adapter, ManualAssistedAdapter)
    assert not isinstance(adapter, OtpGatedStatusMixin)


def test_adapter_registered_and_dispatches_via_get_adapter():
    adapter = get_adapter({"id": 1, "status_check_adapter": "karnataka_ipgrs_api"})
    assert isinstance(adapter, KarnatakaAPIAdapter)


def test_rajasthan_adapter_unaffected_by_karnataka_registration():
    adapter = get_adapter({"id": 2, "status_check_adapter": "rajasthan_sampark_api"})
    assert isinstance(adapter, RajasthanSamparkAPIAdapter)
    assert not isinstance(adapter, KarnatakaAPIAdapter)


def test_describe_flow_matches_confirmed_contract():
    adapter = KarnatakaAPIAdapter({"id": 1})
    flow = adapter.describe_flow()
    assert len(flow.stages) == 1
    stage = flow.stages[0]
    assert stage.inputs == ["grievance_id", "mobile_or_email"]
    assert stage.transport == TransportKind.AJAX_FORM
    assert len(stage.human_verification) == 1
    assert stage.human_verification[0].kind == "captcha"


@patch("requests.Session")
def test_start_reaches_awaiting_human_input_with_captcha_challenge(mock_session_cls):
    session = MagicMock()
    session.get.side_effect = [MagicMock(), _mock_captcha_response()]  # page load, then captcha image
    session.cookies.get_dict.return_value = {"ASP.NET_SessionId": "abc123"}
    mock_session_cls.return_value = session

    adapter = KarnatakaAPIAdapter({"id": 1})
    attempt = adapter.start("372414", tenant_id=1, initial_inputs={"mobile_or_email": "919876500001", "case_id": 20})

    assert attempt.state == StatusCheckAttemptState.AWAITING_HUMAN_INPUT
    assert len(attempt.pending_human_verification) == 1
    assert attempt.pending_human_verification[0].kind == "captcha"
    assert attempt.pending_human_verification[0].challenge.startswith("data:image/png;base64,")
    # Confirms the real page GET happens before the captcha image GET, on the same session
    urls_fetched = [c.args[0] for c in session.get.call_args_list]
    assert urls_fetched == [
        "https://ipgrs.karnataka.gov.in/Grievance/GetGrievanceStatus",
        "https://ipgrs.karnataka.gov.in/Home/GetGrievanceStatusCaptchaImage",
    ]


@patch("requests.Session")
def test_advance_sends_exact_confirmed_request_field_names(mock_session_cls):
    start_session = MagicMock()
    start_session.get.side_effect = [MagicMock(), _mock_captcha_response()]
    start_session.cookies.get_dict.return_value = {"ASP.NET_SessionId": "abc123"}

    advance_session = MagicMock()
    advance_session.post.return_value = _mock_verify_response(_REAL_SUCCESS_PAYLOAD)

    mock_session_cls.side_effect = [start_session, advance_session]

    adapter = KarnatakaAPIAdapter({"id": 1})
    attempt = adapter.start("372414", tenant_id=1, initial_inputs={"mobile_or_email": "919876500001", "case_id": 20})
    result_attempt = adapter.advance(attempt, {"captcha": "AB12C"})

    assert result_attempt.state == StatusCheckAttemptState.COMPLETE
    # Cookie continuity: the exact cookie jar start() captured is what advance() replays
    advance_session.cookies.update.assert_called_once_with({"ASP.NET_SessionId": "abc123"})
    # Exact confirmed field names — GrievanceId/MobileOrEmail/Captcha, form-urlencoded via `data=`
    _, kwargs = advance_session.post.call_args
    assert kwargs["data"] == {"GrievanceId": "372414", "MobileOrEmail": "919876500001", "Captcha": "AB12C"}
    assert advance_session.post.call_args.args[0] == "https://ipgrs.karnataka.gov.in/Grievance/VerifyGrievanceStatus"


@patch("requests.Session")
def test_advance_parses_confirmed_response_exactly(mock_session_cls):
    start_session = MagicMock()
    start_session.get.side_effect = [MagicMock(), _mock_captcha_response()]
    start_session.cookies.get_dict.return_value = {}
    advance_session = MagicMock()
    advance_session.post.return_value = _mock_verify_response(_REAL_SUCCESS_PAYLOAD)
    mock_session_cls.side_effect = [start_session, advance_session]

    adapter = KarnatakaAPIAdapter({"id": 1})
    attempt = adapter.start("372414", tenant_id=1, initial_inputs={"mobile_or_email": "919876500001", "case_id": 20})
    result_attempt = adapter.advance(attempt, {"captcha": "AB12C"})

    result = result_attempt.result
    assert result.checked is True
    assert result.raw_portal_status == "Registered & Sent for Scrutiny"   # preserved exactly
    assert result.status == "submitted"                                   # existing normalize_status_keywords, unmodified
    assert result.needs_verification is False
    assert result.portal_detail["department_name"] == "Urban Development Department"
    assert result.portal_detail["pendency_details"] == "S A Mahajan — Municipal Commissioner, Gokak"


@patch("requests.Session")
def test_advance_wrong_captcha_reports_failed_not_crash(mock_session_cls):
    start_session = MagicMock()
    start_session.get.side_effect = [MagicMock(), _mock_captcha_response()]
    start_session.cookies.get_dict.return_value = {}
    advance_session = MagicMock()
    advance_session.post.return_value = _mock_verify_response({"success": False, "message": "Invalid Captcha", "data": None})
    mock_session_cls.side_effect = [start_session, advance_session]

    adapter = KarnatakaAPIAdapter({"id": 1})
    attempt = adapter.start("372414", tenant_id=1, initial_inputs={"mobile_or_email": "919876500001", "case_id": 20})
    result_attempt = adapter.advance(attempt, {"captcha": "WRONG"})

    assert result_attempt.state == StatusCheckAttemptState.FAILED
    assert result_attempt.result.checked is False
    assert result_attempt.result.raw_portal_status == "Invalid Captcha"


def test_advance_unknown_attempt_id_reports_failed_not_crash():
    adapter = KarnatakaAPIAdapter({"id": 1})
    fake_attempt = StatusCheckAttempt(attempt_id="does-not-exist", case_id=20, tenant_id=1, reference_number="372414")
    result_attempt = adapter.advance(fake_attempt, {"captcha": "AB12C"})
    assert result_attempt.state == StatusCheckAttemptState.FAILED
    assert result_attempt.result.checked is False


# ─── B. Endpoint-level tests ─────────────────────────────────────────────

@patch("requests.Session")
def test_endpoint_start_then_advance_full_round_trip(mock_session_cls):
    _seed_database()
    start_session = MagicMock()
    start_session.get.side_effect = [MagicMock(), _mock_captcha_response()]
    start_session.cookies.get_dict.return_value = {"ASP.NET_SessionId": "abc123"}
    advance_session = MagicMock()
    advance_session.post.return_value = _mock_verify_response(_REAL_SUCCESS_PAYLOAD)
    mock_session_cls.side_effect = [start_session, advance_session]

    start_resp = client.post("/api/cases/20/govt/status-check/start", headers=_auth_headers())
    assert start_resp.status_code == 200, start_resp.text
    body = start_resp.json()
    assert body["success"] is True
    assert body["state"] == "awaiting_human_input"
    assert body["pending_human_verification"][0]["kind"] == "captcha"
    assert body["pending_human_verification"][0]["challenge"].startswith("data:image/")
    attempt_id = body["attempt_id"]

    advance_resp = client.post(
        f"/api/cases/20/govt/status-check/{attempt_id}/advance",
        json={"captcha": "AB12C"}, headers=_auth_headers(),
    )
    assert advance_resp.status_code == 200, advance_resp.text
    adv_body = advance_resp.json()
    assert adv_body["success"] is True
    assert adv_body["state"] == "complete"
    assert adv_body["govt_status"] == "submitted"
    assert adv_body["changed"] is False
    assert adv_body["raw_portal_status"] == "Registered & Sent for Scrutiny"
    assert adv_body["portal_detail"]["pendency_details"] == "S A Mahajan — Municipal Commissioner, Gokak"

    row = client.get("/api/cases/20", headers=_auth_headers()).json()
    assert row["govt_status"] == "submitted"

    govt_state = client.get("/api/cases/20/govt", headers=_auth_headers()).json()
    latest = govt_state["latest_status_check"]
    assert latest["changed"] is False
    assert latest["raw_portal_status"] == "Registered & Sent for Scrutiny"
    assert latest["portal_detail"]["department_name"] == "Urban Development Department"
    assert latest["portal_detail"]["pendency_details"] == "S A Mahajan — Municipal Commissioner, Gokak"


@patch("requests.Session")
def test_endpoint_advance_failure_is_audit_logged_with_attempt_id(mock_session_cls):
    """govt-sync fixation plan Step 3: a failed interactive attempt (wrong
    CAPTCHA here) must now leave a durable audit trail — previously this
    vanished with zero record anywhere. Endpoint-level, not adapter-level,
    since the logging lives in api_router.py's govt_status_check_advance,
    not in the adapter itself."""
    _seed_database()
    start_session = MagicMock()
    start_session.get.side_effect = [MagicMock(), _mock_captcha_response()]
    start_session.cookies.get_dict.return_value = {"ASP.NET_SessionId": "abc123"}
    advance_session = MagicMock()
    advance_session.post.return_value = _mock_verify_response({"success": False, "message": "Invalid Captcha", "data": None})
    mock_session_cls.side_effect = [start_session, advance_session]

    start_resp = client.post("/api/cases/20/govt/status-check/start", headers=_auth_headers())
    attempt_id = start_resp.json()["attempt_id"]

    advance_resp = client.post(
        f"/api/cases/20/govt/status-check/{attempt_id}/advance",
        json={"captcha": "WRONG"}, headers=_auth_headers(),
    )
    assert advance_resp.status_code == 200, advance_resp.text
    body = advance_resp.json()
    assert body["state"] == "failed"
    assert body["note"] == "Invalid Captcha"

    with test_engine.connect() as conn:
        rows = list(conn.execute(
            text("SELECT action, payload FROM govt_submission_log WHERE case_id = 20 ORDER BY id")
        ))
    assert len(rows) == 1
    assert rows[0][0] == "status_check_failed"
    payload = json.loads(rows[0][1]) if isinstance(rows[0][1], str) else rows[0][1]
    assert payload["attempt_id"] == attempt_id
    assert payload["note"] == "Invalid Captcha"


def test_endpoint_start_rejects_non_interactive_portal():
    _seed_database()
    with test_engine.begin() as conn:
        conn.execute(text("UPDATE govt_portals SET status_check_adapter = NULL WHERE id = 1"))
    resp = client.post("/api/cases/20/govt/status-check/start", headers=_auth_headers())
    assert resp.status_code == 400


def test_govt_portal_reports_interactive_status_check_flag():
    _seed_database()
    resp = client.get("/api/govt-portal", headers=_auth_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["portal"]["interactive_status_check"] is True
    assert body["portal"]["otp_verification"] is None  # not OTP-gated — distinct signal


# ─── C. Poller exclusion + regression safety ─────────────────────────────
#
# poller.py's own pending-cases query uses Postgres-only syntax
# (`= ANY(:statuses)`) — pre-existing, unrelated to this change, and not
# something this PR modifies. This repo's CI runs pytest against SQLite
# only (see .github/workflows/product-tests.yml), so that query can't run
# here at all regardless of adapter. Testing the actual exclusion LOGIC
# (the one line added to poller.py's loop) doesn't require running that
# query for real — mock _q to hand back a canned row for a Karnataka case
# and assert the adapter is never touched. (The query's own correctness
# for a real Postgres pending-cases row was exercised manually for the
# earlier Rajasthan/OTP-taxonomy PRs via a local-Postgres validation
# script — this test is scoped to the exclusion behavior only.)

def test_poller_never_invokes_karnataka_adapter():
    import modules.govt_sync.poller as poller_mod

    fake_row = {
        "case_id": 20, "tenant_id": 1, "govt_status": "submitted", "govt_reference_number": "372414",
        "govt_portal_id": 1, "portal_id": 1, "state": "Karnataka", "portal_name": "Karnataka Janaspandana (iPGRS)",
        "portal_type": "state_branded", "base_url": "https://ipgrs.karnataka.gov.in",
        "status_check_url": None, "status_check_mode": "login_required", "otp_bound": True,
        "status_check_adapter": "karnataka_ipgrs_api",
    }

    with patch("modules.govt_sync.poller._q", return_value=[fake_row]), \
         patch("modules.govt_sync.adapters.karnataka_ipgrs.KarnatakaAPIAdapter.check_status") as mock_check, \
         patch("modules.govt_sync.adapters.karnataka_ipgrs.KarnatakaAPIAdapter.start") as mock_start, \
         patch("modules.govt_sync.adapters.karnataka_ipgrs.KarnatakaAPIAdapter.advance") as mock_advance:
        summary = poller_mod.poll_all_pending()

    mock_check.assert_not_called()
    mock_start.assert_not_called()
    mock_advance.assert_not_called()
    assert summary["pending"] == 1
    assert summary["checked"] == 0
    assert summary["changed"] == 0


def test_poller_still_checks_rajasthan_unattended_portal():
    # Regression guard: the new skip-check must not accidentally exclude
    # portals that ARE meant to be polled unattended (Rajasthan/manual).
    import modules.govt_sync.poller as poller_mod

    fake_row = {
        "case_id": 21, "tenant_id": 1, "govt_status": "submitted", "govt_reference_number": "RJ/TEST/1",
        "govt_portal_id": 2, "portal_id": 2, "state": "Rajasthan", "portal_name": "Rajasthan Sampark",
        "portal_type": "state_branded", "base_url": "https://sampark.rajasthan.gov.in",
        "status_check_url": None, "status_check_mode": "public_reference", "otp_bound": True,
        "status_check_adapter": "rajasthan_sampark_api",
    }

    with patch("modules.govt_sync.poller._q", return_value=[fake_row]), \
         patch("modules.govt_sync.adapters.rajasthan_sampark.RajasthanSamparkAPIAdapter.check_status") as mock_check:
        mock_check.return_value.checked = False
        mock_check.return_value.status = ""
        mock_check.return_value.needs_verification = False
        poller_mod.poll_all_pending()

    mock_check.assert_called_once()


def test_poller_logs_portal_detail_even_when_status_is_unchanged():
    _seed_database()
    import modules.govt_sync.poller as poller_mod

    fake_row = {
        "case_id": 20, "tenant_id": 1, "govt_status": "submitted", "govt_reference_number": "RJ/TEST/1",
        "govt_portal_id": 1, "portal_id": 1, "state": "Rajasthan", "portal_name": "Rajasthan Sampark",
        "portal_type": "state_branded", "base_url": "https://sampark.rajasthan.gov.in",
        "status_check_url": None, "status_check_mode": "public_reference", "otp_bound": True,
        "status_check_adapter": "rajasthan_sampark_api",
    }
    result = StatusResult(
        status="submitted",
        raw_portal_status="Registered / Sent to Municipal Department",
        portal_detail={
            "status_text": "Registered",
            "sub_status_text": "Sent to Municipal Department",
            "department_name": "Urban Development",
            "last_action_date": "24-08-2026",
        },
        checked=True,
    )
    poller_mod.engine = test_engine

    with patch("modules.govt_sync.poller._q", return_value=[fake_row]), \
         patch("modules.govt_sync.adapters.rajasthan_sampark.RajasthanSamparkAPIAdapter.check_status", return_value=result):
        summary = poller_mod.poll_all_pending()

    assert summary["checked"] == 1
    assert summary["changed"] == 0
    with test_engine.connect() as conn:
        log = conn.execute(
            text("SELECT payload FROM govt_submission_log WHERE tenant_id = 1 AND case_id = 20 AND action = 'status_polled'")
        ).scalar_one()
    payload = json.loads(log)
    assert payload["changed"] is False
    assert payload["raw_portal_status"] == "Registered / Sent to Municipal Department"
    assert payload["portal_detail"]["department_name"] == "Urban Development"
