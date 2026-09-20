"""Synthetic index-group validation tests; no LLM or network calls."""
import pytest
from modules.citizen_index_grouping_shadow import validate_grouping, group_synthetic_collection


def test_two_issues_with_merged_fragments():
    result = validate_grouping({"groups": [[0, 1], [2]]}, 3)
    assert result.verified
    assert result.groups == ((0, 1), (2,))


@pytest.mark.parametrize("raw,count", [
    ({"groups": [[0, 0], [1]]}, 2),
    ({"groups": [[0]]}, 2),
    ({"groups": [[0, 2]]}, 2),
    ({"groups": [[True, 1]]}, 2),
    ({"groups": [[1, 0]]}, 2),
    ({"groups": [[1], [0]]}, 2),
    ({"groups": []}, 2),
    ({"segments": ["water"]}, 2),
    ({"groups": [[0], [1], [2], [3], [4]]}, 5),
])
def test_invalid_grouping_is_rejected(raw, count):
    assert not validate_grouping(raw, count).verified


def test_offline_grouping_requires_source_ids():
    messages = [
        {"body": "Water issue", "msg_id": "wa1", "inbound_ledger_id": 11},
        {"body": "Ward five", "msg_id": "wa2", "inbound_ledger_id": 12},
        {"body": "Road issue", "msg_id": "wa3", "inbound_ledger_id": 13},
    ]
    assert group_synthetic_collection(messages, {"groups": [[0, 1], [2]]}).verified
    messages[1]["inbound_ledger_id"] = None
    assert not group_synthetic_collection(messages, {"groups": [[0, 1], [2]]}).verified
