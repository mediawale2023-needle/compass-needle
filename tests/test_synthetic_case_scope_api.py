"""Live / Test / All data scope, tenant isolation, analytics exclusion and
server-side action blocking for synthetic cases, exercised through the real API."""
import csv
import inspect
import io
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from tests.auth_token_claims import identity_claims

TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
TEST_DB_URL = "sqlite:///./test_synthetic_case_scope_api.db"

os.environ["JWT_SECRET"] = TEST_JWT_SECRET
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["ENV"] = "test"
os.environ["OPENAI_API_KEY"] = "sk-test-fake-key-for-testing"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@event.listens_for(Engine, "connect")
def _sqlite_register_pg_lock_functions(dbapi_connection, connection_record):
    try:
        dbapi_connection.create_function("pg_try_advisory_lock", 1, lambda _key: 1)
        dbapi_connection.create_function("pg_advisory_unlock", 1, lambda _key: 1)
        dbapi_connection.create_function("pg_try_advisory_xact_lock", 1, lambda _key: 1)
    except Exception:
        pass


import admin_api
import api_router
import core.db_helpers as db_helpers
import main
import sansadx_backend.db as dbmod
from sansadx_backend.db import Base, hash_password

test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False)
client = TestClient(main.app, raise_server_exceptions=False)


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


LIVE_A, SYN_A, LEGACY_A, LOOKALIKE_A, SYN_B, LIVE_B = 201, 202, 203, 204, 301, 302


@pytest.fixture(autouse=True)
def seeded():
    dbmod.engine = test_engine
    dbmod.SessionLocal = TestSession
    db_helpers.engine = test_engine
    main.engine = test_engine
    api_router.engine = test_engine
    api_router.JWT_SECRET = TEST_JWT_SECRET
    Base.metadata.create_all(bind=test_engine)
    now = _utcnow()
    with test_engine.begin() as conn:
        for table in ("case_activity_log", "govt_submission_log", "cases", "token_blocklist", "users", "tenant_profiles", "tenants"):
            conn.execute(text(f"DELETE FROM {table}"))  # nosec B608
        conn.execute(text("INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active, created_at) "
                          "VALUES (1, 'A MP', 'New Delhi', '+919000000001', 'Pro', 1, :n), (2, 'B MP', 'Mumbai North', '+919000000002', 'Pro', 1, :n)"), {"n": now})
        for username, tid in (("mp_a", 1), ("mp_b", 2)):
            conn.execute(text("INSERT INTO users (tenant_id, username, password_hash, role, constituency, house, display_name, is_active) "
                              "VALUES (:t, :u, :p, 'mp', 'x', 'Lok Sabha', :u, true)"), {"t": tid, "u": username, "p": hash_password("ValidPass1!")})
        rows = [
            (LIVE_A, 1, "919810000201", "Genuine water complaint", {}),
            (SYN_A, 1, "synthetic:test:tenant9:001", "Synthetic waste complaint", {"synthetic_test_data": True}),
            (LEGACY_A, 1, "919900010001", "Legacy mock complaint", {"mock_seed": True}),
            (LOOKALIKE_A, 1, "919810000204", "SYNTHETIC TEST DATA looking wording", {"title": "TEST", "synthetic_test_data": False}),
            (SYN_B, 2, "synthetic:test:tenant9:002", "Other tenant synthetic", {"synthetic_test_data": True}),
            (LIVE_B, 2, "919810000302", "Other tenant genuine", {}),
        ]
        for i, (cid, tid, phone, msg, meta) in enumerate(rows):
            conn.execute(text("INSERT INTO cases (id, tenant_id, user_phone, raw_message, category, status, case_ref, case_metadata, is_deleted, is_critical, created_at, updated_at) "
                              "VALUES (:id, :t, :p, :m, 'Infrastructure & Utilities', 'new', :ref, :meta, false, false, :c, :c)"),
                         {"id": cid, "t": tid, "p": phone, "m": msg, "ref": f"REF-{cid}", "meta": json.dumps(meta), "c": now - timedelta(minutes=i)})
    yield


