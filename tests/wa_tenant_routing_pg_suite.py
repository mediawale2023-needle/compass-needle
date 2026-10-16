"""WhatsApp number → tenant routing: reassignment regression suite (PostgreSQL).

Collected via tests/test_wa_tenant_routing_pg.py. Runs against a real PostgreSQL server (the routing guarantees depend on
Postgres row locks, JSON operators and partial unique indexes). Point
TEST_POSTGRES_URL at an EMPTY, disposable database:

    TEST_POSTGRES_URL=postgresql://postgres@localhost:54317/wa_routing_test \
        venv/bin/python -m pytest tests/test_wa_tenant_routing_pg.py -q

When TEST_POSTGRES_URL is unset the shim reports one explicit skip. All numbers below are synthetic.
"""
import hashlib
import hmac
import json
import os
import subprocess
import sys
import textwrap
import uuid
from datetime import datetime, timedelta, timezone

import pytest

PG_URL = os.environ["TEST_POSTGRES_URL"]

TEST_JWT_SECRET = "test-secret-key-32-characters-minimum-ok"
APP_SECRET = "meta-app-secret-for-routing-tests"
os.environ.update({
    "DATABASE_URL": PG_URL,
    "JWT_SECRET": TEST_JWT_SECRET,
    "ENV": "test",
    "OPENAI_API_KEY": "sk-test-fake-key-for-testing",
    "META_APP_SECRET": APP_SECRET,
    "META_ACCESS_TOKEN": "meta-test-token",
    "META_VERIFY_TOKEN": "meta-verify-token",
    "WA_TEXT_BUFFER_ENABLED": "0",
    "RUN_GEO_STARTUP_SYNC": "0",
})
os.environ.pop("WHATSAPP_PHONE_NUMBER_ID", None)
os.environ.pop("META_PHONE_NUMBER_ID", None)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

import jwt  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

import admin_api  # noqa: E402
import main  # noqa: E402
from modules import whatsapp as whatsapp_module  # noqa: E402
from sansadx_backend.db import engine, hash_password  # noqa: E402
from sansadx_backend.wa_routing import (  # noqa: E402
    OUTBOUND_BLOCKED_PHONE_NUMBER_ID,
    outbound_phone_number_id_for_tenant,
    resolve_whatsapp_tenant,
)
from tests.auth_token_claims import credential_claims  # noqa: E402

assert engine.dialect.name == "postgresql", "suite must run on PostgreSQL"

NUMBER = "+919000011111"          # the number being moved 11 → 10
PNID = "700000000011111"          # its Meta Phone Number ID
OTHER_NUMBER = "+919000022222"
OTHER_PNID = "700000000022222"

client = TestClient(main.app, raise_server_exceptions=False)


# ─────────────────────────── fixtures ───────────────────────────

def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture(autouse=True)
def seeded_db(monkeypatch):
    admin_api.JWT_SECRET = TEST_JWT_SECRET
    admin_api.ADMIN_JWT_SECRET = TEST_JWT_SECRET
    with engine.begin() as conn:
        for table in ("wa_inbound_messages", "wa_outbound_messages", "admin_audit_log", "token_blocklist",
                      "cases", "users", "tenant_overrides", "tenants"):
            conn.execute(text(f"DELETE FROM {table}"))  # nosec B608 — fixed table list
        for tid, name in ((1, "System Admin"), (10, "Tenant Ten"), (11, "Tenant Eleven"), (12, "Tenant Twelve")):
            conn.execute(text(
                "INSERT INTO tenants (id, name, constituency, is_active, created_at, config) "
                "VALUES (:id, :name, 'Test Seat', true, :now, CAST('{}' AS json))"
            ), {"id": tid, "name": name, "now": _now()})
        conn.execute(text(
            "INSERT INTO users (tenant_id, username, password_hash, role, constituency, display_name, is_active) "
            "VALUES (1, 'sysadmin', :pw, 'sysadmin', 'Test Seat', 'System Admin', true)"
        ), {"pw": hash_password("AdminPass1!")})
        # Starting state: the number belongs to tenant 11 — via Admin columns AND
        # a legacy phone_mapping row (the production shape that caused the bug).
        conn.execute(text(
            "UPDATE tenants SET whatsapp_number = :n, config = CAST(:cfg AS json) WHERE id = 11"
        ), {"n": NUMBER, "cfg": json.dumps({"meta_phone_number_id": PNID})})
        conn.execute(text(
            "INSERT INTO tenant_overrides (tenant_id, override_type, key, value, created_at) "
            "VALUES (11, 'phone_mapping', :n, '11', :now)"
        ), {"n": NUMBER, "now": _now()})

    # Stand-in for the AI pipeline: resolve the tenant exactly as the real
    # _process_incoming_message does (from the receiver it is handed) and
    # persist one case. Everything upstream — signature check, ledger, dedup,
    # dispatch, routing — is the production code path.
    def _fake_process(sender, message_body, receiver_number, msg_id="", *args, **kwargs):
        tenant_id = main._resolve_tenant(receiver_number)
        if tenant_id is None:
            return
        with engine.begin() as conn:
            case_id = conn.execute(text(
                "INSERT INTO cases (tenant_id, user_phone, raw_message, status, created_at) "
                "VALUES (:t, :p, :m, 'new', :now) RETURNING id"
            ), {"t": tenant_id, "p": sender, "m": message_body, "now": _now()}).scalar()
            if kwargs.get("inbound_ledger_id"):
                conn.execute(text("UPDATE wa_inbound_messages SET case_id = :c WHERE id = :i"),
                             {"c": case_id, "i": kwargs["inbound_ledger_id"]})

    monkeypatch.setattr(main, "_process_incoming_message", _fake_process)
    monkeypatch.setattr(main, "_is_inbound_sender_over_throttle", lambda _row: False)
    yield


