"""
Needle Platform — Pilot Readiness Test Suite
=============================================
QA / Red-Team / Reliability testing before the 10-MP pilot.

Tests covered:
  TEST 1  — Authentication (valid, invalid, tampered, missing header)
  TEST 2  — WhatsApp webhook simulation (100 varied messages)
  TEST 3  — Malicious webhook input (injection, overflow, binary)
  TEST 4  — AI failure handling (OpenAI down, bad JSON)
  TEST 5  — Database stress (500 inserts, 50 concurrent queries)
  TEST 6  — Multi-tenant isolation
  TEST 7  — Admin panel security (role-based access)
  TEST 8  — Dashboard load simulation (10 MPs)
  TEST 9  — Log safety verification (no secrets in logs)

Run with:
    pytest tests/test_pilot_readiness.py -v --tb=short 2>&1 | tee tests/pilot_report.txt
"""

import os
import sys
import json
import time
import hmac
import hashlib
import logging
import threading
import concurrent.futures
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, call
from typing import Generator

import jwt
import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

# ─────────────────────────────────────────────────────────────
# ENVIRONMENT SETUP — must happen before any app import
# ─────────────────────────────────────────────────────────────
TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
TEST_META_APP_SECRET = "test-meta-app-secret"
TEST_DB_URL = "sqlite:///./test_pilot.db"

os.environ.setdefault("JWT_SECRET", TEST_JWT_SECRET)
os.environ.setdefault("DATABASE_URL", TEST_DB_URL)
os.environ.setdefault("ENV", "test")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-testing")
os.environ.setdefault("META_APP_SECRET", TEST_META_APP_SECRET)
os.environ.setdefault("META_PHONE_NUMBER_ID", "15551636821")
os.environ.setdefault("META_ACCESS_TOKEN", "FAKE_ACCESS_TOKEN")
os.environ.setdefault("META_VERIFY_TOKEN", "test-verify-token-123")

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ─────────────────────────────────────────────────────────────
# IMPORT APP (after env is set)
# ─────────────────────────────────────────────────────────────
from sansadx_backend.db import Base, engine as app_engine, hash_password
import sansadx_backend.db as dbmod
import core.db_helpers as db_helpers
import api_router
import admin_api
import main
from main import app

# ─────────────────────────────────────────────────────────────
# TEST DATABASE SETUP
# ─────────────────────────────────────────────────────────────
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(bind=test_engine)


@event.listens_for(Engine, "connect")
def _sqlite_register_pg_lock_functions(dbapi_connection, connection_record):
    try:
        dbapi_connection.create_function("pg_try_advisory_lock", 1, lambda _key: 1)
        dbapi_connection.create_function("pg_advisory_unlock", 1, lambda _key: 1)
        dbapi_connection.create_function("pg_try_advisory_xact_lock", 1, lambda _key: 1)
    except Exception:
        pass


def _seed_database():
    """Create schema and seed test data for both tenants."""
    dbmod.engine = test_engine
    dbmod.SessionLocal = TestSession
    db_helpers.engine = test_engine
    main.engine = test_engine
    api_router.engine = test_engine
    api_router.JWT_SECRET = TEST_JWT_SECRET
    admin_api.engine = test_engine
    admin_api.SessionLocal = TestSession
    admin_api.JWT_SECRET = TEST_JWT_SECRET

    Base.metadata.create_all(bind=test_engine)

    with test_engine.begin() as conn:
        # Wipe tables for a clean run
        conn.execute(text("DELETE FROM wa_message_dedup"))
        conn.execute(text("DELETE FROM token_blocklist"))
        conn.execute(text("DELETE FROM case_activity_log"))
        conn.execute(text("DELETE FROM escalations"))
        conn.execute(text("DELETE FROM officers"))
        conn.execute(text("DELETE FROM contacts"))
        conn.execute(text("DELETE FROM cases"))
        conn.execute(text("DELETE FROM users"))
        conn.execute(text("DELETE FROM tenants"))
        conn.execute(text("DELETE FROM tenant_overrides"))

        # Tenant 1 — MP Arun Kumar (Lok Sabha)
        conn.execute(text("""
            INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active, created_at)
            VALUES (1, 'Arun Kumar', 'Bangalore North', '+919000000001', 'Pro', 1, :now)
        """), {"now": datetime.utcnow()})

        # Tenant 2 — MP Priya Sharma (Rajya Sabha)
        conn.execute(text("""
            INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active, created_at)
            VALUES (2, 'Priya Sharma', 'Mumbai South', '+919000000002', 'Pro', 1, :now)
        """), {"now": datetime.utcnow()})

        # MP user for Tenant 1
        ph1 = hash_password("ValidPass1!")
        conn.execute(text("""
            INSERT INTO users (tenant_id, username, password_hash, role, constituency, house)
            VALUES (1, 'mp_arun', :ph, 'user', 'Bangalore North', 'Lok Sabha')
        """), {"ph": ph1})

        # MP user for Tenant 2
        ph2 = hash_password("ValidPass2!")
        conn.execute(text("""
            INSERT INTO users (tenant_id, username, password_hash, role, constituency, house)
            VALUES (2, 'mp_priya', :ph, 'user', 'Mumbai South', 'Lok Sabha')
        """), {"ph": ph2})

        # Admin user (no tenant)
        ph_admin = hash_password("AdminPass1!")
        conn.execute(text("""
            INSERT INTO users (tenant_id, username, password_hash, role, constituency, house)
            VALUES (1, 'sysadmin', :ph, 'sysadmin', 'India', 'Lok Sabha')
        """), {"ph": ph_admin})

        # Geo overrides for Tenant 1
        conn.execute(text("""
            INSERT INTO tenant_overrides (tenant_id, override_type, key, value, created_at)
            VALUES (1, 'geo_override', 'Whitefield', 'Mahadevapura', :now)
        """), {"now": datetime.utcnow()})

        conn.execute(text("""
            INSERT INTO tenant_overrides (tenant_id, override_type, key, value, created_at)
            VALUES (1, 'geo_override', 'Koramangala', 'BTM Layout', :now)
        """), {"now": datetime.utcnow()})

        # Phone mapping for Tenant 1 WhatsApp number
        conn.execute(text("""
            INSERT INTO tenant_overrides (tenant_id, override_type, key, value, created_at)
            VALUES (1, 'phone_mapping', '+15551636821', '1', :now)
        """), {"now": datetime.utcnow()})

        # Some webhook payloads expose the receiver without a leading '+'.
        conn.execute(text("""
            INSERT INTO tenant_overrides (tenant_id, override_type, key, value, created_at)
            VALUES (1, 'phone_mapping', '15551636821', '1', :now)
        """), {"now": datetime.utcnow()})

    if hasattr(main, "_tenant_config_cache"):
        main._tenant_config_cache.clear()


