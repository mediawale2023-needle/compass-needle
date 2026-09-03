"""
tests/test_govt_portal_seed_durability.py — Maharashtra pilot-readiness
finding: seed_govt_portals() previously overwrote a portal row's
operational/verification state (verification_status, source_note,
live_session_supported, status_check_adapter) on EVERY process start, from
whatever the checked-in modules/data/govt_portals.json still said — so a
manually-confirmed live re-check (via PATCH /admin/govt-portals/{id}, or a
direct DB update after a real staff-run test) would be silently reverted
on the very next deploy/restart, with no error or log line.

These tests pin the fix: those four fields survive a reseed once a row
already exists, while genuinely reference/research fields (base_url,
department_taxonomy, field_schema, otp_bound) still re-sync from the JSON
file every start, and a brand-new portal row still gets its full initial
state from the JSON on first insert.
"""
import json
import os
import sys

from sqlalchemy import create_engine, text

TEST_DB_URL = "sqlite:///./test_govt_portal_seed_durability.db"
os.environ.setdefault("DATABASE_URL", TEST_DB_URL)
os.environ.setdefault("ENV", "test")
os.environ.setdefault("JWT_SECRET", "test-secret-key-32-characters-minimum-ok")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-testing")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sansadx_backend.db as dbmod
from sansadx_backend.db import Base
from modules.govt_sync.seed import seed_govt_portals

test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})


def _reset_db():
    dbmod.engine = test_engine
    Base.metadata.create_all(bind=test_engine)
    with test_engine.begin() as conn:
        conn.execute(text("DELETE FROM govt_portals"))


def _portal_row(portal_name: str) -> dict:
    with test_engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT verification_status, source_note, live_session_supported, "
                "status_check_adapter, base_url, otp_bound, active "
                "FROM govt_portals WHERE portal_name = :name"
            ),
            {"name": portal_name},
        ).mappings().first()
    result = dict(row)
    # SQLite has no native boolean type — these columns come back as 0/1
    # ints via a raw text() query (unlike the ORM, which would coerce them).
    for bool_field in ("live_session_supported", "otp_bound", "active"):
        result[bool_field] = bool(result[bool_field])
    return result


def _seed_names() -> list[str]:
    seed_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "modules", "data", "govt_portals.json",
    )
    with open(seed_path, encoding="utf-8") as f:
        return [p["portal_name"] for p in json.load(f)]


def test_manual_verification_state_survives_a_reseed():
    """The exact Maharashtra pilot-readiness scenario: seed once (creates
    the row from the JSON), then simulate an admin/live-check confirming a
    DIFFERENT state than the JSON currently says, then reseed (simulating a
    backend restart) — the confirmed state must survive, not be reverted."""
    _reset_db()
    seed_govt_portals()

    portal_name = "Maharashtra Aaple Sarkar Grievance Redressal"
    before = _portal_row(portal_name)
    assert before is not None

    with test_engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE govt_portals SET verification_status = :vs, source_note = :sn, "
                "live_session_supported = :lss, status_check_adapter = :sca "
                "WHERE portal_name = :name"
            ),
            {
                "vs": "confirmed_live_2026_09_03",
                "sn": "Manually re-verified after a real staff-run check — do not let a restart silently revert this.",
                "lss": not before["live_session_supported"],
                "sca": "maharashtra_aaplesarkar_api_v2_test_marker",
                "name": portal_name,
            },
        )

    # Simulate a backend restart / redeploy re-running the seed.
    seed_govt_portals()

    after = _portal_row(portal_name)
    assert after["verification_status"] == "confirmed_live_2026_09_03"
    assert "do not let a restart silently revert this" in after["source_note"]
    assert after["live_session_supported"] == (not before["live_session_supported"])
    assert after["status_check_adapter"] == "maharashtra_aaplesarkar_api_v2_test_marker"


def test_reference_fields_still_resync_from_seed_file_on_every_run():
    """The fix must be targeted, not a blanket 'never update anything on
    conflict' regression: genuinely reference/research data (base_url,
    otp_bound) is still ops-edited only in the JSON file and must keep
    re-syncing on every start, same as before this fix."""
    _reset_db()
    seed_govt_portals()

    portal_name = "Maharashtra Aaple Sarkar Grievance Redressal"
    with test_engine.begin() as conn:
        conn.execute(
            text("UPDATE govt_portals SET base_url = :url, otp_bound = :otp WHERE portal_name = :name"),
            {"url": "https://stale-test-only-url.example", "otp": False, "name": portal_name},
        )

    seed_govt_portals()

    after = _portal_row(portal_name)
    # Reseeded back to whatever the real JSON file currently says — proves
    # these columns are NOT part of the "protected" set.
    assert after["base_url"] != "https://stale-test-only-url.example"
    assert after["otp_bound"] is True


def test_active_and_is_primary_remain_unaffected_by_the_fix():
    """Pre-existing behavior (unchanged by this fix): active/is_primary
    were already excluded from the reseed's ON CONFLICT UPDATE."""
    _reset_db()
    seed_govt_portals()

    portal_name = "Rajasthan Sampark"
    with test_engine.begin() as conn:
        conn.execute(
            text("UPDATE govt_portals SET active = 0 WHERE portal_name = :name"),
            {"name": portal_name},
        )

    seed_govt_portals()

    after = _portal_row(portal_name)
    assert after["active"] is False


def test_new_portal_row_still_gets_full_initial_state_from_seed():
    """A brand-new row (first insert, no prior conflict) must still be
    populated entirely from the JSON — the fix only changes what happens on
    an UPDATE to an EXISTING row, not the initial INSERT."""
    _reset_db()
    seed_govt_portals()

    names = _seed_names()
    assert "Maharashtra Aaple Sarkar Grievance Redressal" in names

    row = _portal_row("Maharashtra Aaple Sarkar Grievance Redressal")
    assert row["verification_status"] == "confirmed"
    assert row["status_check_adapter"] == "maharashtra_aaplesarkar_api"
    assert row["live_session_supported"] is False
