from modules.localized_replies import (
    DETAILS_REQUEST_STATUSES,
    ensure_ji_prefix,
    get_generic_ack_reply,
    get_location_update_reply,
    get_review_ack_reply,
    normalize_language_name,
)
from sansadx_backend.ai_engine import detect_input_language


def test_detect_input_language_identifies_roman_marathi_complaint():
    msg = "Kangrali madhe khup chori hot aahe"
    assert detect_input_language(msg) == "Marathi"


def test_detect_input_language_identifies_short_roman_marathi_complaint():
    msg = "Tilakwadi madhe pani nahi"
    assert detect_input_language(msg) == "Marathi"


def test_review_ack_uses_marathi_for_roman_marathi_input():
    msg = "Kangrali madhe khup chori hot aahe"
    reply = get_review_ack_reply("Marathi", msg)
    assert reply.startswith("Ji,")
    assert "Tumcha" in reply
    assert "team" in reply.lower()
    assert "Thank you" not in reply


def test_generic_ack_uses_marathi_for_roman_marathi_input():
    msg = "Kangrali madhe khup chori hot aahe"
    reply = get_generic_ack_reply("Marathi", msg)
    assert reply.startswith("Ji,")
    assert "Tumcha sandesh" in reply
    assert "Thank you" not in reply


def test_location_update_reply_uses_requested_language():
    msg = "Kangrali madhe khup chori hot aahe"
    reply = get_location_update_reply("Kangrali", "Marathi", msg)
    assert reply.startswith("Ji,")
    assert "Kangrali" in reply
    assert "Tumchi" in reply


def test_ensure_ji_prefix_is_idempotent():
    assert ensure_ji_prefix("Ji, Tumcha sandesh milala") == "Ji, Tumcha sandesh milala"
    assert ensure_ji_prefix("Tumcha sandesh milala") == "Ji, Tumcha sandesh milala"


def test_details_request_only_for_incomplete_cases():
    assert DETAILS_REQUEST_STATUSES == {"incomplete"}


def test_normalize_language_name_does_not_invent_hindi_for_unknown_hint():
    assert normalize_language_name("marathi", "") == "Marathi"
    assert normalize_language_name("unknown", "") == ""
