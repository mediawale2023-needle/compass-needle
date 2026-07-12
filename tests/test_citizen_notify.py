import os

os.environ.setdefault("JWT_SECRET", "x" * 32)

import api_router


def test_resolve_notification_prefers_requested_message():
    case = {
        "id": 42,
        "status": "resolved",
        "case_ref": "CN-42",
        "response_to_citizen": "Thank you for reaching out 🙏\n\nYour issue has been received and is being reviewed by our team.",
    }

    message = api_router._resolve_citizen_notification_message(
        case,
        requested_message="Your case has been resolved. Please stay in touch.",
    )

    assert message == "Your case has been resolved. Please stay in touch."


def test_resolve_notification_uses_saved_response_before_template():
    case = {
        "id": 7,
        "status": "resolved",
        "case_ref": "CN-7",
        "response_to_citizen": "Custom stored response",
    }

    message = api_router._resolve_citizen_notification_message(case)

    assert message == "Custom stored response"


def test_resolve_notification_falls_back_to_composer_without_case_refs():
    # Policy: citizen messages never carry case reference numbers, never use
    # emotional language, and never describe a reply-'NO' reopen mechanism
    # (which does not exist). The old English-only status dict did all three.
    case = {
        "id": 9,
        "status": "resolved",
        "case_ref": "CN-9",
        "response_to_citizen": "",
        "case_metadata": "{}",
    }

    message = api_router._resolve_citizen_notification_message(case)

    assert "CN-9" not in message
    assert "#" not in message
    assert "good news" not in message.lower()
    assert "reopen" not in message.lower()
    assert message.startswith("Ji,")


def test_resolve_notification_fallback_uses_citizen_language():
    case = {
        "id": 10,
        "status": "in_progress",
        "response_to_citizen": "",
        "problem_subdomain": "Water Supply",
        "case_metadata": '{"detected_language": "Marathi"}',
    }

    message = api_router._resolve_citizen_notification_message(case)

    assert "तक्रारी" in message  # Marathi, not English
    assert "पाण्याची समस्या" in message  # taxonomy issue phrase, not free text
