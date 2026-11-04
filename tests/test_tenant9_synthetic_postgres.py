"""
tests/test_tenant9_synthetic_postgres.py - real-PostgreSQL verification of the
Tenant 9 synthetic-case lifecycle (scripts/tenant9_delhi_synthetic_cases.py) and of
the central live/test predicates.

Opt-in: runs only when NEEDLE_PG_TEST_URL points at a DISPOSABLE PostgreSQL
database (tables are created and emptied here). Never falls back to SQLite.

Run:  NEEDLE_PG_TEST_URL=postgresql://user@host/throwaway_db \
      python -m pytest tests/test_tenant9_synthetic_postgres.py
"""
import json
import os
import sys

import pytest

PG_URL = os.environ.get("NEEDLE_PG_TEST_URL", "")
if not PG_URL.startswith("postgresql"):
    pytest.skip("NEEDLE_PG_TEST_URL not set to a PostgreSQL URL", allow_module_level=True)

os.environ["DATABASE_URL"] = PG_URL
os.environ.setdefault("ENV", "test")
os.environ.setdefault("JWT_SECRET", "test-secret-key-32-characters-minimum-ok")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-testing")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text

import sansadx_backend.db as dbmod
from modules.synthetic_cases import sql_is_live, sql_is_synthetic
from scripts import tenant9_delhi_synthetic_cases as seed

pg_engine = create_engine(PG_URL)
MANIFEST = seed.load_manifest()
TABLES = ["case_activity_log", "govt_submission_log", "cases", "tenant_overrides", "tenant_profiles", "contacts", "tenants"]


@pytest.fixture(autouse=True)
def database(monkeypatch):
    dbmod.Base.metadata.create_all(pg_engine)
    with pg_engine.begin() as conn:
        for table in TABLES:
            conn.execute(text(f"DELETE FROM {table}"))
        conn.execute(text("INSERT INTO tenants (id, name, constituency, tenant_type, account_stage, seat_type, is_active) "
                          "VALUES (9, 'Bansuri Swaraj', 'New Delhi', 'mp', 'elected', 'mp', true), "
                          "(10, 'Other MP', 'Elsewhere', 'mp', 'elected', 'mp', true)"))
        conn.execute(text("INSERT INTO tenant_profiles (tenant_id, mp_name, constituency, state, house) "
                          "VALUES (9, 'Bansuri Swaraj', 'New Delhi', 'Delhi', 'Lok Sabha')"))
        for assembly in sorted(seed.EXPECTED_ASSEMBLIES):
            entries = [{"locality": item["locality"], "building_name": "x"}
                       for item in MANIFEST["cases"] if item["assembly"] == assembly]
            conn.execute(text("INSERT INTO tenant_overrides (tenant_id, override_type, key, value) "
                              "VALUES (9, 'geography_data', :k, :v)"),
                         {"k": f"mp:New Delhi/{assembly}", "v": json.dumps(entries)})
    monkeypatch.setattr(seed, "engine", pg_engine)
    monkeypatch.setenv("ENV", "test")
    yield


def _count(sql, **params):
    with pg_engine.connect() as conn:
        return conn.execute(text(sql), params).scalar_one()


def _insert_genuine_case(tenant_id, ref):
    with pg_engine.begin() as conn:
        conn.execute(text("INSERT INTO cases (tenant_id, user_phone, raw_message, status, case_ref, case_metadata, is_deleted) "
                          "VALUES (:t, '919800000001', 'Genuine complaint', 'new', :r, CAST('{}' AS JSONB), false)"),
                     {"t": tenant_id, "r": ref})


def _run(*argv, capsys):
    code = seed.main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_dry_run_passes_preflight_and_writes_nothing(capsys):
    before = _count("SELECT COUNT(*) FROM cases")
    code, out, err = _run("--dry-run", capsys=capsys)
    assert code == 0, err
    assert json.loads(out)["manifest_count"] == 20
    assert _count("SELECT COUNT(*) FROM cases") == before == 0


def test_execute_inserts_exactly_twenty_clean_rows(capsys):
    _insert_genuine_case(9, "GENUINE-1")
    code, out, err = _run("--execute", capsys=capsys)
    assert code == 0, err
    assert len(json.loads(out)["inserted_ids"]) == 20
    assert _count("SELECT COUNT(*) FROM cases WHERE tenant_id = 9 AND case_ref LIKE 'SYN-T9-DL-%'") == 20
    with pg_engine.connect() as conn:
        rows = conn.execute(text("SELECT status, govt_status, govt_reference_number, govt_portal_id, govt_department, "
                                 "resolved_at, user_phone, case_metadata FROM cases WHERE case_ref LIKE 'SYN-T9-DL-%'")).mappings().all()
    assert all(r["status"] == "new" and r["govt_status"] == "not_forwarded" for r in rows)
    assert all(r["govt_reference_number"] is None and r["govt_portal_id"] is None and r["govt_department"] is None and r["resolved_at"] is None for r in rows)
    assert all(r["user_phone"].startswith("synthetic:") for r in rows)
    assert all(r["case_metadata"]["synthetic_test_data"] is True and r["case_metadata"]["synthetic_batch_id"] == "tenant9-delhi-filing-v1" for r in rows)
    for table in ("case_activity_log", "govt_submission_log", "contacts"):
        assert _count(f"SELECT COUNT(*) FROM {table}") == 0, table