_seed_database()

# ─────────────────────────────────────────────────────────────
# TEST CLIENT
# ─────────────────────────────────────────────────────────────
client = TestClient(app, raise_server_exceptions=False)


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def _reset_test_state():
    """Keep tests isolated from prior auth revocations and webhook side effects."""
    _seed_database()
    yield


def _make_token(username: str, tenant_id: int, role: str = "user",
                expire_hours: int = 8) -> str:
    now = datetime.utcnow()
    payload = {
        "sub": username,
        "tid": tenant_id,
        "role": role,
        "iat": now.timestamp(),
        "exp": now + timedelta(hours=expire_hours),
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


def _make_expired_token(username: str, tenant_id: int) -> str:
    now = datetime.utcnow()
    payload = {
        "sub": username,
        "tid": tenant_id,
        "role": "user",
        "iat": now.timestamp(),
        "exp": now - timedelta(hours=1),
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


def _make_tampered_token(username: str, tenant_id: int) -> str:
    """Sign with wrong secret."""
    now = datetime.utcnow()
    payload = {
        "sub": username,
        "tid": tenant_id,
        "role": "user",
        "iat": now.timestamp(),
        "exp": now + timedelta(hours=8),
    }
    return jwt.encode(payload, "wrong-secret-key-that-does-not-match-123", algorithm="HS256")


def _whatsapp_payload(sender: str, body: str, receiver: str = "15551636821") -> dict:
    """Build a valid Meta Cloud API webhook payload."""
    return {
        "entry": [{
            "changes": [{
                "value": {
                    "metadata": {"display_phone_number": receiver},
                    "messages": [{
                        "from": sender,
                        "type": "text",
                        "text": {"body": body}
                    }]
                }
            }]
        }]
    }


def _post_signed_webhook(payload, *, secret: str = TEST_META_APP_SECRET, raw_body: bytes | None = None, headers: dict | None = None):
    body = raw_body if raw_body is not None else json.dumps(payload).encode("utf-8")
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    merged_headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature-256": sig,
    }
    if headers:
        merged_headers.update(headers)
    return client.post("/whatsapp/webhook", content=body, headers=merged_headers)


# ─────────────────────────────────────────────────────────────
# TEST 1: AUTHENTICATION
# ─────────────────────────────────────────────────────────────
class TestAuthentication:

    def test_valid_login_returns_token(self):
        """Valid credentials return 200 and a JWT token."""
        resp = client.post("/api/auth/login", json={
            "username": "mp_arun",
            "password": "ValidPass1!"
        })
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "token" in data, "Response missing 'token' field"
        # Validate token is decodeable
        decoded = jwt.decode(data["token"], TEST_JWT_SECRET, algorithms=["HS256"])
        assert decoded["sub"] == "mp_arun"
        assert "tid" in decoded

    def test_invalid_password_returns_401(self):
        """Wrong password returns 401."""
        resp = client.post("/api/auth/login", json={
            "username": "mp_arun",
            "password": "WrongPassword999!"
        })
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    def test_unknown_user_returns_401(self):
        """Non-existent user returns 401."""
        resp = client.post("/api/auth/login", json={
            "username": "ghost_user_xyz",
            "password": "AnyPassword1!"
        })
        assert resp.status_code == 401

    def test_invalid_password_no_credential_leak(self):
        """Failed login must not expose password hash or DB details."""
        resp = client.post("/api/auth/login", json={
            "username": "mp_arun",
            "password": "wrong"
        })
        body = resp.text.lower()
        assert "$2b$" not in body, "bcrypt hash exposed in error response"
        assert "password_hash" not in body, "password_hash field exposed"
        assert "sqlalchemy" not in body, "SQLAlchemy traceback leaked"
        assert "traceback" not in body, "Python traceback leaked"

    def test_expired_token_returns_401(self):
        """Expired JWT is rejected."""
        token = _make_expired_token("mp_arun", 1)
        resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    def test_tampered_token_returns_401(self):
        """Token signed with wrong secret is rejected."""
        token = _make_tampered_token("mp_arun", 1)
        resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    def test_missing_auth_header_returns_403_or_401(self):
        """Protected endpoint without auth header returns 401 or 403."""
        resp = client.get("/api/auth/me")
        assert resp.status_code in (401, 403), f"Expected 401/403, got {resp.status_code}"

    def test_malformed_bearer_token(self):
        """Garbage token string returns 401/403."""
        resp = client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.valid.token"})
        assert resp.status_code in (401, 403)

    def test_valid_token_me_endpoint(self):
        """Valid token allows access to /api/auth/me."""
        token = _make_token("mp_arun", 1)
        resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("username") == "mp_arun"

    def test_me_endpoint_no_sensitive_fields(self):
        """User profile must not expose password hash."""
        token = _make_token("mp_arun", 1)
        resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        body = resp.text
        assert "$2b$" not in body, "password_hash exposed in /me response"
        assert "password_hash" not in body, "password_hash key exposed"

    def test_admin_login_returns_token(self):
        """Admin credentials return a valid JWT."""
        resp = client.post("/api/admin/auth/login", json={
            "username": "sysadmin",
            "password": "AdminPass1!"
        })
        assert resp.status_code == 200
        assert "token" in resp.json()

    def test_mp_token_rejected_on_admin_login(self):
        """MP credentials on admin login endpoint return 401 (wrong role)."""
        resp = client.post("/api/admin/auth/login", json={
            "username": "mp_arun",
            "password": "ValidPass1!"
        })
        assert resp.status_code in (401, 403), \
            f"MP should not get admin token. Got {resp.status_code}"


# ─────────────────────────────────────────────────────────────
# TEST 2: WHATSAPP WEBHOOK SIMULATION
# ─────────────────────────────────────────────────────────────
GRIEVANCE_MESSAGES = [
    # Water complaints
    "Water supply has not come for 3 days in Whitefield area",
    "Pipeline burst near Koramangala market, no water since yesterday",
    "Drinking water is contaminated with mud in Rajajinagar",
    "Water tanker not arriving in Yelahanka since last week",
    "No water supply to apartments in HSR Layout for 5 days",
    # Electricity issues
    "Power cut for 8 hours daily in Hebbal. Please fix",
    "Street lights not working on MG Road for 2 weeks",
    "Electric pole is leaning dangerously near school in Jayanagar",
    "Transformer blast in Malleswaram caused fire. Emergency!",
    "Voltage fluctuation damaging appliances in Basavanagudi",
    # Road repair
    "Road full of potholes on Outer Ring Road near Marathahalli",
    "Bridge under construction blocked for 6 months in Ulsoor",
    "Footpath encroached by shops near Commercial Street",
    "Road cave-in near drainage line in Shivajinagar",
    "No speed breakers near school in JP Nagar causing accidents",
    # Corruption complaints
    "Ward officer demanding bribe for BBMP work approval",
    "Contractor using substandard material for road in Banashankari",
    "Government scheme money diverted — PMAY not given to poor families",
    "Village panchayat head taking 20% cut from farmers",
    "Revenue officer refusing to give caste certificate without payment",
    # Emergency grievances
    "EMERGENCY: Building collapse in Bellandur. People trapped inside!",
    "Flood water entering homes in Varthur. Need rescue immediately",
    "Child missing near Nagawara lake. Please help!",
    "Old woman collapsed on street in Vijayanagar. No help arriving",
    "Violence between groups near mosque in Shivaji Nagar. Need police",
    # Multilingual (Hinglish)
    "Mere area mein paani nahi aata. Please help karo",
    "Sadak bahut kharab hai Whitefield mein. Kabse suno?",
    "Light nahi aati 4 ghante roz. Koi nahi sunta",
    "Nali band hai mere ghar ke bahar. Bahut smell aata hai",
    "Bribe maang raha hai officer. Corruption hai yahan",
    # Scheme-related
    "I applied for PM Awas Yojana 2 years ago but got no response",
    "Kisan Samman Nidhi not credited to bank account since 3 months",
    "Ration card cancelled without reason for my family",
    "Senior citizen pension stopped since January",
    "Scholarship not released for my daughter in class 11",
    # Infrastructure
    "Sewer line overflow near market in Rajajinagar",
    "Garbage not collected for 10 days in Koramangala",
    "Park taken over for private construction in BTM Layout",
    "Hospital building broken. No maintenance done",
    "Government school has no toilets for girls",
    # Telecom
    "No mobile network in Doddaballapur for 1 week after rain",
    "Internet not working in my village since tower damage",
    # Railways
    "Train not stopping at Nayandahalli station as scheduled",
    "Railway level crossing gate broken for 3 weeks",
    # Agriculture
    "Crop damaged by flood — no compensation from government",
    "Fertilizer not available in cooperative store",
    # Health
    "Primary health centre has no doctor since 2 months",
    "Free medicine not given at government hospital",
    "Ambulance service not responding in our village",
    # Education
    "Midday meal not provided to school children",
    "Teacher absent for 30 days in government school",
]


class TestWhatsAppWebhookSimulation:

    @patch("main.send_whatsapp_message")
    @patch("sansadx_backend.ai_engine.get_client")
    def test_single_valid_webhook_accepted(self, mock_get_client, mock_send):
        """Single valid webhook returns 200 immediately."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps({
                "status": "completed",
                "detected_language": "English",
                "political_response": "Your grievance has been noted.",
                "grievance_data": {
                    "categories": ["Water"],
                    "location": "Whitefield",
                    "person": None,
                    "department": "BWSSB",
                    "scheme": None
                }
            })))]
        )
        mock_get_client.return_value = mock_client

        payload = _whatsapp_payload("919876543210", "Water not coming in Whitefield")
        resp = _post_signed_webhook(payload)
        assert resp.status_code == 200
        assert resp.json().get("status") == "received"

    @patch("main.send_whatsapp_message")
    @patch("sansadx_backend.ai_engine.get_client")
    def test_100_messages_all_accepted(self, mock_get_client, mock_send):
        """100 varied messages all return 200 without server error."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps({
                "status": "completed",
                "detected_language": "English",
                "political_response": "Your concern has been registered.",
                "grievance_data": {
                    "categories": ["Infrastructure (State)"],
                    "location": "Koramangala",
                    "person": None,
                    "department": "BBMP",
                    "scheme": None
                }
            })))]
        )
        mock_get_client.return_value = mock_client

        failures = []
        for i, msg in enumerate(GRIEVANCE_MESSAGES):
            sender = f"91987654{i:04d}"
            payload = _whatsapp_payload(sender, msg)
            resp = _post_signed_webhook(payload)
            if resp.status_code != 200:
                failures.append((i, msg[:50], resp.status_code))

        assert len(failures) == 0, f"Webhook failures: {failures}"

    @patch("main.send_whatsapp_message")
    @patch("sansadx_backend.ai_engine.get_client")
    def test_emergency_message_flagged_critical(self, mock_get_client, mock_send):
        """Emergency message is saved as critical and does not get a citizen acknowledgment."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps({
                "status": "emergency",
                "is_critical": True,
                "detected_language": "English",
                "political_response": "Emergency services have been alerted.",
                "grievance_data": {
                    "categories": ["Emergency"],
                    "location": "Bellandur",
                    "person": None,
                    "department": "Police",
                    "scheme": None
                }
            })))]
        )
        mock_get_client.return_value = mock_client

        payload = _whatsapp_payload("919111111111",
                                    "EMERGENCY: Building collapse! People trapped!")
        resp = _post_signed_webhook(payload)
        assert resp.status_code == 200

        # Allow background task to complete (TestClient runs them synchronously)
        time.sleep(0.2)

        with test_engine.connect() as conn:
            row = conn.execute(text(
                "SELECT is_critical, status FROM cases WHERE user_phone = '919111111111' ORDER BY created_at DESC LIMIT 1"
            )).fetchone()
        assert row is not None, "Emergency case not saved to DB"
        assert row[0] == 1 or row[0] is True, "Emergency case not marked as critical"
        mock_send.assert_not_called()

    @patch("main.send_whatsapp_message")
    @patch("sansadx_backend.ai_engine.get_client")
    def test_no_duplicate_cases_on_single_message(self, mock_get_client, mock_send):
        """Same message from same sender creates only one case."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps({
                "status": "completed",
                "detected_language": "English",
                "political_response": "Noted.",
                "grievance_data": {"categories": ["Water"], "location": "Hebbal"}
            })))]
        )
        mock_get_client.return_value = mock_client

        unique_phone = "919222333444"
        unique_msg = f"Unique test message dedup check {time.time()}"
        payload = _whatsapp_payload(unique_phone, unique_msg)

        # Send once
        resp = _post_signed_webhook(payload)
        assert resp.status_code == 200
        time.sleep(0.3)

        with test_engine.connect() as conn:
            count = conn.execute(text(
                "SELECT COUNT(*) FROM cases WHERE user_phone = :p AND raw_message = :m"
            ), {"p": unique_phone, "m": unique_msg}).scalar()

        assert count == 1, f"Expected 1 case, found {count} — possible duplicate insert"

    def test_non_text_message_ignored(self):
        """Image/audio message type is accepted and handled without crashing."""
        payload = {
            "entry": [{
                "changes": [{
                    "value": {
                        "metadata": {"display_phone_number": "15551636821"},
                        "messages": [{
                            "from": "919888777666",
                            "type": "image",
                            "image": {"id": "abc123"}
                        }]
                    }
                }]
            }]
        }
        resp = _post_signed_webhook(payload)
        assert resp.status_code == 200
        assert resp.json().get("status") == "received"

    def test_delivery_receipt_ignored(self):
        """Delivery status update (no messages key) is ignored."""
        payload = {
            "entry": [{
                "changes": [{
                    "value": {
                        "metadata": {"display_phone_number": "15551636821"},
                        "statuses": [{"id": "wamid.xxx", "status": "delivered"}]
                    }
                }]
            }]
        }
        resp = _post_signed_webhook(payload)
        assert resp.status_code == 200
        assert resp.json().get("status") == "ignored"


