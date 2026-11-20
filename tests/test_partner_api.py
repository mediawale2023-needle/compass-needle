import os
import sys
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
                    (2, 2, 'asp_a', :owner_hash, 'owner', 'Belagavi', 'Vidhan Sabha', 'Aspirant A', 1, 0)
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


def _request_and_activate(admin, partner_headers, partner_id, label, tenant_id):
    req = client.post("/api/partner/seat-requests", json={"client_label": label, "constituency": "X"}, headers=partner_headers)
    assert req.status_code == 200, req.text
    seat_id = req.json()["seat"]["id"]
    act = client.post(f"/api/admin/partners/{partner_id}/seats/{seat_id}/activate", json={"tenant_id": tenant_id}, headers=admin)
    assert act.status_code == 200, act.text
    return seat_id


# ── tests ──
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
    # The pre-change token is revoked by the password change
    assert client.get("/api/partner/clients", headers=headers).status_code in (401, 403)


def test_login_failures_do_not_reveal_which_part_was_wrong():
    _seed_database()
    admin = _admin_headers()
    pid = _create_partner(admin)
    _create_partner_user(admin, pid, "ops@rajdhani.in")

    bad_pw = client.post("/api/partner/auth/login", json={"email": "ops@rajdhani.in", "password": "WrongPass1"})
    no_user = client.post("/api/partner/auth/login", json={"email": "ghost@rajdhani.in", "password": "WrongPass1"})
    assert bad_pw.status_code == no_user.status_code == 401
    assert bad_pw.json() == no_user.json()


def test_summary_numbers_scope_to_tenant_and_exclude_deleted():
    _seed_database()
    admin = _admin_headers()
    pid = _create_partner(admin)
    headers = _partner_session(admin, pid, "ops@rajdhani.in")
    seat_id = _request_and_activate(admin, headers, pid, "Client A", tenant_id=2)

    resp = client.get(f"/api/partner/clients/{seat_id}/summary?days=30", headers=headers)
    assert resp.status_code == 200, resp.text
    s = resp.json()["summary"]
    assert s["total"] == 4          # soft-deleted and 45-day-old cases excluded, tenant 3 excluded
    assert s["resolved"] == 2
    assert s["open"] == 2
    assert s["critical"] == 1
    assert s["resolution_rate"] == 0.5
    assert s["avg_resolution_days"] == 2.0
    assert {c["name"] for c in s["top_categories"]} == {"Water", "Roads"}
    assert len(s["weekly"]) == 8

    listing = client.get("/api/partner/clients?days=30", headers=headers).json()
    assert listing["portfolio"]["total"] == 4
    assert listing["clients"][0]["summary"]["total"] == 4
    assert PHONE not in resp.text and "Ramesh" not in resp.text


def test_partner_cannot_see_another_partners_client():
    _seed_database()
    admin = _admin_headers()
    pa, pb = _create_partner(admin, "Alpha Advisory"), _create_partner(admin, "Bravo Campaigns")
    ha = _partner_session(admin, pa, "a@alpha.in")
    hb = _partner_session(admin, pb, "b@bravo.in")
    seat_a = _request_and_activate(admin, ha, pa, "Alpha client", tenant_id=2)
    _request_and_activate(admin, hb, pb, "Bravo client", tenant_id=3)

    for path in ("summary", "report"):
        assert client.get(f"/api/partner/clients/{seat_a}/{path}", headers=hb).status_code == 404
    labels = {c["client_label"] for c in client.get("/api/partner/clients", headers=hb).json()["clients"]}
    assert labels == {"Bravo client"}


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
    assert client.get("/api/auth/me", headers=partner_headers).status_code == 401


