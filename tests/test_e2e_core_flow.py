import os
import sys
import time
import json
import hmac
import hashlib
from datetime import datetime, timedelta

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
TEST_DB_URL = "sqlite:///./test_e2e_core_flow.db"

os.environ["JWT_SECRET"] = TEST_JWT_SECRET
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["ENV"] = "test"
os.environ["OPENAI_API_KEY"] = "sk-test-fake-key-for-testing"
os.environ["META_APP_SECRET"] = ""
os.environ["META_PHONE_NUMBER_ID"] = "15551636821"
os.environ["META_ACCESS_TOKEN"] = "FAKE_ACCESS_TOKEN"
os.environ["META_VERIFY_TOKEN"] = "test-verify-token-123"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@event.listens_for(Engine, "connect")
def _sqlite_register_pg_lock_functions(dbapi_connection, connection_record):
    try:
        dbapi_connection.create_function("pg_try_advisory_lock", 1, lambda _key: 1)
        dbapi_connection.create_function("pg_advisory_unlock", 1, lambda _key: 1)
        dbapi_connection.create_function("pg_try_advisory_xact_lock", 1, lambda _key: 1)
    except Exception:
        pass

import main
import api_router
import core.db_helpers as db_helpers
import modules.whatsapp as whatsapp_module
from main import app
import sansadx_backend.db as dbmod
from sansadx_backend.db import Base, hash_password


test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False)
client = TestClient(app, raise_server_exceptions=False)


def _seed_database():
    dbmod.engine = test_engine
    dbmod.SessionLocal = TestSession
    db_helpers.engine = test_engine
    main.engine = test_engine
    api_router.engine = test_engine

    Base.metadata.create_all(bind=test_engine)

    with test_engine.begin() as conn:
        for table_name in (
            "incident_clusters",
            "wa_message_dedup",
            "activity_history",
            "case_activity_log",
            "contacts",
            "cases",
            "users",
            "tenants",
            "tenant_overrides",
        ):
            conn.execute(text(f"DELETE FROM {table_name}"))  # nosec B608

        now = datetime.utcnow()
        conn.execute(
            text(
                """
                INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active, created_at)
                VALUES (1, 'Arun Kumar', 'Bangalore North', '+919000000001', 'Pro', 1, :now)
                """
            ),
            {"now": now},
        )

        conn.execute(
            text(
                """
                INSERT INTO users (tenant_id, username, password_hash, role, constituency, house)
                VALUES (1, 'mp_arun', :password_hash, 'mp', 'Bangalore North', 'Lok Sabha')
                """
            ),
            {"password_hash": hash_password("ValidPass1!")},
        )

        conn.execute(
            text(
                """
                INSERT INTO tenant_overrides (tenant_id, override_type, key, value, created_at)
                VALUES (1, 'geo_override', 'Whitefield', 'Mahadevapura', :now)
                """
            ),
            {"now": now},
        )
        conn.execute(
            text(
                """
                INSERT INTO tenant_overrides (tenant_id, override_type, key, value, created_at)
                VALUES (1, 'phone_mapping', '+15551636821', '1', :now)
                """
            ),
            {"now": now},
        )


def _make_token(username: str, tenant_id: int, role: str = "mp") -> str:
    payload = {
        "sub": username,
        "tid": tenant_id,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=8),
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


def _whatsapp_payload(sender: str, body: str, receiver: str = "15551636821") -> dict:
    return {
        "entry": [{
            "changes": [{
                "value": {
                    "metadata": {"display_phone_number": receiver},
                    "messages": [{
                        "from": sender,
                        "type": "text",
                        "text": {"body": body},
                    }],
                }
            }]
        }]
    }


def _post_signed_webhook(payload: dict):
    raw_body = json.dumps(payload).encode("utf-8")
    signature = "sha256=" + hmac.new(
        b"test-meta-app-secret",
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return client.post(
        "/whatsapp/webhook",
        data=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        },
    )