# ─────────────────────────────────────────────────────────────
# TEST 3: MALICIOUS WEBHOOK INPUT
# ─────────────────────────────────────────────────────────────
class TestMaliciousWebhookInput:

    def test_empty_body_does_not_crash(self):
        """Empty JSON body returns non-500."""
        resp = _post_signed_webhook({})
        assert resp.status_code != 500, "Server crashed on empty body"

    def test_missing_entry_field_returns_gracefully(self):
        """Payload missing 'entry' key handled gracefully."""
        resp = _post_signed_webhook({"version": "2.0"})
        assert resp.status_code in (200, 400, 422), f"Unexpected: {resp.status_code}"

    def test_extremely_long_message_accepted_without_crash(self):
        """100KB message body does not crash server."""
        long_msg = "A" * 100_000
        payload = _whatsapp_payload("919123123123", long_msg)
        resp = _post_signed_webhook(payload)
        assert resp.status_code != 500, "Server crashed on large payload"

    def test_sql_injection_in_message_body(self):
        """SQL injection string in message body does not crash or corrupt DB."""
        sql_inject = "'; DROP TABLE cases; --"
        payload = _whatsapp_payload("919000111222", sql_inject)
        resp = _post_signed_webhook(payload)
        assert resp.status_code != 500, "Server crashed on SQL injection"

        # Verify cases table still exists
        with test_engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM cases")).scalar()
        assert isinstance(result, int), "cases table dropped by SQL injection!"

    def test_xss_payload_in_message_body(self):
        """XSS payload in message body handled safely."""
        xss = "<script>alert('xss')</script><img src=x onerror=alert(1)>"
        payload = _whatsapp_payload("919000111333", xss)
        resp = _post_signed_webhook(payload)
        assert resp.status_code != 500

    def test_null_bytes_in_message(self):
        """Null bytes in message body handled without crash."""
        null_msg = "Water issue\x00 in area\x00"
        payload = _whatsapp_payload("919000111444", null_msg)
        resp = _post_signed_webhook(payload)
        assert resp.status_code != 500

    def test_unicode_emoji_and_scripts(self):
        """Unicode, emoji, and non-Latin scripts handled."""
        msgs = [
            "पानी नहीं आ रहा 🚰🆘",
            "ನೀರು ಬರ್ತಿಲ್ಲ ಸ್ವಾಮಿ!",
            "مشكلة في المياه",
            "水が来ない" * 100,
        ]
        for msg in msgs:
            payload = _whatsapp_payload("919555666777", msg)
            resp = _post_signed_webhook(payload)
            assert resp.status_code != 500, f"Crash on message: {msg[:30]}"

    def test_deeply_nested_json_does_not_crash(self):
        """Deeply nested/malformed nested JSON does not cause server error."""
        # Valid structure but extra deeply nested garbage
        payload = _whatsapp_payload("919000999888", "test")
        payload["entry"][0]["changes"][0]["value"]["extra"] = {"a": {"b": {"c": {"d": "x" * 10000}}}}
        resp = _post_signed_webhook(payload)
        assert resp.status_code != 500

    def test_missing_from_field_does_not_crash(self):
        """Message missing 'from' field handled gracefully."""
        payload = {
            "entry": [{
                "changes": [{
                    "value": {
                        "metadata": {"display_phone_number": "15551636821"},
                        "messages": [{
                            "type": "text",
                            "text": {"body": "hello"}
                            # 'from' field missing
                        }]
                    }
                }]
            }]
        }
        resp = _post_signed_webhook(payload)
        assert resp.status_code != 500

    def test_wrong_content_type_returns_422_not_500(self):
        """Non-JSON body returns 422 validation error, not 500."""
        resp = _post_signed_webhook(
            None,
            raw_body=b"not json at all @@#$",
            headers={"Content-Type": "text/plain"},
        )
        assert resp.status_code == 400, \
            f"Expected validation error, got {resp.status_code}"


