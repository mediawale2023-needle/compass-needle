"""
tests/test_govt_delhi_filing_api.py — Delhi filing worksheet endpoints (catalogue, save, AI suggestion, reference audit).

Synthetic data and mocked AI only. No request is ever made to the Delhi portal: any HTTP/browser/status-check
call fails the test.
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
TEST_DB_URL = "sqlite:///./test_govt_delhi_filing_api.db"
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
from modules.govt_sync import delhi_filing as df

test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False)
client = TestClient(main.app, raise_server_exceptions=False)

DELHI_PID, KA_PID = 1, 3
WS = "/api/cases/{}/govt/delhi/filing-worksheet"
SUGGEST = "/api/cases/{}/govt/delhi/suggest"
MANUAL = "/api/cases/{}/govt/manual-reference"


def _headers(username):
    token = jwt.encode({"sub": username, "exp": _utcnow() + timedelta(hours=8), "iat": _utcnow().timestamp()},
                       TEST_JWT_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def _case(conn, cid, tid, *, portal=None, status="not_forwarded", ref=None, needle="new", dept=None, msg="msg"):
    conn.execute(
        text("INSERT INTO cases (id, tenant_id, user_phone, raw_message, category, status, created_at, "
             "govt_portal_id, govt_status, govt_reference_number, govt_department, is_deleted) "
             "VALUES (:id, :t, '+919111111111', :m, 'Health', :ns, :now, :p, :gs, :ref, :d, 0)"),
        {"id": cid, "t": tid, "ns": needle, "now": _utcnow(), "p": portal, "gs": status, "ref": ref, "d": dept, "m": msg},
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
        for tid, state, user in ((1, "Delhi", "mp_a"), (2, "Delhi", "mp_b"), (3, "Karnataka", "mp_ka")):
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
            (KA_PID, "Karnataka", "Karnataka Janaspandana (iPGRS)", {"Water": "BBMP"}, 1),
        ):
            conn.execute(text("INSERT INTO govt_portals (id, state, portal_name, portal_type, base_url, status_check_mode, "
                              "department_taxonomy, field_schema, otp_bound, active, is_primary, verification_status, live_session_supported) "
                              "VALUES (:id, :s, :n, 'state_branded', 'https://example.gov.in/', 'login_required', :t, '{}', 1, :a, 1, 'verify', 1)"),
                         {"id": pid, "s": state, "n": name, "t": json.dumps(tax), "a": active})
        _case(conn, 100, 1, msg="Police not registering my FIR for a theft near the market")   # fresh Delhi case
        _case(conn, 102, 1, portal=DELHI_PID, status="submitted", ref="20260000001", needle="in_progress")
        _case(conn, 103, 2)                                                                 # other Delhi tenant
        _case(conn, 104, 3)                                                                 # Karnataka tenant
    yield


@pytest.fixture(autouse=True)
def switch_on(monkeypatch):
    monkeypatch.setenv("GOVT_DELHI_MANUAL_REFERENCE_ENABLED", "true")


@pytest.fixture(autouse=True)
def no_external_calls():
    def boom(*a, **k):
        raise AssertionError("external call attempted")
    import requests
    import modules.govt_sync.translator as tr
    import modules.govt_sync.browser_session as bs
    with patch.object(requests, "get", boom), patch.object(requests, "post", boom), \
            patch.object(requests, "request", boom), patch.object(tr, "translate_for_portal", boom), \
            patch.object(bs, "start_session", boom):
        yield


def _good(**over):
    p = {
        "applicant_name": "Synthetic Applicant", "father_husband_name": "Synthetic Father", "gender": "Female",
        "residential_address": "12 Synthetic Lane, Delhi",
        "department": "Delhi Police", "category": "Abuse of Power", "location": "Typed Constituency",
        "grievance_details": "Synthetic grievance text. Secret-grievance-marker-77.",
        "grievance_area_address": "Synthetic Market, Delhi",
        "selection_sources": {"department": "staff_confirmed", "category": "staff_confirmed", "location": "staff_confirmed"},
    }
    p.update(over)
    return p


def _put(cid, body, user="mp_a"):
    return client.post(WS.format(cid), json=body, headers=_headers(user))


def _row(cid):
    with test_engine.connect() as c:
        return dict(c.execute(text("SELECT govt_portal_id, govt_department, govt_status, govt_reference_number, "
                                   "govt_submission_worksheet FROM cases WHERE id = :i"), {"i": cid}).mappings().first())


def _log(cid):
    with test_engine.connect() as c:
        return [dict(r) for r in c.execute(text("SELECT action, actor_username, payload FROM govt_submission_log "
                                                "WHERE case_id = :i ORDER BY id"), {"i": cid}).mappings()]


def _ws(cid):
    v = _row(cid)["govt_submission_worksheet"]
    return json.loads(v) if isinstance(v, str) else v


# ── Catalogue endpoints ─────────────────────────────────────────────────────────────────────────────
def test_catalogue_lists_90_departments_with_completeness_and_rules():
    r = client.get("/api/govt/delhi/catalogue", headers=_headers("mp_a"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["departments"]) == 90
    police = next(d for d in body["departments"] if d["name"] == "Delhi Police")
    assert police["category_count"] == 369 and police["categories_complete"] is False
    assert police["capture_status"] == "partial" and police["unverified_row_count"] == 19
    assert sum(1 for d in body["departments"] if d["categories_complete"]) == 89
    assert sum(d["category_count"] for d in body["departments"]) == 1814
    assert all("categories" not in d for d in body["departments"])          # summary only
    assert all(d["portal_option_value_observed"] for d in body["departments"])
    assert body["field_rules"]["address_max_chars"] == 250
    assert "invent" in body["meta"]["ids_policy"].lower()
    assert (body["meta"]["category_row_count"], body["meta"]["departments_partial"]) == (1814, 1)


def test_categories_endpoint_returns_police_rows_in_portal_order_with_authorities():
    r = client.get("/api/govt/delhi/catalogue/categories", params={"department": "Delhi Police"}, headers=_headers("mp_a"))
    assert r.status_code == 200
    body = r.json()
    assert len(body["categories"]) == 369 and body["categories_complete"] is False and body["capture_status"] == "partial"
    assert body["unverified_row_count"] == 19 and body["verification_summary"]["screenshot_repaired_not_text_verified"] == 19
    assert "PARTIAL" in body["categories_note"]
    first = body["categories"][0]
    assert first["seq"] == 1 and first["l1"]["disposal_days"] == 21 and first["l2"]["disposal_days"] == 10


def test_categories_endpoint_serves_every_department_complete_except_police():
    total = 0
    for d in df.list_departments():
        r = client.get("/api/govt/delhi/catalogue/categories", params={"department": d["name"]}, headers=_headers("mp_a"))
        assert r.status_code == 200, d["name"]
        body = r.json()
        total += len(body["categories"])
        assert [c["seq"] for c in body["categories"]] == list(range(1, len(body["categories"]) + 1)), d["name"]
        assert body["categories_complete"] is (d["name"] != "Delhi Police"), d["name"]
        assert body["portal_option_value_observed"] == d["portal_option_value_observed"]
        assert body["locations"] == [] and body["locations_status"] == "not_captured"
    assert total == 1814


def test_categories_for_department_without_category_data_are_empty_and_flagged(monkeypatch):
    import copy
    data = copy.deepcopy(df._load_catalogue())
    target = data["departments"][5]
    target["categories"] = []
    target["catalogue"] = {"status": "not_captured", "complete": False, "form_comparison": "pending"}
    monkeypatch.setattr(df, "_load_catalogue", lambda: data)
    r = client.get("/api/govt/delhi/catalogue/categories", params={"department": target["name"]}, headers=_headers("mp_a"))
    assert r.status_code == 200
    assert r.json()["categories"] == [] and r.json()["categories_complete"] is False and r.json()["capture_status"] == "not_captured"
    # and filing is still not blocked: the category is typed and recorded as unverified
    w = _put(100, _good(department=target["name"], category="Typed as shown on the portal", location="Typed location"))
    assert w.json()["validation"]["ready_to_file"] is True
    assert w.json()["saved"]["selection_sources"]["category"] == "staff_typed_unverified"


def test_unknown_department_is_404():
    r = client.get("/api/govt/delhi/catalogue/categories", params={"department": "Nope"}, headers=_headers("mp_a"))
    assert r.status_code == 404


def test_catalogue_is_delhi_tenants_only_and_switch_gated(monkeypatch):
    assert client.get("/api/govt/delhi/catalogue", headers=_headers("mp_ka")).status_code == 400
    monkeypatch.setenv("GOVT_DELHI_MANUAL_REFERENCE_ENABLED", "false")
    assert client.get("/api/govt/delhi/catalogue", headers=_headers("mp_a")).status_code == 403
    assert client.get("/api/govt/delhi/catalogue").status_code in (401, 403)


# ── Saving the worksheet ────────────────────────────────────────────────────────────────────────────
def test_valid_worksheet_is_saved_with_server_derived_provenance_and_links_the_case():
    r = _put(100, _good())
    assert r.status_code == 200, r.text
    v = r.json()["validation"]
    assert v["ready_to_file"] is True
    src = r.json()["saved"]["selection_sources"]
    assert src["department"] == "staff_confirmed" and src["category"] == "staff_confirmed"
    assert src["location"] == "staff_typed_unverified"          # client claimed confirmed; Delhi Police has no location list captured
    row = _row(100)
    assert row["govt_portal_id"] == DELHI_PID and row["govt_department"] == "Delhi Police"
    assert row["govt_status"] == "pending_staff_submit" and not row["govt_reference_number"]
    assert _ws(100)["delhi_filing"]["applicant_name"] == "Synthetic Applicant"


def test_saving_never_marks_the_case_filed():
    _put(100, _good())
    assert _row(100)["govt_status"] != "submitted"


def test_invalid_draft_is_still_saved_but_reported_not_ready():
    r = _put(100, _good(grievance_area_address="", location=""))
    assert r.status_code == 200
    v = r.json()["validation"]
    assert v["ready_to_file"] is False
    assert {"required"} == {e["code"] for e in v["errors"]}
    assert _ws(100)["delhi_filing"]["ready_to_file"] is False


def test_department_outside_catalogue_is_rejected_by_validation_and_not_stored_as_government_department():
    r = _put(100, _good(department="Imaginary Department"))
    assert r.json()["validation"]["ready_to_file"] is False
    assert r.json()["saved"]["selection_sources"]["department"] == "staff_typed_unverified"
    assert _row(100)["govt_department"] is None


def test_forged_confirmed_category_is_downgraded_to_unverified_and_warns_for_a_complete_department():
    r = _put(100, _good(department="Department of Revenue", category="Made up category"))
    assert r.json()["saved"]["selection_sources"]["category"] == "staff_typed_unverified"
    v = r.json()["validation"]
    assert v["ready_to_file"] is True and not v["errors"]                       # a warning, not a block
    assert "not_in_catalogue_unverified" in {w["code"] for w in v["warnings"] if w["field"] == "category"}
    assert _ws(100)["delhi_filing"]["category"] == "Made up category"           # stored exactly as typed, not substituted


def test_audit_row_records_unlisted_category_as_staff_typed_unverified():
    _put(100, _good(department="Department of Revenue", category="Made up category"))
    rows = [r for r in _log(100) if r["action"] == "delhi_filing_worksheet_saved"]
    assert rows, _log(100)
    payload = rows[-1]["payload"]
    payload = json.loads(payload) if isinstance(payload, str) else payload
    assert "staff_typed_unverified" in json.dumps(payload) and "not_in_catalogue_unverified" in json.dumps(payload)
    assert "Secret-grievance-marker-77" not in json.dumps(payload)              # grievance text still never audited


def test_ai_suggested_unlisted_category_is_still_unconfirmed_via_api():
    r = _put(100, _good(department="Department of Revenue", category="Made up category", selection_sources={"category": "ai_suggested"}))
    v = r.json()["validation"]
    assert v["ready_to_file"] is False
    assert ("category", "ai_suggestion_unconfirmed") in {(e["field"], e["code"]) for e in v["errors"]}


def test_forged_confirmed_category_in_partial_police_is_downgraded_but_warns_only():
    r = _put(100, _good(category="Made up category"))
    assert r.json()["saved"]["selection_sources"]["category"] == "staff_typed_unverified"
    v = r.json()["validation"]
    assert v["ready_to_file"] is True and not v["errors"]
    assert "not_in_partial_catalogue" in {w["code"] for w in v["warnings"]}


def test_other_department_category_is_confirmed_from_its_captured_list_and_location_stays_typed():
    djb = df.get_categories("Delhi Jal Board")["categories"][0]["text"]
    r = _put(100, _good(department="Delhi Jal Board", category=djb, location="Typed location"))
    v = r.json()["validation"]
    assert v["ready_to_file"] is True
    assert r.json()["saved"]["selection_sources"] == {"department": "staff_confirmed", "category": "staff_confirmed", "location": "staff_typed_unverified"}
    assert "catalogue_not_captured" in {w["code"] for w in v["warnings"] if w["field"] == "location"}


def test_address_limit_and_attachment_rules_are_enforced_server_side():
    r = _put(100, _good(residential_address="a" * 251, attachment={"filename": "bad name.pdf", "size_bytes": 5, "content_type": "application/pdf"}))
    codes = {(e["field"], e["code"]) for e in r.json()["validation"]["errors"]}
    assert ("residential_address", "too_long") in codes and ("supporting_document", "name_has_space") in codes


def test_long_grievance_details_is_warning_only():
    r = _put(100, _good(grievance_details="x" * 5000))
    assert r.json()["validation"]["ready_to_file"] is True
    assert "long_unknown_limit" in {w["code"] for w in r.json()["validation"]["warnings"]}


def test_group_grievance_needs_no_father_or_gender():
    r = _put(100, _good(group_grievance=True, father_husband_name=None, gender=None))
    assert r.json()["validation"]["ready_to_file"] is True


def test_audit_row_records_who_selected_what_without_personal_data_or_grievance_text():
    _put(100, _good())
    rows = [x for x in _log(100) if x["action"] == "delhi_filing_worksheet_saved"]
    assert len(rows) == 1 and rows[0]["actor_username"] == "mp_a"
    blob = json.dumps(rows[0]["payload"]) if not isinstance(rows[0]["payload"], str) else rows[0]["payload"]
    assert "Delhi Police" in blob and "Abuse of Power" in blob
    assert "Synthetic Applicant" not in blob and "Secret-grievance-marker-77" not in blob and "Synthetic Lane" not in blob


def test_cross_tenant_filed_and_wrong_state_are_refused():
    assert _put(103, _good(), user="mp_a").status_code == 404           # other tenant's case
    assert _put(102, _good()).status_code == 409                        # already filed with a reference
    assert _put(104, _good(), user="mp_ka").status_code == 400          # Karnataka tenant
    assert _row(103)["govt_portal_id"] is None and _row(104)["govt_portal_id"] is None


def test_switch_off_refuses(monkeypatch):
    monkeypatch.setenv("GOVT_DELHI_MANUAL_REFERENCE_ENABLED", "false")
    assert _put(100, _good()).status_code == 403
    assert _row(100)["govt_portal_id"] is None


def test_redrafting_the_ai_text_keeps_the_staff_filing_selections():
    _put(100, _good())
    fake = {"department": None, "district": "", "subdistrict_or_ulb": "", "subject": "S", "description": "D",
            "priority_category": None, "department_note": "n", "limits_note": "l"}
    with patch("modules.govt_sync.translator.translate_subject_description_only", return_value=fake):
        r = client.post("/api/cases/100/govt/delhi/prepare-worksheet", headers=_headers("mp_a"))
    assert r.status_code == 200, r.text
    ws = _ws(100)
    assert ws["subject"] == "S" and ws["delhi_filing"]["department"] == "Delhi Police"


def test_redrafting_never_writes_personal_data_or_draft_text_to_the_audit_log():
    """Regression: the ai_translated audit row used to include the whole saved delhi_filing block."""
    markers = {
        "applicant_name": "ZZ-NAME-MARKER-81", "father_husband_name": "ZZ-FATHER-MARKER-82",
        "residential_address": "ZZ-RESADDR-MARKER-83", "mobile_2": "ZZ-MOBILE-MARKER-84",
        "email": "zz-email-marker-85@example.invalid", "grievance_details": "ZZ-GRIEVANCE-MARKER-86",
        "grievance_area_address": "ZZ-AREAADDR-MARKER-87",
    }
    assert _put(100, _good(**markers)).status_code == 200
    fake = {"department": None, "district": "", "subdistrict_or_ulb": "", "subject": "ZZ-DRAFTSUBJECT-MARKER-88",
            "description": "ZZ-DRAFTDESC-MARKER-89", "priority_category": None, "department_note": "n", "limits_note": "l"}
    with patch("modules.govt_sync.translator.translate_subject_description_only", return_value=fake):
        r = client.post("/api/cases/100/govt/delhi/prepare-worksheet", headers=_headers("mp_a"))
    assert r.status_code == 200, r.text
    assert _ws(100)["delhi_filing"]["applicant_name"] == markers["applicant_name"]       # worksheet itself still keeps them
    with test_engine.connect() as c:
        raw = [dict(x) for x in c.execute(text("SELECT tenant_id, case_id, action, actor_username, payload, created_at "
                                               "FROM govt_submission_log WHERE case_id = 100 ORDER BY id")).mappings()]
    blob = json.dumps(raw, default=str)
    for v in [*markers.values(), "ZZ-DRAFTSUBJECT-MARKER-88", "ZZ-DRAFTDESC-MARKER-89"]:
        assert v not in blob, v
    row = [x for x in raw if x["action"] == "ai_translated"]
    assert len(row) == 1, [x["action"] for x in raw]
    row = row[0]
    pl = json.loads(row["payload"]) if isinstance(row["payload"], str) else row["payload"]
    assert (row["tenant_id"], row["case_id"], row["actor_username"]) == (1, 100, "mp_a") and row["created_at"]
    assert pl["portal"] and pl["portal_id"] == DELHI_PID and pl["kept_staff_filing_selections"] is True
    assert pl["subject_chars"] == len(fake["subject"]) and pl["description_chars"] == len(fake["description"])
    assert "delhi_filing" not in pl and "subject" not in pl and "description" not in pl


def test_saving_the_worksheet_never_writes_the_typed_location_to_the_audit_log():
    """Regression: delhi_filing_worksheet_saved used to log the staff-typed location string (may be an address)."""
    marker = "ZZ-LOCATION-ADDRESS-MARKER-91, Flat 4B, Synthetic Nagar"
    r = _put(100, _good(location=marker, selection_sources={"department": "staff_confirmed", "category": "staff_confirmed",
                                                          "location": "staff_confirmed"}))
    assert r.status_code == 200, r.text
    assert _ws(100)["delhi_filing"]["location"] == marker                      # the worksheet itself still stores it
    with test_engine.connect() as c:
        raw = [dict(x) for x in c.execute(text("SELECT tenant_id, case_id, action, actor_username, payload, created_at "
                                               "FROM govt_submission_log WHERE case_id = 100 ORDER BY id")).mappings()]
    assert "ZZ-LOCATION-ADDRESS-MARKER-91" not in json.dumps(raw, default=str)
    assert "Synthetic Nagar" not in json.dumps(raw, default=str)
    rows = [x for x in raw if x["action"] == "delhi_filing_worksheet_saved"]
    assert len(rows) == 1, [x["action"] for x in raw]
    row = rows[0]
    pl = json.loads(row["payload"]) if isinstance(row["payload"], str) else row["payload"]
    assert (row["tenant_id"], row["case_id"], row["actor_username"]) == (1, 100, "mp_a") and row["created_at"]
    assert "location" not in pl
    assert pl["location_supplied"] is True and pl["location_source"] == "staff_typed_unverified"   # not in the catalogue -> typed
    assert pl["portal"] and pl["department"] == "Delhi Police" and pl["category"] == "Abuse of Power"
    assert pl["selection_sources"]["location"] == "staff_typed_unverified" and "ready_to_file" in pl
    assert "warning_codes" in pl and "error_codes" in pl
    # no location supplied -> flagged as not supplied
    _put(100, _good(location="", selection_sources={"department": "staff_confirmed", "category": "staff_confirmed"}))
    with test_engine.connect() as c:
        last = c.execute(text("SELECT payload FROM govt_submission_log WHERE case_id = 100 AND action = "
                              "'delhi_filing_worksheet_saved' ORDER BY id DESC LIMIT 1")).scalar()
    last = json.loads(last) if isinstance(last, str) else last
    assert last["location_supplied"] is False and last["location_source"] is None


# ── AI suggestions ──────────────────────────────────────────────────────────────────────────────────
def test_ai_suggestion_is_stored_unconfirmed_and_cannot_satisfy_validation():
    answers = iter([{"department": "Delhi Police"}, {"category": "Abuse of Power"}])
    with patch("modules.govt_sync.delhi_ai._ask", side_effect=lambda prompt: next(answers)):
        r = client.post(SUGGEST.format(100), headers=_headers("mp_a"))
    assert r.status_code == 200, r.text
    sug = r.json()["suggestion"]
    assert sug["department"] == "Delhi Police" and sug["category"] == "Abuse of Power" and sug["source"] == "ai_suggested"
    row = _row(100)
    assert row["govt_department"] is None                               # a suggestion never becomes the department
    assert _ws(100)["delhi_filing"]["ai_suggestions"]["department"] == "Delhi Police"
    # sending it back unconfirmed is refused by validation
    res = _put(100, _good(selection_sources={"department": "ai_suggested", "category": "ai_suggested"}))
    assert res.json()["validation"]["ready_to_file"] is False
    assert _ws(100)["delhi_filing"]["ai_suggestions"]["department"] == "Delhi Police"     # still kept alongside


def test_ai_values_outside_the_catalogue_are_dropped():
    answers = iter([{"department": "Ministry of Made-Up Things"}])
    with patch("modules.govt_sync.delhi_ai._ask", side_effect=lambda prompt: next(answers)):
        r = client.post(SUGGEST.format(100), headers=_headers("mp_a"))
    assert r.json()["suggestion"]["department"] is None and r.json()["suggestion"]["category"] is None
    answers = iter([{"department": "Delhi Police"}, {"category": "A category the portal does not have"}])
    with patch("modules.govt_sync.delhi_ai._ask", side_effect=lambda prompt: next(answers)):
        r = client.post(SUGGEST.format(100), headers=_headers("mp_a"))
    assert r.json()["suggestion"]["department"] == "Delhi Police" and r.json()["suggestion"]["category"] is None


def test_ai_failure_is_a_502_and_changes_nothing():
    with patch("modules.govt_sync.delhi_ai._ask", return_value=None):
        r = client.post(SUGGEST.format(100), headers=_headers("mp_a"))
    assert r.status_code == 502 and _row(100)["govt_portal_id"] is None


def test_suggestion_endpoint_is_gated():
    assert client.post(SUGGEST.format(104), headers=_headers("mp_ka")).status_code == 400
    assert client.post(SUGGEST.format(103), headers=_headers("mp_a")).status_code == 404
    assert client.post(SUGGEST.format(102), headers=_headers("mp_a")).status_code == 409


# ── Reference recording: staff report, not verification ─────────────────────────────────────────────
def test_reference_entry_is_audited_as_staff_reported_with_who_when_portal_and_selections():
    _put(100, _good())
    r = client.post(MANUAL.format(100), json={"reference_number": "20260000450"}, headers=_headers("mp_a"))
    assert r.status_code == 200, r.text
    assert r.json()["filing_record_state"] == "staff_reported_filed"
    assert r.json()["govt_status"] == "submitted"
    row = [x for x in _log(100) if x["action"] == "staff_submitted"][0]
    pl = json.loads(row["payload"]) if isinstance(row["payload"], str) else row["payload"]
    assert row["actor_username"] == "mp_a"
    assert pl["reference_number"] == "20260000450" and pl["portal"] == "Delhi CM Jan Sunwai"
    assert pl["filing_record_state"] == "staff_reported_filed" and pl["verified_with_portal"] is False
    assert pl["reported_by"] == "mp_a" and pl["reported_at"] and pl["portal_id"] == DELHI_PID
    assert pl["department"] == "Delhi Police" and pl["selection_sources"]["department"] == "staff_confirmed"
    assert "verified_by_portal" not in json.dumps(pl)


def test_reference_without_a_worksheet_is_still_recordable_and_never_verified():
    r = client.post(MANUAL.format(100), json={"reference_number": "20260000467"}, headers=_headers("mp_a"))
    assert r.status_code == 200
    pl = json.loads([x for x in _log(100) if x["action"] == "staff_submitted"][0]["payload"])
    assert pl["department"] is None and pl["verified_with_portal"] is False


def test_duplicate_and_conflicting_references_stay_protected():
    ok = client.post(MANUAL.format(100), json={"reference_number": "20260000474"}, headers=_headers("mp_a"))
    assert ok.status_code == 200 and not ok.json().get("idempotent")
    again = client.post(MANUAL.format(100), json={"reference_number": "20260000474"}, headers=_headers("mp_a"))
    assert again.status_code == 200 and again.json()["idempotent"] is True
    assert again.json()["filing_record_state"] == "staff_reported_filed"
    other = client.post(MANUAL.format(100), json={"reference_number": "20260000481"}, headers=_headers("mp_a"))
    assert other.status_code == 409
    assert _row(100)["govt_reference_number"] == "20260000474"
    assert len([x for x in _log(100) if x["action"] == "staff_submitted"]) == 1


def test_worksheet_cannot_be_changed_after_the_reference_is_recorded():
    client.post(MANUAL.format(100), json={"reference_number": "20260000498"}, headers=_headers("mp_a"))
    assert _put(100, _good()).status_code == 409


# --- portal identity on the case payloads (lets the modal recognise a Delhi case from every entry path) ---

def test_case_detail_carries_the_stable_portal_identity_for_a_linked_case():
    r = client.get("/api/cases/102", headers=_headers("mp_a"))
    assert r.status_code == 200
    body = r.json()
    assert body["govt_portal_state"] == "Delhi"
    assert body["govt_portal_name"] == "Delhi CM Jan Sunwai"


def test_case_detail_has_no_portal_identity_for_an_unlinked_case():
    body = client.get("/api/cases/100", headers=_headers("mp_a")).json()
    assert body["govt_portal_state"] is None and body["govt_portal_name"] is None


def test_case_detail_reports_another_portals_own_identity_not_delhi():
    with test_engine.begin() as conn:
        conn.execute(text("UPDATE cases SET govt_portal_id = :p, govt_status = 'submitted' WHERE id = 104"), {"p": KA_PID})
    body = client.get("/api/cases/104", headers=_headers("mp_ka")).json()
    assert body["govt_portal_state"] == "Karnataka"
    assert body["govt_portal_name"] == "Karnataka Janaspandana (iPGRS)"


def test_case_list_carries_the_portal_state_next_to_the_name():
    rows = client.get("/api/cases", headers=_headers("mp_a")).json()
    rows = rows.get("cases", rows) if isinstance(rows, dict) else rows
    filed = next(r for r in rows if r["id"] == 102)
    assert filed["govt_portal_state"] == "Delhi" and filed["govt_portal_name"] == "Delhi CM Jan Sunwai"


def test_govt_state_endpoint_carries_portal_state_for_the_modal_after_filing():
    body = client.get("/api/cases/102/govt", headers=_headers("mp_a")).json()["case"]
    assert body["portal_state"] == "Delhi" and body["portal_name"] == "Delhi CM Jan Sunwai"
    unlinked = client.get("/api/cases/100/govt", headers=_headers("mp_a")).json()["case"]
    assert unlinked["portal_state"] is None
