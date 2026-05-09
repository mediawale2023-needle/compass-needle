import os
import sys
from datetime import datetime, timedelta

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
TEST_DB_URL = "sqlite:///./test_convergence_api.db"

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


import api_router
import core.db_helpers as db_helpers
import main
import modules.csr_matching_engine as csr_matching_engine
import modules.csr_pipeline as csr_pipeline
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
    api_router.JWT_SECRET = TEST_JWT_SECRET

    Base.metadata.create_all(bind=test_engine)

    with test_engine.begin() as conn:
        for table_name in (
            "opportunity_company_matches",
            "csr_pipeline_entries",
            "csr_opportunities",
            "csr_companies",
            "token_blocklist",
            "users",
            "tenant_profiles",
            "tenants",
        ):
            conn.execute(text(f"DELETE FROM {table_name}"))  # nosec B608
        conn.execute(text("DROP TABLE IF EXISTS prs_schemes"))
        conn.execute(text("""
            CREATE TABLE prs_schemes (
                id INTEGER PRIMARY KEY,
                name VARCHAR(300) NOT NULL,
                full_name VARCHAR(500),
                ministry VARCHAR(300),
                aliases TEXT,
                first_seen DATE,
                last_seen DATE,
                answer_count INTEGER DEFAULT 0
            )
        """))

        now = datetime.utcnow()
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
        for username, tenant_id in (("mp_arun", 1), ("mp_priya", 2)):
            conn.execute(
                text(
                    """
                    INSERT INTO users
                        (tenant_id, username, password_hash, role, constituency, house, display_name, is_active)
                    VALUES
                        (:tenant_id, :username, :password_hash, 'mp', 'Test Constituency', 'Lok Sabha', :username, true)
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "username": username,
                    "password_hash": hash_password("ValidPass1!"),
                },
            )
        conn.execute(
            text(
                """
                INSERT INTO prs_schemes
                    (id, name, full_name, ministry, aliases, first_seen, last_seen, answer_count)
                VALUES
                    (1, 'Jal Jeevan Mission', 'Jal Jeevan Mission', 'Ministry of Jal Shakti',
                     '["JJM", "drinking water"]', '2024-01-01', '2025-01-01', 18),
                    (2, 'AMRUT 2.0', 'Atal Mission for Rejuvenation and Urban Transformation',
                     'Ministry of Housing and Urban Affairs', '["urban water", "sewerage"]',
                     '2024-01-01', '2025-01-01', 11),
                    (3, 'Samagra Shiksha', 'Samagra Shiksha', 'Ministry of Education',
                     '["school education", "learning"]', '2024-01-01', '2025-01-01', 14),
                    (4, 'National Social Assistance Programme', 'National Social Assistance Programme',
                     'Ministry of Rural Development', '["pension", "welfare beneficiary"]',
                     '2024-01-01', '2025-01-01', 9),
                    (5, 'Unrelated Tourism Promotion Scheme', 'Unrelated Tourism Promotion Scheme',
                     'Ministry of Tourism', '["tourism"]', '2024-01-01', '2025-01-01', 50)
                """
            )
        )


def _make_token(username: str, tenant_id: int) -> str:
    now = datetime.utcnow()
    payload = {
        "sub": username,
        "tid": tenant_id,
        "role": "mp",
        "iat": now.timestamp(),
        "exp": now + timedelta(hours=8),
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


def _headers(username="mp_arun", tenant_id=1):
    return {"Authorization": f"Bearer {_make_token(username, tenant_id)}"}


def _fake_company_matches(opportunity, _companies, _tenant_id, top_n=3):
    return [
        {
            "name": "Acme CSR Foundation",
            "company_id": 10,
            "slug": "acme-csr-foundation",
            "sector": "Water",
            "district": "Bangalore",
            "match_score": 86,
            "reason": "Strong sector alignment and local presence.",
            "suggested_next_action": "dpr",
            "suggested_approach": "Generate a convergence note after department verification.",
            "recommended_ask_amount": 25,
        }
    ][:top_n]


def test_convergence_opportunity_combines_grievance_scheme_and_csr(monkeypatch):
    _seed_database()

    monkeypatch.setattr(
        csr_pipeline,
        "get_grievance_clusters",
        lambda tenant_id, min_threshold=100: [
            {
                "category": "Infrastructure & Utilities",
                "volume": 225,
                "progress_pct": 100,
                "status": "verify",
                "csr_sector": "Service Delivery Strengthening",
                "affected_areas": [{"area": "Whitefield", "volume": 140}],
            }
        ],
    )
    monkeypatch.setattr(csr_matching_engine, "get_top_companies_for_opportunity", _fake_company_matches)
    monkeypatch.setattr(api_router, "_cached_load", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(api_router, "_load_ngo_data", lambda: [])

    resp = client.get("/api/convergence/opportunities", headers=_headers())

    assert resp.status_code == 200, resp.text
    opportunity = resp.json()["opportunities"][0]
    assert opportunity["category"] == "Infrastructure & Utilities"
    assert opportunity["government_route"]["schemes"][0]["name"] == "Jal Jeevan Mission"
    assert opportunity["government_route"]["schemes"][0]["source"] == "prs_schemes"
    assert opportunity["convergence_plan"]["scheme_source"] == "prs_schemes"
    assert opportunity["convergence_plan"]["scheme_match_status"] == "ranked"
    assert "department" in opportunity["government_route"]
    assert opportunity["convergence_plan"]["recommended_pathway"] == "hybrid"
    assert "CSR" in opportunity["convergence_plan"]["pathway_label"]
    assert opportunity["csr_route"]["top_companies"][0]["name"] == "Acme CSR Foundation"
    assert opportunity["next_action"]


def test_welfare_convergence_is_government_first(monkeypatch):
    _seed_database()

    monkeypatch.setattr(
        csr_pipeline,
        "get_grievance_clusters",
        lambda tenant_id, min_threshold=100: [
            {
                "category": "Government Schemes & Welfare",
                "volume": 180,
                "progress_pct": 90,
                "status": "watch",
                "csr_sector": "Last-mile Access & Outreach",
                "affected_areas": [{"area": "Hebbal", "volume": 80}],
            }
        ],
    )
    monkeypatch.setattr(csr_matching_engine, "get_top_companies_for_opportunity", _fake_company_matches)
    monkeypatch.setattr(api_router, "_cached_load", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(api_router, "_load_ngo_data", lambda: [])

    resp = client.get("/api/convergence/opportunities", headers=_headers())

    assert resp.status_code == 200, resp.text
    plan = resp.json()["opportunities"][0]["convergence_plan"]
    assert plan["recommended_pathway"] == "government_first"
    assert plan["pathway_label"] == "Government first"
    assert "statutory benefits" in plan["csr_complement"]
    assert plan["schemes"][0]["name"] == "National Social Assistance Programme"


def test_convergence_opportunities_use_requesting_tenant(monkeypatch):
    _seed_database()
    seen_tenant_ids = []

    def _clusters(tenant_id, min_threshold=100):
        seen_tenant_ids.append(tenant_id)
        if tenant_id == 2:
            return [
                {
                    "category": "Education",
                    "volume": 205,
                    "progress_pct": 100,
                    "status": "verify",
                    "csr_sector": "Last-mile Access & Outreach",
                    "affected_areas": [{"area": "Borivali", "volume": 110}],
                }
            ]
        return []

    monkeypatch.setattr(csr_pipeline, "get_grievance_clusters", _clusters)
    monkeypatch.setattr(csr_matching_engine, "get_top_companies_for_opportunity", _fake_company_matches)
    monkeypatch.setattr(api_router, "_cached_load", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(api_router, "_load_ngo_data", lambda: [])

    resp = client.get("/api/convergence/opportunities", headers=_headers("mp_priya", 2))

    assert resp.status_code == 200, resp.text
    assert seen_tenant_ids == [2]
    opportunities = resp.json()["opportunities"]
    assert len(opportunities) == 1
    assert opportunities[0]["category"] == "Education"
    assert opportunities[0]["constituency"] == "Mumbai North"
    assert opportunities[0]["convergence_plan"]["schemes"][0]["name"] == "Samagra Shiksha"
