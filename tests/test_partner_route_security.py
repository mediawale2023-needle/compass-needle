"""
Route-level security guard rails for the partner channel (PR 1 of the partner/MP dashboard parity work).

These tests change no production code. They enumerate EVERY route registered on the real FastAPI app (all routers
mounted in main.py: api_router, admin_api, partner_api, partner admin, and the routes defined on `app` itself) and
assert, from the dependency graph and from live requests, that:

  1. every route is classified by who may call it (MP, admin, partner, or an explicit public allowlist);
  2. a partner token is rejected by every MP and admin route, and MP/admin/no tokens are rejected by every partner route;
  3. public routes never accept a partner token as authority;
  4. nothing a partner can GET contains citizen contact data, complaint text or case-level identifiers;
  5. partner routes that take a seat id enforce ownership, paused and revoked rules and ignore tenant-id overrides.

Any NEW route added in a later PR is picked up automatically: an unclassified route, an unfillable path parameter on
a partner route or a PII leak fails these tests until it is handled deliberately.
"""
import re

import pytest
from fastapi.routing import APIRoute, APIWebSocketRoute

from tests.test_partner_api import (  # noqa: F401  (shared fixtures/helpers; importing sets up the isolated test DB)
    PHONE, RAW_MESSAGE, _admin_headers, _attach, _create_partner, _partner_session, _reassign, _seed_database, client,
    main, test_engine,
)

# ──────────────────────────── route registry ────────────────────────────
# Public routes (no bearer-token dependency). Every entry states why it is safe; an unlisted route without an auth
# dependency fails test_every_route_is_classified.
PUBLIC_ROUTES = {
    ("POST", "/api/auth/login"): "MP login",
    ("POST", "/api/admin/auth/login"): "admin login",
    ("POST", "/api/partner/auth/login"): "partner login",
    ("POST", "/api/support-access/consume"): "single-use launch token issued after MP approval",
    ("POST", "/internal/morning-digest"): "shared secret header (DIGEST_TOKEN), 503 when unset",
    ("GET", "/whatsapp/webhook"): "Meta verification handshake",
    ("POST", "/whatsapp/webhook"): "Meta HMAC signature",
    ("GET", "/"): "service banner",
    ("GET", "/health"): "health check",
    ("GET", "/health/db"): "health check",
    ("GET", "/health/ai"): "health check",
}
FRAMEWORK_ROUTES = {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}
WEBSOCKET_ROUTES = {"/api/govt/session/{session_id}/stream"}

# Keys that must never appear in a partner-visible JSON payload (case-insensitive, matched on the key name).
FORBIDDEN_KEYS = {
    "phone", "user_phone", "mobile", "msisdn", "whatsapp", "whatsapp_number", "contact_number",
    "raw_message", "message", "messages", "complaint", "complaint_text", "description_text",
    "notes_for_staff", "response_to_citizen", "assigned_to", "case_ref", "case_id", "case_ids", "cases",
    "citizen", "citizen_name", "reporter", "address", "govt_reference_number", "reference_number",
    "password", "password_hash", "token_hash",
}
PHONE_LIKE = re.compile(r"(?<!\d)(?:\+?91)?[6-9]\d{9}(?!\d)")
EMAIL_LIKE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
FORBIDDEN_VALUES = (PHONE, "Ramesh Patil", RAW_MESSAGE, "Sewage overflow", "Lane 4")


def _auth_family(route: APIRoute) -> set[str]:
    names: set[str] = set()

    def walk(dep):
        for sub in dep.dependencies:
            name = getattr(sub.call, "__name__", "")
            if name == "get_current_user":
                names.add("mp")
            elif name == "get_admin_user":
                names.add("admin")
            elif name in ("get_partner_user", "get_partner_user_pending_ok"):
                names.add("partner")
            walk(sub)

    walk(route.dependant)
    return names


def _registry():
    """Returns (api_routes, other_routes). api_routes: list of dicts with method, path, family."""
    api_routes, other = [], []
    for route in main.app.routes:
        if isinstance(route, APIRoute):
            fam = _auth_family(route)
            for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
                api_routes.append({"method": method, "path": route.path, "family": fam, "route": route})
        else:
            other.append(route)
    return api_routes, other


def _fill(path: str, **values) -> str:
    def repl(match):
        name = match.group(1).split(":")[0]
        return str(values.get(name, 1))
    return re.sub(r"\{([^}]+)\}", repl, path)