def _admin_headers():
    now = datetime.now(timezone.utc).timestamp()
    token = jwt.encode(
        {**credential_claims(engine, "sysadmin"), "sub": "sysadmin", "tid": 1, "role": "sysadmin",
         "iat": now, "exp": now + 3600},
        TEST_JWT_SECRET, algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def _webhook(sender, body="Road broken near the school", *, number=NUMBER, pnid=PNID, msg_id=None):
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{"id": "waba", "changes": [{"field": "messages", "value": {
            "messaging_product": "whatsapp",
            "metadata": {"display_phone_number": number.lstrip("+"), "phone_number_id": pnid},
            "messages": [{"id": msg_id or f"wamid.{uuid.uuid4().hex}", "from": sender,
                          "timestamp": "1760000000", "type": "text", "text": {"body": body}}],
        }}]}],
    }
    raw = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(APP_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return client.post("/whatsapp/webhook", content=raw,
                       headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"})


def _reassign(tenant_id, *, number=NUMBER, pnid=PNID, transfer=True):
    return client.patch(f"/api/admin/mps/{tenant_id}/whatsapp", headers=_admin_headers(),
                        json={"whatsapp_number": number, "phone_number_id": pnid, "transfer": transfer})


def _cases(tenant_id, sender=None):
    sql = "SELECT id, user_phone FROM cases WHERE tenant_id = :t"
    params = {"t": tenant_id}
    if sender:
        sql += " AND user_phone = :s"
        params["s"] = sender
    with engine.connect() as conn:
        return conn.execute(text(sql), params).fetchall()


# ─────────────────────────── tests ───────────────────────────

def test_1_number_assigned_to_11_routes_to_11():
    assert _webhook("919800000001").status_code == 200
    assert len(_cases(11, "919800000001")) == 1
    assert _cases(10) == []


def test_2_reassigned_number_routes_new_messages_to_10():
    resp = _reassign(10)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["effective_routing"]["effective_tenant_id"] == 10
    assert body["effective_routing"]["source"] == "phone_number_id"
    assert body["transferred_from_tenant_ids"] == [11]
    assert body["legacy_overrides_removed"] == 1

    _webhook("919800000002")
    assert len(_cases(10, "919800000002")) == 1


def test_3_after_reassignment_tenant_11_gets_no_new_cases():
    _webhook("919800000003")
    before = len(_cases(11))
    assert _reassign(10).status_code == 200
    for i in range(3):
        _webhook(f"91980000010{i}")
    assert len(_cases(11)) == before
    assert len(_cases(10)) == 3


def test_4_historical_tenant_11_cases_unchanged():
    _webhook("919800000004")
    with engine.connect() as conn:
        historical = conn.execute(text(
            "SELECT id, tenant_id, user_phone, raw_message FROM cases WHERE tenant_id = 11 ORDER BY id"
        )).fetchall()
        ledger = conn.execute(text("SELECT id, tenant_id FROM wa_inbound_messages ORDER BY id")).fetchall()
    assert historical
    assert _reassign(10).status_code == 200
    _webhook("919800000005")
    with engine.connect() as conn:
        after = conn.execute(text(
            "SELECT id, tenant_id, user_phone, raw_message FROM cases WHERE id = ANY(:ids) ORDER BY id"
        ), {"ids": [r.id for r in historical]}).fetchall()
        ledger_after = conn.execute(text(
            "SELECT id, tenant_id FROM wa_inbound_messages WHERE id = ANY(:ids) ORDER BY id"
        ), {"ids": [r.id for r in ledger]}).fetchall()
    assert after == historical
    assert ledger_after == ledger


_WORKER = textwrap.dedent("""
    import sys
    from sansadx_backend.wa_routing import resolve_whatsapp_tenant
    for line in sys.stdin:
        number, pnid = line.split()
        print(resolve_whatsapp_tenant(number, pnid).tenant_id, flush=True)
""")


def _start_worker():
    env = {**os.environ, "PYTHONPATH": REPO_ROOT}
    return subprocess.Popen([sys.executable, "-c", _WORKER], cwd=REPO_ROOT, env=env, text=True,
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE)


def _ask(worker):
    worker.stdin.write(f"{NUMBER} {PNID}\n")
    worker.stdin.flush()
    return worker.stdout.readline().strip()


def test_5_two_independent_worker_processes_observe_new_mapping_immediately():
    workers = [_start_worker(), _start_worker()]
    try:
        assert [_ask(w) for w in workers] == ["11", "11"]   # warm: both have resolved before
        assert _reassign(10).status_code == 200
        assert [_ask(w) for w in workers] == ["10", "10"]   # no restart, no TTL wait
    finally:
        for w in workers:
            w.stdin.close()
            w.wait(timeout=10)


def test_6_unknown_phone_number_id_routes_nowhere():
    resp = _webhook("919800000006", number="+919000099999", pnid="799999999999999")
    assert resp.status_code == 200
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM cases")).scalar() == 0
        row = conn.execute(text("SELECT tenant_id, status, last_error FROM wa_inbound_messages")).one()
    assert row.tenant_id is None
    assert row.status == "failed" and row.last_error.startswith("TENANT_UNRESOLVED:unassigned_number")
    assert resolve_whatsapp_tenant("", "").tenant_id is None          # no implicit tenant 1


def test_7_conflicting_assignments_fail_safely():
    # Clash without explicit transfer → 409, nothing changes.
    resp = _reassign(10, transfer=False)
    assert resp.status_code == 409
    assert "currently assigned to" in resp.json()["detail"]
    assert resolve_whatsapp_tenant(NUMBER, PNID).tenant_id == 11

    # The database refuses a second owner of the same Phone Number ID.
    with pytest.raises(Exception):
        with engine.begin() as conn:
            conn.execute(text("UPDATE tenants SET config = CAST(:c AS json) WHERE id = 12"),
                         {"c": json.dumps({"meta_phone_number_id": PNID})})

    # Split ownership (Phone Number ID on 11, display number on 12) is ambiguous → rejected.
    with engine.begin() as conn:
        conn.execute(text("UPDATE tenants SET whatsapp_number = NULL WHERE id = 11"))
        conn.execute(text("UPDATE tenants SET whatsapp_number = :n WHERE id = 12"), {"n": NUMBER})
    res = resolve_whatsapp_tenant(NUMBER, PNID)
    assert res.tenant_id is None and res.reason == "ambiguous_assignment" and res.candidates == [11, 12]
    _webhook("919800000007")
    assert _cases(11) == [] and _cases(12) == []


def test_7b_stale_legacy_override_cannot_outrank_admin_assignment():
    # Reproduces the production failure: Admin gives the number to tenant 10,
    # but a phone_mapping row still says 11 (e.g. re-saved by the Overrides editor).
    with engine.begin() as conn:
        conn.execute(text("UPDATE tenants SET whatsapp_number = NULL, config = CAST('{}' AS json) WHERE id = 11"))
        conn.execute(text("UPDATE tenants SET whatsapp_number = :n, config = CAST(:c AS json) WHERE id = 10"),
                     {"n": NUMBER, "c": json.dumps({"meta_phone_number_id": PNID})})
    _webhook("919800000077")
    assert len(_cases(10, "919800000077")) == 1
    assert _cases(11) == []


def test_7c_legacy_override_only_for_unclaimed_numbers():
    # Backward compatible: a number no tenant claims still follows its legacy row…
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO tenant_overrides (tenant_id, override_type, key, value, created_at) "
            "VALUES (12, 'phone_mapping', :n, '12', :now)"
        ), {"n": OTHER_NUMBER, "now": _now()})
    res = resolve_whatsapp_tenant(OTHER_NUMBER, OTHER_PNID)
    assert (res.tenant_id, res.source) == (12, "legacy_override")
    # …until Admin assigns it, at which point Admin wins and the row is removed.
    resp = _reassign(10, number=OTHER_NUMBER, pnid=OTHER_PNID, transfer=False)
    assert resp.status_code == 200 and resp.json()["legacy_overrides_removed"] == 1
    assert resolve_whatsapp_tenant(OTHER_NUMBER, OTHER_PNID).tenant_id == 10