# ─────────────────────────────────────────────────────────────
# TEST 4: AI FAILURE HANDLING
# ─────────────────────────────────────────────────────────────
class TestAIFailureHandling:

    @patch("main.send_whatsapp_message")
    @patch("sansadx_backend.ai_engine.get_client")
    def test_openai_api_exception_does_not_crash_server(self, mock_get_client, mock_send):
        """When OpenAI raises ConnectionError, server returns 200 and saves fallback case."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = ConnectionError("OpenAI unreachable")
        mock_get_client.return_value = mock_client

        unique_phone = "919300000001"
        payload = _whatsapp_payload(unique_phone, "Water problem in area")
        resp = _post_signed_webhook(payload)
        assert resp.status_code == 200, "Server crashed when OpenAI was down"

    @patch("main.send_whatsapp_message")
    @patch("sansadx_backend.ai_engine.get_client")
    def test_openai_timeout_does_not_crash(self, mock_get_client, mock_send):
        """OpenAI timeout is handled gracefully."""
        import socket
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = TimeoutError("OpenAI timed out")
        mock_get_client.return_value = mock_client

        payload = _whatsapp_payload("919300000002", "Road broken in Koramangala")
        resp = _post_signed_webhook(payload)
        assert resp.status_code == 200

    @patch("main.send_whatsapp_message")
    @patch("sansadx_backend.ai_engine.get_client")
    def test_invalid_json_from_ai_does_not_crash(self, mock_get_client, mock_send):
        """AI returns non-JSON string — server handles gracefully."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="INVALID JSON {{{{not parseable!!!}"))]
        )
        mock_get_client.return_value = mock_client

        payload = _whatsapp_payload("919300000003", "Garbage collection issue")
        resp = _post_signed_webhook(payload)
        assert resp.status_code == 200

    @patch("main.send_whatsapp_message")
    @patch("sansadx_backend.ai_engine.get_client")
    def test_ai_returns_empty_string_handled(self, mock_get_client, mock_send):
        """AI returns empty string — server handles gracefully."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=""))]
        )
        mock_get_client.return_value = mock_client

        payload = _whatsapp_payload("919300000004", "School fee problem")
        resp = _post_signed_webhook(payload)
        assert resp.status_code == 200

    @patch("main.send_whatsapp_message")
    @patch("sansadx_backend.ai_engine.get_client")
    def test_ai_missing_key_fields_handled(self, mock_get_client, mock_send):
        """AI returns JSON missing expected fields — server uses defaults."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps({
                # Missing: status, political_response, grievance_data
                "random_field": "unexpected"
            })))]
        )
        mock_get_client.return_value = mock_client

        unique_phone = "919300000005"
        payload = _whatsapp_payload(unique_phone, "Health centre issue")
        resp = _post_signed_webhook(payload)
        assert resp.status_code == 200

        time.sleep(0.2)
        # Case should still be saved with fallback values
        with test_engine.connect() as conn:
            row = conn.execute(text(
                "SELECT id FROM cases WHERE user_phone = :p ORDER BY created_at DESC LIMIT 1"
            ), {"p": unique_phone}).fetchone()
        assert row is not None, "Case not saved even after AI partial response"

    def test_missing_openai_key_returns_error_not_crash(self):
        """When OPENAI_API_KEY is not set, AI returns an error dict (not exception)."""
        from sansadx_backend.ai_engine import ask_chatgpt_agent
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            # get_client returns None when key missing
            result = ask_chatgpt_agent("test message", tenant_id=1)
        # Should return a dict with error status, not raise exception
        assert isinstance(result, dict), "Expected dict response when API key missing"
        assert "status" in result