def _fetch_case_by_phone(phone: str):
    with test_engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT id, user_phone, category, problem_domain, status, response_to_citizen, "
                "raw_message, case_metadata, is_critical "
                "FROM cases WHERE user_phone = :phone ORDER BY created_at DESC LIMIT 1"
            ),
            {"phone": phone},
        ).mappings().first()
    return dict(row) if row else None


def _cluster_rows():
    with test_engine.connect() as conn:
        return conn.execute(
            text(
                "SELECT id, raw_case_ids, alert_level, unique_sender_count, alert_acknowledged "
                "FROM incident_clusters ORDER BY created_at DESC"
            )
        ).mappings().all()


def _cases_for_phone(phone: str):
    with test_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, user_phone, category, status, raw_message, case_metadata "
                "FROM cases WHERE user_phone = :phone ORDER BY created_at ASC, id ASC"
            ),
            {"phone": phone},
        ).mappings().all()
    return [dict(row) for row in rows]


def _inbound_rows_for_sender(phone: str):
    with test_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, meta_message_id, status, case_id "
                "FROM wa_inbound_messages WHERE sender_phone = :phone ORDER BY id ASC"
            ),
            {"phone": phone},
        ).mappings().all()
    return [dict(row) for row in rows]


def _wait_for(predicate, timeout_seconds: float = 2.0, interval_seconds: float = 0.05):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(interval_seconds)
    return predicate()


def test_citizen_webhook_to_notify_and_resolve_flow(monkeypatch):
    _seed_database()
    monkeypatch.setattr(main, "META_APP_SECRET", "test-meta-app-secret")

    intake_messages = []
    citizen_notifications = []

    monkeypatch.setattr(
        main,
        "ask_chatgpt_agent",
        lambda prompt, tenant_id=None: {
            "status": "new",
            "detected_language": "English",
            "political_response": "Your grievance has been noted and will be reviewed.",
            "grievance_data": {
                "problem_domain": "Infrastructure & Utilities",
                "problem_subdomain": "Water Supply",
                "convergence_program_type": "Service Delivery Strengthening",
                "categories": ["Infrastructure & Utilities"],
                "location": "Whitefield",
                "department": "BWSSB",
                "summary": "No water supply in Whitefield for three days",
            },
        },
    )
    monkeypatch.setattr(
        main,
        "send_whatsapp_message",
        lambda phone, message, phone_number_id=None: intake_messages.append((phone, message, phone_number_id)),
    )
    monkeypatch.setattr(
        whatsapp_module,
        "send_whatsapp_message",
        # Accept the audit kwargs (tenant_id, case_id, initiated_by, …) the
        # notify path now passes alongside the positional args.
        lambda phone, message, phone_number_id=None, **kwargs: citizen_notifications.append((phone, message, phone_number_id)),
    )

    sender = f"9198800{int(time.time()) % 100000:05d}"
    webhook_resp = _post_signed_webhook(
        _whatsapp_payload(sender, "Water supply has not come for 3 days in Whitefield area")
    )
    assert webhook_resp.status_code == 200, webhook_resp.text
    assert webhook_resp.json()["status"] == "received"
    assert _wait_for(lambda: list(intake_messages)), "Normal grievance intake should acknowledge the citizen immediately"
    assert intake_messages[-1][1] == (
        "Ji, Thank you for reaching out 🙏\n\n"
        "Your issue has been received and is being reviewed. We will contact you shortly."
    )
    assert intake_messages[-1][1] != "Your grievance has been noted and will be reviewed."

    created_case = _wait_for(lambda: _fetch_case_by_phone(sender))
    assert created_case is not None, "Webhook intake should create a case"
    assert created_case["status"] == "new"
    assert created_case["category"] == "Infrastructure & Utilities"
    assert created_case["problem_domain"] == "Infrastructure & Utilities"
    assert "Whitefield" in str(created_case["case_metadata"])

    auth_headers = {"Authorization": f"Bearer {_make_token('mp_arun', 1)}"}

    list_resp = client.get("/api/cases", headers=auth_headers)
    assert list_resp.status_code == 200, list_resp.text
    listed_case = next((case for case in list_resp.json()["cases"] if case["id"] == created_case["id"]), None)
    assert listed_case is not None, "Newly created case should appear in MP case list"
    assert listed_case["problem_subdomain"] == "Water Supply"
    assert listed_case["convergence_program_type"] == "Service Delivery Strengthening"
    assert listed_case["location"] == "Whitefield"

    draft_message = "Your case has been resolved. Please stay in touch."
    patch_resp = client.patch(
        f"/api/cases/{created_case['id']}",
        headers=auth_headers,
        json={
            "notes_for_staff": "Verified with BWSSB ward office.",
            "response_to_citizen": draft_message,
        },
    )
    assert patch_resp.status_code == 200, patch_resp.text
    assert patch_resp.json()["success"] is True

    notify_resp = client.post(
        f"/api/cases/{created_case['id']}/notify/send",
        headers=auth_headers,
        json={"message": draft_message},
    )
    assert notify_resp.status_code == 200, notify_resp.text
    assert notify_resp.json()["success"] is True
    assert citizen_notifications, "MP notify flow should send a WhatsApp message"
    assert citizen_notifications[-1][0] == sender
    assert citizen_notifications[-1][1] == draft_message

    detail_resp = client.get(f"/api/cases/{created_case['id']}", headers=auth_headers)
    assert detail_resp.status_code == 200, detail_resp.text
    detail = detail_resp.json()
    assert detail["status"] == "resolved"
    assert detail["response_to_citizen"] == draft_message

    with test_engine.connect() as conn:
        activity = conn.execute(
            text(
                "SELECT action, new_value FROM case_activity_log "
                "WHERE case_id = :cid ORDER BY created_at DESC LIMIT 1"
            ),
            {"cid": created_case["id"]},
        ).mappings().first()
    assert activity is not None
    assert activity["action"] == "citizen_notified"
    assert activity["new_value"] == "resolved"


