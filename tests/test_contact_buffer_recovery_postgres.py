"""
tests/test_contact_buffer_recovery_postgres.py — held (contact-buffered) cases are
released after a restart, exactly once.

A case is held for a short window before it is acknowledged. The release used to
depend only on an in-process timer, so a restart during the hold stranded the case
(the citizen was acknowledged, staff never saw it). The startup and periodic
sweeps now release due cases, and an atomic claim stops two workers releasing the
same case. The release SQL is PostgreSQL-only (jsonb), so this needs a DISPOSABLE
PostgreSQL database; without NEEDLE_PG_TEST_URL the module is skipped.
"""
import inspect
import json
import os
import sys
import threading
from datetime import datetime, timezone

import pytest

PG_URL = os.environ.get("NEEDLE_PG_TEST_URL", "")
if not PG_URL.startswith("postgresql"):
    pytest.skip("NEEDLE_PG_TEST_URL not set to a PostgreSQL URL", allow_module_level=True)

os.environ.setdefault("DATABASE_URL", PG_URL)
os.environ.setdefault("ENV", "test")
os.environ.setdefault("JWT_SECRET", "test-secret-key-32-characters-minimum-ok")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-testing")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text  # noqa: E402

import core.db_helpers as db_helpers  # noqa: E402
import main  # noqa: E402
import sansadx_backend.db as dbmod  # noqa: E402
from sansadx_backend.db import Base  # noqa: E402

pg_engine = create_engine(PG_URL, pool_size=6)


def _epoch(offset=0):
    return int(datetime.now(timezone.utc).timestamp()) + offset


@pytest.fixture(autouse=True)
def pg(monkeypatch):
    dbmod.engine = pg_engine
    db_helpers.engine = pg_engine
    main.engine = pg_engine
    Base.metadata.create_all(bind=pg_engine)
    with pg_engine.begin() as conn:
        for t in ("case_activity_log", "cases", "tenants"):
            conn.execute(text(f"DELETE FROM {t}"))  # nosec B608
        conn.execute(text("INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active, created_at) "
                          "VALUES (1, 'T1', 'X', '+919000000001', 'Pro', true, NOW())"))
        for cid, release in ((10, _epoch(-60)), (11, _epoch(3600))):
            conn.execute(text(
                "INSERT INTO cases (id, tenant_id, user_phone, raw_message, category, status, case_metadata, created_at, is_deleted) "
                "VALUES (:id, 1, '919812345678', 'No water for three days', 'Water', 'contact_buffered', CAST(:m AS JSON), NOW(), false)"),
                {"id": cid, "m": json.dumps({"contact_buffered": True, "contact_release_after_epoch": release,
                                             "contact_buffer_release_status": "new", "contact_buffer_ack_message": "We got it"})})
    released = []
    lock = threading.Lock()

    def fake_release(**kw):
        with lock:
            released.append(kw["case_id"])
        with pg_engine.begin() as conn:
            conn.execute(text("UPDATE cases SET status = 'new' WHERE id = :id"), {"id": kw["case_id"]})

    monkeypatch.setattr(main, "_save_case_enrichment_and_respond", fake_release)
    monkeypatch.setattr(main, "get_tenant_phone_number_id", lambda tid: "pnid")
    yield released
    with pg_engine.begin() as conn:
        for t in ("case_activity_log", "cases", "tenants"):
            conn.execute(text(f"DELETE FROM {t}"))  # nosec B608


def test_sweep_releases_due_held_case_after_restart(pg):
    # No in-process timer exists (as after a restart); the sweep alone releases it.
    assert not main._contact_buffer_release_timers
    main._release_due_buffered_contact_cases()
    assert pg == [10]
    with pg_engine.connect() as conn:
        assert conn.execute(text("SELECT status FROM cases WHERE id = 11")).scalar() == "contact_buffered"  # not due yet


def test_concurrent_sweeps_release_once(pg):
    barrier = threading.Barrier(4)

    def sweep():
        barrier.wait()
        main._release_due_buffered_contact_cases()

    threads = [threading.Thread(target=sweep) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert pg == [10]


def test_fresh_claim_blocks_and_stale_claim_is_retaken(pg):
    with pg_engine.begin() as conn:
        conn.execute(text("UPDATE cases SET case_metadata = CAST(jsonb_set(CAST(case_metadata AS jsonb), "
                          "'{contact_buffer_claimed_epoch}', to_jsonb(CAST(:e AS bigint))) AS json) WHERE id = 10"), {"e": _epoch(-30)})
    main._release_due_buffered_contact_cases()
    assert pg == []                      # another worker claimed it 30 s ago
    with pg_engine.begin() as conn:
        conn.execute(text("UPDATE cases SET case_metadata = CAST(jsonb_set(CAST(case_metadata AS jsonb), "
                          "'{contact_buffer_claimed_epoch}', to_jsonb(CAST(:e AS bigint))) AS json) WHERE id = 10"), {"e": _epoch(-3600)})
    main._release_due_buffered_contact_cases()
    assert pg == [10]                    # that worker died; the claim is retaken


def test_release_is_wired_into_startup_and_periodic_sweeps():
    assert "_release_due_buffered_contact_cases" in inspect.getsource(main.startup_jobs)
    assert "_release_due_buffered_contact_cases" in inspect.getsource(main._schedule_inbound_ledger_sweep)
