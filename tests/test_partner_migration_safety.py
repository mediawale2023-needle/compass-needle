"""Partner schema migration safety: expand/contract, lock-gated migration, readiness.

SQLite section: gate + HTTP behaviour (failure, lock contention, retry).
PostgreSQL section (set NEEDLE_PG_TEST_URL to a DISPOSABLE database): real advisory locks, the retained
`seat_cap` column, the phase-2 drop, and the CLI. Skipped, never silently passed, without that variable.
"""
import logging
import os
import subprocess
import sys

import pytest

PG_URL = os.environ.get("NEEDLE_PG_TEST_URL", "")
TEST_DB_URL = PG_URL if PG_URL.startswith("postgresql") else "sqlite:///./test_partner_migration_safety.db"

os.environ["JWT_SECRET"] = "test-secret-key-32-characters-minimum-ok"
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["ENV"] = "test"
os.environ["OPENAI_API_KEY"] = "sk-test-fake-key-for-testing"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine


@event.listens_for(Engine, "connect")
def _sqlite_register_pg_lock_functions(dbapi_connection, connection_record):
    try:
        dbapi_connection.create_function("pg_try_advisory_lock", 1, lambda _key: 1)
        dbapi_connection.create_function("pg_advisory_unlock", 1, lambda _key: 1)
        dbapi_connection.create_function("pg_try_advisory_xact_lock", 1, lambda _key: 1)
    except Exception:
        pass


import main
import modules.partners as P
import sansadx_backend.db as dbmod

client = TestClient(main.app, raise_server_exceptions=False)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(autouse=True)
def _restore_gate():
    yield
    P.SCHEMA_GATE.set_ready()


def _fresh_gate():
    return P.PartnerSchemaGate()


# ───────────────────────── SQLite: failure / contention / retry ─────────────────────────
pytestmark_sqlite = pytest.mark.skipif(PG_URL.startswith("postgresql"), reason="SQLite-section tests")


@pytestmark_sqlite
def test_genuine_migration_failure_blocks_readiness_and_dependent_endpoints_only(monkeypatch, caplog):
    def boom(engine=None):
        raise P.PartnerMigrationError("OperationalError: permission denied for table partners")
    monkeypatch.setattr(P, "ensure_partner_schema", boom)
    with caplog.at_level(logging.CRITICAL, logger="needle.partner"):
        P.startup_partner_migration(dbmod.engine, gate=P.SCHEMA_GATE, start_retry_thread=False)

    assert P.SCHEMA_GATE.state == "failed" and "permission denied" in P.SCHEMA_GATE.detail
    msg = " ".join(r.getMessage() for r in caplog.records)
    assert "PARTNER SCHEMA MIGRATION FAILED" in msg and "permission denied" in msg and "retries automatically" in msg   # actionable

    health = client.get("/health")
    assert health.status_code == 503 and health.json()["partner_schema"] == "failed"
    for method, path in (("get", "/api/partner/me"), ("get", "/api/partner/clients"), ("get", "/api/admin/partners"),
                         ("post", "/api/admin/partners"), ("post", "/api/admin/mps"), ("get", "/api/admin/partners/selectable")):
        resp = getattr(client, method)(path)
        assert resp.status_code == 503 and resp.headers.get("retry-after") == "30", path        # even before auth: nothing half-works
    assert client.get("/api/admin/mps").status_code != 503                                        # unrelated admin routes keep serving
    assert client.get("/").status_code == 200                                                    # citizen-facing app is not taken down