def test_history_save_then_list_returns_saved_draft():
    _seed_database()
    auth_headers = {"Authorization": f"Bearer {_make_token('mp_arun', 1)}"}

    save_resp = client.post(
        "/api/history/save",
        headers=auth_headers,
        json={
            "activity_type": "draft_letter",
            "title": "Archive visibility test letter",
            "content": "This letter should be visible in Archives.",
            "metadata": {"recipient": "Collector"},
        },
    )
    assert save_resp.status_code == 200, save_resp.text
    assert save_resp.json()["success"] is True

    list_resp = client.get("/api/history?activity_type=draft_letter", headers=auth_headers)
    assert list_resp.status_code == 200, list_resp.text
    items = list_resp.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Archive visibility test letter"
    assert items[0]["content"] == "This letter should be visible in Archives."
    assert items[0]["metadata"] == {"recipient": "Collector"}


def test_emergency_webhook_creates_cluster_and_sends_no_ack(monkeypatch):
    _seed_database()
    monkeypatch.setattr(main, "META_APP_SECRET", "test-meta-app-secret")

    outbound_messages = []
    monkeypatch.setattr(
        main,
        "ask_chatgpt_agent",
        lambda prompt, tenant_id=None: {
            "status": "emergency",
            "is_critical": True,
            "detected_language": "English",
            "political_response": "Emergency services have been alerted.",
            "grievance_data": {
                "problem_domain": "Infrastructure & Utilities",
                "problem_subdomain": "Roads & Bridges",
                "convergence_program_type": "Public Asset Upgrade",
                "categories": ["Infrastructure & Utilities"],
                "location": "Whitefield",
                "department": "PWD",
                "summary": "Emergency road accident reported in Whitefield",
            },
        },
    )
    monkeypatch.setattr(
        main,
        "send_whatsapp_message",
        lambda phone, message, phone_number_id=None: outbound_messages.append((phone, message, phone_number_id)),
    )

    sender = f"9197711{int(time.time()) % 100000:05d}"
    webhook_resp = _post_signed_webhook(
        _whatsapp_payload(sender, "Violence between groups in Whitefield. Immediate police needed.")
    )
    assert webhook_resp.status_code == 200, webhook_resp.text
    assert webhook_resp.json()["status"] == "received"
    assert outbound_messages == [], "Emergency complaints must not receive citizen acknowledgments"

    created_case = _wait_for(lambda: _fetch_case_by_phone(sender))
    assert created_case is not None
    assert created_case["status"] == "pending_review"
    assert created_case["category"] == "Emergency"
    assert created_case["problem_domain"] == "Infrastructure & Utilities"
    assert created_case["is_critical"] in (True, 1)

    clusters = _wait_for(lambda: _cluster_rows())
    assert len(clusters) == 1, "Emergency intake should create an incident cluster"
    assert clusters[0]["alert_level"] == "t0"
    assert clusters[0]["unique_sender_count"] == 1
    assert str(created_case["id"]) in str(clusters[0]["raw_case_ids"])

    auth_headers = {"Authorization": f"Bearer {_make_token('mp_arun', 1)}"}
    detail_resp = client.get(f"/api/cases/{created_case['id']}", headers=auth_headers)
    assert detail_resp.status_code == 200, detail_resp.text
    detail = detail_resp.json()
    assert detail["status"] == "pending_review"
    assert detail["category"] == "Emergency"


