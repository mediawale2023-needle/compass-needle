"""Real JWT/SQL regression tests; synthetic tenants only, no provider calls."""
import os
import uuid
import sys
import types
import jwt
from threading import Barrier, Event
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_pilot_sessions.db")
os.environ.setdefault("GEMINI_API_KEY", "test-only")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text, event
from starlette.websockets import WebSocketDisconnect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import make_url

import api_router as mp
import admin_api as admin
import core.db_helpers as helpers
from sansadx_backend.db import Base, hash_password


@pytest.fixture
def env(tmp_path, monkeypatch):
    pg_url = os.environ.get("PILOT_SESSION_TEST_POSTGRES_URL")
    schema = None
    if pg_url:
        url = make_url(pg_url)
        assert url.host in {"127.0.0.1", "localhost"} and url.database == "needle_phase1_test"
        schema = "session_test_" + uuid.uuid4().hex
        setup_engine = create_engine(pg_url)
        with setup_engine.begin() as c:
            c.execute(text(f'CREATE SCHEMA "{schema}"'))
        engine = create_engine(pg_url, connect_args={"options": f"-csearch_path={schema}"})
    else:
        engine = create_engine(f"sqlite:///{tmp_path}/sessions.db", connect_args={"check_same_thread": False})
    names = ["tenants", "users", "token_blocklist", "support_access_requests", "admin_audit_log"]
    Base.metadata.create_all(engine, tables=[Base.metadata.tables[n] for n in names])
    for module in (mp, admin, helpers):
        monkeypatch.setattr(module, "engine", engine)
    monkeypatch.setattr(admin, "SessionLocal", sessionmaker(bind=engine))
    with engine.begin() as c:
        c.execute(text("INSERT INTO tenants(id,name,is_active,account_stage,seat_type) VALUES (1,'A',true,'aspirant','mp'),(2,'B',true,'aspirant','mp')"))
        for ident, name, role, tid in [(1,"owner","owner",1),(2,"staff","staff",1),(3,"operator","sysadmin",None),(4,"rival","owner",2)]:
            c.execute(text("INSERT INTO users(id,username,role,tenant_id,is_active,password_hash) VALUES (:id,:u,:r,:t,true,:p)"),
                      {"id":ident,"u":name,"r":role,"t":tid,"p":hash_password("SafePassword9!")})
    app = FastAPI()
    app.include_router(mp.router, prefix="/api")
    app.include_router(admin.router, prefix="/api/admin")
    client = TestClient(app, raise_server_exceptions=False)
    yield engine, client
    engine.dispose()
    if schema:
        with setup_engine.begin() as c:
            c.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        setup_engine.dispose()


def headers(name="staff", tid=1, role="staff", **claims):
    return {"Authorization": "Bearer " + mp.create_token({"sub":name,"tid":tid,"role":role,**claims}, credential_user=mp._q_one("SELECT * FROM users WHERE username = :u", {"u":name}))}


def admin_headers():
    return {"Authorization": "Bearer " + admin.create_admin_token({"sub":"operator","tid":0,"role":"sysadmin"}, credential_user=admin._q_one("SELECT * FROM users WHERE username = :u", {"u":"operator"}))}


def sql(engine, statement, **params):
    with engine.begin() as c:
        c.execute(text(statement), params)


@pytest.mark.parametrize("statement", [
    "UPDATE users SET is_active=false WHERE username='staff'",
    "UPDATE users SET tenant_id=2 WHERE username='staff'",
    "UPDATE users SET role='owner' WHERE username='staff'",
    "UPDATE tenants SET is_active=false WHERE id=1",
])
def test_issued_token_loses_http_and_ws_access(env, statement):
    engine, client = env
    auth = headers()
    assert client.get("/api/auth/me", headers=auth).status_code == 200
    sql(engine, statement)
    assert client.get("/api/auth/me", headers=auth).status_code == 401
    assert mp._get_ws_user(auth["Authorization"][7:]) is None


def test_admin_suspension_and_logout_revoke_existing_token(env):
    engine, client = env
    auth = admin_headers()
    sql(engine, "UPDATE users SET is_active=false WHERE username='operator'")
    assert client.post("/api/admin/logout", headers=auth).status_code == 401
    sql(engine, "UPDATE users SET is_active=true WHERE username='operator'")
    auth = admin_headers()
    assert client.post("/api/admin/logout", headers=auth).status_code == 200
    assert client.post("/api/admin/logout", headers=auth).status_code == 401


