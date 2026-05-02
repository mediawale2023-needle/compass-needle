import csv
import os
import sys
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


TEST_DB_URL = "sqlite:///./test_geography_curation_apply.db"
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["ENV"] = "test"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sansadx_backend.db as dbmod
from sansadx_backend.db import Base
import scripts.geography_curation_apply as curation_apply
from scripts.geography_curation_apply import apply_curation_csv, _override_keys_for_locality


test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False)


def _seed_database():
    dbmod.engine = test_engine
    dbmod.SessionLocal = TestSession
    curation_apply.SessionLocal = TestSession
    Base.metadata.create_all(bind=test_engine)

    with test_engine.begin() as conn:
        for table_name in ("tenant_overrides", "tenants"):
            conn.execute(text(f"DELETE FROM {table_name}"))  # nosec B608

        now = datetime.utcnow()
        conn.execute(
            text(
                """
                INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active, created_at)
                VALUES
                    (2, 'Ghaziabad MP', 'Ghaziabad', '+910000000002', 'Pro', 1, :now),
                    (3, 'Aligarh MP', 'Aligarh', '+910000000003', 'Pro', 1, :now)
                """
            ),
            {"now": now},
        )
        conn.execute(
            text(
                """
                INSERT INTO tenant_overrides (tenant_id, override_type, key, value, created_at)
                VALUES
                    (2, 'geo_override', 'lohiya nagar', 'Ghaziabad', :now),
                    (2, 'geo_override', 'lohia nagar', 'Ghaziabad', :now),
                    (3, 'geo_override', 'ramghat road', 'Koil', :now)
                """
            ),
            {"now": now},
        )


def _write_csv(tmp_path: Path, rows: list[dict]) -> Path:
    csv_path = tmp_path / "curation.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "parliamentary_constituency",
                "locality",
                "ambiguous_assemblies",
                "assembly_count",
                "status",
                "curated_assembly",
                "suggested_action",
                "notes",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return csv_path


def test_apply_curation_csv_dry_run_leaves_db_unchanged(tmp_path):
    _seed_database()
    csv_path = _write_csv(
        tmp_path,
        [
            {
                "parliamentary_constituency": "Ghaziabad",
                "locality": "Lohiya Nagar",
                "ambiguous_assemblies": "Ghaziabad | Muradnagar | Loni",
                "assembly_count": "3",
                "status": "resolved",
                "curated_assembly": "Loni",
                "suggested_action": "",
                "notes": "",
            }
        ],
    )

    result = apply_curation_csv(csv_path, dry_run=True)

    assert result["apply"]["dry_run"] is True
    with test_engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT key, value FROM tenant_overrides
                WHERE tenant_id = 2 AND override_type = 'geo_override'
                ORDER BY key
                """
            )
        ).fetchall()
    assert rows == [("lohia nagar", "Ghaziabad"), ("lohiya nagar", "Ghaziabad")]


def test_apply_curation_csv_writes_resolved_and_clears_leave_unresolved(tmp_path):
    _seed_database()
    csv_path = _write_csv(
        tmp_path,
        [
            {
                "parliamentary_constituency": "Ghaziabad",
                "locality": "Lohiya Nagar",
                "ambiguous_assemblies": "Ghaziabad | Muradnagar | Loni",
                "assembly_count": "3",
                "status": "resolved",
                "curated_assembly": "Loni",
                "suggested_action": "",
                "notes": "",
            },
            {
                "parliamentary_constituency": "Aligarh",
                "locality": "Ramghat Road",
                "ambiguous_assemblies": "Aligarh | Koil",
                "assembly_count": "2",
                "status": "leave_unresolved",
                "curated_assembly": "",
                "suggested_action": "",
                "notes": "",
            },
            {
                "parliamentary_constituency": "Ghaziabad",
                "locality": "Patel Nagar",
                "ambiguous_assemblies": "Ghaziabad | Muradnagar",
                "assembly_count": "2",
                "status": "needs_review",
                "curated_assembly": "",
                "suggested_action": "",
                "notes": "",
            },
        ],
    )

    result = apply_curation_csv(csv_path)

    assert result["apply"]["resolved_applied"] == 1
    assert result["apply"]["left_unresolved_cleared"] == 1
    assert result["apply"]["needs_review_skipped"] == 1

    expected_keys = _override_keys_for_locality("Lohiya Nagar")
    with test_engine.connect() as conn:
        ghaziabad_rows = conn.execute(
            text(
                """
                SELECT key, value FROM tenant_overrides
                WHERE tenant_id = 2 AND override_type = 'geo_override'
                ORDER BY key
                """
            )
        ).fetchall()
        aligarh_rows = conn.execute(
            text(
                """
                SELECT key, value FROM tenant_overrides
                WHERE tenant_id = 3 AND override_type = 'geo_override'
                ORDER BY key
                """
            )
        ).fetchall()

    assert ghaziabad_rows == [(key, "Loni") for key in expected_keys]
    assert aligarh_rows == []


def test_apply_curation_csv_rejects_invalid_csv(tmp_path):
    _seed_database()
    csv_path = _write_csv(
        tmp_path,
        [
            {
                "parliamentary_constituency": "Ghaziabad",
                "locality": "Lohiya Nagar",
                "ambiguous_assemblies": "Ghaziabad | Muradnagar",
                "assembly_count": "2",
                "status": "resolved",
                "curated_assembly": "",
                "suggested_action": "",
                "notes": "",
            }
        ],
    )

    with pytest.raises(ValueError, match="CSV validation failed"):
        apply_curation_csv(csv_path)
