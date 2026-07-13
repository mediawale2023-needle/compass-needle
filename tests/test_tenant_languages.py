import json
import os
import sys
from datetime import datetime

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
TEST_DB_URL = "sqlite:///./test_tenant_languages.db"

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

import sansadx_backend.db as dbmod
from sansadx_backend.db import Base
import modules.tenant_languages as tenant_languages

test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False)


def _seed_database():
    dbmod.engine = test_engine
    dbmod.SessionLocal = TestSession
    tenant_languages.SessionLocal = TestSession
    tenant_languages.clear_tenant_language_cache()

    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    with test_engine.begin() as conn:
        now = datetime.utcnow()
        conn.execute(text("""
            INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active, created_at, config)
            VALUES
                (1, 'Maharashtra MP', 'Bangalore North', '+910000000001', 'Pro', 1, :now, :cfg1),
                (2, 'Karnataka MP', 'Mumbai North', '+910000000002', 'Pro', 1, :now, :cfg2),
                (3, 'No Profile MP', 'Somewhere', '+910000000003', 'Pro', 1, :now, :cfg3),
                (4, 'Override MP', 'Elsewhere', '+910000000004', 'Pro', 1, :now, :cfg4)
        """), {
            "now": now,
            "cfg1": json.dumps({}),
            "cfg2": json.dumps({}),
            "cfg3": json.dumps({}),
            "cfg4": json.dumps({"communication_languages": ["Tamil", "English"]}),
        })
        conn.execute(text("""
            INSERT INTO tenant_profiles (tenant_id, mp_name, constituency, state, house, created_at)
            VALUES
                (1, 'MP One', 'Bangalore North', 'Maharashtra', 'Lok Sabha', :now),
                (2, 'MP Two', 'Mumbai North', 'Karnataka', 'Lok Sabha', :now),
                (4, 'MP Four', 'Elsewhere', 'Tamil Nadu', 'Lok Sabha', :now)
        """), {"now": now})


def test_state_based_default_maharashtra():
    _seed_database()
    assert tenant_languages.resolve_tenant_languages(1) == ["Marathi", "Hindi", "English", "Hinglish"]


def test_state_based_default_karnataka():
    _seed_database()
    assert tenant_languages.resolve_tenant_languages(2) == ["Kannada", "English", "Hindi", "Hinglish"]


def test_fallback_when_no_profile_row():
    _seed_database()
    assert tenant_languages.resolve_tenant_languages(3) == ["Hindi", "Hinglish", "English"]


def test_explicit_config_override_wins_over_state():
    _seed_database()
    # Tenant 4 has state=Tamil Nadu (which would default to Tamil/English) but
    # an explicit override should win.
    assert tenant_languages.resolve_tenant_languages(4) == ["Tamil", "English"]


def test_unknown_tenant_id_falls_back_safely():
    _seed_database()
    assert tenant_languages.resolve_tenant_languages(9999) == ["Hindi", "Hinglish", "English"]


def test_result_is_cached_across_calls():
    _seed_database()
    first = tenant_languages.resolve_tenant_languages(1)
    with test_engine.begin() as conn:
        conn.execute(
            text("UPDATE tenant_profiles SET state = 'Karnataka' WHERE tenant_id = 1"),
        )
    second = tenant_languages.resolve_tenant_languages(1)
    assert second == first  # still Maharashtra languages: cache not invalidated

    tenant_languages.clear_tenant_language_cache(1)
    third = tenant_languages.resolve_tenant_languages(1)
    assert third == ["Kannada", "English", "Hindi", "Hinglish"]
