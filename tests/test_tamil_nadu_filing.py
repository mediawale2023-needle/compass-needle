import os
import sys

import pytest

os.environ.setdefault("JWT_SECRET", "test-secret-key-32-characters-minimum-ok")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_tamil_nadu_filing.db")
os.environ.setdefault("ENV", "test")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-testing")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import api_router
from modules.govt_sync.adapters import get_adapter
from modules.govt_sync.adapters.karnataka_ipgrs import KarnatakaAPIAdapter
from modules.govt_sync.adapters.maharashtra_aaplesarkar import MaharashtraAapleSarkarAdapter
from modules.govt_sync.adapters.rajasthan_sampark import RajasthanSamparkAPIAdapter
from modules.govt_sync.filing import get_filing_adapter
from modules.govt_sync.filing.base import FilingState, PortalValidationError
from modules.govt_sync.filing.tamil_nadu import (
    TamilNaduFilingAdapter,
    detect_human_checkpoint,
    extract_reference,
    extract_short_id,
    upload_file,
)


def _tn_portal():
    return {
        "id": 99,
        "state": "Tamil Nadu",
        "portal_name": "Tamil Nadu CM Helpline (Mudhalvarin Mugavari)",
        "base_url": "https://cmhelpline.tnega.org",
    }


def test_tamil_nadu_filing_adapter_registered_by_state():
    adapter = get_filing_adapter(_tn_portal())
    assert isinstance(adapter, TamilNaduFilingAdapter)
    assert adapter.portal_urls()["signin"] == "https://cmhelpline.tnega.org/portal/ta/signin"
    assert adapter.portal_urls()["form"] == "https://cmhelpline.tnega.org/portal/ta/newticket"


def test_existing_status_adapter_registry_still_dispatches_protected_states():
    assert isinstance(get_adapter({"status_check_adapter": "rajasthan_sampark_api"}), RajasthanSamparkAPIAdapter)
    assert isinstance(get_adapter({"status_check_adapter": "karnataka_ipgrs_api"}), KarnatakaAPIAdapter)
    assert isinstance(get_adapter({"status_check_adapter": "maharashtra_aaplesarkar_api"}), MaharashtraAapleSarkarAdapter)


def test_required_fields_include_taluk_revenue_division_dependency_chain():
    adapter = TamilNaduFilingAdapter(_tn_portal())
    values = adapter.build_field_values(
        {
            "department": "Co-operation Food and Consumer Protection Department",
            "district": "Coimbatore",
            "subject": "Ration commodity delay",
            "description": "Ration commodities have not been made available.",
        },
        {
            "address": "Test address",
            "gender": "Male",
            "differently_abled": "No",
            "petition_scope": "Public",
            "grievance_type": "Commodities Issues",
            "grievance_subtype": "Delay-Non-Availability of Commodities",
            "responsible_officer": "Pollachi",
        },
    )

    try:
        adapter.validate_required_inputs(values)
    except PortalValidationError as exc:
        assert "revenue_division" in exc.missing_fields
    else:
        raise AssertionError("Expected missing revenue_division to block filing")

    values["taluk"] = "Anaimalai"
    values["revenue_division"] = "Pollachi (91)"
    adapter.validate_required_inputs(values)


def test_reference_and_short_id_extraction():
    text = "Your grievance TN/FOODCO/CBE/P/PORTAL/01SEP26/18968314 has been created. #18968314"
    assert extract_reference(text) == "TN/FOODCO/CBE/P/PORTAL/01SEP26/18968314"
    assert extract_short_id(text) == "#18968314"
    assert extract_reference("TN/BAD") is None
    assert extract_short_id("ticket created without short id") is None


def test_human_checkpoint_detection_is_explicit():
    assert detect_human_checkpoint("/portal/ta/signin", "").kind == "auth"
    assert detect_human_checkpoint("/portal/ta/newticket", "Enter OTP").kind == "otp"
    assert detect_human_checkpoint("/portal/ta/newticket", "Captcha text").kind == "captcha"
    assert detect_human_checkpoint("/portal/ta/newticket", "Submit A Grievance") is None


def test_inspect_state_reports_auth_before_form_for_mock_page():
    class Locator:
        async def inner_text(self, timeout=0):
            return "Sign in to continue"

    class Page:
        url = "https://cmhelpline.tnega.org/portal/ta/signin"

        def locator(self, _selector):
            return Locator()

    adapter = TamilNaduFilingAdapter(_tn_portal())

    import asyncio

    result = asyncio.run(adapter.inspect_state(Page()))
    assert result.state == FilingState.AUTH_REQUIRED