def _headers(username="mp_a"):
    token = jwt.encode({"sub": username, **identity_claims(test_engine, username),
                        "exp": _utcnow() + timedelta(hours=8), "iat": _utcnow().timestamp()}, TEST_JWT_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def _ids(response):
    assert response.status_code == 200, response.text
    return {item["id"] for item in response.json()["cases"]}


def test_default_scope_is_live_and_hides_all_synthetic_provenance():
    assert _ids(client.get("/api/cases", headers=_headers())) == {LIVE_A, LOOKALIKE_A}


def test_test_scope_shows_new_and_legacy_synthetic_only_for_own_tenant():
    assert _ids(client.get("/api/cases?data_scope=test", headers=_headers())) == {SYN_A, LEGACY_A}
    assert _ids(client.get("/api/cases?data_scope=test", headers=_headers("mp_b"))) == {SYN_B}


def test_all_scope_shows_both_but_never_another_tenant():
    assert _ids(client.get("/api/cases?data_scope=all", headers=_headers())) == {LIVE_A, SYN_A, LEGACY_A, LOOKALIKE_A}


def test_invalid_scope_is_rejected():
    assert client.get("/api/cases?data_scope=everything", headers=_headers()).status_code == 422


def test_search_and_category_filters_still_work_inside_a_scope():
    assert _ids(client.get("/api/cases?data_scope=test&search=waste", headers=_headers())) == {SYN_A}
    assert _ids(client.get("/api/cases?data_scope=all&search=genuine", headers=_headers())) == {LIVE_A}
    assert _ids(client.get("/api/cases?data_scope=test&category=Infrastructure%20%26%20Utilities", headers=_headers())) == {SYN_A, LEGACY_A}


def test_list_and_detail_carry_the_synthetic_designation():
    listing = client.get("/api/cases?data_scope=all", headers=_headers()).json()["cases"]
    flags = {c["id"]: c["is_synthetic_test_data"] for c in listing}
    assert flags == {LIVE_A: False, SYN_A: True, LEGACY_A: True, LOOKALIKE_A: False}
    assert client.get(f"/api/cases/{SYN_A}", headers=_headers()).json()["is_synthetic_test_data"] is True
    assert client.get(f"/api/cases/{LIVE_A}", headers=_headers()).json()["is_synthetic_test_data"] is False


def test_other_tenants_synthetic_case_is_not_reachable():
    assert client.get(f"/api/cases/{SYN_B}", headers=_headers()).status_code == 404


def test_dashboard_summary_counts_only_live_cases():
    body = client.get("/api/dashboard/summary", headers=_headers()).json()
    assert body["total_cases"] == 2 if "total_cases" in body else sum(body["status_breakdown"].values()) == 2


def test_export_defaults_to_live_and_can_target_test_cases():
    def refs(url):
        response = client.get(url, headers=_headers())
        assert response.status_code == 200, response.text
        return {row["case_ref"] for row in csv.DictReader(io.StringIO(response.text))}
    assert refs("/api/cases/export") == {f"REF-{LIVE_A}", f"REF-{LOOKALIKE_A}"}
    assert refs("/api/cases/export?data_scope=test") == {f"REF-{SYN_A}", f"REF-{LEGACY_A}"}


@pytest.mark.parametrize("method,path,payload", [
    ("post", "/api/cases/{id}/notify", None),
    ("post", "/api/cases/{id}/notify/send", {"message": "hello"}),
    ("post", "/api/cases/{id}/govt/submit", {"reference_number": "123"}),
    ("post", "/api/cases/{id}/govt/manual-reference", {"reference_number": "123"}),
    ("post", "/api/cases/{id}/govt/poll", None),
    ("post", "/api/cases/{id}/govt/translate", None),
])
@pytest.mark.parametrize("case_id", [SYN_A, LEGACY_A])
def test_external_actions_on_synthetic_cases_are_blocked_server_side(method, path, payload, case_id, monkeypatch):
    def forbid(*_a, **_k):
        raise AssertionError("external transport reached for a synthetic case")
    import modules.whatsapp as wa
    monkeypatch.setattr(wa, "send_whatsapp_message", forbid)
    response = getattr(client, method)(path.format(id=case_id), headers=_headers(), **({"json": payload} if payload is not None else {}))
    assert response.status_code == 409, (path, response.status_code, response.text)
    with test_engine.connect() as conn:
        assert conn.execute(text("SELECT govt_reference_number FROM cases WHERE id = :i"), {"i": case_id}).scalar() in (None, "")
        assert conn.execute(text("SELECT COUNT(*) FROM govt_submission_log")).scalar() == 0


def test_genuine_case_is_not_blocked_by_the_synthetic_guard():
    response = client.post(f"/api/cases/{LIVE_A}/govt/submit", json={"reference_number": "123"}, headers=_headers())
    assert response.status_code != 409 or "Synthetic" not in response.text


@pytest.mark.parametrize("module,names", [
    (admin_api, ["case_health", "case_analytics", "case_aggregates", "case_explorer", "tenant_health", "usage_analytics", "mp_detail", "get_alerts"]),
    (api_router, ["dashboard_summary", "dashboard_overview", "get_summary", "get_live_gaps", "_get_velocity", "get_report_card", "export_cases", "download_grievance_report"]),
])
def test_reporting_entry_points_apply_the_central_scope_predicate(module, names):
    for name in names:
        source = inspect.getsource(getattr(module, name))
        assert "sql_is_live" in source or "append_data_scope_condition" in source, f"{module.__name__}.{name} does not exclude synthetic cases"
