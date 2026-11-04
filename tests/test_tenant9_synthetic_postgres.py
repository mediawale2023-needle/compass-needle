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
# A mark (not a module-level skip): the file stays collectable so scripts/run_backend_tests.sh sees a
# skip with exit code 0 instead of "no tests collected" (exit 5).
pytestmark = pytest.mark.skipif(not PG_URL.startswith("postgresql"), reason="NEEDLE_PG_TEST_URL not set to a PostgreSQL URL")

os.environ["DATABASE_URL"] = PG_URL if PG_URL.startswith("postgresql") else os.environ.get("DATABASE_URL", "sqlite:///./test_tenant9_synthetic_postgres_unused.db")
os.environ.setdefault("ENV", "test")
os.environ.setdefault("JWT_SECRET", "test-secret-key-32-characters-minimum-ok")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-testing")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text

import sansadx_backend.db as dbmod
from modules.synthetic_cases import sql_is_live, sql_is_synthetic
from scripts import tenant9_delhi_synthetic_cases as seed

pg_engine = create_engine(PG_URL) if PG_URL.startswith("postgresql") else None
MANIFEST = seed.load_manifest()
TABLES = ["case_activity_log", "govt_submission_log", "cases", "govt_portals", "tenant_overrides", "tenant_profiles", "contacts", "tenants"]


@pytest.fixture(autouse=True)
def database(monkeypatch):
    dbmod.Base.metadata.create_all(pg_engine)
    with pg_engine.begin() as conn:
        conn.execute(text("TRUNCATE " + ", ".join(TABLES) + " RESTART IDENTITY CASCADE"))  # disposable DB; CASCADE also clears other suites' leftovers
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
    with pg_engine.begin() as conn:  # leave the disposable database empty for whatever runs next
        conn.execute(text("TRUNCATE " + ", ".join(TABLES) + " RESTART IDENTITY CASCADE"))


def _count(sql, **params):
    with pg_engine.connect() as conn:
        return conn.execute(text(sql), params).scalar_one()


def _insert_genuine_case(tenant_id, ref):
    with pg_engine.begin() as conn:
        conn.execute(text("INSERT INTO cases (tenant_id, user_phone, raw_message, status, case_ref, case_metadata, is_deleted) "
                          "VALUES (:t, '919800000001', 'Genuine complaint', 'new', :r, CAST('{}' AS JSONB), false)"),
                     {"t": tenant_id, "r": ref})


def _delhi_portal_id():
    from sqlalchemy.orm import Session
    with Session(pg_engine) as session:  # the ORM applies the model's NOT NULL defaults
        portal = dbmod.GovtPortal(state="Delhi", portal_name="Delhi CM Jan Sunwai", base_url="https://example.invalid/", active=False)
        session.add(portal)
        session.commit()
        return portal.id


def _simulate_worksheet_testing(portal_id, ref="SYN-T9-DL-003", log_action="ai_translated", activity_action="govt_delhi_worksheet_drafted"):
    """What POST .../govt/delhi/prepare-worksheet writes on a case."""
    with pg_engine.begin() as conn:
        conn.execute(text("UPDATE cases SET govt_portal_id = :p, govt_status = 'pending_staff_submit' WHERE case_ref = :r"), {"p": portal_id, "r": ref})
        cid = conn.execute(text("SELECT id FROM cases WHERE case_ref = :r"), {"r": ref}).scalar_one()
        conn.execute(text("INSERT INTO govt_submission_log (tenant_id, case_id, action, actor_username, payload, created_at) VALUES (9, :c, :a, 'staff', CAST('{}' AS JSON), now())"), {"c": cid, "a": log_action})
        conn.execute(text("INSERT INTO case_activity_log (tenant_id, case_id, username, action, created_at) VALUES (9, :c, 'staff', :a, now())"), {"c": cid, "a": activity_action})
    return cid


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


# ---- review hardening: redaction, read-only dry run, geography master, worksheet-aware rollback ----

