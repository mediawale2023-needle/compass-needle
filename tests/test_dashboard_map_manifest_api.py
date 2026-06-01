import os
import sys
import io
import json
import zipfile
from datetime import datetime, timedelta

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
TEST_DB_URL = "sqlite:///./test_dashboard_map_manifest_api.db"

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
import main
import api_router
import core.db_helpers as db_helpers
import sansadx_backend.db as dbmod
from sansadx_backend.db import Base, hash_password


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
    api_router.JWT_SECRET = TEST_JWT_SECRET
    admin_api.JWT_SECRET = TEST_JWT_SECRET

    Base.metadata.create_all(bind=test_engine)

    with test_engine.begin() as conn:
        for table_name in ("admin_audit_log", "seat_boundary_assets", "seat_map_manifests", "tenant_overrides", "users", "tenant_profiles", "tenants"):
            conn.execute(text(f"DELETE FROM {table_name}"))  # nosec B608

        now = datetime.utcnow()
        conn.execute(
            text(
                """
                INSERT INTO tenants
                    (id, name, constituency, seat_type, account_stage, whatsapp_number, subscription_plan, is_active, created_at)
                VALUES
                    (10, 'Sanket', 'Belgaum Dakshin', 'mla', 'aspirant', '+919000001010', 'Pro', 1, :now),
                    (11, 'Arun', 'Unknown Seat', 'mla', 'elected', '+919000001011', 'Pro', 1, :now),
                    (12, 'Belagavi MP', 'Belagavi', 'mp', 'elected', '+919000001012', 'Pro', 1, :now)
                """
            ),
            {"now": now},
        )
        conn.execute(
            text(
                """
                INSERT INTO users
                    (tenant_id, username, password_hash, role, constituency, house, display_name, is_active)
                VALUES
                    (10, 'sanket', :password_hash, 'owner', 'Belgaum Dakshin', 'Vidhan Sabha', 'Sanket', 1),
                    (11, 'arun', :password_hash, 'owner', 'Unknown Seat', 'Vidhan Sabha', 'Arun', 1),
                    (12, 'belagavi_mp', :password_hash, 'owner', 'Belagavi', 'Lok Sabha', 'Belagavi MP', 1),
                    (10, 'sysadmin', :password_hash, 'admin', 'Belgaum Dakshin', 'Vidhan Sabha', 'Sysadmin', 1)
                """
            ),
            {"password_hash": hash_password("ValidPass1!")},
        )
        conn.execute(
            text(
                """
                INSERT INTO tenant_overrides
                    (tenant_id, override_type, key, value, created_at)
                VALUES
                    (10, 'geography_data', 'mla:Belgaum Dakshin/Belgaum South', :value_one, :now),
                    (10, 'geography_data', 'mla:Belgaum Dakshin/Yellur', :value_two, :now),
                    (12, 'geography_data', 'mp:Belagavi/Belagavi', :value_three, :now)
                """
            ),
            {
                "now": now,
                "value_one": '[{"locality":"Nath Pai Circle"},{"locality":"Shahapur"}]',
                "value_two": '[{"locality":"Yellur"}]',
                "value_three": '[{"locality":"Belagavi City"},{"locality":"Camp"}]',
            },
        )


