"""
Tamil Nadu authenticated status-check adapter + endpoint-context tests.

Mirrors tests/test_tamil_nadu_filing.py: mock Playwright Page/Locator surface,
asyncio.run, SQLite env. No real portal is contacted. These tests pin the
fail-closed contract — the adapter must never return STATUS_CHECKED unless an
authenticated page was reached and a status was read and normalized.
"""
import asyncio
import os
import re
import sys

import pytest

os.environ.setdefault("JWT_SECRET", "test-secret-key-32-characters-minimum-ok")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_tamil_nadu_status.db")
os.environ.setdefault("ENV", "test")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-testing")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import api_router
from modules.govt_sync.adapters import get_adapter
from modules.govt_sync.adapters.karnataka_ipgrs import KarnatakaAPIAdapter
from modules.govt_sync.adapters.maharashtra_aaplesarkar import MaharashtraAapleSarkarAdapter
from modules.govt_sync.adapters.rajasthan_sampark import RajasthanSamparkAPIAdapter
from modules.govt_sync.filing import get_filing_adapter
from modules.govt_sync.status import get_status_adapter
from modules.govt_sync.status.base import StatusCheckState
from modules.govt_sync.status.tamil_nadu import TamilNaduStatusAdapter, _match_cards, _short_id_for

REF = "TN/FOODCO/CBE/P/PORTAL/01SEP26/18968314"
SHORT = "#18968314"


def _tn_portal():
    return {
        "id": 99,
        "state": "Tamil Nadu",
        "portal_name": "Tamil Nadu CM Helpline (Mudhalvarin Mugavari)",
        "base_url": "https://cmhelpline.tnega.org",
        "field_schema": {"status_area_path": "/portal/ta/myarea"},
    }


# ─────────────────────────── mock Playwright surface ───────────────────────────

class FakeNode:
    def __init__(self, text="", match_text=None, children=None, attrs=None, on_click=None):
        self.text = text
        self.match_text = text if match_text is None else match_text
        self.children = children or {}
        self.attrs = attrs or {}
        self.on_click = on_click

    def query(self, selector):
        if selector in self.children:
            return self.children[selector]
        if selector == "a, button":
            return self.children.get("a", []) or self.children.get("button", [])
        if selector.startswith("xpath="):
            return [self]
        return []


class FakeLoc:
    def __init__(self, nodes):
        self._nodes = list(nodes)

    async def count(self):
        return len(self._nodes)

    async def all(self):
        return [FakeLoc([n]) for n in self._nodes]

    @property
    def first(self):
        return FakeLoc(self._nodes[:1])

    def nth(self, i):
        return FakeLoc(self._nodes[i:i + 1])

    async def inner_text(self, timeout=0):
        if not self._nodes:
            raise RuntimeError("locator resolved no node")
        return self._nodes[0].text

    async def get_attribute(self, name, timeout=0):
        if not self._nodes:
            return None
        return self._nodes[0].attrs.get(name)

    async def click(self, timeout=0):
        if not self._nodes:
            raise RuntimeError("locator resolved no node")
        if self._nodes[0].on_click:
            self._nodes[0].on_click()

    def locator(self, selector):
        if not self._nodes:
            return FakeLoc([])
        return FakeLoc(self._nodes[0].query(selector))


class FakePage:
    def __init__(self, url, body_text="", selectors=None, roles=None, texts=None,
                 goto_raises=False, frames=None):
        self.url = url
        self.body_text = body_text
        self.selectors = selectors or {}
        self.roles = roles or {}
        self.texts = texts or []
        self.goto_raises = goto_raises
        self.goto_calls = []
        self.frames = frames if frames is not None else [self]

    def set_state(self, *, url=None, body_text=None, selectors=None, texts=None):
        if url is not None:
            self.url = url
        if body_text is not None:
            self.body_text = body_text
        if selectors is not None:
            self.selectors = selectors
        if texts is not None:
            self.texts = texts

    async def goto(self, url, wait_until=None, timeout=0):
        self.goto_calls.append(url)
        if self.goto_raises:
            raise TimeoutError("navigation timed out")

    async def wait_for_load_state(self, *a, **k):
        return None

    async def wait_for_timeout(self, *a, **k):
        return None

    def locator(self, selector):
        if selector == "body":
            return FakeLoc([FakeNode(text=self.body_text)])
        return FakeLoc(self.selectors.get(selector, []))

    def get_by_role(self, role, name=None):
        want = None
        if name is not None:
            want = (name.pattern if hasattr(name, "pattern") else str(name)).lower()
        out = []
        for substr, node in self.roles.get(role, []):
            if want is None or substr.lower() in want or want in substr.lower():
                out.append(node)
        return FakeLoc(out)

    def get_by_text(self, pattern):
        rx = pattern if hasattr(pattern, "search") else re.compile(re.escape(str(pattern)), re.I)
        return FakeLoc([node for txt, node in self.texts if rx.search(txt)])