def test_hindi_riot_message_sends_no_ack_even_if_ai_misclassifies(monkeypatch):
    _seed_database()
    monkeypatch.setattr(main, "META_APP_SECRET", "test-meta-app-secret")

    outbound_messages = []
    monkeypatch.setattr(
        main,
        "ask_chatgpt_agent",
        lambda prompt, tenant_id=None: {
            "status": "new",
            "is_critical": False,
            "detected_language": "Hindi",
            "political_response": "Aapka sandesh mil gaya hai.",
            "grievance_data": {
                "problem_domain": "Infrastructure & Utilities",
                "problem_subdomain": "Roads & Bridges",
                "convergence_program_type": "Public Asset Upgrade",
                "categories": ["Infrastructure & Utilities"],
                "location": "Angol",
                "department": None,
                "summary": "Riot report in Angol",
            },
        },
    )
    monkeypatch.setattr(
        main,
        "send_whatsapp_message",
        lambda phone, message, phone_number_id=None: outbound_messages.append((phone, message, phone_number_id)),
    )

    sender = f"9197733{int(time.time()) % 100000:05d}"
    webhook_resp = _post_signed_webhook(
        _whatsapp_payload(sender, "आंगोल में दंगा हुआ है, कुछ मस्जिद पर पत्थर मारे लोगों ने।")
    )
    assert webhook_resp.status_code == 200, webhook_resp.text
    assert webhook_resp.json()["status"] == "received"
    assert outbound_messages == [], "Hindi riot complaints must not receive citizen acknowledgments"

    created_case = _wait_for(lambda: _fetch_case_by_phone(sender))
    assert created_case is not None
    assert created_case["category"] == "Emergency"
    assert created_case["status"] == "pending_review"


def test_personal_request_gets_special_office_contact_reply(monkeypatch):
    _seed_database()
    monkeypatch.setattr(main, "META_APP_SECRET", "test-meta-app-secret")

    outbound_messages = []
    monkeypatch.setattr(
        main,
        "ask_chatgpt_agent",
        lambda prompt, tenant_id=None: {
            "status": "new",
            "detected_language": "Hindi",
            "political_response": "जनप्रतिनिधि कार्यालय में व्यक्तिगत रूप से संपर्क करें।",
            "case_category": "Personal Request",
            "is_personal_request": True,
            "grievance_data": {
                "problem_domain": "Housing & Land",
                "problem_subdomain": "Encroachment/Dispute",
                "convergence_program_type": "Monitoring & Transparency",
                "categories": ["Housing & Land"],
                "location": None,
                "department": None,
                "summary": "Private land dispute help request",
            },
        },
    )
    monkeypatch.setattr(
        main,
        "send_whatsapp_message",
        lambda phone, message, phone_number_id=None: outbound_messages.append((phone, message, phone_number_id)),
    )

    sender = f"9196611{int(time.time()) % 100000:05d}"
    webhook_resp = _post_signed_webhook(
        _whatsapp_payload(sender, "Mera mere bhai ke saath zameen ko lekar jhagda hua. AAP meri madad karo")
    )
    assert webhook_resp.status_code == 200, webhook_resp.text
    assert webhook_resp.json()["status"] == "received"
    assert _wait_for(lambda: list(outbound_messages)), "Personal requests should receive the office-contact reply"
    assert "Hamare karyalaya mein vyaktigat roop se sampark karein." in outbound_messages[-1][1]

    created_case = _wait_for(lambda: _fetch_case_by_phone(sender))
    assert created_case is not None
    assert created_case["category"] == "Personal Request"
    assert created_case["status"] == "new"


