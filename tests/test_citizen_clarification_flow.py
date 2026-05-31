from main import (
    _apply_clarification_metadata,
    _build_clarification_follow_up_message,
    _resolve_citizen_ack_message,
)


def test_awaiting_location_ack_stays_generic_on_first_reply():
    msg = "Raat ko area mein patrolling kam hai aur bike theft incidents badh gaye hain."
    reply = _resolve_citizen_ack_message(
        status="awaiting_location",
        detected_language="Hindi",
        message_body=msg,
        location_name="",
    )

    assert "message mil gaya" in reply.lower() or "sandesh mil gaya" in reply.lower()
    assert "ward" not in reply.lower()
    assert "landmark" not in reply.lower()


def test_incomplete_ack_does_not_ask_for_details_immediately():
    msg = "Please help"
    reply = _resolve_citizen_ack_message(
        status="incomplete",
        detected_language="English",
        message_body=msg,
        location_name=None,
    )

    assert "your issue" in reply.lower() or "message" in reply.lower()
    assert "your name" not in reply.lower()
    assert "address" not in reply.lower()


def test_apply_clarification_metadata_marks_missing_location_followup():
    meta, scheduled = _apply_clarification_metadata(
        {"summary": "road issue"},
        status="awaiting_location",
        sender="919876543210",
        detected_language="Hindi",
    )

    assert scheduled is True
    assert meta["clarification_follow_up_pending"] is True
    assert meta["clarification_follow_up_sent"] is False
    assert meta["clarification_follow_up_kind"] == "missing_location"
    assert meta["citizen_phone"] == "919876543210"
    assert isinstance(meta["clarification_follow_up_after_epoch"], int)


def test_apply_clarification_metadata_clears_flags_when_case_is_complete():
    meta, scheduled = _apply_clarification_metadata(
        {
            "clarification_follow_up_pending": True,
            "clarification_follow_up_sent": True,
            "clarification_follow_up_kind": "missing_details",
            "clarification_follow_up_after_epoch": 123,
            "citizen_phone": "919876543210",
        },
        status="new",
        sender="919876543210",
        detected_language="English",
    )

    assert scheduled is False
    assert "clarification_follow_up_pending" not in meta
    assert "clarification_follow_up_kind" not in meta
    assert "citizen_phone" not in meta


def test_missing_location_followup_message_asks_only_for_location():
    msg = "Raat ko area mein patrolling kam hai aur bike theft incidents badh gaye hain."
    reply = _build_clarification_follow_up_message(
        {
            "clarification_language": "Hindi",
            "clarification_follow_up_kind": "missing_location",
        },
        msg,
    )

    assert "landmark" in reply.lower() or "gaon" in reply.lower() or "area" in reply.lower()
    assert "aapka naam" not in reply.lower()