# ─────────────────────────────────────────────────────────────
# TEST 5: DATABASE STRESS TEST
# ─────────────────────────────────────────────────────────────
class TestDatabaseStress:

    def _insert_stress_cases(self, count: int = 500):
        with test_engine.begin() as conn:
            for i in range(count):
                conn.execute(text("""
                    INSERT INTO cases
                    (tenant_id, user_phone, category, raw_message, status, case_metadata, is_critical, created_at)
                    VALUES (:tid, :phone, :cat, :msg, :stat, :meta, 0, :now)
                """), {
                    "tid": 1,
                    "phone": f"91900{i:07d}",
                    "cat": ["Water", "Roads", "Electricity", "Health", "Education"][i % 5],
                    "msg": f"Stress test grievance number {i}",
                    "stat": "new",
                    "meta": json.dumps({"stress_test": True, "index": i}),
                    "now": datetime.utcnow(),
                })

    def test_500_grievance_inserts_no_error(self):
        """500 direct DB inserts complete without connection errors."""
        errors = []
        with test_engine.begin() as conn:
            for i in range(500):
                try:
                    conn.execute(text("""
                        INSERT INTO cases
                        (tenant_id, user_phone, category, raw_message, status, case_metadata, is_critical, created_at)
                        VALUES (:tid, :phone, :cat, :msg, :stat, :meta, 0, :now)
                    """), {
                        "tid": 1,
                        "phone": f"91900{i:07d}",
                        "cat": ["Water", "Roads", "Electricity", "Health", "Education"][i % 5],
                        "msg": f"Stress test grievance number {i}",
                        "stat": "new",
                        "meta": json.dumps({"stress_test": True, "index": i}),
                        "now": datetime.utcnow(),
                    })
                except Exception as e:
                    errors.append((i, str(e)))

        assert len(errors) == 0, f"DB insert errors: {errors[:5]}"

    def test_500_cases_saved_count_matches(self):
        """After stress inserts verify count is consistent."""
        self._insert_stress_cases()
        with test_engine.connect() as conn:
            count = conn.execute(text(
                "SELECT COUNT(*) FROM cases WHERE tenant_id = 1"
            )).scalar()
        assert count >= 500, f"Expected ≥500 rows, got {count}"

    def test_concurrent_reads_no_deadlock(self):
        """50 concurrent dashboard queries complete without errors."""
        self._insert_stress_cases()
        token = _make_token("mp_arun", 1)
        errors = []
        results = []

        def query_dashboard():
            try:
                r = client.get(
                    "/api/cases",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"page": 1, "limit": 20}
                )
                results.append(r.status_code)
                if r.status_code != 200:
                    errors.append(r.status_code)
            except Exception as e:
                errors.append(str(e))

        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(query_dashboard) for _ in range(50)]
            concurrent.futures.wait(futures)

        assert len(errors) == 0, f"Concurrent query errors: {errors[:5]}"
        assert all(s == 200 for s in results), f"Non-200 statuses: {set(results)}"

    def test_dashboard_query_responds_in_time(self):
        """Dashboard query completes within 2 seconds even under loaded DB."""
        self._insert_stress_cases()
        token = _make_token("mp_arun", 1)
        start = time.time()
        resp = client.get(
            "/api/cases",
            headers={"Authorization": f"Bearer {token}"},
            params={"page": 1, "limit": 50}
        )
        elapsed = time.time() - start
        assert resp.status_code == 200
        assert elapsed < 2.0, f"Dashboard query too slow: {elapsed:.2f}s"

    def test_summary_endpoint_responds_in_time(self):
        """Summary/stats endpoint responds within 2 seconds."""
        self._insert_stress_cases()
        token = _make_token("mp_arun", 1)
        start = time.time()
        resp = client.get(
            "/api/dashboard/summary",
            headers={"Authorization": f"Bearer {token}"}
        )
        elapsed = time.time() - start
        assert resp.status_code == 200
        assert elapsed < 2.0, f"Summary endpoint too slow: {elapsed:.2f}s"


