"""
tests/test_govt_delhi_portal_config.py — Phase 1 Delhi CM Jan Sunwai
configuration: a staged, INACTIVE portal row with only the official URL.

Pins that:
- the row carries no invented API endpoint, taxonomy, selectors or adapter,
  and stays taxonomy_verified=false / active=false;
- it resolves for a Delhi tenant only when the portal is eligible for
  selection (active, primary, base_url set), otherwise Delhi keeps falling
  back to CPGRAMS exactly as before this row existed;
- Karnataka / Maharashtra / Rajasthan / Tamil Nadu / UP routing is unchanged,
  and unknown / missing states fail safely;
- reseeding never overwrites operational fields on the Delhi row;
- CURRENT BLOCKER (characterization, not a fix): the manual filing flow
  cannot record a reference for a portal with an empty department_taxonomy.
"""
import json
import os
import sys

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text

TEST_DB_URL = "sqlite:///./test_govt_delhi_portal_config.db"
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["ENV"] = "test"
os.environ.setdefault("JWT_SECRET", "test-secret-key-32-characters-minimum-ok")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-testing")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import api_router
import core.db_helpers as db_helpers
import sansadx_backend.db as dbmod
from sansadx_backend.db import Base
from modules.govt_sync.adapters import get_adapter
from modules.govt_sync.adapters.manual import ManualAssistedAdapter
from modules.govt_sync.seed import seed_govt_portals

test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})

_PORTALS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "modules", "data", "govt_portals.json",
)
DELHI = "Delhi CM Jan Sunwai"

# tenant_id -> state value stored on tenant_profiles (never altered to force a match)
_TENANTS = {
    1: "Delhi",
    2: "Karnataka",
    3: "Maharashtra",
    4: "Rajasthan",
    5: "Tamil Nadu",
    6: "Uttar Pradesh",
    7: "Goa",           # no active branded portal -> CPGRAMS fallback
    8: "",              # no state on file
    9: "Atlantis",      # invalid state
    10: "delhi",        # case-insensitive match, same as other states
}
_EXPECTED_UNCHANGED = {
    2: "Karnataka Janaspandana (iPGRS)",
    3: "Maharashtra Aaple Sarkar Grievance Redressal",
    4: "Rajasthan Sampark",
    5: "Tamil Nadu CM Helpline (Mudhalvarin Mugavari)",
    6: "UP Jansunwai (IGRS)",
    7: "CPGRAMS",
    8: "CPGRAMS",
    9: "CPGRAMS",
}


def _seed_row(name: str) -> dict:
    with open(_PORTALS_PATH, encoding="utf-8") as f:
        return next(p for p in json.load(f) if p["portal_name"] == name)


@pytest.fixture()
def db(monkeypatch):
    dbmod.engine = test_engine
    db_helpers.engine = test_engine
    api_router.engine = test_engine
    Base.metadata.create_all(bind=test_engine)
    with test_engine.begin() as conn:
        for t in ("govt_portals", "tenant_profiles", "tenants"):
            conn.execute(text(f"DELETE FROM {t}"))  # nosec B608
        for tid, state in _TENANTS.items():
            conn.execute(
                text("INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan, is_active) "
                     "VALUES (:id, :n, 'X', :w, 'Pro', 1)"),
                {"id": tid, "n": f"T{tid}", "w": f"+9190000000{tid:02d}"},
            )
            conn.execute(
                text("INSERT INTO tenant_profiles (tenant_id, mp_name, constituency, state, house) "
                     "VALUES (:id, 'MP', 'X', :s, 'Lok Sabha')"),
                {"id": tid, "s": state},
            )
    seed_govt_portals()
    yield test_engine


def _resolve(tid):
    portal, _state = api_router._resolve_govt_portal_for_tenant(tid)
    return portal


def _set_delhi(engine, **cols):
    sets = ", ".join(f"{k} = :{k}" for k in cols)
    with engine.begin() as conn:
        conn.execute(text(f"UPDATE govt_portals SET {sets} WHERE portal_name = :n"),  # nosec B608
                     {**cols, "n": DELHI})


# ─── Data-level: exactly what was configured, nothing invented ─────────────

def test_delhi_row_is_official_url_only_and_inactive():
    row = _seed_row(DELHI)
    assert row["state"] == "Delhi"
    assert row["base_url"] == "https://cmjansunwai.delhi.gov.in/"
    assert row["status_check_url"] is None
    assert row["department_taxonomy"] == {}
    assert row["field_schema"]["taxonomy_verified"] is False
    assert row["field_schema"]["selectors"] == {}
    assert row["field_schema"]["reference_selector"] is None
    # VERIFIED from the portal's own tracker (numeric, maxlength 14). Nothing else about the form is verified.
    assert row["field_schema"]["reference_regex"] == "^[0-9]{1,14}$"
    # The portal's real subject/description limits are UNKNOWN: they must not be invented.
    assert row["field_schema"]["subject_max_chars"] is None
    assert row["field_schema"]["description_max_chars"] is None
    assert row["field_schema"]["fields"] == ["subject", "description"]
    assert row["active"] is False
    assert row["verification_status"] != "confirmed"
    # Explicit no-automation adapter (never polled, never contacts the portal): not a status adapter.
    assert row["status_check_adapter"] == "delhi_staff_assisted"
    assert row["otp_bound"] is True
    assert row["status_check_mode"] == "login_required"