def _call(method, path, headers=None, **kw):
    kw.setdefault("json", {}) if method in ("POST", "PUT", "PATCH", "DELETE") else None
    return client.request(method, path, headers=headers or {}, **kw)


# ──────────────────────────── PII scanner ────────────────────────────
def pii_findings(payload, *, allow_keys=frozenset(), allow_values=frozenset(), _path="$") -> list[str]:
    """Walks any JSON-like value (or HTML/text string) and returns a list of PII findings. Empty list = clean."""
    found: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if str(key).lower() in FORBIDDEN_KEYS and str(key).lower() not in allow_keys:
                found.append(f"{_path}.{key}: forbidden key")
            found.extend(pii_findings(value, allow_keys=allow_keys, allow_values=allow_values, _path=f"{_path}.{key}"))
    elif isinstance(payload, (list, tuple)):
        for i, value in enumerate(payload):
            found.extend(pii_findings(value, allow_keys=allow_keys, allow_values=allow_values, _path=f"{_path}[{i}]"))
    elif isinstance(payload, str):
        for needle in FORBIDDEN_VALUES:
            if needle.lower() in payload.lower():
                found.append(f"{_path}: contains seeded sensitive value {needle!r}")
        if PHONE_LIKE.search(payload):
            found.append(f"{_path}: phone-like number")
        for email in EMAIL_LIKE.findall(payload):
            if email.lower() not in allow_values:
                found.append(f"{_path}: email address {email!r}")
    return found


def test_pii_scanner_detects_leaks_and_passes_clean_payloads():
    """Guards against a vacuous scanner: the seeded sensitive values and forbidden keys must be caught."""
    assert pii_findings({"clients": [{"client_label": "Asha", "summary": {"total": 4}}]}) == []
    assert pii_findings({"user_phone": "x"})
    assert pii_findings({"nested": [{"raw_message": "x"}]})
    assert pii_findings({"top_locations": [{"name": f"call {PHONE}"}]})
    assert pii_findings({"note": "reach me on +919812345678"})
    assert pii_findings({"x": RAW_MESSAGE})
    assert pii_findings("<p>Ramesh Patil</p>")
    assert pii_findings({"x": "someone@example.com"})
    assert pii_findings({"x": "someone@example.com"}, allow_values={"someone@example.com"}) == []
    assert pii_findings({"total": 1234567890}) == []  # ints are never treated as phone numbers


# ──────────────────────────── 1. classification ────────────────────────────
def test_every_route_is_classified():
    api_routes, other = _registry()
    assert len(api_routes) > 300, "route enumeration returned suspiciously few routes"

    problems = []
    for r in api_routes:
        key = (r["method"], r["path"])
        fam = r["family"]
        if len(fam) > 1:
            problems.append(f"{key}: mixes auth families {sorted(fam)}")
        elif not fam and key not in PUBLIC_ROUTES:
            problems.append(f"{key}: no auth dependency and not in PUBLIC_ROUTES")
        elif fam and key in PUBLIC_ROUTES:
            problems.append(f"{key}: has auth but is listed as public")
        if "partner" in fam and not r["path"].startswith("/api/partner/"):
            problems.append(f"{key}: partner-authenticated route outside /api/partner/")
        if r["path"].startswith("/api/partner/") and fam != {"partner"} and key != ("POST", "/api/partner/auth/login"):
            problems.append(f"{key}: under /api/partner/ but not partner-authenticated")
    assert not problems, "\n".join(problems)

    known = {(r["method"], r["path"]) for r in api_routes}
    stale = [k for k in PUBLIC_ROUTES if k not in known]
    assert not stale, f"stale PUBLIC_ROUTES entries: {stale}"

    non_api = {getattr(r, "path", "") for r in other if not isinstance(r, APIWebSocketRoute)}
    assert non_api <= FRAMEWORK_ROUTES, f"unexpected non-API routes: {non_api - FRAMEWORK_ROUTES}"
    sockets = {r.path for r in other if isinstance(r, APIWebSocketRoute)}
    assert sockets == WEBSOCKET_ROUTES, f"websocket routes changed, review their auth: {sockets ^ WEBSOCKET_ROUTES}"

    families = {f for r in api_routes for f in r["family"]}
    assert families == {"mp", "admin", "partner"}
    assert sum(1 for r in api_routes if "mp" in r["family"]) >= 140
    assert sum(1 for r in api_routes if "admin" in r["family"]) >= 140