def test_support_message_is_logged_without_citizen_reply(monkeypatch):
    _seed_database()
    monkeypatch.setattr(main, "META_APP_SECRET", "test-meta-app-secret")

    outbound_messages = []
    monkeypatch.setattr(
        main,
        "ask_chatgpt_agent",
        lambda prompt, tenant_id=None: {
            "status": "irrelevant",
            "detected_language": "English",
            "political_response": "Thank you for reaching out.",
            "case_category": "Political / Support Message",
            "is_silent_log_category": True,
            "grievance_data": {
                "problem_domain": None,
                "problem_subdomain": None,
                "convergence_program_type": None,
                "categories": [],
                "location": None,
                "department": None,
                "summary": "Support message logged for office review",
            },
        },
    )
    monkeypatch.setattr(
        main,
        "send_whatsapp_message",
        lambda phone, message, phone_number_id=None: outbound_messages.append((phone, message, phone_number_id)),
    )

    sender = f"9196655{int(time.time()) % 100000:05d}"
    webhook_resp = _post_signed_webhook(_whatsapp_payload(sender, "Thank you sir and happy birthday to you"))

    assert webhook_resp.status_code == 200, webhook_resp.text
    assert webhook_resp.json()["status"] == "received"
    time.sleep(0.3)
    assert outbound_messages == [], "Support-only messages should be logged silently without a citizen reply"

    created_case = _wait_for(lambda: _fetch_case_by_phone(sender))
    assert created_case is not None
    assert created_case["category"] == "Political / Support Message"
    assert created_case["status"] == "irrelevant"


def test_abusive_message_gets_warning_reply_without_ai(monkeypatch):
    _seed_database()
    monkeypatch.setattr(main, "META_APP_SECRET", "test-meta-app-secret")

    outbound_messages = []

    def _fail_ai(*_args, **_kwargs):
        raise AssertionError("AI should not be called for pre-filtered abusive messages")

    monkeypatch.setattr(main, "ask_chatgpt_agent", _fail_ai)
    monkeypatch.setattr(
        main,
        "send_whatsapp_message",
        lambda phone, message, phone_number_id=None: outbound_messages.append((phone, message, phone_number_id)),
    )
    monkeypatch.setattr(
        whatsapp_module,
        "send_whatsapp_message",
        lambda phone, message, phone_number_id=None: outbound_messages.append((phone, message, phone_number_id)),
    )

    sender = f"9197722{int(time.time()) % 100000:05d}"
    webhook_resp = _post_signed_webhook(_whatsapp_payload(sender, "fuck you madarchod"))

    assert webhook_resp.status_code == 200, webhook_resp.text
    assert webhook_resp.json()["status"] == "received"
    assert _wait_for(lambda: list(outbound_messages)), "Abusive message should receive a moderation warning"

    created_case = _wait_for(lambda: _fetch_case_by_phone(sender))
    assert created_case is not None
    assert created_case["category"] == "Spam (Offensive)"
    assert created_case["status"] == "offensive"
    assert outbound_messages[0][1] == "Maintain decorum. Legal action can be taken for abusive language."