def test_delhi_uses_manual_adapter_and_makes_no_request(monkeypatch):
    import requests

    def _boom(*a, **k):
        raise AssertionError("Delhi check_status made an HTTP request")

    monkeypatch.setattr(requests, "get", _boom)
    monkeypatch.setattr(requests, "post", _boom)
    row = _seed_row(DELHI)
    adapter = get_adapter(row)
    from modules.govt_sync.adapters.delhi_cm_jan_sunwai import DelhiStaffAssistedAdapter
    assert type(adapter) is DelhiStaffAssistedAdapter and isinstance(adapter, ManualAssistedAdapter)
    assert adapter.supports_unattended_status_check is False      # structurally excluded from the poller
    result = adapter.check_status("20260000001")
    assert result.checked is False and result.status == "" and result.needs_verification is False


# ─── Tenant routing ────────────────────────────────────────────────────────

def test_delhi_tenant_falls_back_to_cpgrams_while_portal_inactive(db):
    assert _resolve(1)["portal_name"] == "CPGRAMS"
    assert _resolve(10)["portal_name"] == "CPGRAMS"


def test_delhi_tenant_resolves_to_delhi_only_when_eligible(db):
    _set_delhi(db, active=1)
    assert _resolve(1)["portal_name"] == DELHI
    assert _resolve(10)["portal_name"] == DELHI  # LOWER() match, like other states
    p = _resolve(1)
    assert p["department_taxonomy"] == {} and p["status_check_adapter"] == "delhi_staff_assisted"


@pytest.mark.parametrize("cols", [{"base_url": None}, {"is_primary": 0}, {"active": 0}])
def test_delhi_ineligible_variants_fall_back_to_cpgrams(db, cols):
    _set_delhi(db, active=1)
    _set_delhi(db, **cols)
    assert _resolve(1)["portal_name"] == "CPGRAMS"


def test_other_states_routing_unchanged_with_delhi_inactive_or_active(db):
    for delhi_active in (0, 1):
        _set_delhi(db, active=delhi_active)
        for tid, expected in _EXPECTED_UNCHANGED.items():
            assert _resolve(tid)["portal_name"] == expected, (tid, delhi_active)


def test_missing_or_invalid_configuration_fails_safe(db):
    with db.begin() as conn:
        conn.execute(text("DELETE FROM govt_portals WHERE portal_type = 'cpgrams'"))
    _set_delhi(db, active=0)
    portal, state = api_router._resolve_govt_portal_for_tenant(1)
    assert portal is None and state == "Delhi"   # fails closed, never another state's portal
    assert _resolve(8) is None
    assert _resolve(9) is None
    # tenant with no profile row at all
    assert api_router._resolve_govt_portal_for_tenant(999)[0] is None


def test_delhi_portal_is_never_reachable_by_non_delhi_tenants(db):
    _set_delhi(db, active=1)
    for tid in (2, 3, 4, 5, 6, 7, 8, 9):
        assert _resolve(tid)["portal_name"] != DELHI


# ─── Seed durability ───────────────────────────────────────────────────────

def test_reseed_does_not_overwrite_delhi_operational_fields(db):
    _set_delhi(db, active=1, verification_status="confirmed",
               source_note="ops note", live_session_supported=0)
    seed_govt_portals()
    with db.connect() as conn:
        r = conn.execute(
            text("SELECT active, verification_status, source_note, live_session_supported, "
                 "status_check_adapter, base_url FROM govt_portals WHERE portal_name = :n"),
            {"n": DELHI},
        ).mappings().first()
    assert bool(r["active"]) is True
    assert r["verification_status"] == "confirmed"
    assert r["source_note"] == "ops note"
    assert bool(r["live_session_supported"]) is False
    assert r["status_check_adapter"] == "delhi_staff_assisted"   # seeded value; operational fields are not overwritten by a reseed
    assert r["base_url"] == "https://cmjansunwai.delhi.gov.in/"


def test_first_seed_inserts_delhi_inactive_and_unverified(db):
    with db.connect() as conn:
        r = conn.execute(
            text("SELECT active, verification_status FROM govt_portals WHERE portal_name = :n"),
            {"n": DELHI},
        ).mappings().first()
    assert bool(r["active"]) is False
    assert r["verification_status"] == "verify"
    # field_schema/taxonomy_verified is pinned on the JSON itself above; SQLite
    # can't round-trip CAST(... AS JSONB), so it isn't asserted via this DB.


# ─── CURRENT BLOCKER: pins today's behaviour; not a fix ────────────────────

def test_blocker_worksheet_prep_refuses_empty_taxonomy_so_no_portal_link(db):
    """cases.govt_portal_id is set only by _prepare_govt_worksheet, which
    refuses an empty department_taxonomy. govt/submit then requires
    govt_portal_id, so a Delhi reference can't be recorded today."""
    _set_delhi(db, active=1)
    portal = _resolve(1)
    with pytest.raises(HTTPException) as exc:
        api_router._prepare_govt_worksheet(1, {"id": 1}, portal, "staff")
    assert exc.value.status_code == 400
    assert "department list" in exc.value.detail
