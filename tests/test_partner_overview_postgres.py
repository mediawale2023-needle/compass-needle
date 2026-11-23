"""PostgreSQL-backed regression for the Partner Overview 500 (cases.assigned_to is an INTEGER in prod).

SQLite is permissive (TRIM() works on integers), so the original defect was invisible to the seeded
SQLite tests. This module runs the real partner SQL on PostgreSQL against tables created from the
ORM metadata, with ``cases.assigned_to`` altered to INTEGER like production.

Opt-in like the other real-PostgreSQL files: set ``NEEDLE_PARTNER_PG_URL`` to a THROWAWAY database (the test
only creates and drops its own uniquely named schema). CI provides one via a service container.
"""

import os
import uuid
from datetime import datetime

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_partner_overview_postgres.db")

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.exc import DBAPIError  # noqa: E402

from modules.dashboard_overview import (  # noqa: E402
    PARTNER_CASE_SQL,
    PARTNER_LETTER_SQL,
    PARTNER_SYNC_SQL,
)
from modules.synthetic_cases import sql_is_live  # noqa: E402
from sansadx_backend.db import Base  # noqa: E402

PG_URL = os.environ.get("NEEDLE_PARTNER_PG_URL", "")
pytestmark = pytest.mark.skipif(not PG_URL, reason="NEEDLE_PARTNER_PG_URL not set")

ORIGINAL_UNASSIGNED = "TRIM(c.assigned_to) = ''"
FIXED_UNASSIGNED = "TRIM(CAST(c.assigned_to AS TEXT)) = ''"


@pytest.fixture(scope="module")
def pg():
    # When opted in, an unreachable database must FAIL, not skip: a silent skip hid the original defect.
    engine = create_engine(PG_URL, connect_args={"connect_timeout": 5})
    schema = f"partner_ov_{uuid.uuid4().hex[:8]}"
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped = create_engine(
        PG_URL, connect_args={"options": f"-csearch_path={schema}"}
    )
    try:
        Base.metadata.create_all(bind=scoped)
        with scoped.begin() as conn:
            # Production drift: the live column is an integer FK to users.id.
            conn.execute(text(
                "ALTER TABLE cases ALTER COLUMN assigned_to TYPE INTEGER USING assigned_to::integer"
            ))
            conn.execute(text(
                "INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, "
                "is_active, created_at, seat_type, account_stage) VALUES "
                "(1, 'T', 'Belagavi', '+919000000001', 'Pro', true, :now, 'mp', 'elected')"
            ), {"now": datetime(2026, 3, 1)})
            for cid, assigned in ((1, 7), (2, None)):
                conn.execute(text(
                    "INSERT INTO cases (id, tenant_id, user_phone, case_ref, status, raw_message, "
                    "is_deleted, created_at, updated_at, assigned_to) VALUES "
                    "(:i, 1, '+919650787758', :ref, 'new', 'x', false, :t, :t, :a)"
                ), {"i": cid, "ref": f"CN-{cid}", "t": datetime(2026, 3, 1), "a": assigned})
        yield scoped
    finally:
        scoped.dispose()
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()


def _case_sql(unassigned_expr: str) -> str:
    sql = PARTNER_CASE_SQL.format(live=sql_is_live("c"))
    # Only the unassigned expression differs between the original and corrected statements.
    return sql.replace(FIXED_UNASSIGNED, unassigned_expr)


def test_assigned_to_is_integer_like_production(pg):
    with pg.connect() as conn:
        dtype = conn.execute(text(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = 'cases' AND column_name = 'assigned_to'"
        )).scalar()
    assert dtype == "integer"


def test_original_sql_fails_on_integer_assigned_to(pg):
    assert ORIGINAL_UNASSIGNED in _case_sql(ORIGINAL_UNASSIGNED)
    with pg.connect() as conn:
        with pytest.raises(DBAPIError) as exc:
            conn.execute(text(_case_sql(ORIGINAL_UNASSIGNED)), {"tid": 1})
    assert "btrim" in str(exc.value).lower() or "integer" in str(exc.value).lower()


def test_corrected_sql_succeeds_with_one_assigned_one_unassigned(pg):
    with pg.connect() as conn:
        rows = conn.execute(text(_case_sql(FIXED_UNASSIGNED)), {"tid": 1}).mappings().all()
    assert {r["id"]: r["unassigned"] for r in rows} == {1: 0, 2: 1}


def test_shipped_partner_sql_runs_on_postgres(pg):
    """The exact shipped statements (not the test's rewrites) execute against production-typed tables."""
    with pg.connect() as conn:
        rows = conn.execute(text(PARTNER_CASE_SQL.format(live=sql_is_live("c"))), {"tid": 1}).mappings().all()
        assert sum(r["unassigned"] for r in rows) == 1
        conn.execute(text(PARTNER_SYNC_SQL), {"tid": 1}).all()
        for direction, statuses in (("inbox", "'new', 'needs_review', 'processing'"), ("outbox", "'drafted'")):
            conn.execute(
                text(PARTNER_LETTER_SQL.format(statuses=statuses)), {"tid": 1, "direction": direction}
            ).one()
