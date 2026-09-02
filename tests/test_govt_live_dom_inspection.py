import os
import sys
from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient


TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"

os.environ["JWT_SECRET"] = TEST_JWT_SECRET
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_govt_live_dom_inspection.db")
os.environ.setdefault("ENV", "test")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-testing")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import api_router
import main
from modules.govt_sync import browser_session
from modules.govt_sync.browser_session import LiveSession


client = TestClient(main.app, raise_server_exceptions=False)


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _auth_headers(username: str = "mp_tn") -> dict[str, str]:
    token = jwt.encode(
        {"sub": username, "exp": _utcnow() + timedelta(hours=8), "iat": _utcnow().timestamp()},
        TEST_JWT_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


class FakeLocator:
    def __init__(self, page, selector, nodes):
        self.page = page
        self.selector = selector
        self.nodes = list(nodes)

    async def count(self):
        return len(self.nodes)

    def nth(self, idx):
        return FakeLocator(self.page, self.selector, self.nodes[idx:idx + 1])

    async def inner_text(self, timeout=0):
        if self.selector == "body":
            return self.page.body_text
        if not self.nodes:
            return ""
        return self.nodes[0].get("text", "")

    async def get_attribute(self, name, timeout=0):
        if not self.nodes:
            return None
        return self.nodes[0].get("attrs", {}).get(name)


class FakePage:
    def __init__(self, *, body_text=None, html=None, nodes=None, frames=None):
        self.url = "https://cmhelpline.tnega.org/portal/ta/myarea"
        self._title = "My Petitions"
        self.body_text = body_text or "OTP: 123456 password: hunter2 token: abc123 TN/FOODCO/CBE/P/PORTAL/01SEP26/18968314 Pending Action"
        self.html = html or (
            "<html><body><input name='otp' value='123456'>"
            "<input type='password' value='hunter2'>"
            "<a href='/ticket/18968314' data-token='abc123'>TN/FOODCO/CBE/P/PORTAL/01SEP26/18968314 Pending Action</a>"
            "</body></html>"
        )
        self.nodes = nodes or {
            "input": [{"text": "", "attrs": {"name": "otp", "type": "text", "value": "123456"}}],
            "a": [{"text": "TN/FOODCO/CBE/P/PORTAL/01SEP26/18968314 Pending Action", "attrs": {"href": "/ticket/18968314", "data-token": "abc123"}}],
            "button": [{"text": "View", "attrs": {"aria-label": "View petition"}}],
            "div": [{"text": "Status: Pending Action", "attrs": {"class": "ticket-card"}}],
        }
        self.frames = frames or []
        self.clicks = 0
        self.keys = 0
        self.gotos = 0
        self.evaluations = 0

    async def title(self):
        return self._title

    async def content(self):
        return self.html

    def locator(self, selector):
        return FakeLocator(self, selector, self.nodes.get(selector, []))

    async def goto(self, *_a, **_k):
        self.gotos += 1
        raise AssertionError("DOM inspection must not navigate")

    async def click(self, *_a, **_k):
        self.clicks += 1
        raise AssertionError("DOM inspection must not click")

    async def evaluate(self, *_a, **_k):
        self.evaluations += 1
        raise AssertionError("DOM inspection must not evaluate caller JS")


def _session(session_id="sess-tn", tenant_id=12, case_id=44, page=None):
    return LiveSession(
        session_id=session_id,
        tenant_id=tenant_id,
        case_id=case_id,
        portal={"portal_name": "Tamil Nadu CM Helpline (Mudhalvarin Mugavari)"},
        context=object(),
        page=page or FakePage(),
        cdp=object(),
    )


def _override_user(tenant_id=12):
    main.app.dependency_overrides[api_router.get_current_user] = lambda: {
        "username": "mp_tn",
        "tenant_id": tenant_id,
        "role": "mp",
    }


def teardown_function(_fn):
    main.app.dependency_overrides.clear()
    browser_session._sessions.clear()


def test_endpoint_disabled_by_default(monkeypatch):
    _override_user()
    browser_session._sessions["sess-tn"] = _session()
    monkeypatch.delenv("GOVT_SYNC_DEV_DOM_INSPECTION", raising=False)
    monkeypatch.setenv("ENV", "test")

    resp = client.get("/api/dev/govt/session/sess-tn/dom", headers=_auth_headers())

    assert resp.status_code == 404


def test_endpoint_unavailable_when_dev_flag_false(monkeypatch):
    _override_user()
    browser_session._sessions["sess-tn"] = _session()
    monkeypatch.setenv("GOVT_SYNC_DEV_DOM_INSPECTION", "false")
    monkeypatch.setenv("ENV", "development")

    resp = client.get("/api/dev/govt/session/sess-tn/dom", headers=_auth_headers())

    assert resp.status_code == 404


def test_valid_owned_session_can_be_inspected(monkeypatch):
    _override_user()
    browser_session._sessions["sess-tn"] = _session()
    monkeypatch.setenv("GOVT_SYNC_DEV_DOM_INSPECTION", "true")
    monkeypatch.setenv("ENV", "development")

    resp = client.get("/api/dev/govt/session/sess-tn/dom", headers=_auth_headers())

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["success"] is True
    assert payload["session_id"] == "sess-tn"
    assert payload["case_id"] == 44
    assert payload["title"] == "My Petitions"
    assert payload["url"].startswith("https://cmhelpline.tnega.org")
    assert payload["elements"]


def test_nonexistent_session_rejected(monkeypatch):
    _override_user()
    monkeypatch.setenv("GOVT_SYNC_DEV_DOM_INSPECTION", "true")
    monkeypatch.setenv("ENV", "development")

    resp = client.get("/api/dev/govt/session/missing/dom", headers=_auth_headers())

    assert resp.status_code == 404


def test_cross_tenant_session_rejected(monkeypatch):
    _override_user(tenant_id=12)
    browser_session._sessions["sess-other"] = _session(session_id="sess-other", tenant_id=99)
    monkeypatch.setenv("GOVT_SYNC_DEV_DOM_INSPECTION", "true")
    monkeypatch.setenv("ENV", "development")

    resp = client.get("/api/dev/govt/session/sess-other/dom", headers=_auth_headers())

    assert resp.status_code == 404


def test_expired_session_rejected(monkeypatch):
    _override_user()
    stale = _session()
    stale.last_activity_at = 0
    browser_session._sessions["sess-tn"] = stale
    monkeypatch.setenv("GOVT_SYNC_DEV_DOM_INSPECTION", "true")
    monkeypatch.setenv("ENV", "development")

    resp = client.get("/api/dev/govt/session/sess-tn/dom", headers=_auth_headers())

    assert resp.status_code == 404


def test_non_government_session_rejected(monkeypatch):
    _override_user()
    nongov = _session()
    nongov.portal = {}
    browser_session._sessions["sess-tn"] = nongov
    monkeypatch.setenv("GOVT_SYNC_DEV_DOM_INSPECTION", "true")
    monkeypatch.setenv("ENV", "development")

    resp = client.get("/api/dev/govt/session/sess-tn/dom", headers=_auth_headers())

    assert resp.status_code == 400


def test_inspection_contains_no_input_values(monkeypatch):
    _override_user()
    browser_session._sessions["sess-tn"] = _session()
    monkeypatch.setenv("GOVT_SYNC_DEV_DOM_INSPECTION", "true")
    monkeypatch.setenv("ENV", "development")

    text = client.get("/api/dev/govt/session/sess-tn/dom", headers=_auth_headers()).text

    assert "123456" not in text
    assert "hunter2" not in text
    assert '"value"' not in text


def test_inspection_contains_no_cookies_tokens_or_auth_headers(monkeypatch):
    _override_user()
    browser_session._sessions["sess-tn"] = _session()
    monkeypatch.setenv("GOVT_SYNC_DEV_DOM_INSPECTION", "true")
    monkeypatch.setenv("ENV", "development")

    text = client.get("/api/dev/govt/session/sess-tn/dom", headers=_auth_headers()).text.lower()

    assert "abc123" not in text
    assert "cookie" not in text
    assert "authorization" not in text
    assert "bearer" not in text
    assert "data-token" not in text


def test_output_is_bounded_and_truncated(monkeypatch):
    _override_user()
    page = FakePage(body_text="Status " + ("x" * 20_000), html="<div>" + ("y" * 40_000) + "</div>")
    browser_session._sessions["sess-tn"] = _session(page=page)
    monkeypatch.setenv("GOVT_SYNC_DEV_DOM_INSPECTION", "true")
    monkeypatch.setenv("ENV", "development")

    payload = client.get("/api/dev/govt/session/sess-tn/dom", headers=_auth_headers()).json()

    assert len(payload["body_text"]) < 13_000
    assert len(payload["html"]) < 31_000
    assert "[truncated" in payload["body_text"]
    assert "[truncated" in payload["html"]


def test_endpoint_cannot_perform_mutation(monkeypatch):
    _override_user()
    page = FakePage()
    browser_session._sessions["sess-tn"] = _session(page=page)
    monkeypatch.setenv("GOVT_SYNC_DEV_DOM_INSPECTION", "true")
    monkeypatch.setenv("ENV", "development")

    resp = client.get("/api/dev/govt/session/sess-tn/dom", headers=_auth_headers())

    assert resp.status_code == 200
    assert page.clicks == 0
    assert page.keys == 0
    assert page.gotos == 0
    assert page.evaluations == 0


def test_production_configuration_rejects_endpoint(monkeypatch):
    _override_user()
    browser_session._sessions["sess-tn"] = _session()
    monkeypatch.setenv("GOVT_SYNC_DEV_DOM_INSPECTION", "true")
    monkeypatch.setenv("ENV", "production")

    resp = client.get("/api/dev/govt/session/sess-tn/dom", headers=_auth_headers())

    assert resp.status_code == 404


def test_accessible_frame_dom_is_included(monkeypatch):
    _override_user()
    frame = FakePage(
        body_text="Frame petition TN/FOODCO/CBE/P/PORTAL/01SEP26/18968314 Status: Received",
        html="<section>Status: Received</section>",
        nodes={"div": [{"text": "Status: Received", "attrs": {"role": "status"}}]},
    )
    frame.url = "https://cmhelpline.tnega.org/frame"
    frame.name = "petition-frame"
    page = FakePage(frames=[object(), frame])
    browser_session._sessions["sess-tn"] = _session(page=page)
    monkeypatch.setenv("GOVT_SYNC_DEV_DOM_INSPECTION", "true")
    monkeypatch.setenv("ENV", "development")

    payload = client.get("/api/dev/govt/session/sess-tn/dom", headers=_auth_headers()).json()

    assert payload["frames"]
    assert payload["frames"][0]["name"] == "petition-frame"
    assert "Received" in payload["frames"][0]["body_text"]