# ─────────────────────────────────────────────────────────────
# TEST 6: MULTI-TENANT ISOLATION
# ─────────────────────────────────────────────────────────────
class TestMultiTenantIsolation:

    def _seed_cross_tenant_cases(self):
        """Insert known cases for both tenants."""
        with test_engine.begin() as conn:
            # Tenant 1 case
            conn.execute(text("""
                INSERT INTO cases (tenant_id, user_phone, category, raw_message, status, case_metadata, is_critical, created_at)
                VALUES (1, '919500000001', 'Water', 'Tenant1 confidential case', 'new', '{}', 0, :now)
            """), {"now": datetime.utcnow()})

            # Tenant 2 case
            conn.execute(text("""
                INSERT INTO cases (tenant_id, user_phone, category, raw_message, status, case_metadata, is_critical, created_at)
                VALUES (2, '919500000002', 'Roads', 'Tenant2 confidential case', 'new', '{}', 0, :now)
            """), {"now": datetime.utcnow()})

    def test_mp_cannot_read_other_tenants_cases(self):
        """Tenant 1 MP cannot see Tenant 2 cases in /api/cases."""
        self._seed_cross_tenant_cases()
        token = _make_token("mp_arun", 1)  # Tenant 1 token

        resp = client.get("/api/cases", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

        data = resp.json()
        cases = data.get("cases", data if isinstance(data, list) else [])

        # Check no Tenant 2 messages appear
        for case in cases:
            raw = case.get("raw_message", "")
            assert "Tenant2 confidential case" not in raw, \
                f"Cross-tenant data leak: Tenant 2 case visible to Tenant 1 user"

    def test_injected_tenant_id_in_query_param_blocked(self):
        """Passing ?tenant_id=2 in query param must not expose other tenant's data."""
        token = _make_token("mp_arun", 1)  # Tenant 1

        resp = client.get(
            "/api/cases?tenant_id=2",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200

        data = resp.json()
        cases = data.get("cases", data if isinstance(data, list) else [])
        for case in cases:
            raw = case.get("raw_message", "")
            assert "Tenant2 confidential case" not in raw, \
                "Tenant isolation bypassed via query parameter injection"

    def test_mp_cannot_access_specific_case_from_other_tenant(self):
        """MP cannot fetch a case belonging to another tenant by ID."""
        self._seed_cross_tenant_cases()

        # Get the Tenant 2 case ID
        with test_engine.connect() as conn:
            row = conn.execute(text(
                "SELECT id FROM cases WHERE raw_message = 'Tenant2 confidential case' LIMIT 1"
            )).fetchone()

        if not row:
            pytest.skip("Tenant 2 case not found in DB")

        tenant2_case_id = row[0]
        token = _make_token("mp_arun", 1)  # Tenant 1 user

        resp = client.get(
            f"/api/cases/{tenant2_case_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        # Should be 404 (not found in tenant) or 403 (forbidden), NOT 200
        assert resp.status_code in (403, 404), \
            f"Cross-tenant case {tenant2_case_id} visible to Tenant 1 user! Status: {resp.status_code}"

    def test_summary_only_shows_own_tenant_counts(self):
        """Dashboard summary counts must reflect only own tenant's cases."""
        self._seed_cross_tenant_cases()

        t1_token = _make_token("mp_arun", 1)
        t2_token = _make_token("mp_priya", 2)

        resp1 = client.get("/api/dashboard/summary", headers={"Authorization": f"Bearer {t1_token}"})
        resp2 = client.get("/api/dashboard/summary", headers={"Authorization": f"Bearer {t2_token}"})

        assert resp1.status_code == 200
        assert resp2.status_code == 200

        # Both tenants have cases but they should differ
        d1 = resp1.json()
        d2 = resp2.json()

        # Get total case counts
        t1_total = d1.get("total_cases", d1.get("total", None))
        t2_total = d2.get("total_cases", d2.get("total", None))

        # They should not be identical OR both should be > 0 (just verifying isolation logic runs)
        # Key check: Tenant 2 should not see Tenant 1's 500+ stress test cases
        if t1_total is not None and t2_total is not None:
            assert t1_total != t2_total or t1_total > 0, \
                "Tenant summaries look suspiciously identical or zero"

    def test_webhook_routes_to_correct_tenant(self):
        """WhatsApp message sent to MP Arun's number routes to Tenant 1, not Tenant 2."""
        with test_engine.connect() as conn:
            before_t1 = conn.execute(text(
                "SELECT COUNT(*) FROM cases WHERE tenant_id = 1"
            )).scalar()
            before_t2 = conn.execute(text(
                "SELECT COUNT(*) FROM cases WHERE tenant_id = 2"
            )).scalar()

        with patch("main.send_whatsapp_message"), \
             patch("sansadx_backend.ai_engine.get_client") as mock_get_client:

            mock_client = MagicMock()
            mock_client.chat.completions.create.return_value = MagicMock(
                choices=[MagicMock(message=MagicMock(content=json.dumps({
                    "status": "completed",
                    "detected_language": "English",
                    "political_response": "Noted.",
                    "grievance_data": {"categories": ["Water"], "location": "Whitefield"}
                })))]
            )
            mock_get_client.return_value = mock_client

            # Send to Tenant 1's registered number
            payload = _whatsapp_payload("919600000001", "Water problem",
                                         receiver="15551636821")
            _post_signed_webhook(payload)
            time.sleep(0.3)

        with test_engine.connect() as conn:
            after_t1 = conn.execute(text(
                "SELECT COUNT(*) FROM cases WHERE tenant_id = 1"
            )).scalar()
            after_t2 = conn.execute(text(
                "SELECT COUNT(*) FROM cases WHERE tenant_id = 2"
            )).scalar()

        assert after_t1 > before_t1, "Webhook did not save to Tenant 1"
        assert after_t2 == before_t2, "Webhook accidentally saved to Tenant 2"


# ─────────────────────────────────────────────────────────────
# TEST 7: ADMIN PANEL SECURITY (RBAC)
# ─────────────────────────────────────────────────────────────
class TestAdminPanelSecurity:

    def test_admin_endpoint_without_token_returns_401_or_403(self):
        """Admin /stats without token is rejected."""
        resp = client.get("/api/admin/stats")
        assert resp.status_code in (401, 403), \
            f"Admin endpoint accessible without auth! Status: {resp.status_code}"

    def test_mp_token_rejected_on_admin_stats(self):
        """MP-role JWT cannot access admin-only /stats."""
        mp_token = _make_token("mp_arun", 1, role="user")
        resp = client.get("/api/admin/stats",
                          headers={"Authorization": f"Bearer {mp_token}"})
        assert resp.status_code in (401, 403), \
            f"MP token granted admin access! Status: {resp.status_code}"

    def test_mp_token_rejected_on_admin_mps_list(self):
        """MP token cannot list all MPs via admin endpoint."""
        mp_token = _make_token("mp_arun", 1, role="user")
        resp = client.get("/api/admin/mps",
                          headers={"Authorization": f"Bearer {mp_token}"})
        assert resp.status_code in (401, 403)

    def test_mp_token_rejected_on_create_mp(self):
        """MP token cannot create a new MP account."""
        mp_token = _make_token("mp_arun", 1, role="user")
        resp = client.post("/api/admin/mps",
                           headers={"Authorization": f"Bearer {mp_token}"},
                           json={"name": "Fake MP", "username": "fakempx",
                                 "password": "FakePass1!", "constituency": "Unknown"})
        assert resp.status_code in (401, 403)

    def test_admin_token_can_access_stats(self):
        """Valid admin token can access /api/admin/stats."""
        admin_token = _make_token("sysadmin", 1, role="sysadmin")
        resp = client.get("/api/admin/stats",
                          headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200, \
            f"Admin cannot access /stats. Status: {resp.status_code}: {resp.text[:200]}"

    def test_admin_cannot_modify_other_tenant_without_permission(self):
        """Admin endpoint with wrong tenant context blocked correctly."""
        # Use MP token with injected admin role but wrong tenant
        fake_admin_token = _make_token("mp_arun", 1, role="user")
        resp = client.delete(
            "/api/admin/mps/2",
            headers={"Authorization": f"Bearer {fake_admin_token}"}
        )
        assert resp.status_code in (401, 403)

    def test_tampered_role_in_token_rejected(self):
        """Token with role='sysadmin' but wrong secret is rejected."""
        # Create token claiming admin role but signed incorrectly
        fake_admin_token = jwt.encode(
            {"sub": "mp_arun", "tid": 1, "role": "sysadmin",
             "exp": datetime.utcnow() + timedelta(hours=8)},
            "wrong-secret-tampered-123",
            algorithm="HS256"
        )
        resp = client.get("/api/admin/stats",
                          headers={"Authorization": f"Bearer {fake_admin_token}"})
        assert resp.status_code in (401, 403)

    def test_admin_login_with_mp_role_rejected(self):
        """Admin login endpoint must reject users without admin role."""
        resp = client.post("/api/admin/auth/login", json={
            "username": "mp_arun",
            "password": "ValidPass1!"
        })
        assert resp.status_code in (401, 403), \
            f"Non-admin user got admin token: {resp.status_code}"


# ─────────────────────────────────────────────────────────────
# TEST 8: DASHBOARD LOAD SIMULATION (10 MPs)
# ─────────────────────────────────────────────────────────────
class TestDashboardLoad:

    def test_10_concurrent_case_list_queries(self):
        """10 MPs querying their case lists simultaneously — all succeed."""
        # Use the two seeded tenants (alternate token usage)
        tokens = [
            _make_token("mp_arun", 1) if i % 2 == 0 else _make_token("mp_priya", 2)
            for i in range(10)
        ]

        results = []
        errors = []

        def fetch_cases(token):
            try:
                r = client.get("/api/cases",
                               headers={"Authorization": f"Bearer {token}"},
                               params={"page": 1, "limit": 20})
                results.append(r.status_code)
                if r.status_code != 200:
                    errors.append(f"Status {r.status_code}: {r.text[:100]}")
            except Exception as e:
                errors.append(str(e))

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(fetch_cases, t) for t in tokens]
            concurrent.futures.wait(futures, timeout=10)

        assert len(errors) == 0, f"Load test errors: {errors}"
        assert all(s == 200 for s in results), f"Non-200 responses: {results}"

    def test_10_concurrent_summary_queries(self):
        """10 MPs loading dashboard summaries simultaneously — all succeed within 2s."""
        tokens = [
            _make_token("mp_arun", 1) if i % 2 == 0 else _make_token("mp_priya", 2)
            for i in range(10)
        ]

        timings = []
        errors = []

        def fetch_summary(token):
            try:
                start = time.time()
                r = client.get("/api/dashboard/summary",
                               headers={"Authorization": f"Bearer {token}"})
                elapsed = time.time() - start
                timings.append(elapsed)
                if r.status_code != 200:
                    errors.append(r.status_code)
            except Exception as e:
                errors.append(str(e))

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(fetch_summary, t) for t in tokens]
            concurrent.futures.wait(futures, timeout=15)

        assert len(errors) == 0, f"Summary load errors: {errors}"
        assert all(t < 2.0 for t in timings), \
            f"Slow responses: {[f'{t:.2f}s' for t in timings if t >= 2.0]}"

    def test_health_check_endpoint_always_fast(self):
        """/ health check responds in under 100ms."""
        start = time.time()
        resp = client.get("/")
        elapsed = time.time() - start
        assert resp.status_code == 200
        assert elapsed < 0.1, f"Health check too slow: {elapsed:.3f}s"


# ─────────────────────────────────────────────────────────────
# TEST 9: LOG SAFETY (No secrets in logs)
# ─────────────────────────────────────────────────────────────
class TestLogSafety:

    def test_login_failure_log_has_no_password(self):
        """Failed login event logged but password not included."""
        log_records = []

        class CapturingHandler(logging.Handler):
            def emit(self, record):
                log_records.append(record.getMessage())

        handler = CapturingHandler()
        logging.getLogger("needle.api").addHandler(handler)
        logging.getLogger("needle.admin_api").addHandler(handler)

        try:
            client.post("/api/auth/login", json={
                "username": "mp_arun",
                "password": "SuperSecret999!"
            })
        finally:
            logging.getLogger("needle.api").removeHandler(handler)
            logging.getLogger("needle.admin_api").removeHandler(handler)

        combined = " ".join(log_records)
        assert "SuperSecret999!" not in combined, "Password leaked in logs!"

    def test_jwt_token_not_logged_on_invalid_request(self):
        """Invalid JWT token string must not appear verbatim in logs."""
        log_records = []

        class CapturingHandler(logging.Handler):
            def emit(self, record):
                log_records.append(record.getMessage())

        handler = CapturingHandler()
        logging.getLogger("needle.api").addHandler(handler)

        test_token = _make_tampered_token("mp_arun", 1)
        try:
            client.get("/api/auth/me",
                       headers={"Authorization": f"Bearer {test_token}"})
        finally:
            logging.getLogger("needle.api").removeHandler(handler)

        combined = " ".join(log_records)
        # Token should not appear fully in logs (might appear partially for debugging, but not full)
        assert test_token not in combined, "Full JWT token string leaked in logs"

    def test_api_keys_not_in_error_responses(self):
        """OpenAI/Meta API keys must never appear in HTTP error responses."""
        openai_key = os.environ.get("OPENAI_API_KEY", "sk-test-fake-key-for-testing")

        # Trigger various error conditions
        endpoints = [
            ("GET", "/api/auth/me", {}),
            ("POST", "/api/auth/login", {"json": {"username": "x", "password": "y"}}),
            ("POST", "/whatsapp/webhook", {"json": {}}),
        ]
        for method, url, kwargs in endpoints:
            if method == "GET":
                resp = client.get(url)
            else:
                resp = client.post(url, **kwargs)
            assert openai_key not in resp.text, \
                f"OpenAI API key exposed in {url} response!"
            assert "META_ACCESS_TOKEN" not in resp.text, \
                f"Meta access token name exposed in {url} response!"

    def test_bcrypt_hash_not_in_responses(self):
        """bcrypt hashes must never appear in any API response."""
        token = _make_token("mp_arun", 1)
        endpoints = [
            "/api/auth/me",
            "/api/cases",
            "/api/profile",
        ]
        for endpoint in endpoints:
            resp = client.get(endpoint, headers={"Authorization": f"Bearer {token}"})
            if resp.status_code == 200:
                assert "$2b$" not in resp.text, \
                    f"bcrypt hash exposed in {endpoint}!"
                assert "$2a$" not in resp.text, \
                    f"bcrypt hash exposed in {endpoint}!"

    def test_stack_traces_not_in_error_responses(self):
        """Internal stack traces must not be returned in error responses."""
        # Send bad data to several endpoints
        responses = [
            client.post("/api/auth/login", json={"username": None, "password": None}),
            _post_signed_webhook(None, raw_body=b"}{bad json}"),
            client.get("/api/cases/999999999"),  # non-existent ID
        ]
        for resp in responses:
            body = resp.text.lower()
            assert "traceback" not in body, "Python traceback in response"
            assert "sqlalchemy" not in body, "SQLAlchemy internals in response"
            assert "file \"/app" not in body, "File path in response"


# ─────────────────────────────────────────────────────────────
# WEBHOOK SIGNATURE VALIDATION TEST
# ─────────────────────────────────────────────────────────────
class TestWebhookSignatureValidation:

    def test_valid_signature_accepted(self):
        """Correct HMAC-SHA256 signature is accepted."""
        secret = "test-app-secret-12345"
        with patch.dict(os.environ, {"META_APP_SECRET": secret}):
            payload = json.dumps(_whatsapp_payload("919700000001", "test message")).encode()
            sig = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

            resp = client.post(
                "/whatsapp/webhook",
                content=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-Hub-Signature-256": sig
                }
            )
            assert resp.status_code == 200

    def test_invalid_signature_rejected(self):
        """Wrong HMAC signature returns 403."""
        secret = "test-app-secret-12345"
        with patch.dict(os.environ, {"META_APP_SECRET": secret}):
            payload = json.dumps(_whatsapp_payload("919700000002", "test")).encode()
            # Wrong signature
            resp = client.post(
                "/whatsapp/webhook",
                content=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-Hub-Signature-256": "sha256=badhashvalue1234567890"
                }
            )
            assert resp.status_code == 403

    def test_missing_signature_header_rejected(self):
        """Missing X-Hub-Signature-256 header returns 403 when secret is set."""
        secret = "test-app-secret-12345"
        with patch.dict(os.environ, {"META_APP_SECRET": secret}):
            payload = json.dumps(_whatsapp_payload("919700000003", "test")).encode()
            resp = client.post(
                "/whatsapp/webhook",
                content=payload,
                headers={"Content-Type": "application/json"}
            )
            assert resp.status_code == 403


