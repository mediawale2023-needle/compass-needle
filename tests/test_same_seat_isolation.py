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


def test_auto_generate_overrides_fans_out_shared_seat_geography_per_tenant():
    _seed_database()

    result = geography_resolver.auto_generate_overrides()

    assert result["success"] is True

    with test_engine.connect() as conn:
        mp_rows = conn.execute(
            text(
                """
                SELECT tenant_id, key, value
                FROM tenant_overrides
                WHERE override_type = 'geo_alias'
                ORDER BY tenant_id, key
                """
            )
        ).fetchall()

    rows_by_tenant = {}
    for tenant_id, key, value in mp_rows:
        rows_by_tenant.setdefault(tenant_id, {})[key] = value

    assert "Belgaum Uttar" in rows_by_tenant[11]["hanuman nagar"]
    assert "Belgaum Uttar" in rows_by_tenant[12]["hanuman nagar"]
    assert "Belgaum Uttar" in rows_by_tenant[13]["hanuman nagar"]
    assert "Belgaum Uttar" in rows_by_tenant[11]["tilakwadi"]
    assert "Belgaum Uttar" in rows_by_tenant[12]["tilakwadi"]
    assert "Belgaum Uttar" in rows_by_tenant[13]["tilakwadi"]
    assert "sector 1" not in rows_by_tenant[11]
    assert "sector 1" not in rows_by_tenant[12]
    assert "sector 1" not in rows_by_tenant[13]
    assert "Core Zone" in rows_by_tenant[21]["sector 1"]
