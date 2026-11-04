"""
tests/test_govt_manual_reference_delhi.py — POST /api/cases/{id}/govt/manual-reference

Staff-assisted reference capture for the staged (inactive, empty-taxonomy)
Delhi CM Jan Sunwai portal. Pins that the bypass is Delhi-only, server-resolved
from the tenant, tenant/case isolated, duplicate/idempotency-safe, leaves
govt_department NULL, and never touches AI / network / browser / status checks.
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import jwt
from tests.auth_token_claims import identity_claims
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
TEST_DB_URL = "sqlite:///./test_govt_manual_reference_delhi.db"
os.environ["JWT_SECRET"] = TEST_JWT_SECRET
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["ENV"] = "test"
os.environ["OPENAI_API_KEY"] = "sk-test-fake-key-for-testing"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@event.listens_for(Engine, "connect")
def _sqlite_pg_fns(dbapi_connection, connection_record):
    try:
        dbapi_connection.create_function("pg_try_advisory_lock", 1, lambda _k: 1)
        dbapi_connection.create_function("pg_advisory_unlock", 1, lambda _k: 1)
        dbapi_connection.create_function("pg_try_advisory_xact_lock", 1, lambda _k: 1)
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

DELHI_PID, OTHER_EMPTY_PID, KA_PID = 1, 2, 3
URL = "/api/cases/{}/govt/manual-reference"


def _headers(username):
    token = jwt.encode({"sub": username, **identity_claims(test_engine, username), "exp": _utcnow() + timedelta(hours=8), "iat": _utcnow().timestamp()},
                       TEST_JWT_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def _case(conn, cid, tid, *, portal=None, status="not_forwarded", ref=None, needle="new", dept=None):
    conn.execute(
        text("INSERT INTO cases (id, tenant_id, user_phone, raw_message, category, status, created_at, "
             "govt_portal_id, govt_status, govt_reference_number, govt_department, is_deleted) "
             "VALUES (:id, :t, '+919111111111', 'msg', 'Health', :ns, :now, :p, :gs, :ref, :d, 0)"),
        {"id": cid, "t": tid, "ns": needle, "now": _utcnow(), "p": portal, "gs": status, "ref": ref, "d": dept},
    )


@pytest.fixture(autouse=True)
def seeded():
    dbmod.engine = test_engine
    dbmod.SessionLocal = TestSession
    for m in (db_helpers, main, api_router, admin_api):
        m.engine = test_engine
    api_router.JWT_SECRET = admin_api.JWT_SECRET = TEST_JWT_SECRET
    Base.metadata.create_all(bind=test_engine)
    now = _utcnow()
    with test_engine.begin() as conn:
        for t in ("govt_submission_log", "case_activity_log", "cases", "govt_portals",
                  "token_blocklist", "users", "tenant_profiles", "tenants"):
            conn.execute(text(f"DELETE FROM {t}"))  # nosec B608
        # tenant 1,2 = Delhi; 3 = Karnataka (taxonomy); 4 = Haryana (empty taxonomy, NOT allowlisted)
        for tid, state, user in ((1, "Delhi", "mp_a"), (2, "Delhi", "mp_b"),
                                 (3, "Karnataka", "mp_ka"), (4, "Haryana", "mp_hr")):
            conn.execute(text("INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active, created_at) "
                              "VALUES (:i, :n, 'X', :w, 'Pro', 1, :now)"),
                         {"i": tid, "n": f"T{tid}", "w": f"+9190000000{tid:02d}", "now": now})
            conn.execute(text("INSERT INTO tenant_profiles (tenant_id, mp_name, constituency, state, house, created_at) "
                              "VALUES (:i, 'MP', 'X', :s, 'Lok Sabha', :now)"), {"i": tid, "s": state, "now": now})
            conn.execute(text("INSERT INTO users (tenant_id, username, password_hash, role, constituency, house, display_name, is_active) "
                              "VALUES (:i, :u, :pw, 'mp', 'X', 'Lok Sabha', 'MP', 1)"),
                         {"i": tid, "u": user, "pw": hash_password("Password1")})
        for pid, state, name, tax, active in (
            (DELHI_PID, "Delhi", "Delhi CM Jan Sunwai", {}, 0),
            (OTHER_EMPTY_PID, "Haryana", "Haryana CM Window", {}, 1),
            (KA_PID, "Karnataka", "Karnataka Janaspandana (iPGRS)", {"Water": "BBMP"}, 1),
        ):
            conn.execute(text("INSERT INTO govt_portals (id, state, portal_name, portal_type, base_url, status_check_mode, "
                              "department_taxonomy, field_schema, otp_bound, active, is_primary, verification_status, live_session_supported) "
                              "VALUES (:id, :s, :n, 'state_branded', 'https://example.gov.in/', 'login_required', :t, '{}', 1, :a, 1, 'verify', 1)"),
                         {"id": pid, "s": state, "n": name, "t": json.dumps(tax), "a": active})
        _case(conn, 100, 1)                                              # fresh Delhi case
        _case(conn, 101, 1, portal=DELHI_PID, status="pending_staff_submit")
        _case(conn, 102, 1, portal=DELHI_PID, status="submitted", ref="20260000001", needle="in_progress")
        _case(conn, 103, 2)                                              # other Delhi tenant's case
        _case(conn, 104, 3)
        _case(conn, 105, 4)
        _case(conn, 106, 1, needle="resolved")
        _case(conn, 107, 1, portal=KA_PID, status="pending_staff_submit")  # linked elsewhere
        _case(conn, 108, 1, status="under_review")                        # filed, ref cleared
    yield


@pytest.fixture(autouse=True)
def exception_enabled(monkeypatch):
    monkeypatch.setenv("GOVT_DELHI_MANUAL_REFERENCE_ENABLED", "true")


@pytest.fixture(autouse=True)
def no_external_calls():
    """Any AI / HTTP / browser / status-check call fails the test."""
    def boom(*a, **k):
        raise AssertionError("external call attempted")
    import requests
    import modules.govt_sync.translator as tr
    import modules.govt_sync.browser_session as bs
    with patch.object(requests, "get", boom), patch.object(requests, "post", boom), \
            patch.object(requests, "request", boom), patch.object(tr, "translate_for_portal", boom), \
            patch.object(bs, "start_session", boom), \
            patch.object(api_router, "_prepare_govt_worksheet", boom):
        yield


def _case_row(cid):
    with test_engine.connect() as c:
        return dict(c.execute(text("SELECT status, govt_portal_id, govt_department, govt_status, govt_reference_number "
                                   "FROM cases WHERE id = :i"), {"i": cid}).mappings().first())


def _post(cid, ref, user="mp_a", **extra):
    return client.post(URL.format(cid), json={"reference_number": ref, **extra}, headers=_headers(user))


def test_delhi_case_links_and_records_reference_without_department():
    r = _post(100, "  20260000008 ")
    assert r.status_code == 200, r.text
    assert r.json()["govt_reference_number"] == "20260000008"
    row = _case_row(100)
    assert row["govt_portal_id"] == DELHI_PID
    assert row["govt_department"] is None
    assert row["govt_status"] == "submitted"
    assert row["govt_reference_number"] == "20260000008"
    assert row["status"] == "in_progress"
    with test_engine.connect() as c:
        acts = [a[0] for a in c.execute(text("SELECT action FROM govt_submission_log WHERE case_id = 100"))]
    assert acts == ["staff_submitted"]


def test_pending_staff_submit_case_can_be_completed():
    assert _post(101, "20260000015").status_code == 200
    assert _case_row(101)["govt_status"] == "submitted"


def test_terminal_needle_status_is_not_demoted():
    assert _post(106, "20260000022").status_code == 200
    assert _case_row(106)["status"] == "resolved"


def test_empty_reference_rejected():
    assert _post(100, "   ").status_code == 400
    assert _case_row(100)["govt_portal_id"] is None


def test_forged_portal_id_in_body_is_ignored():
    r = _post(100, "20260000029", portal_id=KA_PID, govt_portal_id=KA_PID)
    assert r.status_code == 200
    assert _case_row(100)["govt_portal_id"] == DELHI_PID


def test_cross_tenant_case_is_404_and_untouched():
    r = _post(103, "20260000036", user="mp_a")
    assert r.status_code == 404
    assert _case_row(103)["govt_reference_number"] is None


def test_unauthenticated_rejected():
    assert client.post(URL.format(100), json={"reference_number": "X"}).status_code in (401, 403)


def test_empty_taxonomy_on_non_delhi_portal_stays_blocked():
    r = _post(105, "HR-1", user="mp_hr")      # Haryana: active, empty taxonomy
    assert r.status_code == 400
    assert _case_row(105)["govt_portal_id"] is None


def test_taxonomy_portal_tenant_cannot_use_bypass():
    r = _post(104, "KA-1", user="mp_ka")
    assert r.status_code == 400
    assert _case_row(104)["govt_reference_number"] is None


def test_delhi_portal_with_taxonomy_configured_leaves_the_bypass():
    with test_engine.begin() as c:
        c.execute(text("UPDATE govt_portals SET department_taxonomy = :t WHERE id = :i"),
                  {"t": json.dumps({"Health": "Health Dept"}), "i": DELHI_PID})
    assert _post(100, "20260000043").status_code == 400


def test_portal_not_activated_by_this_path():
    _post(100, "20260000050")
    with test_engine.connect() as c:
        r = c.execute(text("SELECT active, verification_status FROM govt_portals WHERE id = :i"), {"i": DELHI_PID}).first()
    assert not r[0] and r[1] == "verify"


def test_same_reference_is_idempotent():
    assert _post(100, "20260000057").status_code == 200
    again = _post(100, "20260000057")
    assert again.status_code == 200 and again.json()["idempotent"] is True
    with test_engine.connect() as c:
        n = c.execute(text("SELECT COUNT(*) FROM govt_submission_log WHERE case_id = 100")).scalar()
    assert n == 1


def test_conflicting_reference_is_409_and_preserved():
    assert _post(102, "20260000064").status_code == 409
    assert _case_row(102)["govt_reference_number"] == "20260000001"
    assert _post(102, "20260000001").json()["idempotent"] is True


def test_filed_without_reference_is_409():
    assert _post(108, "20260000071").status_code == 409
    assert _case_row(108)["govt_reference_number"] is None


def test_case_linked_to_another_portal_is_409_not_relinked():
    assert _post(107, "20260000078").status_code == 409
    assert _case_row(107)["govt_portal_id"] == KA_PID


def test_existing_submit_endpoint_behaviour_unchanged():
    # Unlinked case still can't use plain /govt/submit
    r = client.post("/api/cases/100/govt/submit", json={"reference_number": "X"}, headers=_headers("mp_a"))
    assert r.status_code == 400


# ─── Server-controlled eligibility switch ──────────────────────────────────

@pytest.mark.parametrize("value", [None, "", "false", "0", "yes"])
def test_default_deny_when_switch_unset_or_not_true(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("GOVT_DELHI_MANUAL_REFERENCE_ENABLED", raising=False)
    else:
        monkeypatch.setenv("GOVT_DELHI_MANUAL_REFERENCE_ENABLED", value)
    r = _post(100, "20260000085")
    assert r.status_code == 403
    row = _case_row(100)
    assert row["govt_portal_id"] is None and row["govt_reference_number"] is None


def test_request_body_cannot_enable_the_exception(monkeypatch):
    monkeypatch.delenv("GOVT_DELHI_MANUAL_REFERENCE_ENABLED", raising=False)
    r = _post(100, "20260000092", enabled=True, manual_reference_enabled=True, active=True)
    assert r.status_code == 403
    assert _case_row(100)["govt_reference_number"] is None


def test_switch_does_not_activate_portal_or_change_verification():
    _post(100, "20260000099")
    with test_engine.connect() as c:
        r = c.execute(text("SELECT active, verification_status FROM govt_portals WHERE id = :i"), {"i": DELHI_PID}).first()
    assert not r[0] and r[1] == "verify"


def test_switch_does_not_enable_other_govt_functionality():
    """With the switch on, every other govt endpoint still treats the inactive
    Delhi portal as unconfigured (falls back to CPGRAMS/none) and nothing external fires."""
    portal, _ = api_router._resolve_govt_portal_for_tenant(1)
    assert portal is None or portal["portal_name"] != "Delhi CM Jan Sunwai"
    for path in ("translate", "session/start", "poll", "status-check/start", "session/start-status-check"):
        r = client.post(f"/api/cases/100/govt/{path}", json={}, headers=_headers("mp_a"))
        assert r.status_code in (400, 403, 404, 405, 422), (path, r.status_code)
    assert _case_row(100)["govt_portal_id"] is None
    from modules.govt_sync.adapters import get_adapter
    from modules.govt_sync.adapters.manual import ManualAssistedAdapter
    assert type(get_adapter({"portal_type": "state_branded"})) is ManualAssistedAdapter


def test_switch_gates_only_the_manual_endpoint_other_portals_unaffected(monkeypatch):
    # Karnataka tenant's normal /govt/submit path doesn't read the switch.
    monkeypatch.delenv("GOVT_DELHI_MANUAL_REFERENCE_ENABLED", raising=False)
    with test_engine.begin() as c:
        _case(c, 110, 3, portal=KA_PID, status="pending_staff_submit")
    r = client.post("/api/cases/110/govt/submit", json={"reference_number": "KA-9"}, headers=_headers("mp_ka"))
    assert r.status_code == 200


# ─── Concurrency: identical simultaneous requests ──────────────────────────

def test_identical_concurrent_requests_write_once_and_loser_is_idempotent():
    """Controlled race harness. Both requests are forced (via a threading
    barrier on the pre-check case read) to observe the case as UNFILED before
    either reaches the guarded UPDATE, so exactly one can win the UPDATE and
    the other must take the rowcount==0 re-read path. SQLite serialises the
    two writers; this exercises the application's guard, not Postgres row
    locking (same guarded-UPDATE semantics there, not separately proven)."""
    import threading

    barrier = threading.Barrier(2, timeout=10)
    real_q_one = api_router._q_one
    precheck_reads = []

    def gated_q_one(sql, params=None, *a, **k):
        row = real_q_one(sql, params, *a, **k) if params is not None else real_q_one(sql, *a, **k)
        if "govt_portal_id, govt_reference_number, govt_status, status FROM cases" in sql:
            precheck_reads.append(dict(row) if row else None)
            barrier.wait()          # neither thread proceeds until both have read
        return row

    results = [None, None]

    def worker(i):
        results[i] = _post(100, "20260000106")

    with patch.object(api_router, "_q_one", gated_q_one):
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        assert not any(t.is_alive() for t in threads), "race harness deadlocked"

    # Both really saw the case unfiled before either wrote (the race was real).
    assert len(precheck_reads) == 2
    assert all(r["govt_reference_number"] in (None, "") and r["govt_portal_id"] is None for r in precheck_reads)

    assert [r.status_code for r in results] == [200, 200], [r.text for r in results]
    bodies = [r.json() for r in results]
    assert sorted(b.get("idempotent", False) for b in bodies) == [False, True]
    assert all(b["govt_reference_number"] == "20260000106" and b["govt_status"] == "submitted" for b in bodies)

    row = _case_row(100)
    assert row["govt_reference_number"] == "20260000106" and row["govt_portal_id"] == DELHI_PID
    assert row["govt_department"] is None
    with test_engine.connect() as c:
        log = [a[0] for a in c.execute(text("SELECT action FROM govt_submission_log WHERE case_id = 100"))]
        acts = c.execute(text("SELECT COUNT(*) FROM case_activity_log WHERE case_id = 100 AND action = 'govt_submitted'")).scalar()
    assert log == ["staff_submitted"]          # exactly one audit set
    assert acts == 1


# ─── /api/govt-portal capability flag ──────────────────────────────────────

def _portal_flag(user="mp_a", params=None):
    r = client.get("/api/govt-portal", params=params or {}, headers=_headers(user))
    assert r.status_code == 200, r.text
    return r.json()


def test_capability_true_only_for_eligible_delhi_tenant_with_switch_on():
    assert _portal_flag("mp_a")["manual_reference_enabled"] is True
    assert _portal_flag("mp_b")["manual_reference_enabled"] is True      # also a Delhi tenant
    for other in ("mp_ka", "mp_hr"):                                      # Karnataka (taxonomy), Haryana (empty, not allowlisted)
        assert _portal_flag(other)["manual_reference_enabled"] is False


@pytest.mark.parametrize("value", [None, "", "false", "0", "yes"])
def test_capability_false_when_switch_off(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("GOVT_DELHI_MANUAL_REFERENCE_ENABLED", raising=False)
    else:
        monkeypatch.setenv("GOVT_DELHI_MANUAL_REFERENCE_ENABLED", value)
    assert _portal_flag("mp_a")["manual_reference_enabled"] is False


def test_capability_false_once_delhi_portal_gains_a_taxonomy():
    with test_engine.begin() as c:
        c.execute(text("UPDATE govt_portals SET department_taxonomy = :t WHERE id = :i"),
                  {"t": json.dumps({"Health": "Health Dept"}), "i": DELHI_PID})
    assert _portal_flag("mp_a")["manual_reference_enabled"] is False


def test_capability_cannot_be_enabled_or_overridden_by_the_request(monkeypatch):
    monkeypatch.delenv("GOVT_DELHI_MANUAL_REFERENCE_ENABLED", raising=False)
    r = client.get("/api/govt-portal", params={"manual_reference_enabled": "true", "enabled": "1"},
                   headers={**_headers("mp_a"), "X-Manual-Reference-Enabled": "true"})
    assert r.json()["manual_reference_enabled"] is False


def test_capability_flag_leaks_no_configuration_and_does_not_activate_portal():
    r = client.get("/api/govt-portal", headers=_headers("mp_a"))
    assert "GOVT_DELHI_MANUAL_REFERENCE_ENABLED" not in r.text
    with test_engine.connect() as c:
        row = c.execute(text("SELECT active, verification_status FROM govt_portals WHERE id = :i"), {"i": DELHI_PID}).first()
    assert not row[0] and row[1] == "verify"
    # Existing resolution is untouched: an inactive Delhi row still isn't "the" portal.
    assert r.json()["portal"] is None or r.json()["portal"]["portal_name"] != "Delhi CM Jan Sunwai"
