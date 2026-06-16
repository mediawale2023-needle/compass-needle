import os
import sys
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


TEST_DB_URL = "sqlite:///./test_same_seat_isolation.db"
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["ENV"] = "test"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sansadx_backend.db as dbmod
from sansadx_backend.db import Base
import modules.geography_resolver as geography_resolver


test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False)


def _seed_database():
    dbmod.engine = test_engine
    dbmod.SessionLocal = TestSession
    geography_resolver.SessionLocal = TestSession
    Base.metadata.create_all(bind=test_engine)

    with test_engine.begin() as conn:
        for table_name in ("tenant_overrides", "users", "tenant_profiles", "tenants"):
            conn.execute(text(f"DELETE FROM {table_name}"))  # nosec B608

        now = datetime.utcnow()
        conn.execute(
            text(
                """
                INSERT INTO tenants (
                    id, name, constituency, whatsapp_number, subscription_plan,
                    tenant_type, account_stage, seat_type, is_active, created_at
                )
                VALUES
                    (11, 'Belagavi Aspirant A', 'Belagavi', '+910000000011', 'Pro', 'aspirant', 'aspirant', 'mp', 1, :now),
                    (12, 'Belagavi Aspirant B', 'Belagavi', '+910000000012', 'Pro', 'aspirant', 'aspirant', 'mp', 1, :now),
                    (13, 'Belagavi Elected MP', 'Belagavi', '+910000000013', 'Pro', 'mp', 'elected', 'mp', 1, :now),
                    (21, 'Belagavi North MLA', 'Belagavi North', '+910000000021', 'Pro', 'mla', 'elected', 'mla', 1, :now)
                """
            ),
            {"now": now},
        )
        conn.execute(
            text(
                """
                INSERT INTO tenant_overrides (tenant_id, override_type, key, value, created_at)
                VALUES
                    (NULL, 'geography_data', 'mp:Belagavi/Belgaum Uttar', :mp_geo, :now),
                    (NULL, 'geography_data', 'mla:Belagavi North/Core Zone', :mla_geo, :now)
                """
            ),
            {
                "now": now,
                "mp_geo": '[{"station_number":"1","locality":"Hanuman Nagar","building_name":""},{"station_number":"2","locality":"Tilakwadi","building_name":""}]',
                "mla_geo": '[{"station_number":"1","locality":"Sector 1","building_name":""}]',
            },
        )


def test_auto_generate_overrides_purges_deprecated_generated_aliases():
    _seed_database()

    with test_engine.begin() as conn:
        now = datetime.utcnow()
        conn.execute(
            text(
                """
                INSERT INTO tenant_overrides (tenant_id, override_type, key, value, created_at)
                VALUES
                    (11, 'geo_alias', 'hanuman nagar', '{"assembly":"Belgaum Uttar","display":"Hanuman Nagar"}', :now),
                    (12, 'geo_alias', 'tilakwadi', '{"assembly":"Belgaum Uttar","display":"Tilakwadi"}', :now),
                    (21, 'geo_alias', 'sector 1', '{"assembly":"Core Zone","display":"Sector 1"}', :now)
                """
            ),
            {"now": now},
        )

    result = geography_resolver.auto_generate_overrides()

    assert result["success"] is True
    assert result["aliases_deleted"] == 3

    with test_engine.connect() as conn:
        remaining = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM tenant_overrides
                WHERE override_type = 'geo_alias'
                """
            )
        ).scalar_one()

    assert remaining == 0


def test_same_seat_tenants_share_seat_scoped_manual_corrections():
    _seed_database()
    geography_resolver.reload_index()

    with test_engine.begin() as conn:
        now = datetime.utcnow()
        conn.execute(
            text(
                """
                INSERT INTO tenant_overrides (tenant_id, override_type, key, value, created_at)
                VALUES
                    (NULL, 'geo_seat_manual_override', 'mp:Belagavi::hanuman colony', 'Belgaum Uttar', :now)
                """
            ),
            {"now": now},
        )

    tenant_a = geography_resolver.resolve_location("Hanuman Colony drainage issue", tenant_id=11)
    tenant_b = geography_resolver.resolve_location("Hanuman Colony water problem", tenant_id=12)
    mla_tenant = geography_resolver.resolve_location("Hanuman Colony drainage issue", tenant_id=21)

    assert tenant_a["location_resolved"] is True
    assert tenant_a["assembly_constituency"] == "Belgaum Uttar"
    assert tenant_a["match_type"] in {"db_alias_exact", "db_alias_boundary"}

    assert tenant_b["location_resolved"] is True
    assert tenant_b["assembly_constituency"] == "Belgaum Uttar"
    assert tenant_b["match_type"] in {"db_alias_exact", "db_alias_boundary"}

    assert mla_tenant["location_resolved"] is False
