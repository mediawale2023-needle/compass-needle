"""Synthetic provenance tests; no production records or WhatsApp traffic."""
import pytest
from modules.whatsapp_segment_provenance import attribute_segments


def message(body, msg_id="wa-1", ledger_id=101):
    return {"body": body, "msg_id": msg_id, "inbound_ledger_id": ledger_id}


def test_single_exact_message():
    result = attribute_segments([message("Streetlight broken")], ["Streetlight broken"])
    assert result[0].verified
    assert result[0].source_message_ids == ("wa-1",)
    assert result[0].inbound_ledger_ids == (101,)


def test_distinct_exact_messages():
    result = attribute_segments(
        [message("Streetlight", "wa-1", 101), message("Water", "wa-2", 102)],
        ["Streetlight", "Water"])
    assert all(item.verified for item in result)


@pytest.mark.parametrize("messages,segments", [
    ([message("Streetlight"), message("Near school", "wa-2", 102)],
     ["Streetlight near school"]),
    ([message("Streetlight and water")], ["Streetlight", "water"]),
    ([message("Streetlight")], ["Streetlight repaired"]),
    ([message("Same"), message("Same", "wa-2", 102)], ["Same", "Same"]),
    ([message("Streetlight", ledger_id=None)], ["Streetlight"]),
    ([message("Streetlight", msg_id="")], ["Streetlight"]),
    ([message("Streetlight"), message("Water", "wa-2", 102)],
     ["Water", "Streetlight"]),
])
def test_ambiguous_or_incomplete_provenance_fails_closed(messages, segments):
    result = attribute_segments(messages, segments)
    assert result
    assert not any(item.verified for item in result)
    assert all(not item.source_message_ids and not item.inbound_ledger_ids for item in result)
