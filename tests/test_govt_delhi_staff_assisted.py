"""
tests/test_govt_delhi_staff_assisted.py — Delhi CM Jan Sunwai staff-assisted integration.

What is (and is not) proven here: the portal needs a human CAPTCHA + OTP for every operation and its
post-OTP pages were never observed (DELHI_CM_JAN_SUNWAI_CAPABILITY_MAP.md), so these tests cover Needle's
OWN behaviour only — routing with no CPGRAMS fallback, AI drafting (Gemini mocked), the filing lifecycle,
duplicate/conflict protection, tenant isolation, audit events, poller exclusion. They are NOT evidence that
any Delhi portal response was read, and no test fabricates one. Any HTTP request to the portal fails the test.
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt
from tests.auth_token_claims import identity_claims
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
TEST_DB_URL = "sqlite:///./test_govt_delhi_staff_assisted.db"
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
from modules.govt_sync import delhi_portal
from modules.govt_sync import translator as translator_mod

test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False)
client = TestClient(main.app, raise_server_exceptions=False)

DELHI_PID, KA_PID, MH_PID, CPGRAMS_PID = 1, 2, 3, 4
DRAFT = {"department": None, "district": "New Delhi", "subdistrict_or_ulb": "W5", "subject": "Water supply failure in Ward 5",
         "description": "Residents of Ward 5 report no piped water for three days.", "priority_category": None,
         "department_note": "n/a", "limits_note": "soft"}
REF = "20260000123"
REF2 = "20260000999"


def _headers(username):
    token = jwt.encode({"sub": username, **identity_claims(test_engine, username), "exp": _utcnow() + timedelta(hours=8), "iat": _utcnow().timestamp()}, TEST_JWT_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def _case(conn, cid, tid, *, portal=None, status="not_forwarded", ref=None, deleted=False, ws=None):
    conn.execute(
        text("INSERT INTO cases (id, tenant_id, user_phone, raw_message, category, status, created_at, assembly, ward, "
             "govt_portal_id, govt_status, govt_reference_number, govt_submission_worksheet, is_deleted) "
             "VALUES (:id, :t, '+919111111111', 'SYNTHETIC: no water in ward 5', 'Infrastructure & Utilities', 'new', :now, 'New Delhi', 'W5', "
             ":p, :gs, :ref, :ws, :del)"),
        {"id": cid, "t": tid, "now": _utcnow(), "p": portal, "gs": status, "ref": ref, "ws": ws, "del": deleted},
    )


@pytest.fixture(autouse=True)
def seeded(monkeypatch):
    monkeypatch.setenv("GOVT_DELHI_MANUAL_REFERENCE_ENABLED", "true")
    dbmod.engine = test_engine
    dbmod.SessionLocal = TestSession
    for m in (db_helpers, main, api_router, admin_api):
        m.engine = test_engine
    api_router.JWT_SECRET = admin_api.JWT_SECRET = TEST_JWT_SECRET
    Base.metadata.create_all(bind=test_engine)
    now = _utcnow()
    with test_engine.begin() as conn:
        for t in ("govt_submission_log", "case_activity_log", "cases", "govt_portals", "token_blocklist", "users", "tenant_profiles", "tenants"):
            conn.execute(text(f"DELETE FROM {t}"))  # nosec B608
        for tid, state, user in ((1, "Delhi", "mp_a"), (2, "Delhi", "mp_b"), (3, "Karnataka", "mp_ka"), (4, "Maharashtra", "mp_mh")):
            conn.execute(text("INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active, created_at) "
                              "VALUES (:i, :n, 'X', :w, 'Pro', 1, :now)"), {"i": tid, "n": f"T{tid}", "w": f"+9190000000{tid:02d}", "now": now})
            conn.execute(text("INSERT INTO tenant_profiles (tenant_id, mp_name, constituency, state, house, created_at) "
                              "VALUES (:i, 'MP', 'X', :s, 'Lok Sabha', :now)"), {"i": tid, "s": state, "now": now})
            conn.execute(text("INSERT INTO users (tenant_id, username, password_hash, role, constituency, house, display_name, is_active) "
                              "VALUES (:i, :u, :pw, 'mp', 'X', 'Lok Sabha', 'MP', 1)"), {"i": tid, "u": user, "pw": hash_password("Password1")})
        for pid, state, name, ptype, tax, active, adapter in (
            (DELHI_PID, "Delhi", "Delhi CM Jan Sunwai", "state_branded", {}, 0, "delhi_staff_assisted"),
            (KA_PID, "Karnataka", "Karnataka Janaspandana (iPGRS)", "state_branded", {"Water": "BBMP"}, 1, None),
            (MH_PID, "Maharashtra", "Maharashtra Aaple Sarkar Grievance Redressal", "state_branded", {"Water": "PWD"}, 1, None),
            (CPGRAMS_PID, "All (fallback)", "CPGRAMS", "cpgrams", {"Water": "x"}, 1, None),
        ):
            conn.execute(text("INSERT INTO govt_portals (id, state, portal_name, portal_type, base_url, status_check_mode, department_taxonomy, "
                              "field_schema, otp_bound, active, is_primary, verification_status, live_session_supported, status_check_adapter) "
                              "VALUES (:id, :s, :n, :t, 'https://example.gov.in/', 'login_required', :tx, '{}', 1, :a, 1, 'verify', 1, :ad)"),
                         {"id": pid, "s": state, "n": name, "t": ptype, "tx": json.dumps(tax), "a": active, "ad": adapter})
        _case(conn, 100, 1)                                                   # fresh Delhi case
        _case(conn, 101, 1, portal=DELHI_PID, status="submitted", ref=REF)    # filed in Delhi
        _case(conn, 102, 2)                                                   # other Delhi tenant's case
        _case(conn, 103, 3)                                                   # Karnataka tenant's case
        _case(conn, 104, 1, portal=CPGRAMS_PID, status="pending_staff_submit")  # legacy: linked to CPGRAMS
        _case(conn, 105, 1, portal=DELHI_PID, status="pending_staff_submit")  # prepared in Delhi, not filed
        _case(conn, 106, 1, deleted=True)
    yield


@pytest.fixture(autouse=True)
def no_portal_traffic_and_no_real_ai():
    """Any HTTP request to a government portal fails the test; the real Gemini client must never be reached."""
    def boom(*a, **k):
        raise AssertionError("an HTTP request was attempted")
    import requests
    with patch.object(requests, "get", boom), patch.object(requests, "post", boom), patch.object(requests, "request", boom), \
            patch.object(translator_mod, "get_gemini_client", MagicMock(return_value=None)):
        yield


@pytest.fixture()
def ai():
    with patch.object(translator_mod, "translate_subject_description_only", return_value=dict(DRAFT)) as m:
        yield m


def _case_row(cid):
    with test_engine.connect() as c:
        return dict(c.execute(text("SELECT status, govt_portal_id, govt_department, govt_status, govt_reference_number, govt_submission_worksheet "
                                   "FROM cases WHERE id = :i"), {"i": cid}).mappings().first())


def _log(cid, action=None):
    with test_engine.connect() as c:
        rows = c.execute(text("SELECT action, payload FROM govt_submission_log WHERE case_id = :i ORDER BY id"), {"i": cid}).all()
    return [r for r in rows if action is None or r[0] == action]


def _prep(cid, user="mp_a"):
    return client.post(f"/api/cases/{cid}/govt/delhi/prepare-worksheet", headers=_headers(user))


def _task(cid, task, user="mp_a"):
    return client.post(f"/api/cases/{cid}/govt/delhi/task", json={"task": task}, headers=_headers(user))


def _record(cid, ref, user="mp_a"):
    return client.post(f"/api/cases/{cid}/govt/manual-reference", json={"reference_number": ref}, headers=_headers(user))


def _portal(user="mp_a"):
    r = client.get("/api/govt-portal", headers=_headers(user))
    assert r.status_code == 200, r.text
    return r.json()


# ─── Tenant / portal resolution: Delhi never falls back to CPGRAMS while the capability is on ───────────

def test_delhi_does_not_fall_back_to_cpgrams_when_enabled():
    portal, state = api_router._resolve_govt_portal_for_tenant(1)
    assert portal is None and state == "Delhi"


def test_delhi_legacy_cpgrams_fallback_is_unchanged_when_switch_off(monkeypatch):
    monkeypatch.delenv("GOVT_DELHI_MANUAL_REFERENCE_ENABLED", raising=False)
    portal, _ = api_router._resolve_govt_portal_for_tenant(1)
    assert portal["portal_name"] == "CPGRAMS"


@pytest.mark.parametrize("switch", ["true", None])
def test_karnataka_maharashtra_resolution_is_identical_with_switch_on_or_off(monkeypatch, switch):
    if switch is None:
        monkeypatch.delenv("GOVT_DELHI_MANUAL_REFERENCE_ENABLED", raising=False)
    assert api_router._resolve_govt_portal_for_tenant(3)[0]["portal_name"] == "Karnataka Janaspandana (iPGRS)"
    assert api_router._resolve_govt_portal_for_tenant(4)[0]["portal_name"] == "Maharashtra Aaple Sarkar Grievance Redressal"


def test_generic_filing_endpoints_refuse_a_delhi_tenant_and_never_call_ai(ai):
    with patch.object(translator_mod, "translate_for_portal", side_effect=AssertionError("generic translate must not run for Delhi")):
        assert client.post("/api/cases/100/govt/translate", headers=_headers("mp_a")).status_code == 400
        assert client.post("/api/cases/100/govt/session/start", json={}, headers=_headers("mp_a")).status_code == 400
    ai.assert_not_called()
    assert _case_row(100)["govt_portal_id"] is None


def test_govt_portal_exposes_verified_tasks_only_to_an_eligible_delhi_tenant():
    d = _portal("mp_a")
    assert d["state"] == "Delhi" and d["supported"] is False and d["manual_reference_enabled"] is True
    assert [t["key"] for t in d["staff_assisted_tasks"]] == ["file", "status", "reminder", "feedback"]
    assert all(t["automation"] == "none" and t["url"].startswith("https://cmjansunwai.delhi.gov.in/") for t in d["staff_assisted_tasks"])
    assert "14 digits" in d["reference_rule"]
    for other in ("mp_ka", "mp_mh"):
        o = _portal(other)
        assert o["staff_assisted_tasks"] is None and o["reference_rule"] is None and o["manual_reference_enabled"] is False
        assert o["portal"] is not None and o["supported"] is True


def test_govt_portal_hides_delhi_tasks_when_switch_off(monkeypatch):
    monkeypatch.delenv("GOVT_DELHI_MANUAL_REFERENCE_ENABLED", raising=False)
    d = _portal("mp_a")
    assert d["staff_assisted_tasks"] is None and d["manual_reference_enabled"] is False


# ─── Filing preparation (AI drafts subject + description only) ──────────────────────────────────────────

def test_prepare_worksheet_links_case_drafts_text_and_never_picks_a_department(ai):
    r = _prep(100)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["worksheet"]["department"] is None and body["worksheet"]["subject"] == DRAFT["subject"]
    assert body["portal"]["portal_name"] == "Delhi CM Jan Sunwai" and body["task"]["key"] == "file"
    ai.assert_called_once()
    kwargs = ai.call_args.kwargs
    assert kwargs["portal_name"] == "Delhi CM Jan Sunwai" and kwargs["subject_max_chars"] == delhi_portal.SOFT_SUBJECT_CHARS
    row = _case_row(100)
    assert row["govt_portal_id"] == DELHI_PID and row["govt_department"] is None and row["govt_status"] == "pending_staff_submit"
    assert row["govt_reference_number"] is None
    assert json.loads(row["govt_submission_worksheet"])["description"] == DRAFT["description"]
    logged = _log(100, "ai_translated")
    assert len(logged) == 1 and json.loads(logged[0][1])["portal"] == "Delhi CM Jan Sunwai"


def _activity(cid):
    with test_engine.connect() as c:
        return [(r[0], r[1]) for r in c.execute(text("SELECT action, new_value FROM case_activity_log WHERE case_id = :i ORDER BY id"), {"i": cid}).all()]


def test_staff_actions_appear_in_the_case_activity_timeline(ai):
    assert _prep(100).status_code == 200
    assert _record(100, REF).status_code == 200
    assert _task(100, "status").status_code == 200
    assert _task(100, "reminder").status_code == 200
    govt_events = [a for a in _activity(100) if a[0].startswith("govt_")]
    assert govt_events == [("govt_delhi_worksheet_drafted", None), ("govt_submitted", REF), ("govt_delhi_task", "status"), ("govt_delhi_task", "reminder")]
    assert ("status_change", "in_progress") in _activity(100)      # the existing filing transition is still logged


def test_prepare_worksheet_can_be_repeated_while_unfiled(ai):
    assert _prep(105).status_code == 200 and _prep(105).status_code == 200
    assert _case_row(105)["govt_status"] == "pending_staff_submit"


def test_prepare_worksheet_ai_failure_leaves_the_case_untouched():
    with patch.object(translator_mod, "translate_subject_description_only", return_value=None):
        assert _prep(100).status_code == 502
    row = _case_row(100)
    assert row["govt_portal_id"] is None and row["govt_status"] == "not_forwarded" and _log(100) == []


def test_prepare_worksheet_refuses_filed_other_portal_deleted_and_cross_tenant_cases(ai):
    assert _prep(101).status_code == 409      # already filed with a reference
    assert _prep(104).status_code == 409      # linked to CPGRAMS: never silently relinked
    assert _case_row(104)["govt_portal_id"] == CPGRAMS_PID
    assert _prep(106).status_code == 404      # deleted
    assert _prep(102, "mp_a").status_code == 404   # another tenant's case
    ai.assert_not_called()
    assert _case_row(102)["govt_portal_id"] is None


def test_prepare_worksheet_is_denied_for_other_states_and_when_switch_off(ai, monkeypatch):
    assert _prep(103, "mp_ka").status_code == 400
    assert _prep(103, "mp_mh").status_code == 400
    monkeypatch.delenv("GOVT_DELHI_MANUAL_REFERENCE_ENABLED", raising=False)
    assert _prep(100).status_code == 403
    ai.assert_not_called()


def test_prepare_worksheet_requires_authentication(ai):
    assert client.post("/api/cases/100/govt/delhi/prepare-worksheet").status_code in (401, 403)


# ─── Full filing lifecycle: prepare -> staff files on the portal -> record the number ───────────────────

def test_full_filing_lifecycle_prepare_then_record_reference(ai):
    assert _prep(100).status_code == 200
    r = _record(100, f" {REF} ")
    assert r.status_code == 200 and r.json()["govt_reference_number"] == REF
    row = _case_row(100)
    assert row["govt_status"] == "submitted" and row["govt_reference_number"] == REF and row["govt_portal_id"] == DELHI_PID
    assert [a for a, _ in _log(100)] == ["ai_translated", "staff_submitted"]
    assert _prep(100).status_code == 409          # once filed it can no longer be re-prepared


@pytest.mark.parametrize("bad", ["DEL-123", "2026-0001", "123456789012345", "12 34", "abc", "1e5", "٣٤٥"])
def test_reference_must_satisfy_the_verified_portal_rule(bad):
    r = _record(100, bad)
    assert r.status_code == 400 and "14 digits" in r.json()["detail"]
    assert _case_row(100)["govt_reference_number"] is None


@pytest.mark.parametrize("ok", ["1", "12345678901234", "00012345"])
def test_reference_boundary_values_accepted(ok):
    assert _record(100, ok).status_code == 200


def test_conflicting_and_repeated_references_follow_existing_rules():
    assert _record(101, REF).json()["idempotent"] is True
    assert _record(101, REF2).status_code == 409
    assert _case_row(101)["govt_reference_number"] == REF


def test_delhi_reference_cannot_be_recorded_by_another_tenant_or_state():
    assert _record(100, REF, "mp_b").status_code == 404
    assert _record(103, REF, "mp_ka").status_code == 400


# ─── Staff-assisted tasks (file / status / reminder / feedback) and their audit trail ───────────────────

def test_file_task_available_before_filing_and_audited():
    r = _task(100, "file")
    assert r.status_code == 200 and r.json()["task"]["key"] == "file"
    assert r.json()["task"]["url"] == "https://cmjansunwai.delhi.gov.in/"   # the verified official URL, not a database value
    evt = _log(100, "staff_assisted_task")
    assert len(evt) == 1 and json.loads(evt[0][1]) == {"task": "file", "portal": "Delhi CM Jan Sunwai"}


def test_file_task_refused_once_filed():
    assert _task(101, "file").status_code == 409


@pytest.mark.parametrize("key", ["status", "reminder", "feedback"])
def test_status_reminder_feedback_need_a_recorded_complaint_number(key):
    assert _task(100, key).status_code == 409           # not filed
    assert _task(105, key).status_code == 409           # prepared but no number yet
    ok = _task(101, key)
    assert ok.status_code == 200 and ok.json()["task"]["key"] == key and ok.json()["task"]["automation"] == "none"
    evt = _log(101, "staff_assisted_task")
    assert json.loads(evt[-1][1])["task"] == key


def test_tasks_record_no_outcome_and_never_change_the_case():
    before = _case_row(101)
    for key in ("status", "reminder", "feedback"):
        _task(101, key)
    assert _case_row(101) == before


def test_task_endpoint_validation_and_isolation():
    assert _task(101, "poll").status_code == 400
    assert _task(101, "STATUS ").status_code == 200       # normalised
    assert _task(101, "status", "mp_b").status_code == 404   # other tenant
    assert _task(103, "status", "mp_ka").status_code == 400
    assert _task(104, "status").status_code == 409           # legacy CPGRAMS-linked case
    assert _task(106, "file").status_code == 404


def test_task_endpoint_denied_when_switch_off(monkeypatch):
    monkeypatch.delenv("GOVT_DELHI_MANUAL_REFERENCE_ENABLED", raising=False)
    assert _task(101, "status").status_code == 403


# ─── No automation: poller exclusion, no HTTP, no status claims ─────────────────────────────────────────

def test_poller_never_calls_delhi_check_status_and_makes_no_request():
    """The poller query is Postgres-only (= ANY()), so, like the existing poller tests, the row source is
    patched; what is under test is that a Delhi row is skipped STRUCTURALLY: no check_status call, no
    'inconclusive' audit row, no persisted status, no HTTP."""
    from modules.govt_sync import poller as poller_mod
    from modules.govt_sync.adapters.delhi_cm_jan_sunwai import DelhiStaffAssistedAdapter
    delhi_row = {"case_id": 101, "tenant_id": 1, "govt_status": "submitted", "govt_reference_number": REF, "govt_portal_id": DELHI_PID,
                 "portal_id": DELHI_PID, "state": "Delhi", "portal_name": "Delhi CM Jan Sunwai", "portal_type": "state_branded",
                 "base_url": "https://cmjansunwai.delhi.gov.in/", "status_check_url": None, "status_check_mode": "login_required",
                 "otp_bound": True, "status_check_adapter": "delhi_staff_assisted"}
    with patch.object(poller_mod, "_q", return_value=[delhi_row]), \
            patch.object(DelhiStaffAssistedAdapter, "check_status", side_effect=AssertionError("poller called Delhi check_status")), \
            patch.object(poller_mod, "_log_inconclusive", side_effect=AssertionError("poller logged for Delhi")), \
            patch.object(poller_mod, "persist_successful_status_result", side_effect=AssertionError("poller persisted for Delhi")):
        summary = poller_mod.poll_all_pending()
    assert (summary or {}).get("checked", 0) == 0
    assert _case_row(101)["govt_status"] == "submitted"


def test_generic_status_check_endpoint_is_not_available_for_delhi_tenants():
    r = client.post("/api/cases/101/govt/poll", headers=_headers("mp_a"))
    assert r.status_code == 409 and "CAPTCHA" in r.json()["detail"]
    # no misleading "no change" answer, and no audit row implying a check happened
    assert _log(101, "status_polled") == [] and _log(101, "status_check_inconclusive") == []


# ─── translate_subject_description_only (Gemini mocked) ─────────────────────────────────────────────────

def _fake_client(text_out):
    c = MagicMock()
    c.models.generate_content.return_value = MagicMock(text=text_out)
    return c


def _call(**over):
    kw = dict(raw_grievance="SYNTHETIC water problem", category="Water", district="New Delhi", ulb="W5",
              portal_name="Delhi CM Jan Sunwai", subject_max_chars=150, description_max_chars=1500)
    kw.update(over)
    return translator_mod.translate_subject_description_only(**kw)


def test_translator_returns_text_only_and_no_department():
    with patch.object(translator_mod, "get_gemini_client", return_value=_fake_client(json.dumps({"subject": "S", "description": "D"}))) as g:
        out = _call()
    assert out["subject"] == "S" and out["description"] == "D" and out["department"] is None and out["priority_category"] is None
    prompt = g.return_value.models.generate_content.call_args.kwargs["contents"][0]
    assert "<constituent_grievance>" in prompt and "department_list" not in prompt and "Do NOT choose or mention a department" in prompt
    assert "soft" in out["limits_note"].lower() and "not chosen by Needle" in out["department_note"]


def test_translator_truncates_to_soft_targets_and_fails_closed():
    long = json.dumps({"subject": "s" * 400, "description": "d" * 5000})
    with patch.object(translator_mod, "get_gemini_client", return_value=_fake_client(long)):
        out = _call()
    assert len(out["subject"]) == 150 and len(out["description"]) == 1500
    for bad in ("not json", json.dumps({"subject": "", "description": "x"}), json.dumps({"subject": "x"})):
        with patch.object(translator_mod, "get_gemini_client", return_value=_fake_client(bad)):
            assert _call() is None
    with patch.object(translator_mod, "get_gemini_client", return_value=None):
        assert _call() is None
    boom = MagicMock(); boom.models.generate_content.side_effect = RuntimeError("quota")
    with patch.object(translator_mod, "get_gemini_client", return_value=boom):
        assert _call() is None


def test_existing_taxonomy_translator_is_untouched_and_still_refuses_an_empty_taxonomy():
    with patch.object(translator_mod, "get_gemini_client", return_value=_fake_client("{}")):
        assert translator_mod.translate_for_portal("x", "Water", "d", "u", "Delhi CM Jan Sunwai", {}, {}) is None


# ─── delhi_portal facts module ──────────────────────────────────────────────────────────────────────────

def test_delhi_portal_facts_are_only_the_verified_official_urls():
    tasks = delhi_portal.staff_assisted_tasks()
    urls = {t["key"]: t["url"] for t in tasks}
    assert urls == {"file": "https://cmjansunwai.delhi.gov.in/", "status": "https://cmjansunwai.delhi.gov.in/ComplaintTracker",
                    "reminder": "https://cmjansunwai.delhi.gov.in/SendReminder", "feedback": "https://cmjansunwai.delhi.gov.in/onlineFeedbackEntry"}
    for t in tasks:
        assert any("CAPTCHA" in i for i in t["inputs"]) and any("OTP" in i for i in t["inputs"])
    assert delhi_portal.normalize_reference("20260000123") == "20260000123" and delhi_portal.normalize_reference("12a") is None
