import os
import sys
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


TEST_DB_URL = "sqlite:///./test_override_persistence.db"
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["ENV"] = "test"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sansadx_backend.db as dbmod
from sansadx_backend.db import Base


test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False)


def _seed_database():
    dbmod.engine = test_engine
    dbmod.SessionLocal = TestSession
    Base.metadata.create_all(bind=test_engine)

    with test_engine.begin() as conn:
        conn.execute(text("DELETE FROM tenant_overrides"))  # nosec B608
        now = datetime.utcnow()
        conn.execute(
            text(
                """
                INSERT INTO tenant_overrides (tenant_id, override_type, key, value, created_at)
                VALUES
                    (NULL, 'geography_data', 'mla:Belagavi North/Core Zone', '[]', :now),
                    (10, 'geo_alias', 'shahapur', '{"assembly":"Belgaum South","display":"Shahapur"}', :now),
                    (2, 'geo_override', 'old locality', 'Old Assembly', :now),
                    (2, 'phone_mapping', 'whatsapp:+919999999999', '2', :now)
                """
            ),
            {"now": now},
        )


def test_save_overrides_to_db_preserves_shared_geography_and_alias_rows():
    _seed_database()

    dbmod.save_overrides_to_db(
        {
            "whatsapp:+918888888888": "10",
            "geo_overrides": {
                "10": {
                    "shahapur": "Belgaum South",
                }
            },
        }
    )

    with test_engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT tenant_id, override_type, key, value
                FROM tenant_overrides
                ORDER BY override_type, tenant_id, key
                """
            )
        ).fetchall()

    row_map = {(tenant_id, override_type, key): value for tenant_id, override_type, key, value in rows}

    assert row_map[(None, "geography_data", "mla:Belagavi North/Core Zone")] == "[]"
    assert row_map[(10, "geo_alias", "shahapur")] == '{"assembly":"Belgaum South","display":"Shahapur"}'
    assert row_map[(10, "geo_override", "shahapur")] == "Belgaum South"
    assert row_map[(10, "phone_mapping", "whatsapp:+918888888888")] == "10"
    assert (2, "geo_override", "old locality") not in row_map
    assert (2, "phone_mapping", "whatsapp:+919999999999") not in row_map
