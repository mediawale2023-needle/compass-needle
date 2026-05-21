from modules.localized_replies import (
    get_generic_ack_reply,
    get_location_update_reply,
    get_review_ack_reply,
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
    assert "Tumcha" in reply
    assert "team" in reply.lower()
    assert "Thank you" not in reply


def test_generic_ack_uses_marathi_for_roman_marathi_input():
    msg = "Kangrali madhe khup chori hot aahe"
    reply = get_generic_ack_reply("Marathi", msg)
    assert "Tumcha sandesh" in reply
    assert "Thank you" not in reply


def test_location_update_reply_uses_requested_language():
    msg = "Kangrali madhe khup chori hot aahe"
    reply = get_location_update_reply("Kangrali", "Marathi", msg)
    assert "Kangrali" in reply
    assert "Tumchi" in reply
