"""Golden tests + validator tests for the citizen communication policy.

The golden section asserts BYTE-IDENTICAL composer output for a fixed input
matrix. This is what guarantees consistent acknowledgements regardless of the
underlying LLM: wording can only change through a reviewed diff to these
snapshots, never through model drift.
"""
import os
import sys

os.environ.setdefault("JWT_SECRET", "x" * 32)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.ack_composer import compose_status_update, resolve_issue_phrase
from modules.ack_validator import validate_citizen_message, violation_codes
from modules import localized_replies


# ── Golden snapshots: exact strings, reviewed by hand ────────────────────────

GOLDEN = {
    ("resolved", "English", None): (
        "Ji, Action on your complaint has been completed 🙏 "
        "If the problem still remains, please tell us on this same number."
    ),
    ("in_progress", "Marathi", "Water Supply"): (
        "Ji, तुमच्या तक्रारीवर (पाण्याची समस्या) काम सुरू आहे 🙏 "
        "काही अपडेट मिळताच आम्ही तुम्हाला कळवू."
    ),
    ("new", "Hinglish", None): (
        "Ji, Aapki complaint hamare paas registered hai aur review mein hai 🙏 "
        "Jaise hi koi update hoga, hum aapko batayenge."
    ),
    ("closed", "Kannada", None): (
        "Ji, ನಿಮ್ಮ ದೂರನ್ನು ಮುಚ್ಚಲಾಗಿದೆ 🙏 "
        "ಯಾವುದೇ ಹೊಸ ಸಮಸ್ಯೆಗೆ ನೀವು ಇದೇ ಸಂಖ್ಯೆಗೆ ಬರೆಯಬಹುದು."
    ),
    # Unknown language falls back to Hindi; unknown status falls back to a
    # truthful receipt confirmation.
    ("weird_status", "Klingon", None): (
        "Ji, Aapki shikayat hamare paas darj hai aur review mein hai 🙏 "
        "Jaise hi koi update hoga, hum aapko batayenge."
    ),
}


def test_composer_output_is_byte_identical_to_golden_snapshots():
    for (status, language, subdomain), expected in GOLDEN.items():
        actual = compose_status_update(status, language, problem_subdomain=subdomain)
        assert actual == expected, f"({status}, {language}, {subdomain}):\n got: {actual!r}\n want: {expected!r}"


def test_composer_is_deterministic_across_calls():
    first = [compose_status_update("resolved", "Marathi", problem_subdomain="Roads & Bridges") for _ in range(3)]
    assert len(set(first)) == 1


def test_every_composer_output_passes_the_validator():
    statuses = ["new", "pending", "in_progress", "escalated", "resolved", "completed", "closed", "unknown"]
    languages = ["Hindi", "Hinglish", "Marathi", "Kannada", "English", "Tamil", ""]
    subdomains = [None, "Water Supply", "Roads & Bridges", "Drainage & Sewerage", "No Such Subdomain"]
    for status in statuses:
        for language in languages:
            for subdomain in subdomains:
                message = compose_status_update(status, language, problem_subdomain=subdomain)
                result = validate_citizen_message(message, lane="notify")
                assert result["ok"], f"composer violated policy for ({status},{language},{subdomain}): {result['violations']}"


def test_intake_templates_pass_the_validator():
    """The deterministic intake acks must themselves comply with the policy."""
    samples = [
        localized_replies.get_generic_ack_reply("Hindi", "paani nahi hai"),
        localized_replies.get_generic_ack_reply("English", "no water"),
        localized_replies.get_details_request_reply("Marathi", ""),
        localized_replies.get_missing_location_reply("Hinglish", "road kharab hai"),
        localized_replies.get_additional_issue_ack_reply(3, "Kannada", ""),
        localized_replies.get_thread_reassurance_reply("English", "hello?"),
        localized_replies.get_high_frequency_notice_reply("Hindi", ""),
    ]
    for message in samples:
        result = validate_citizen_message(message, lane="ack")
        assert result["ok"], f"intake template violated policy: {result['violations']}\n{message!r}"


def test_issue_phrase_comes_from_dictionary_only():
    assert resolve_issue_phrase("Water Supply", "Marathi") == "पाण्याची समस्या"
    assert resolve_issue_phrase("Water Supply", "Unknown Lang") == "paani ki samasya"  # Hindi fallback
    assert resolve_issue_phrase("Quantum Teleportation", "Hindi") is None  # no entry -> no slot, no AI


# ── Validator: each violation class ──────────────────────────────────────────

def _codes(text, lane="notify"):
    return violation_codes(validate_citizen_message(text, lane=lane))


def test_validator_rejects_case_references():
    assert "case_reference" in _codes("Your grievance (#123) has been resolved.")
    assert "case_reference" in _codes("Complaint number: 456 is in progress")


def test_validator_rejects_outcome_and_deadline_promises():
    assert "outcome_promise" in _codes("The road will be fixed soon.")
    assert "outcome_promise" in _codes("Aapka kaam ho jayega, chinta mat kijiye.")
    assert "outcome_promise" in _codes("We guarantee resolution.")
    assert "deadline_promise" in _codes("This will be handled within 3 days.")
    assert "deadline_promise" in _codes("Team will visit by tomorrow.")
    assert "reopen_mechanism" in _codes("If unsatisfied, reply 'NO' to reopen.")


def test_validator_rejects_political_content_and_amplifiers():
    assert "political_content" in _codes("Vote for our party in the next election.")
    assert "political_content" in _codes("The BJP office has been informed.")
    assert "emotional_amplifier" in _codes("Good news! Your issue is resolved.")
    assert "exclamation" in _codes("Done!")


def test_validator_rejects_formatting_problems():
    assert "leftover_placeholder" in _codes("Your complaint {issue} is registered.")
    assert "emoji_not_allowed" in _codes("All done 🎉🙏")
    assert "too_long" in _codes("x" * 800)


def test_validator_accepts_clean_office_messages():
    clean = (
        "Ji, we have forwarded your complaint to the PWD office 🙏 "
        "We will inform you when there is an update."
    )
    result = validate_citizen_message(clean, lane="notify")
    assert result["ok"], result["violations"]


def test_validator_treats_empty_as_valid():
    assert validate_citizen_message("", lane="notify")["ok"] is True
    assert validate_citizen_message(None, lane="notify")["ok"] is True
