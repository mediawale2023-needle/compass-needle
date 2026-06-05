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


def test_save_overrides_to_db_preserves_shared_geography_rows():
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
    assert row_map[(10, "geo_manual_override", "shahapur")] == "Belgaum South"
    assert row_map[(10, "phone_mapping", "whatsapp:+918888888888")] == "10"
    assert (2, "geo_override", "old locality") not in row_map
    assert (2, "phone_mapping", "whatsapp:+919999999999") not in row_map


def test_get_all_overrides_keeps_legacy_geo_override_as_manual_fallback():
    _seed_database()

    with test_engine.begin() as conn:
        now = datetime.utcnow()
        conn.execute(
            text(
                """
                INSERT INTO tenant_overrides (tenant_id, override_type, key, value, created_at)
                VALUES
                    (10, 'geo_override', 'shahapur', 'Wrong Assembly', :now),
                    (10, 'geo_manual_override', 'teacher colony', 'Belgaum South', :now)
                """
            ),
            {"now": now},
        )

    overrides = dbmod.get_all_overrides()

    assert overrides["geo_overrides"]["10"]["teacher colony"] == "Belgaum South"
    assert overrides["geo_overrides"]["10"]["shahapur"] == "Wrong Assembly"


def test_cleanup_legacy_generated_geo_overrides_deletes_alias_collisions_only():
    _seed_database()

    with test_engine.begin() as conn:
        now = datetime.utcnow()
        conn.execute(
            text(
                """
                INSERT INTO tenant_overrides (tenant_id, override_type, key, value, created_at)
                VALUES
                    (10, 'geo_override', 'shahapur', 'Wrong Assembly', :now),
                    (10, 'geo_override', 'teacher colony', 'Wrong Assembly', :now),
                    (10, 'geo_manual_override', 'teacher colony manual', 'Belgaum South', :now)
                """
            ),
            {"now": now},
        )

    result = dbmod.cleanup_legacy_generated_geo_overrides()

    assert result["deleted"] == 1
    assert result["tenants"] == 1

    with test_engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT override_type, key, value
                FROM tenant_overrides
                WHERE tenant_id = 10
                ORDER BY override_type, key
                """
            )
        ).fetchall()

    assert ("geo_override", "shahapur", "Wrong Assembly") not in rows
    assert ("geo_override", "teacher colony", "Wrong Assembly") in rows
    assert ("geo_manual_override", "teacher colony manual", "Belgaum South") in rows


def test_purge_generated_geo_aliases_deletes_only_alias_rows():
    _seed_database()

    result = dbmod.purge_generated_geo_aliases()

    assert result["deleted"] == 1
    assert result["tenants"] == 1

    with test_engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT override_type, key, value
                FROM tenant_overrides
                ORDER BY override_type, key
                """
            )
        ).fetchall()

    assert ("geo_alias", "shahapur", '{"assembly":"Belgaum South","display":"Shahapur"}') not in rows
    assert ("phone_mapping", "whatsapp:+919999999999", "2") in rows


def test_wipe_all_geography_data_removes_shared_and_manual_geography_rows_only():
    _seed_database()

    with test_engine.begin() as conn:
        now = datetime.utcnow()
        conn.execute(
            text(
                """
                INSERT INTO tenant_overrides (tenant_id, override_type, key, value, created_at)
                VALUES
                    (10, 'geo_manual_override', 'teacher colony', 'Belgaum South', :now),
                    (10, 'geo_override', 'old locality', 'Belgaum South', :now)
                """
            ),
            {"now": now},
        )

    result = dbmod.wipe_all_geography_data()

    assert result["geography_data"] == 1
    assert result["geo_alias"] == 1
    assert result["geo_manual_override"] == 1
    assert result["geo_override"] >= 2

    with test_engine.connect() as conn:
        remaining = conn.execute(
            text(
                """
                SELECT override_type, key
                FROM tenant_overrides
                ORDER BY override_type, key
                """
            )
        ).fetchall()

    assert remaining == [("phone_mapping", "whatsapp:+919999999999")]


def test_run_one_time_geography_reset_applies_once_and_records_marker():
    _seed_database()

    first = dbmod.run_one_time_geography_reset("reset-2026-06-05")
    second = dbmod.run_one_time_geography_reset("reset-2026-06-05")

    assert first["applied"] is True
    assert first["summary"]["deleted_total"] == 3
    assert second == {"applied": False, "reason": "already_applied"}

    with test_engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT override_type, key
                FROM tenant_overrides
                ORDER BY override_type, key
                """
            )
        ).fetchall()

    assert rows == [
        ("phone_mapping", "whatsapp:+919999999999"),
        ("system_migration", "reset-2026-06-05"),
    ]