def test_8_admin_ui_and_webhook_agree_on_effective_mapping():
    assert _reassign(10).status_code == 200
    detail = client.get("/api/admin/mps/10/detail", headers=_admin_headers())
    assert detail.status_code == 200, detail.text
    routing = detail.json()["profile"]["whatsapp_routing"]
    assert routing["routes_to_this_tenant"] is True and routing["effective_tenant_id"] == 10

    old = client.get("/api/admin/mps/11/detail", headers=_admin_headers()).json()["profile"]
    assert old["whatsapp_routing"] is None and not old["whatsapp_number"]

    _webhook("919800000008")
    assert len(_cases(routing["effective_tenant_id"], "919800000008")) == 1

    with engine.connect() as conn:
        audit = conn.execute(text(
            "SELECT action, target_name, change_summary FROM admin_audit_log "
            "WHERE target_type = 'tenant_whatsapp' ORDER BY id"
        )).fetchall()
    assert [(a.action, a.target_name) for a in audit] == [("ended", "11"), ("updated", "10")]
    assert NUMBER not in " ".join(a.change_summary for a in audit)     # numbers are masked


def test_8b_inactive_target_is_not_reported_as_effective():
    with engine.begin() as conn:
        conn.execute(text("UPDATE tenants SET is_active = false WHERE id = 12"))
    resp = _reassign(12, number=OTHER_NUMBER, pnid=OTHER_PNID, transfer=False)
    assert resp.status_code == 200
    assert resp.json()["effective_routing"]["routes_to_this_tenant"] is False
    assert resp.json()["effective_routing"]["reason"] == "tenant_inactive"