def test_seat_cap_enforced_and_rejected_seat_frees_capacity():
    _seed_database()
    admin = _admin_headers()
    pid = _create_partner(admin, seat_cap=1)
    headers = _partner_session(admin, pid, "ops@rajdhani.in")

    first = client.post("/api/partner/seat-requests", json={"client_label": "One"}, headers=headers)
    assert first.status_code == 200
    second = client.post("/api/partner/seat-requests", json={"client_label": "Two"}, headers=headers)
    assert second.status_code == 409

    pending = client.get("/api/admin/partners/requests/pending", headers=admin).json()["requests"]
    assert [r["client_label"] for r in pending] == ["One"]

    seat_id = first.json()["seat"]["id"]
    assert client.post(f"/api/admin/partners/{pid}/seats/{seat_id}/reject", headers=admin).status_code == 200
    assert client.post("/api/partner/seat-requests", json={"client_label": "Two"}, headers=headers).status_code == 200


def test_tenant_cannot_be_linked_to_two_seats_or_be_inactive():
    _seed_database()
    admin = _admin_headers()
    pa, pb = _create_partner(admin, "Alpha Advisory"), _create_partner(admin, "Bravo Campaigns")
    ha = _partner_session(admin, pa, "a@alpha.in")
    hb = _partner_session(admin, pb, "b@bravo.in")
    _request_and_activate(admin, ha, pa, "Alpha client", tenant_id=2)

    seat_b = client.post("/api/partner/seat-requests", json={"client_label": "Bravo"}, headers=hb).json()["seat"]["id"]
    dup = client.post(f"/api/admin/partners/{pb}/seats/{seat_b}/activate", json={"tenant_id": 2}, headers=admin)
    inactive = client.post(f"/api/admin/partners/{pb}/seats/{seat_b}/activate", json={"tenant_id": 4}, headers=admin)
    missing = client.post(f"/api/admin/partners/{pb}/seats/{seat_b}/activate", json={"tenant_id": 999}, headers=admin)
    assert dup.status_code == 409
    assert inactive.status_code == 404
    assert missing.status_code == 404


def test_paused_seat_stops_serving_data():
    _seed_database()
    admin = _admin_headers()
    pid = _create_partner(admin)
    headers = _partner_session(admin, pid, "ops@rajdhani.in")
    seat_id = _request_and_activate(admin, headers, pid, "Client A", tenant_id=2)

    assert client.post(f"/api/admin/partners/{pid}/seats/{seat_id}/status", json={"status": "paused"}, headers=admin).status_code == 200
    assert client.get(f"/api/partner/clients/{seat_id}/summary", headers=headers).status_code == 409


def test_report_is_branded_escaped_and_free_of_citizen_data():
    _seed_database()
    admin = _admin_headers()
    pid = _create_partner(admin, brand_name="Rajdhani <b>Strategy</b>", brand_color="#B8860B",
                          brand_logo_url="https://cdn.example.com/logo.png", show_powered_by=False)
    headers = _partner_session(admin, pid, "ops@rajdhani.in")
    req = client.post("/api/partner/seat-requests", json={"client_label": "<script>alert(1)</script>", "constituency": "Belagavi"}, headers=headers)
    seat_id = req.json()["seat"]["id"]
    client.post(f"/api/admin/partners/{pid}/seats/{seat_id}/activate", json={"tenant_id": 2}, headers=admin)

    resp = client.get(f"/api/partner/clients/{seat_id}/report", headers=headers)
    assert resp.status_code == 200
    body = resp.text
    assert "<script>alert(1)</script>" not in body and "&lt;script&gt;" in body
    assert "Rajdhani &lt;b&gt;Strategy&lt;/b&gt;" in body
    assert "#B8860B" in body and "https://cdn.example.com/logo.png" in body
    assert "Compass Needle" not in body  # white-label: powered-by switched off
    assert PHONE not in body and "Ramesh" not in body and "Sewage" not in body


