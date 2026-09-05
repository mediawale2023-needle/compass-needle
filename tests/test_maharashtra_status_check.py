"""
tests/test_maharashtra_status_check.py — Maharashtra Aaple Sarkar
interactive status-check adapter (3-stage: CAPTCHA -> OTP+CAPTCHA -> CAPTCHA).

Same two-layer structure as tests/test_karnataka_status_check.py:

  A. Pure adapter unit tests — MaharashtraAapleSarkarAdapter.start()/
     advance() called directly across all 3 stages, requests.Session
     mocked throughout. No live network call, ever.
  B. Endpoint-level tests — the real /status-check/start + /advance routes
     through TestClient, same mocking underneath, proving the generalized
     (Karnataka-and-Maharashtra-shaped) advance() response contract works.
  C. Poller-exclusion + registration/MRO sanity + regression guards for
     Karnataka and Rajasthan.

Never solves/OCRs a real CAPTCHA, never enters/derives a real OTP, never
hits the live portal — every HTTP call in this file is mocked. The exact
request field names below (verification_id, securitycode, _csrfToken,
_method, otp, registration_no, cid) are the CONFIRMED/OBSERVED contract
from a live, human-assisted trace against grievances.maharashtra.gov.in —
see modules/govt_sync/adapters/maharashtra_aaplesarkar.py's module
docstring for exactly what's confirmed vs. observed vs. inferred. The
result-page HTML fixture used below (_RESULT_PAGE_HTML_FIXTURE) is a REAL
CAPTURED PAGE — a live, human-assisted end-to-end status check was run
against grievances.maharashtra.gov.in on 2026-08-25 (real case #2446,
reference DEP/RDDE/BULD/2026/183, tenant 3), and the "View Page Source" of
the actual result page was captured and trimmed (script/style/nav/footer
removed, structurally-significant markup — the #customers table and the
.district block — preserved verbatim) into this fixture. This is no longer
an approximation; district/department/office/officer/office_contact/
office_email extraction is validated against it.
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
TEST_DB_URL = "sqlite:///./test_maharashtra_status_check.db"

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

from modules.govt_sync.adapters import KarnatakaAPIAdapter, MaharashtraAapleSarkarAdapter, get_adapter
from modules.govt_sync.adapters.base import OtpGatedStatusMixin, normalize_status_keywords
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

_TOKEN = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"  # 32-char lowercase hex, matching the confirmed shape
_CID = "AB12345"  # 7 chars, matching the confirmed shape (real value not retained per the evidence)

_STAGE0_PAGE_HTML = '<form id="anonymous-verify-frm"><input type="hidden" name="_csrfToken" value="csrf-stage0"/></form>'
_STAGE1_PAGE_HTML = '<form><input type="hidden" name="_csrfToken" value="csrf-stage1"/><input type="hidden" name="otp" value=""/></form>'
_STAGE2_PAGE_HTML = f'<form><input type="hidden" name="_csrfToken" value="csrf-stage2"/><input type="hidden" name="cid" value="{_CID}"/></form>'

# REAL CAPTURED PAGE (2026-08-25) — see module docstring. Trimmed of
# script/style/nav/footer; the #customers table and .district block are
# preserved verbatim from the actual "View Page Source" capture, including
# the real whitespace patterns (these matter — see _extract_label_value's
# docstring on labels/values landing on separate lines after flattening).
_RESULT_PAGE_HTML_FIXTURE = """
<html><body>
<div class="district">
    <div class="distHere">
        <h5>जिल्हा : बुलढाणा                            <p>
                स्थिती :
                Submitted                            </p>
        </h5>
    </div>
</div>
<table id="cpgraminfo">
    <div class="cpgramsStatusSection"></div>
</table>
<table id="customers" class="">
    <tr>
        <tr>
            <th class="with200">तक्रार स्त्रोत</th>
            <td>
                                                Aaple Sarkar                            </td>
            <th class="with200">तक्रार टोकन</th>
            <td>DEP/RDDE/0001/2026/001</td>
        </tr>
                        <tr>
            <th class="with200">Current Department</th>
            <td>ग्राम विकास</td>
            <th class="with200">PG Portal Registration No.</th>
            <td></td>
        </tr>
            <tr>
                <th class="with200">कार्यालय</th>
                <td>
                                                                                    Rural Development & Panchayat Raj Department, Mantralaya                                </td>
                <th class="with200">अधिकारी</th>
                <td>
                                                                                    डॉ. चंद्रकांत पुलकुंडवार                                                                                    (Add Chief Secretary, Rural Development & Panchayat Raj Department)                                </td>
            </tr>
            <tr>
                <th class="with200">कार्यालय संपर्क</th>
                <td>
                                                                                    02222060442                                </td>
                <th class="with200">ऑफिस ईमेल</th>
                <td>
                                                                                    rdde.sec@nic.in                                </td>
            </tr>
                        <tr>
            <th class="with200">अपलोड केलेली कागदपत्र</th>
            <td>
                                            </td>
            <th class="with200">तक्रार प्रतिमा</th>
            <td>
                                            </td>
        </tr>
    </tr>