@pytestmark_sqlite
def test_retry_after_failure_recovers_without_restart(monkeypatch):
    calls = {"n": 0}
    real = P.ensure_partner_schema

    def flaky(engine=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise P.PartnerMigrationError("OperationalError: connection reset")
        return real(engine)
    monkeypatch.setattr(P, "ensure_partner_schema", flaky)

    P.startup_partner_migration(dbmod.engine, gate=P.SCHEMA_GATE, start_retry_thread=False)
    assert P.SCHEMA_GATE.state == "failed" and client.get("/health").status_code == 503
    P._migrate_under_lock(dbmod.engine, P.SCHEMA_GATE)                                           # what the retry thread does
    assert P.SCHEMA_GATE.ready and calls["n"] == 2
    assert client.get("/health").status_code == 200
    assert client.get("/api/partner/me").status_code == 401                                     # reachable again (needs auth), not 503
    P._migrate_under_lock(dbmod.engine, P.SCHEMA_GATE)                                           # idempotent: another run is harmless
    assert P.SCHEMA_GATE.ready


@pytestmark_sqlite
def test_instance_without_the_lock_waits_and_never_migrates_on_its_own(monkeypatch):
    ran = []
    monkeypatch.setattr(P, "ensure_partner_schema", lambda engine=None: ran.append(1))
    monkeypatch.setattr(P, "_try_acquire_lock", lambda engine: (None, False))                    # another instance holds it
    monkeypatch.setattr(P, "partner_schema_status", lambda engine=None: {"ready": False, "problems": ["missing tables: partners"]})
    gate = _fresh_gate()
    P.startup_partner_migration(dbmod.engine, gate=gate, start_retry_thread=False)
    assert ran == [] and gate.state == "pending" and "waiting" in gate.detail                     # did NOT migrate, not ready

    # the lock holder finishes -> the waiter becomes ready without ever running the migration
    monkeypatch.setattr(P, "partner_schema_status", lambda engine=None: {"ready": True, "problems": []})
    P._migrate_under_lock(dbmod.engine, gate)
    assert gate.ready and ran == []


@pytestmark_sqlite
def test_waiter_takes_over_only_by_acquiring_the_lock(monkeypatch):
    ran, released = [], []
    monkeypatch.setattr(P, "ensure_partner_schema", lambda engine=None: ran.append(1) or {})
    monkeypatch.setattr(P, "partner_schema_status", lambda engine=None: {"ready": False, "problems": ["missing tables: partners"]})
    answers = iter([(None, False), ("LOCK-CONN", True)])
    monkeypatch.setattr(P, "_try_acquire_lock", lambda engine: next(answers))
    monkeypatch.setattr(P, "_release_lock", lambda conn: released.append(conn))
    gate = _fresh_gate()
    P._migrate_under_lock(dbmod.engine, gate)
    assert ran == [] and gate.state == "pending"
    P._migrate_under_lock(dbmod.engine, gate)                                                     # lock now free: this instance migrates
    assert ran == [1] and released == ["LOCK-CONN"]
    # (ensure is mocked, so the schema check above still says not ready -> failed, which is the correct outcome here)


@pytestmark_sqlite
def test_holder_from_main_runs_once_without_a_second_lock_attempt(monkeypatch):
    ran = []
    monkeypatch.setattr(P, "ensure_partner_schema", lambda engine=None: ran.append(1) or {})
    monkeypatch.setattr(P, "_try_acquire_lock", lambda engine: (_ for _ in ()).throw(AssertionError("must not re-acquire")))
    gate = _fresh_gate()
    P.startup_partner_migration(dbmod.engine, gate=gate, start_retry_thread=False, holds_lock=True)
    assert ran == [1] and gate.ready


@pytestmark_sqlite
def test_unreachable_database_reports_failed_not_ready(monkeypatch):
    def down(engine):
        raise RuntimeError("could not connect to server")
    monkeypatch.setattr(P, "_try_acquire_lock", down)
    gate = _fresh_gate()
    P.startup_partner_migration(dbmod.engine, gate=gate, start_retry_thread=False)
    assert gate.state == "failed" and "database" in gate.detail


@pytestmark_sqlite
def test_status_flags_unattributed_seats_and_migration_fixes_them():
    from datetime import datetime
    P.ensure_partner_schema(dbmod.engine)
    with dbmod.engine.begin() as conn:
        conn.execute(text("DELETE FROM tenant_attribution_events")); conn.execute(text("DELETE FROM tenant_attributions"))
        conn.execute(text("DELETE FROM partner_seats")); conn.execute(text("DELETE FROM partners")); conn.execute(text("DELETE FROM tenants"))
        conn.execute(text("INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, tenant_type, account_stage, seat_type, is_active, created_at) "
                          "VALUES (91, 'T', 'C', '+910000009191', 'Pro', 'aspirant', 'aspirant', 'mla', 1, :n)"), {"n": datetime.utcnow()})
        conn.execute(text("INSERT INTO partners (id, name, slug, brand_name, is_active, created_at) VALUES (91, 'P', 'p91', 'P', 1, :n)"), {"n": datetime.utcnow()})
        conn.execute(text("INSERT INTO partner_seats (partner_id, tenant_id, client_label, status, created_at) VALUES (91, 91, 'x', 'active', :n)"), {"n": datetime.utcnow()})
    status = P.partner_schema_status(dbmod.engine)
    assert status["ready"] is False and "no attribution record" in status["problems"][0]
    assert P.ensure_partner_schema(dbmod.engine)["backfilled"] == 1 and P.partner_schema_status(dbmod.engine)["ready"]


# ───────────────────────── PostgreSQL: real locks, expand / contract ─────────────────────────
needs_pg = pytest.mark.skipif(not PG_URL.startswith("postgresql"), reason="NEEDLE_PG_TEST_URL not set to a PostgreSQL URL")


@pytest.fixture
def pg():
    eng = create_engine(PG_URL, pool_size=5)
    with eng.begin() as c:
        c.execute(text("DROP SCHEMA public CASCADE")); c.execute(text("CREATE SCHEMA public"))
    dbmod.Base.metadata.create_all(bind=eng, tables=[dbmod.Tenant.__table__])
    yield eng
    eng.dispose()


def _cap_default(eng):
    with eng.connect() as c:
        return c.execute(text("SELECT column_default FROM information_schema.columns WHERE table_name='partners' AND column_name='seat_cap'")).scalar()


def _legacy_partners_table(eng):
    P.ensure_partner_schema(eng)
    with eng.begin() as c:
        c.execute(text("ALTER TABLE partners ADD COLUMN seat_cap integer"))
        c.execute(text("INSERT INTO partners (name, slug, brand_name, seat_cap, is_active) VALUES ('Old', 'old', 'Old', 5, true)"))


@needs_pg
def test_phase1_keeps_seat_cap_so_old_instances_still_work(pg):
    _legacy_partners_table(pg)
    first = P.ensure_partner_schema(pg)
    second = P.ensure_partner_schema(pg)
    assert first["legacy_seat_cap_column"] and second["legacy_seat_cap_column"]                    # column retained, run twice, no error
    assert str(P.LEGACY_SEAT_CAP_DEFAULT) in _cap_default(pg)
    with pg.begin() as c:                                                                         # what the NEW code inserts (no seat_cap)
        c.execute(text("INSERT INTO partners (name, slug, brand_name, is_active) VALUES ('New', 'new', 'New', true)"))
        # what the OLD code does: reads seat_cap and compares it with a seat count -> must not be NULL
        caps = dict(c.execute(text("SELECT slug, seat_cap FROM partners")).all())
    assert caps["old"] == 5 and caps["new"] == P.LEGACY_SEAT_CAP_DEFAULT                          # existing value untouched; new row never NULL


@needs_pg
def test_phase2_contract_is_explicit_dry_run_first_and_repeatable(pg):
    _legacy_partners_table(pg)
    P.ensure_partner_schema(pg)
    dry = P.contract_seat_cap(pg)
    assert dry["column_present"] and not dry["dropped"] and _cap_default(pg) is not None          # dry run changes nothing
    done = P.contract_seat_cap(pg, execute=True)
    assert done["dropped"]
    with pg.connect() as c:
        assert not c.execute(text("SELECT 1 FROM information_schema.columns WHERE table_name='partners' AND column_name='seat_cap'")).first()
        assert c.execute(text("SELECT count(*) FROM partners")).scalar() == 1                     # data intact
    again = P.contract_seat_cap(pg, execute=True)                                                 # re-run is a no-op
    assert not again["column_present"] and not again["dropped"]
    P.ensure_partner_schema(pg)                                                                   # phase 1 still fine after phase 2


@needs_pg
def test_phase2_refuses_when_phase1_incomplete_or_lock_is_held(pg):
    with pytest.raises(P.PartnerMigrationError, match="incomplete"):
        P.contract_seat_cap(pg, execute=True)                                                     # nothing migrated yet
    _legacy_partners_table(pg)
    P.ensure_partner_schema(pg)
    holder = pg.connect()
    try:
        assert holder.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": P.SCHEMA_LOCK_KEY}).scalar()
        with pytest.raises(P.PartnerMigrationError, match="lock"):
            P.contract_seat_cap(pg, execute=True)
    finally:
        holder.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": P.SCHEMA_LOCK_KEY}); holder.close()
    assert P.contract_seat_cap(pg, execute=True)["dropped"]


@needs_pg
def test_real_advisory_lock_contention_only_the_holder_migrates(pg):
    holder = pg.connect()
    try:
        assert holder.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": P.SCHEMA_LOCK_KEY}).scalar()
        gate = _fresh_gate()
        P.startup_partner_migration(pg, gate=gate, start_retry_thread=False)
        assert gate.state == "pending"
        with pg.connect() as c:                                                                   # the waiter created nothing
            assert not c.execute(text("SELECT 1 FROM information_schema.tables WHERE table_name='partners'")).first()
    finally:
        holder.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": P.SCHEMA_LOCK_KEY}); holder.close()
    P.startup_partner_migration(pg, gate=gate, start_retry_thread=False)                          # lock is free: this instance now migrates
    assert gate.ready
    probe = pg.connect()
    try:                                                                                          # and released the lock afterwards
        assert probe.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": P.SCHEMA_LOCK_KEY}).scalar()
    finally:
        probe.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": P.SCHEMA_LOCK_KEY}); probe.close()


@needs_pg
def test_waiter_becomes_ready_when_the_holder_finishes(pg):
    holder = pg.connect()
    gate = _fresh_gate()
    try:
        assert holder.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": P.SCHEMA_LOCK_KEY}).scalar()
        P._migrate_under_lock(pg, gate)
        assert gate.state == "pending"
        P.ensure_partner_schema(pg)                                                               # the holder completes its migration
        P._migrate_under_lock(pg, gate)
        assert gate.ready                                                                         # waiter noticed, never migrated itself
    finally:
        holder.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": P.SCHEMA_LOCK_KEY}); holder.close()


@needs_pg
def test_drop_script_cli_requires_confirmation_and_dry_runs_by_default(pg):
    _legacy_partners_table(pg)
    P.ensure_partner_schema(pg)
    env = {**os.environ, "DATABASE_URL": PG_URL}
    script = os.path.join(ROOT, "scripts", "partner_drop_seat_cap.py")
    refused = subprocess.run([sys.executable, script, "--execute"], env=env, capture_output=True, text=True, cwd=ROOT)
    assert refused.returncode == 2 and "confirm-no-old-instances" in refused.stderr
    dry = subprocess.run([sys.executable, script], env=env, capture_output=True, text=True, cwd=ROOT)
    assert dry.returncode == 0 and '"column_present": true' in dry.stdout and _cap_default(pg) is not None
    run = subprocess.run([sys.executable, script, "--execute", "--confirm-no-old-instances"], env=env, capture_output=True, text=True, cwd=ROOT)
    assert run.returncode == 0 and '"dropped": true' in run.stdout
