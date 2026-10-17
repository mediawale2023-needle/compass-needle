"""Real PostgreSQL concurrency checks for modules/case_lifecycle.py.

SQLite cannot run two writers against one row, so these run only when
NEEDLE_LIFECYCLE_PG_URL points at a THROWAWAY PostgreSQL database (the test
creates and drops its own tables). Skipped otherwise; the deterministic
compare-and-set test in test_case_status_lifecycle.py always runs.
"""
import os
import threading
import time

import pytest
from sqlalchemy import create_engine, text

from modules import case_lifecycle

PG_URL = os.getenv("NEEDLE_LIFECYCLE_PG_URL", "")
pytestmark = pytest.mark.skipif(not PG_URL, reason="NEEDLE_LIFECYCLE_PG_URL not set")


@pytest.fixture
def pg_engine():
    engine = create_engine(PG_URL, pool_size=4)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS case_activity_log"))
        conn.execute(text("DROP TABLE IF EXISTS cases"))
        conn.execute(text(
            "CREATE TABLE cases (id INT PRIMARY KEY, tenant_id INT NOT NULL, status VARCHAR, "
            "updated_at TIMESTAMP, status_changed_at TIMESTAMP)"
        ))
        conn.execute(text(
            "CREATE TABLE case_activity_log (id SERIAL PRIMARY KEY, tenant_id INT, case_id INT, "
            "username VARCHAR, action VARCHAR, old_value VARCHAR, new_value VARCHAR, details TEXT, "
            "created_at TIMESTAMP)"
        ))
        conn.execute(text("INSERT INTO cases (id, tenant_id, status) VALUES (1, 1, 'new')"))
    yield engine
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS case_activity_log"))
        conn.execute(text("DROP TABLE IF EXISTS cases"))
    engine.dispose()


def _final(engine):
    with engine.connect() as conn:
        status = conn.execute(text("SELECT status FROM cases WHERE id = 1")).scalar_one()
        logs = conn.execute(text("SELECT COUNT(*) FROM case_activity_log")).scalar_one()
    return status, logs


def test_concurrent_staff_resolution_wins_over_evidence(pg_engine):
    staff_locked = threading.Event()
    outcome = {}

    def staff():
        with pg_engine.begin() as conn:
            conn.execute(text("UPDATE cases SET status = 'resolved' WHERE id = 1"))
            staff_locked.set()
            time.sleep(0.5)  # evidence's UPDATE is now blocked on this row lock

    def evidence():
        staff_locked.wait(5)
        with pg_engine.begin() as conn:
            outcome["moved"] = case_lifecycle.apply_external_evidence(
                conn, tenant_id=1, case_id=1, evidence=case_lifecycle.EVIDENCE_GOVT_PORTAL_CONFIRMED,
            )

    threads = [threading.Thread(target=staff), threading.Thread(target=evidence)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)

    assert outcome["moved"] is False
    assert _final(pg_engine) == ("resolved", 0)


def test_concurrent_duplicate_evidence_moves_and_logs_exactly_once(pg_engine):
    barrier = threading.Barrier(4)
    results = []

    def evidence():
        barrier.wait(5)
        with pg_engine.begin() as conn:
            results.append(case_lifecycle.apply_external_evidence(
                conn, tenant_id=1, case_id=1, evidence=case_lifecycle.EVIDENCE_GOVT_FILING_RECORDED,
            ))

    threads = [threading.Thread(target=evidence) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)

    assert sorted(results) == [False, False, False, True]
    assert _final(pg_engine) == ("in_progress", 1)
