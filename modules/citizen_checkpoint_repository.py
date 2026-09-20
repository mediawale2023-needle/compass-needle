"""Transactional checkpoint repository for future buffered intake.

This module has no production caller. The case factory MUST create its case
using the supplied SQLAlchemy Session, never open another connection or send
WhatsApp messages. Database uniqueness guards concurrent attempts.
"""
from dataclasses import dataclass
from typing import Callable, Sequence

from modules.citizen_segment_checkpoint import stable_segment_key


@dataclass(frozen=True)
class ClaimResult:
    case_id: int
    created: bool
    segment_key: str


def create_or_reuse_case(
    session_factory: Callable,
    *,
    tenant_id: int,
    buffer_id: int,
    ordinal: int,
    source_ledger_ids: Sequence[int],
    create_case: Callable,
) -> ClaimResult:
    """Atomically commit a new case and checkpoint, or reuse a committed case.

    An existing checkpoint without a case ID is NOT treated as permission to
    create a case; it needs manual reconciliation. A uniqueness conflict from
    concurrent processing is surfaced for a later retry, not guessed away.
    """
    from sansadx_backend.db import CitizenSegmentCheckpoint

    ids = tuple(source_ledger_ids)
    key = stable_segment_key(tenant_id, buffer_id, ordinal, ids)
    with session_factory() as session:
        with session.begin():
            checkpoint = session.query(CitizenSegmentCheckpoint).filter_by(
                segment_key=key
            ).with_for_update().one_or_none()
            if checkpoint is not None:
                if (checkpoint.tenant_id != tenant_id or checkpoint.buffer_id != buffer_id
                        or checkpoint.segment_ordinal != ordinal):
                    raise ValueError("checkpoint identity mismatch")
                if tuple(checkpoint.source_ledger_ids) != ids:
                    raise ValueError("checkpoint source mismatch")
                if checkpoint.case_id is None:
                    raise RuntimeError("checkpoint has no committed case")
                return ClaimResult(int(checkpoint.case_id), False, key)
            # Keep case creation and checkpoint INSERT in this SAME transaction.
            case = create_case(session)
            case_id = getattr(case, "id", None)
            if case_id is None:
                session.flush()
                case_id = getattr(case, "id", None)
            if not isinstance(case_id, int) or case_id <= 0:
                raise RuntimeError("case factory did not create a persisted case")
            session.add(CitizenSegmentCheckpoint(
                tenant_id=tenant_id,
                buffer_id=buffer_id,
                segment_ordinal=ordinal,
                segment_key=key,
                source_ledger_ids=list(ids),
                case_id=case_id,
                state="case_created",
                acknowledgement_state="not_attempted",
            ))
            session.flush()
            return ClaimResult(case_id, True, key)
