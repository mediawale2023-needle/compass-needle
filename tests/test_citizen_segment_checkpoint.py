"""Checkpoint identity and retry decisions without live citizen data."""
import pytest
from modules.citizen_segment_checkpoint import (
    SegmentCheckpoint, next_action, stable_segment_key,
)


def test_stable_identity_and_distinct_segments():
    key = stable_segment_key(1, 12, 0, [101, 102])
    assert key == stable_segment_key(1, 12, 0, [101, 102])
    assert key != stable_segment_key(1, 12, 1, [103])
    assert key != stable_segment_key(2, 12, 0, [101, 102])


@pytest.mark.parametrize("ids", [[], [0], [1, 1], [-1], ["1"], [True]])
def test_invalid_source_identity_rejected(ids):
    with pytest.raises(ValueError):
        stable_segment_key(1, 12, 0, ids)


def test_retry_reuses_created_case_instead_of_creating_another():
    checkpoint = SegmentCheckpoint("key", 12, 0, (101, 102), 900, "case_created")
    assert next_action(checkpoint) == "verify_source_links"


def test_unknown_case_state_requires_reconciliation():
    checkpoint = SegmentCheckpoint("key", 12, 0, (101,), None, "case_created")
    assert next_action(checkpoint) == "manual_reconciliation"


def test_outbound_never_authorized_by_checkpoint():
    for state in ("pending", "case_created", "links_verified", "done", "unknown"):
        checkpoint = SegmentCheckpoint("key", 12, 0, (101,), 900, state)
        assert next_action(checkpoint) != "send_whatsapp"