def test_9_outbound_cannot_use_another_tenants_number(monkeypatch):
    sent = []
    monkeypatch.setattr(whatsapp_module.http_requests, "post",
                        lambda url, **kw: sent.append(url) or type("R", (), {"ok": True, "status_code": 200,
                                                                              "json": lambda self: {"messages": [{"id": "x"}]},
                                                                              "text": "{}"})())
    assert _reassign(10).status_code == 200

    # The global env number is now tenant 10's — tenant 11 must not borrow it.
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", PNID)
    assert outbound_phone_number_id_for_tenant(11) == OUTBOUND_BLOCKED_PHONE_NUMBER_ID
    assert outbound_phone_number_id_for_tenant(10) == PNID
    with pytest.raises(ValueError):
        whatsapp_module.send_whatsapp_message("919800000009", "hi", outbound_phone_number_id_for_tenant(11), tenant_id=11)
    with pytest.raises(ValueError):
        whatsapp_module.send_whatsapp_message("919800000009", "hi", PNID, tenant_id=11)   # explicit foreign ID
    assert sent == []

    assert whatsapp_module.send_whatsapp_message("919800000009", "hi", PNID, tenant_id=10) is True
    assert len(sent) == 1 and PNID in sent[0]
    with engine.connect() as conn:
        refused = conn.execute(text(
            "SELECT COUNT(*) FROM wa_outbound_messages WHERE tenant_id = 11 AND status = 'failed'"
        )).scalar()
    assert refused == 2


def test_10_duplicate_webhook_delivery_creates_one_case_one_tenant():
    assert _reassign(10).status_code == 200
    msg_id = f"wamid.{uuid.uuid4().hex}"
    for _ in range(3):
        assert _webhook("919800000010", msg_id=msg_id).status_code == 200
    with engine.connect() as conn:
        ledger = conn.execute(text(
            "SELECT tenant_id, case_id FROM wa_inbound_messages WHERE meta_message_id = :m"
        ), {"m": msg_id}).fetchall()
        cases = conn.execute(text(
            "SELECT tenant_id FROM cases WHERE user_phone = '919800000010'"
        )).fetchall()
    assert len(ledger) == 1 and ledger[0].tenant_id == 10
    assert [c.tenant_id for c in cases] == [10]