def test_live_and_test_predicates_split_the_data_set(capsys):
    _insert_genuine_case(9, "GENUINE-1")
    with pg_engine.begin() as conn:  # legacy provenance flags must be honoured too
        conn.execute(text("INSERT INTO cases (tenant_id, user_phone, raw_message, status, case_ref, case_metadata, is_deleted) VALUES "
                          "(9, '91900', 'legacy', 'new', 'LEG-1', CAST('{\"mock_seed\": true}' AS JSONB), false), "
                          "(9, '91901', 'legacy', 'new', 'LEG-2', CAST('{\"synthetic_seed\": true}' AS JSONB), false), "
                          "(9, '91902', 'SYN-T9-DL-001 synthetic test wording', 'new', 'SYN-T9-DL-FAKE', CAST('{}' AS JSONB), false)"))
    assert _run("--execute", capsys=capsys)[0] == 0
    assert _count(f"SELECT COUNT(*) FROM cases c WHERE c.tenant_id = 9 AND {sql_is_synthetic('c')}") == 22
    # genuine row and the look-alike (reference/wording only) stay live
    assert _count(f"SELECT COUNT(*) FROM cases c WHERE c.tenant_id = 9 AND {sql_is_live('c')}") == 2


def test_execute_is_atomic_when_a_late_insert_fails(capsys, monkeypatch):
    original = seed.execute

    def insert_then_fail(conn, manifest, preflight):
        original(conn, manifest, preflight)
        raise RuntimeError("simulated failure after all inserts")

    monkeypatch.setattr(seed, "execute", insert_then_fail)
    with pytest.raises(RuntimeError):
        seed.main(["--execute"])
    capsys.readouterr()
    assert _count("SELECT COUNT(*) FROM cases") == 0


def test_second_execute_is_blocked_by_batch_collision(capsys):
    assert _run("--execute", capsys=capsys)[0] == 0
    code, _out, err = _run("--execute", capsys=capsys)
    assert code == 2 and "collision" in err
    assert _count("SELECT COUNT(*) FROM cases WHERE case_ref LIKE 'SYN-T9-DL-%'") == 20


def test_wrong_tenant_identity_blocks_everything(capsys):
    with pg_engine.begin() as conn:
        conn.execute(text("UPDATE tenants SET name = 'Someone Else' WHERE id = 9"))
    code, _out, err = _run("--execute", capsys=capsys)
    assert code == 2 and "identity mismatch" in err
    assert _count("SELECT COUNT(*) FROM cases") == 0


def test_unverified_geography_blocks_execution(capsys):
    with pg_engine.begin() as conn:
        conn.execute(text("DELETE FROM tenant_overrides WHERE key = 'mp:New Delhi/Malviya Nagar'"))
    code, _out, err = _run("--execute", capsys=capsys)
    assert code == 2 and "geography" in err.lower()
    assert _count("SELECT COUNT(*) FROM cases") == 0


def test_production_requires_exact_confirmation(capsys, monkeypatch):
    monkeypatch.setenv("ENV", "production")
    code, _out, err = _run("--execute", capsys=capsys)
    assert code == 2 and "--confirm-production" in err
    assert _count("SELECT COUNT(*) FROM cases") == 0


def test_rollback_removes_only_the_batch(capsys):
    _insert_genuine_case(9, "GENUINE-1")
    _insert_genuine_case(10, "OTHER-1")
    assert _run("--execute", capsys=capsys)[0] == 0
    code, out, err = _run("--rollback", capsys=capsys)
    assert code == 0, err
    assert len(json.loads(out)["deleted_ids"]) == 20
    assert _count("SELECT COUNT(*) FROM cases") == 2
    assert _count("SELECT COUNT(*) FROM cases WHERE case_ref IN ('GENUINE-1', 'OTHER-1')") == 2


@pytest.mark.parametrize("tamper", [
    "UPDATE cases SET govt_reference_number = '1234' WHERE case_ref = 'SYN-T9-DL-003'",
    "UPDATE cases SET govt_status = 'submitted' WHERE case_ref = 'SYN-T9-DL-004'",
    "INSERT INTO case_activity_log (tenant_id, case_id, username, action) "
    "SELECT 9, id, 'staff', 'note' FROM cases WHERE case_ref = 'SYN-T9-DL-005'",
])
def test_rollback_aborts_when_a_case_acquired_real_activity(capsys, tamper):
    assert _run("--execute", capsys=capsys)[0] == 0
    with pg_engine.begin() as conn:
        conn.execute(text(tamper))
    code, _out, err = _run("--rollback", capsys=capsys)
    assert code == 2 and "rollback aborted" in err
    assert _count("SELECT COUNT(*) FROM cases WHERE case_ref LIKE 'SYN-T9-DL-%'") == 20


def test_whatsapp_transport_refuses_synthetic_contacts(monkeypatch):
    import modules.whatsapp as wa
    from modules.synthetic_cases import SyntheticCaseActionBlocked

    def no_network(*_a, **_k):
        raise AssertionError("network must not be reached")

    monkeypatch.setattr(wa.http_requests, "post", no_network)
    with pytest.raises(SyntheticCaseActionBlocked):
        wa.send_whatsapp_message("synthetic:test:tenant9:001", "hello", "123", tenant_id=9)
