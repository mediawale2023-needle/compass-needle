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


def test_explicit_grouping_preserves_all_source_ids():
    from modules.whatsapp_segment_provenance import attribute_indexed_segments
    messages = [message("Water issue", "wa-1", 101),
                message("Ward five", "wa-2", 102),
                message("Road issue", "wa-3", 103)]
    result = attribute_indexed_segments(messages, [[0, 1], [2]])
    assert all(segment.verified for segment in result)
    assert result[0].source_message_ids == ("wa-1", "wa-2")
    assert result[0].inbound_ledger_ids == (101, 102)
    assert result[1].source_message_ids == ("wa-3",)


@pytest.mark.parametrize("groups", [[[0], [0, 1]], [[0]], [[0, 3]], [[], [0, 1]], [[True, 1]]])
def test_invalid_explicit_grouping_fails_closed(groups):
    from modules.whatsapp_segment_provenance import attribute_indexed_segments
    result = attribute_indexed_segments(
        [message("Water", "wa-1", 101), message("Road", "wa-2", 102)], groups)
    assert all(not segment.verified for segment in result)


def test_explicit_grouping_rejects_missing_ledger():
    from modules.whatsapp_segment_provenance import attribute_indexed_segments
    result = attribute_indexed_segments(
        [message("Water", "wa-1", 101), message("Ward", "wa-2", None)], [[0, 1]])
    assert not result[0].verified
