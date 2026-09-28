"""Durable segment checkpoint primitives for a future transactional intake path.

No production caller: do not use this as a substitute for atomic case creation
and an idempotent outbound queue. All transitions require the caller to hold
the buffer's database processing lock.
"""
import hashlib
import json
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class SegmentCheckpoint:
    key: str
    buffer_id: int
    segment_ordinal: int
    source_ledger_ids: tuple[int, ...]
    case_id: int | None = None
    state: str = "pending"
    acknowledgement_state: str = "not_attempted"


def stable_segment_key(
    tenant_id: int, buffer_id: int, ordinal: int, source_ledger_ids: Sequence[int]
) -> str:
    if tenant_id <= 0 or buffer_id <= 0 or ordinal < 0:
        raise ValueError("invalid checkpoint identity")
    ids = tuple(source_ledger_ids)
    if not ids or any(type(value) is not int or value <= 0 for value in ids):
        raise ValueError("missing source ledger identity")
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate source ledger identity")
    payload = json.dumps([tenant_id, buffer_id, ordinal, ids], separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def next_action(checkpoint: SegmentCheckpoint) -> str:
    """Fail closed when outbound status is uncertain.

    A checkpoint must be committed in the same transaction as case creation.
    The outbound sender must use a separate idempotency guarantee before
    attempting a send. This function never authorizes a WhatsApp send.
    """
    if checkpoint.state == "pending" and checkpoint.case_id is None:
        return "create_case_transactionally"
    if checkpoint.case_id is None:
        return "manual_reconciliation"
    if checkpoint.state == "case_created":
        return "verify_source_links"
    if checkpoint.state == "links_verified":
        return "await_idempotent_outbound"
    if checkpoint.state == "done":
        return "already_processed"
    return "manual_reconciliation"
