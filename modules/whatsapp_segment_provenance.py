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


def attribute_indexed_segments(
    messages: Sequence[dict],
    groups: Sequence[Sequence[int]],
) -> tuple[SegmentProvenance, ...]:
    """Validate explicit zero-based source indices; never infer them from text.

    Every source message must appear exactly once across groups. The caller
    must obtain grouping from a trusted segmentation result, not guess it
    from the number or ordering of generated segment strings.
    """
    if not messages or not groups:
        return ()
    flat = [index for group in groups for index in group]
    valid = (
        all(group for group in groups)
        and all(type(index) is int and 0 <= index < len(messages) for index in flat)
        and sorted(flat) == list(range(len(messages)))
    )
    if not valid:
        return tuple(SegmentProvenance("", (), (), False) for _ in groups)
    results = []
    for group in groups:
        sources = [messages[index] for index in group]
        ids = tuple(str(item.get("msg_id") or "").strip() for item in sources)
        try:
            ledgers = tuple(int(item.get("inbound_ledger_id")) for item in sources)
        except (TypeError, ValueError):
            ledgers = ()
        verified = (
            all(ids) and len(set(ids)) == len(ids)
            and len(ledgers) == len(sources)
            and all(value > 0 for value in ledgers)
            and len(set(ledgers)) == len(ledgers)
        )
        results.append(SegmentProvenance(
            segment_text="\\n".join(str(item.get("body") or "").strip() for item in sources)
                if verified else "",
            source_message_ids=ids if verified else (),
            inbound_ledger_ids=ledgers if verified else (),
            verified=bool(verified),
        ))
    return tuple(results)