@pytest.mark.parametrize("path,body,undo", [
    ("/api/admin/staff/2/suspend", None, None),
    ("/api/admin/staff/2/reassign", {"tenant_id":2}, {"tenant_id":1}),
    ("/api/admin/staff/2", {"role":"user"}, {"role":"staff"}),
    ("/api/admin/mps/1/onboarding", {"live":False}, {"live":True}),
])
def test_authority_round_trip_does_not_resurrect_token(env, path, body, undo):
    _, client = env
    auth, operator = headers(), admin_headers()
    assert client.patch(path, json=body, headers=operator).status_code == 200
    assert client.patch(path, json=undo, headers=operator).status_code == 200
    assert client.get("/api/auth/me", headers=auth).status_code == 401


def seed_support(engine):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    sql(engine, """INSERT INTO support_access_requests
        (request_key,tenant_id,target_username,requested_by_admin_username,approved_by_username,
         reason,scope,status,duration_minutes,launch_token,launch_token_expires_at,requested_at)
        VALUES ('support',1,'owner','operator','owner','Investigate','full_view','approved',30,'one-time',:expires,:now)""",
        expires=now+timedelta(minutes=15), now=now)


def consume(client):
    return client.post("/api/support-access/consume", json={"request_key":"support","launch_token":"one-time"})


@pytest.mark.parametrize("terminal", ["revoked","ended","expired"])
def test_support_terminal_state_invalidates_issued_token(env, terminal):
    engine, client = env
    seed_support(engine)
    response = consume(client)
    assert response.status_code == 200, response.text
    auth = {"Authorization":"Bearer "+response.json()["token"]}
    assert client.get("/api/auth/me", headers=auth).status_code == 200
    if terminal == "revoked":
        assert client.post("/api/support-access/support/revoke", headers=headers("owner",role="owner")).status_code == 200
    elif terminal == "ended":
        assert client.post("/api/support-access/end", headers=auth).status_code == 200
    else:
        sql(engine,"UPDATE support_access_requests SET session_expires_at=:past",past=datetime(2000,1,1))
    assert client.get("/api/auth/me", headers=auth).status_code == 401


def test_support_read_only_scope_and_operator_revocation(env):
    engine, client = env
    seed_support(engine)
    response = consume(client)
    assert response.status_code == 200, response.text
    token=response.json()["token"]
    auth={"Authorization":"Bearer "+token}
    assert client.post("/api/logout",headers=auth).status_code == 403
    assert client.post("/api/support-access/support/approve",headers=auth).status_code == 403
    assert client.get("/api/support-access/inbox",headers=auth).status_code == 403
    assert mp._get_ws_user(token) is None
    assert client.post("/api/admin/logout",headers=admin_headers()).status_code == 200
    assert client.get("/api/auth/me",headers=auth).status_code == 401


def test_support_claim_is_atomic(env, monkeypatch):
    engine, client = env
    seed_support(engine)
    barrier = Barrier(2)
    original = mp._q_one
    def synchronized_read(query, params=None):
        row = original(query, params)
        if "SELECT * FROM support_access_requests" in query and params == {"request_key":"support"}:
            barrier.wait(timeout=5)
        return row
    monkeypatch.setattr(mp, "_q_one", synchronized_read)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses=list(pool.map(lambda _: consume(client), range(2)))
    assert sorted(r.status_code for r in responses) == [200,409]
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM admin_audit_log WHERE action='session_started'")).scalar() == 1


def test_support_wrong_tenant_and_expired_launch_denied(env):
    engine, client = env
    seed_support(engine)
    sql(engine,"UPDATE users SET tenant_id=2 WHERE username='owner'")
    assert consume(client).status_code == 401
    sql(engine,"UPDATE users SET tenant_id=1 WHERE username='owner'")
    sql(engine,"UPDATE support_access_requests SET launch_token_expires_at=:past",past=datetime(2000,1,1))
    assert consume(client).status_code in (400,409)


