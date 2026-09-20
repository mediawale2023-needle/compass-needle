"""Experimental index-based grouping for buffered citizen messages.

Not wired to production intake. The existing text-only segmenter remains
unchanged. All model-supplied indices are validated before use.
"""
import json
from dataclasses import dataclass
from typing import Callable, Sequence

from modules.whatsapp_segment_provenance import attribute_indexed_segments


@dataclass(frozen=True)
class GroupingResult:
    groups: tuple[tuple[int, ...], ...]
    verified: bool
    reason: str


def validate_grouping(raw: object, message_count: int, max_groups: int = 4) -> GroupingResult:
    if type(message_count) is not int or message_count < 1:
        return GroupingResult((), False, "empty_input")
    if not isinstance(raw, dict) or not isinstance(raw.get("groups"), list):
        return GroupingResult((), False, "invalid_schema")
    groups = raw["groups"]
    if not groups or len(groups) > max_groups:
        return GroupingResult((), False, "invalid_group_count")
    if any(not isinstance(group, list) or not group for group in groups):
        return GroupingResult((), False, "invalid_group")
    flat = [index for group in groups for index in group]
    if any(type(index) is not int or index < 0 or index >= message_count for index in flat):
        return GroupingResult((), False, "invalid_index")
    if sorted(flat) != list(range(message_count)):
        return GroupingResult((), False, "missing_or_duplicate_source")
    if any(group != sorted(group) for group in groups):
        return GroupingResult((), False, "reordered_source")
    if [group[0] for group in groups] != sorted(group[0] for group in groups):
        return GroupingResult((), False, "reordered_groups")
    return GroupingResult(tuple(tuple(group) for group in groups), True, "validated")


def group_synthetic_collection(
    messages: Sequence[dict],
    model_grouping: object,
) -> GroupingResult:
    """Offline adapter: group indices plus independently verified source IDs."""
    result = validate_grouping(model_grouping, len(messages))
    if not result.verified:
        return result
    provenance = attribute_indexed_segments(messages, result.groups)
    if not provenance or not all(segment.verified for segment in provenance):
        return GroupingResult((), False, "missing_source_identifiers")
    return result
