import os
import sys
import json
import re
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
TEST_DB_URL = "sqlite:///./test_partner_api.db"

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


import main
import admin_api
import api_router
import partner_api
import core.db_helpers as db_helpers
import modules.partners as partners_mod
import sansadx_backend.db as dbmod
from sansadx_backend.db import Base


test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False)
client = TestClient(main.app, raise_server_exceptions=False)

PHONE = "919812345678"
RAW_MESSAGE = "Sewage overflow outside my house, Ramesh Patil, Lane 4"


def _seed_database():
    dbmod.engine = test_engine
    dbmod.SessionLocal = TestSession
    db_helpers.engine = test_engine
    main.engine = test_engine
    api_router.engine = test_engine
    admin_api.engine = test_engine
    admin_api.SessionLocal = TestSession

    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    now = datetime.utcnow()
    with test_engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO tenants (id, name, constituency, whatsapp_number, subscription_plan,
                                     tenant_type, account_stage, seat_type, is_active, created_at)
                VALUES
                    (1, 'System Admin', 'India', '+910000000001', 'System', 'mp', 'elected', 'mp', 1, :now),
                    (2, 'Aspirant A', 'Belagavi South', '+910000000002', 'Pro', 'aspirant', 'aspirant', 'mla', 1, :now),
                    (3, 'Aspirant B', 'Pune Cantonment', '+910000000003', 'Pro', 'aspirant', 'aspirant', 'mla', 1, :now),
                    (4, 'Dormant', 'Nowhere', '+910000000004', 'Pro', 'aspirant', 'aspirant', 'mla', 0, :now)
                """
            ),
            {"now": now},
        )
        conn.execute(
            text(
                """
                INSERT INTO users (id, tenant_id, username, password_hash, role, constituency,
                                   house, display_name, is_active, must_change_password)
                VALUES
                    (1, 1, 'sysadmin', :admin_hash, 'sysadmin', 'India', 'Lok Sabha', 'System Admin', 1, 0),
                    (2, 2, 'asp_a', :owner_hash, 'owner', 'Belagavi', 'Vidhan Sabha', 'Aspirant A', 1, 0),
                    (4, 1, 'plainadmin', :admin_hash, 'admin', 'India', 'Lok Sabha', 'Plain Admin', 1, 0)
                """
            ),
            {"admin_hash": admin_api.hash_password("AdminPass1!"), "owner_hash": admin_api.hash_password("OwnerPass1!")},
        )

        def case(cid, tenant, status, days_ago, critical=0, deleted=0, category="Water", ward="Ward 5", resolved_after=None):
            created = now - timedelta(days=days_ago)
            resolved = created + timedelta(days=resolved_after) if resolved_after is not None else None
            conn.execute(
                text(
                    """
                    INSERT INTO cases (id, tenant_id, user_phone, raw_message, category, status, ward,
                                       is_critical, is_deleted, created_at, resolved_at)
                    VALUES (:id, :t, :ph, :msg, :cat, :st, :ward, :crit, :del, :cr, :rs)
                    """
                ),
                {"id": cid, "t": tenant, "ph": PHONE, "msg": RAW_MESSAGE, "cat": category, "st": status,
                 "ward": ward, "crit": critical, "del": deleted, "cr": created, "rs": resolved},
            )

        # Tenant 2: 4 live cases in window (2 resolved, 1 critical), 1 deleted, 1 outside 30d window
        case(1, 2, "resolved", 2, resolved_after=1)
        case(2, 2, "resolved", 5, resolved_after=3, category="Roads", ward="Ward 7")
        case(3, 2, "new", 3, critical=1)
        case(4, 2, "pending", 10)
        case(5, 2, "new", 4, deleted=1)
        case(6, 2, "new", 45)
        # Tenant 3 belongs to another client entirely
        case(7, 3, "new", 1)
        case(8, 3, "new", 2)


# ── helpers ──
def _admin_headers():
    resp = client.post("/api/admin/auth/login", json={"username": "sysadmin", "password": "AdminPass1!"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['token']}"}


def _create_partner(admin, name="Rajdhani Strategy", **kw):
    resp = client.post("/api/admin/partners", json={"name": name, **kw}, headers=admin)
    assert resp.status_code == 200, resp.text
    return resp.json()["partner"]["id"]


def _create_partner_user(admin, partner_id, email):
    resp = client.post(f"/api/admin/partners/{partner_id}/users", json={"email": email}, headers=admin)
    assert resp.status_code == 200, resp.text
    return resp.json()["temporary_password"]


def _partner_session(admin, partner_id, email):
    """Create a user, log in, complete the forced password change, return auth headers."""
    temp = _create_partner_user(admin, partner_id, email)
    login = client.post("/api/partner/auth/login", json={"email": email, "password": temp})
    assert login.status_code == 200, login.text
    assert login.json()["must_change_password"] is True
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    changed = client.post(
        "/api/partner/auth/change-password",
        json={"current_password": temp, "new_password": "NewSecret9"},
        headers=headers,
    )
    assert changed.status_code == 200, changed.text
    return {"Authorization": f"Bearer {changed.json()['token']}"}




_wa_counter = [0]


def _login_admin(username):
    resp = client.post("/api/admin/auth/login", json={"username": username, "password": "AdminPass1!"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['token']}"}


def _onboard(admin, username, name="New Client", channel="direct", partner_id=None, **extra):
    """Create a tenant through the real onboarding endpoint (POST /api/admin/mps)."""
    _wa_counter[0] += 1
    body = {
        "name": name, "username": username, "password": "TempPass1!", "tenant_type": "aspirant",
        "account_stage": "aspirant", "seat_type": "mla", "house": "Vidhan Sabha", "constituency": "Test Seat",
        "state": "Karnataka", "whatsapp_number": f"+9190000{_wa_counter[0]:05d}", "acquisition_channel": channel,
    }
    if partner_id is not None:
        body["partner_id"] = partner_id
    body.update(extra)
    return client.post("/api/admin/mps", json=body, headers=admin)


def _rows(sql, **params):
    with test_engine.begin() as conn:
        return [dict(r) for r in conn.execute(text(sql), params).mappings().all()]


def _reassign(admin, tenant_id, partner_id, reason="Introduced by this consultancy"):
    return client.post(f"/api/admin/partners/tenants/{tenant_id}/attribution/reassign",
                       json={"partner_id": partner_id, "reason": reason}, headers=admin)


def _attach(admin, partner_id, tenant_id):
    """Attribute one of the pre-seeded tenants (they own the seeded cases) to a partner; returns the seat id."""
    resp = _reassign(admin, tenant_id, partner_id)
    assert resp.status_code == 200, resp.text
    return resp.json()["seat_id"]


def _portfolio(headers):
    resp = client.get("/api/partner/clients?days=30", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


# ───────────────────────── auth / existing behaviour ─────────────────────────
def test_onboarding_flow_and_forced_password_change():
    _seed_database()
    admin = _admin_headers()
    pid = _create_partner(admin)
    temp = _create_partner_user(admin, pid, "Ops@Rajdhani.in")

    login = client.post("/api/partner/auth/login", json={"email": "ops@rajdhani.in", "password": temp})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['token']}"}

    assert client.get("/api/partner/clients", headers=headers).status_code == 403  # must change password first

    weak = client.post("/api/partner/auth/change-password", json={"current_password": temp, "new_password": "short"}, headers=headers)
    assert weak.status_code == 400
    wrong = client.post("/api/partner/auth/change-password", json={"current_password": "nope", "new_password": "NewSecret9"}, headers=headers)
    assert wrong.status_code == 401

    ok = client.post("/api/partner/auth/change-password", json={"current_password": temp, "new_password": "NewSecret9"}, headers=headers)
    assert ok.status_code == 200
    new_headers = {"Authorization": f"Bearer {ok.json()['token']}"}
    assert client.get("/api/partner/clients", headers=new_headers).status_code == 200
    assert client.get("/api/partner/clients", headers=headers).status_code in (401, 403)  # old token revoked


def test_login_failures_do_not_reveal_which_part_was_wrong():
    _seed_database()
    admin = _admin_headers()
    pid = _create_partner(admin)
    _create_partner_user(admin, pid, "ops@rajdhani.in")
    bad_pw = client.post("/api/partner/auth/login", json={"email": "ops@rajdhani.in", "password": "WrongPass1"})
    no_user = client.post("/api/partner/auth/login", json={"email": "ghost@rajdhani.in", "password": "WrongPass1"})
    assert bad_pw.status_code == no_user.status_code == 401
    assert bad_pw.json() == no_user.json()


def test_tokens_do_not_cross_between_mp_admin_and_partner_systems():
    _seed_database()
    admin = _admin_headers()
    pid = _create_partner(admin)
    partner_headers = _partner_session(admin, pid, "ops@rajdhani.in")
    mp_login = client.post("/api/auth/login", json={"username": "asp_a", "password": "OwnerPass1!"})
    assert mp_login.status_code == 200, mp_login.text
    mp_headers = {"Authorization": f"Bearer {mp_login.json()['token']}"}

    assert client.get("/api/partner/clients", headers=mp_headers).status_code == 401
    assert client.get("/api/partner/clients", headers=admin).status_code == 401
    assert client.get("/api/admin/partners", headers=partner_headers).status_code in (401, 403)
    assert client.get("/api/admin/partners/selectable", headers=partner_headers).status_code in (401, 403)
    assert client.post("/api/admin/partners/tenants/2/attribution/reassign", json={"partner_id": pid, "reason": "forged attempt"},
                       headers=partner_headers).status_code in (401, 403)
    assert client.get("/api/auth/me", headers=partner_headers).status_code == 401


def test_partner_config_validation():
    _seed_database()
    admin = _admin_headers()
    http_logo = client.post("/api/admin/partners", json={"name": "Bad Logo", "brand_logo_url": "http://x.com/l.png"}, headers=admin)
    js_logo = client.post("/api/admin/partners", json={"name": "Bad Logo", "brand_logo_url": "javascript:alert(1)"}, headers=admin)
    assert http_logo.status_code == 400 and js_logo.status_code == 400
    pid = _create_partner(admin, brand_color="red; background:url(x)")
    listing = client.get("/api/admin/partners", headers=admin).json()["partners"]
    assert [p["brand_color"] for p in listing if p["id"] == pid] == [partners_mod.DEFAULT_BRAND_COLOR]
    a, b = _create_partner(admin, "Same Name"), _create_partner(admin, "Same Name")
    slugs = {p["slug"] for p in client.get("/api/admin/partners", headers=admin).json()["partners"] if p["id"] in (a, b)}
    assert len(slugs) == 2


def test_admin_can_list_users_reset_password_and_deactivate():
    _seed_database()
    admin = _admin_headers()
    pid = _create_partner(admin)
    headers = _partner_session(admin, pid, "ops@rajdhani.in")
    users = client.get(f"/api/admin/partners/{pid}/users", headers=admin).json()["users"]
    assert [u["email"] for u in users] == ["ops@rajdhani.in"] and "password_hash" not in users[0]
    uid = users[0]["id"]
    reset = client.post(f"/api/admin/partners/{pid}/users/{uid}/reset-password", headers=admin)
    assert reset.status_code == 200
    temp = reset.json()["temporary_password"]
    assert client.get("/api/partner/clients", headers=headers).status_code == 401
    relogin = client.post("/api/partner/auth/login", json={"email": "ops@rajdhani.in", "password": temp})
    assert relogin.status_code == 200 and relogin.json()["must_change_password"] is True
    assert client.post(f"/api/admin/partners/{pid}/users/{uid}/active", json={"is_active": False}, headers=admin).status_code == 200
    assert client.post("/api/partner/auth/login", json={"email": "ops@rajdhani.in", "password": temp}).status_code == 401


def test_admin_user_actions_cannot_cross_partners():
    _seed_database()
    admin = _admin_headers()
    pa, pb = _create_partner(admin, "Alpha Advisory"), _create_partner(admin, "Bravo Campaigns")
    _create_partner_user(admin, pa, "a@alpha.in")
    uid = client.get(f"/api/admin/partners/{pa}/users", headers=admin).json()["users"][0]["id"]
    assert client.post(f"/api/admin/partners/{pb}/users/{uid}/reset-password", headers=admin).status_code == 404
    assert client.post(f"/api/admin/partners/{pb}/users/{uid}/active", json={"is_active": False}, headers=admin).status_code == 404


# ───────────────────────── onboarding attribution ─────────────────────────
def test_direct_onboarding_has_no_partner_association():
    _seed_database()
    admin = _admin_headers()
    pid = _create_partner(admin)
    headers = _partner_session(admin, pid, "ops@rajdhani.in")

    resp = _onboard(admin, "direct_client")  # channel defaults to direct
    assert resp.status_code == 200, resp.text
    tid = resp.json()["tenant_id"]
    assert resp.json()["acquisition"] == {"channel": "direct", "partner_id": None, "seat_id": None}

    row = _rows("SELECT * FROM tenant_attributions WHERE tenant_id = :t", t=tid)[0]
    assert (row["channel"], row["partner_id"], row["attributed_by"], row["attributed_by_user_id"]) == ("direct", None, "sysadmin", 1)
    assert _rows("SELECT * FROM partner_seats WHERE tenant_id = :t", t=tid) == []
    assert _portfolio(headers)["clients"] == []


def test_partner_onboarding_creates_active_association_and_persists_attribution():
    _seed_database()
    admin = _admin_headers()
    pid = _create_partner(admin)
    headers = _partner_session(admin, pid, "ops@rajdhani.in")

    resp = _onboard(admin, "partner_client", name="Asha Patil", channel="partner", partner_id=pid)
    assert resp.status_code == 200, resp.text
    tid = resp.json()["tenant_id"]
    assert resp.json()["acquisition"]["channel"] == "partner" and resp.json()["acquisition"]["partner_id"] == pid

    attribution = _rows("SELECT * FROM tenant_attributions WHERE tenant_id = :t", t=tid)
    assert len(attribution) == 1
    a = attribution[0]
    assert (a["channel"], a["partner_id"], a["attributed_by"], a["attributed_by_user_id"]) == ("partner", pid, "sysadmin", 1)
    assert a["attributed_at"] is not None

    seats = _rows("SELECT * FROM partner_seats WHERE tenant_id = :t", t=tid)
    assert len(seats) == 1 and seats[0]["status"] == "active" and seats[0]["partner_id"] == pid  # no approval step
    assert seats[0]["client_label"] == "Asha Patil" and seats[0]["activated_at"] is not None

    events = _rows("SELECT * FROM tenant_attribution_events WHERE tenant_id = :t", t=tid)
    assert [(e["event"], e["to_channel"], e["to_partner_id"], e["changed_by"]) for e in events] == [("onboarded", "partner", pid, "sysadmin")]

    clients = _portfolio(headers)["clients"]   # visible immediately, no seat request/approval
    assert [(c["client_label"], c["status"]) for c in clients] == [("Asha Patil", "active")]
    assert client.get(f"/api/partner/clients/{clients[0]['id']}/summary", headers=headers).status_code == 200


def test_client_cannot_forge_attribution_metadata():
    _seed_database()
    admin = _admin_headers()
    pid = _create_partner(admin)
    resp = _onboard(admin, "forger", channel="partner", partner_id=pid, attributed_by="somebody_else",
                    attributed_at="2001-01-01T00:00:00", status="paused", seat_status="paused", attributed_by_user_id=999)
    assert resp.status_code == 200, resp.text
    tid = resp.json()["tenant_id"]
    a = _rows("SELECT * FROM tenant_attributions WHERE tenant_id = :t", t=tid)[0]
    assert a["attributed_by"] == "sysadmin" and a["attributed_by_user_id"] == 1 and not str(a["attributed_at"]).startswith("2001")
    assert _rows("SELECT status FROM partner_seats WHERE tenant_id = :t", t=tid)[0]["status"] == "active"
    # unauthenticated / non-admin callers cannot onboard at all
    assert client.post("/api/admin/mps", json={"name": "x", "username": "x", "password": "TempPass1!", "acquisition_channel": "partner", "partner_id": pid}).status_code in (401, 403)
    owner = client.post("/api/auth/login", json={"username": "asp_a", "password": "OwnerPass1!"}).json()["token"]
    assert _onboard({"Authorization": f"Bearer {owner}"}, "nope", channel="partner", partner_id=pid).status_code in (401, 403)


def test_tenant_visible_only_to_attributed_partner_and_aggregates_stay_isolated():
    _seed_database()
    admin = _admin_headers()
    pa, pb = _create_partner(admin, "Alpha Advisory"), _create_partner(admin, "Bravo Campaigns")
    ha = _partner_session(admin, pa, "a@alpha.in")
    hb = _partner_session(admin, pb, "b@bravo.in")
    seat_a = _attach(admin, pa, 2)   # tenant 2: 4 live cases in window
    seat_b = _attach(admin, pb, 3)   # tenant 3: 2 cases
    direct = _onboard(admin, "direct_only").json()["tenant_id"]

    pa_view, pb_view = _portfolio(ha), _portfolio(hb)
    assert pa_view["portfolio"]["total"] == 4 and pb_view["portfolio"]["total"] == 2
    assert [c["id"] for c in pa_view["clients"]] == [seat_a] and [c["id"] for c in pb_view["clients"]] == [seat_b]
    for path in ("summary", "report"):
        assert client.get(f"/api/partner/clients/{seat_a}/{path}", headers=hb).status_code == 404
        assert client.get(f"/api/partner/clients/{seat_b}/{path}", headers=ha).status_code == 404
    assert direct not in {r["tenant_id"] for r in _rows("SELECT tenant_id FROM partner_seats WHERE tenant_id IS NOT NULL")}
    assert PHONE not in str(pa_view) and "Ramesh" not in str(pa_view)


def test_summary_numbers_scope_to_tenant_and_exclude_deleted():
    _seed_database()
    admin = _admin_headers()
    pid = _create_partner(admin)
    headers = _partner_session(admin, pid, "ops@rajdhani.in")
    seat_id = _attach(admin, pid, 2)

    resp = client.get(f"/api/partner/clients/{seat_id}/summary?days=30", headers=headers)
    assert resp.status_code == 200, resp.text
    s = resp.json()["summary"]
    assert (s["total"], s["resolved"], s["open"], s["critical"], s["resolution_rate"], s["avg_resolution_days"]) == (4, 2, 2, 1, 0.5, 2.0)
    assert {c["name"] for c in s["top_categories"]} == {"Water", "Roads"}
    assert s["bucket_days"] == 7 and len(s["trend"]) == 5 and sum(b["received"] for b in s["trend"]) == 4
    assert PHONE not in resp.text and "Ramesh" not in resp.text


def test_inactive_partner_cannot_receive_new_tenants_and_is_not_silently_converted():
    _seed_database()
    admin = _admin_headers()
    pid = _create_partner(admin)
    assert client.patch(f"/api/admin/partners/{pid}", json={"is_active": False}, headers=admin).status_code == 200
    resp = _onboard(admin, "inactive_try", channel="partner", partner_id=pid)
    assert resp.status_code == 400 and "inactive" in resp.json()["detail"].lower()
    # nothing was created — in particular no silent fallback to a direct tenant
    assert _rows("SELECT id FROM users WHERE username = 'inactive_try'") == []
    assert _rows("SELECT id FROM tenant_attributions") == []
    selectable = client.get("/api/admin/partners/selectable", headers=admin).json()["partners"]
    assert pid not in {p["id"] for p in selectable}


def test_partner_channel_requires_a_valid_partner():
    _seed_database()
    admin = _admin_headers()
    missing = _onboard(admin, "no_partner", channel="partner")
    invalid = _onboard(admin, "bad_partner", channel="partner", partner_id=9999)
    direct_with_partner = _onboard(admin, "confused", channel="direct", partner_id=_create_partner(admin))
    bad_channel = _onboard(admin, "weird", channel="reseller")
    assert missing.status_code == 400 and "partner" in missing.json()["detail"].lower()
    assert invalid.status_code == 400 and "does not exist" in invalid.json()["detail"]
    assert direct_with_partner.status_code == 400
    assert bad_channel.status_code == 400
    assert _rows("SELECT id FROM users WHERE username IN ('no_partner','bad_partner','confused','weird')") == []
    assert _rows("SELECT id FROM tenant_attributions") == [] and _rows("SELECT id FROM partner_seats") == []


def test_selectable_partners_lists_only_active_ones():
    _seed_database()
    admin = _admin_headers()
    a, b = _create_partner(admin, "Alpha Advisory"), _create_partner(admin, "Bravo Campaigns")
    client.patch(f"/api/admin/partners/{b}", json={"is_active": False}, headers=admin)
    selectable = client.get("/api/admin/partners/selectable", headers=admin).json()["partners"]
    assert selectable == [{"id": a, "name": "Alpha Advisory"}]


# ───────────────────────── no seat limits ─────────────────────────
def test_no_seat_cap_anywhere():
    _seed_database()
    admin = _admin_headers()
    created = client.post("/api/admin/partners", json={"name": "Big Consultancy", "seat_cap": 1}, headers=admin)  # stale client field
    assert created.status_code == 200
    partner = created.json()["partner"]
    assert "seat_cap" not in partner and "seats_used" not in partner
    pid = partner["id"]
    assert "seat_cap" not in {c["name"] for c in _rows("SELECT name FROM pragma_table_info('partners')")}

    for i in range(8):
        assert _onboard(admin, f"bulk_{i}", channel="partner", partner_id=pid).status_code == 200
    headers = _partner_session(admin, pid, "ops@big.in")
    listing = _portfolio(headers)
    assert len(listing["clients"]) == 8 and listing["active_clients"] == 8
    assert "seat_cap" not in listing and "seat_cap" not in listing["clients"][0]
    assert "seat_cap" not in client.get("/api/partner/me", headers=headers).json()["partner"]
    assert client.patch(f"/api/admin/partners/{pid}", json={"seat_cap": 3}, headers=admin).status_code == 200
    assert len(_portfolio(headers)["clients"]) == 8
    # the old partner-initiated request workflow is gone
    assert client.post("/api/partner/seat-requests", json={"client_label": "X"}, headers=headers).status_code in (404, 405)


# ───────────────────────── reassignment ─────────────────────────
def test_reassignment_requires_super_admin_and_a_reason():
    _seed_database()
    admin = _admin_headers()
    plain = _login_admin("plainadmin")
    pid = _create_partner(admin)
    tid = _onboard(admin, "t1").json()["tenant_id"]

    assert _reassign(plain, tid, pid).status_code == 403                 # regular admin role: no
    assert client.post(f"/api/admin/partners/tenants/{tid}/attribution/reassign", json={"partner_id": pid, "reason": "x" * 10}).status_code in (401, 403)
    for reason in ("", "   ", "ok"):
        resp = _reassign(admin, tid, pid, reason=reason)
        assert resp.status_code == 400 and "reason" in resp.json()["detail"].lower()
    assert _rows("SELECT * FROM partner_seats") == []                    # nothing changed
    assert _reassign(admin, 99999, pid).status_code == 404
    assert _reassign(admin, tid, pid).status_code == 200


def test_reassignment_moves_access_atomically_and_is_audited():
    _seed_database()
    admin = _admin_headers()
    pa, pb = _create_partner(admin, "Alpha Advisory"), _create_partner(admin, "Bravo Campaigns")
    ha = _partner_session(admin, pa, "a@alpha.in")
    hb = _partner_session(admin, pb, "b@bravo.in")
    tid = _onboard(admin, "moving", name="Moving Client", channel="partner", partner_id=pa).json()["tenant_id"]
    old_seat = _portfolio(ha)["clients"][0]["id"]

    resp = _reassign(admin, tid, pb, reason="Mis-attributed at onboarding")
    assert resp.status_code == 200, resp.text
    assert (resp.json()["from_partner_id"], resp.json()["to_partner_id"]) == (pa, pb)

    assert _portfolio(ha)["clients"] == []                                           # previous partner lost access immediately
    assert client.get(f"/api/partner/clients/{old_seat}/summary", headers=ha).status_code == 404
    assert client.get(f"/api/partner/clients/{old_seat}/summary", headers=hb).status_code == 404
    new_clients = _portfolio(hb)["clients"]
    assert [c["client_label"] for c in new_clients] == ["Moving Client"]             # new partner has access
    assert client.get(f"/api/partner/clients/{new_clients[0]['id']}/summary", headers=hb).status_code == 200

    holders = _rows("SELECT partner_id, status FROM partner_seats WHERE tenant_id = :t", t=tid)
    assert holders == [{"partner_id": pb, "status": "active"}]                       # exactly one association
    revoked = _rows("SELECT status, tenant_id FROM partner_seats WHERE id = :i", i=old_seat)[0]
    assert revoked == {"status": "revoked", "tenant_id": None}                       # history kept, detached
    attribution = _rows("SELECT channel, partner_id FROM tenant_attributions WHERE tenant_id = :t", t=tid)
    assert attribution == [{"channel": "partner", "partner_id": pb}]

    events = _rows("SELECT * FROM tenant_attribution_events WHERE tenant_id = :t ORDER BY id", t=tid)
    assert [e["event"] for e in events] == ["onboarded", "reassigned"]
    e = events[-1]
    assert (e["from_partner_id"], e["to_partner_id"], e["reason"], e["changed_by"]) == (pa, pb, "Mis-attributed at onboarding", "sysadmin")
    assert e["created_at"] is not None
    audit = _rows("SELECT change_summary FROM admin_audit_log WHERE action = 'reassign_tenant_attribution'")
    assert len(audit) == 1 and f"from=partner:{pa}" in audit[0]["change_summary"] and f"to=partner:{pb}" in audit[0]["change_summary"]

    detail = client.get(f"/api/admin/partners/tenants/{tid}/attribution", headers=admin).json()
    assert detail["attribution"]["partner_id"] == pb and [h["event"] for h in detail["history"]] == ["reassigned", "onboarded"]
    assert _reassign(admin, tid, pb).status_code == 409                              # no-op move rejected


def test_reassignment_to_inactive_or_unknown_partner_changes_nothing():
    _seed_database()
    admin = _admin_headers()
    pa, pb = _create_partner(admin, "Alpha Advisory"), _create_partner(admin, "Bravo Campaigns")
    ha = _partner_session(admin, pa, "a@alpha.in")
    tid = _onboard(admin, "stays", channel="partner", partner_id=pa).json()["tenant_id"]
    client.patch(f"/api/admin/partners/{pb}", json={"is_active": False}, headers=admin)

    assert _reassign(admin, tid, pb).status_code == 400
    assert _reassign(admin, tid, 9999).status_code == 400
    assert len(_portfolio(ha)["clients"]) == 1                                       # old partner keeps access
    assert [e["event"] for e in _rows("SELECT event FROM tenant_attribution_events WHERE tenant_id = :t", t=tid)] == ["onboarded"]


def test_reassigning_to_direct_and_back_never_duplicates_associations():
    _seed_database()
    admin = _admin_headers()
    pa, pb = _create_partner(admin, "Alpha Advisory"), _create_partner(admin, "Bravo Campaigns")
    ha = _partner_session(admin, pa, "a@alpha.in")
    hb = _partner_session(admin, pb, "b@bravo.in")
    tid = _onboard(admin, "roundtrip", channel="partner", partner_id=pa).json()["tenant_id"]

    assert _reassign(admin, tid, None, reason="Customer left the consultancy").status_code == 200
    assert _portfolio(ha)["clients"] == []
    assert _rows("SELECT channel, partner_id FROM tenant_attributions WHERE tenant_id = :t", t=tid) == [{"channel": "direct", "partner_id": None}]
    assert _rows("SELECT id FROM partner_seats WHERE tenant_id = :t", t=tid) == []

    assert _reassign(admin, tid, pb, reason="Now managed by Bravo").status_code == 200
    assert len(_portfolio(hb)["clients"]) == 1 and _portfolio(ha)["clients"] == []
    assert len(_rows("SELECT id FROM partner_seats WHERE tenant_id = :t", t=tid)) == 1
    assert len(_rows("SELECT id FROM partner_seats WHERE status = 'revoked'")) == 1   # Alpha's old seat kept as history


def test_concurrent_reassignments_leave_exactly_one_association():
    from concurrent.futures import ThreadPoolExecutor
    _seed_database()
    admin = _admin_headers()
    partners = [_create_partner(admin, f"Partner {i}") for i in range(3)]
    tid = _onboard(admin, "contested").json()["tenant_id"]

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda p: _reassign(admin, tid, p, reason="Concurrent claim").status_code, partners * 2))
    assert 200 in results                      # at least one claim wins (others: 409 conflict / lock contention)
    seats = _rows("SELECT partner_id FROM partner_seats WHERE tenant_id = :t", t=tid)
    attribution = _rows("SELECT partner_id FROM tenant_attributions WHERE tenant_id = :t", t=tid)
    assert len(seats) == 1 and len(attribution) == 1 and seats[0]["partner_id"] == attribution[0]["partner_id"]


def test_database_rejects_duplicate_associations():
    from sqlalchemy.exc import IntegrityError
    _seed_database()
    admin = _admin_headers()
    pa, pb = _create_partner(admin, "Alpha Advisory"), _create_partner(admin, "Bravo Campaigns")
    tid = _onboard(admin, "unique", channel="partner", partner_id=pa).json()["tenant_id"]
    for model_kwargs, model in (
        ({"partner_id": pb, "tenant_id": tid, "client_label": "dup", "status": "active"}, partners_mod.PartnerSeat),
        ({"tenant_id": tid, "channel": "partner", "partner_id": pb}, partners_mod.TenantAttribution),
        ({"tenant_id": 3, "channel": "partner", "partner_id": None}, partners_mod.TenantAttribution),   # partner channel needs a partner
        ({"tenant_id": 3, "channel": "direct", "partner_id": pa}, partners_mod.TenantAttribution),      # direct cannot have one
    ):
        db = TestSession()
        db.add(model(**model_kwargs))
        try:
            db.commit()
            raise AssertionError(f"{model.__name__} accepted {model_kwargs}")
        except IntegrityError:
            db.rollback()
        finally:
            db.close()


# ───────────────────────── transactional integrity ─────────────────────────
def test_onboarding_failure_after_association_rolls_everything_back(monkeypatch):
    _seed_database()
    admin = _admin_headers()
    pid = _create_partner(admin)

    def boom(*a, **k):
        raise RuntimeError("simulated failure while recording history")
    monkeypatch.setattr(partners_mod, "TenantAttributionEvent", boom)
    resp = _onboard(admin, "rollback_a", channel="partner", partner_id=pid)
    assert resp.status_code == 500
    assert _rows("SELECT id FROM users WHERE username = 'rollback_a'") == []
    assert _rows("SELECT id FROM tenants WHERE name = 'New Client'") == []
    assert _rows("SELECT id FROM partner_seats") == [] and _rows("SELECT id FROM tenant_attributions") == []


def test_association_failure_rolls_back_the_tenant(monkeypatch):
    _seed_database()
    admin = _admin_headers()
    pid = _create_partner(admin)

    def boom(*a, **k):
        raise RuntimeError("simulated seat creation failure")
    monkeypatch.setattr(partners_mod, "_new_seat", boom)
    assert _onboard(admin, "rollback_b", channel="partner", partner_id=pid).status_code == 500
    assert _rows("SELECT id FROM users WHERE username = 'rollback_b'") == []
    assert _rows("SELECT id FROM tenants WHERE name = 'New Client'") == []
    assert _rows("SELECT id FROM tenant_attributions") == []
    monkeypatch.undo()
    assert _onboard(admin, "rollback_b", channel="partner", partner_id=pid).status_code == 200   # retry succeeds, no leftovers


def test_failed_username_check_creates_no_attribution():
    _seed_database()
    admin = _admin_headers()
    pid = _create_partner(admin)
    assert _onboard(admin, "dupe_user", channel="partner", partner_id=pid).status_code == 200
    again = _onboard(admin, "dupe_user", channel="partner", partner_id=pid)
    assert again.status_code == 400
    assert len(_rows("SELECT id FROM partner_seats")) == 1 and len(_rows("SELECT id FROM tenant_attributions")) == 1


# ───────────────────────── access control: pause / deactivate ─────────────────────────
def test_pausing_an_association_revokes_access_without_changing_attribution():
    _seed_database()
    admin = _admin_headers()
    pid = _create_partner(admin)
    headers = _partner_session(admin, pid, "ops@rajdhani.in")
    seat_id = _attach(admin, pid, 2)
    tid = 2

    assert client.post(f"/api/admin/partners/{pid}/seats/{seat_id}/status", json={"status": "paused"}, headers=admin).status_code == 200
    assert client.get(f"/api/partner/clients/{seat_id}/summary", headers=headers).status_code == 409
    assert client.get(f"/api/partner/clients/{seat_id}/report", headers=headers).status_code == 409
    paused = _portfolio(headers)
    assert paused["clients"][0]["status"] == "paused" and paused["clients"][0]["summary"] is None and paused["portfolio"]["total"] == 0
    attribution = client.get(f"/api/admin/partners/tenants/{tid}/attribution", headers=admin).json()["attribution"]
    assert (attribution["channel"], attribution["partner_id"], attribution["access_status"]) == ("partner", pid, "paused")

    assert client.post(f"/api/admin/partners/{pid}/seats/{seat_id}/status", json={"status": "active"}, headers=admin).status_code == 200
    assert client.get(f"/api/partner/clients/{seat_id}/summary", headers=headers).status_code == 200


def test_deactivated_partner_loses_access_immediately_and_reactivation_restores_it():
    _seed_database()
    admin = _admin_headers()
    pid = _create_partner(admin)
    headers = _partner_session(admin, pid, "ops@rajdhani.in")
    seat_id = _attach(admin, pid, 2)
    assert client.get(f"/api/partner/clients/{seat_id}/summary", headers=headers).status_code == 200

    assert client.patch(f"/api/admin/partners/{pid}", json={"is_active": False}, headers=admin).status_code == 200
    for path in ("/api/partner/me", "/api/partner/clients", f"/api/partner/clients/{seat_id}/summary", f"/api/partner/clients/{seat_id}/report"):
        assert client.get(path, headers=headers).status_code == 401
    assert client.post("/api/partner/auth/login", json={"email": "ops@rajdhani.in", "password": "NewSecret9"}).status_code == 401
    # attribution is untouched by deactivation
    assert _rows("SELECT partner_id FROM tenant_attributions WHERE tenant_id = 2") == [{"partner_id": pid}]
    client.patch(f"/api/admin/partners/{pid}", json={"is_active": True}, headers=admin)
    assert client.get(f"/api/partner/clients/{seat_id}/summary", headers=headers).status_code == 200


# ───────────────────────── legacy requests / migration ─────────────────────────
def _legacy_seat(partner_id, label, status="requested", tenant_id=None):
    with test_engine.begin() as conn:
        conn.execute(text("INSERT INTO partner_seats (partner_id, tenant_id, client_label, seat_type, status, created_at) "
                          "VALUES (:p, :t, :l, 'mla', :s, :now)"),
                     {"p": partner_id, "t": tenant_id, "l": label, "s": status, "now": datetime.utcnow()})
        return conn.execute(text("SELECT max(id) FROM partner_seats")).scalar()


def test_legacy_requests_are_kept_hidden_from_partner_and_linked_through_the_same_rules():
    _seed_database()
    admin = _admin_headers()
    pa, pb = _create_partner(admin, "Alpha Advisory"), _create_partner(admin, "Bravo Campaigns")
    ha = _partner_session(admin, pa, "a@alpha.in")
    legacy = _legacy_seat(pa, "Old request", "requested")
    rejected = _legacy_seat(pa, "Old rejected", "rejected")

    assert _portfolio(ha)["clients"] == []                                           # not part of the portfolio
    pending = client.get("/api/admin/partners/requests/pending", headers=admin).json()["requests"]
    assert [r["client_label"] for r in pending] == ["Old request"]
    p = [x for x in client.get("/api/admin/partners", headers=admin).json()["partners"] if x["id"] == pa][0]
    assert p["legacy_requests"] == 1 and p["clients_active"] == 0

    # tenant 3 already belongs to Bravo -> legacy request for Alpha must not create a second association
    _attach(admin, pb, 3)
    dup = client.post(f"/api/admin/partners/{pa}/seats/{legacy}/activate", json={"tenant_id": 3}, headers=admin)
    assert dup.status_code == 409
    assert len(_rows("SELECT id FROM partner_seats WHERE tenant_id = 3")) == 1

    ok = client.post(f"/api/admin/partners/{pa}/seats/{legacy}/activate", json={"tenant_id": 2}, headers=admin)
    assert ok.status_code == 200, ok.text
    assert _rows("SELECT channel, partner_id FROM tenant_attributions WHERE tenant_id = 2") == [{"channel": "partner", "partner_id": pa}]
    assert [e["event"] for e in _rows("SELECT event FROM tenant_attribution_events WHERE tenant_id = 2")] == ["legacy_request_activated"]
    assert len(_portfolio(ha)["clients"]) == 1
    assert client.post(f"/api/admin/partners/{pa}/seats/{legacy}/activate", json={"tenant_id": 2}, headers=admin).status_code == 409   # not requested any more
    assert client.post(f"/api/admin/partners/{pa}/seats/{rejected}/activate", json={"tenant_id": 2}, headers=admin).status_code == 409
    assert client.post(f"/api/admin/partners/{pa}/seats/{rejected}/reject", headers=admin).status_code == 409


def test_startup_migration_backfills_attribution_for_existing_seats_idempotently():
    _seed_database()
    admin = _admin_headers()
    pid = _create_partner(admin)
    headers = _partner_session(admin, pid, "ops@rajdhani.in")
    active = _legacy_seat(pid, "Pre-existing active", "active", tenant_id=2)
    paused = _legacy_seat(pid, "Pre-existing paused", "paused", tenant_id=3)
    pending = _legacy_seat(pid, "Pre-existing request", "requested")
    assert _rows("SELECT id FROM tenant_attributions") == []

    first = partners_mod.ensure_partner_schema(test_engine)
    second = partners_mod.ensure_partner_schema(test_engine)
    assert first["backfilled"] == 2 and second["backfilled"] == 0
    rows = {r["tenant_id"]: r for r in _rows("SELECT * FROM tenant_attributions")}
    assert set(rows) == {2, 3} and all(r["channel"] == "partner" and r["partner_id"] == pid and r["attributed_by"] == "migration" for r in rows.values())
    assert _rows("SELECT status FROM partner_seats WHERE id = :i", i=pending)[0]["status"] == "requested"   # untouched
    assert {c["client_label"]: c["status"] for c in _portfolio(headers)["clients"]} == {
        "Pre-existing active": "active", "Pre-existing paused": "paused"}
    # paused association does not grant access; the active one does
    assert client.get(f"/api/partner/clients/{active}/summary", headers=headers).status_code == 200
    assert client.get(f"/api/partner/clients/{paused}/summary", headers=headers).status_code == 409


# ───────────────────────── staff-only visibility, deletion, billing ─────────────────────────
def test_acquisition_info_is_staff_only():
    _seed_database()
    admin = _admin_headers()
    pid = _create_partner(admin, "Rajdhani Strategy")
    tid = _onboard(admin, "visible_to_staff", channel="partner", partner_id=pid).json()["tenant_id"]

    detail = client.get(f"/api/admin/mps/{tid}/detail", headers=admin).json()
    assert detail["acquisition"]["channel"] == "partner" and detail["acquisition"]["partner_name"] == "Rajdhani Strategy"
    assert detail["acquisition"]["attributed_by"] == "sysadmin" and detail["acquisition"]["attributed_at"]
    assert detail["acquisition_history"][0]["event"] == "onboarded"
    direct = _onboard(admin, "direct_one").json()["tenant_id"]
    assert client.get(f"/api/admin/mps/{direct}/detail", headers=admin).json()["acquisition"]["channel"] == "direct"
    legacy = client.get("/api/admin/mps/2/detail", headers=admin).json()["acquisition"]
    assert legacy["recorded"] is False and legacy["channel"] == "direct"             # pre-attribution tenants read as direct

    owner = client.post("/api/auth/login", json={"username": "asp_a", "password": "OwnerPass1!"})
    owner_headers = {"Authorization": f"Bearer {owner.json()['token']}"}
    assert client.get(f"/api/admin/mps/{tid}/detail", headers=owner_headers).status_code in (401, 403)
    for path in ("/api/auth/me",):
        text_body = client.get(path, headers=owner_headers).text.lower()
        assert "partner" not in text_body and "acquisition" not in text_body
    assert "partner" not in owner.text.lower() and "acquisition" not in owner.text.lower()


def test_deleting_a_tenant_revokes_its_association_and_keeps_history():
    _seed_database()
    admin = _admin_headers()
    pid = _create_partner(admin)
    headers = _partner_session(admin, pid, "ops@rajdhani.in")
    tid = _onboard(admin, "to_delete", channel="partner", partner_id=pid).json()["tenant_id"]
    assert len(_portfolio(headers)["clients"]) == 1

    resp = client.delete(f"/api/admin/mps/{tid}", headers=admin)
    assert resp.status_code == 200, resp.text
    assert _portfolio(headers)["clients"] == []
    assert _rows("SELECT id FROM tenant_attributions WHERE tenant_id = :t", t=tid) == []
    assert [e["event"] for e in _rows("SELECT event FROM tenant_attribution_events WHERE tenant_id = :t ORDER BY id", t=tid)] == ["onboarded", "tenant_deleted"]
    assert _rows("SELECT status, tenant_id FROM partner_seats") == [{"status": "revoked", "tenant_id": None}]


def test_billing_counts_only_active_attributed_clients():
    _seed_database()
    admin = _admin_headers()
    pid = _create_partner(admin, wholesale_price_inr=15000)
    for i in range(3):
        _onboard(admin, f"billed_{i}", channel="partner", partner_id=pid)
    seats = [r["id"] for r in _rows("SELECT id FROM partner_seats ORDER BY id")]
    _legacy_seat(pid, "legacy pending", "requested")
    client.post(f"/api/admin/partners/{pid}/seats/{seats[0]}/status", json={"status": "paused"}, headers=admin)

    p = client.get("/api/admin/partners", headers=admin).json()["partners"][0]
    assert (p["clients_active"], p["clients_paused"], p["legacy_requests"]) == (2, 1, 1)
    assert (p["billable_clients"], p["wholesale_price_inr"], p["monthly_wholesale_inr"]) == (2, 15000, 30000)
    assert client.patch(f"/api/admin/partners/{pid}", json={"wholesale_price_inr": 20000}, headers=admin).json()["partner"]["monthly_wholesale_inr"] == 40000


def test_available_tenants_excludes_partner_attributed_inactive_and_admin_accounts():
    _seed_database()
    admin = _admin_headers()
    with test_engine.begin() as conn:
        conn.execute(text("INSERT INTO users (id, tenant_id, username, password_hash, role, constituency, house, display_name, is_active, must_change_password) "
                          "VALUES (3, 3, 'asp_b', 'x', 'owner', 'Pune', 'Vidhan Sabha', 'Aspirant B', 1, 0)"))
    pid = _create_partner(admin)
    before = {t["tenant_id"] for t in client.get("/api/admin/partners/available-tenants", headers=admin).json()["tenants"]}
    assert before == {2, 3}
    _attach(admin, pid, 2)
    after = {t["tenant_id"] for t in client.get("/api/admin/partners/available-tenants", headers=admin).json()["tenants"]}
    assert after == {3}


def test_report_is_branded_escaped_and_free_of_citizen_data():
    _seed_database()
    admin = _admin_headers()
    pid = _create_partner(admin, brand_name="Rajdhani <b>Strategy</b>", brand_color="#B8860B",
                          brand_logo_url="https://cdn.example.com/logo.png", show_powered_by=False)
    headers = _partner_session(admin, pid, "ops@rajdhani.in")
    seat_id = _attach(admin, pid, 2)
    with test_engine.begin() as conn:
        conn.execute(text("UPDATE partner_seats SET client_label = '<script>alert(1)</script>' WHERE id = :i"), {"i": seat_id})

    resp = client.get(f"/api/partner/clients/{seat_id}/report", headers=headers)
    assert resp.status_code == 200
    body = resp.text
    assert "<script>alert(1)</script>" not in body and "&lt;script&gt;" in body
    assert "Rajdhani &lt;b&gt;Strategy&lt;/b&gt;" in body
    assert "#B8860B" in body and "https://cdn.example.com/logo.png" in body
    assert "Compass Needle" not in body
    assert PHONE not in body and "Ramesh" not in body and "Sewage" not in body


# ───────────────────────── pre-merge audit additions ─────────────────────────
def test_retried_onboarding_never_creates_a_second_tenant_seat_or_attribution():
    _seed_database()
    admin = _admin_headers()
    pid = _create_partner(admin)
    first = _onboard(admin, "retry_me", channel="partner", partner_id=pid, whatsapp_number="+919000099999")
    assert first.status_code == 200
    for _ in range(2):                                                      # client retries the identical request
        again = _onboard(admin, "retry_me", channel="partner", partner_id=pid, whatsapp_number="+919000099999")
        assert again.status_code == 400
    assert len(_rows("SELECT id FROM tenants WHERE whatsapp_number = '+919000099999'")) == 1
    assert len(_rows("SELECT id FROM partner_seats")) == 1 and len(_rows("SELECT id FROM tenant_attributions")) == 1
    assert len(_rows("SELECT id FROM tenant_attribution_events")) == 1


def test_concurrent_onboarding_of_the_same_account_leaves_no_orphans():
    from concurrent.futures import ThreadPoolExecutor
    _seed_database()
    admin = _admin_headers()
    pid = _create_partner(admin)
    with ThreadPoolExecutor(max_workers=6) as pool:
        codes = list(pool.map(lambda _i: _onboard(admin, "racing_user", channel="partner", partner_id=pid,
                                                  whatsapp_number="+919000088888").status_code, range(6)))
    assert codes.count(200) == 1, codes                                      # exactly one onboarding wins
    tenants = _rows("SELECT id FROM tenants WHERE whatsapp_number = '+919000088888'")
    assert len(tenants) == 1
    assert len(_rows("SELECT id FROM users WHERE username = 'racing_user'")) == 1
    assert len(_rows("SELECT id FROM partner_seats")) == 1 and len(_rows("SELECT id FROM tenant_attributions")) == 1
    assert _rows("SELECT tenant_id FROM partner_seats") == [{"tenant_id": tenants[0]["id"]}]      # no orphaned seat
    assert _rows("SELECT s.id FROM partner_seats s LEFT JOIN tenants t ON t.id = s.tenant_id WHERE t.id IS NULL") == []


def test_failed_reassignment_keeps_the_previous_association_intact(monkeypatch):
    _seed_database()
    admin = _admin_headers()
    pa, pb = _create_partner(admin, "Alpha Advisory"), _create_partner(admin, "Bravo Campaigns")
    ha = _partner_session(admin, pa, "a@alpha.in")
    tid = _onboard(admin, "keepme", channel="partner", partner_id=pa).json()["tenant_id"]
    seat_before = _rows("SELECT id, partner_id, status, tenant_id FROM partner_seats")
    attr_before = _rows("SELECT tenant_id, channel, partner_id, attributed_by FROM tenant_attributions")

    def boom(*a, **k):
        raise RuntimeError("simulated failure creating the new association")
    monkeypatch.setattr(partners_mod, "_new_seat", boom)
    assert _reassign(admin, tid, pb).status_code == 500
    monkeypatch.undo()

    assert _rows("SELECT id, partner_id, status, tenant_id FROM partner_seats") == seat_before        # old seat NOT revoked
    assert _rows("SELECT tenant_id, channel, partner_id, attributed_by FROM tenant_attributions") == attr_before
    assert [e["event"] for e in _rows("SELECT event FROM tenant_attribution_events")] == ["onboarded"]
    assert len(_portfolio(ha)["clients"]) == 1                                                       # old partner still has access
    assert _reassign(admin, tid, pb).status_code == 200                                              # and a clean retry works


def test_failed_history_write_during_reassignment_rolls_back_the_move(monkeypatch):
    _seed_database()
    admin = _admin_headers()
    pa, pb = _create_partner(admin, "Alpha Advisory"), _create_partner(admin, "Bravo Campaigns")
    tid = _onboard(admin, "keepme2", channel="partner", partner_id=pa).json()["tenant_id"]

    def boom(*a, **k):
        raise RuntimeError("simulated failure writing history")
    monkeypatch.setattr(partners_mod, "TenantAttributionEvent", boom)
    assert _reassign(admin, tid, pb).status_code == 500
    monkeypatch.undo()
    assert _rows("SELECT partner_id, status FROM partner_seats WHERE tenant_id = :t", t=tid) == [{"partner_id": pa, "status": "active"}]
    assert _rows("SELECT partner_id FROM tenant_attributions WHERE tenant_id = :t", t=tid) == [{"partner_id": pa}]


def test_deactivating_a_partner_keeps_attribution_history_and_billing_records():
    _seed_database()
    admin = _admin_headers()
    pid = _create_partner(admin, wholesale_price_inr=10000)
    _onboard(admin, "hist_a", channel="partner", partner_id=pid)
    _onboard(admin, "hist_b", channel="partner", partner_id=pid)
    seats_before = _rows("SELECT id, tenant_id, status FROM partner_seats ORDER BY id")
    events_before = _rows("SELECT id, tenant_id, event FROM tenant_attribution_events ORDER BY id")
    client.patch(f"/api/admin/partners/{pid}", json={"is_active": False}, headers=admin)

    assert _rows("SELECT id, tenant_id, status FROM partner_seats ORDER BY id") == seats_before
    assert _rows("SELECT id, tenant_id, event FROM tenant_attribution_events ORDER BY id") == events_before
    assert len(_rows("SELECT id FROM tenant_attributions WHERE partner_id = :p", p=pid)) == 2
    listed = next(p for p in client.get("/api/admin/partners", headers=admin).json()["partners"] if p["id"] == pid)
    assert listed["clients_active"] == 2 and listed["is_active"] is False                 # still visible to staff for billing review


def test_portfolio_trend_sums_client_trends_and_skips_paused_clients():
    _seed_database()
    admin = _admin_headers()
    pid = _create_partner(admin)
    headers = _partner_session(admin, pid, "ops@rajdhani.in")
    seat_a = _attach(admin, pid, 2)
    seat_b = _attach(admin, pid, 3)
    view = _portfolio(headers)
    by_id = {c["id"]: c for c in view["clients"]}
    buckets = view["portfolio"]["trend"]
    assert len(buckets) == 5 and [b["period_end"] for b in buckets] == sorted(b["period_end"] for b in buckets)
    for i, b in enumerate(buckets):
        assert set(b) == {"period_start", "period_end", "received", "resolved"}            # aggregate counts only
        parts = [by_id[s]["summary"]["trend"][i] for s in (seat_a, seat_b)]
        assert all(p["period_end"] == b["period_end"] for p in parts)
        assert b["received"] == sum(p["received"] for p in parts) and b["resolved"] == sum(p["resolved"] for p in parts)

    assert client.post(f"/api/admin/partners/{pid}/seats/{seat_b}/status", json={"status": "paused"}, headers=admin).status_code == 200
    paused_view = _portfolio(headers)
    only_a = {c["id"]: c for c in paused_view["clients"]}[seat_a]["summary"]["trend"]
    assert [b["received"] for b in paused_view["portfolio"]["trend"]] == [b["received"] for b in only_a]


# ───────────────────────── historical data / date windows ─────────────────────────
def _add_history():
    """Tenant 2 gains older cases, a deleted old case and a synthetic test case; tenant 3 gains an old case."""
    now = datetime.utcnow()
    rows = [
        (101, 2, "resolved", 200, 0, 0, "Health", now - timedelta(days=200) + timedelta(days=10), "{}"),
        (102, 2, "new", 400, 1, 0, "Land", None, "{}"),
        (103, 2, "new", 300, 0, 1, "Water", None, "{}"),                       # deleted: never counted
        (104, 2, "new", 1, 0, 0, "Water", None, '{"synthetic_test_data": true}'),  # synthetic: never counted
        (105, 3, "new", 500, 0, 0, "Roads", None, "{}"),                        # other tenant
    ]
    with test_engine.begin() as conn:
        for cid, t, st, ago, crit, dele, cat, res, meta in rows:
            conn.execute(text(
                "INSERT INTO cases (id, tenant_id, user_phone, raw_message, category, status, ward, is_critical, "
                "is_deleted, created_at, resolved_at, case_metadata) VALUES (:id, :t, :ph, :msg, :cat, :st, 'Ward 9', "
                ":crit, :del, :cr, :rs, :meta)"),
                {"id": cid, "t": t, "ph": PHONE, "msg": RAW_MESSAGE, "cat": cat, "st": st, "crit": crit, "del": dele,
                 "cr": now - timedelta(days=ago), "rs": res, "meta": meta})


def _summary(headers, seat_id, query):
    resp = client.get(f"/api/partner/clients/{seat_id}/summary?{query}", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["summary"]


def test_all_time_includes_records_older_than_90_days_exactly_once():
    _seed_database()
    _add_history()
    admin = _admin_headers()
    pid = _create_partner(admin)
    headers = _partner_session(admin, pid, "ops@rajdhani.in")
    seat_id = _attach(admin, pid, 2)

    recent = _summary(headers, seat_id, "days=90")
    assert recent["total"] == 5  # cases 1-4 and 6; synthetic 104 and deleted 5 excluded
    everything = _summary(headers, seat_id, "range=all")
    # + case 101 (200 days) and 102 (400 days); deleted 103, synthetic 104 and tenant 3's 105 never counted
    assert (everything["total"], everything["resolved"], everything["critical"]) == (7, 3, 2)
    assert everything["window"]["kind"] == "all" and everything["window"]["from"] == (
        (datetime.utcnow() - timedelta(days=400)).date().isoformat())
    assert sum(b["received"] for b in everything["trend"]) == 7                       # no bucket double-counts
    assert sum(b["resolved"] for b in everything["trend"]) == 3
    assert len(everything["trend"]) <= 14 and everything["bucket_days"] == 30
    assert {c["name"] for c in everything["top_categories"]} == {"Water", "Roads", "Health", "Land"}
    assert everything["avg_resolution_days"] == round((1 + 3 + 10) / 3, 1)


def test_long_day_windows_and_custom_ranges_count_the_right_records():
    _seed_database()
    _add_history()
    admin = _admin_headers()
    pid = _create_partner(admin)
    headers = _partner_session(admin, pid, "ops@rajdhani.in")
    seat_id = _attach(admin, pid, 2)

    assert _summary(headers, seat_id, "days=365")["total"] == 6                          # adds case 101 only
    today = datetime.utcnow().date()
    older = _summary(headers, seat_id, f"from={(today - timedelta(days=450)).isoformat()}&to={(today - timedelta(days=100)).isoformat()}")
    assert (older["total"], older["resolved"]) == (2, 1)                                  # 101 and 102 only
    assert older["window"] == {"kind": "custom", "from": (today - timedelta(days=450)).isoformat(),
                               "to": (today - timedelta(days=100)).isoformat(), "days": 351}
    empty = _summary(headers, seat_id, f"from={(today - timedelta(days=150)).isoformat()}&to={(today - timedelta(days=120)).isoformat()}")
    assert (empty["total"], empty["resolution_rate"], empty["avg_resolution_days"], empty["top_categories"]) == (0, None, None, [])
    assert all(b["received"] == 0 for b in empty["trend"])
    single_day = _summary(headers, seat_id, f"from={(today - timedelta(days=2)).isoformat()}&to={(today - timedelta(days=2)).isoformat()}")
    assert single_day["total"] == 1 and single_day["bucket_days"] == 1


def test_portfolio_all_time_shares_one_window_across_clients():
    _seed_database()
    _add_history()
    admin = _admin_headers()
    pid = _create_partner(admin)
    headers = _partner_session(admin, pid, "ops@rajdhani.in")
    seat_a = _attach(admin, pid, 2)
    seat_b = _attach(admin, pid, 3)
    resp = client.get("/api/partner/clients?range=all", headers=headers)
    assert resp.status_code == 200, resp.text
    view = resp.json()
    # all time starts at the earliest case across this partner's clients (tenant 3's 500-day-old case)
    assert view["window"]["from"] == (datetime.utcnow() - timedelta(days=500)).date().isoformat()
    by_id = {c["id"]: c for c in view["clients"]}
    assert by_id[seat_a]["summary"]["total"] == 7 and by_id[seat_b]["summary"]["total"] == 3
    assert view["portfolio"]["total"] == 10 == sum(b["received"] for b in view["portfolio"]["trend"])
    assert view["portfolio"]["bucket_days"] == 91  # 500 days of history -> quarters, <= 14 points
    assert len(by_id[seat_a]["summary"]["trend"]) == len(by_id[seat_b]["summary"]["trend"]) == len(view["portfolio"]["trend"])


def test_window_parameters_are_validated():
    _seed_database()
    admin = _admin_headers()
    pid = _create_partner(admin)
    headers = _partner_session(admin, pid, "ops@rajdhani.in")
    seat_id = _attach(admin, pid, 2)
    base = f"/api/partner/clients/{seat_id}/summary"
    for bad in ("days=0", "days=3651", "range=forever", "range=all&days=30", "from=2026-01-10",
                "from=2026-02-01&to=2026-01-01", "from=2010-01-01&to=2026-01-01", "days=30&from=2026-01-01&to=2026-01-02",
                "from=not-a-date&to=2026-01-02"):
        assert client.get(f"{base}?{bad}", headers=headers).status_code == 422, bad
    assert client.get(base, headers=headers).json()["summary"]["window"]["days"] == 30          # default unchanged


def test_historical_windows_keep_tenant_isolation():
    _seed_database()
    _add_history()
    admin = _admin_headers()
    pid_a = _create_partner(admin, "Partner A")
    pid_b = _create_partner(admin, "Partner B")
    a = _partner_session(admin, pid_a, "a@a.in")
    b = _partner_session(admin, pid_b, "b@b.in")
    seat_a = _attach(admin, pid_a, 2)
    for q in ("range=all", "days=3650", "from=2005-01-01&to=2009-12-31"):
        assert client.get(f"/api/partner/clients/{seat_a}/summary?{q}", headers=b).status_code == 404, q
        assert client.get(f"/api/partner/clients/{seat_a}/report?{q}", headers=b).status_code == 404, q
    assert client.get("/api/partner/clients?range=all", headers=b).json()["clients"] == []
    report = client.get(f"/api/partner/clients/{seat_a}/report?range=all", headers=a)
    assert report.status_code == 200 and "All time" in report.text and PHONE not in report.text and RAW_MESSAGE not in report.text


def test_partner_payloads_never_contain_citizen_level_data():
    import json
    _seed_database()
    admin = _admin_headers()
    pid = _create_partner(admin)
    headers = _partner_session(admin, pid, "ops@rajdhani.in")
    seat_id = _attach(admin, pid, 2)
    bodies = [
        client.get("/api/partner/me", headers=headers).text,
        client.get("/api/partner/clients?days=90", headers=headers).text,
        client.get(f"/api/partner/clients/{seat_id}/summary?days=90", headers=headers).text,
        client.get(f"/api/partner/clients/{seat_id}/report?days=90", headers=headers).text,
    ]
    for body in bodies:
        assert PHONE not in body and "Ramesh" not in body and "Sewage" not in body and "Lane 4" not in body
        low = body.lower()
        for forbidden in ("user_phone", "raw_message", "phone_number", "whatsapp", "attachment", "media_url", "govt_ref", "reference_no"):
            assert forbidden not in low, forbidden
    for body in bodies[:3]:
        json.loads(body)                                                                  # stays well-formed JSON


def test_direct_tenants_never_appear_in_any_partner_portfolio_or_by_id():
    _seed_database()
    admin = _admin_headers()
    pa, pb = _create_partner(admin, "Alpha Advisory"), _create_partner(admin, "Bravo Campaigns")
    ha, hb = _partner_session(admin, pa, "a@alpha.in"), _partner_session(admin, pb, "b@bravo.in")
    direct_tid = _onboard(admin, "direct_only").json()["tenant_id"]
    a_seat = _attach(admin, pa, 2)
    assert [c["id"] for c in _portfolio(ha)["clients"]] == [a_seat] and _portfolio(hb)["clients"] == []
    for seat_id in range(1, 15):                                                          # probe ids, incl. other partner's seat
        for h in (hb,):
            assert client.get(f"/api/partner/clients/{seat_id}/summary", headers=h).status_code == 404
            assert client.get(f"/api/partner/clients/{seat_id}/report", headers=h).status_code == 404
    assert _rows("SELECT id FROM partner_seats WHERE tenant_id = :t", t=direct_tid) == []
    # tenant ids / partner ids supplied by the caller are ignored: query params cannot widen scope
    sneaky = client.get(f"/api/partner/clients?tenant_id={direct_tid}&partner_id={pa}", headers=hb)
    assert sneaky.status_code == 200 and sneaky.json()["clients"] == []


# ── consultant briefing ──
def _add_briefing_cases():
    """Tenant 2 gains filed, government-resolved, office-actioned, ready-to-file, noise and unmapped cases."""
    now = datetime.utcnow()
    rows = [
        # id, days ago, category, status, govt_status, govt_ref, govt_updated_days_ago, matched_value, free-text location
        (301, 3, "Roads", "in_progress", "submitted", "CPG/2026/1", 2, "Shahpur", None),
        (302, 4, "Roads", "in_progress", "resolved", "CPG/2026/2", 1, "Shahpur", None),
        (303, 6, "Drainage", "closed", "not_forwarded", None, None, "Anagol", None),
        (304, 7, "Drainage", "new", "pending_staff_submit", None, 5, "Anagol", None),
        (305, 8, "Drainage", "irrelevant", "not_forwarded", None, None, "Anagol", None),   # not a grievance
        (306, 40, "Drainage", "new", "not_forwarded", None, None, "Anagol", None),         # previous period
        (307, 9, "Roads", "new", "not_forwarded", None, None, "", "Behind Ramesh Patil house, Lane 4"),
    ]
    with test_engine.begin() as conn:
        for cid, ago, cat, st, gs, ref, gago, loc, free in rows:
            conn.execute(text(
                "INSERT INTO cases (id, tenant_id, user_phone, raw_message, category, status, location, ward, is_critical, "
                "is_deleted, created_at, govt_status, govt_reference_number, govt_status_updated_at, case_metadata) "
                "VALUES (:id, 2, :ph, :msg, :cat, :st, :free, 'Ward 9', 0, 0, :cr, :gs, :ref, :gup, :meta)"),
                {"id": cid, "ph": PHONE, "msg": RAW_MESSAGE, "cat": cat, "st": st, "free": free,
                 "cr": now - timedelta(days=ago), "gs": gs, "ref": ref,
                 "gup": now - timedelta(days=gago) if gago is not None else None,
                 "meta": json.dumps({"matched_value": loc, "location_resolved": bool(loc)})})


def _briefing(headers, seat_id, query="days=30"):
    resp = client.get(f"/api/partner/clients/{seat_id}/briefing?{query}", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["briefing"]


def test_briefing_momentum_funnel_and_comparison():
    _seed_database()
    _add_briefing_cases()
    admin = _admin_headers()
    pid = _create_partner(admin)
    headers = _partner_session(admin, pid, "ops@rajdhani.in")
    seat_id = _attach(admin, pid, 2)

    b = _briefing(headers, seat_id)
    m = b["momentum"]
    # now: cases 1-4 + 301-304 + 307 (deleted 5, noise 305 and older 6/306 excluded)
    assert {k: v["now"] for k, v in m.items()} == {
        "received": 9, "filed": 2, "resolved_by_government": 1, "other_actions": 3, "pending": 4}
    assert m["received"]["previous"] == 2  # cases 6 and 306
    for v in m.values():
        assert sum(v["trend"]) == v["now"] and len(v["trend"]) == len(b["periods"])
    assert b["funnel"] == {"received": 9, "action_taken": 5, "filed": 2, "resolved_by_government": 1,
                           "pending": 4, "ready_to_file": 1, "oldest_ready_days": 5}
    assert b["compare"] is not None and b["window"]["kind"] == "days"

    everything = _briefing(headers, seat_id, "range=all")
    assert everything["compare"] is None and everything["momentum"]["received"]["previous"] is None
    assert everything["momentum"]["received"]["now"] == 11


def test_briefing_issues_hotspots_and_wins_use_mapped_localities_only():
    _seed_database()
    _add_briefing_cases()
    admin = _admin_headers()
    pid = _create_partner(admin)
    headers = _partner_session(admin, pid, "ops@rajdhani.in")
    seat_id = _attach(admin, pid, 2)

    b = _briefing(headers, seat_id)
    issues = {i["name"]: i for i in b["issues"]}
    assert (issues["Roads"]["count"], issues["Roads"]["previous"]) == (4, 0)
    assert (issues["Water"]["count"], issues["Water"]["previous"]) == (3, 1)
    assert (issues["Drainage"]["count"], issues["Drainage"]["previous"]) == (2, 1)
    assert [x["name"] for x in issues["Roads"]["top_localities"]] == ["Shahpur"]
    assert sum(issues["Roads"]["trend"]) == 4

    hot = b["hotspots"]
    assert hot["columns"] == ["Roads", "Water", "Drainage"]
    assert hot["localities"] == [
        {"name": "Anagol", "total": 2, "counts": [0, 0, 2]},
        {"name": "Shahpur", "total": 2, "counts": [2, 0, 0]},
    ]
    assert hot["total_localities"] == 2 and hot["unmapped"] == 5
    assert b["wins"] == [{"name": "Roads", "count": 1, "localities": ["Shahpur"]}] and b["wins_total"] == 1

    body = json.dumps(b)
    for leaked in ("Ramesh", "Lane 4", PHONE, "Sewage overflow", "CPG/2026", "Ward 9"):
        assert leaked not in body


def test_briefing_is_seat_scoped():
    _seed_database()
    _add_briefing_cases()
    admin = _admin_headers()
    pid = _create_partner(admin)
    other = _create_partner(admin, name="Other Strategy")
    headers = _partner_session(admin, pid, "ops@rajdhani.in")
    other_headers = _partner_session(admin, other, "ops@other.in")
    seat_id = _attach(admin, pid, 2)
    other_seat = _attach(admin, other, 3)

    assert client.get(f"/api/partner/clients/{other_seat}/briefing?days=30", headers=headers).status_code == 404
    assert client.get(f"/api/partner/clients/{seat_id}/briefing?days=30", headers=other_headers).status_code == 404
    assert client.get(f"/api/partner/clients/{seat_id}/briefing?days=30").status_code in (401, 403)
    assert client.get(f"/api/partner/clients/{seat_id}/briefing?days=0", headers=headers).status_code == 422
    theirs = _briefing(other_headers, other_seat)
    assert theirs["momentum"]["received"]["now"] == 2 and theirs["hotspots"]["localities"] == []


# ── white-label report editions ──
def _set_edition(tenant_id, stage, seat_type):
    with test_engine.begin() as conn:
        conn.execute(text("UPDATE tenants SET account_stage = :s, tenant_type = :tt, seat_type = :st WHERE id = :i"),
                     {"s": stage, "tt": "aspirant" if stage == "aspirant" else seat_type, "st": seat_type, "i": tenant_id})
        conn.execute(text("UPDATE partner_seats SET seat_type = :st WHERE tenant_id = :i"), {"st": seat_type, "i": tenant_id})


def _report(headers, seat_id, query="days=30"):
    resp = client.get(f"/api/partner/clients/{seat_id}/report?{query}", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp


def _assert_no_citizen_data(body):
    low = body.lower()
    for leaked in (PHONE, RAW_MESSAGE, "Ramesh", "Lane 4", "Sewage overflow", "CPG/2026", "Ward 9"):
        assert leaked not in body, leaked
    for forbidden in ("user_phone", "raw_message", "phone_number", "whatsapp", "govt_ref", "reference_no"):
        assert forbidden not in low, forbidden


def test_report_edition_follows_the_tenant_not_the_request():
    _seed_database()
    _add_briefing_cases()
    admin = _admin_headers()
    pid = _create_partner(admin)
    headers = _partner_session(admin, pid, "ops@rajdhani.in")
    seat_id = _attach(admin, pid, 2)

    aspirant = _report(headers, seat_id)                    # tenant 2 is seeded as an aspirant
    assert aspirant.headers["x-report-edition"] == "aspirant"
    assert "Where the current administration is failing" in aspirant.text and "Presence map" in aspirant.text
    assert "never “resolved by”" in aspirant.text and "Government departments" not in aspirant.text
    assert _report(headers, seat_id, "days=30&edition=mla").headers["x-report-edition"] == "aspirant"

    _set_edition(2, "elected", "mla")
    mla = _report(headers, seat_id)
    assert mla.headers["x-report-edition"] == "mla"
    assert "Government departments" in mla.text and "Vidhan Sabha" in mla.text and "Presence map" not in mla.text
    assert "Assembly segments compared" not in mla.text

    _set_edition(2, "elected", "mp")
    mp = _report(headers, seat_id)
    assert mp.headers["x-report-edition"] == "mp"
    assert "Assembly segments compared" in mp.text and "Lok Sabha" in mp.text
    for r in (aspirant, mla, mp):
        _assert_no_citizen_data(r.text)


def test_office_report_numbers_departments_and_small_count_suppression():
    _seed_database()
    _add_briefing_cases()
    with test_engine.begin() as conn:
        conn.execute(text("UPDATE cases SET govt_department = 'Public Works Dept' WHERE id IN (301, 302)"))
        conn.execute(text("UPDATE cases SET is_critical = 1 WHERE id = 303"))
    _set_edition(2, "elected", "mla")
    admin = _admin_headers()
    pid = _create_partner(admin)
    headers = _partner_session(admin, pid, "ops@rajdhani.in")
    seat_id = _attach(admin, pid, 2)

    body = _report(headers, seat_id).text
    # scorecard: received 9, filed 2, resolved by government 1, other 3, pending 4
    for label, value in (("Complaints received", 9), ("Filed with government", 2), ("Resolved by government", 1),
                         ("Other actions taken", 3), ("Pending", 4)):
        assert re.search(rf'{label}</div><div class="v num"[^>]*>{value}<', body), label
    assert "<b>Public Works Dept</b>" in body
    # two complaints each in Shahpur and Anagol: printed as "<3", never as 1 or 2
    assert "&lt;3" in body and ">Shahpur<" in body
    assert "Recommended actions for the next 30 days" in body
    assert "Critical received this period</div><div class=\"v num\">2<" in body   # seeded case 4 + case 303
    _assert_no_citizen_data(body)


def test_aspirant_presence_lists_mapped_localities_with_no_contact():
    _seed_database()
    _add_briefing_cases()
    with test_engine.begin() as conn:
        for name in ("Shahpur", "Anagol", "Hindwadi", "Khasbag"):
            conn.execute(text(
                "INSERT INTO geo_places (seat_type, seat_name, parliamentary_constituency, assembly, canonical_name, "
                "canonical_norm, place_type, status, source, created_at) VALUES ('mla', 'Belagavi South', 'Belagavi', "
                "'Belagavi South', :n, :norm, 'locality', 'verified', 'test', :now)"),
                {"n": name, "norm": name.lower(), "now": datetime.utcnow()})
    admin = _admin_headers()
    pid = _create_partner(admin)
    headers = _partner_session(admin, pid, "ops@rajdhani.in")
    seat_id = _attach(admin, pid, 2)

    body = _report(headers, seat_id).text
    assert "localities have no contact with you yet" in body
    assert ">Hindwadi<" in body and ">Khasbag<" in body and "No presence" in body
    assert "2 of 4 localities in the constituency have at least one person in touch with you" in body
    _assert_no_citizen_data(body)


def test_mp_report_compares_assembly_segments_and_flags_the_weak_flank():
    _seed_database()
    _set_edition(2, "elected", "mp")
    now = datetime.utcnow()
    with test_engine.begin() as conn:
        rows = [(400 + i, "City", "new") for i in range(12)] + [(420 + i, "Rampur", "closed") for i in range(10)]
        for cid, seg, st in rows:
            conn.execute(text(
                "INSERT INTO cases (id, tenant_id, user_phone, raw_message, category, status, assembly, is_critical, is_deleted, created_at) "
                "VALUES (:id, 2, :ph, :msg, 'Roads', :st, :seg, 0, 0, :cr)"),
                {"id": cid, "ph": PHONE, "msg": RAW_MESSAGE, "st": st, "seg": seg, "cr": now - timedelta(days=2)})
    admin = _admin_headers()
    pid = _create_partner(admin)
    headers = _partner_session(admin, pid, "ops@rajdhani.in")
    seat_id = _attach(admin, pid, 2)

    body = _report(headers, seat_id).text
    assert "Assembly segments compared" in body
    city = body[body.index("<b>City</b>"):]
    assert city.startswith("<b>City</b><span class=\"tagx plank\">Weak flank</span>")
    assert "<b>Rampur</b></td>" in body       # fully acted on: not flagged
    _assert_no_citizen_data(body)