def test_contact_buffering_merges_duplicate_followups(monkeypatch):
    _seed_database()
    monkeypatch.setattr(main, "META_APP_SECRET", "test-meta-app-secret")

    outbound_messages = []

    def _fake_ai(prompt, tenant_id=None):
        text_blob = str(prompt or "")
        if "Road issue in KR Puram" in text_blob:
            return {
                "status": "new",
                "detected_language": "English",
                "political_response": "Road issue noted.",
                "grievance_data": {
                    "problem_domain": "Infrastructure & Utilities",
                    "problem_subdomain": "Roads & Bridges",
                    "convergence_program_type": "Service Delivery Strengthening",
                    "categories": ["Infrastructure & Utilities"],
                    "location": "KR Puram",
                    "summary": "Road issue in KR Puram",
                },
            }
        return {
            "status": "new",
            "detected_language": "English",
            "political_response": "Water issue noted.",
            "grievance_data": {
                "problem_domain": "Infrastructure & Utilities",
                "problem_subdomain": "Water Supply",
                "convergence_program_type": "Service Delivery Strengthening",
                "categories": ["Infrastructure & Utilities"],
                "location": "Whitefield",
                "summary": "Water issue in Whitefield",
            },
        }

    monkeypatch.setattr(main, "ask_chatgpt_agent", _fake_ai)
    monkeypatch.setattr(
        main,
        "send_whatsapp_message",
        lambda phone, message, phone_number_id=None: outbound_messages.append((phone, message, phone_number_id)),
    )
    monkeypatch.setattr(
        whatsapp_module,
        "send_whatsapp_message",
        lambda phone, message, phone_number_id=None: outbound_messages.append((phone, message, phone_number_id)),
    )

    sender = "919912341234"
    main._process_incoming_message(sender, "Water issue in Whitefield", receiver_number="+15551636821")
    main._process_incoming_message(sender, "Road issue in KR Puram", receiver_number="+15551636821")
    main._process_incoming_message(sender, "Road issue in KR Puram urgent", receiver_number="+15551636821")

    rows = _cases_for_phone(sender)
    assert len(rows) == 2
    road_case = next(row for row in rows if "kr puram" in (row["raw_message"] or "").lower())
    water_case = next(row for row in rows if "whitefield" in (row["raw_message"] or "").lower())

    road_meta = json.loads(road_case["case_metadata"] or "{}")
    water_meta = json.loads(water_case["case_metadata"] or "{}")
    assert road_meta["contact_thread_id"] == water_meta["contact_thread_id"]
    assert len(road_meta.get("contact_message_events") or []) == 1
    assert "urgent" in road_meta["contact_message_events"][0]["message"].lower()
    assert water_meta.get("matched_value") == "Whitefield"

    # Ack policy: full ack for the first issue, a short "separate issue" ack
    # for the second distinct issue, and ONE reassurance for the duplicate
    # follow-up. No case reference numbers anywhere.
    assert len(outbound_messages) == 3
    assert "separate issue" in outbound_messages[1][1].lower()
    assert "2" in outbound_messages[1][1]
    assert "under review" in outbound_messages[2][1].lower()
    assert not any("#" in message for _, message, _ in outbound_messages)

    # The reassurance budget is one per thread: another duplicate stays silent.
    main._process_incoming_message(sender, "Road issue in KR Puram still urgent", receiver_number="+15551636821")
    assert len(outbound_messages) == 3