def test_partner_config_validation():
    _seed_database()
    admin = _admin_headers()
    http_logo = client.post("/api/admin/partners", json={"name": "Bad Logo", "brand_logo_url": "http://x.com/l.png"}, headers=admin)
    js_logo = client.post("/api/admin/partners", json={"name": "Bad Logo", "brand_logo_url": "javascript:alert(1)"}, headers=admin)
    assert http_logo.status_code == 400 and js_logo.status_code == 400

    pid = _create_partner(admin, brand_color="red; background:url(x)")
    listing = client.get("/api/admin/partners", headers=admin).json()["partners"]
    assert [p["brand_color"] for p in listing if p["id"] == pid] == [partners_mod.DEFAULT_BRAND_COLOR]

    a = _create_partner(admin, "Same Name")
    b = _create_partner(admin, "Same Name")
    slugs = {p["slug"] for p in client.get("/api/admin/partners", headers=admin).json()["partners"] if p["id"] in (a, b)}
    assert len(slugs) == 2


def test_deactivated_partner_loses_access_immediately():
    _seed_database()
    admin = _admin_headers()
    pid = _create_partner(admin)
    headers = _partner_session(admin, pid, "ops@rajdhani.in")
    assert client.get("/api/partner/me", headers=headers).status_code == 200

    assert client.patch(f"/api/admin/partners/{pid}", json={"is_active": False}, headers=admin).status_code == 200
    assert client.get("/api/partner/me", headers=headers).status_code == 401


def test_admin_can_list_users_reset_password_and_deactivate():
    _seed_database()
    admin = _admin_headers()
    pid = _create_partner(admin)
    headers = _partner_session(admin, pid, "ops@rajdhani.in")

    users = client.get(f"/api/admin/partners/{pid}/users", headers=admin).json()["users"]
    assert [u["email"] for u in users] == ["ops@rajdhani.in"]
    uid = users[0]["id"]
    assert "password_hash" not in users[0]

    reset = client.post(f"/api/admin/partners/{pid}/users/{uid}/reset-password", headers=admin)
    assert reset.status_code == 200
    temp = reset.json()["temporary_password"]
    assert client.get("/api/partner/clients", headers=headers).status_code == 401  # old session revoked
    assert client.post("/api/partner/auth/login", json={"email": "ops@rajdhani.in", "password": "NewSecret9"}).status_code == 401
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


def test_available_tenants_excludes_linked_inactive_and_admin_accounts():
    _seed_database()
    admin = _admin_headers()
    # tenant 3 gets an owner user so it qualifies; tenant 2 is linked below; tenant 4 inactive; tenant 1 is the admin tenant
    with test_engine.begin() as conn:
        conn.execute(text("INSERT INTO users (id, tenant_id, username, password_hash, role, constituency, house, display_name, is_active, must_change_password) "
                          "VALUES (3, 3, 'asp_b', 'x', 'owner', 'Pune', 'Vidhan Sabha', 'Aspirant B', 1, 0)"))
    pid = _create_partner(admin)
    headers = _partner_session(admin, pid, "ops@rajdhani.in")

    before = {t["tenant_id"] for t in client.get("/api/admin/partners/available-tenants", headers=admin).json()["tenants"]}
    assert before == {2, 3}
    _request_and_activate(admin, headers, pid, "Client A", tenant_id=2)
    after = {t["tenant_id"] for t in client.get("/api/admin/partners/available-tenants", headers=admin).json()["tenants"]}
    assert after == {3}


def test_admin_partner_list_and_seats_include_counts_and_tenant_name():
    _seed_database()
    admin = _admin_headers()
    pid = _create_partner(admin)
    headers = _partner_session(admin, pid, "ops@rajdhani.in")
    _request_and_activate(admin, headers, pid, "Client A", tenant_id=2)
    client.post("/api/partner/seat-requests", json={"client_label": "Client B"}, headers=headers)

    p = client.get("/api/admin/partners", headers=admin).json()["partners"][0]
    assert (p["seats_active"], p["seats_requested"], p["seats_used"], p["users_count"]) == (1, 1, 2, 1)
    seats = client.get(f"/api/admin/partners/{pid}/seats", headers=admin).json()["seats"]
    assert {s["client_label"]: s["tenant_name"] for s in seats} == {"Client A": "Aspirant A", "Client B": None}