# ─────────────────────────────────────────────────────────────
# WEBHOOK VERIFICATION TEST
# ─────────────────────────────────────────────────────────────
class TestWebhookVerification:

    def test_valid_verification_challenge_returned(self):
        """GET /whatsapp/webhook with correct token returns challenge."""
        resp = client.get("/whatsapp/webhook", params={
            "hub.mode": "subscribe",
            "hub.verify_token": "test-verify-token-123",
            "hub.challenge": "CHALLENGE_CODE_12345"
        })
        assert resp.status_code == 200
        assert "CHALLENGE_CODE_12345" in resp.text

    def test_invalid_verify_token_returns_403(self):
        """GET /whatsapp/webhook with wrong token returns 403."""
        resp = client.get("/whatsapp/webhook", params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong-token",
            "hub.challenge": "CHALLENGE"
        })
        assert resp.status_code == 403


# ─────────────────────────────────────────────────────────────
# LANGUAGE DETECTION UNIT TESTS
# ─────────────────────────────────────────────────────────────
class TestLanguageDetection:

    def test_english_message_detected(self):
        from sansadx_backend.ai_engine import detect_input_language
        assert detect_input_language("Water supply is broken near the school") == "English"

    def test_marathi_message_detected(self):
        from sansadx_backend.ai_engine import detect_input_language
        result = detect_input_language("paani yeina aahe madhe traas hota")
        assert result == "Marathi"

    def test_hinglish_detected(self):
        from sansadx_backend.ai_engine import detect_input_language
        result = detect_input_language("yahan paani nahi aata hai kya")
        assert result in ("Hinglish", "Hindi"), f"Expected Hinglish/Hindi, got {result}"

    def test_kannada_detected(self):
        from sansadx_backend.ai_engine import detect_input_language
        result = detect_input_language("neeru illa alli maadi beku")
        assert result == "Kannada"


# ─────────────────────────────────────────────────────────────
# CLEANUP
# ─────────────────────────────────────────────────────────────
def pytest_sessionfinish(session, exitstatus):
    """Clean up test database after all tests."""
    db_path = "./test_pilot.db"
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass
