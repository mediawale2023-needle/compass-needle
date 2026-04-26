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


def test_resolve_notification_falls_back_to_status_template():
    case = {
        "id": 9,
        "status": "resolved",
        "case_ref": "CN-9",
        "response_to_citizen": "",
    }

    message = api_router._resolve_citizen_notification_message(case)

    assert "resolved" in message.lower()
    assert "CN-9" in message
