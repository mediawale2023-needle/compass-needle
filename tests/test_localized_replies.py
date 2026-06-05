from modules.localized_replies import (
    DETAILS_REQUEST_STATUSES,
    ensure_ji_prefix,
    get_awaiting_location_reply,
    get_generic_ack_reply,
    get_greeting_reply,
    get_location_update_reply,
    get_review_ack_reply,
    normalize_language_name,
)


def test_greeting_reply_invites_concern_and_is_not_a_grievance_ack():
    reply = get_greeting_reply("English", "Good morning")
    assert reply.startswith("Ji, Namaste")
    assert "help you" in reply.lower()
    # Must NOT reuse the grievance acknowledgement wording.
    assert "issue has been received" not in reply.lower()


def test_greeting_reply_uses_roman_marathi_for_roman_input():
    reply = get_greeting_reply("Marathi", "Namaskar saheb")
    assert "Namaskar" in reply
    assert "madat" in reply.lower()
from sansadx_backend.ai_engine import (
    detect_input_language,
    detect_input_language_confident,
)


def test_detect_input_language_identifies_roman_marathi_complaint():
    msg = "Kangrali madhe khup chori hot aahe"
    assert detect_input_language(msg) == "Marathi"


def test_unrecognized_romanized_input_is_not_confident():
    # Romanized Kannada the static marker list cannot enumerate
    # ("idhe"/"nalli", code-mixed with Marathi "raste"). The rule-based
    # detector must NOT confidently claim English here — it should report low
    # confidence so the caller defers to the LLM's detection instead of
    # replying to the citizen in the wrong language.
    msg = "Hindwadi nalli raste bahal kait idhe"
    _lang, confident = detect_input_language_confident(msg)
    assert confident is False


def test_confident_detection_preserved_for_strong_markers():
    # Strong, unambiguous signals must stay confident so the rule-based result
    # still wins over the LLM for these cases.
    assert detect_input_language_confident("neeru illa alli maadi beku") == ("Kannada", True)
    assert detect_input_language_confident("Kangrali madhe khup chori hot aahe") == ("Marathi", True)
    assert detect_input_language_confident("Tilakwadi madhe pani nahi") == ("Marathi", True)
    assert detect_input_language_confident("yahan paani nahi aata hai kya") == ("Hinglish", True)


def test_plain_english_is_not_confidently_overridden():
    # Plain English with no markers is a low-confidence guess; the LLM (which
    # also sees the message) confirms English, so the citizen still gets English.
    lang, confident = detect_input_language_confident("Water supply is broken near the school")
    assert lang == "English"
    assert confident is False


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


def test_awaiting_location_reply_asks_for_more_details_without_failure_language():
    reply = get_awaiting_location_reply("Shanti Baswad", "English", "Shanti Baswad road issue")

    assert reply.startswith("Ji,")
    assert "name" in reply.lower()
    assert "exact location/area" in reply
    assert "ward" in reply.lower()
    assert "landmark" in reply.lower()
    assert "Shanti Baswad" not in reply
    assert "could not" not in reply.lower()
    assert "identify" not in reply.lower()
    assert "not able" not in reply.lower()


def test_awaiting_location_reply_uses_neutral_roman_marathi_wording():
    reply = get_awaiting_location_reply("Shanti Baswad", "Marathi", "Shanti Baswad madhe rasta kharab aahe")

    assert reply.startswith("Ji,")
    assert "tumcha naav" in reply.lower()
    assert "ward number" in reply.lower()
    assert "landmark" in reply.lower()
    assert "Shanti Baswad" not in reply
    assert "olakh" not in reply.lower()
    assert "samajh nahi" not in reply.lower()


def test_ensure_ji_prefix_is_idempotent():
    assert ensure_ji_prefix("Ji, Tumcha sandesh milala") == "Ji, Tumcha sandesh milala"
    assert ensure_ji_prefix("Tumcha sandesh milala") == "Ji, Tumcha sandesh milala"


def test_details_request_only_for_incomplete_cases():
    assert DETAILS_REQUEST_STATUSES == {"incomplete"}


def test_normalize_language_name_does_not_invent_hindi_for_unknown_hint():
    assert normalize_language_name("marathi", "") == "Marathi"
    assert normalize_language_name("unknown", "") == ""
