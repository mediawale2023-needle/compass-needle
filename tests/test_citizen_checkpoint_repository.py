"""Transactional checkpoint tests: no live WhatsApp or production database."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from modules.citizen_checkpoint_repository import create_or_reuse_case
from sansadx_backend.db import Base, Case, CitizenSegmentCheckpoint


@pytest.fixture
def sessions(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "checkpoints.db"))
    Base.metadata.create_all(engine, tables=[
        Case.__table__, CitizenSegmentCheckpoint.__table__,
    ])
    yield sessionmaker(bind=engine, expire_on_commit=False)
    engine.dispose()


def _create_case(session):
    case = Case(tenant_id=1, user_phone="test-only")
    session.add(case)
    session.flush()
    return case


def _claim(sessions, ids=(101, 102), create_case=_create_case):
    return create_or_reuse_case(
        sessions, tenant_id=1, buffer_id=20, ordinal=0,
        source_ledger_ids=ids, create_case=create_case,
    )


def test_committed_retry_reuses_case(sessions):
    first = _claim(sessions)
    second = _claim(sessions)
    assert first.created is True
    assert second.created is False
    assert second.case_id == first.case_id
    with sessions() as session:
        assert session.query(Case).count() == 1
        assert session.query(CitizenSegmentCheckpoint).count() == 1


def test_changed_grouping_fails_closed(sessions):
    _claim(sessions)
    with pytest.raises(ValueError, match="source mismatch"):
        _claim(sessions, ids=(101, 103))
    with sessions() as session:
        assert session.query(Case).count() == 1


def test_case_factory_failure_rolls_back_checkpoint_and_case(sessions):
    def fail_after_insert(session):
        _create_case(session)
        raise RuntimeError("simulated crash")
    with pytest.raises(RuntimeError, match="simulated crash"):
        _claim(sessions, create_case=fail_after_insert)
    with sessions() as session:
        assert session.query(Case).count() == 0
        assert session.query(CitizenSegmentCheckpoint).count() == 0
    assert _claim(sessions).created is True


def test_orphan_checkpoint_requires_reconciliation(sessions):
    from modules.citizen_segment_checkpoint import stable_segment_key
    with sessions.begin() as session:
        session.add(CitizenSegmentCheckpoint(
            tenant_id=1, buffer_id=20, segment_ordinal=0,
            segment_key=stable_segment_key(1, 20, 0, (101, 102)),
            source_ledger_ids=[101, 102], case_id=None,
            state="pending", acknowledgement_state="not_attempted",
        ))
    with pytest.raises(RuntimeError, match="no committed case"):
        _claim(sessions)
    with sessions() as session:
        assert session.query(Case).count() == 0
