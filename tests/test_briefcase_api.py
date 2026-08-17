import json
import os
import sys
from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
TEST_DB_URL = "sqlite:///./test_briefcase_api.db"

os.environ["JWT_SECRET"] = TEST_JWT_SECRET
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["ENV"] = "test"
os.environ["OPENAI_API_KEY"] = "sk-test-fake-key-for-testing"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@event.listens_for(Engine, "connect")
def _sqlite_register_pg_lock_functions(dbapi_connection, connection_record):
    try:
        dbapi_connection.create_function("pg_try_advisory_lock", 1, lambda _key: 1)
        dbapi_connection.create_function("pg_advisory_unlock", 1, lambda _key: 1)
        dbapi_connection.create_function("pg_try_advisory_xact_lock", 1, lambda _key: 1)
    except Exception:
        pass


import api_router
import core.db_helpers as db_helpers
import main
import sansadx_backend.db as dbmod
from sansadx_backend.db import Base, hash_password
from modules.geography_resolver import resolve_location


test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False)
client = TestClient(main.app, raise_server_exceptions=False)


def _seed_database():
    dbmod.engine = test_engine
    dbmod.SessionLocal = TestSession
    db_helpers.engine = test_engine
    main.engine = test_engine
    api_router.engine = test_engine
    api_router.JWT_SECRET = TEST_JWT_SECRET

    Base.metadata.create_all(bind=test_engine)

    with test_engine.begin() as conn:
        for table_name in (
            "escalations",
            "officers",
            "case_activity_log",
            "case_media",
            "cases",
            "tenant_overrides",
            "token_blocklist",
            "users",
            "tenant_profiles",
            "tenants",
        ):
            conn.execute(text(f"DELETE FROM {table_name}"))  # nosec B608

        now = _utcnow()

        conn.execute(
            text(
                """
                INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active, created_at)
                VALUES
                    (1, 'Arun Kumar', 'Bangalore North', '+919000000001', 'Pro', 1, :now),
                    (2, 'Priya Sharma', 'Mumbai North', '+919000000002', 'Pro', 1, :now)
                """
            ),
            {"now": now},
        )

        conn.execute(
            text(
                """
                INSERT INTO tenant_profiles (tenant_id, mp_name, constituency, state, house, created_at)
                VALUES
                    (1, 'Shri Arun Kumar', 'Bangalore North', 'Karnataka', 'Lok Sabha', :now),
                    (2, 'Smt Priya Sharma', 'Mumbai North', 'Maharashtra', 'Lok Sabha', :now)
                """
            ),
            {"now": now},
        )

        users = [
            ("mp_arun", "mp", 1, "Arun Kumar", "Lok Sabha", "Arun MP"),
            ("owner_arun", "owner", 1, "Arun Kumar", "Lok Sabha", "Arun Owner"),
            ("pr_meera", "pr", 1, "Bangalore North", "Lok Sabha", "Meera PR"),
            ("staff_raj", "user", 1, "Bangalore North", "Lok Sabha", "Raj Staff"),
            ("mp_priya", "mp", 2, "Mumbai North", "Lok Sabha", "Priya MP"),
        ]
        for username, role, tenant_id, constituency, house, display_name in users:
            conn.execute(
                text(
                    """
                    INSERT INTO users
                        (tenant_id, username, password_hash, role, constituency, house, display_name, is_active)
                    VALUES
                        (:tenant_id, :username, :password_hash, :role, :constituency, :house, :display_name, true)
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "username": username,
                    "password_hash": hash_password("ValidPass1!"),
                    "role": role,
                    "constituency": constituency,
                    "house": house,
                    "display_name": display_name,
                },
            )

        cases = [
            {
                "id": 101,
                "tenant_id": 1,
                "user_phone": "919810000101",
                "raw_message": "No water supply in Whitefield for 3 days",
                "category": "Infrastructure & Utilities",
                "problem_domain": None,
                "problem_subdomain": None,
                "convergence_program_type": None,
                "status": "new",
                "location": None,
                "assembly": None,
                "response_to_citizen": None,
                "notes_for_staff": None,
                "assigned_to": None,
                "is_deleted": False,
                "deleted_at": None,
                "deleted_by": None,
                "case_ref": "NDL-2026-00101",
                "created_at": now - timedelta(minutes=1),
                "meta": json.dumps(
                    {
                        "matched_value": "Whitefield",
                        "assembly_constituency": "Mahadevapura",
                        "summary": "Water outage in Whitefield",
                        "problem_domain": "Infrastructure & Utilities",
                        "problem_subdomain": "Water Supply",
                        "convergence_program_type": "Service Delivery Strengthening",
                    }
                ),
            },
            {
                "id": 102,
                "tenant_id": 1,
                "user_phone": "919810000102",
                "raw_message": "Streetlight not working near Indiranagar market",
                "category": "Infrastructure & Utilities",
                "problem_domain": "Infrastructure & Utilities",
                "problem_subdomain": "Streetlights",
                "convergence_program_type": "Service Delivery Strengthening",
                "status": "in_progress",
                "location": "Indiranagar",
                "assembly": "CV Raman Nagar",
                "response_to_citizen": None,
                "notes_for_staff": None,
                "assigned_to": "pr_meera",
                "is_deleted": False,
                "deleted_at": None,
                "deleted_by": None,
                "case_ref": "NDL-2026-00102",
                "created_at": now - timedelta(minutes=2),
                "meta": json.dumps(
                    {
                        "matched_value": "Indiranagar",
                        "assembly_constituency": "CV Raman Nagar",
                        "summary": "Streetlight issue",
                    }
                ),
            },
            {
                "id": 103,
                "tenant_id": 1,
                "user_phone": "919810000103",
                "raw_message": "Please call me back",
                "category": "Request",
                "problem_domain": None,
                "problem_subdomain": None,
                "convergence_program_type": None,
                "status": "new",
                "location": None,
                "assembly": None,
                "response_to_citizen": None,
                "notes_for_staff": None,
                "assigned_to": None,
                "is_deleted": False,
                "deleted_at": None,
                "deleted_by": None,
                "case_ref": "NDL-2026-00103",
                "created_at": now - timedelta(minutes=3),
                "meta": json.dumps({}),
            },
            {
                "id": 104,
                "tenant_id": 1,
                "user_phone": "919810000104",
                "raw_message": "Good news! Issue solved.",
                "category": "Infrastructure & Utilities",
                "problem_domain": "Infrastructure & Utilities",
                "problem_subdomain": "Road Repair",
                "convergence_program_type": "Service Delivery Strengthening",
                "status": "resolved",
                "location": "Malleshwaram",
                "assembly": "Malleshwaram",
                "response_to_citizen": "Resolved and closed.",
                "notes_for_staff": "Done",
                "assigned_to": "pr_meera",
                "is_deleted": False,
                "deleted_at": None,
                "deleted_by": None,
                "case_ref": "NDL-2026-00104",
                "created_at": now - timedelta(minutes=4),
                "meta": json.dumps(
                    {
                        "matched_value": "Malleshwaram",
                        "assembly_constituency": "Malleshwaram",
                    }
                ),
            },
            {
                "id": 105,
                "tenant_id": 1,
                "user_phone": "919810000101",
                "raw_message": "Still no water supply in Whitefield lane 4",
                "category": "Infrastructure & Utilities",
                "problem_domain": "Infrastructure & Utilities",
                "problem_subdomain": "Water Supply",
                "convergence_program_type": "Service Delivery Strengthening",
                "status": "pending",
                "location": "Whitefield",
                "assembly": "Mahadevapura",
                "response_to_citizen": None,
                "notes_for_staff": None,
                "assigned_to": None,
                "is_deleted": False,
                "deleted_at": None,
                "deleted_by": None,
                "case_ref": "NDL-2026-00105",
                "created_at": now - timedelta(days=2),
                "meta": json.dumps(
                    {
                        "matched_value": "Whitefield",
                        "assembly_constituency": "Mahadevapura",
                    }
                ),
            },
            {
                "id": 106,
                "tenant_id": 1,
                "user_phone": "919810000106",
                "raw_message": "Old deleted case",
                "category": "Infrastructure & Utilities",
                "problem_domain": "Infrastructure & Utilities",
                "problem_subdomain": "Water Supply",
                "convergence_program_type": "Service Delivery Strengthening",
                "status": "new",
                "location": "Yelahanka",
                "assembly": "Yelahanka",
                "response_to_citizen": None,
                "notes_for_staff": None,
                "assigned_to": None,
                "is_deleted": True,
                "deleted_at": now - timedelta(days=2),
                "deleted_by": "pr_meera",
                "case_ref": "NDL-2026-00106",
                "created_at": now - timedelta(days=3),
                "meta": json.dumps(
                    {
                        "matched_value": "Yelahanka",
                        "assembly_constituency": "Yelahanka",
                    }
                ),
            },
            {
                "id": 107,
                "tenant_id": 1,
                "user_phone": "919810000107",
                "raw_message": "Very old deleted case",
                "category": "Infrastructure & Utilities",
                "problem_domain": "Infrastructure & Utilities",
                "problem_subdomain": "Garbage",
                "convergence_program_type": "Service Delivery Strengthening",
                "status": "new",
                "location": "Hebbal",
                "assembly": "Byatarayanapura",
                "response_to_citizen": None,
                "notes_for_staff": None,
                "assigned_to": None,
                "is_deleted": True,
                "deleted_at": now - timedelta(days=10),
                "deleted_by": "pr_meera",
                "case_ref": "NDL-2026-00107",
                "created_at": now - timedelta(days=11),
                "meta": json.dumps(
                    {
                        "matched_value": "Hebbal",
                        "assembly_constituency": "Byatarayanapura",
                    }
                ),
            },
            {
                "id": 201,
                "tenant_id": 2,
                "user_phone": "919810000101",
                "raw_message": "Water issue in Kandivali",
                "category": "Infrastructure & Utilities",
                "problem_domain": "Infrastructure & Utilities",
                "problem_subdomain": "Water Supply",
                "convergence_program_type": "Service Delivery Strengthening",
                "status": "new",
                "location": "Kandivali",
                "assembly": "Kandivali East",
                "response_to_citizen": None,
                "notes_for_staff": None,
                "assigned_to": None,
                "is_deleted": False,
                "deleted_at": None,
                "deleted_by": None,
                "case_ref": "NDL-2026-00201",
                "created_at": now - timedelta(minutes=1),
                "meta": json.dumps(
                    {
                        "matched_value": "Kandivali",
                        "assembly_constituency": "Kandivali East",
                    }
                ),
            },
        ]

        for case in cases:
            conn.execute(
                text(
                    """
                    INSERT INTO cases
                        (id, tenant_id, user_phone, raw_message, category, problem_domain,
                         problem_subdomain, convergence_program_type, status, location,
                         assembly, response_to_citizen, notes_for_staff, assigned_to,
                         case_metadata, is_critical, created_at, updated_at,
                         is_deleted, deleted_at, deleted_by, case_ref)
                    VALUES
                        (:id, :tenant_id, :user_phone, :raw_message, :category, :problem_domain,
                         :problem_subdomain, :convergence_program_type, :status, :location,
                         :assembly, :response_to_citizen, :notes_for_staff, :assigned_to,
                         :meta, false, :created_at, :created_at,
                         :is_deleted, :deleted_at, :deleted_by, :case_ref)
                    """
                ),
                case,
            )

        conn.execute(
            text(
                """
                INSERT INTO officers
                    (id, tenant_id, name, designation, department, email, phone, jurisdiction, categories, is_active, created_at)
                VALUES
                    (1, 1, 'Asha Rao', 'Executive Engineer', 'BWSSB', 'asha.rao@example.com', '9876543210', 'Mahadevapura', :cats, true, :now)
                """
            ),
            {"cats": json.dumps(["Infrastructure & Utilities"]), "now": now},
        )


def _auth_headers(username: str) -> dict[str, str]:
    token = jwt.encode(
        {
            "sub": username,
            "exp": _utcnow() + timedelta(hours=8),
            "iat": _utcnow().timestamp(),
        },
        TEST_JWT_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def test_briefcase_cases_list_supports_filters_search_pagination_and_metadata_fallback():
    _seed_database()
    headers = _auth_headers("mp_arun")

    resp = client.get("/api/cases?page=1&limit=2", headers=headers)
    assert resp.status_code == 200, resp.text
    payload = resp.json()

    assert payload["total"] == 5
    assert payload["pages"] == 3
    assert [case["id"] for case in payload["cases"]] == [101, 102]
    assert payload["cases"][0]["location"] == "Whitefield"
    assert payload["cases"][0]["assembly"] == "Mahadevapura"
    assert payload["cases"][0]["problem_domain"] == "Infrastructure & Utilities"
    assert payload["cases"][0]["problem_subdomain"] == "Water Supply"
    assert payload["cases"][0]["convergence_program_type"] == "Service Delivery Strengthening"
    assert payload["cases"][0]["created_at"].endswith("Z")
    assert payload["cases"][0]["updated_at"].endswith("Z")

    search_resp = client.get("/api/cases?search=Whitefield", headers=headers)
    assert search_resp.status_code == 200, search_resp.text
    assert {case["id"] for case in search_resp.json()["cases"]} == {101, 105}

    status_resp = client.get("/api/cases?status=in_progress", headers=headers)
    assert status_resp.status_code == 200, status_resp.text
    assert [case["id"] for case in status_resp.json()["cases"]] == [102]

    bucket_resp = client.get("/api/cases?bucket=other", headers=headers)
    assert bucket_resp.status_code == 200, bucket_resp.text
    assert {case["id"] for case in bucket_resp.json()["cases"]} == {103}

    export_resp = client.get("/api/cases/export?search=Whitefield", headers=headers)
    assert export_resp.status_code == 200, export_resp.text
    assert export_resp.headers["content-type"].startswith("text/csv")
    assert "NDL-2026-00101" in export_resp.text
    assert "Z" in export_resp.text


def test_briefcase_exposes_pending_contact_counts_without_listing_buffered_rows():
    _seed_database()
    now = _utcnow()
    with test_engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE cases
                SET case_metadata = :meta
                WHERE id = 101
                """
            ),
            {
                "meta": json.dumps(
                    {
                        "matched_value": "KR Puram",
                        "assembly_constituency": "KR Puram",
                        "summary": "Road issue in KR Puram",
                        "problem_domain": "Infrastructure & Utilities",
                        "problem_subdomain": "Roads & Bridges",
                        "convergence_program_type": "Service Delivery Strengthening",
                        "contact_thread_items": [
                            {
                                "issue_id": "thread-101-1",
                                "raw_message": "No water supply in Whitefield for 3 days",
                                "category": "Infrastructure & Utilities",
                                "problem_domain": "Infrastructure & Utilities",
                                "problem_subdomain": "Water Supply",
                                "convergence_program_type": "Service Delivery Strengthening",
                                "status": "new",
                                "matched_value": "Whitefield",
                                "assembly_constituency": "Mahadevapura",
                                "detected_language": "English",
                                "summary": "Water outage in Whitefield",
                                "created_at": (now - timedelta(minutes=4)).isoformat(),
                                "last_message_at": (now - timedelta(minutes=1)).isoformat(),
                                "contact_message_events": [{"message": "Road issue in KR Puram urgent", "created_at": now.isoformat()}],
                            }
                        ],
                    }
                ),
            },
        )

    headers = _auth_headers("mp_arun")
    resp = client.get("/api/cases", headers=headers)
    assert resp.status_code == 200, resp.text
    payload = resp.json()

    assert payload["total"] == 5
    ids = {case["id"] for case in payload["cases"]}
    assert 101 in ids
    first_case = next(case for case in payload["cases"] if case["id"] == 101)
    assert first_case["pending_contact_count"] == 1
    assert first_case["distinct_issue_count"] == 2
    assert first_case["contact_thread_state"] == "valid_multi_issue"

    detail_resp = client.get("/api/cases/101", headers=headers)
    assert detail_resp.status_code == 200, detail_resp.text
    detail = detail_resp.json()
    assert detail["distinct_issue_count"] == 2
    assert detail["contact_thread_state"] == "valid_multi_issue"
    assert len(detail["pending_contact_messages"]) == 1
    assert detail["pending_contact_messages"][0]["id"] == "thread-101-1"
    assert detail["pending_contact_messages"][0]["contact_message_events"][0]["message"] == "Road issue in KR Puram urgent"