def test_materialize_case_media_writes_selected_attachments_and_cleanup(monkeypatch):
    def fake_q(_sql, _params):
        return [
            {"id": 7, "media_data": b"pdf-bytes", "mime_type": "application/pdf", "file_name": "ration.pdf"},
            {"id": 8, "media_data": b"jpg-bytes", "mime_type": "image/jpeg", "file_name": "shop.jpg"},
        ]

    monkeypatch.setattr(api_router, "_q", fake_q)
    paths, metas = api_router._materialize_tn_case_media_attachments(1, 22, [7, 8, 8])
    try:
        assert len(paths) == 2
        assert [m["media_id"] for m in metas] == [7, 8]
        assert [m["file_name"] for m in metas] == ["ration.pdf", "shop.jpg"]
        assert all(os.path.exists(path) for path in paths)
        with open(paths[0], "rb") as fh:
            assert fh.read() == b"pdf-bytes"
    finally:
        api_router._cleanup_materialized_attachments(paths)
    assert all(not os.path.exists(path) for path in paths)


def test_materialize_case_media_fails_if_selected_attachment_not_on_case(monkeypatch):
    monkeypatch.setattr(api_router, "_q", lambda _sql, _params: [])
    with pytest.raises(api_router.HTTPException) as exc:
        api_router._materialize_tn_case_media_attachments(1, 22, [999])
    assert exc.value.status_code == 404


def test_prepare_to_submit_does_not_click_submit_when_ready(monkeypatch):
    calls = []
    adapter = TamilNaduFilingAdapter(_tn_portal())

    class Page:
        url = "https://cmhelpline.tnega.org/portal/ta/newticket"
        frames = []

        def locator(self, selector):
            class Locator:
                async def inner_text(self, timeout=0):
                    return "Submit A Grievance"

                async def all_inner_texts(self, timeout=0):
                    return []

            return Locator()

        async def wait_for_load_state(self, *args, **kwargs):
            return None

        async def wait_for_timeout(self, *args, **kwargs):
            return None

        def get_by_role(self, *args, **kwargs):
            calls.append("get_by_role")
            return object()

    async def noop(*args, **kwargs):
        return None

    monkeypatch.setattr("modules.govt_sync.filing.tamil_nadu.fill_text_field", noop)
    monkeypatch.setattr("modules.govt_sync.filing.tamil_nadu.select_dropdown", noop)
    monkeypatch.setattr("modules.govt_sync.filing.tamil_nadu.fill_rich_text", noop)

    import asyncio

    fields = {
        "address": "Test address",
        "gender": "Male",
        "differently_abled": "No",
        "petition_scope": "Public",
        "department": "Co-operation Food and Consumer Protection Department",
        "grievance_type": "Commodities Issues",
        "grievance_subtype": "Delay-Non-Availability of Commodities",
        "district": "Coimbatore",
        "taluk": "Anaimalai",
        "revenue_division": "Pollachi (91)",
        "responsible_officer": "Pollachi",
        "subject": "Ration commodity delay",
        "description": "Ration commodities have not been made available.",
    }
    result = asyncio.run(adapter.prepare_to_submit(Page(), {}, fields, []))
    assert result.state == FilingState.READY_TO_SUBMIT
    assert calls == []


def test_upload_file_reports_success_only_after_visible_file_name(tmp_path):
    path = tmp_path / "proof.pdf"
    path.write_bytes(b"pdf")

    class First:
        async def count(self):
            return 1

        async def set_input_files(self, value, timeout=0):
            assert value == str(path)

    class Text:
        @property
        def first(self):
            return self

        async def wait_for(self, timeout=0):
            return None

    class Page:
        def locator(self, selector):
            assert selector == "input[type='file']"
            class Input:
                @property
                def first(self):
                    return First()
            return Input()

        def get_by_text(self, *_args, **_kwargs):
            return Text()

    import asyncio

    assert asyncio.run(upload_file(Page(), str(path))) == {
        "source_path": str(path),
        "file_name": "proof.pdf",
        "status": "uploaded",
    }


def test_upload_file_surfaces_portal_rejection(tmp_path, monkeypatch):
    path = tmp_path / "too-large.pdf"
    path.write_bytes(b"pdf")

    class First:
        async def count(self):
            return 1

        async def set_input_files(self, value, timeout=0):
            return None

    class Text:
        @property
        def first(self):
            return self

        async def wait_for(self, timeout=0):
            raise TimeoutError("not visible")

    class Page:
        def locator(self, selector):
            class Input:
                @property
                def first(self):
                    return First()
            return Input()

        def get_by_text(self, *_args, **_kwargs):
            return Text()

    async def fake_errors(_page):
        return ["File size exceeds allowed limit"]

    monkeypatch.setattr("modules.govt_sync.filing.tamil_nadu.detect_validation_errors", fake_errors)

    import asyncio

    with pytest.raises(PortalValidationError) as exc:
        asyncio.run(upload_file(Page(), str(path)))
    assert "File size exceeds allowed limit" in str(exc.value)