def test_contact_thread_high_frequency_and_spam_suspected_thresholds(monkeypatch):
    _seed_database()
    outbound_messages = []

    def _fake_ai(prompt, tenant_id=None):
        user_message = prompt.split("USER MESSAGE:", 1)[-1].strip()
        label = user_message.split(" at ", 1)[-1] if " at " in user_message else user_message[-12:]
        return {
            "status": "new",
            "detected_language": "English",
            "political_response": "Your grievance has been noted.",
            "grievance_data": {
                "problem_domain": "Infrastructure & Utilities",
                "problem_subdomain": "Service Issue",
                "convergence_program_type": "Service Delivery Strengthening",
                "categories": ["Infrastructure & Utilities"],
                "location": label,
                "summary": f"Issue reported at {label}",
            },
        }

    monkeypatch.setattr(main, "ask_chatgpt_agent", _fake_ai)
    monkeypatch.setattr(
        main,
        "send_whatsapp_message",
        lambda phone, message, phone_number_id=None: outbound_messages.append((phone, message, phone_number_id)),
    )
    monkeypatch.setattr(
        whatsapp_module,
        "send_whatsapp_message",
        lambda phone, message, phone_number_id=None: outbound_messages.append((phone, message, phone_number_id)),
    )

    sender = "919900001111"
    issue_messages = [
        "Water outage at Alpha ward",
        "Streetlight problem at Bravo colony",
        "Drainage blockage at Charlie road",
        # NB: avoid the word "missing" here — it trips the emergency keyword
        # detector (missing-person hazard) and emergency cases get no ack.
        "Garbage pickup skipped at Delta layout",
        "Pothole complaint at Echo chowk",
        "Transformer sparking at Foxtrot nagar",
        "Sewage overflow at Golf line",
        "Bus stop damage at Hotel market",
        "Footpath collapse at India camp",
        "Illegal dumping at Juliet circle",
    ]

    for message in issue_messages[:6]:
        main._process_incoming_message(sender, message, receiver_number="+15551636821")

    rows = _cases_for_phone(sender)
    assert len(rows) == 6
    metas_after_six = [json.loads(row["case_metadata"] or "{}") for row in rows]
    thread_ids = {meta.get("contact_thread_id") for meta in metas_after_six}
    assert len(thread_ids) == 1
    meta_after_six = next(meta for meta in metas_after_six if meta.get("contact_thread_state") == "high_frequency")
    assert meta_after_six["distinct_issue_count"] == 6
    assert meta_after_six["contact_thread_state"] == "high_frequency"
    # Ack policy: full ack (1st) + separate-issue acks (2nd-5th) + one
    # boundary notice when the 6th distinct issue crosses high-frequency.
    assert len(outbound_messages) == 6
    assert all("separate issue" in message.lower() for _, message, _ in outbound_messages[1:5])
    assert "one message per issue" in outbound_messages[5][1].lower()
    assert not any("#" in message for _, message, _ in outbound_messages)

    for message in issue_messages[6:]:
        main._process_incoming_message(sender, message, receiver_number="+15551636821")

    rows = _cases_for_phone(sender)
    assert len(rows) == 9
    final_metas = [json.loads(row["case_metadata"] or "{}") for row in rows]
    final_meta = next(meta for meta in final_metas if meta.get("contact_thread_state") == "spam_suspected")
    assert final_meta["distinct_issue_count"] == 10
    assert final_meta["contact_thread_state"] == "spam_suspected"
    # Issues 7-9 and the spam-suppressed 10th stay silent: the boundary notice
    # was the last thing this thread hears in the window.
    assert len(outbound_messages) == 6