def test_open_websocket_stops_after_suspension(env, monkeypatch):
    engine, client = env
    fake = types.ModuleType("modules.govt_sync.browser_session")
    fake.get_session_meta = lambda _: {"tenant_id":1, "case_id":1}
    async def noop(*args): pass
    fake.attach_stream = fake.detach_stream = fake.relay_input = noop
    monkeypatch.setitem(sys.modules, "modules.govt_sync.browser_session", fake)
    token = headers()["Authorization"][7:]
    with client.websocket_connect(f"/api/govt/session/demo/stream?token={token}") as ws:
        assert ws.receive_json()["type"] == "ready"
        sql(engine,"UPDATE users SET is_active=false WHERE username='staff'")
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()  # idle connection must close without another input
        assert exc.value.code == 4401


def test_revocation_failure_rolls_back_staff_change(env):
    engine, client = env
    auth, operator = headers(), admin_headers()
    def fail_revocation(conn, cursor, statement, parameters, context, many):
        if statement.startswith("INSERT INTO token_blocklist"):
            raise RuntimeError("Simulated storage failure")
    event.listen(engine,"before_cursor_execute",fail_revocation)
    try:
        assert client.patch("/api/admin/staff/2/reassign",json={"tenant_id":2},headers=operator).status_code == 500
    finally:
        event.remove(engine,"before_cursor_execute",fail_revocation)
    assert client.get("/api/auth/me",headers=auth).status_code == 200


@pytest.mark.parametrize("name,tid,role", [("owner",1,"owner"),("rival",2,"owner")])
def test_same_seat_tenants_remain_bound(env,name,tid,role):
    engine, client = env
    sql(engine,"UPDATE tenants SET constituency='Same constituency'")
    auth = headers(name,tid,role)
    assert client.get("/api/auth/me",headers=auth).json()["tenant_id"] == tid
    forged_binding = headers(name,3-tid,role)
    assert client.get("/api/auth/me",headers=forged_binding).status_code == 401


def test_password_change_invalidates_issued_token(env):
    _, client = env
    auth = headers()
    response=client.post("/api/auth/change-password",headers=auth,
                         json={"current_password":"SafePassword9!","new_password":"AnotherSafe9!"})
    assert response.status_code == 200, response.text
    assert client.get("/api/auth/me",headers=auth).status_code == 401


def test_support_reads_are_attributed_and_owner_session_survives_end(env):
    engine, client=env
    seed_support(engine)
    owner=headers("owner",role="owner")
    response=consume(client)
    assert response.json()["user"]["is_support_access_session"] is True
    support={"Authorization":"Bearer "+response.json()["token"]}
    assert client.get("/api/auth/me",headers=support).status_code == 200
    with engine.connect() as c:
        assert c.execute(text("SELECT admin_username FROM admin_audit_log WHERE action='support_request'")).scalar() == "operator"
    assert client.post("/api/support-access/end",headers=support).status_code == 200
    assert client.get("/api/auth/me",headers=owner).status_code == 200


def test_disabled_tenant_cannot_login(env):
    engine,client=env
    sql(engine,"UPDATE tenants SET is_active=false WHERE id=1")
    response=client.post("/api/auth/login",json={"username":"staff","password":"SafePassword9!"})
    assert response.status_code == 401


@pytest.mark.parametrize("missing", ["tid", "role", "iat", "exp", "credential_state"])
def test_incomplete_tokens_are_rejected(env, missing):
    _,client=env
    payload={"sub":"staff","tid":1,"role":"staff",
             "iat":datetime.now(timezone.utc).timestamp(),
             "exp":datetime.now(timezone.utc).timestamp()+3600}
    payload["credential_state"] = mp.credential_binding(mp._q_one("SELECT * FROM users WHERE username = :u", {"u":"staff"}))
    del payload[missing]
    token=jwt.encode(payload,mp.JWT_SECRET,algorithm=mp.JWT_ALGORITHM)
    assert client.get("/api/auth/me",headers={"Authorization":"Bearer "+token}).status_code == 401
    assert mp._get_ws_user(token) is None


@pytest.mark.parametrize("change", [
    "UPDATE support_access_requests SET scope='owner'",
    "UPDATE support_access_requests SET tenant_id=2",
    "UPDATE users SET is_active=false WHERE username='operator'",
    "UPDATE users SET role='staff' WHERE username='operator'",
])
def test_support_rechecks_scope_tenant_and_operator(env, change):
    engine,client=env
    seed_support(engine)
    response=consume(client)
    auth={"Authorization":"Bearer "+response.json()["token"]}
    sql(engine,change)
    assert client.get("/api/auth/me",headers=auth).status_code == 401