def test_briefcase_status_notes_and_assignment_updates_are_logged():
    _seed_database()
    headers = _auth_headers("mp_arun")

    status_resp = client.patch("/api/cases/101/status", headers=headers, json={"status": "in_progress"})
    assert status_resp.status_code == 200, status_resp.text
    assert status_resp.json()["success"] is True

    update_resp = client.patch(
        "/api/cases/101",
        headers=headers,
        json={
            "notes_for_staff": "Called ward engineer and logged complaint.",
            "response_to_citizen": "We are working on this issue.",
            "assigned_to": "pr_meera",
        },
    )
    assert update_resp.status_code == 200, update_resp.text
    assert update_resp.json()["success"] is True

    detail_resp = client.get("/api/cases/101", headers=headers)
    assert detail_resp.status_code == 200, detail_resp.text
    detail = detail_resp.json()
    assert detail["status"] == "in_progress"
    assert detail["notes_for_staff"] == "Called ward engineer and logged complaint."
    assert detail["response_to_citizen"] == "We are working on this issue."
    assert detail["assigned_to"] == "pr_meera"

    activity_resp = client.get("/api/cases/101/activity", headers=headers)
    assert activity_resp.status_code == 200, activity_resp.text
    actions = [activity["action"] for activity in activity_resp.json()["activities"]]
    assert "status_change" in actions
    assert "case_updated" in actions


