from modules.localized_replies import get_additional_issue_ack_reply


def test_additional_issue_ack_does_not_expose_internal_issue_classification():
    reply = get_additional_issue_ack_reply(
        2,
        "Hinglish",
        "Dhar mein drainage ki samasya hai",
    )
    lowered = reply.lower()
    assert "alag issue" not in lowered
    assert "separate issue" not in lowered
    assert "total 2" not in lowered
    assert "2 complaints" not in lowered
    assert "review mein" not in lowered
    assert "under review" not in lowered
    assert "message note kar liya" in lowered


def test_additional_issue_ack_does_not_expose_count_in_english():
    reply = get_additional_issue_ack_reply(7, "English", "Drainage is blocked")
    lowered = reply.lower()
    assert "7" not in reply
    assert "complaints" not in lowered
    assert "separate" not in lowered
    assert "review" not in lowered
    assert "noted this concern" in lowered


def test_additional_issue_ack_preserves_romanized_hindi_style():
    reply = get_additional_issue_ack_reply(
        3,
        "Hindi",
        "Ghar ke paas naali jam hai",
    )
    assert reply.startswith("Ji,")
    assert "Aapki baat note kar li gayi hai" in reply
