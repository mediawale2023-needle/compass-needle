import os
import sys
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


TEST_DB_URL = "sqlite:///./test_case_geography_backfill.db"
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["ENV"] = "test"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sansadx_backend.db as dbmod
from sansadx_backend.db import Base
from scripts.backfill_case_geography import backfill_tenant_case_geography


test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False)


def _seed_database():
    dbmod.engine = test_engine
    dbmod.SessionLocal = TestSession
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    with test_engine.begin() as conn:
        for table_name in ("cases", "tenant_profiles", "users", "tenants", "tenant_overrides"):
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
                    (10, 'Jadhav', 'Belagavi', '+910000000010', 'Pro', 'aspirant', 'aspirant', 'mp', 1, :now),
                    (11, 'Other Tenant', 'Aligarh', '+910000000011', 'Pro', 'mp', 'elected', 'mp', 1, :now)
                """
            ),
            {"now": now},
        )
        conn.execute(
            text(
                """
                INSERT INTO tenant_overrides (tenant_id, override_type, key, value, created_at)
                VALUES
                    (NULL, 'geography_data', 'mp:Belagavi/Belgaum South', :geo, :now)
                """
            ),
            {
                "now": now,
                "geo": '[{"station_number":"1","locality":"Shahapur","building_name":""}]',
            },
        )
        conn.execute(
            text(
                """
                INSERT INTO cases (
                    id, tenant_id, user_phone, raw_message, category, status, location, assembly, case_metadata, is_deleted, created_at
                )
                VALUES
                    (101, 10, '+919999999999', 'Shahapur madhe paani nahi', 'Uncategorised', 'pending', NULL, NULL, '{}', 0, :now),
                    (102, 10, '+919999999999', 'Unknown place issue', 'Uncategorised', 'pending', NULL, NULL, '{}', 0, :now),
                    (201, 11, '+918888888888', 'Shahapur madhe paani nahi', 'Uncategorised', 'pending', NULL, NULL, '{}', 0, :now)
                """
            ),
            {"now": now},
        )


def test_backfill_tenant_case_geography_updates_only_target_tenant(monkeypatch):
    _seed_database()

    monkeypatch.setattr(
        "scripts.backfill_case_geography._get_tenant_constituency",
        lambda tenant_id: "Belagavi" if tenant_id == 10 else "Aligarh",
    )
    monkeypatch.setattr(
        "scripts.backfill_case_geography.resolve_location",
        lambda text, scope_parliamentary=None, tenant_id=None: {
            "location_resolved": True,
            "matched_value": "Shahapur",
            "assembly_constituency": "Belgaum South",
            "confidence_level": "boundary",
            "match_type": "word_boundary",
        } if tenant_id == 10 and "Shahapur" in text else {"location_resolved": False, "reason": "no_match"},
    )

    result = backfill_tenant_case_geography(tenant_id=10, limit=10)

    assert result["examined"] == 2
    assert result["updated"] == 1
    assert result["unresolved"] == 1

    with test_engine.connect() as conn:
        target = conn.execute(
            text("SELECT location, assembly, case_metadata FROM cases WHERE id = 101")
        ).fetchone()
        unresolved = conn.execute(
            text("SELECT case_metadata FROM cases WHERE id = 102")
        ).fetchone()
        other = conn.execute(
            text("SELECT location, assembly FROM cases WHERE id = 201")
        ).fetchone()

    assert target[0] == "Shahapur"
    assert target[1] == "Belgaum South"
    assert '"geography_diagnostics"' in target[2]
    assert '"backfill_raw_message"' in target[2]
    assert '"unresolved"' in unresolved[0]
    assert other[0] is None
    assert other[1] is None