# ──────────────────────────── 2. token separation ────────────────────────────
def _world():
    _seed_database()
    admin = _admin_headers()
    pid_a = _create_partner(admin, "Partner A")
    pid_b = _create_partner(admin, "Partner B")
    partner_a = _partner_session(admin, pid_a, "a@partner-a.in")
    partner_b = _partner_session(admin, pid_b, "b@partner-b.in")
    mp_login = client.post("/api/auth/login", json={"username": "asp_a", "password": "OwnerPass1!"})
    assert mp_login.status_code == 200, mp_login.text
    return {
        "admin": admin, "pid_a": pid_a, "pid_b": pid_b, "partner_a": partner_a, "partner_b": partner_b,
        "mp": {"Authorization": f"Bearer {mp_login.json()['token']}"},
    }


def test_partner_token_is_rejected_by_every_mp_and_admin_route():
    w = _world()
    api_routes, _ = _registry()
    bad = []
    checked = 0
    for r in api_routes:
        if not ({"mp", "admin"} & r["family"]):
            continue
        path = _fill(r["path"])
        for label, headers in (("partner token", w["partner_a"]), ("no token", {})):
            resp = _call(r["method"], path, headers)
            checked += 1
            if resp.status_code not in (401, 403):
                bad.append(f"{r['method']} {r['path']} with {label} -> {resp.status_code}")
    assert checked > 580
    assert not bad, "\n".join(bad)


def test_partner_routes_reject_mp_admin_and_missing_tokens():
    w = _world()
    api_routes, _ = _registry()
    partner_routes = [r for r in api_routes if r["family"] == {"partner"}]
    assert len(partner_routes) >= 5
    bad = []
    for r in partner_routes:
        path = _fill(r["path"])
        for label in ("mp", "admin"):
            resp = _call(r["method"], path, w[label])
            if resp.status_code not in (401, 403):
                bad.append(f"{r['method']} {r['path']} with {label} token -> {resp.status_code}")
        resp = _call(r["method"], path, {})
        if resp.status_code not in (401, 403):
            bad.append(f"{r['method']} {r['path']} with no token -> {resp.status_code}")
    assert not bad, "\n".join(bad)


def test_public_routes_never_accept_a_partner_token_as_authority():
    w = _world()
    headers = w["partner_a"]
    # Called deliberately: none can act on a bearer token. Login routes are excluded (they take credentials, not tokens).
    digest = client.post("/internal/morning-digest", headers=headers)
    assert digest.status_code >= 400, digest.text            # DIGEST_TOKEN unset in tests -> 503; never 2xx
    consume = client.post("/api/support-access/consume", json={"request_key": "does-not-exist"}, headers=headers)
    assert consume.status_code >= 400, consume.text
    hook_get = client.get("/whatsapp/webhook", headers=headers)
    assert hook_get.status_code >= 400, hook_get.text
    hook_post = client.post("/whatsapp/webhook", json={}, headers=headers)
    assert hook_post.status_code >= 400, hook_post.text


def test_websocket_rejects_partner_token():
    w = _world()
    token = w["partner_a"]["Authorization"].split(" ", 1)[1]
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/api/govt/session/abc/stream?token={token}") as ws:
            ws.receive_json()
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/govt/session/abc/stream") as ws:
            ws.receive_json()


# ──────────────────────────── 3. no PII on any partner GET ────────────────────────────
def _partner_get_routes():
    api_routes, _ = _registry()
    return [r for r in api_routes if r["family"] == {"partner"} and r["method"] == "GET"]


def test_no_partner_get_route_exposes_citizen_or_case_level_data():
    w = _world()
    seat_id = _attach(w["admin"], w["pid_a"], 2)  # tenant 2 owns the seeded cases that contain PHONE/RAW_MESSAGE
    routes = _partner_get_routes()
    assert len(routes) >= 3
    covered = 0
    for r in routes:
        params = re.findall(r"\{([^}:]+)", r["path"])
        unknown = [p for p in params if p != "seat_id"]
        assert not unknown, f"{r['path']}: test cannot fill path parameter(s) {unknown}; extend this test deliberately"
        for days in (7, 30, 90):
            resp = client.get(_fill(r["path"], seat_id=seat_id), params={"days": days}, headers=w["partner_a"])
            assert resp.status_code == 200, f"{r['path']} -> {resp.status_code} {resp.text[:200]}"
            body = resp.json() if "json" in resp.headers.get("content-type", "") else resp.text
            # /me legitimately returns the signed-in partner user's own email.
            allow = {"a@partner-a.in"} if r["path"].endswith("/me") else frozenset()
            assert pii_findings(body, allow_values=allow) == [], f"{r['path']} leaked: {pii_findings(body, allow_values=allow)}"
            covered += 1
    assert covered >= 9

    # Non-vacuous: the seeded tenant really does hold the sensitive data this test looks for.
    with test_engine.begin() as conn:
        row = conn.exec_driver_sql("select user_phone, raw_message from cases where tenant_id = 2 limit 1").fetchone()
    assert row[0] == PHONE and row[1] == RAW_MESSAGE