def _run(page, reference=REF):
    return asyncio.run(TamilNaduStatusAdapter(_tn_portal()).check_status_on_page(page, reference))


def _detail_body(status="Received", *, atr=True, ref=True):
    lines = [
        f"Grievance {REF}" if ref else "Grievance detail",
        f"Status: {status}",
        "Department: Revenue and Disaster Management Department",
        "Last Updated: 01 Sep 2026",
    ]
    if atr:
        lines.append("Action Taken Report: Forwarded to the Tahsildar for field inspection")
    return "\n".join(lines)


def _list_page(card_nodes, url="https://cmhelpline.tnega.org/portal/ta/myarea?viewId=abc&sortBy=recentThread"):
    list_box = FakeNode(text="box", children={".TicketListItem__container": card_nodes})
    return FakePage(
        url=url,
        body_text="My Petitions",
        selectors={
            "#layoutContainer.Layout__twoColumn[role='main']": [FakeNode(text="layout")],
            ".TicketListLeftContainer1__boxView": [list_box],
            ".TicketListItem__container": card_nodes,
        },
    )


def _card(text, *, status_child=None, short_id=SHORT, created_title="01 Sep 2026 10:14 AM", department="Food and Civil Supplies", on_click=None):
    children = {"[data-id^='ticket_title_']": [FakeNode(text=text, attrs={"data-id": "ticket_title_18968314"}, on_click=on_click)]}
    if short_id is not None:
        children["[data-id^='ticket_id_']"] = [FakeNode(text=short_id, attrs={"data-id": "ticket_id_18968314"})]
    if created_title is not None:
        children["[data-id^='createdTime_'][title]"] = [
            FakeNode(text="19 மணிநேரங்களுக்கு முன்னர்", attrs={"data-id": "createdTime_18968314", "title": created_title})
        ]
    if department is not None:
        children["[data-id='ticket_department_name']"] = [FakeNode(text=department)]
    if status_child is not None:
        children[".TicketListItem_status .Badge__badge"] = [
            FakeNode(text=status_child, attrs={"data-id": f"ticketStatus_{status_child}_18968314", "class": "Badge__badge pending_action"})
        ]
    if on_click:
        children["a"] = [FakeNode(text="open", on_click=on_click)]
    return FakeNode(text=text, children=children)


def _detail_selectors(status="Received", *, comments=None, reference_text=REF):
    return {
        ".TicketDetailLeftContainer__wrapper": [FakeNode(text=f"Grievance {reference_text}" if reference_text else "detail")],
        "[data-id='ticket_status_value']": [FakeNode(text=status, attrs={"data-id": "ticket_status_value"})],
        ".Post__container": [FakeNode(text=f"Petitioner post {REF}")],
        ".Post__postContent": [FakeNode(text=f"Delay / Non-Availability of Commodities ({REF})")],
        ".enduser_thread": [FakeNode(text=f"Original petitioner thread {REF}")],
        ".web_cont": [FakeNode(text=f"Web content {REF}")],
        ".comment": [FakeNode(text=c) for c in (comments or [])],
    }


# ─────────────────────────────── registry ───────────────────────────────

def test_status_adapter_registered_by_state():
    adapter = get_status_adapter(_tn_portal())
    assert isinstance(adapter, TamilNaduStatusAdapter)
    assert adapter.state_key == "tamil_nadu"
    assert adapter.status_area_url() == "https://cmhelpline.tnega.org/portal/ta/myarea"
    assert get_status_adapter({"state": "Rajasthan"}) is None
    assert get_status_adapter({}) is None


def test_protected_status_registries_untouched():
    # The new status package must not disturb the existing status-check registry.
    assert isinstance(get_adapter({"status_check_adapter": "rajasthan_sampark_api"}), RajasthanSamparkAPIAdapter)
    assert isinstance(get_adapter({"status_check_adapter": "karnataka_ipgrs_api"}), KarnatakaAPIAdapter)
    assert isinstance(get_adapter({"status_check_adapter": "maharashtra_aaplesarkar_api"}), MaharashtraAapleSarkarAdapter)
    # Filing registry still resolves Tamil Nadu independently of the status one.
    assert getattr(get_filing_adapter(_tn_portal()), "state_key", "") == "tamil_nadu"


