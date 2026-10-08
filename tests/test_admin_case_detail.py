"""Admin case investigation detail: read-only, admin-only, tenant-scoped.

Covers the Phase 4 additive exposure on GET /api/admin/cases/{id}
(priority, assignment, govt_* fields, case_activity_log, WhatsApp ledger
rows, labelled AI metadata) and the real explorer filters. Nothing in these
endpoints may write, and citizen names must never be exposed.
"""
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
TEST_DB_URL = "sqlite:///./test_admin_case_detail.db"

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
import core.db_helpers as db_helpers
import main
import sansadx_backend.db as dbmod
from sansadx_backend.db import Base, GovtPortal, hash_password


test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False)
client = TestClient(main.app, raise_server_exceptions=False)

NOW = datetime(2026, 10, 1, 9, 30, 0)
RAW_MESSAGE = "Paani nahi aa raha hai ward 5 mein teen din se"


def _utcnow():
    return datetime.now(timezone.utc)


def _headers(role="sysadmin", sub="sysadmin"):
    token = jwt.encode(
        {"sub": sub, "tenant_id": 1, "role": role, "iat": _utcnow().timestamp(), "exp": _utcnow().timestamp() + 3600},
        TEST_JWT_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def _seed(with_inbound_table=True):
    _seed_rows(with_inbound_table)
    _seed_portal()


def _seed_rows(with_inbound_table):
    dbmod.engine = test_engine
    dbmod.SessionLocal = TestSession
    db_helpers.engine = test_engine
    main.engine = test_engine
    admin_api.engine = test_engine
    admin_api.JWT_SECRET = TEST_JWT_SECRET
    admin_api.ADMIN_JWT_SECRET = TEST_JWT_SECRET
    Base.metadata.create_all(bind=test_engine)
    with test_engine.begin() as conn:
        # wa_inbound_messages is created by main.py's startup migration, not
        # the ORM metadata, so the harness builds the columns the endpoint reads.
        conn.execute(text("DROP TABLE IF EXISTS wa_inbound_messages"))
        if with_inbound_table:
            conn.execute(text(
                "CREATE TABLE wa_inbound_messages (id INTEGER PRIMARY KEY, meta_message_id VARCHAR, tenant_id INTEGER, "
                "sender_phone VARCHAR, message_type VARCHAR, status VARCHAR, case_id INTEGER, raw_payload TEXT, "
                "created_at TIMESTAMP, processed_at TIMESTAMP)"
            ))
        for table_name in (
            "wa_outbound_messages", "case_activity_log", "contacts", "govt_portals",
            "token_blocklist", "users", "cases", "tenants",
        ):
            conn.execute(text(f"DELETE FROM {table_name}"))  # nosec B608

        for tid, name in ((1, "Admin Home"), (2, "Belagavi MP"), (3, "Other MP")):
            conn.execute(
                text("INSERT INTO tenants (id, name, constituency, subscription_plan, is_active, created_at, config) VALUES (:id, :n, :c, 'Pro', 1, :now, '{}')"),
                {"id": tid, "n": name, "c": f"Constituency {tid}", "now": NOW},
            )
        conn.execute(
            text("INSERT INTO users (tenant_id, username, password_hash, role, constituency, house, display_name, is_active) VALUES (1, 'sysadmin', :pw, 'sysadmin', 'X', 'Lok Sabha', 'System Admin', true)"),
            {"pw": hash_password("AdminPass1!")},
        )
        conn.execute(
            text("INSERT INTO users (tenant_id, username, password_hash, role, constituency, house, display_name, is_active) VALUES (2, 'mp_staff', :pw, 'staff', 'X', 'Lok Sabha', 'MP Staff', true)"),
            {"pw": hash_password("StaffPass1!")},
        )
        meta = {
            "summary": "No water supply in Ward 5 for three days.",
            "ai_category": "Water Supply",
            "ai_subcategory": "No supply",
            "ai_confidence": 0.82,
            "category_decided_by": "ai",
            "needs_review": True,
            "classification_mode": "shadow",
            "detected_language": "hinglish",
            "english_translation": "Water has not come in ward 5 for three days",
            "english_translation_source": RAW_MESSAGE,
            "department": "Jal Board",
            "person": "Ramesh Kumar",
            "matched_value": "Ward 5",
            "assembly_constituency": "Belagavi North",
            "geography_confidence": "high",
            "geography_source": "gazetteer",
        }
        conn.execute(
            text(
                "INSERT INTO cases (id, tenant_id, user_phone, raw_message, category, status, is_critical, priority, assigned_to, "
                "case_metadata, created_at, updated_at, status_changed_at, case_ref, govt_portal_id, govt_department, "
                "govt_reference_number, govt_status, govt_status_updated_at, notes_for_staff, is_deleted) VALUES "
                "(101, 2, '+919800000101', :raw, 'Water Supply', 'in_progress', 1, 'critical', 'pa_rao', :meta, :created, :updated, "
                ":updated, 'BGM-0101', 7, 'Water Resources', 'KJ/2026/5512', 'forwarded', :updated, 'Called JE on Monday', 0)"
            ),
            {"raw": RAW_MESSAGE, "meta": json.dumps(meta), "created": NOW - timedelta(days=3), "updated": NOW - timedelta(days=1)},
        )
        stale_meta = {"english_translation": "old translation", "english_translation_source": "an earlier message"}
        conn.execute(
            text(
                "INSERT INTO cases (id, tenant_id, user_phone, raw_message, category, status, priority, assigned_to, case_metadata, created_at, is_deleted) "
                "VALUES (102, 3, '+919800000102', 'Road broken', 'Roads', 'new', 'low', NULL, :meta, :created, 0)"
            ),
            {"meta": json.dumps(stale_meta), "created": NOW - timedelta(days=1)},
        )
        conn.execute(text(
            "INSERT INTO contacts (tenant_id, phone, display_name) VALUES (2, '+919800000101', 'Ramesh Kumar')"
        ))
        # Activity for case 101 in its own tenant, plus a mis-scoped row that
        # claims case 101 under another tenant — it must never be returned.
        for i, (tid, action, old, new) in enumerate((
            (2, "status_change", "new", "in_progress"),
            (2, "assigned", None, "pa_rao"),
            (3, "status_change", "in_progress", "resolved"),
        )):
            conn.execute(
                text("INSERT INTO case_activity_log (tenant_id, case_id, username, action, old_value, new_value, details, created_at) VALUES (:tid, 101, 'pa_rao', :a, :o, :n, NULL, :at)"),
                {"tid": tid, "a": action, "o": old, "n": new, "at": NOW - timedelta(days=2, hours=-i)},
            )
        conn.execute(
            text("INSERT INTO wa_outbound_messages (tenant_id, case_id, to_number, message_body, template_key, status, created_at, sent_at, request_payload, meta_response) VALUES (2, 101, '+919800000101', 'We have registered your complaint.', 'ack', 'sent', :at, :at, '{}', '{}')"),
            {"at": NOW - timedelta(days=3)},
        )
        conn.execute(
            text("INSERT INTO wa_outbound_messages (tenant_id, case_id, to_number, message_body, status, created_at, request_payload, meta_response) VALUES (3, 101, '+919800000999', 'cross-tenant leak', 'sent', :at, '{}', '{}')"),
            {"at": NOW - timedelta(days=3)},
        )
        if with_inbound_table:
            conn.execute(
                text("INSERT INTO wa_inbound_messages (id, meta_message_id, tenant_id, sender_phone, message_type, status, case_id, raw_payload, created_at, processed_at) VALUES (1, 'wamid.1', 2, '+919800000101', 'text', 'processed', 101, '{\"secret\": \"raw\"}', :at, :at)"),
                {"at": NOW - timedelta(days=3)},
            )


def _seed_portal():
    # ORM insert so every NOT NULL column picks up its model default.
    with TestSession() as session:
        session.add(GovtPortal(id=7, state="Karnataka", portal_name="Karnataka Janaspandana", portal_type="state_branded"))
        session.commit()


def _snapshot():
    with test_engine.connect() as conn:
        return {
            "cases": [tuple(r) for r in conn.execute(text("SELECT * FROM cases ORDER BY id"))],
            "activity": conn.execute(text("SELECT COUNT(*) FROM case_activity_log")).scalar(),
            "outbound": conn.execute(text("SELECT COUNT(*) FROM wa_outbound_messages")).scalar(),
        }


def test_case_detail_requires_admin():
    _seed()
    assert client.get("/api/admin/cases/101").status_code in (401, 403)
    assert client.get("/api/admin/cases/101", headers=_headers(role="staff", sub="mp_staff")).status_code == 403
    assert client.get("/api/admin/cases/explorer", headers=_headers(role="staff", sub="mp_staff")).status_code == 403


def test_case_detail_exposes_recorded_fields_read_only():
    _seed()
    before = _snapshot()
    resp = client.get("/api/admin/cases/101", headers=_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert _snapshot() == before  # GET wrote nothing

    # Existing contract is unchanged.
    assert body["id"] == 101 and body["status"] == "in_progress" and body["phone"] == "+919800000101"
    assert body["notes_for_staff"] == "Called JE on Monday"
    # Additive, recorded (staff/system) fields.
    assert body["tenant_id"] == 2
    assert body["case_ref"] == "BGM-0101"
    assert body["priority"] == "critical"
    assert body["assigned_to"] == "pa_rao"
    assert body["is_deleted"] is False
    assert body["timestamps"]["status_changed_at"].startswith("2026-09-30")
    gov = body["government"]
    assert gov["status"] == "forwarded"
    assert gov["department"] == "Water Resources"
    assert gov["reference_number"] == "KJ/2026/5512"
    assert gov["portal"] == {"name": "Karnataka Janaspandana", "state": "Karnataka", "type": "state_branded"}


def test_case_detail_labels_ai_fields_and_withholds_names():
    _seed()
    body = client.get("/api/admin/cases/101", headers=_headers()).json()
    analysis = body["analysis"]
    assert analysis["summary"] == "No water supply in Ward 5 for three days."
    assert analysis["ai_category"] == "Water Supply"
    assert analysis["ai_confidence"] == 0.82
    assert analysis["category_decided_by"] == "ai"
    assert analysis["needs_review"] is True
    assert analysis["classification_mode"] == "shadow"
    assert analysis["language"] == "hinglish"
    assert analysis["english_translation"] == "Water has not come in ward 5 for three days"
    assert analysis["department_mentioned"] == "Jal Board"
    assert analysis["geography"]["confidence"] == "high"

    serialized = json.dumps(body)
    assert "Ramesh Kumar" not in serialized  # neither contacts.display_name nor meta.person
    assert "person" not in analysis
    assert "display_name" not in serialized
    assert "raw_payload" not in serialized and '"secret"' not in serialized


def test_stale_translation_is_not_presented():
    _seed()
    body = client.get("/api/admin/cases/102", headers=_headers()).json()
    assert body["analysis"]["english_translation"] is None
    assert body["priority"] == "low" and body["assigned_to"] is None
    assert body["government"]["portal"] is None
    assert body["activity"] == []


def test_activity_and_messages_are_tenant_scoped():
    _seed()
    body = client.get("/api/admin/cases/101", headers=_headers()).json()
    assert [(a["action"], a["new_value"]) for a in body["activity"]] == [
        ("status_change", "in_progress"),
        ("assigned", "pa_rao"),
    ]
    outbound = body["messages"]["outbound"]
    assert [m["body"] for m in outbound] == ["We have registered your complaint."]
    assert outbound[0]["status"] == "sent" and outbound[0]["template_key"] == "ack"
    inbound = body["messages"]["inbound"]
    assert inbound == [{
        "id": 1, "status": "processed", "message_type": "text",
        "created_at": inbound[0]["created_at"], "processed_at": inbound[0]["processed_at"],
    }]


def test_missing_inbound_ledger_marks_section_unavailable():
    _seed(with_inbound_table=False)
    resp = client.get("/api/admin/cases/101", headers=_headers())
    assert resp.status_code == 200
    assert resp.json()["messages"]["inbound"] is None
    assert len(resp.json()["messages"]["outbound"]) == 1


def test_case_routes_expose_no_mutations():
    _seed()
    before = _snapshot()
    for method in ("patch", "put", "delete", "post"):
        resp = getattr(client, method)("/api/admin/cases/101", headers=_headers())
        assert resp.status_code in (404, 405), method
    assert _snapshot() == before


def test_explorer_rows_and_real_filters():
    _seed()
    resp = client.get("/api/admin/cases/explorer", headers=_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert data["filter_options"]["priorities"] == ["critical", "high", "standard", "low"]
    row = next(c for c in data["cases"] if c["id"] == 101)
    assert row["priority"] == "critical" and row["assigned_to"] == "pa_rao"
    assert row["tenant_id"] == 2 and row["case_ref"] == "BGM-0101" and row["is_deleted"] is False

    critical = client.get("/api/admin/cases/explorer?priority=critical", headers=_headers()).json()
    assert [c["id"] for c in critical["cases"]] == [101]
    unassigned = client.get("/api/admin/cases/explorer?assignment=unassigned", headers=_headers()).json()
    assert [c["id"] for c in unassigned["cases"]] == [102]
    assigned = client.get("/api/admin/cases/explorer?assignment=assigned&mp_id=2", headers=_headers()).json()
    assert [c["id"] for c in assigned["cases"]] == [101]

    assert client.get("/api/admin/cases/explorer?priority=urgent", headers=_headers()).status_code == 400
    assert client.get("/api/admin/cases/explorer?assignment=me", headers=_headers()).status_code == 400