def test_aspirant_csr_edit_is_already_restricted_server_side(env):
    _,client=env
    response=client.patch("/api/csr/companies/1/profile",headers=headers("owner",role="owner"),
                          json={"notes":"Must not write shared data"})
    assert response.status_code == 403
    assert "aspirant" in response.json()["detail"]


def test_login_racing_revocation_cannot_mint_fresh_authority(env, monkeypatch):
    engine, client = env
    original = mp.verify_password

    def revoke_during_verification(password, password_hash):
        verified = original(password, password_hash)
        with engine.begin() as conn:
            mp.revoke_in_transaction(conn, "staff")
        return verified

    monkeypatch.setattr(mp, "verify_password", revoke_during_verification)
    response = client.post("/api/auth/login", json={"username": "staff", "password": "SafePassword9!"})
    assert response.status_code == 200
    auth = {"Authorization": "Bearer " + response.json()["token"]}
    assert client.get("/api/auth/me", headers=auth).status_code == 401


def test_revocation_storage_failure_denies_existing_session(env):
    engine, client = env
    auth = headers()

    def fail_read(conn, cursor, statement, parameters, context, many):
        if "SELECT revoked_at FROM token_blocklist" in statement:
            raise RuntimeError("Simulated revocation read failure")

    event.listen(engine, "before_cursor_execute", fail_read)
    try:
        assert client.get("/api/auth/me", headers=auth).status_code == 401
        assert mp._get_ws_user(auth["Authorization"][7:]) is None
    finally:
        event.remove(engine, "before_cursor_execute", fail_read)


def test_deleted_username_reuse_does_not_resurrect_token(env):
    engine, client = env
    sql(engine, "UPDATE users SET role='editor' WHERE username='staff'")
    auth = headers(role="editor")
    assert client.get("/api/auth/me", headers=auth).status_code == 200
    assert client.delete("/api/admin/editors/2", headers=admin_headers()).status_code == 200
    sql(engine, """INSERT INTO users(id, username, tenant_id, role, is_active, password_hash)
        VALUES (2, 'staff', 1, 'editor', true, :password_hash)""",
        password_hash=hash_password("DifferentSafe9!"))
    assert client.get("/api/auth/me", headers=auth).status_code == 401


@pytest.mark.parametrize("is_admin", [False, True], ids=["aspirant", "admin"])
@pytest.mark.parametrize("login_count", [1, 3], ids=["one-login", "multiple-logins"])
def test_postgres_login_during_uncommitted_password_change(env, monkeypatch, is_admin, login_count):
    engine, client = env
    if engine.dialect.name != "postgresql":
        pytest.skip("Requires PostgreSQL MVCC; covered by PostgreSQL 17 CI")
    module = admin if is_admin else mp
    username = "operator" if is_admin else "staff"
    login_path = "/api/admin/auth/login" if is_admin else "/api/auth/login"
    original_auth = admin_headers() if is_admin else headers()
    inserted, release = Event(), Event()
    verified = Barrier(login_count + 1)
    original_revoke, original_clear = module.revoke_in_transaction, module._clear_login_failures

    def hold_before_commit(conn, subject):
        original_revoke(conn, subject)
        inserted.set()
        assert release.wait(30), "Controller did not release password transaction"

    def after_old_credentials_verified(subject):
        # Real login has already verified the committed old hash. Its next write
        # may wait for the password transaction; no credential verification mock.
        verified.wait(timeout=30)
        original_clear(subject)

    monkeypatch.setattr(module, "revoke_in_transaction", hold_before_commit)
    monkeypatch.setattr(module, "_clear_login_failures", after_old_credentials_verified)
    change_path = "/api/admin/settings/password" if is_admin else "/api/auth/change-password"
    change_method = client.patch if is_admin else client.post
    with ThreadPoolExecutor(max_workers=login_count + 1) as pool:
        change = pool.submit(change_method, change_path, headers=original_auth,
                             json={"current_password":"SafePassword9!", "new_password":"AnotherSafe9!"})
        try:
            assert inserted.wait(30), "Password transaction did not reach its cutoff"
            logins = [pool.submit(client.post, login_path,
                                  json={"username":username, "password":"SafePassword9!"})
                      for _ in range(login_count)]
            verified.wait(timeout=30)
        finally:
            release.set()
        assert change.result(timeout=30).status_code == 200
        responses = [future.result(timeout=30) for future in logins]
    monkeypatch.setattr(module, "_clear_login_failures", original_clear)
    monkeypatch.setattr(module, "revoke_in_transaction", original_revoke)

    # A harmless read which exists in the minimal synthetic schema.
    probe_path = "/api/admin/staff" if is_admin else "/api/auth/me"
    assert client.get(probe_path, headers=original_auth).status_code == 401
    for response in responses:
        assert response.status_code == 200, response.text
        stale = {"Authorization":"Bearer " + response.json()["token"]}
        assert client.get(probe_path, headers=stale).status_code == 401
        if not is_admin:
            assert mp._get_ws_user(response.json()["token"]) is None
    assert client.post(login_path, json={"username":username,"password":"SafePassword9!"}).status_code == 401
    fresh = client.post(login_path, json={"username":username,"password":"AnotherSafe9!"})
    assert fresh.status_code == 200, fresh.text
    assert client.get(probe_path, headers={"Authorization":"Bearer " + fresh.json()["token"]}).status_code == 200


