import os
import sys

os.environ.setdefault("JWT_SECRET", "x" * 32)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.case_comment_heuristics import detect_case_comment, MAX_WORDS

MAHARASHTRA_LANGUAGES = ["Marathi", "Hindi", "English", "Hinglish"]
KARNATAKA_LANGUAGES = ["Kannada", "English", "Hindi", "Hinglish"]


def test_detects_urging_english():
    matched, tone = detect_case_comment(
        "But we need action. Dont just register complaints", MAHARASHTRA_LANGUAGES
    )
    assert matched is True
    assert tone == "urging"


def test_detects_gratitude_english():
    matched, tone = detect_case_comment("Thank you so much", MAHARASHTRA_LANGUAGES)
    assert matched is True
    assert tone == "grateful"


def test_detects_status_inquiry_english():
    matched, tone = detect_case_comment("Any update on this?", MAHARASHTRA_LANGUAGES)
    assert matched is True
    assert tone == "status_inquiry"


def test_detects_pending_commentary():
    matched, tone = detect_case_comment("The issue is still pending", MAHARASHTRA_LANGUAGES)
    assert matched is True
    assert tone == "status_inquiry"


def test_detects_marathi_urging():
    matched, tone = detect_case_comment("त्वरित कारवाई करा", MAHARASHTRA_LANGUAGES)
    assert matched is True
    assert tone == "urging"


def test_detects_kannada_gratitude():
    matched, tone = detect_case_comment("dhanyavadagalu", KARNATAKA_LANGUAGES)
    assert matched is True
    assert tone == "grateful"


def test_does_not_match_language_not_in_tenant_set():
    # Kannada phrase, but tenant is configured for Maharashtra languages only.
    matched, _ = detect_case_comment("dhanyavadagalu", MAHARASHTRA_LANGUAGES)
    assert matched is False


def test_does_not_match_a_real_new_complaint():
    matched, _ = detect_case_comment(
        "Water supply has not come for 3 days in Whitefield area", MAHARASHTRA_LANGUAGES
    )
    assert matched is False


def test_long_message_is_not_matched_even_if_it_contains_a_phrase():
    # A genuine long complaint that happens to include "any update" as an
    # aside must not be hijacked by the heuristic — length cap protects this.
    long_message = (
        "Sir the drainage near our house has been overflowing for many days "
        "and children cannot walk on the road any update would help but the "
        "main problem is the smell and mosquitoes are increasing every day"
    )
    assert len(long_message.split()) > MAX_WORDS
    matched, _ = detect_case_comment(long_message, MAHARASHTRA_LANGUAGES)
    assert matched is False


def test_empty_text_does_not_match():
    matched, tone = detect_case_comment("", MAHARASHTRA_LANGUAGES)
    assert matched is False
    assert tone is None


def test_media_attachment_note_is_detected_as_other():
    matched, tone = detect_case_comment("I have attached the photo", MAHARASHTRA_LANGUAGES)
    assert matched is True
    assert tone == "other"
