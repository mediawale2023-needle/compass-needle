"""
tests/test_tamil_nadu_http_replay_diagnostic.py — Phase 2 controlled-proof
harness for the Tamil Nadu Playwright-to-HTTP migration investigation:
MULTI-TICKET SCOPE + SESSION DURABILITY.

Everything here is mocked: no real Playwright browser, no real HTTP
request, no real government portal. requests.Session itself is patched for
every test that would otherwise make a network call. This file proves the
harness's own mechanics — status-code classification, multi-ticket
discovery/selection, elapsed-time reporting, and credential-safety — never
a live result.
"""
import asyncio
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.govt_sync.status.tn_http_replay_diagnostic import (
    HTTP_REPLAY_AUTH_FAILURE,
    HTTP_REPLAY_AUTHENTICATED,
    HTTP_REPLAY_FORBIDDEN,
    HTTP_REPLAY_INCONCLUSIVE,
    HTTP_REPLAY_NOT_FOUND,
    HTTP_REPLAY_SERVER_ERROR,
    HTTP_REPLAY_TRANSPORT_FAILURE,
    TicketHttpReplayAttempt,
    _classify_http_status,
    _perform_ticket_http_replay,
    capture_tn_http_replay_diagnostic,
    replay_previously_observed_ticket,
)
from modules.govt_sync.status.tn_network_diagnostic import (
    _NetworkEvidenceEntry,
    _redact_url,
    discover_all_ticket_record_ids,
)

_HOST = "cmhelpline.tnega.org"
_PRIMARY_ID = "35665012402750744"


def _entry(url, resource_type="xhr"):
    return _NetworkEvidenceEntry(method="GET", url=url, resource_type=resource_type)


def _fake_response(status_code, content_type="application/json", content=b'{"ok":true}'):
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = {"Content-Type": content_type}
    resp.content = content
    return resp


# ─── 1-7: HTTP status classification ────────────────────────────────────────

def test_classify_http_status_200_is_authenticated():
    assert _classify_http_status(200) == HTTP_REPLAY_AUTHENTICATED


def test_classify_http_status_401_is_auth_failure():
    assert _classify_http_status(401) == HTTP_REPLAY_AUTH_FAILURE


def test_classify_http_status_403_is_forbidden():
    assert _classify_http_status(403) == HTTP_REPLAY_FORBIDDEN


def test_classify_http_status_404_is_not_found():
    assert _classify_http_status(404) == HTTP_REPLAY_NOT_FOUND


def test_classify_http_status_5xx_is_server_error():
    assert _classify_http_status(500) == HTTP_REPLAY_SERVER_ERROR
    assert _classify_http_status(502) == HTTP_REPLAY_SERVER_ERROR
    assert _classify_http_status(503) == HTTP_REPLAY_SERVER_ERROR


def test_classify_http_status_unexpected_is_inconclusive():
    for code in (301, 418, 429, 204):
        assert _classify_http_status(code) == HTTP_REPLAY_INCONCLUSIVE, code


@patch("requests.Session")
def test_perform_ticket_http_replay_transport_exception_is_transport_failure(mock_session_cls):
    mock_session_cls.return_value.get.side_effect = ConnectionError("boom")
    attempt = _perform_ticket_http_replay(MagicMock(), f"https://{_HOST}", _PRIMARY_ID)
    assert attempt.outcome == HTTP_REPLAY_TRANSPORT_FAILURE
    assert attempt.content_type is None
    assert attempt.response_bytes is None


@patch("requests.Session")
def test_perform_ticket_http_replay_200_is_authenticated_end_to_end(mock_session_cls):
    mock_session_cls.return_value.get.return_value = _fake_response(200)
    attempt = _perform_ticket_http_replay(MagicMock(), f"https://{_HOST}", _PRIMARY_ID)
    assert attempt.outcome == HTTP_REPLAY_AUTHENTICATED
    safe = attempt.to_safe_dict()
    assert safe["authenticated"] is True
    assert safe["ticket_response_successful"] is True
    assert safe["content_type"] == "application/json"
    assert safe["response_bytes"] == len(b'{"ok":true}')


# ─── 8-10: multi-ticket scope discovery/selection ───────────────────────────

def test_multiple_observed_ticket_ids_are_all_discovered():
    evidence = [
        _entry(f"https://{_HOST}/portal/api/tickets/{_PRIMARY_ID}"),
        _entry(f"https://{_HOST}/portal/api/tickets/{_PRIMARY_ID}/conversations"),
        _entry(f"https://{_HOST}/portal/api/tickets/999888777"),
    ]
    ids = discover_all_ticket_record_ids(evidence, expected_host=_HOST)
    assert ids == [_PRIMARY_ID, "999888777"]


@patch("requests.Session")
def test_second_observed_ticket_is_selected_and_replayed_without_guessing(mock_session_cls):
    mock_session_cls.return_value.get.return_value = _fake_response(200)
    evidence = [
        _entry(f"https://{_HOST}/portal/api/tickets/{_PRIMARY_ID}"),
        _entry(f"https://{_HOST}/portal/api/tickets/999888777"),
    ]
    session = _fake_session()

    report = asyncio.run(capture_tn_http_replay_diagnostic(
        session, evidence, primary_record_id=_PRIMARY_ID,
    ))

    assert report.multiple_tickets_observed is True
    assert report.observed_ticket_record_id_count == 2
    assert report.primary_attempt.record_id == _PRIMARY_ID
    assert report.secondary_attempt is not None
    assert report.secondary_attempt.record_id == "999888777"