def test_thread_distinct_issue_links_each_inbound_ledger_row_to_its_case(monkeypatch):
    _seed_database()
    outbound_messages = []

    def _fake_ai(prompt, tenant_id=None):
        user_message = prompt.split("USER MESSAGE:", 1)[-1].strip()
        summary = user_message.splitlines()[0][:120]
        return {
            "status": "new",
            "detected_language": "English",
            "political_response": "Your grievance has been noted.",
            "grievance_data": {
                "problem_domain": "Infrastructure & Utilities",
                "problem_subdomain": "Service Issue",
                "convergence_program_type": "Service Delivery Strengthening",
                "categories": ["Infrastructure & Utilities"],
                "location": "Whitefield",
                "summary": summary,
            },
        }

    monkeypatch.setattr(main, "ask_chatgpt_agent", _fake_ai)
    monkeypatch.setattr(
        main,
        "send_whatsapp_message",
        lambda phone, message, phone_number_id=None: outbound_messages.append((phone, message, phone_number_id)),
    )
    monkeypatch.setattr(
        whatsapp_module,
        "send_whatsapp_message",
        lambda phone, message, phone_number_id=None: outbound_messages.append((phone, message, phone_number_id)),
    )

    sender = "919955551111"
    messages = [
        ("wamid.thread.1", "Water issue in Whitefield"),
        ("wamid.thread.2", "Road issue in KR Puram"),
        ("wamid.thread.3", "Garbage issue in Indiranagar"),
    ]

    with test_engine.begin() as conn:
        now = datetime.utcnow()
        for idx, (msg_id, body) in enumerate(messages, start=1):
            conn.execute(
                text(
                    """
                    INSERT INTO wa_inbound_messages (
                        meta_message_id, tenant_id, sender_phone, receiver_number, message_type,
                        status, delivery_attempts, retry_count, raw_payload, created_at, updated_at, last_received_at
                    ) VALUES (
                        :msg_id, 1, :sender_phone, '+15551636821', 'text',
                        'processing', 1, 0, :payload, :now, :now, :now
                    )
                    """
                ),
                {
                    "msg_id": msg_id,
                    "sender_phone": sender,
                    "payload": json.dumps(
                        {
                            "entry_metadata": {"display_phone_number": "15551636821"},
                            "message": {
                                "id": msg_id,
                                "from": sender,
                                "type": "text",
                                "text": {"body": body},
                            },
                        }
                    ),
                    "now": now + timedelta(seconds=idx),
                },
            )

    inbound_rows = _inbound_rows_for_sender(sender)
    inbound_ids = [int(row["id"]) for row in inbound_rows]

    for inbound_id, (_, body) in zip(inbound_ids, messages):
        main._process_incoming_message(
            sender,
            body,
            receiver_number="+15551636821",
            msg_id=f"manual-{inbound_id}",
            inbound_ledger_id=inbound_id,
        )

    cases = _cases_for_phone(sender)
    inbound_after = _inbound_rows_for_sender(sender)

    assert len(cases) == 3
    assert len(inbound_after) == 3
    assert all(row["status"] == "processing" for row in inbound_after)
    assert all(row["case_id"] is not None for row in inbound_after)
    assert len({row["case_id"] for row in inbound_after}) == 3
    # Ack policy: every distinct issue earns exactly one ack — a full ack for
    # the first and a short "separate issue" ack for each additional one.
    assert len(outbound_messages) == 3
    assert all("separate issue" in message.lower() for _, message, _ in outbound_messages[1:])


def test_low_information_nudge_gets_one_reassurance_then_silence(monkeypatch):
    _seed_database()
    outbound_messages = []

    def _fake_ai(prompt, tenant_id=None):
        return {
            "status": "new",
            "detected_language": "English",
            "political_response": "Your grievance has been noted.",
            "grievance_data": {
                "problem_domain": "Infrastructure & Utilities",
                "problem_subdomain": "Water Supply",
                "convergence_program_type": "Service Delivery Strengthening",
                "categories": ["Infrastructure & Utilities"],
                "location": "Whitefield",
                "summary": "Water issue in Whitefield",
            },
        }

    monkeypatch.setattr(main, "ask_chatgpt_agent", _fake_ai)
    monkeypatch.setattr(
        main,
        "send_whatsapp_message",
        lambda phone, message, phone_number_id=None: outbound_messages.append((phone, message, phone_number_id)),
    )
    monkeypatch.setattr(
        whatsapp_module,
        "send_whatsapp_message",
        lambda phone, message, phone_number_id=None: outbound_messages.append((phone, message, phone_number_id)),
    )

    sender = "919944442222"
    main._process_incoming_message(sender, "Water issue in Whitefield", receiver_number="+15551636821")
    assert len(outbound_messages) == 1

    # First nudge: exactly one reassurance, in the thread's detected language.
    main._process_incoming_message(sender, "hello?", receiver_number="+15551636821")
    assert len(outbound_messages) == 2
    assert "under review" in outbound_messages[1][1].lower()

    # Every further nudge in the window stays silent.
    main._process_incoming_message(sender, "any update", receiver_number="+15551636821")
    main._process_incoming_message(sender, "please reply", receiver_number="+15551636821")
    assert len(outbound_messages) == 2

    # Nudges never create cases.
    assert len(_cases_for_phone(sender)) == 1
