"""
tests/test_govt_status_manual_window.py — dedicated tests for
ManualAssistedAdapter.check_status()'s reference-number-window scan
(fixation-plan Step 6: scope the keyword scan to text near the citizen's own
reference number, instead of the whole flattened page).

Step 5 (modules/govt_sync/adapters/base.py's normalize_status_keywords) is
NOT modified or retested here — these tests exercise manual.py's new window
selection, which happens before normalize_status_keywords() is ever called
and does not change that function.

Two of the fixtures below (UP_TRACKER_TEXT, CPGRAMS_STATUS_TEXT) are the real
flattened page text captured during the Step 6 read-only investigation via a
plain GET against each portal's live public URL — no CAPTCHA, OTP, login, or
form submission was performed to obtain them. Neither is a real status
result page (UP's is the pre-search tracker form; CPGRAMS's is its
login/CAPTCHA-gated status form) — that's the point: as of this change,
neither portal exposes a real result page through this adapter's plain
unauthenticated GET, so these are the only two real, non-hypothetical
"whole-page text a citizen's browser never asked to see a status on" samples
this project has.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.govt_sync.adapters.manual import ManualAssistedAdapter


# ─── Real captured page text (see module docstring) ────────────────────────

UP_TRACKER_TEXT = (
    "Track Grievance | Samadhan उत्तर प्रदेश सरकार Uttar Pradesh Government A + A A - "
    "Language हिंदी English M Material Style Login Register Recovery Pass Username "
    "Password Remember Me Login Login with Facebook Twitter Google Username Email "
    "Password Re-type Password Register Now Username Email Send Password सन्दर्भ की "
    "स्थिति देखें/Track Complaint Status नोट :- जनसुनवाई पोर्टल द्वारा केवल 3 माह "
    "पूर्व तक के निस्तारित सन्दर्भों का विवरण देखा जा सकेगा मोबाइल नंबर से पंजीकृत "
    "शिकायतें प्राप्त करें शिकायत संख्या * मोबाइल नंबर * कृपया नीचे दिए बॉक्स में "
    "उपलब्ध सुरक्षा कोड अंकित करें कैप्चा अंकित करें * सबमिट करें रीसेट Enter OTP * "
    "सत्यापित ओ० टी० पी०/Verify OTP होम © Content owned, updated by the Lok Shikayat "
    "Vibhag, Chief Minister Office Uttar Pradesh Government. Website is designed, "
    "developed, maintained and hosted by National Informatics Centre, Uttar Pradesh. × ×"
)

CPGRAMS_STATUS_TEXT = (
    "View Status भारत सरकार Government of India कार्मिक, लोक शिकायत और पेंशन "
    "मंत्रालय Ministry of Personnel, Public Grievances & Pensions Home Download "
    "Contact Us About Us FAQs/Help Site Map CPGRAMS Centralized Public Grievance "
    "Redress And Monitoring System EXPERIENCE CPGRAMS APP ON MOBILE View Status "
    "Grievance Status Appeal Status Nodal PG Officers Central Government State "
    "Government Redress Process Redress Process Flow Grievance Lodge Public "
    "Grievance Lodge Pension Grievance View Status Reminder Clarification Rate "
    "Grievance Nodal Authority for Appeal (current) Mobile App Language : English "
    "English हिंदी (Hindi) ગુજરાતી (Gujarati) मराठी (Marathi) বাংলা (Bangala) "
    "తెలుగు (Telugu) অসমীয়া (Assamese) ଓଡିଆ (Odia) தமிழ் (Tamil) മലയാളം "
    "(Malayalam) (Urdu) اردو Sindhi बोडो (Bodo) कोंकणी (Konkani) नेपाली (Nepali) "
    "Manipuri ਪੰਜਾਬੀ (Punjabi) ಕನ್ನಡ (Kannada) डोगरी (Dogri) मैथिली (Maithili) "
    "کشمیر (Kashmiri) संस्कृत (Sanskrit) ᱥᱟᱱᱛᱟᱲᱤ (Santhali) Sign In View Status "
    "Fields marked with * are mandatory. Registration number Grievance password "
    "#--OR-- Email id or Mobile number Security Code submit This site is designed, "
    "developed & hosted by National Informatics Centre, Ministry of Electronics & "
    "IT (MeitY), Government of India and Content owned by Department of "
    "Administrative Reforms & Public Grievances. Portal is Compatible with all "
    "major Browsers like Google Chrome, Mozilla Firefox, Microsoft Edge, Safari "
    "etc. Best Viewed in 1440 x 900 resolution Disclaimer Website Policies Web "
    "Information Manager Version 7.0.01092019.0.0, Copyright © 2026 Last Updated "
    "On: 21-08-2026 Total Visitors : 7897287 (since 19-01-2024)"
)


def _adapter():
    return ManualAssistedAdapter({
        "portal_name": "Test Portal",
        "status_check_mode": "public_reference",
        "status_check_url": "https://example.test/status",
    })


def _check(monkeypatch, page_text, reference_number="REF123"):
    import requests

    class _FakeResponse:
        text = f"<html><body>{page_text}</body></html>"
        def raise_for_status(self):
            pass

    monkeypatch.setattr(requests, "get", lambda *a, **kw: _FakeResponse())
    return _adapter().check_status(reference_number)


# ─── Reference-not-found: fail closed, no fallback to full-page scan ───────

def test_reference_absent_fails_closed_even_with_status_keywords_present(monkeypatch):
    # "Resolved" is right there in the page — but REF123 never appears
    # anywhere in it. Per the Step 6 decision this must fail closed rather
    # than fall back to scanning the rest of the page.
    page_text = "Grievance Resolved. Please contact us for any other query."
    result = _check(monkeypatch, page_text, reference_number="REF123")
    assert result.checked is False
    assert result.status == ""


# ─── Reference found: window behavior ──────────────────────────────────────

def test_status_inside_window_is_detected(monkeypatch):
    page_text = "Status for REF123: Resolved"
    result = _check(monkeypatch, page_text, reference_number="REF123")
    assert result.checked is True
    assert result.status == "resolved"


def test_status_outside_window_is_not_detected(monkeypatch):
    # "Resolved" sits ~320 chars after REF123 — just past the ±300 window.
    padding = "x" * 310
    page_text = f"Ref REF123 {padding} Resolved"
    result = _check(monkeypatch, page_text, reference_number="REF123")
    assert result.checked is False
    assert result.status == ""


def test_far_away_unrelated_keyword_is_ignored_near_match_still_wins(monkeypatch):
    # A stray "Rejected" far from the reference number (well outside the
    # window) must not collide with a real, near "Resolved" and must not
    # itself be picked up.
    far_padding = "x" * 400
    page_text = f"Rejected {far_padding} Ref REF123: Resolved"
    result = _check(monkeypatch, page_text, reference_number="REF123")
    assert result.checked is True
    assert result.status == "resolved"


def test_ordinary_reference_and_nearby_status_regression(monkeypatch):
    # Plain, no-decoy case — must keep working exactly as the pre-Step-6
    # whole-page scan did for the simple case.
    page_text = "Your grievance REF123 is currently Under Review."
    result = _check(monkeypatch, page_text, reference_number="REF123")
    assert result.checked is True
    assert result.status == "under_review"


def test_no_keyword_near_reference_returns_unchecked(monkeypatch):
    page_text = "Details for REF123 are being compiled. Check back later."
    result = _check(monkeypatch, page_text, reference_number="REF123")
    assert result.checked is False
    assert result.status == ""


# ─── Window boundary behavior ───────────────────────────────────────────────

def test_status_exactly_at_window_boundary_is_included(monkeypatch):
    # window_end = ref_index + len(ref) + 300. With ref="REF123" (6 chars)
    # starting at index 0, window_end = 306, i.e. the slice includes indices
    # 0..305. 292 padding chars put "Resolved" (8 chars) at indices 298..305
    # — landing exactly on the last 8 characters the window includes.
    # Verified directly (not just derived by hand) before writing this test.
    ref = "REF123"
    padding = "x" * 292
    page_text = f"{ref}{padding}Resolved"
    result = _check(monkeypatch, page_text, reference_number=ref)
    assert result.checked is True
    assert result.status == "resolved"


def test_status_one_char_past_window_boundary_is_excluded(monkeypatch):
    # One more padding character shifts "Resolved" to indices 299..306 — the
    # window (0..305) now only catches "Resolve" (missing the final "d"),
    # which is not a substring match for the "resolved" keyword, so no
    # bucket matches at all. Verified directly before writing this test.
    ref = "REF123"
    padding = "x" * 293
    page_text = f"{ref}{padding}Resolved"
    result = _check(monkeypatch, page_text, reference_number=ref)
    assert result.checked is False
    assert result.status == ""


def test_reference_near_start_of_page_window_does_not_go_negative(monkeypatch):
    # ref_index - 300 would be negative here; window_start = max(0, ...)
    # must clamp instead of wrapping/erroring.
    page_text = "REF123 Resolved"
    result = _check(monkeypatch, page_text, reference_number="REF123")
    assert result.checked is True
    assert result.status == "resolved"


# ─── Real captured non-result pages (see module docstring) ─────────────────

def test_real_up_jansunwai_tracker_pre_search_page_fails_closed(monkeypatch):
    # Real page contains two different STATUS_KEYWORDS hits in its own
    # boilerplate/disclaimer text (resolved bucket via "निस्तारित", submitted
    # bucket via "प्राप्त") but never mentions this reference number at all —
    # it's the pre-search form, not a result. Must fail closed on
    # reference-not-found, not on Step 5's cross-bucket collision.
    result = _check(monkeypatch, UP_TRACKER_TEXT, reference_number="UP/2026/00012345")
    assert result.checked is False
    assert result.status == ""


def test_real_cpgrams_status_login_form_page_fails_closed(monkeypatch):
    # Real page is CPGRAMS's login/CAPTCHA-gated status form, not a result —
    # never mentions any reference number either.
    result = _check(monkeypatch, CPGRAMS_STATUS_TEXT, reference_number="DARPG/E/2026/00012345")
    assert result.checked is False
    assert result.status == ""
