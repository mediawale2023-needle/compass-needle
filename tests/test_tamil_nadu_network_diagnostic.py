"""
tests/test_tn_network_diagnostic.py — Phase 1 controlled-proof harness for
the Tamil Nadu Playwright-to-HTTP migration investigation.

Everything here is mocked: no real Playwright browser, no real HTTP request,
no real government portal. This file proves the harness's own mechanics —
redaction, evidence collection, record-id discovery, outcome classification,
and the disabled-by-default/scope-limited API gate — never a live result.

Reuses the already-working Fake* Playwright-surface fixtures from
tests/test_tamil_nadu_status.py rather than re-inventing them, so the
"drives the exact same production check_status_on_page()" claim in
tn_network_diagnostic.py's docstring is actually exercised against the same
mocks that file's own tests already trust.
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
TEST_DB_URL = "sqlite:///./test_tn_network_diagnostic.db"

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

from modules.govt_sync.status.tn_network_diagnostic import (
    OUTCOME_API_REQUIRED,
    OUTCOME_HTTP_SUCCESS,
    OUTCOME_RECORD_ID_UNRESOLVED,
    OUTCOME_REDIRECT_TO_LOGIN,
    OUTCOME_SPA_SHELL,
    OUTCOME_UNDETERMINED,
    TnDiagnosticReport,
    _classify_outcome,
    _discover_ticket_record_id,
    _NetworkEvidenceCollector,
    _NetworkEvidenceEntry,
    _redact_url,
    capture_tn_diagnostic,
)
from tests.test_tamil_nadu_status import REF, _card, _detail_body, _detail_selectors, _list_page, _tn_portal

test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False)
client = TestClient(main.app, raise_server_exceptions=False)


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
        for table_name in ("govt_submission_log", "case_activity_log", "cases", "govt_portals",
                            "tenant_overrides", "token_blocklist", "users", "tenant_profiles", "tenants"):
            conn.execute(text(f"DELETE FROM {table_name}"))  # nosec B608
        conn.execute(text(
            "INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active, created_at) "
            "VALUES (1, 'Priya Sharma', 'Kalyan Dombivli', '+919000000002', 'Pro', 1, :now)"
        ), {"now": now})
        conn.execute(text(
            "INSERT INTO tenant_profiles (tenant_id, mp_name, constituency, state, house, created_at) "
            "VALUES (1, 'Shri Priya Sharma', 'Kalyan Dombivli', 'Tamil Nadu', 'Lok Sabha', :now)"
        ), {"now": now})
        conn.execute(text(
            "INSERT INTO users (tenant_id, username, password_hash, role, constituency, house, display_name, is_active) "
            "VALUES (1, 'mp_priya', :password_hash, 'mp', 'Kalyan Dombivli', 'Lok Sabha', 'Priya MP', 1)"
        ), {"password_hash": hash_password("Password1")})
        conn.execute(text(
            "INSERT INTO govt_portals (id, state, portal_name, portal_type, base_url, status_check_mode, "
            "department_taxonomy, field_schema, otp_bound, active, is_primary, verification_status, "
            "live_session_supported) VALUES "
            "(1, 'Tamil Nadu', 'Tamil Nadu CM Helpline (Mudhalvarin Mugavari)', 'state_branded', "
            "'https://cmhelpline.tnega.org', 'login_required', '{}', '{}', 0, 1, 1, 'confirmed', 1)"
        ), {})
        conn.execute(text(
            "INSERT INTO cases (id, tenant_id, user_phone, raw_message, category, status, created_at, "
            "govt_portal_id, govt_status, govt_reference_number, is_deleted) VALUES "
            f"(40, 1, '+919111111140', 'No food ration', 'Infrastructure & Utilities', 'in_progress', :now, "
            f"1, 'submitted', '{REF}', 0)"
        ), {"now": now})


# ─── Pure helper tests ──────────────────────────────────────────────────────

def test_redact_url_strips_query_values_keeps_keys():
    redacted = _redact_url("https://cmhelpline.tnega.org/portal/ta/myarea?viewId=abc123&sortBy=recentThread")
    assert "abc123" not in redacted
    assert "recentThread" not in redacted
    assert "viewId=" in redacted
    assert "sortBy=" in redacted
    assert redacted.startswith("https://cmhelpline.tnega.org/portal/ta/myarea?")


def test_redact_url_handles_no_query_and_garbage_gracefully():
    assert _redact_url("https://cmhelpline.tnega.org/portal/ta/myarea") == "https://cmhelpline.tnega.org/portal/ta/myarea"
    assert _redact_url("") == ""
    assert _redact_url(None) in ("", "<unparseable-url>")


def test_redact_url_never_leaks_a_session_style_token_value():
    redacted = _redact_url("https://cmhelpline.tnega.org/api/data?token=SUPERSECRETVALUE123")
    assert "SUPERSECRETVALUE123" not in redacted


def _entry(url, resource_type="document"):
    return _NetworkEvidenceEntry(method="GET", url=url, resource_type=resource_type)


def test_discover_ticket_record_id_from_real_evidence():
    evidence = [
        _entry("https://cmhelpline.tnega.org/portal/ta/myarea"),
        _entry("https://cmhelpline.tnega.org/portal/ta/ticket/18968314"),
    ]
    assert _discover_ticket_record_id(evidence) == "18968314"


def test_discover_ticket_record_id_returns_none_when_absent():
    evidence = [_entry("https://cmhelpline.tnega.org/portal/ta/myarea")]
    assert _discover_ticket_record_id(evidence) is None


def test_discover_ticket_record_id_never_guesses_from_query_string():
    # A query-string mention of something ticket-shaped must not be treated
    # as the record id — only the URL PATH shape counts.
    evidence = [_entry("https://cmhelpline.tnega.org/portal/ta/myarea?ref=ticket/99999")]
    assert _discover_ticket_record_id(evidence) is None


# ─── /portal/api/tickets/{numeric_id} discovery (2026-09-07 controlled proof) ──
#
# The first live controlled proof observed the REAL ticket-detail traffic
# as GET /portal/api/tickets/{numeric_record_id} — not the originally
# hypothesized /portal/ta/ticket/{id} shape — and the diagnostic's
# extraction logic didn't recognize it (RECORD_ID_UNRESOLVED). These tests
# lock in the corrected, deterministic matching rule.

_TN_HOST = "cmhelpline.tnega.org"


def test_ticket_api_canonical_single_ticket_request_is_detected():
    evidence = [
        _entry(f"https://{_TN_HOST}/portal/api/tickets/35665012402750744?include=fields"),
    ]
    assert _discover_ticket_record_id(evidence, expected_host=_TN_HOST) == "35665012402750744"


def test_ticket_api_prefers_canonical_over_conversations_subresource():
    # Real evidence order from the proof run: the canonical ticket request,
    # then its /conversations sub-resource. The canonical one must win
    # regardless of list order.
    evidence = [
        _entry(f"https://{_TN_HOST}/portal/api/tickets/35665012402750744/conversations?page=1"),
        _entry(f"https://{_TN_HOST}/portal/api/tickets/35665012402750744"),
    ]
    assert _discover_ticket_record_id(evidence, expected_host=_TN_HOST) == "35665012402750744"


def test_ticket_api_list_endpoint_without_id_is_ignored():
    evidence = [_entry(f"https://{_TN_HOST}/portal/api/tickets?viewId=abc")]
    assert _discover_ticket_record_id(evidence, expected_host=_TN_HOST) is None


def test_ticket_api_ticketsfields_is_ignored():
    evidence = [_entry(f"https://{_TN_HOST}/portal/api/ticketsFields")]
    assert _discover_ticket_record_id(evidence, expected_host=_TN_HOST) is None


def test_ticket_api_ticketscountbyfieldvalues_is_ignored():
    evidence = [_entry(f"https://{_TN_HOST}/portal/api/ticketsCountByFieldValues")]
    assert _discover_ticket_record_id(evidence, expected_host=_TN_HOST) is None


def test_ticket_api_count_endpoint_is_ignored():
    evidence = [_entry(f"https://{_TN_HOST}/portal/api/tickets/count")]
    assert _discover_ticket_record_id(evidence, expected_host=_TN_HOST) is None


def test_ticket_api_conversations_subresource_alone_is_ignored():
    evidence = [_entry(f"https://{_TN_HOST}/portal/api/tickets/35665012402750744/conversations")]
    assert _discover_ticket_record_id(evidence, expected_host=_TN_HOST) is None


def test_ticket_api_threads_subresource_is_ignored():
    evidence = [_entry(f"https://{_TN_HOST}/portal/api/tickets/35665012402750744/threads/99")]
    assert _discover_ticket_record_id(evidence, expected_host=_TN_HOST) is None


def test_ticket_api_attachments_subresource_is_ignored():
    evidence = [_entry(f"https://{_TN_HOST}/portal/api/tickets/35665012402750744/attachments")]
    assert _discover_ticket_record_id(evidence, expected_host=_TN_HOST) is None


def test_ticket_api_unrelated_host_is_ignored():
    # Same exact canonical path shape, but on a host that is not the
    # configured TN portal's own base_url host.
    evidence = [_entry("https://evil.example.com/portal/api/tickets/35665012402750744")]
    assert _discover_ticket_record_id(evidence, expected_host=_TN_HOST) is None


def test_ticket_api_malformed_non_numeric_id_is_ignored():
    for bad_id in ("18968314x", "abc", "18968314-suffix", "18968314/extra"):
        evidence = [_entry(f"https://{_TN_HOST}/portal/api/tickets/{bad_id}")]
        assert _discover_ticket_record_id(evidence, expected_host=_TN_HOST) is None, bad_id


def test_ticket_api_discovery_respects_existing_redaction_and_never_touches_query_values():
    # The redaction guarantee (_redact_url strips query VALUES, keeps only
    # key names) must still hold for canonical ticket-detail evidence —
    # discovery must work purely off the redacted URL, never a raw one.
    raw_url = f"https://{_TN_HOST}/portal/api/tickets/35665012402750744?authToken=SUPERSECRETVALUE123"
    redacted = _redact_url(raw_url)
    assert "SUPERSECRETVALUE123" not in redacted
    evidence = [_entry(redacted)]
    assert _discover_ticket_record_id(evidence, expected_host=_TN_HOST) == "35665012402750744"


def test_classify_outcome_record_id_unresolved_takes_priority():
    assert _classify_outcome(replay_result="REPLAY_SUCCESS", record_id=None, non_document_count=3) == OUTCOME_RECORD_ID_UNRESOLVED


def test_classify_outcome_success():
    assert _classify_outcome(replay_result="REPLAY_SUCCESS", record_id="18968314", non_document_count=0) == OUTCOME_HTTP_SUCCESS


def test_classify_outcome_redirect_to_login():
    assert _classify_outcome(replay_result="REPLAY_REDIRECTED_TO_LOGIN", record_id="18968314", non_document_count=0) == OUTCOME_REDIRECT_TO_LOGIN


def test_classify_outcome_anonymous_with_xhr_evidence_is_api_required():
    assert _classify_outcome(replay_result="REPLAY_ANONYMOUS", record_id="18968314", non_document_count=2) == OUTCOME_API_REQUIRED


def test_classify_outcome_anonymous_without_xhr_evidence_is_auth_failure():
    from modules.govt_sync.status.tn_network_diagnostic import OUTCOME_AUTH_FAILURE
    assert _classify_outcome(replay_result="REPLAY_ANONYMOUS", record_id="18968314", non_document_count=0) == OUTCOME_AUTH_FAILURE


def test_classify_outcome_inconclusive_with_xhr_evidence_is_spa_shell():
    assert _classify_outcome(replay_result="REPLAY_INCONCLUSIVE", record_id="18968314", non_document_count=1) == OUTCOME_SPA_SHELL


def test_classify_outcome_inconclusive_without_xhr_evidence_is_undetermined():
    assert _classify_outcome(replay_result="REPLAY_INCONCLUSIVE", record_id="18968314", non_document_count=0) == OUTCOME_UNDETERMINED


def test_classify_outcome_never_attempted_replay_is_undetermined():
    assert _classify_outcome(replay_result=None, record_id="18968314", non_document_count=0) == OUTCOME_UNDETERMINED


# ─── Network evidence collector (direct, no real Playwright) ───────────────

class _FakeContext:
    def __init__(self):
        self._handlers: dict[str, list] = {}

    def on(self, event_name, handler):
        self._handlers.setdefault(event_name, []).append(handler)

    def remove_listener(self, event_name, handler):
        if event_name in self._handlers and handler in self._handlers[event_name]:
            self._handlers[event_name].remove(handler)

    def fire_request(self, request):
        for h in list(self._handlers.get("request", [])):
            h(request)

    def fire_response(self, response):
        for h in list(self._handlers.get("response", [])):
            h(response)


class _FakeRequest:
    def __init__(self, method, url, resource_type="document"):
        self.method = method
        self.url = url
        self.resource_type = resource_type


class _FakeResponse:
    def __init__(self, request, status, content_type=None, body=b""):
        self.request = request
        self.status = status
        self._content_type = content_type
        self._body = body

    async def header_value(self, name):
        # Only the one explicitly-named safe header should ever be requested —
        # anything else is a bug in the collector, so fail loudly in tests.
        assert name == "content-type", f"collector requested an unexpected header: {name}"
        return self._content_type

    async def body(self):
        return self._body


def test_collector_attach_registers_request_and_response_listeners():
    ctx = _FakeContext()
    collector = _NetworkEvidenceCollector()
    collector.attach(ctx)
    assert collector._on_request in ctx._handlers["request"]
    assert collector._on_response in ctx._handlers["response"]
    collector.detach()
    assert collector._on_request not in ctx._handlers.get("request", [])
    assert collector._on_response not in ctx._handlers.get("response", [])


def test_collector_records_safe_metadata_only():
    async def run():
        ctx = _FakeContext()
        collector = _NetworkEvidenceCollector()
        collector.attach(ctx)
        req = _FakeRequest("GET", "https://cmhelpline.tnega.org/portal/ta/myarea?viewId=SECRET123", resource_type="document")
        ctx.fire_request(req)
        resp = _FakeResponse(req, 200, content_type="text/html; charset=utf-8", body=b"x" * 42)
        ctx.fire_response(resp)
        await asyncio.sleep(0.05)  # let the background content-metadata task complete
        collector.detach()
        return collector.entries

    entries = asyncio.run(run())
    assert len(entries) == 1
    entry = entries[0].to_safe_dict()
    assert entry["method"] == "GET"
    assert "SECRET123" not in entry["url"]
    assert entry["status"] == 200
    assert entry["content_type"] == "text/html; charset=utf-8"
    assert entry["response_bytes"] == 42
    assert entry["resource_type"] == "document"


def test_collector_caps_number_of_entries():
    from modules.govt_sync.status import tn_network_diagnostic as mod

    ctx = _FakeContext()
    collector = _NetworkEvidenceCollector()
    collector.attach(ctx)
    for i in range(mod._MAX_EVIDENCE_ENTRIES + 25):
        ctx.fire_request(_FakeRequest("GET", f"https://cmhelpline.tnega.org/x/{i}"))
    collector.detach()
    assert len(collector.entries) == mod._MAX_EVIDENCE_ENTRIES


def test_collector_never_calls_generic_headers_accessor():
    """Defense-in-depth: a FakeResponse without .headers/.all_headers() must
    still work fine — proves the collector genuinely never reaches for them."""
    class _NoGenericHeadersResponse(_FakeResponse):
        headers = None
        def all_headers(self):
            raise AssertionError("collector must never call all_headers()")

    async def run():
        ctx = _FakeContext()
        collector = _NetworkEvidenceCollector()
        collector.attach(ctx)
        req = _FakeRequest("GET", "https://cmhelpline.tnega.org/portal/ta/myarea")
        ctx.fire_request(req)
        ctx.fire_response(_NoGenericHeadersResponse(req, 200, content_type="text/html"))
        await asyncio.sleep(0.05)
        collector.detach()
        return collector.entries

    entries = asyncio.run(run())
    assert entries[0].content_type == "text/html"


# ─── capture_tn_diagnostic() reference-number guard ────────────────────────

def test_capture_diagnostic_refuses_any_reference_without_the_allowed_grievance():
    with pytest.raises(ValueError):
        asyncio.run(capture_tn_diagnostic(session=MagicMock(), reference_number="TN/OTHER/CASE/P/PORTAL/01SEP26/99999999"))


# ─── End-to-end: real production check_status_on_page() + evidence capture ─

class _FakeSession:
    """Minimal stand-in for modules.govt_sync.browser_session.LiveSession —
    only the attributes capture_tn_diagnostic()/check_status_on_page() ever
    read (.context, .page, .portal, .session_id)."""
    def __init__(self, page, context, portal):
        self.page = page
        self.context = context
        self.portal = portal
        self.session_id = "fake-session-1"


def _open_detail_with_network_evidence(ctx, page_box, *, status="Disposed"):
    """Wires the existing test_tamil_nadu_status.py card on_click callback so
    it ALSO fires a fake context request/response for the ticket-detail
    navigation — simulating what a real browser generates during that same
    click, which our FakePage (borrowed from that other test file) does not
    do on its own since it isn't real Playwright. Takes a mutable `page_box`
    dict (populated with the real page AFTER this closure is built, since
    the page's own construction needs this very on_click callback first) so
    the closure always mutates the actual, final page object, not a stale
    reference to one built before the card existed."""
    def _click():
        req = _FakeRequest("GET", "https://cmhelpline.tnega.org/portal/ta/ticket/18968314", resource_type="document")
        ctx.fire_request(req)
        ctx.fire_response(_FakeResponse(req, 200, content_type="text/html; charset=utf-8", body=b"<html></html>"))
        page_box["page"].set_state(
            url="https://cmhelpline.tnega.org/portal/ta/ticket/18968314",
            body_text=_detail_body(status),
            selectors=_detail_selectors(status),
        )
    return _click


@patch("scripts.tn_session_replay_poc.tn_session_replay_experiment", new_callable=AsyncMock)
def test_capture_diagnostic_end_to_end_success_path(mock_replay):
    mock_replay.return_value = "REPLAY_SUCCESS"
    ctx = _FakeContext()
    page_box = {}
    page = _list_page([_card(f"{REF} Pending Action", status_child="Pending Action",
                              on_click=_open_detail_with_network_evidence(ctx, page_box))])
    page_box["page"] = page
    session = _FakeSession(page=page, context=ctx, portal=_tn_portal())

    report = asyncio.run(capture_tn_diagnostic(session, REF))

    assert report.playwright_result["state"] == "STATUS_CHECKED"
    assert report.playwright_result["normalized_status"] == "resolved"
    assert report.discovered_ticket_record_id == "18968314"
    assert report.http_replay_result == "REPLAY_SUCCESS"
    assert report.outcome == OUTCOME_HTTP_SUCCESS
    mock_replay.assert_awaited_once_with("fake-session-1", "18968314")

    # Security: the safe dict must never carry any credential-shaped content.
    safe = report.to_safe_dict()
    dumped = str(safe)
    for forbidden in ("Cookie", "cookie=", "Set-Cookie", "Authorization", "authtoken", "session_id=fake"):
        assert forbidden not in dumped or forbidden == "session_id=fake"  # session_id itself isn't a secret, only cookies/tokens are
    assert "http_replay_result" in safe and "network_evidence" in safe


def _open_detail_with_ticket_api_network_evidence(ctx, page_box, *, status="Pending Action"):
    """Same shape as _open_detail_with_network_evidence, but simulates the
    REAL traffic observed in the 2026-09-07 controlled proof run: the
    canonical GET /portal/api/tickets/{id} request plus its /conversations
    sub-resource — proving the fixed discovery logic picks the canonical
    one over the sub-resource end-to-end, not just at the unit level."""
    def _click():
        detail_req = _FakeRequest(
            "GET", "https://cmhelpline.tnega.org/portal/api/tickets/35665012402750744", resource_type="xhr",
        )
        ctx.fire_request(detail_req)
        ctx.fire_response(_FakeResponse(detail_req, 200, content_type="application/json", body=b"{}"))

        conversations_req = _FakeRequest(
            "GET", "https://cmhelpline.tnega.org/portal/api/tickets/35665012402750744/conversations", resource_type="xhr",
        )
        ctx.fire_request(conversations_req)
        ctx.fire_response(_FakeResponse(conversations_req, 200, content_type="application/json", body=b"{}"))

        page_box["page"].set_state(
            url="https://cmhelpline.tnega.org/portal/ta/myarea",
            body_text=_detail_body(status),
            selectors=_detail_selectors(status),
        )
    return _click


@patch("scripts.tn_session_replay_poc.tn_session_replay_experiment", new_callable=AsyncMock)
def test_capture_diagnostic_discovers_real_observed_ticket_api_shape_end_to_end(mock_replay):
    mock_replay.return_value = "REPLAY_SUCCESS"
    ctx = _FakeContext()
    page_box = {}
    page = _list_page([_card(f"{REF} Pending Action", status_child="Pending Action",
                              on_click=_open_detail_with_ticket_api_network_evidence(ctx, page_box))])
    page_box["page"] = page
    session = _FakeSession(page=page, context=ctx, portal=_tn_portal())

    report = asyncio.run(capture_tn_diagnostic(session, REF))

    assert report.discovered_ticket_record_id == "35665012402750744"
    assert report.outcome == OUTCOME_HTTP_SUCCESS
    mock_replay.assert_awaited_once_with("fake-session-1", "35665012402750744")


def test_capture_diagnostic_record_id_unresolved_when_no_ticket_url_observed():
    async def run():
        ctx = _FakeContext()
        # A card whose click does NOT produce any /portal/ta/ticket/ request —
        # simulating an SPA that navigates without a full document request.
        def _click_no_network_evidence():
            page.set_state(
                url="https://cmhelpline.tnega.org/portal/ta/myarea",  # URL never actually changes
                body_text=_detail_body("Disposed"),
                selectors=_detail_selectors("Disposed"),
            )
        page = _list_page([_card(f"{REF} Pending Action", status_child="Pending Action", on_click=_click_no_network_evidence)])
        session = _FakeSession(page=page, context=ctx, portal=_tn_portal())
        with patch("scripts.tn_session_replay_poc.tn_session_replay_experiment", new_callable=AsyncMock) as mock_replay:
            report = await capture_tn_diagnostic(session, REF)
            mock_replay.assert_not_awaited()
        return report

    report = asyncio.run(run())
    assert report.discovered_ticket_record_id is None
    assert report.http_replay_result is None
    assert report.outcome == OUTCOME_RECORD_ID_UNRESOLVED


# ─── Endpoint gating (disabled-by-default, scope-limited) ──────────────────

def test_endpoint_404s_when_diagnostic_flag_is_not_set():
    _seed_database()
    os.environ.pop("GOVT_SYNC_TN_HTTP_DIAGNOSTIC_ENABLED", None)
    resp = client.post(
        "/api/cases/40/govt/session/some-session/tamil-nadu/diagnostic/http-replay-proof",
        headers=_auth_headers(),
    )
    assert resp.status_code == 404


def test_endpoint_404s_when_flag_explicitly_false():
    _seed_database()
    with patch.dict(os.environ, {"GOVT_SYNC_TN_HTTP_DIAGNOSTIC_ENABLED": "false"}):
        resp = client.post(
            "/api/cases/40/govt/session/some-session/tamil-nadu/diagnostic/http-replay-proof",
            headers=_auth_headers(),
        )
    assert resp.status_code == 404


def test_endpoint_403s_for_a_reference_outside_the_authorized_grievance():
    _seed_database()
    with test_engine.begin() as conn:
        conn.execute(text(
            "UPDATE cases SET govt_reference_number = 'TN/OTHER/CASE/P/PORTAL/01SEP26/99999999' WHERE id = 40"
        ))
    with patch.dict(os.environ, {"GOVT_SYNC_TN_HTTP_DIAGNOSTIC_ENABLED": "true"}), \
         patch("modules.govt_sync.browser_session.get_live_session") as mock_get_session:
        mock_get_session.return_value = MagicMock(tenant_id=1, case_id=40, portal=_tn_portal())
        resp = client.post(
            "/api/cases/40/govt/session/some-session/tamil-nadu/diagnostic/http-replay-proof",
            headers=_auth_headers(),
        )
    assert resp.status_code == 403


def test_endpoint_runs_diagnostic_when_enabled_and_in_scope(monkeypatch):
    _seed_database()
    fake_report = TnDiagnosticReport(
        playwright_result={"state": "STATUS_CHECKED", "normalized_status": "resolved"},
        network_evidence=[{"method": "GET", "url": "https://cmhelpline.tnega.org/portal/ta/ticket/18968314",
                            "resource_type": "document", "status": 200, "content_type": "text/html", "response_bytes": 10}],
        non_document_request_count=0,
        discovered_ticket_record_id="18968314",
        http_replay_result="REPLAY_SUCCESS",
        outcome=OUTCOME_HTTP_SUCCESS,
    )
    with patch.dict(os.environ, {"GOVT_SYNC_TN_HTTP_DIAGNOSTIC_ENABLED": "true"}), \
         patch("modules.govt_sync.browser_session.get_live_session") as mock_get_session, \
         patch("modules.govt_sync.status.tn_network_diagnostic.capture_tn_diagnostic", new_callable=AsyncMock) as mock_capture:
        mock_get_session.return_value = MagicMock(tenant_id=1, case_id=40, portal=_tn_portal())
        mock_capture.return_value = fake_report
        resp = client.post(
            "/api/cases/40/govt/session/some-session/tamil-nadu/diagnostic/http-replay-proof",
            headers=_auth_headers(),
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["outcome"] == OUTCOME_HTTP_SUCCESS
    assert body["discovered_ticket_record_id"] == "18968314"
    mock_capture.assert_awaited_once()

    # No real browser/network activity of any kind occurred — capture_tn_diagnostic
    # itself was mocked out entirely for this endpoint-level test.
    with test_engine.connect() as conn:
        rows = list(conn.execute(
            text("SELECT action, payload FROM govt_submission_log WHERE case_id = 40 ORDER BY id")
        ))
    assert len(rows) == 1
    assert rows[0][0] == "TN_HTTP_DIAGNOSTIC_RUN"