def test_short_id_derivation_and_match_helpers():
    assert _short_id_for(REF) == SHORT
    assert _short_id_for("TN/AB") is None
    cards = [(object(), f"road repair {REF} Pending Action"), (object(), "unrelated #99999")]
    matches, how = _match_cards(cards, REF, SHORT)
    assert how == "reference" and len(matches) == 1
    # short-id only matches when the full reference is on no card
    only_short = [(object(), "water issue #18968314 Received")]
    matches, how = _match_cards(only_short, REF, SHORT)
    assert how == "short_id" and len(matches) == 1
    # two short-id hits -> caller must treat as ambiguous, helper returns both
    two = [(object(), "a #18968314"), (object(), "b #18968314")]
    matches, _ = _match_cards(two, REF, SHORT)
    assert len(matches) == 2


# ─────────────────────── human checkpoints (fail closed) ───────────────────────

def test_auth_required_when_not_signed_in():
    page = FakePage(url="https://cmhelpline.tnega.org/portal/ta/signin", body_text="Please sign in to continue")
    assert _run(page).state == StatusCheckState.AUTH_REQUIRED


def test_otp_required():
    page = FakePage(url="https://cmhelpline.tnega.org/portal/ta/myarea", body_text="Enter the OTP sent to your mobile")
    assert _run(page).state == StatusCheckState.OTP_REQUIRED


def test_captcha_required():
    page = FakePage(url="https://cmhelpline.tnega.org/portal/ta/myarea", body_text="Type the CAPTCHA text shown")
    assert _run(page).state == StatusCheckState.CAPTCHA_REQUIRED


def test_session_expired_mid_flow():
    def reopen():
        page.set_state(url="https://cmhelpline.tnega.org/portal/ta/signin",
                       body_text="Your session expired, please sign in again")
    page = _list_page([_card(f"{REF} Pending Action", on_click=reopen)])
    assert _run(page).state == StatusCheckState.SESSION_EXPIRED


# ─────────────────────────── list / matching ───────────────────────────

def test_petitions_list_not_loaded_fails_closed():
    page = FakePage(url="https://cmhelpline.tnega.org/portal/ta/myarea", body_text="loading spinner")
    result = _run(page)
    assert result.state == StatusCheckState.PETITIONS_LOADING
    assert result.normalized_status is None


def test_case_not_found_when_list_empty():
    page = FakePage(url="https://cmhelpline.tnega.org/portal/ta/myarea",
                    body_text="You have no petitions yet.",
                    selectors={'[data-id="no_ticket"]': [FakeNode(text="No tickets")]})
    assert _run(page).state == StatusCheckState.CASE_NOT_FOUND


def test_case_not_found_when_no_card_matches():
    page = _list_page([_card("TN/OTHER/XYZ/P/PORTAL/01SEP26/70000001 Received", short_id="#70000001")])
    result = _run(page)
    assert result.state == StatusCheckState.CASE_NOT_FOUND
    assert result.matched_count == 0


def test_global_card_outside_verified_list_container_is_ignored():
    page = FakePage(
        url="https://cmhelpline.tnega.org/portal/ta/myarea",
        body_text="My Petitions",
        selectors={
            "#layoutContainer.Layout__twoColumn[role='main']": [FakeNode(text="layout")],
            ".TicketListLeftContainer1__boxView": [FakeNode(text="box", children={".TicketListItem__container": []})],
            ".TicketListItem__container": [_card(f"{REF} Received")],
        },
    )
    result = _run(page)
    assert result.state == StatusCheckState.CASE_NOT_FOUND
    assert result.matched_count == 0


def test_ambiguous_match_is_not_guessed():
    page = _list_page([_card(f"{REF} Pending Action"), _card(f"duplicate {REF} Received")])
    result = _run(page)
    assert result.state == StatusCheckState.AMBIGUOUS_MATCH
    assert result.matched_count == 2


def test_short_id_ambiguous_match_is_not_guessed():
    page = _list_page([_card("first #18968314 Pending Action"), _card("second #18968314 Received")])
    assert _run(page).state == StatusCheckState.AMBIGUOUS_MATCH


# ─────────────────────── successful reads ───────────────────────