def test_emergency_case_sends_no_citizen_ack_and_flag_says_so(monkeypatch):
    """Policy: emergencies alert staff but never auto-reply to the citizen
    (no false hope of immediate rescue). citizen_ack_sent must reflect that."""
    _seed_database()
    sent = []
    monkeypatch.setattr(main, "send_whatsapp_message", lambda *args, **kwargs: sent.append(args))
    monkeypatch.setattr(main, "_schedule_case_clarification_follow_up", lambda *a, **k: None)
    monkeypatch.setattr(main, "_cancel_case_clarification_follow_up", lambda *a, **k: None)
    import modules.emergency_intake as emergency_intake
    monkeypatch.setattr(emergency_intake, "process_emergency_case", lambda **kwargs: None)

    def _enrichment(is_emergency):
        return {
            "status": "emergency" if is_emergency else "new",
            "category": "Emergency" if is_emergency else "Infrastructure & Utilities",
            "detected_language": "English",
            "citizen_ack_message": "Acknowledgement text",
            "meta_data": {},
            "problem_domain": None,
            "problem_subdomain": None,
            "convergence_program_type": None,
            "is_emergency_complaint": is_emergency,
            "emergency_keyword_match": is_emergency,
            "final_constituency": "Unknown",
            "political_reply": "Held AI reply",
        }

    main._save_case_enrichment_and_respond(
        case_id=101,
        sender="919810000101",
        current_tenant=1,
        message_body="Accident hua hai, ambulance bhejo jaldi",
        wa_phone_id="15550001111",
        enrichment=_enrichment(True),
    )
    assert sent == []  # nothing goes to the citizen
    with test_engine.connect() as conn:
        meta_raw = conn.execute(
            text("SELECT case_metadata FROM cases WHERE id = 101")
        ).scalar()
    meta = meta_raw if isinstance(meta_raw, dict) else json.loads(meta_raw)
    assert meta["citizen_ack_sent"] is False

    main._save_case_enrichment_and_respond(
        case_id=102,
        sender="919810000102",
        current_tenant=1,
        message_body="Streetlight kharab hai",
        wa_phone_id="15550001111",
        enrichment=_enrichment(False),
    )
    assert len(sent) == 1  # ordinary grievances still get the ack
    with test_engine.connect() as conn:
        meta_raw = conn.execute(
            text("SELECT case_metadata FROM cases WHERE id = 102")
        ).scalar()
    meta = meta_raw if isinstance(meta_raw, dict) else json.loads(meta_raw)
    assert meta["citizen_ack_sent"] is True