def test_partner_login_and_password_responses_contain_no_forbidden_fields():
    w = _world()
    resp = client.post("/api/partner/auth/login", json={"email": "a@partner-a.in", "password": "NewSecret9"})
    assert resp.status_code == 200
    findings = pii_findings(resp.json(), allow_values={"a@partner-a.in"})
    assert findings == [], findings
    assert "password_hash" not in resp.text and "token_hash" not in resp.text


# ──────────────────────────── 4. seat isolation on every {seat_id} route ────────────────────────────
def _seat_routes():
    return [r for r in _partner_get_routes() if "{seat_id}" in r["path"]]


def test_every_seat_route_enforces_ownership_pause_and_revocation():
    w = _world()
    admin = w["admin"]
    seat_a = _attach(admin, w["pid_a"], 2)
    seat_b = _attach(admin, w["pid_b"], 3)
    routes = _seat_routes()
    assert len(routes) >= 2

    for r in routes:
        # own seat works
        assert client.get(_fill(r["path"], seat_id=seat_a), headers=w["partner_a"]).status_code == 200, r["path"]
        # another partner's seat and nonexistent seats look identical: 404, never 403/200
        assert client.get(_fill(r["path"], seat_id=seat_b), headers=w["partner_a"]).status_code == 404, r["path"]
        assert client.get(_fill(r["path"], seat_id=999999), headers=w["partner_a"]).status_code == 404, r["path"]
        assert client.get(_fill(r["path"], seat_id=seat_a), headers=w["partner_b"]).status_code == 404, r["path"]

    # paused: existing behaviour preserved (409), no data
    paused = client.post(f"/api/admin/partners/{w['pid_a']}/seats/{seat_a}/status", json={"status": "paused"}, headers=admin)
    assert paused.status_code == 200, paused.text
    for r in routes:
        resp = client.get(_fill(r["path"], seat_id=seat_a), headers=w["partner_a"])
        assert resp.status_code == 409, f"{r['path']} paused -> {resp.status_code}"
        assert pii_findings(resp.text) == []

    # resumed, then reassigned away: the old seat is revoked and indistinguishable from a missing one (404)
    resumed = client.post(f"/api/admin/partners/{w['pid_a']}/seats/{seat_a}/status", json={"status": "active"}, headers=admin)
    assert resumed.status_code == 200, resumed.text
    moved = _reassign(admin, 2, w["pid_b"])
    assert moved.status_code == 200, moved.text
    for r in routes:
        assert client.get(_fill(r["path"], seat_id=seat_a), headers=w["partner_a"]).status_code == 404, r["path"]


def test_partner_routes_ignore_tenant_id_overrides():
    w = _world()
    seat_a = _attach(w["admin"], w["pid_a"], 2)
    _attach(w["admin"], w["pid_b"], 3)
    for r in _seat_routes():
        path = _fill(r["path"], seat_id=seat_a)
        base = client.get(path, headers=w["partner_a"])
        assert base.status_code == 200
        for override in ({"tenant_id": 3}, {"tid": 3}, {"tenant": 3}, {"partner_id": w["pid_b"]}, {"seat_id": 999}):
            resp = client.get(path, params=override, headers=w["partner_a"])
            assert resp.status_code == 200
            if "json" in base.headers.get("content-type", ""):
                assert resp.json() == base.json(), f"{r['path']} changed output for override {override}"
            else:
                assert resp.text == base.text, f"{r['path']} changed output for override {override}"
    portfolio = client.get("/api/partner/clients", headers=w["partner_a"]).json()
    other = client.get("/api/partner/clients", params={"tenant_id": 3, "partner_id": w["pid_b"]}, headers=w["partner_a"]).json()
    assert portfolio == other
    assert [c["id"] for c in portfolio["clients"]] == [seat_a]