</table>
</body></html>
"""

_FAILURE_PAGE_NO_STATUS = "<html><body><div>An error occurred. Please try again.</div></body></html>"


def _bind_engines():
    dbmod.engine = test_engine
    dbmod.SessionLocal = TestSession
    db_helpers.engine = test_engine
    main.engine = test_engine
    api_router.engine = test_engine
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
        for table_name in ("govt_status_snapshot_events", "govt_status_snapshot_fields", "govt_status_snapshots",
                            "govt_submission_log", "case_activity_log", "cases", "govt_portals",
                            "tenant_overrides", "token_blocklist", "users", "tenant_profiles", "tenants"):
            conn.execute(text(f"DELETE FROM {table_name}"))  # nosec B608

        conn.execute(text(
            "INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active, "
            "created_at, govt_contact_primary_number) VALUES "
            "(1, 'Priya Sharma', 'Kalyan Dombivli', '+919000000002', 'Pro', 1, :now, '919650787758')"
        ), {"now": now})
        conn.execute(text(
            "INSERT INTO tenant_profiles (tenant_id, mp_name, constituency, state, house, created_at) "
            "VALUES (1, 'Shri Priya Sharma', 'Kalyan Dombivli', 'Maharashtra', 'Lok Sabha', :now)"
        ), {"now": now})
        conn.execute(text(
            "INSERT INTO users (tenant_id, username, password_hash, role, constituency, house, display_name, is_active) "
            "VALUES (1, 'mp_priya', :password_hash, 'mp', 'Kalyan Dombivli', 'Lok Sabha', 'Priya MP', 1)"
        ), {"password_hash": hash_password("Password1")})
        conn.execute(text(
            "INSERT INTO govt_portals (id, state, portal_name, portal_type, base_url, status_check_mode, "
            "department_taxonomy, field_schema, otp_bound, active, is_primary, verification_status, "
            "live_session_supported, status_check_adapter) VALUES "
            "(1, 'Maharashtra', 'Maharashtra Aaple Sarkar Grievance Redressal', 'state_branded', "
            "'https://grievances.maharashtra.gov.in', 'login_required', :taxonomy, :schema, 1, 1, 1, "
            "'confirmed', 0, 'maharashtra_aaplesarkar_api')"
        ), {"taxonomy": json.dumps({"Infrastructure & Utilities": "Public Works Department"}), "schema": json.dumps({})})
        conn.execute(text(
            "INSERT INTO cases (id, tenant_id, user_phone, raw_message, category, status, created_at, "
            "govt_portal_id, govt_status, govt_reference_number, is_deleted) VALUES "
            "(30, 1, '+919111111130', 'No water supply', 'Infrastructure & Utilities', 'in_progress', :now, "
            "1, 'submitted', 'DEP/RDDE/0001/2026/001', 0)"
        ), {"now": now})


def _mock_captcha_response():
    resp = MagicMock()
    resp.headers = {"Content-Type": "image/png"}
    resp.content = b"\x89PNG-fake-bytes"
    resp.raise_for_status = MagicMock()
    return resp


def _mock_page_response(html: str, url: str = "https://grievances.maharashtra.gov.in/mr/pg-portal-grievance/track-grievance-verification"):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.text = html
    resp.url = url
    return resp


def _full_success_session_sequence():
    """Builds the 4 requests.Session() instances a full 3-stage run makes:
    start() (page + captcha#1), advance stage0 (post + captcha#2),
    advance stage1 (post + captcha#3), advance stage2 (post, final result).
    Returns the list to pass as mock_session_cls.side_effect."""
    start_session = MagicMock()
    start_session.get.side_effect = [_mock_page_response(_STAGE0_PAGE_HTML), _mock_captcha_response()]
    start_session.cookies.get_dict.return_value = {"MAHASESS": "s0"}

    stage0_session = MagicMock()
    stage0_session.post.return_value = _mock_page_response(
        _STAGE1_PAGE_HTML,
        url=f"https://grievances.maharashtra.gov.in/mr/pg-portal-grievance/track-grievance-verification?token={_TOKEN}",
    )
    stage0_session.get.return_value = _mock_captcha_response()
    stage0_session.cookies.get_dict.return_value = {"MAHASESS": "s1"}

    stage1_session = MagicMock()
    stage1_session.post.return_value = _mock_page_response(
        _STAGE2_PAGE_HTML, url="https://grievances.maharashtra.gov.in/mr/pg-portal-grievance/track-grievance",
    )
    stage1_session.get.return_value = _mock_captcha_response()
    stage1_session.cookies.get_dict.return_value = {"MAHASESS": "s2"}

    stage2_session = MagicMock()
    stage2_session.post.return_value = _mock_page_response(_RESULT_PAGE_HTML_FIXTURE)

    return [start_session, stage0_session, stage1_session, stage2_session]


# ─── A. Pure adapter unit tests ─────────────────────────────────────────

def test_adapter_supports_unattended_status_check_is_false():
    adapter = MaharashtraAapleSarkarAdapter({"id": 1, "portal_name": "Maharashtra Aaple Sarkar Grievance Redressal"})
    assert adapter.supports_unattended_status_check is False


def test_adapter_mro_check_status_from_mixin_prepare_submission_from_manual():
    assert MaharashtraAapleSarkarAdapter.check_status.__qualname__.startswith("InteractiveStatusCheckMixin.")
    assert MaharashtraAapleSarkarAdapter.prepare_submission.__qualname__.startswith("ManualAssistedAdapter.")
    adapter = MaharashtraAapleSarkarAdapter({"id": 1})
    assert isinstance(adapter, InteractiveStatusCheckMixin)
    assert isinstance(adapter, ManualAssistedAdapter)
    assert not isinstance(adapter, OtpGatedStatusMixin)


def test_adapter_registered_and_dispatches_via_get_adapter():
    adapter = get_adapter({"id": 1, "status_check_adapter": "maharashtra_aaplesarkar_api"})
    assert isinstance(adapter, MaharashtraAapleSarkarAdapter)


def test_karnataka_and_rajasthan_adapters_unaffected_by_maharashtra_registration():
    ka = get_adapter({"id": 2, "status_check_adapter": "karnataka_ipgrs_api"})
    rj = get_adapter({"id": 3, "status_check_adapter": "rajasthan_sampark_api"})
    assert isinstance(ka, KarnatakaAPIAdapter) and not isinstance(ka, MaharashtraAapleSarkarAdapter)
    assert isinstance(rj, RajasthanSamparkAPIAdapter) and not isinstance(rj, MaharashtraAapleSarkarAdapter)


def test_describe_flow_matches_confirmed_three_stage_protocol():
    adapter = MaharashtraAapleSarkarAdapter({"id": 1})
    flow = adapter.describe_flow()
    assert len(flow.stages) == 3

    s0, s1, s2 = flow.stages
    assert s0.transport == TransportKind.HTML_FORM_POST
    assert [hv.kind for hv in s0.human_verification] == ["captcha"]

    assert [hv.kind for hv in s1.human_verification] == ["otp", "captcha"]

    assert [hv.kind for hv in s2.human_verification] == ["captcha"]
    # reference_number (Needle's own govt_reference_number) is Needle-known,
    # never a staff-typed field — same principle as Karnataka's GrievanceId
    assert "reference_number" in s2.inputs


@patch("requests.Session")
def test_start_reaches_awaiting_human_input_with_first_captcha(mock_session_cls):
    session = MagicMock()
    session.get.side_effect = [_mock_page_response(_STAGE0_PAGE_HTML), _mock_captcha_response()]
    session.cookies.get_dict.return_value = {"MAHASESS": "s0"}
    mock_session_cls.return_value = session

    adapter = MaharashtraAapleSarkarAdapter({"id": 1})
    attempt = adapter.start("DEP/RDDE/0001/2026/001", tenant_id=1, initial_inputs={"mobile_or_email": "919650787758", "case_id": 30})

    assert attempt.state == StatusCheckAttemptState.AWAITING_HUMAN_INPUT
    assert attempt.current_stage_index == 0
    assert [hv.kind for hv in attempt.pending_human_verification] == ["captcha"]
    assert attempt.pending_human_verification[0].challenge.startswith("data:image/png;base64,")

    urls_fetched = [c.args[0] for c in session.get.call_args_list]
    assert urls_fetched == [
        "https://grievances.maharashtra.gov.in/mr/pg-portal-grievance/track-grievance-verification",
        "https://grievances.maharashtra.gov.in/mr/citizens/captcha?type=image&field=securitycode&width=100&height=42&theme=default&length=6",
    ]


@patch("requests.Session")
def test_start_raises_portal_unavailable_error_on_connection_failure(mock_session_cls):
    """Production-readiness review K3: the entry-page GET failing outright
    (connection error/timeout — exactly the confirmed EC2-cannot-reach-
    grievances.maharashtra.gov.in condition) must raise the specific
    PortalUnavailableError, not a plain RuntimeError, so api_router.py can
    tell staff this is a known standing condition rather than an ordinary
    transient failure."""
    from modules.govt_sync.adapters.status_flow import PortalUnavailableError

    session = MagicMock()
    session.get.side_effect = ConnectionError("Connection timed out")
    mock_session_cls.return_value = session

    adapter = MaharashtraAapleSarkarAdapter({"id": 1})
    try:
        adapter.start("DEP/RDDE/0001/2026/001", tenant_id=1, initial_inputs={"mobile_or_email": "919650787758", "case_id": 30})
        assert False, "expected PortalUnavailableError"
    except PortalUnavailableError as e:
        assert "temporarily unavailable" in str(e)
        assert "known issue" in str(e)
    except RuntimeError:
        assert False, "raised plain RuntimeError instead of the more specific PortalUnavailableError"


@patch("requests.Session")
def test_missing_portal_contact_number_still_raises_plain_runtime_error(mock_session_cls):
    """Regression guard: a config/usage error (no portal contact number on
    file) must NOT be reclassified as PortalUnavailableError — only the
    diagnosed network-connectivity branch is."""
    adapter = MaharashtraAapleSarkarAdapter({"id": 1})
    try:
        adapter.start("DEP/RDDE/0001/2026/001", tenant_id=1, initial_inputs={"mobile_or_email": None, "case_id": 30})
        assert False, "expected RuntimeError"
    except Exception as e:
        assert type(e) is RuntimeError, f"expected plain RuntimeError, got {type(e).__name__}"
        assert "portal contact number" in str(e)
    mock_session_cls.assert_not_called()


@patch("requests.Session")
def test_stage0_advance_sends_exact_confirmed_field_names(mock_session_cls):
    sessions = _full_success_session_sequence()
    mock_session_cls.side_effect = sessions

    adapter = MaharashtraAapleSarkarAdapter({"id": 1})
    attempt = adapter.start("DEP/RDDE/0001/2026/001", tenant_id=1, initial_inputs={"mobile_or_email": "919650787758", "case_id": 30})
    result_attempt = adapter.advance(attempt, {"captcha": "CAP1"})

    stage0_session = sessions[1]
    _, kwargs = stage0_session.post.call_args
    assert kwargs["data"] == {
        "_method": "POST", "_csrfToken": "csrf-stage0",
        "verification_id": "919650787758", "registration_no": "", "securitycode": "CAP1",
    }
    assert stage0_session.post.call_args.args[0] == "https://grievances.maharashtra.gov.in/mr/pg-portal-grievance/track-grievance-verification"
    # Cookie continuity: start()'s cookie jar is exactly what stage 0's advance replays
    stage0_session.cookies.update.assert_called_once_with({"MAHASESS": "s0"})

    assert result_attempt.state == StatusCheckAttemptState.AWAITING_HUMAN_INPUT
    assert result_attempt.current_stage_index == 1
    assert result_attempt.collected_values["token"] == _TOKEN
    assert [hv.kind for hv in result_attempt.pending_human_verification] == ["otp", "captcha"]
    otp_req, captcha_req = result_attempt.pending_human_verification
    assert otp_req.challenge  # human-facing description present
    assert "919650787758" not in otp_req.challenge  # never expose the mobile number in the UI copy
    assert captcha_req.challenge.startswith("data:image/png;base64,")


@patch("requests.Session")
def test_stage1_advance_sends_otp_field_and_preserves_csrf_and_cookies(mock_session_cls):
    sessions = _full_success_session_sequence()
    mock_session_cls.side_effect = sessions

    adapter = MaharashtraAapleSarkarAdapter({"id": 1})
    attempt = adapter.start("DEP/RDDE/0001/2026/001", tenant_id=1, initial_inputs={"mobile_or_email": "919650787758", "case_id": 30})
    attempt = adapter.advance(attempt, {"captcha": "CAP1"})
    result_attempt = adapter.advance(attempt, {"otp": "654321", "captcha": "CAP2"})

    stage1_session = sessions[2]
    _, kwargs = stage1_session.post.call_args
    assert kwargs["data"] == {
        "_method": "POST", "_csrfToken": "csrf-stage1",  # fresh — NOT stage 0's csrf-stage0
        "verification_id": "919650787758", "otp": "654321",
        "registration_no": "", "securitycode": "CAP2",
    }
    assert stage1_session.post.call_args.args[0] == f"https://grievances.maharashtra.gov.in/mr/pg-portal-grievance/track-grievance-verification?token={_TOKEN}"
    stage1_session.cookies.update.assert_called_once_with({"MAHASESS": "s1"})

    assert result_attempt.state == StatusCheckAttemptState.AWAITING_HUMAN_INPUT
    assert result_attempt.current_stage_index == 2
    assert result_attempt.collected_values["cid"] == _CID
    assert [hv.kind for hv in result_attempt.pending_human_verification] == ["captcha"]


@patch("requests.Session")
def test_stage2_advance_submits_registration_no_cid_and_captcha_and_completes(mock_session_cls):
    sessions = _full_success_session_sequence()
    mock_session_cls.side_effect = sessions

    adapter = MaharashtraAapleSarkarAdapter({"id": 1})
    attempt = adapter.start("DEP/RDDE/0001/2026/001", tenant_id=1, initial_inputs={"mobile_or_email": "919650787758", "case_id": 30})
    attempt = adapter.advance(attempt, {"captcha": "CAP1"})
    attempt = adapter.advance(attempt, {"otp": "654321", "captcha": "CAP2"})
    result_attempt = adapter.advance(attempt, {"captcha": "CAP3"})

    stage2_session = sessions[3]
    _, kwargs = stage2_session.post.call_args
    assert kwargs["data"] == {
        "_method": "POST", "_csrfToken": "csrf-stage2",
        "registration_no": "DEP/RDDE/0001/2026/001",  # Needle's own reference_number — never asked of staff
        "securitycode": "CAP3", "cid": _CID,
    }
    assert stage2_session.post.call_args.args[0] == "https://grievances.maharashtra.gov.in/mr/pg-portal-grievance/track-grievance"

    assert result_attempt.state == StatusCheckAttemptState.COMPLETE
    result = result_attempt.result
    assert result.raw_portal_status == "Submitted"  # preserved exactly
    assert result.needs_verification is False
    # base.py's STATUS_KEYWORDS "submitted" bucket was extended (2026-08-24,
    # approved separately) to also match the literal word "submitted" —
    # previously Maharashtra's one CONFIRMED real status value normalized to
    # nothing (see TASK_LOG.md). Asserting the current, correct behavior.
    assert normalize_status_keywords("Submitted") == "submitted"
    assert result.status == "submitted"
    assert result.checked is True
    # portal_detail populated from the #customers table (2026-08-25 real
    # evidence, approved parser extension) — administrative fields only,
    # never uploaded-document/complaint-image cells.
    assert result.portal_detail == {
        "district": "बुलढाणा",
        "department": "ग्राम विकास",
        "office": "Rural Development & Panchayat Raj Department, Mantralaya",
        "officer": "डॉ. चंद्रकांत पुलकुंडवार (Add Chief Secretary, Rural Development & Panchayat Raj Department)",
        "office_contact": "02222060442",
        "office_email": "rdde.sec@nic.in",
    }


@patch("requests.Session")
def test_wrong_captcha_at_stage0_fails_closed(mock_session_cls):
    session = MagicMock()
    session.get.side_effect = [_mock_page_response(_STAGE0_PAGE_HTML), _mock_captcha_response()]
    session.cookies.get_dict.return_value = {"MAHASESS": "s0"}
    stage0_session = MagicMock()
    # No token in the landed URL == the confirmed failure signal (portal re-rendered the same form)
    stage0_session.post.return_value = _mock_page_response(_STAGE0_PAGE_HTML)
    mock_session_cls.side_effect = [session, stage0_session]

    adapter = MaharashtraAapleSarkarAdapter({"id": 1})
    attempt = adapter.start("DEP/RDDE/0001/2026/001", tenant_id=1, initial_inputs={"mobile_or_email": "919650787758", "case_id": 30})
    result_attempt = adapter.advance(attempt, {"captcha": "WRONG"})

    assert result_attempt.state == StatusCheckAttemptState.FAILED
    assert result_attempt.result.checked is False


@patch("requests.Session")
def test_wrong_otp_at_stage1_fails_closed(mock_session_cls):
    start_session, stage0_session, _, _ = _full_success_session_sequence()
    stage1_session = MagicMock()
    # Still on the token-bearing verify URL == confirmed failure signal (wrong OTP/CAPTCHA)
    stage1_session.post.return_value = _mock_page_response(
        _STAGE1_PAGE_HTML,
        url=f"https://grievances.maharashtra.gov.in/mr/pg-portal-grievance/track-grievance-verification?token={_TOKEN}",
    )
    mock_session_cls.side_effect = [start_session, stage0_session, stage1_session]

    adapter = MaharashtraAapleSarkarAdapter({"id": 1})
    attempt = adapter.start("DEP/RDDE/0001/2026/001", tenant_id=1, initial_inputs={"mobile_or_email": "919650787758", "case_id": 30})
    attempt = adapter.advance(attempt, {"captcha": "CAP1"})
    result_attempt = adapter.advance(attempt, {"otp": "000000", "captcha": "CAP2"})

    assert result_attempt.state == StatusCheckAttemptState.FAILED
    assert result_attempt.result.checked is False


@patch("requests.Session")
def test_wrong_captcha_at_stage2_no_status_found_fails_closed(mock_session_cls):
    start_session, stage0_session, stage1_session, _ = _full_success_session_sequence()
    stage2_session = MagicMock()
    stage2_session.post.return_value = _mock_page_response(_FAILURE_PAGE_NO_STATUS)
    mock_session_cls.side_effect = [start_session, stage0_session, stage1_session, stage2_session]

    adapter = MaharashtraAapleSarkarAdapter({"id": 1})
    attempt = adapter.start("DEP/RDDE/0001/2026/001", tenant_id=1, initial_inputs={"mobile_or_email": "919650787758", "case_id": 30})
    attempt = adapter.advance(attempt, {"captcha": "CAP1"})
    attempt = adapter.advance(attempt, {"otp": "654321", "captcha": "CAP2"})
    result_attempt = adapter.advance(attempt, {"captcha": "WRONG3"})

    assert result_attempt.state == StatusCheckAttemptState.FAILED
    assert result_attempt.result.checked is False


def test_advance_unknown_attempt_id_fails_closed():
    adapter = MaharashtraAapleSarkarAdapter({"id": 1})
    fake_attempt = StatusCheckAttempt(attempt_id="does-not-exist", case_id=30, tenant_id=1, reference_number="DEP/RDDE/0001/2026/001")
    result_attempt = adapter.advance(fake_attempt, {"captcha": "CAP1"})
    assert result_attempt.state == StatusCheckAttemptState.FAILED
    assert result_attempt.result.checked is False


@patch("requests.Session")
def test_advance_wrong_tenant_or_case_fails_closed(mock_session_cls):
    session = MagicMock()
    session.get.side_effect = [_mock_page_response(_STAGE0_PAGE_HTML), _mock_captcha_response()]
    session.cookies.get_dict.return_value = {"MAHASESS": "s0"}
    mock_session_cls.return_value = session

    adapter = MaharashtraAapleSarkarAdapter({"id": 1})
    attempt = adapter.start("DEP/RDDE/0001/2026/001", tenant_id=1, initial_inputs={"mobile_or_email": "919650787758", "case_id": 30})

    wrong_tenant_attempt = StatusCheckAttempt(attempt_id=attempt.attempt_id, case_id=30, tenant_id=999, reference_number="DEP/RDDE/0001/2026/001")
    result = adapter.advance(wrong_tenant_attempt, {"captcha": "CAP1"})
    assert result.state == StatusCheckAttemptState.FAILED

    wrong_case_attempt = StatusCheckAttempt(attempt_id=attempt.attempt_id, case_id=999, tenant_id=1, reference_number="DEP/RDDE/0001/2026/001")
    result = adapter.advance(wrong_case_attempt, {"captcha": "CAP1"})
    assert result.state == StatusCheckAttemptState.FAILED


@patch("requests.Session")
def test_advance_after_ttl_expiry_from_last_activity_fails_closed(mock_session_cls):
    """Maharashtra's TTL (600s) is measured from last_activity_at, not
    created_at — advancing stage 0 refreshes it. Age the row directly (as
    a stand-in for real elapsed wall-clock time) to prove expiry is
    enforced from the most recent activity, matching the pre-migration
    `_gc_expired()` semantics exactly."""
    from modules.govt_sync.adapters.maharashtra_aaplesarkar import _ATTEMPT_TTL_SECONDS

    _seed_database()
    sessions = _full_success_session_sequence()
    mock_session_cls.side_effect = sessions

    adapter = MaharashtraAapleSarkarAdapter({"id": 1})
    attempt = adapter.start("DEP/RDDE/0001/2026/001", tenant_id=1, initial_inputs={"mobile_or_email": "919650787758", "case_id": 30})
    attempt = adapter.advance(attempt, {"captcha": "CAP1"})  # stage 0 -> 1, refreshes last_activity_at
    assert attempt.state == StatusCheckAttemptState.AWAITING_HUMAN_INPUT

    with test_engine.begin() as conn:
        conn.execute(
            text("UPDATE govt_status_check_attempts SET last_activity_at = :old WHERE attempt_id = :aid"),
            {"old": _utcnow() - timedelta(seconds=_ATTEMPT_TTL_SECONDS + 1), "aid": attempt.attempt_id},
        )

    result = adapter.advance(attempt, {"otp": "654321", "captcha": "CAP2"})
    assert result.state == StatusCheckAttemptState.FAILED
    assert result.result.checked is False


@patch("requests.Session")
def test_stage_advance_still_fresh_just_under_ttl_succeeds(mock_session_cls):
    """Regression guard alongside the expiry test above: a row just under
    the TTL boundary must remain usable — proving the cutoff comparison
    isn't accidentally off-by-one in the strict direction."""
    from modules.govt_sync.adapters.maharashtra_aaplesarkar import _ATTEMPT_TTL_SECONDS

    _seed_database()
    sessions = _full_success_session_sequence()
    mock_session_cls.side_effect = sessions

    adapter = MaharashtraAapleSarkarAdapter({"id": 1})
    attempt = adapter.start("DEP/RDDE/0001/2026/001", tenant_id=1, initial_inputs={"mobile_or_email": "919650787758", "case_id": 30})
    attempt = adapter.advance(attempt, {"captcha": "CAP1"})

    with test_engine.begin() as conn:
        conn.execute(
            text("UPDATE govt_status_check_attempts SET last_activity_at = :recent WHERE attempt_id = :aid"),
            {"recent": _utcnow() - timedelta(seconds=_ATTEMPT_TTL_SECONDS - 5), "aid": attempt.attempt_id},
        )

    result = adapter.advance(attempt, {"otp": "654321", "captcha": "CAP2"})
    assert result.state == StatusCheckAttemptState.AWAITING_HUMAN_INPUT


@patch("requests.Session")
def test_concurrent_duplicate_stage0_advance_only_one_succeeds(mock_session_cls):
    """The core Maharashtra concurrency proof: two near-simultaneous
    advance() calls both believing the attempt is still at stage 0 (e.g. a
    doubled client request) must not both move it forward. Both callers'
    load_attempt() sees stage 0 and both proceed through the (mocked)
    portal round trip identically — the only place they can differ is
    update_attempt_stage()'s atomic expected_stage guard, so this patches
    that single call site to return False for this caller, exactly what a
    real concurrent winner elsewhere would cause. The loser must fail
    closed, never crash, and never silently re-present a stale CAPTCHA as
    if it were still current."""
    from modules.govt_sync.status_attempts import load_attempt

    _seed_database()
    sessions = _full_success_session_sequence()
    mock_session_cls.side_effect = sessions

    adapter = MaharashtraAapleSarkarAdapter({"id": 1})
    attempt = adapter.start("DEP/RDDE/0001/2026/001", tenant_id=1, initial_inputs={"mobile_or_email": "919650787758", "case_id": 30})

    with patch("modules.govt_sync.adapters.maharashtra_aaplesarkar.update_attempt_stage", return_value=False) as mock_update:
        result = adapter.advance(attempt, {"captcha": "CAP1"})
    mock_update.assert_called_once()
    assert mock_update.call_args.kwargs["expected_stage"] == 0

    assert result.state == StatusCheckAttemptState.FAILED
    assert result.result.checked is False

    # A lost stage-transition race is NOT treated as a terminal failure for
    # cleanup purposes: the row is left untouched rather than deleted,
    # because in a real race it would hold the concurrent winner's freshly-
    # advanced state — deleting it here would corrupt that winner's
    # progress rather than just failing this (losing) caller cleanly.
    row = load_attempt(attempt.attempt_id, 1, 30, ttl_seconds=600)
    assert row is not None
    assert row["stage"] == 0


@patch("requests.Session")
def test_completion_removes_attempt_row(mock_session_cls):
    _seed_database()
    sessions = _full_success_session_sequence()
    mock_session_cls.side_effect = sessions

    adapter = MaharashtraAapleSarkarAdapter({"id": 1})
    attempt = adapter.start("DEP/RDDE/0001/2026/001", tenant_id=1, initial_inputs={"mobile_or_email": "919650787758", "case_id": 30})
    attempt = adapter.advance(attempt, {"captcha": "CAP1"})
    attempt = adapter.advance(attempt, {"otp": "654321", "captcha": "CAP2"})
    result = adapter.advance(attempt, {"captcha": "CAP3"})
    assert result.state == StatusCheckAttemptState.COMPLETE

    with test_engine.connect() as conn:
        row = conn.execute(
            text("SELECT attempt_id FROM govt_status_check_attempts WHERE attempt_id = :aid"),
            {"aid": attempt.attempt_id},
        ).first()
    assert row is None


@patch("requests.Session")
def test_stage2_failure_removes_attempt_row_requiring_fresh_start(mock_session_cls):
    _seed_database()
    start_session, stage0_session, stage1_session, _ = _full_success_session_sequence()
    stage2_session = MagicMock()
    stage2_session.post.return_value = _mock_page_response(_FAILURE_PAGE_NO_STATUS)
    mock_session_cls.side_effect = [start_session, stage0_session, stage1_session, stage2_session]

    adapter = MaharashtraAapleSarkarAdapter({"id": 1})
    attempt = adapter.start("DEP/RDDE/0001/2026/001", tenant_id=1, initial_inputs={"mobile_or_email": "919650787758", "case_id": 30})
    attempt = adapter.advance(attempt, {"captcha": "CAP1"})
    attempt = adapter.advance(attempt, {"otp": "654321", "captcha": "CAP2"})
    result = adapter.advance(attempt, {"captcha": "WRONG3"})
    assert result.state == StatusCheckAttemptState.FAILED

    with test_engine.connect() as conn:
        row = conn.execute(
            text("SELECT attempt_id FROM govt_status_check_attempts WHERE attempt_id = :aid"),
            {"aid": attempt.attempt_id},
        ).first()
    assert row is None  # gone — a retry must start() fresh, not resume this attempt_id


@patch("requests.Session")
def test_last_activity_at_refreshes_on_each_stage_advance(mock_session_cls):
    _seed_database()
    sessions = _full_success_session_sequence()
    mock_session_cls.side_effect = sessions

    adapter = MaharashtraAapleSarkarAdapter({"id": 1})
    attempt = adapter.start("DEP/RDDE/0001/2026/001", tenant_id=1, initial_inputs={"mobile_or_email": "919650787758", "case_id": 30})

    with test_engine.connect() as conn:
        after_start = conn.execute(
            text("SELECT last_activity_at FROM govt_status_check_attempts WHERE attempt_id = :aid"),
            {"aid": attempt.attempt_id},
        ).scalar_one()

    # Backdate it, then advance — the stage-0 advance must bump
    # last_activity_at forward again, not merely leave the original value.
    with test_engine.begin() as conn:
        conn.execute(
            text("UPDATE govt_status_check_attempts SET last_activity_at = :old WHERE attempt_id = :aid"),
            {"old": _utcnow() - timedelta(seconds=100), "aid": attempt.attempt_id},
        )
    adapter.advance(attempt, {"captcha": "CAP1"})

    with test_engine.connect() as conn:
        after_advance = conn.execute(
            text("SELECT last_activity_at FROM govt_status_check_attempts WHERE attempt_id = :aid"),
            {"aid": attempt.attempt_id},
        ).scalar_one()
    if isinstance(after_advance, str):
        after_advance = datetime.fromisoformat(after_advance)
    assert after_advance > _utcnow() - timedelta(seconds=10)


def test_no_sensitive_fields_are_logged_across_stages(caplog):
    """Security invariant: session cookies, CSRF token, CAPTCHA answers,
    OTP, cid/token correlation values, and the tenant's portal contact
    number must never appear in any log line this module emits."""
    import logging as _logging

    _seed_database()
    with patch("requests.Session") as mock_session_cls, caplog.at_level(_logging.DEBUG, logger="needle.govt_sync.adapter.maharashtra_aaplesarkar"):
        sessions = _full_success_session_sequence()
        sessions[0].cookies.get_dict.return_value = {"MAHASESS": "top-secret-cookie"}
        mock_session_cls.side_effect = sessions

        adapter = MaharashtraAapleSarkarAdapter({"id": 1})
        attempt = adapter.start("DEP/RDDE/0001/2026/001", tenant_id=1, initial_inputs={"mobile_or_email": "919650787758", "case_id": 30})
        attempt = adapter.advance(attempt, {"captcha": "SECRETCAP1"})
        attempt = adapter.advance(attempt, {"otp": "999888", "captcha": "SECRETCAP2"})
        adapter.advance(attempt, {"captcha": "SECRETCAP3"})

    log_text = caplog.text
    for secret in ("top-secret-cookie", "SECRETCAP1", "SECRETCAP2", "SECRETCAP3", "999888", "919650787758"):
        assert secret not in log_text


def test_result_html_fixture_parses_expected_status():
    # Parser test against the REAL captured fixture (see module docstring) —
    # validates both the original Status extraction and the newer
    # district/department/office/officer/office_contact/office_email fields
    # extracted from the #customers table's <th>/<td> pairs.
    from modules.govt_sync.adapters.maharashtra_aaplesarkar import _parse_result_html
    parsed = _parse_result_html(_RESULT_PAGE_HTML_FIXTURE)
    assert parsed == {
        "status_text": "Submitted",
        "district": "बुलढाणा",
        "department": "ग्राम विकास",
        "office": "Rural Development & Panchayat Raj Department, Mantralaya",
        "officer": "डॉ. चंद्रकांत पुलकुंडवार (Add Chief Secretary, Rural Development & Panchayat Raj Department)",
        "office_contact": "02222060442",
        "office_email": "rdde.sec@nic.in",
    }
    # Uploaded-document / complaint-image cells are present but empty on
    # this real page, and are never extracted even when populated — see
    # _parse_result_html's docstring.
    assert "uploaded_documents" not in parsed and "complaint_image" not in parsed


def test_result_html_no_status_label_returns_none():
    from modules.govt_sync.adapters.maharashtra_aaplesarkar import _parse_result_html
    assert _parse_result_html(_FAILURE_PAGE_NO_STATUS) is None


# ─── B. Endpoint-level tests ─────────────────────────────────────────────

@patch("requests.Session")
def test_endpoint_full_three_stage_round_trip(mock_session_cls):
    _seed_database()
    mock_session_cls.side_effect = _full_success_session_sequence()

    start_resp = client.post("/api/cases/30/govt/status-check/start", headers=_auth_headers())
    assert start_resp.status_code == 200, start_resp.text
    body = start_resp.json()
    assert body["state"] == "awaiting_human_input"
    assert [r["kind"] for r in body["pending_human_verification"]] == ["captcha"]
    attempt_id = body["attempt_id"]

    stage0_resp = client.post(
        f"/api/cases/30/govt/status-check/{attempt_id}/advance",
        json={"captcha": "CAP1"}, headers=_auth_headers(),
    )
    assert stage0_resp.status_code == 200, stage0_resp.text
    stage0_body = stage0_resp.json()
    assert stage0_body["state"] == "awaiting_human_input"
    assert [r["kind"] for r in stage0_body["pending_human_verification"]] == ["otp", "captcha"]

    stage1_resp = client.post(
        f"/api/cases/30/govt/status-check/{attempt_id}/advance",
        json={"captcha": "CAP2", "otp": "654321"}, headers=_auth_headers(),
    )
    assert stage1_resp.status_code == 200, stage1_resp.text
    stage1_body = stage1_resp.json()
    assert stage1_body["state"] == "awaiting_human_input"
    assert [r["kind"] for r in stage1_body["pending_human_verification"]] == ["captcha"]

    stage2_resp = client.post(
        f"/api/cases/30/govt/status-check/{attempt_id}/advance",
        json={"captcha": "CAP3"}, headers=_auth_headers(),
    )
    assert stage2_resp.status_code == 200, stage2_resp.text
    stage2_body = stage2_resp.json()
    assert stage2_body["success"] is True
    assert stage2_body["state"] == "complete"
    # "Submitted" now normalizes to "submitted" (base.py fix, 2026-08-24,
    # approved separately). The seeded case's govt_status was already
    # 'submitted', so this is a real, checked, matching result — changed is
    # correctly False because the value didn't move, not because the check
    # was inconclusive (no "note" key on this path — see govt_status_check_advance).
    assert stage2_body["changed"] is False
    assert stage2_body["govt_status"] == "submitted"
    assert stage2_body["raw_portal_status"] == "Submitted"
    assert "note" not in stage2_body
    # portal_detail flows through the existing, unmodified api_router.py
    # response shape (getattr(result, "portal_detail", None) or {}) — no
    # api_router.py change was needed for this to appear.
    assert stage2_body["portal_detail"]["department"] == "ग्राम विकास"
    assert stage2_body["portal_detail"]["office_email"] == "rdde.sec@nic.in"

    row = client.get("/api/cases/30", headers=_auth_headers()).json()
    assert row["govt_status"] == "submitted"

    # govt-sync fixation plan Step 3: the audit-log row this completion
    # writes now carries attempt_id, for correlating it back to this
    # specific 3-stage run — added at the api_router.py call site, not the
    # response body, so this reads govt_submission_log directly.
    with test_engine.connect() as conn:
        log_rows = list(conn.execute(
            text("SELECT payload FROM govt_submission_log WHERE case_id = 30 AND action = 'status_polled'")
        ))
    assert len(log_rows) == 1
    logged_payload = json.loads(log_rows[0][0]) if isinstance(log_rows[0][0], str) else log_rows[0][0]
    assert logged_payload["attempt_id"] == attempt_id


@patch("requests.Session")
def test_endpoint_full_three_stage_round_trip_persists_snapshot_without_duplicate_events(mock_session_cls):
    """Maharashtra pilot gap closed: prior coverage never proved a real
    3-stage completion reaches the Phase 9 snapshot layer at all. A first
    completion must persist exactly one govt_status_snapshots row and zero
    events (first snapshot = baseline, per the approved snapshot contract).
    A second, identical 3-stage run (repeated status check, unchanged
    status) must persist a SECOND snapshot row (audit trail) but create NO
    new events — this is the same "repeated identical successful reads
    create snapshots without events" contract tested generically in
    tests/test_govt_status_snapshot.py, exercised here through Maharashtra's
    own real StatusResult/portal_detail shape end to end, not a synthetic one."""
    _seed_database()
    mock_session_cls.side_effect = _full_success_session_sequence()

    attempt_id = client.post("/api/cases/30/govt/status-check/start", headers=_auth_headers()).json()["attempt_id"]
    client.post(f"/api/cases/30/govt/status-check/{attempt_id}/advance", json={"captcha": "CAP1"}, headers=_auth_headers())
    client.post(f"/api/cases/30/govt/status-check/{attempt_id}/advance", json={"captcha": "CAP2", "otp": "654321"}, headers=_auth_headers())
    first = client.post(f"/api/cases/30/govt/status-check/{attempt_id}/advance", json={"captcha": "CAP3"}, headers=_auth_headers())
    assert first.status_code == 200, first.text

    with test_engine.connect() as conn:
        snapshots = list(conn.execute(text(
            "SELECT id, normalized_status FROM govt_status_snapshots WHERE case_id = 30 AND portal_id = 1"
        )))
        events = list(conn.execute(text("SELECT event_type FROM govt_status_snapshot_events WHERE case_id = 30")))
    assert len(snapshots) == 1
    assert snapshots[0][1] == "submitted"
    assert events == []  # baseline snapshot — no prior snapshot to diff against

    # Repeat the identical 3-stage flow (a fresh attempt — the first one is
    # already complete). Unchanged status must persist a second snapshot
    # (audit trail is append-only by design) but create zero new events.
    mock_session_cls.side_effect = _full_success_session_sequence()
    attempt_id2 = client.post("/api/cases/30/govt/status-check/start", headers=_auth_headers()).json()["attempt_id"]
    client.post(f"/api/cases/30/govt/status-check/{attempt_id2}/advance", json={"captcha": "CAP1"}, headers=_auth_headers())
    client.post(f"/api/cases/30/govt/status-check/{attempt_id2}/advance", json={"captcha": "CAP2", "otp": "654321"}, headers=_auth_headers())
    second = client.post(f"/api/cases/30/govt/status-check/{attempt_id2}/advance", json={"captcha": "CAP3"}, headers=_auth_headers())
    assert second.status_code == 200, second.text

    with test_engine.connect() as conn:
        snapshots2 = list(conn.execute(text(
            "SELECT id FROM govt_status_snapshots WHERE case_id = 30 AND portal_id = 1"
        )))
        events2 = list(conn.execute(text("SELECT event_type FROM govt_status_snapshot_events WHERE case_id = 30")))
    assert len(snapshots2) == 2
    assert events2 == []

    # Briefcase-facing contract: the history API must surface this real
    # Maharashtra result correctly (current_state + latest_known.status).
    history = client.get("/api/cases/30/govt/history", headers=_auth_headers()).json()
    assert history["current_state"]["needle_govt_status"] == "submitted"
    assert history["latest_known"]["status"]["value"] == "submitted"
    assert len(history["snapshots"]) == 2


@patch("requests.Session")
def test_endpoint_start_reports_503_portal_unavailable_on_connection_failure(mock_session_cls):
    """Production-readiness review K3, endpoint level: a connection failure
    to grievances.maharashtra.gov.in must surface as a 503 with the stable
    X-Govt-Sync-Error-Code header, not the ordinary 400 a ManualAssistedAdapter-
    style RuntimeError gets elsewhere in this same endpoint."""
    _seed_database()
    session = MagicMock()
    session.get.side_effect = ConnectionError("Connection timed out")
    mock_session_cls.return_value = session

    resp = client.post("/api/cases/30/govt/status-check/start", headers=_auth_headers())
    assert resp.status_code == 503, resp.text
    assert resp.headers.get("X-Govt-Sync-Error-Code") == "portal_unavailable"
    detail = resp.json()["detail"]
    assert isinstance(detail, str)  # plain string — frontend/lib/api.js's `err.detail` renders this unmodified
    assert "temporarily unavailable" in detail
    assert "known issue" in detail


# Karnataka's own existing request/response contract (no `otp` field sent
# at all) is regression-tested directly by tests/test_karnataka_status_check.py
# itself, run alongside this file — not duplicated here.


@patch("requests.Session")
def test_endpoint_responses_never_expose_cookies_or_correlation_state(mock_session_cls):
    """Security invariant, migration-specific: cookies/csrf_token/token/cid
    now live in govt_status_check_attempts rather than a process-local
    dict — proves none of the 3 request/response round trips leak them."""
    _seed_database()
    sessions = _full_success_session_sequence()
    sessions[0].cookies.get_dict.return_value = {"MAHASESS": "top-secret-cookie-value"}
    mock_session_cls.side_effect = sessions

    start_resp = client.post("/api/cases/30/govt/status-check/start", headers=_auth_headers())
    attempt_id = start_resp.json()["attempt_id"]
    assert "top-secret-cookie-value" not in start_resp.text
    assert "MAHASESS" not in start_resp.text

    stage0_resp = client.post(f"/api/cases/30/govt/status-check/{attempt_id}/advance", json={"captcha": "CAP1"}, headers=_auth_headers())
    stage1_resp = client.post(f"/api/cases/30/govt/status-check/{attempt_id}/advance", json={"captcha": "CAP2", "otp": "654321"}, headers=_auth_headers())
    stage2_resp = client.post(f"/api/cases/30/govt/status-check/{attempt_id}/advance", json={"captcha": "CAP3"}, headers=_auth_headers())

    for resp in (stage0_resp, stage1_resp, stage2_resp):
        assert "top-secret-cookie-value" not in resp.text
        assert "MAHASESS" not in resp.text
        assert _TOKEN not in resp.text
        for forbidden_key in ("cookies", "csrf_token", "cid"):
            assert forbidden_key not in resp.json()


# ─── C. Poller exclusion + regression safety ─────────────────────────────

def test_poller_never_invokes_maharashtra_adapter():
    import modules.govt_sync.poller as poller_mod

    fake_row = {
        "case_id": 30, "tenant_id": 1, "govt_status": "submitted", "govt_reference_number": "DEP/RDDE/0001/2026/001",
        "govt_portal_id": 1, "portal_id": 1, "state": "Maharashtra", "portal_name": "Maharashtra Aaple Sarkar Grievance Redressal",
        "portal_type": "state_branded", "base_url": "https://grievances.maharashtra.gov.in",
        "status_check_url": None, "status_check_mode": "login_required", "otp_bound": True,
        "status_check_adapter": "maharashtra_aaplesarkar_api",
    }

    with patch("modules.govt_sync.poller._q", return_value=[fake_row]), \
         patch("modules.govt_sync.adapters.maharashtra_aaplesarkar.MaharashtraAapleSarkarAdapter.check_status") as mock_check, \
         patch("modules.govt_sync.adapters.maharashtra_aaplesarkar.MaharashtraAapleSarkarAdapter.start") as mock_start, \
         patch("modules.govt_sync.adapters.maharashtra_aaplesarkar.MaharashtraAapleSarkarAdapter.advance") as mock_advance:
        summary = poller_mod.poll_all_pending()

    mock_check.assert_not_called()
    mock_start.assert_not_called()
    mock_advance.assert_not_called()
    assert summary["pending"] == 1
    assert summary["checked"] == 0


def test_poller_still_checks_rajasthan_and_excludes_karnataka_alongside_maharashtra():
    # Both interactive adapters excluded, unattended one still polled —
    # proves the shared supports_unattended_status_check gate handles a
    # mix of portal shapes correctly in one run, not just one at a time.
    import modules.govt_sync.poller as poller_mod

    maharashtra_row = {
        "case_id": 30, "tenant_id": 1, "govt_status": "submitted", "govt_reference_number": "DEP/RDDE/0001/2026/001",
        "govt_portal_id": 1, "portal_id": 1, "state": "Maharashtra", "portal_name": "Maharashtra Aaple Sarkar Grievance Redressal",
        "portal_type": "state_branded", "base_url": "https://grievances.maharashtra.gov.in",
        "status_check_url": None, "status_check_mode": "login_required", "otp_bound": True,
        "status_check_adapter": "maharashtra_aaplesarkar_api",
    }
    karnataka_row = {
        "case_id": 20, "tenant_id": 2, "govt_status": "submitted", "govt_reference_number": "372414",
        "govt_portal_id": 2, "portal_id": 2, "state": "Karnataka", "portal_name": "Karnataka Janaspandana (iPGRS)",
        "portal_type": "state_branded", "base_url": "https://ipgrs.karnataka.gov.in",
        "status_check_url": None, "status_check_mode": "login_required", "otp_bound": True,
        "status_check_adapter": "karnataka_ipgrs_api",
    }
    rajasthan_row = {
        "case_id": 21, "tenant_id": 3, "govt_status": "submitted", "govt_reference_number": "RJ/TEST/1",
        "govt_portal_id": 3, "portal_id": 3, "state": "Rajasthan", "portal_name": "Rajasthan Sampark",
        "portal_type": "state_branded", "base_url": "https://sampark.rajasthan.gov.in",
        "status_check_url": None, "status_check_mode": "public_reference", "otp_bound": True,
        "status_check_adapter": "rajasthan_sampark_api",
    }

    with patch("modules.govt_sync.poller._q", return_value=[maharashtra_row, karnataka_row, rajasthan_row]), \
         patch("modules.govt_sync.adapters.maharashtra_aaplesarkar.MaharashtraAapleSarkarAdapter.check_status") as mh_check, \
         patch("modules.govt_sync.adapters.karnataka_ipgrs.KarnatakaAPIAdapter.check_status") as ka_check, \
         patch("modules.govt_sync.adapters.rajasthan_sampark.RajasthanSamparkAPIAdapter.check_status") as rj_check:
        rj_check.return_value.checked = False
        rj_check.return_value.status = ""
        rj_check.return_value.needs_verification = False
        summary = poller_mod.poll_all_pending()

    mh_check.assert_not_called()
    ka_check.assert_not_called()
    rj_check.assert_called_once()
    assert summary["pending"] == 3
    assert summary["checked"] == 1