def test_dry_run_output_is_redacted_for_public_ci_logs(capsys):
    code, out, err = _run("--dry-run", capsys=capsys)
    assert code == 0, err
    report = json.loads(out)
    assert report["status"] == "OK" and report["would_insert"] == 20 and report["environment"] == "test"
    for forbidden in ("Bansuri", "needle_t9", "New Delhi/", "mp:", "synthetic:"):
        assert forbidden not in out, forbidden


def test_dry_run_runs_in_a_read_only_transaction(capsys, monkeypatch):
    from sqlalchemy.exc import InternalError
    real = seed.run_preflight

    def preflight_then_try_to_write(conn, manifest):
        result = real(conn, manifest)
        with pytest.raises(InternalError):  # ReadOnlySqlTransaction
            conn.execute(text("INSERT INTO tenants (id, name) VALUES (99, 'x')"))
        return result

    monkeypatch.setattr(seed, "run_preflight", preflight_then_try_to_write)
    code, _out, err = _run("--dry-run", capsys=capsys)
    assert code == 0, err
    assert _count("SELECT COUNT(*) FROM tenants WHERE id = 99") == 0


def test_geography_rows_are_matched_by_seat_not_tenant_like_the_app(capsys):
    with pg_engine.begin() as conn:  # shared seat geography owned by another tenant / by nobody
        conn.execute(text("UPDATE tenant_overrides SET tenant_id = 10 WHERE key LIKE 'mp:New Delhi/%' AND key LIKE '%Karol Bagh'"))
        conn.execute(text("UPDATE tenant_overrides SET tenant_id = NULL WHERE key LIKE 'mp:New Delhi/%' AND key LIKE '%Moti Nagar'"))
    assert _run("--dry-run", capsys=capsys)[0] == 0


def test_non_list_geography_payload_cannot_verify_a_locality(capsys):
    with pg_engine.begin() as conn:
        conn.execute(text("UPDATE tenant_overrides SET value = :v WHERE key = 'mp:New Delhi/Malviya Nagar'"), {"v": json.dumps({"locality": "Malviya Nagar"})})
    code, _out, err = _run("--dry-run", capsys=capsys)
    assert code == 2 and "Malviya Nagar" in err


def test_unsupported_case_metadata_column_type_blocks(capsys):
    with pg_engine.begin() as conn:
        conn.execute(text("ALTER TABLE cases ALTER COLUMN case_metadata TYPE text USING case_metadata::text"))
    try:
        code, _out, err = _run("--dry-run", capsys=capsys)
    finally:
        with pg_engine.begin() as conn:
            conn.execute(text("ALTER TABLE cases ALTER COLUMN case_metadata TYPE json USING case_metadata::json"))
    assert code == 2 and "expected json/jsonb" in err


def test_seeded_cases_are_geography_locked_so_reads_cannot_rewrite_the_assembly(capsys):
    assert _run("--execute", capsys=capsys)[0] == 0
    with pg_engine.connect() as conn:
        metas = [r[0] for r in conn.execute(text("SELECT case_metadata FROM cases WHERE case_ref LIKE 'SYN-T9-DL-%'")).all()]
    assert len(metas) == 20 and all(m["geography_locked"] is True for m in metas)


def test_rollback_is_strict_by_default_when_worksheet_testing_happened(capsys):
    assert _run("--execute", capsys=capsys)[0] == 0
    _simulate_worksheet_testing(_delhi_portal_id())
    code, _out, err = _run("--rollback", capsys=capsys)
    assert code == 2 and "rollback aborted" in err
    assert _count("SELECT COUNT(*) FROM cases WHERE case_ref LIKE 'SYN-T9-DL-%'") == 20