def test_briefcase_manual_category_confirmation_validates_and_logs():
    _seed_database()
    headers = _auth_headers("mp_arun")

    bad_domain = client.patch("/api/cases/101", headers=headers, json={"problem_domain": "Not A Real Domain"})
    assert bad_domain.status_code == 400

    orphan_subdomain = client.patch("/api/cases/101", headers=headers, json={"problem_subdomain": "Water Supply"})
    assert orphan_subdomain.status_code == 400

    wrong_pair = client.patch(
        "/api/cases/101",
        headers=headers,
        json={"problem_domain": "Infrastructure & Utilities", "problem_subdomain": "Pension"},
    )
    assert wrong_pair.status_code == 400

    ok = client.patch(
        "/api/cases/101",
        headers=headers,
        json={"problem_domain": "Infrastructure & Utilities", "problem_subdomain": "Water Supply"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["success"] is True

    detail = client.get("/api/cases/101", headers=headers).json()
    assert detail["problem_domain"] == "Infrastructure & Utilities"
    assert detail["problem_subdomain"] == "Water Supply"
    assert detail["category"] == "Infrastructure & Utilities"
    assert detail["convergence_program_type"] == "Public Asset Upgrade"

    meta = detail.get("case_metadata")
    if isinstance(meta, str):
        meta = json.loads(meta)
    assert meta["problem_domain"] == "Infrastructure & Utilities"
    assert meta["problem_subdomain"] == "Water Supply"
    assert meta["needs_review"] is False
    assert meta["classification_confirmed"]["by"] == "mp_arun"
    assert meta["classification_confirmed"]["source"] == "manual"

    activity_resp = client.get("/api/cases/101/activity", headers=headers)
    actions = [activity["action"] for activity in activity_resp.json()["activities"]]
    assert "category_confirmed" in actions


def test_briefcase_notify_send_is_mp_only_and_auto_resolves(monkeypatch):
    _seed_database()
    outbound = []

    monkeypatch.setattr(api_router, "get_tenant_phone_number_id", lambda _tid: "15551636821")
    monkeypatch.setattr(
        "modules.whatsapp.send_whatsapp_message",
        lambda phone, message, phone_number_id=None, **kwargs: outbound.append((phone, message, phone_number_id)),
    )

    pr_resp = client.post(
        "/api/cases/101/notify/send",
        headers=_auth_headers("pr_meera"),
        json={"message": "Custom update from PR"},
    )
    assert pr_resp.status_code == 403, pr_resp.text

    notify_resp = client.post(
        "/api/cases/101/notify/send",
        headers=_auth_headers("mp_arun"),
        json={"message": "Water tanker arranged for tonight."},
    )
    assert notify_resp.status_code == 200, notify_resp.text
    assert notify_resp.json()["success"] is True
    assert outbound == [("919810000101", "Water tanker arranged for tonight.", "15551636821")]

    detail_resp = client.get("/api/cases/101", headers=_auth_headers("mp_arun"))
    assert detail_resp.status_code == 200, detail_resp.text
    detail = detail_resp.json()
    assert detail["status"] == "resolved"
    assert detail["response_to_citizen"] == "Water tanker arranged for tonight."

    activity_resp = client.get("/api/cases/101/activity", headers=_auth_headers("mp_arun"))
    assert activity_resp.status_code == 200, activity_resp.text
    latest = activity_resp.json()["activities"][0]
    assert latest["action"] == "citizen_notified"
    assert latest["new_value"] == "resolved"


def test_briefcase_delete_restore_and_deleted_list_respect_roles():
    _seed_database()

    forbidden_delete = client.delete("/api/cases/102", headers=_auth_headers("staff_raj"))
    assert forbidden_delete.status_code == 403, forbidden_delete.text

    delete_resp = client.delete("/api/cases/102", headers=_auth_headers("pr_meera"))
    assert delete_resp.status_code == 200, delete_resp.text
    assert delete_resp.json()["success"] is True

    active_list_resp = client.get("/api/cases", headers=_auth_headers("mp_arun"))
    assert active_list_resp.status_code == 200, active_list_resp.text
    assert 102 not in {case["id"] for case in active_list_resp.json()["cases"]}

    deleted_list_resp = client.get("/api/cases/deleted", headers=_auth_headers("mp_arun"))
    assert deleted_list_resp.status_code == 200, deleted_list_resp.text
    deleted_ids = {case["id"] for case in deleted_list_resp.json()["cases"]}
    assert 102 in deleted_ids
    assert 106 in deleted_ids
    assert 107 not in deleted_ids

    forbidden_restore = client.patch("/api/cases/102/restore", headers=_auth_headers("staff_raj"), json={})
    assert forbidden_restore.status_code == 403, forbidden_restore.text

    restore_resp = client.patch("/api/cases/102/restore", headers=_auth_headers("pr_meera"), json={})
    assert restore_resp.status_code == 200, restore_resp.text
    assert restore_resp.json()["success"] is True

    restored_list_resp = client.get("/api/cases", headers=_auth_headers("mp_arun"))
    assert restored_list_resp.status_code == 200, restored_list_resp.text
    assert 102 in {case["id"] for case in restored_list_resp.json()["cases"]}


def test_briefcase_owner_can_delete_view_deleted_and_restore_cases():
    _seed_database()

    delete_resp = client.delete("/api/cases/103", headers=_auth_headers("owner_arun"))
    assert delete_resp.status_code == 200, delete_resp.text
    assert delete_resp.json()["success"] is True

    active_list_resp = client.get("/api/cases", headers=_auth_headers("owner_arun"))
    assert active_list_resp.status_code == 200, active_list_resp.text
    assert 103 not in {case["id"] for case in active_list_resp.json()["cases"]}

    deleted_list_resp = client.get("/api/cases/deleted", headers=_auth_headers("owner_arun"))
    assert deleted_list_resp.status_code == 200, deleted_list_resp.text
    assert 103 in {case["id"] for case in deleted_list_resp.json()["cases"]}

    restore_resp = client.patch("/api/cases/103/restore", headers=_auth_headers("owner_arun"), json={})
    assert restore_resp.status_code == 200, restore_resp.text
    assert restore_resp.json()["success"] is True

    restored_list_resp = client.get("/api/cases", headers=_auth_headers("owner_arun"))
    assert restored_list_resp.status_code == 200, restored_list_resp.text
    assert 103 in {case["id"] for case in restored_list_resp.json()["cases"]}


def test_briefcase_similar_cases_are_tenant_scoped():
    _seed_database()

    similar_resp = client.get("/api/cases/101/similar", headers=_auth_headers("mp_arun"))
    assert similar_resp.status_code == 200, similar_resp.text
    payload = similar_resp.json()

    similar_ids = {case["id"] for case in payload["cases"]}
    assert 105 in similar_ids
    assert 201 not in similar_ids
    assert payload["source_phone"] == "919810000101"
    assert payload["source_category"] == "Infrastructure & Utilities"


def test_briefcase_escalation_endpoints_are_removed():
    _seed_database()
    headers = _auth_headers("mp_arun")

    create_resp = client.post("/api/escalations", headers=headers, json={"case_id": 101})
    assert create_resp.status_code == 404, create_resp.text

    history_resp = client.get("/api/escalations?case_id=101", headers=headers)
    assert history_resp.status_code == 404, history_resp.text


def test_briefcase_pilot_flow_assign_note_notify_resolves(monkeypatch):
    _seed_database()
    headers = _auth_headers("mp_arun")
    outbound = []

    # Safe E2E: prove the WhatsApp path without sending a real external message.
    monkeypatch.setattr(api_router, "get_tenant_phone_number_id", lambda _tid: "15551636821")
    monkeypatch.setattr(
        "modules.whatsapp.send_whatsapp_message",
        lambda phone, message, phone_number_id=None, **kwargs: outbound.append((phone, message, phone_number_id)),
    )

    created_resp = client.get("/api/cases/101", headers=headers)
    assert created_resp.status_code == 200, created_resp.text
    assert created_resp.json()["status"] == "new"

    assign_note_resp = client.patch(
        "/api/cases/101",
        headers=headers,
        json={
            "assigned_to": "pr_meera",
            "notes_for_staff": "Pilot E2E: assigned to PR for constituency follow-up.",
            "response_to_citizen": "Pilot E2E update: your water supply grievance is being reviewed by the constituency team.",
        },
    )
    assert assign_note_resp.status_code == 200, assign_note_resp.text
    assert assign_note_resp.json()["success"] is True

    after_assign = client.get("/api/cases/101", headers=headers).json()
    assert after_assign["assigned_to"] == "pr_meera"
    assert after_assign["notes_for_staff"] == "Pilot E2E: assigned to PR for constituency follow-up."

    notify_resp = client.post(
        "/api/cases/101/notify/send",
        headers=headers,
        json={"message": "Pilot E2E update: your complaint has been resolved by the MP office."},
    )
    assert notify_resp.status_code == 200, notify_resp.text
    assert notify_resp.json()["success"] is True
    assert outbound == [
        (
            "919810000101",
            "Pilot E2E update: your complaint has been resolved by the MP office.",
            "15551636821",
        )
    ]

    final_detail = client.get("/api/cases/101", headers=headers).json()
    assert final_detail["status"] == "resolved"
    assert final_detail["assigned_to"] == "pr_meera"
    assert final_detail["response_to_citizen"] == "Pilot E2E update: your complaint has been resolved by the MP office."

    activity_actions = [
        activity["action"]
        for activity in client.get("/api/cases/101/activity", headers=headers).json()["activities"]
    ]
    assert "case_updated" in activity_actions
    assert "citizen_notified" in activity_actions


def test_case_source_media_metadata_and_download():
    _seed_database()
    headers = _auth_headers("mp_arun")

    with test_engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO case_media (
                    tenant_id, case_id, source, media_type, mime_type,
                    file_name, media_data, caption, extracted_text, created_at
                ) VALUES (
                    1, 101, 'whatsapp', 'image', 'image/png',
                    'source.png', :data, 'road photo', 'Whitefield road issue', :now
                )
                """
            ),
            {"data": b"\x89PNG\r\nsource", "now": _utcnow()},
        )

    detail_resp = client.get("/api/cases/101", headers=headers)
    assert detail_resp.status_code == 200, detail_resp.text
    detail = detail_resp.json()
    assert detail["media_count"] == 1
    assert detail["media"][0]["media_type"] == "image"
    assert detail["media"][0]["mime_type"] == "image/png"
    assert detail["media"][0]["caption"] == "road photo"

    media_id = detail["media"][0]["id"]
    media_resp = client.get(f"/api/cases/101/media/{media_id}", headers=headers)
    assert media_resp.status_code == 200, media_resp.text
    assert media_resp.headers["content-type"] == "image/png"
    assert media_resp.content == b"\x89PNG\r\nsource"


def test_case_audio_source_media_metadata_and_download():
    _seed_database()
    headers = _auth_headers("mp_arun")

    with test_engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO case_media (
                    tenant_id, case_id, source, media_type, mime_type,
                    file_name, media_data, caption, extracted_text, created_at
                ) VALUES (
                    1, 101, 'whatsapp', 'audio', 'audio/ogg',
                    'voice-note.ogg', :data, '', 'voice transcript', :now
                )
                """
            ),
            {"data": b"OggSvoice", "now": _utcnow()},
        )

    detail_resp = client.get("/api/cases/101", headers=headers)
    assert detail_resp.status_code == 200, detail_resp.text
    detail = detail_resp.json()
    assert detail["media_count"] == 1
    assert detail["media"][0]["media_type"] == "audio"
    assert detail["media"][0]["mime_type"] == "audio/ogg"

    media_id = detail["media"][0]["id"]
    media_resp = client.get(f"/api/cases/101/media/{media_id}", headers=headers)
    assert media_resp.status_code == 200, media_resp.text
    assert media_resp.headers["content-type"] == "audio/ogg"
    assert media_resp.content == b"OggSvoice"


