import asyncio
import json
import os
import secrets
import sys
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import jwt
import pytest
import requests
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

TEST_DB_URL = "sqlite:///./test_tamil_nadu_inboard_status.db"
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["ENV"] = "test"
os.environ["JWT_SECRET"] = "test-secret-key-32-characters-minimum-ok"
os.environ["OPENAI_API_KEY"] = "sk-test-fake-key-for-testing"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import api_router
import core.db_helpers as db_helpers
import sansadx_backend.db as dbmod
from modules.govt_sync import cookie_sessions
from modules.govt_sync.adapters import get_adapter
from modules.govt_sync.adapters.base import StatusFailureKind, StatusResult
from modules.govt_sync.adapters.tamil_nadu_http import TamilNaduHTTPStatusAdapter
from sansadx_backend.db import Base

test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})

REF = "TN/FOODCO/CBE/P/PORTAL/01SEP26/18968314"
RECORD_ID = "35665012402750744"
REF_TWO = "TN/FOODCO/CBE/P/PORTAL/02SEP26/18968315"
RECORD_ID_TWO = "35665012402750745"
COOKIE_VALUE = "cookie-" + secrets.token_urlsafe(18)
FERNET_KEY = Fernet.generate_key().decode("ascii")


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _bind_engine():
    dbmod.engine = test_engine
    db_helpers.engine = test_engine
    api_router.engine = test_engine
    api_router.JWT_SECRET = os.environ["JWT_SECRET"]


def _reset_db():
    _bind_engine()
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    with test_engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active, created_at) "
            "VALUES (1, 'TN Tenant', 'Coimbatore', '+919000000001', 'Pro', 1, :now), "
            "(2, 'Other Tenant', 'Other', '+919000000002', 'Pro', 1, :now)"
        ), {"now": _utcnow()})
        conn.execute(text(
            "INSERT INTO users (tenant_id, username, password_hash, role, constituency, is_active) "
            "VALUES (1, 'mp_tn', '$2b$12$syntheticnotusedsyntheticnotusedsyntheticnotused', 'mp', 'Coimbatore', 1)"
        ))
        conn.execute(text(
            "INSERT INTO govt_portals (id, state, portal_name, portal_type, base_url, status_check_url, "
            "status_check_mode, department_taxonomy, field_schema, otp_bound, active, is_primary, "
            "verification_status, live_session_supported, status_check_adapter) "
            "VALUES (10, 'Tamil Nadu', 'Tamil Nadu CM Helpline (Mudhalvarin Mugavari)', 'state_branded', "
            "'https://cmhelpline.tnega.org', NULL, 'login_required', :taxonomy, :schema, 1, 1, 1, "
            "'confirmed', 1, 'tamil_nadu_http_api')"
        ), {"taxonomy": json.dumps({}), "schema": json.dumps({"status_area_path": "/portal/ta/myarea"})})
        conn.execute(text(
            "INSERT INTO cases (id, tenant_id, user_phone, raw_message, category, status, created_at, "
            "govt_portal_id, govt_status, govt_reference_number, is_deleted) VALUES "
            "(40, 1, '+919111111140', 'Test grievance', 'Infrastructure & Utilities', 'in_progress', :now, "
            "10, 'submitted', :ref, 0), "
            "(41, 1, '+919111111141', 'Second grievance', 'Infrastructure & Utilities', 'in_progress', :now, "
            "10, 'submitted', :ref_two, 0)"
        ), {"now": _utcnow(), "ref": REF, "ref_two": REF_TWO})


def _portal():
    return {
        "id": 10,
        "portal_id": 10,
        "state": "Tamil Nadu",
        "portal_name": "Tamil Nadu CM Helpline (Mudhalvarin Mugavari)",
        "portal_type": "state_branded",
        "base_url": "https://cmhelpline.tnega.org",
        "status_check_adapter": "tamil_nadu_http_api",
        "field_schema": {"status_area_path": "/portal/ta/myarea"},
    }


def _cookie_jar(value=COOKIE_VALUE):
    return [{"name": "tn_session", "value": value, "domain": "cmhelpline.tnega.org", "path": "/", "expires": -1}]


def _store(mapping=None, tenant_id=1, value=COOKIE_VALUE):
    cookie_sessions.store_cookie_session(
        tenant_id=tenant_id,
        portal_id=10,
        cookie_jar=_cookie_jar(value),
        ticket_mappings=mapping if mapping is not None else {REF: RECORD_ID},
    )


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("GOVT_COOKIE_SESSION_KEY", FERNET_KEY)
    _reset_db()