@pytest.mark.parametrize("is_admin", [False, True], ids=["aspirant", "admin"])
def test_password_transaction_rollback_preserves_credentials_and_sessions(env, monkeypatch, is_admin):
    _, client = env
    module = admin if is_admin else mp
    auth = admin_headers() if is_admin else headers()
    original_revoke = module.revoke_in_transaction

    def rollback_after_revocation(conn, username):
        original_revoke(conn, username)
        raise RuntimeError("Simulated failure before commit")

    monkeypatch.setattr(module, "revoke_in_transaction", rollback_after_revocation)
    method, path = (client.patch, "/api/admin/settings/password") if is_admin else (client.post, "/api/auth/change-password")
    assert method(path, headers=auth, json={"current_password":"SafePassword9!","new_password":"AnotherSafe9!"}).status_code == 500
    probe_path = "/api/admin/staff" if is_admin else "/api/auth/me"
    assert client.get(probe_path, headers=auth).status_code == 200
    login_path = "/api/admin/auth/login" if is_admin else "/api/auth/login"
    username = "operator" if is_admin else "staff"
    assert client.post(login_path, json={"username":username,"password":"SafePassword9!"}).status_code == 200
    assert client.post(login_path, json={"username":username,"password":"AnotherSafe9!"}).status_code == 401


def test_open_websocket_stops_after_password_change(env, monkeypatch):
    _, client = env
    fake = types.ModuleType("modules.govt_sync.browser_session")
    fake.get_session_meta = lambda _: {"tenant_id":1, "case_id":1}
    async def noop(*args): pass
    fake.attach_stream = fake.detach_stream = fake.relay_input = noop
    monkeypatch.setitem(sys.modules, "modules.govt_sync.browser_session", fake)
    auth = headers()
    with client.websocket_connect('/api/govt/session/demo/stream?token=' + auth["Authorization"][7:]) as ws:
        assert ws.receive_json()["type"] == "ready"
        assert client.post("/api/auth/change-password", headers=auth,
                           json={"current_password":"SafePassword9!","new_password":"AnotherSafe9!"}).status_code == 200
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
        assert exc.value.code == 4401


def test_support_operator_credential_change_invalidates_capability_without_cutoff(env):
    engine, client = env
    seed_support(engine)
    response = consume(client)
    assert response.status_code == 200
    auth = {"Authorization":"Bearer " + response.json()["token"]}
    sql(engine, "UPDATE users SET password_hash=:password_hash WHERE username='operator'",
        password_hash=hash_password("AnotherSafe9!"))
    assert client.get("/api/auth/me", headers=auth).status_code == 401


def test_unverifiable_credential_state_fails_closed(env, monkeypatch):
    _, client = env
    auth = headers()
    original = mp._q_one
    def missing_credential(query, params=None):
        row = original(query, params)
        if row and "SELECT * FROM users" in query:
            row = {**row, "password_hash":None}
        return row
    monkeypatch.setattr(mp, "_q_one", missing_credential)
    assert client.get("/api/auth/me", headers=auth).status_code == 401
    assert mp._get_ws_user(auth["Authorization"][7:]) is None