def test_rollback_can_remove_exactly_the_worksheet_artifacts_when_allowed(capsys):
    _insert_genuine_case(9, "GENUINE-1")
    with pg_engine.begin() as conn:
        conn.execute(text("INSERT INTO case_activity_log (tenant_id, case_id, username, action, created_at) "
                          "SELECT 9, id, 'staff', 'govt_delhi_worksheet_drafted', now() FROM cases WHERE case_ref = 'GENUINE-1'"))
    assert _run("--execute", capsys=capsys)[0] == 0
    portal_id = _delhi_portal_id()
    _simulate_worksheet_testing(portal_id, "SYN-T9-DL-003")
    _simulate_worksheet_testing(portal_id, "SYN-T9-DL-004", "delhi_ai_suggested", "govt_delhi_filing_saved")
    code, out, err = _run("--rollback", "--allow-worksheet-artifacts", capsys=capsys)
    assert code == 0, err
    assert json.loads(out)["removed_worksheet_artifacts"] == {"case_activity_log": 2, "govt_submission_log": 2}
    assert _count("SELECT COUNT(*) FROM cases WHERE case_ref LIKE 'SYN-T9-DL-%'") == 0
    assert _count("SELECT COUNT(*) FROM cases WHERE case_ref = 'GENUINE-1'") == 1
    assert _count("SELECT COUNT(*) FROM case_activity_log") == 1  # the genuine case's row survived


@pytest.mark.parametrize("tamper", [
    "INSERT INTO case_activity_log (tenant_id, case_id, username, action, created_at) SELECT 9, id, 'staff', 'status_changed', now() FROM cases WHERE case_ref = 'SYN-T9-DL-003'",
    "INSERT INTO govt_submission_log (tenant_id, case_id, action, actor_username, payload, created_at) SELECT 9, id, 'staff_submitted', 'staff', CAST('{}' AS JSON), now() FROM cases WHERE case_ref = 'SYN-T9-DL-003'",
    "UPDATE cases SET govt_reference_number = '1234' WHERE case_ref = 'SYN-T9-DL-003'",
    "UPDATE cases SET govt_status = 'submitted' WHERE case_ref = 'SYN-T9-DL-003'",
    "UPDATE cases SET govt_last_forwarded_to_citizen_at = now() WHERE case_ref = 'SYN-T9-DL-003'",
])
def test_artifact_flag_never_excuses_genuine_activity(capsys, tamper):
    assert _run("--execute", capsys=capsys)[0] == 0
    _simulate_worksheet_testing(_delhi_portal_id(), "SYN-T9-DL-004")
    with pg_engine.begin() as conn:
        conn.execute(text(tamper))
    activity_before = _count("SELECT COUNT(*) FROM case_activity_log")
    logs_before = _count("SELECT COUNT(*) FROM govt_submission_log")
    code, _out, err = _run("--rollback", "--allow-worksheet-artifacts", capsys=capsys)
    assert code == 2 and "rollback aborted" in err
    assert _count("SELECT COUNT(*) FROM cases WHERE case_ref LIKE 'SYN-T9-DL-%'") == 20
    # nothing was deleted, not even the removable worksheet rows (single all-or-nothing transaction)
    assert _count("SELECT COUNT(*) FROM case_activity_log") == activity_before
    assert _count("SELECT COUNT(*) FROM govt_submission_log") == logs_before


def test_rollback_aborts_on_rows_in_any_other_table_that_references_the_cases(capsys):
    assert _run("--execute", capsys=capsys)[0] == 0
    with pg_engine.begin() as conn:
        conn.execute(text("CREATE TABLE t9_extra_dependency (case_id integer REFERENCES cases(id))"))
        conn.execute(text("INSERT INTO t9_extra_dependency SELECT id FROM cases WHERE case_ref = 'SYN-T9-DL-001'"))
    try:
        code, _out, err = _run("--rollback", "--allow-worksheet-artifacts", capsys=capsys)
    finally:
        with pg_engine.begin() as conn:
            conn.execute(text("DROP TABLE t9_extra_dependency"))
    assert code == 2 and "t9_extra_dependency=1" in err
    assert _count("SELECT COUNT(*) FROM cases WHERE case_ref LIKE 'SYN-T9-DL-%'") == 20
