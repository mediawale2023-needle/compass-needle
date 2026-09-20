"""Conservative source attribution for buffered WhatsApp segmentation.

This helper does not modify intake or outbound behaviour. Segmentation that
merges, splits, reorders or rewrites input messages needs an explicit source
mapping from the segmenter; positional attribution is not evidence.
"""
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class SegmentProvenance:
    segment_text: str
    source_message_ids: tuple[str, ...]
    inbound_ledger_ids: tuple[int, ...]
    verified: bool


def attribute_segments(
    messages: Sequence[dict], segments: Sequence[str]
) -> tuple[SegmentProvenance, ...]:
    """Return verified provenance only for unambiguous exact 1:1 mapping.

    Reject duplicate text, missing IDs, rewritten text, merged messages and
    split messages. In all such cases an explicit segmenter mapping is needed.
    """
    bodies = [str(item.get("body") or "").strip() for item in messages]
    texts = [str(segment or "").strip() for segment in segments]
    exact = (
        len(messages) == len(texts)
        and all(bodies[i] == texts[i] and bodies[i] for i in range(len(texts)))
        and len(set(bodies)) == len(bodies)
    )
    result = []
    for index, segment in enumerate(texts):
        item = messages[index] if exact else {}
        msg_id = str(item.get("msg_id") or "").strip()
        raw_ledger = item.get("inbound_ledger_id")
        try:
            ledger_id = int(raw_ledger)
        except (TypeError, ValueError):
            ledger_id = 0
        verified = bool(exact and msg_id and ledger_id > 0)
        result.append(SegmentProvenance(
            segment_text=segment,
            source_message_ids=(msg_id,) if verified else (),
            inbound_ledger_ids=(ledger_id,) if verified else (),
            verified=verified,
        ))
    return tuple(result)
