import io
import os
import sys
import types
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
TEST_DB_URL = "sqlite:///./test_geography_onboarding.db"

os.environ["JWT_SECRET"] = TEST_JWT_SECRET
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["ENV"] = "test"
os.environ["OPENAI_API_KEY"] = "sk-test-fake-key-for-testing"
os.environ["META_APP_SECRET"] = "test-meta-app-secret"
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
import admin_api
import api_router
import core.db_helpers as db_helpers
import sansadx_backend.db as dbmod
from sansadx_backend.db import Base


test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False)
client = TestClient(main.app, raise_server_exceptions=False)


def _seed_database():
    dbmod.engine = test_engine
    dbmod.SessionLocal = TestSession
    db_helpers.engine = test_engine
    main.engine = test_engine
    api_router.engine = test_engine
    admin_api.engine = test_engine
    admin_api.SessionLocal = TestSession

    Base.metadata.create_all(bind=test_engine)

    with test_engine.begin() as conn:
        for table_name in (
            "admin_audit_log",
            "token_blocklist",
            "wa_message_dedup",
            "case_activity_log",
            "contacts",
            "cases",
            "users",
            "tenant_profiles",
            "tenants",
            "tenant_overrides",
        ):
            conn.execute(text(f"DELETE FROM {table_name}"))  # nosec B608

        now = datetime.utcnow()
        conn.execute(text("""
            INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active, created_at)
            VALUES
                (1, 'System Admin', 'India', '+910000000001', 'System', 1, :now),
                (2, 'Ghaziabad MP', 'Ghaziabad', '+910000000002', 'Pro', 1, :now),
                (3, 'Aligarh MP', 'Aligarh', '+910000000003', 'Pro', 1, :now)
        """), {"now": now})

        conn.execute(text("""
            INSERT INTO users (tenant_id, username, password_hash, role, constituency, house, display_name, is_active)
            VALUES (1, 'sysadmin', :ph, 'sysadmin', 'India', 'Lok Sabha', 'System Admin', 1)
        """), {"ph": admin_api.hash_password("AdminPass1!")})

        # Existing Ghaziabad geography used for ambiguity tests
        conn.execute(text("""
            INSERT INTO tenant_overrides (tenant_id, override_type, key, value, created_at)
            VALUES
                (2, 'geography_data', 'Ghaziabad/Ghaziabad', :gzb, :now),
                (2, 'geography_data', 'Ghaziabad/Muradnagar', :mrd, :now)
        """), {
            "now": now,
            "gzb": '[{"station_number":"1","locality":"Lohiya Nagar","building_name":""},{"station_number":"2","locality":"Patel Nagar","building_name":""}]',
            "mrd": '[{"station_number":"1","locality":"Lohiya Nagar","building_name":""}]',
        })


def _admin_headers():
    resp = client.post("/api/admin/auth/login", json={"username": "sysadmin", "password": "AdminPass1!"})
    assert resp.status_code == 200, resp.text
    token = resp.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_save_geography_sanitizes_rows_and_returns_validation():
    _seed_database()
    headers = _admin_headers()

    payload = {
        "data": [
            {"station_number": "1", "locality": "District", "building_name": "Ghaziabad"},
            {"station_number": "2", "locality": "Unique Colony", "building_name": ""},
            {"station_number": "3", "locality": "Lohiya Nagar", "building_name": ""},
        ]
    }
    resp = client.put("/api/admin/geography/Ghaziabad/Loni", json=payload, headers=headers)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["stations_saved"] == 2
    assert body["validation"]["meta_rows_removed"] == 1
    assert body["validation"]["meta_row_samples"] == ["District"]
    assert body["validation"]["ambiguous_localities_against_constituency"] == {
        "Lohiya Nagar": ["Ghaziabad", "Muradnagar"]
    }

    with test_engine.connect() as conn:
        saved = conn.execute(text("""
            SELECT value FROM tenant_overrides
            WHERE tenant_id = 2 AND override_type = 'geography_data' AND key = 'Ghaziabad/Loni'
        """)).scalar_one()
    assert "District" not in saved
    assert "Unique Colony" in saved
    assert "Lohiya Nagar" in saved


def test_bulk_geography_skips_live_override_for_ambiguous_locality():
    _seed_database()
    headers = _admin_headers()

    resp = client.post(
        "/api/admin/mps/2/geography/bulk",
        json={
            "parliamentary_constituency": "Ghaziabad",
            "assembly_constituency": "Loni",
            "localities": ["District", "Unique Colony", "Lohiya Nagar"],
        },
        headers=headers,
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["localities_saved"] == 2
    assert body["validation"]["meta_rows_removed"] == 1
    assert body["validation"]["ambiguous_localities_against_constituency"] == {
        "Lohiya Nagar": ["Ghaziabad", "Muradnagar"]
    }

    with test_engine.connect() as conn:
        unique_override = conn.execute(text("""
            SELECT value FROM tenant_overrides
            WHERE tenant_id = 2 AND override_type = 'geo_override' AND key = 'unique colony'
        """)).scalar()
        ambiguous_override = conn.execute(text("""
            SELECT value FROM tenant_overrides
            WHERE tenant_id = 2 AND override_type = 'geo_override' AND key = 'lohiya nagar'
        """)).scalar()

    assert unique_override == "Loni"
    assert ambiguous_override is None


def test_upload_pdf_returns_sanitized_stations_and_validation(monkeypatch):
    _seed_database()
    headers = _admin_headers()

    class FakePage:
        def extract_tables(self, *_args, **_kwargs):
            return [[
                ["1", "District", "Header"],
                ["2", "Lohiya Nagar", ""],
                ["3", "Unique Colony", ""],
            ]]

        def extract_text(self):
            return None

    class FakePDF:
        pages = [FakePage()]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    fake_pdfplumber = types.SimpleNamespace(open=lambda _stream: FakePDF())
    monkeypatch.setitem(sys.modules, "pdfplumber", fake_pdfplumber)
    monkeypatch.setattr(admin_api, "_extract_station_from_row", lambda row: {
        "station_number": str(row[0]),
        "locality": str(row[1]),
        "building_name": str(row[2] or ""),
    })

    files = {"file": ("ghaziabad.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")}
    resp = client.post("/api/admin/geography/upload-pdf", files=files, headers=headers)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [row["locality"] for row in body["stations"]] == ["Lohiya Nagar", "Unique Colony"]
    assert body["validation"]["meta_rows_removed"] == 1
    assert body["validation"]["meta_row_samples"] == ["District"]