def test_cookie_session_encrypts_and_decrypts_without_plaintext_persistence():
    _store()
    with test_engine.connect() as conn:
        row = conn.execute(text("SELECT encrypted_cookie_jar, ticket_mappings FROM govt_cookie_sessions")).mappings().one()
    assert COOKIE_VALUE not in row["encrypted_cookie_jar"]
    assert cookie_sessions.load_cookie_session(1, 10).cookie_jar == _cookie_jar()
    assert cookie_sessions.load_cookie_session(1, 10).ticket_mappings == {REF: RECORD_ID}


def test_cookie_session_missing_or_invalid_key_fails_closed(monkeypatch):
    _store()
    monkeypatch.delenv("GOVT_COOKIE_SESSION_KEY", raising=False)
    with pytest.raises(cookie_sessions.CookieSessionKeyError):
        cookie_sessions.load_cookie_session(1, 10)
    monkeypatch.setenv("GOVT_COOKIE_SESSION_KEY", "not-a-fernet-key")
    with pytest.raises(cookie_sessions.CookieSessionKeyError):
        cookie_sessions.load_cookie_session(1, 10)


def test_tenant_a_cannot_use_tenant_b_cookie_session():
    _store(tenant_id=2)
    assert cookie_sessions.load_cookie_session(1, 10) is None
    assert cookie_sessions.load_cookie_session(2, 10).ticket_mappings == {REF: RECORD_ID}


def test_tamil_nadu_adapter_registered_for_normal_status_poll():
    adapter = get_adapter(_portal())
    assert isinstance(adapter, TamilNaduHTTPStatusAdapter)


def _response(status_code, payload=None, text=""):
    resp = Mock()
    resp.status_code = status_code
    resp.text = text
    if isinstance(payload, Exception):
        resp.json.side_effect = payload
    else:
        resp.json.return_value = payload
    return resp


def test_http_200_parses_exact_reference_and_pending_action(monkeypatch):
    _store()
    ticket = {
        "data": {
            "reference_number": REF,
            "status": "Pending Action",
            "department_name": "Food and Civil Supplies",
            "updated_at": "2026-09-01T10:00:00Z",
        }
    }
    conv = {"data": [{"id": "r1", "message": "Assigned", "created_at": "2026-09-01T11:00:00Z", "parent_id": "c1"}]}
    get = Mock(side_effect=[_response(200, ticket), _response(200, conv)])
    monkeypatch.setattr("modules.govt_sync.adapters.tamil_nadu_http.requests.get", get)

    result = TamilNaduHTTPStatusAdapter(_portal()).check_status(REF, tenant_id=1)

    assert result.checked is True
    assert result.status == "submitted"
    assert result.raw_portal_status == "Pending Action"
    assert result.portal_detail["department_name"] == "Food and Civil Supplies"
    assert result.portal_detail["replies"][0]["parent_id"] == "c1"
    assert result.failure_kind is None  # a genuine success is never classified as a failure
    assert get.call_args_list[0].args[0].endswith(f"/portal/api/tickets/{RECORD_ID}")
    assert get.call_args_list[1].args[0].endswith(f"/portal/api/tickets/{RECORD_ID}/conversations")
    with test_engine.connect() as conn:
        assert conn.execute(text("SELECT last_used_at FROM govt_cookie_sessions")).scalar() is not None


def test_http_wrong_reference_fails_closed_without_status_update(monkeypatch):
    _store()
    monkeypatch.setattr(
        "modules.govt_sync.adapters.tamil_nadu_http.requests.get",
        Mock(return_value=_response(200, {"data": {"reference_number": "TN/OTHER/CBE/P/PORTAL/01SEP26/18968314", "status": "Pending Action"}})),
    )
    result = TamilNaduHTTPStatusAdapter(_portal()).check_status(REF, tenant_id=1)
    assert result.checked is False
    assert result.status == ""
    # The response was valid JSON but didn't self-report the reference we
    # asked about — a structural match failure, not an HTTP-layer signal.
    assert result.failure_kind == StatusFailureKind.PARSE_FAILED


@pytest.mark.parametrize(
    "status_code,needs_verification,expected_failure_kind",
    [
        (401, True, StatusFailureKind.SESSION_EXPIRED),
        (403, True, StatusFailureKind.SESSION_EXPIRED),
        (404, False, StatusFailureKind.REFERENCE_NOT_FOUND),
        (500, False, StatusFailureKind.PORTAL_UNAVAILABLE),
        (502, False, StatusFailureKind.PORTAL_UNAVAILABLE),
    ],
)
def test_http_error_classification(status_code, needs_verification, expected_failure_kind, monkeypatch):
    _store()
    monkeypatch.setattr("modules.govt_sync.adapters.tamil_nadu_http.requests.get", Mock(return_value=_response(status_code, {})))
    result = TamilNaduHTTPStatusAdapter(_portal()).check_status(REF, tenant_id=1)
    assert result.checked is False
    assert result.needs_verification is needs_verification
    # The new internal classification never changes any pre-existing,
    # externally-observable field — only adds the label alongside them.
    assert result.failure_kind == expected_failure_kind
    with test_engine.connect() as conn:
        requires_verification = conn.execute(text("SELECT requires_verification FROM govt_cookie_sessions")).scalar()
    if needs_verification:
        assert bool(requires_verification) is True


def test_unexpected_non_200_status_is_classified_unknown(monkeypatch):
    """A status code this adapter doesn't specifically branch on (e.g. a
    3xx it saw despite allow_redirects=False, or an unmapped 4xx) — no
    adapters currently have a structured signal for WHY, so it stays
    UNKNOWN rather than guessing."""
    _store()
    monkeypatch.setattr("modules.govt_sync.adapters.tamil_nadu_http.requests.get", Mock(return_value=_response(418, {})))
    result = TamilNaduHTTPStatusAdapter(_portal()).check_status(REF, tenant_id=1)
    assert result.checked is False
    assert result.raw_portal_status == "Tamil Nadu status check was inconclusive."
    assert result.failure_kind == StatusFailureKind.UNKNOWN


def test_timeout_and_malformed_response_are_transient_or_inconclusive(monkeypatch):
    _store()
    monkeypatch.setattr("modules.govt_sync.adapters.tamil_nadu_http.requests.get", Mock(side_effect=requests.Timeout()))
    result = TamilNaduHTTPStatusAdapter(_portal()).check_status(REF, tenant_id=1)
    assert result.checked is False
    assert result.needs_verification is False
    assert result.raw_portal_status == "Tamil Nadu portal timed out."
    assert result.failure_kind == StatusFailureKind.TIMEOUT

    _store()
    monkeypatch.setattr("modules.govt_sync.adapters.tamil_nadu_http.requests.get", Mock(return_value=_response(200, ValueError("bad"))))
    result = TamilNaduHTTPStatusAdapter(_portal()).check_status(REF, tenant_id=1)
    assert result.checked is False
    assert result.needs_verification is False
    assert result.raw_portal_status == "Tamil Nadu returned an unreadable response."
    assert result.failure_kind == StatusFailureKind.PARSE_FAILED


def test_network_error_classified_as_network_failure(monkeypatch):
    _store()
    monkeypatch.setattr("modules.govt_sync.adapters.tamil_nadu_http.requests.get", Mock(side_effect=requests.ConnectionError()))
    result = TamilNaduHTTPStatusAdapter(_portal()).check_status(REF, tenant_id=1)
    assert result.checked is False
    assert result.needs_verification is False
    assert result.raw_portal_status == "Tamil Nadu portal could not be reached."
    assert result.failure_kind == StatusFailureKind.NETWORK_FAILURE


def test_unrecognised_status_text_classified_as_parse_failed(monkeypatch):
    """A 200, matching reference, but portal wording that doesn't map onto
    any known STATUS_KEYWORDS bucket — a normalization/parsing failure,
    not a legitimate empty result."""
    _store()
    ticket = {"data": {"reference_number": REF, "status": "Some Brand New Portal Wording Nobody Has Seen"}}
    monkeypatch.setattr("modules.govt_sync.adapters.tamil_nadu_http.requests.get", Mock(return_value=_response(200, ticket)))
    result = TamilNaduHTTPStatusAdapter(_portal()).check_status(REF, tenant_id=1)
    assert result.checked is False
    assert result.raw_portal_status == "Some Brand New Portal Wording Nobody Has Seen"
    assert result.failure_kind == StatusFailureKind.PARSE_FAILED


def test_missing_mapping_never_attempts_numeric_neighbors(monkeypatch):
    _store(mapping={})
    get = Mock()
    monkeypatch.setattr("modules.govt_sync.adapters.tamil_nadu_http.requests.get", get)
    result = TamilNaduHTTPStatusAdapter(_portal()).check_status(REF, tenant_id=1)
    assert result.checked is False
    assert result.needs_verification is False
    assert result.raw_portal_status == "Tamil Nadu grievance is not mapped to the authenticated portal session."
    # A valid cookie session may exist even though no ticket mapping is
    # known for THIS reference — that is not evidence of an auth/session
    # problem, so it must NOT be classified AUTH_REQUIRED. UNKNOWN is the
    # correct, evidence-based classification (Phase 2A correction).
    assert result.failure_kind == StatusFailureKind.UNKNOWN
    get.assert_not_called()


def test_multiple_mapped_cases_reuse_one_encrypted_session(monkeypatch):
    _store(mapping={REF: RECORD_ID, REF_TWO: RECORD_ID_TWO})
    ticket_one = {"data": {"reference_number": REF, "status": "Pending Action"}}
    ticket_two = {"data": {"reference_number": REF_TWO, "status": "Pending Action"}}
    get = Mock(side_effect=[
        _response(200, ticket_one), _response(200, {"data": []}),
        _response(200, ticket_two), _response(200, {"data": []}),
    ])
    monkeypatch.setattr("modules.govt_sync.adapters.tamil_nadu_http.requests.get", get)

    adapter = TamilNaduHTTPStatusAdapter(_portal())
    assert adapter.check_status(REF, tenant_id=1).checked is True
    assert adapter.check_status(REF_TWO, tenant_id=1).checked is True
    assert cookie_sessions.load_cookie_session(1, 10).ticket_mappings == {
        REF: RECORD_ID,
        REF_TWO: RECORD_ID_TWO,
    }
    assert get.call_args_list[0].args[0].endswith(f"/portal/api/tickets/{RECORD_ID}")
    assert get.call_args_list[2].args[0].endswith(f"/portal/api/tickets/{RECORD_ID_TWO}")


def test_cookie_key_error_through_adapter_classified_auth_required(monkeypatch):
    """Exercises the adapter's own CookieSessionKeyError branch directly
    (not just cookie_sessions.load_cookie_session() in isolation) — a
    pre-flight condition, no HTTP request possible, so AUTH_REQUIRED
    rather than SESSION_EXPIRED."""
    _store()
    monkeypatch.delenv("GOVT_COOKIE_SESSION_KEY", raising=False)
    get = Mock()
    monkeypatch.setattr("modules.govt_sync.adapters.tamil_nadu_http.requests.get", get)
    result = TamilNaduHTTPStatusAdapter(_portal()).check_status(REF, tenant_id=1)
    assert result.checked is False
    assert result.needs_verification is True
    assert result.raw_portal_status == "Tamil Nadu access needs verification. Please sign in again."
    assert result.failure_kind == StatusFailureKind.AUTH_REQUIRED
    get.assert_not_called()