def _auth_headers(username: str, tenant_id: int, role: str = "owner"):
    token = jwt.encode(
        {"sub": username, "tid": tenant_id, "role": role, "exp": datetime.utcnow() + timedelta(hours=8)},
        TEST_JWT_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def test_dashboard_map_manifest_returns_tenant_seat_manifest():
    _seed_database()
    resp = client.get("/api/maps/seat-manifest", headers=_auth_headers("sanket", 10))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["seat_key"] == "mla:belgaum-dakshin"
    assert data["seat_type"] == "mla"
    assert data["asset"]["path"] == "/maps/mla/belgaum-dakshin-outline.svg"
    assert len(data["features"]) > 0


def test_dashboard_map_manifest_404_for_unmapped_seat():
    _seed_database()
    resp = client.get("/api/maps/seat-manifest", headers=_auth_headers("arun", 11))
    assert resp.status_code == 404


def test_admin_seat_map_upsert_overrides_repo_manifest():
    _seed_database()
    admin_headers = _auth_headers("sysadmin", 10, role="admin")

    create_resp = client.post(
        "/api/admin/seat-maps",
        headers=admin_headers,
        json={
            "seat_key": "mla:belgaum-dakshin",
            "seat_type": "mla",
            "seat_name": "Belgaum Dakshin",
            "state": "Karnataka",
            "aliases": ["Belgaum Dakshin", "Belagavi South"],
            "asset": {"type": "svg", "path": "/maps/mla/custom-bd.svg", "aspect_ratio": "4 / 3"},
            "features": [
                {
                    "feature_key": "custom-core",
                    "label": "Custom Core",
                    "aliases": ["nath pai circle"],
                    "anchor": {"x": 50, "y": 50},
                }
            ],
            "fallback_anchors": [{"x": 10, "y": 10}],
            "status": "live",
        },
    )
    assert create_resp.status_code == 200, create_resp.text

    resp = client.get("/api/maps/seat-manifest", headers=_auth_headers("sanket", 10))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["source"] == "admin"
    assert data["asset"]["path"] == "/maps/mla/custom-bd.svg"
    assert data["features"][0]["feature_key"] == "custom-core"


def test_admin_seat_map_generate_creates_generated_manifest():
    _seed_database()
    admin_headers = _auth_headers("sysadmin", 10, role="admin")

    resp = client.post(
        "/api/admin/seat-maps/generate",
        headers=admin_headers,
        json={
            "seat_type": "mla",
            "seat_name": "Belgaum Dakshin",
            "state": "Karnataka",
            "aliases": ["Belgaum Dakshin"],
        },
    )
    assert resp.status_code == 200, resp.text
    manifest = resp.json()["manifest"]
    assert manifest["asset"]["type"] == "generated-svg"
    assert manifest["asset"]["generated"] is True
    assert "<svg" in manifest["asset"]["inline_svg"]
    assert len(manifest["features"]) >= 3


def test_admin_seat_map_workflow_reports_geography_and_tenants():
    _seed_database()
    admin_headers = _auth_headers("sysadmin", 10, role="admin")

    resp = client.get("/api/admin/seat-maps/workflow", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    belgaum = next(item for item in items if item["seat_key"] == "mla:Belgaum Dakshin")
    assert belgaum["geography_ready"] is True
    assert belgaum["tenant_count"] == 1
    assert belgaum["assembly_count"] == 2


def test_admin_seat_boundary_registration_and_workflow_visibility():
    _seed_database()
    admin_headers = _auth_headers("sysadmin", 10, role="admin")

    save_resp = client.post(
        "/api/admin/seat-boundaries",
        headers=admin_headers,
        json={
            "seat_type": "mla",
            "seat_name": "Belgaum Dakshin",
            "state": "Karnataka",
            "asset_type": "svg",
            "asset_path": "/maps/mla/belgaum-dakshin-real.svg",
            "metadata": {"aspect_ratio": "72 / 63"},
        },
    )
    assert save_resp.status_code == 200, save_resp.text

    workflow_resp = client.get("/api/admin/seat-maps/workflow", headers=admin_headers)
    assert workflow_resp.status_code == 200, workflow_resp.text
    belgaum = next(item for item in workflow_resp.json()["items"] if item["seat_key"] == "mla:Belgaum Dakshin")
    assert belgaum["boundary_ready"] is True
    assert belgaum["boundary_type"] == "svg"


def test_admin_imports_parliamentary_boundary_for_mp_seat():
    _seed_database()
    admin_headers = _auth_headers("sysadmin", 10, role="admin")

    feature_collection = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "pc_id": 2902,
                    "st_name": "Karnataka",
                    "pc_no": 2,
                    "pc_name": "Belagavi",
                    "pc_name_hi": "बेलगाम",
                    "pc_category": "GEN",
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[74.4, 15.7], [74.9, 15.7], [74.9, 16.0], [74.4, 16.0], [74.4, 15.7]]],
                },
            }
        ],
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "maps-master/parliamentary-constituencies/india_pc_2019_simplified.geojson",
            json.dumps(feature_collection),
        )
    buffer.seek(0)

    import_resp = client.post(
        "/api/admin/seat-boundaries/import-parliamentary?seat_type=mp&seat_name=Belagavi&state=Karnataka",
        headers=admin_headers,
        files={"file": ("maps-master.zip", buffer.getvalue(), "application/zip")},
    )
    assert import_resp.status_code == 200, import_resp.text
    boundary = import_resp.json()["boundary"]
    assert boundary["asset"]["type"] == "geojson"
    assert boundary["seat_key"] == "mp:Belagavi"

    workflow_resp = client.get("/api/admin/seat-maps/workflow", headers=admin_headers)
    assert workflow_resp.status_code == 200, workflow_resp.text
    belagavi = next(item for item in workflow_resp.json()["items"] if item["seat_key"] == "mp:Belagavi")
    assert belagavi["boundary_ready"] is True
    assert belagavi["boundary_type"] == "geojson"

    generate_resp = client.post(
        "/api/admin/seat-maps/generate",
        headers=admin_headers,
        json={
            "seat_type": "mp",
            "seat_name": "Belagavi",
            "state": "Karnataka",
            "aliases": ["Belagavi"],
        },
    )
    assert generate_resp.status_code == 200, generate_resp.text
    manifest = generate_resp.json()["manifest"]
    assert manifest["asset"]["type"] == "geojson"
    assert manifest["asset"]["generated"] is False
    assert manifest["source"] == "generated-from-boundary"


def test_admin_imports_builtin_parliamentary_boundary_for_mp_seat(monkeypatch):
    _seed_database()
    admin_headers = _auth_headers("sysadmin", 10, role="admin")

    monkeypatch.setattr(
        admin_api,
        "import_builtin_parliamentary_boundary_for_seat",
        lambda **kwargs: {
            "seat_key": "mp:Belagavi",
            "seat_type": "mp",
            "seat_name": "Belagavi",
            "state": "Karnataka",
            "asset": {"type": "geojson", "path": "", "inline_svg": "", "geojson": {"type": "FeatureCollection", "features": []}},
            "metadata": {"aspect_ratio": "100 / 60"},
            "status": "verified",
            "source": "datameet-parliamentary-2019",
        },
    )

    resp = client.post(
        "/api/admin/seat-boundaries/import-parliamentary-auto",
        headers=admin_headers,
        json={"seat_type": "mp", "seat_name": "Belagavi", "state": "Karnataka"},
    )
    assert resp.status_code == 200, resp.text
    boundary = resp.json()["boundary"]
    assert boundary["seat_key"] == "mp:Belagavi"
    assert boundary["asset"]["type"] == "geojson"