def test_manual_geography_update_locks_case_metadata():
    _seed_database()
    headers = _auth_headers("mp_arun")

    update_resp = client.patch(
        "/api/cases/101",
        headers=headers,
        json={"location": "Santibastawad", "assembly": "Belgaum Rural"},
    )
    assert update_resp.status_code == 200, update_resp.text
    assert update_resp.json()["success"] is True

    detail_resp = client.get("/api/cases/101", headers=headers)
    assert detail_resp.status_code == 200, detail_resp.text
    detail = detail_resp.json()
    assert detail["location"] == "Santibastawad"
    assert detail["assembly"] == "Belgaum Rural"
    assert detail["case_metadata"]["matched_value"] == "Santibastawad"
    assert detail["case_metadata"]["assembly_constituency"] == "Belgaum Rural"
    assert detail["case_metadata"]["geography_confidence"] == "manual"
    assert detail["case_metadata"]["geography_locked"] is True


def test_manual_geography_update_does_not_create_reusable_alias():
    _seed_database()
    headers = _auth_headers("mp_arun")

    update_resp = client.patch(
        "/api/cases/101",
        headers=headers,
        json={"location": "Teachers Colony", "assembly": "Belgaum South"},
    )
    assert update_resp.status_code == 200, update_resp.text
    assert update_resp.json()["success"] is True

    with test_engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT override_type, key, value
                FROM tenant_overrides
                WHERE tenant_id = 1
                  AND override_type = 'geo_manual_override'
                  AND key = 'teachers colony'
                """
            )
        ).mappings().first()
    assert row is None

    detail_resp = client.get("/api/cases/101", headers=headers)
    assert detail_resp.status_code == 200, detail_resp.text
    detail = detail_resp.json()
    assert detail["location"] == "Teachers Colony"
    assert detail["assembly"] == "Belgaum South"
    assert detail["case_metadata"]["geography_confidence"] == "manual"
    assert detail["case_metadata"]["geography_locked"] is True


def test_audio_media_intake_passes_voice_note_as_source_media(monkeypatch):
    captured = {}

    monkeypatch.setattr(main, "_resolve_tenant", lambda _receiver_number: 1)
    monkeypatch.setattr(main, "get_tenant_phone_number_id", lambda _tenant_id: "15550001111")
    monkeypatch.setattr(main, "download_meta_media", lambda _media_id: (b"OggSvoice", "audio/ogg"))
    monkeypatch.setattr(
        main,
        "normalize_media_complaint",
        lambda *_args, **_kwargs: type(
            "Normalized",
            (),
            {
                "ok": True,
                "text": "Shanti Baswad road issue",
                "error": "",
                "mentioned_location_roman": "Shanti Baswad",
                "mentioned_location_original": "शांती बसवाड",
                "extracted_language": "Marathi",
            },
        )(),
    )

    def _capture_process(
        sender,
        message_body,
        receiver_number,
        msg_id,
        media_source=None,
        language_hint=None,
        resolver_message_body=None,
        resolver_fallback_message_body=None,
        wa_reply_to_msg_id=None,
        # Accept newer intake kwargs (inbound_ledger_id, existing_case_id, …)
        # so this stub stays signature-compatible with production.
        **kwargs,
    ):
        captured["sender"] = sender
        captured["message_body"] = message_body
        captured["receiver_number"] = receiver_number
        captured["msg_id"] = msg_id
        captured["media_source"] = media_source
        captured["language_hint"] = language_hint
        captured["resolver_message_body"] = resolver_message_body
        captured["resolver_fallback_message_body"] = resolver_fallback_message_body
        captured["wa_reply_to_msg_id"] = wa_reply_to_msg_id

    monkeypatch.setattr(main, "_process_incoming_message", _capture_process)

    main._process_citizen_media_complaint(
        sender="919999999999",
        media_id="wamid.audio.1",
        mime_type="audio/ogg",
        receiver_number="+919000000001",
        caption="",
        media_type="audio",
        msg_id="wamid-msg-1",
    )

    assert captured["media_source"]["media_type"] == "audio"
    assert captured["media_source"]["mime_type"] == "audio/ogg"
    assert captured["media_source"]["media_bytes"] == b"OggSvoice"
    assert captured["media_source"]["extracted_text"] == "Shanti Baswad road issue"


def test_briefcase_newest_grouping_ignores_staff_updated_at():
    older = {
        "id": 1,
        "user_phone": "919800000001",
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-08-17T12:00:00",
        "case_metadata": {},
    }
    newer = {
        "id": 2,
        "user_phone": "919800000002",
        "created_at": "2026-06-01T00:00:00",
        "updated_at": "2026-06-01T00:00:00",
        "case_metadata": {},
    }
    rows = api_router._group_briefcase_cases([older, newer], sort="newest")
    assert [row["id"] for row in rows] == [2, 1]

    updated_rows = api_router._group_briefcase_cases([older, newer], sort="updated")
    assert [row["id"] for row in updated_rows] == [1, 2]