def _auth_headers():
    token = jwt.encode({"sub": "mp_tn", "tenant_id": 1, "iat": datetime.now(timezone.utc).timestamp()}, os.environ["JWT_SECRET"], algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def test_promote_session_encrypts_cookies_and_returns_no_secret_or_record_id(monkeypatch):
    import main

    _bind_engine()
    main.engine = test_engine
    fake_context = Mock()
    fake_context.cookies = AsyncMock(return_value=_cookie_jar())
    fake_page = Mock()
    fake_session = Mock(
        tenant_id=1,
        case_id=40,
        portal=_portal(),
        page=fake_page,
        context=fake_context,
    )
    monkeypatch.setattr("modules.govt_sync.browser_session.get_live_session", Mock(return_value=fake_session))
    monkeypatch.setattr(
        "modules.govt_sync.status.tamil_nadu.TamilNaduStatusAdapter.check_status_and_observe_record_id",
        AsyncMock(return_value=(Mock(state="STATUS_CHECKED"), RECORD_ID)),
    )

    resp = TestClient(main.app).post(
        "/api/cases/40/govt/session/sess-tn/tamil-nadu/promote-session",
        headers=_auth_headers(),
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "success": True,
        "promoted": True,
        "needs_verification": False,
        "message": "Tamil Nadu access verified for status checks.",
    }
    assert COOKIE_VALUE not in resp.text
    assert RECORD_ID not in resp.text

    with test_engine.connect() as conn:
        stored = conn.execute(text("SELECT encrypted_cookie_jar, ticket_mappings FROM govt_cookie_sessions")).mappings().one()
    assert COOKIE_VALUE not in stored["encrypted_cookie_jar"]
    assert RECORD_ID in stored["ticket_mappings"]


def test_promotions_merge_existing_mappings_and_new_observation_wins(monkeypatch):
    import main

    _bind_engine()
    main.engine = test_engine
    old_ref = "TN/OLD/REFERENCE/1"
    old_record_id = "35665012402750000"
    refreshed_record_id = "35665012402750999"
    _store(mapping={old_ref: old_record_id, REF: "stale-record-id"})

    sessions = {
        "sess-one": Mock(tenant_id=1, case_id=40, portal=_portal(), page=Mock(), context=Mock()),
        "sess-two": Mock(tenant_id=1, case_id=41, portal=_portal(), page=Mock(), context=Mock()),
        "sess-refresh": Mock(tenant_id=1, case_id=40, portal=_portal(), page=Mock(), context=Mock()),
    }
    for session in sessions.values():
        session.context.cookies = AsyncMock(return_value=_cookie_jar())
    monkeypatch.setattr(
        "modules.govt_sync.browser_session.get_live_session",
        lambda session_id: sessions.get(session_id),
    )
    observed = AsyncMock(side_effect=[
        (Mock(state="STATUS_CHECKED"), RECORD_ID),
        (Mock(state="STATUS_CHECKED"), RECORD_ID_TWO),
        (Mock(state="STATUS_CHECKED"), refreshed_record_id),
    ])
    monkeypatch.setattr(
        "modules.govt_sync.status.tamil_nadu.TamilNaduStatusAdapter.check_status_and_observe_record_id",
        observed,
    )
    client = TestClient(main.app)

    assert client.post(
        "/api/cases/40/govt/session/sess-one/tamil-nadu/promote-session", headers=_auth_headers(),
    ).status_code == 200
    assert client.post(
        "/api/cases/41/govt/session/sess-two/tamil-nadu/promote-session", headers=_auth_headers(),
    ).status_code == 200
    assert client.post(
        "/api/cases/40/govt/session/sess-refresh/tamil-nadu/promote-session", headers=_auth_headers(),
    ).status_code == 200

    stored = cookie_sessions.load_cookie_session(1, 10)
    assert stored.ticket_mappings == {
        old_ref: old_record_id,
        REF: refreshed_record_id,
        REF_TWO: RECORD_ID_TWO,
    }
    with test_engine.connect() as conn:
        encrypted = conn.execute(text("SELECT encrypted_cookie_jar FROM govt_cookie_sessions")).scalar()
    assert COOKIE_VALUE not in encrypted


# ─── StatusResult backward-compatibility (Phase 2A additive-field proof) ───
#
# StatusResult is a @dataclass, so equality/repr are structural (dataclass-
# generated) and every field mentioned below is keyword-only in EVERY real
# construction site in this repo (confirmed by grepping every
# `StatusResult(` call before adding failure_kind — none of them construct
# positionally), so a new field with a default cannot break any existing
# caller regardless of where it sits in the field order.

def test_status_result_old_style_success_construction_still_works():
    result = StatusResult(status="submitted", checked=True, raw_portal_status="Registered")
    assert result.status == "submitted"
    assert result.checked is True
    assert result.needs_verification is False
    assert result.failure_kind is None  # new field defaults to None, untouched by old-style callers


def test_status_result_old_style_inconclusive_construction_still_works():
    result = StatusResult(status="", checked=False, raw_portal_status="Unrecognised page text")
    assert result.checked is False
    assert result.failure_kind is None


def test_status_result_needs_verification_default_unaffected_by_new_field():
    result = StatusResult(status="", checked=False, needs_verification=True)
    assert result.needs_verification is True
    assert result.failure_kind is None


def test_status_result_equality_and_repr_include_failure_kind_consistently():
    """Dataclass-generated __eq__/__repr__ automatically include every
    field, including the new one — two results are equal only if
    failure_kind also matches, and repr() doesn't raise. This is expected,
    additive dataclass behavior, not something adapters need to account
    for (none of them compare StatusResult instances for equality today)."""
    a = StatusResult(status="", checked=False, failure_kind=StatusFailureKind.TIMEOUT)
    b = StatusResult(status="", checked=False, failure_kind=StatusFailureKind.TIMEOUT)
    c = StatusResult(status="", checked=False)
    assert a == b
    assert a != c
    assert "failure_kind" in repr(a)


def test_status_result_explicit_failure_kind_construction():
    result = StatusResult(status="", checked=False, failure_kind=StatusFailureKind.NETWORK_FAILURE)
    assert result.failure_kind == StatusFailureKind.NETWORK_FAILURE
    assert result.failure_kind == "NETWORK_FAILURE"  # str-Enum: compares equal to its plain string value


def test_other_adapters_returning_no_failure_kind_are_unaffected():
    """Characterizes that an adapter which has NOT adopted the taxonomy
    (every adapter except TamilNaduHTTPStatusAdapter, as of Phase 2A)
    continues to produce a perfectly ordinary StatusResult — accessing
    failure_kind on it is always safe and always None, never an
    AttributeError, regardless of which adapter produced it."""
    from modules.govt_sync.adapters.manual import ManualAssistedAdapter

    result = ManualAssistedAdapter({"status_check_mode": "login_required"}).check_status("REF/1")
    assert result.checked is False
    assert result.failure_kind is None