def test_unobserved_ticket_ids_are_rejected_never_synthesized():
    # Only ONE id (_PRIMARY_ID) ever actually appears in evidence. Neither
    # of its numeric neighbors, nor any other id, must ever be invented as
    # a "second ticket" candidate.
    evidence = [_entry(f"https://{_HOST}/portal/api/tickets/{_PRIMARY_ID}")]
    ids = discover_all_ticket_record_ids(evidence, expected_host=_HOST)
    assert ids == [_PRIMARY_ID]
    neighbor_low = str(int(_PRIMARY_ID) - 1)
    neighbor_high = str(int(_PRIMARY_ID) + 1)
    assert neighbor_low not in ids
    assert neighbor_high not in ids


@patch("requests.Session")
def test_no_secondary_attempt_when_only_one_ticket_observed(mock_session_cls):
    mock_session_cls.return_value.get.return_value = _fake_response(200)
    evidence = [_entry(f"https://{_HOST}/portal/api/tickets/{_PRIMARY_ID}")]
    session = _fake_session()

    report = asyncio.run(capture_tn_http_replay_diagnostic(
        session, evidence, primary_record_id=_PRIMARY_ID,
    ))

    assert report.multiple_tickets_observed is False
    assert report.observed_ticket_record_id_count == 1
    assert report.secondary_attempt is None


# ─── Session durability ─────────────────────────────────────────────────────

class _FakeContext:
    def __init__(self, cookies):
        self._cookies = cookies

    async def cookies(self):
        return list(self._cookies)


class _FakeSession:
    def __init__(self, context, portal, created_at):
        self.context = context
        self.portal = portal
        self.created_at = created_at


def _fake_session(created_at=500.0):
    cookies = [{"name": "zoho_session", "value": "opaque-test-value", "domain": _HOST, "path": "/"}]
    return _FakeSession(context=_FakeContext(cookies), portal={"base_url": f"https://{_HOST}"}, created_at=created_at)


@patch("requests.Session")
def test_first_replay_has_no_elapsed_time_and_reports_session_established_at(mock_session_cls):
    mock_session_cls.return_value.get.return_value = _fake_response(200)
    session = _fake_session(created_at=500.0)

    report = asyncio.run(replay_previously_observed_ticket(session, _PRIMARY_ID))

    assert report.elapsed_seconds_since_previous_attempt is None
    assert report.session_established_at == 500.0
    assert report.primary_attempt.outcome == HTTP_REPLAY_AUTHENTICATED


@patch("requests.Session")
def test_second_replay_reports_elapsed_time_since_previous_attempt(mock_session_cls):
    mock_session_cls.return_value.get.return_value = _fake_response(200)
    session = _fake_session()

    first = asyncio.run(replay_previously_observed_ticket(session, _PRIMARY_ID))
    second = asyncio.run(replay_previously_observed_ticket(
        session, _PRIMARY_ID, previous_attempt_at=first.this_attempt_at - 42.0,
    ))

    assert second.elapsed_seconds_since_previous_attempt >= 42.0


@patch("requests.Session")
def test_replay_uses_same_cookie_export_path_each_call_no_caching(mock_session_cls):
    """No cookie jar is cached/reused across calls — each call re-exports
    fresh from the still-open LiveSession.context, per the no-artificial-
    keep-alive requirement."""
    mock_session_cls.return_value.get.return_value = _fake_response(200)
    session = _fake_session()
    session.context.cookies = MagicMock(wraps=session.context.cookies)

    asyncio.run(replay_previously_observed_ticket(session, _PRIMARY_ID))
    asyncio.run(replay_previously_observed_ticket(session, _PRIMARY_ID))

    assert session.context.cookies.call_count == 2


# ─── 11-12: credential safety / redaction guarantees ────────────────────────

def test_no_credential_values_appear_in_diagnostic_output():
    attempt = TicketHttpReplayAttempt(
        record_id=_PRIMARY_ID, outcome=HTTP_REPLAY_AUTHENTICATED,
        content_type="application/json", response_bytes=11356, attempted_at=1000.0,
    )
    dumped = str(attempt.to_safe_dict())
    for forbidden in ("Cookie", "Set-Cookie", "Authorization", "csrf", "CSRF", "JWT", "session_id=", "zoho_session"):
        assert forbidden not in dumped


@patch("requests.Session")
def test_full_report_never_exposes_cookie_or_session_material(mock_session_cls):
    mock_session_cls.return_value.get.return_value = _fake_response(200)
    session = _fake_session()

    report = asyncio.run(replay_previously_observed_ticket(session, _PRIMARY_ID))
    dumped = str(report.to_safe_dict())
    for forbidden in ("Cookie", "Set-Cookie", "Authorization", "opaque-test-value", "zoho_session"):
        assert forbidden not in dumped


def test_existing_redaction_remains_intact_for_multi_ticket_discovery():
    # discover_all_ticket_record_ids must work purely off already-redacted
    # URLs (query values stripped) — a query-string secret must never
    # resurface via this new discovery path either.
    raw = f"https://{_HOST}/portal/api/tickets/{_PRIMARY_ID}?authToken=SUPERSECRETVALUE123"
    redacted = _redact_url(raw)
    assert "SUPERSECRETVALUE123" not in redacted
    ids = discover_all_ticket_record_ids([_entry(redacted)], expected_host=_HOST)
    assert ids == [_PRIMARY_ID]