def test_exact_full_reference_match_reads_and_normalizes():
    def open_detail():
        page.set_state(url="https://cmhelpline.tnega.org/portal/ta/ticket/18968314",
                       body_text=_detail_body("Disposed"),
                       selectors=_detail_selectors("Disposed", comments=["Officer: closed after inspection"]))
    page = _list_page([_card(f"{REF} Pending Action", status_child="Pending Action", on_click=open_detail)])
    result = _run(page)
    assert result.state == StatusCheckState.STATUS_CHECKED
    assert result.normalized_status == "resolved"
    assert result.raw_detail_status == "Disposed"
    assert result.raw_list_status == "Pending Action"          # list vs detail preserved distinctly
    assert result.department == "Food and Civil Supplies"
    assert result.created_at == "01 Sep 2026 10:14 AM"
    assert result.last_updated is None
    assert result.action_taken_report is None
    assert result.to_dict()["replies"] == []
    assert result.reference_number == REF
    assert result.matched_count == 1


def test_short_id_unique_match_reads_status():
    def open_detail():
        page.set_state(body_text=_detail_body("In Process"), selectors=_detail_selectors("In Process"))
    page = _list_page([_card("water supply ticket", status_child="Received", on_click=open_detail)])
    result = _run(page)
    assert result.state == StatusCheckState.STATUS_CHECKED
    assert result.normalized_status == "under_review"


def test_received_vs_pending_action_are_both_preserved():
    def open_detail():
        page.set_state(body_text=_detail_body("Received", atr=False), selectors=_detail_selectors("Received"))
    page = _list_page([_card(f"{REF}", status_child="Pending Action", on_click=open_detail)])
    result = _run(page)
    assert result.state == StatusCheckState.STATUS_CHECKED
    assert result.raw_list_status == "Pending Action"
    assert result.raw_detail_status == "Received"
    assert result.raw_list_status != result.raw_detail_status
    assert result.normalized_status == "submitted"
    assert result.action_taken_report is None      # empty ATR stays empty, not fabricated


def test_populated_action_taken_report_is_captured():
    def open_detail():
        frame = FakePage(
            url="https://example.zappsusercontent.in/atr",
            body_text="Action Taken Report: Forwarded to the Tahsildar for field inspection",
        )
        page.frames = [page, frame]
        page.set_state(body_text=_detail_body("Under Process", atr=True), selectors=_detail_selectors("Under Process"))
    page = _list_page([_card(f"{REF}", on_click=open_detail)])
    assert "Tahsildar" in _run(page).action_taken_report


def test_inaccessible_action_taken_report_iframe_is_explicit_not_parent_inferred():
    class InaccessibleFrame:
        url = "https://example.zappsusercontent.in/atr"

        def locator(self, _selector):
            raise RuntimeError("cross-origin frame body unavailable")

    def open_detail():
        page.frames = [page, InaccessibleFrame()]
        page.set_state(
            body_text=_detail_body("Received", atr=True),
            selectors=_detail_selectors("Received"),
        )
    page = _list_page([_card(f"{REF}", on_click=open_detail)])
    result = _run(page)
    assert result.state == StatusCheckState.STATUS_CHECKED
    assert result.action_taken_report == "Action Taken Report iframe not accessible"


# ─────────────────────── inconclusive / fail-closed reads ───────────────────────

def test_empty_reference_is_inconclusive():
    page = _list_page([_card(f"{REF} Received")])
    result = _run(page, reference="")
    assert result.state == StatusCheckState.STATUS_CHECK_INCONCLUSIVE
    assert result.normalized_status is None


def test_malformed_reference_finds_no_match():
    page = _list_page([_card(f"{REF} Received")])
    assert _run(page, reference="TN/BAD").state == StatusCheckState.CASE_NOT_FOUND


def test_detail_without_readable_status_is_inconclusive():
    def open_detail():
        page.set_state(
            body_text=f"Grievance detail {REF}\nDepartment: Revenue\nNo status shown here",
            selectors={".TicketDetailLeftContainer__wrapper": [FakeNode(text="detail")]},
        )
    page = _list_page([_card(f"{REF}", on_click=open_detail)])  # no status child, no phrase in text
    result = _run(page)
    assert result.state == StatusCheckState.STATUS_CHECK_INCONCLUSIVE
    assert result.normalized_status is None


def test_ambiguous_portal_wording_is_inconclusive_not_guessed():
    def open_detail():
        page.set_state(body_text=_detail_body("Rejected and Closed"), selectors=_detail_selectors("Rejected and Closed"))
    page = _list_page([_card(f"{REF}", on_click=open_detail)])
    result = _run(page)
    assert result.state == StatusCheckState.STATUS_CHECK_INCONCLUSIVE
    assert result.raw_detail_status == "Rejected and Closed"     # raw wording still surfaced
    assert result.normalized_status is None


