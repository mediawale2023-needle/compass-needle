"""
tests/test_govt_status_check_attempts.py — direct tests of
modules/govt_sync/status_attempts.py, the Postgres-backed replacement for
Karnataka's/Maharashtra's process-local `_attempts` dicts.

This file tests ONLY the persistence mechanics (create/load/update-stage/
delete) — portal-interaction behavior (CAPTCHA/OTP/parsing) is unaffected
by this migration and stays covered by test_karnataka_status_check.py and
test_maharashtra_status_check.py, unmodified.

No government portal is contacted anywhere in this file.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, text

TEST_DB_URL = "sqlite:///./test_govt_status_check_attempts.db"
os.environ.setdefault("JWT_SECRET", "test-secret-key-32-characters-minimum-ok")
os.environ.setdefault("DATABASE_URL", TEST_DB_URL)
os.environ.setdefault("ENV", "test")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-testing")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.db_helpers as db_helpers
import sansadx_backend.db as dbmod
from sansadx_backend.db import Base

from modules.govt_sync.status_attempts import create_attempt, delete_attempt, load_attempt, update_attempt_stage

test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _reset_db():
    # load_attempt() reads via core.db_helpers._q_one, which uses
    # core.db_helpers.engine — a separate module global from
    # sansadx_backend.db.engine. Both must point at this file's test_engine,
    # or load_attempt() silently reads/writes the wrong sqlite file when
    # this test file runs alongside others in one pytest session.
    dbmod.engine = test_engine
    db_helpers.engine = test_engine
    Base.metadata.create_all(bind=test_engine)
    with test_engine.begin() as conn:
        conn.execute(text("DELETE FROM govt_status_check_attempts"))
        conn.execute(text("DELETE FROM cases"))
        conn.execute(text("DELETE FROM tenants"))
        conn.execute(text(
            "INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active, created_at) "
            "VALUES (1, 'Test Tenant', 'Test Constituency', '+919000000099', 'Pro', 1, :now)"
        ), {"now": _utcnow()})
        conn.execute(text(
            "INSERT INTO cases (id, tenant_id, user_phone, raw_message, category, status, created_at, is_deleted) "
            "VALUES (50, 1, '+919111111150', 'Test grievance', 'Infrastructure & Utilities', 'in_progress', :now, 0)"
        ), {"now": _utcnow()})


def _create(attempt_id="attempt-1", tenant_id=1, case_id=50, stage=0, cookies=None):
    create_attempt(
        attempt_id=attempt_id,
        tenant_id=tenant_id,
        case_id=case_id,
        adapter_key="karnataka_ipgrs",
        reference_number="REF/0001",
        mobile_or_email="919000000000",
        cookies=cookies or {"ASP.NET_SessionId": "abc123"},
        stage=stage,
    )


def test_create_then_load_from_a_separate_engine_simulates_cross_worker_access():
    """The entire point of this migration: an attempt created via one DB
    connection/engine handle must be readable via a completely different
    one — modeling two different backend workers, which don't share any
    Python process memory."""
    _reset_db()
    _create()

    other_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    with other_engine.connect() as conn:
        row = conn.execute(
            text("SELECT attempt_id, tenant_id, case_id, cookies FROM govt_status_check_attempts WHERE attempt_id = :aid"),
            {"aid": "attempt-1"},
        ).mappings().first()
    assert row is not None
    assert row["tenant_id"] == 1
    assert row["case_id"] == 50

    loaded = load_attempt("attempt-1", 1, 50, ttl_seconds=300)
    assert loaded is not None
    assert loaded["cookies"] == {"ASP.NET_SessionId": "abc123"}
    assert loaded["reference_number"] == "REF/0001"
    assert loaded["mobile_or_email"] == "919000000000"


def test_tenant_mismatch_returns_none_indistinguishable_from_not_found():
    _reset_db()
    _create(tenant_id=1)
    assert load_attempt("attempt-1", 999, 50, ttl_seconds=300) is None


def test_case_mismatch_returns_none_indistinguishable_from_not_found():
    _reset_db()
    _create(case_id=50)
    assert load_attempt("attempt-1", 1, 999, ttl_seconds=300) is None


def test_unknown_attempt_id_returns_none():
    _reset_db()
    assert load_attempt("does-not-exist", 1, 50, ttl_seconds=300) is None


def test_expired_attempt_returns_none():
    _reset_db()
    _create()
    # Directly age the row past its TTL — the same effect real wall-clock
    # time would have, without an actual sleep in the test.
    with test_engine.begin() as conn:
        conn.execute(
            text("UPDATE govt_status_check_attempts SET last_activity_at = :old WHERE attempt_id = :aid"),
            {"old": _utcnow() - timedelta(seconds=301), "aid": "attempt-1"},
        )
    assert load_attempt("attempt-1", 1, 50, ttl_seconds=300) is None
    # Still fresh at 299s must remain usable.
    with test_engine.begin() as conn:
        conn.execute(
            text("UPDATE govt_status_check_attempts SET last_activity_at = :recent WHERE attempt_id = :aid"),
            {"recent": _utcnow() - timedelta(seconds=299), "aid": "attempt-1"},
        )
    assert load_attempt("attempt-1", 1, 50, ttl_seconds=300) is not None


def test_update_attempt_stage_succeeds_when_expected_stage_matches():
    _reset_db()
    _create(stage=0)
    advanced = update_attempt_stage(
        "attempt-1", expected_stage=0, stage=1,
        cookies={"MAHASESS": "s1"}, csrf_token="csrf-1", token="tok-1",
    )
    assert advanced is True
    loaded = load_attempt("attempt-1", 1, 50, ttl_seconds=600)
    assert loaded["stage"] == 1
    assert loaded["cookies"] == {"MAHASESS": "s1"}
    assert loaded["csrf_token"] == "csrf-1"
    assert loaded["token"] == "tok-1"


def test_update_attempt_stage_preserves_token_and_cid_when_not_passed():
    """Stage 1->2 doesn't touch `token` (only cid changes) — the update must
    not silently null it out."""
    _reset_db()
    _create(stage=0)
    update_attempt_stage("attempt-1", expected_stage=0, stage=1, cookies={}, csrf_token="c0", token="tok-1")
    update_attempt_stage("attempt-1", expected_stage=1, stage=2, cookies={}, csrf_token="c1", cid="cid-1")
    loaded = load_attempt("attempt-1", 1, 50, ttl_seconds=600)
    assert loaded["stage"] == 2
    assert loaded["token"] == "tok-1"  # preserved
    assert loaded["cid"] == "cid-1"


def test_update_attempt_stage_fails_atomically_on_concurrent_stage_mismatch():
    """The core concurrency proof: two requests both believing the attempt
    is still at stage 0 cannot both successfully advance it. Exactly one
    UPDATE affects a row; the other affects zero rows and its caller must
    treat that as a clean failure, never a second success."""
    _reset_db()
    _create(stage=0)

    first = update_attempt_stage("attempt-1", expected_stage=0, stage=1, cookies={"c": "1"}, csrf_token="csrf-a")
    second = update_attempt_stage("attempt-1", expected_stage=0, stage=1, cookies={"c": "2"}, csrf_token="csrf-b")

    assert first is True
    assert second is False  # the loser — row was already at stage 1, not 0
    loaded = load_attempt("attempt-1", 1, 50, ttl_seconds=600)
    assert loaded["cookies"] == {"c": "1"}  # the winner's write, not corrupted/overwritten by the loser
    assert loaded["csrf_token"] == "csrf-a"


def test_delete_attempt_is_atomic_and_idempotent():
    """Two near-simultaneous terminal consumptions (success/failure) of the
    same attempt_id must never both report success — exactly one DELETE
    actually removes the row."""
    _reset_db()
    _create()

    first_delete = delete_attempt("attempt-1")
    second_delete = delete_attempt("attempt-1")

    assert first_delete is True
    assert second_delete is False  # already gone — not a crash, not a second "success"
    assert load_attempt("attempt-1", 1, 50, ttl_seconds=300) is None


def test_concurrent_attempts_for_different_cases_are_independent():
    _reset_db()
    _create(attempt_id="attempt-A", case_id=50)
    with test_engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO cases (id, tenant_id, user_phone, raw_message, category, status, created_at, is_deleted) "
            "VALUES (51, 1, '+919111111151', 'Second grievance', 'Infrastructure & Utilities', 'in_progress', :now, 0)"
        ), {"now": _utcnow()})
    _create(attempt_id="attempt-B", case_id=51)

    assert load_attempt("attempt-A", 1, 50, ttl_seconds=300) is not None
    assert load_attempt("attempt-B", 1, 51, ttl_seconds=300) is not None
    # Cross-referencing the wrong case for either attempt fails closed.
    assert load_attempt("attempt-A", 1, 51, ttl_seconds=300) is None
    assert load_attempt("attempt-B", 1, 50, ttl_seconds=300) is None