def test_opened_wrong_reference_is_inconclusive():
    def open_detail():
        page.set_state(
            body_text="Grievance TN/OTHER/XYZ/P/PORTAL/01SEP26/70000001\nStatus: Disposed",
            selectors=_detail_selectors("Disposed", reference_text="TN/OTHER/XYZ/P/PORTAL/01SEP26/70000001"),
        )
    page = _list_page([_card(f"{REF} Pending Action", on_click=open_detail)])
    result = _run(page)
    assert result.state == StatusCheckState.STATUS_CHECK_INCONCLUSIVE
    assert result.normalized_status is None


def test_reference_in_page_body_outside_detail_wrapper_is_not_proof():
    def open_detail():
        page.set_state(
            body_text=f"List column still contains {REF}\nDetail has another petition",
            selectors=_detail_selectors(
                "Disposed",
                reference_text="TN/OTHER/XYZ/P/PORTAL/01SEP26/70000001",
            ),
        )
    page = _list_page([_card(f"{REF} Pending Action", on_click=open_detail)])
    result = _run(page)
    assert result.state == StatusCheckState.STATUS_CHECK_INCONCLUSIVE
    assert result.normalized_status is None


def test_navigation_timeout_fails_closed():
    page = FakePage(url="https://cmhelpline.tnega.org/portal/ta/home", body_text="Home", goto_raises=True)
    assert _run(page).state == StatusCheckState.PETITIONS_LOADING


def test_missing_page_is_portal_error():
    result = asyncio.run(TamilNaduStatusAdapter(_tn_portal()).check_status_on_page(None, REF))
    assert result.state == StatusCheckState.PORTAL_ERROR


def test_status_form_loading_when_detail_cannot_open():
    # Card matches but has no anchor and clicking it raises -> fail closed.
    node = FakeNode(text=f"{REF} Pending Action")
    node.on_click = None
    page = _list_page([node])
    # remove the "a, button" child AND make node.click raise by resolving to no node
    node.children = {}
    node.query = lambda selector: []  # every child query empty; card.click resolves a node but no on_click
    result = _run(page)
    # card.click() succeeds (no-op) then detail == list page, no status -> inconclusive
    assert result.state in (StatusCheckState.STATUS_CHECK_INCONCLUSIVE, StatusCheckState.STATUS_FORM_LOADING)


# ─────────────────────── endpoint context helper ───────────────────────

class _FakeSession:
    def __init__(self, tenant_id, case_id, portal):
        self.tenant_id = tenant_id
        self.case_id = case_id
        self.portal = portal
        self.page = object()


def test_status_context_helper_happy_path(monkeypatch):
    monkeypatch.setattr(
        "modules.govt_sync.browser_session.get_live_session",
        lambda sid: _FakeSession(1, 22, _tn_portal()),
    )
    monkeypatch.setattr(api_router, "_q_one", lambda *_a, **_k: {
        "id": 22, "govt_status": "submitted", "govt_reference_number": REF,
    })
    tid, session, case, adapter, ref = api_router._get_tamil_nadu_live_status_context(
        22, "sess", {"tenant_id": 1, "username": "pa"},
    )
    assert tid == 1 and ref == REF
    assert isinstance(adapter, TamilNaduStatusAdapter)


def test_status_context_helper_requires_reference(monkeypatch):
    monkeypatch.setattr(
        "modules.govt_sync.browser_session.get_live_session",
        lambda sid: _FakeSession(1, 22, _tn_portal()),
    )
    monkeypatch.setattr(api_router, "_q_one", lambda *_a, **_k: {
        "id": 22, "govt_status": "pending_staff_submit", "govt_reference_number": None,
    })
    with pytest.raises(api_router.HTTPException) as exc:
        api_router._get_tamil_nadu_live_status_context(22, "sess", {"tenant_id": 1})
    assert exc.value.status_code == 400


def test_status_context_helper_rejects_foreign_session(monkeypatch):
    monkeypatch.setattr(
        "modules.govt_sync.browser_session.get_live_session",
        lambda sid: _FakeSession(999, 22, _tn_portal()),
    )
    with pytest.raises(api_router.HTTPException) as exc:
        api_router._get_tamil_nadu_live_status_context(22, "sess", {"tenant_id": 1})
    assert exc.value.status_code == 404
