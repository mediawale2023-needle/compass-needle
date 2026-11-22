"""Partner-mode overview builder: counts only, restricted columns never selected.

Run on its own (``rm -f *.db`` first), like the other dashboard test modules.
The builder is not routed in this PR, so it is exercised directly with the
same dependency wiring the route uses.
"""

import json
import re
from datetime import datetime

import pytest
from sqlalchemy import text

import api_router
import core.db_helpers as db_helpers
import sansadx_backend.db as dbmod
from modules.dashboard_overview import (
    PARTNER_CASE_SQL,
    build_mp_overview,
    build_partner_overview,
)
from tests import test_dashboard_overview_golden as golden
from tests.test_partner_route_security import pii_findings

SEEDED_SECRETS = [
    "+919650787758", "919650787758", "Water supply problem", "GOV-306", "GOV-307",
    "GOV-308", "GOV-309", "GOV-310", "CN-301", "CN-305", "Ramesh", "Asha",
    "Tilakwadi", "Ward 5", "Vadgaon", "Hubli",
]

# Fragments that must never appear in SQL executed in partner mode.
FORBIDDEN_SQL = [
    r"user_phone", r"raw_message", r"case_ref", r"response_to_citizen", r"notes_for_staff",
    r"matched_value", r"\bc\.location\b", r"SELECT\s+\*", r"c\.case_metadata\s*(,|\bFROM\b)",
    r"activity_history", r"\bcontacts\b", r"wa_inbound_messages", r"wa_outbound_messages",
    r"govt_reference_number\s*(,|\bAS\b)",
]


@pytest.fixture()
def env(monkeypatch):
    dbmod.engine = golden.test_engine
    dbmod.SessionLocal = golden.TestSession
    db_helpers.engine = golden.test_engine
    api_router.engine = golden.test_engine
    golden.seed()
    with golden.test_engine.begin() as conn:
        conn.execute(text("DELETE FROM govt_submission_log"))
        for cid, action, payload in (
            (306, "status_check_failed", {}),
            (307, "status_polled", {"changed": True}),
        ):
            conn.execute(
                text("INSERT INTO govt_submission_log (tenant_id, case_id, action, payload, created_at) "
                     "VALUES (1, :c, :a, :p, :t)"),
                {"c": cid, "a": action, "p": json.dumps(payload), "t": datetime(2026, 3, 9, 9)},
            )
    monkeypatch.setattr(api_router, "_dashboard_govt_sync_map", golden._stub_sync_map)
    return api_router._overview_deps()


def _spy(deps):
    seen = []
    real_q, real_q1 = deps.q, deps.q_one
    deps.q = lambda sql, params=None: (seen.append(sql), real_q(sql, params))[1]
    deps.q_one = lambda sql, params=None: (seen.append(sql), real_q1(sql, params))[1]
    return seen


def test_partner_queries_never_select_restricted_columns(env):
    seen = _spy(env)
    build_partner_overview(1, env)
    assert len(seen) >= 4
    for sql in seen:
        for pattern in FORBIDDEN_SQL:
            assert not re.search(pattern, sql, re.I | re.S), f"{pattern!r} in partner SQL:\n{sql}"
    # The only case_metadata / payload / assigned_to / reference reads allowed:
    case_sql = PARTNER_CASE_SQL
    assert "case_metadata->>'assembly_constituency'" in case_sql
    assert "case_metadata->>'contact_thread_id'" in case_sql
    assert len(re.findall(r"case_metadata", case_sql)) == 2


def test_partner_output_is_counts_only_and_pii_free(env):
    out = build_partner_overview(1, env)
    assert "attention_queue" not in out and "recent_movement" not in out
    blob = json.dumps(out)
    for secret in SEEDED_SECRETS:
        assert secret not in blob, secret
    assert pii_findings(out) == []
    for key in ("attention_counts", "government_tracking", "constituency_pressure",
                "issue_pressure", "office_pending", "validation"):
        assert key in out
    assert out["mode"] == "partner"


def test_partner_counts_match_mp_overview(env):
    mp = build_mp_overview(1, {"constituency": "Belagavi"}, env)
    partner = build_partner_overview(1, env)
    assert {c["key"]: c["value"] for c in partner["attention_counts"]} == \
           {c["key"]: c["value"] for c in mp["attention_counts"]}
    assert partner["validation"]["thread_count"] == mp["validation"]["thread_count"]
    assert partner["office_pending"][0]["value"] == 2
    assert partner["office_pending"][1]["value"] == 1
    assert partner["office_pending"][2]["value"] == int(
        re.search(r"(\d+) unassigned", mp["office_pending"][2]["label"]).group(1)
    )


def test_partner_government_tracking_is_government_side_only(env):
    gt = build_partner_overview(1, env)["government_tracking"]
    assert gt == {
        "ready": 1, "submitted": 0, "registered": 1, "forwarded": 1, "awaiting_action": 1,
        "resolved": 1, "disposed": 0, "rejected": 1, "awaiting_verification": 0, "sync_issues": 1,
    }


def test_partner_counts_awaiting_verification(env):
    with golden.test_engine.begin() as conn:
        conn.execute(
            text("INSERT INTO govt_submission_log (tenant_id, case_id, action, payload, created_at) "
                 "VALUES (1, 310, 'status_check_needs_verification', '{}', :t)"),
            {"t": datetime(2026, 3, 9, 10)},
        )
    gt = build_partner_overview(1, env)["government_tracking"]
    assert gt["awaiting_verification"] == 1 and gt["sync_issues"] == 2


def test_partner_latest_sync_event_wins(env):
    with golden.test_engine.begin() as conn:
        conn.execute(
            text("INSERT INTO govt_submission_log (tenant_id, case_id, action, payload, created_at) "
                 "VALUES (1, 306, 'status_polled', :p, :t)"),
            {"p": json.dumps({"changed": False}), "t": datetime(2026, 3, 9, 11)},
        )
    out = build_partner_overview(1, env)
    assert out["government_tracking"]["sync_issues"] == 0


def test_partner_is_tenant_scoped(env):
    t1 = build_partner_overview(1, env)
    t2 = build_partner_overview(2, env)
    assert t2["validation"]["thread_count"] == 1
    assert t2["government_tracking"]["sync_issues"] == 0
    assert t1["validation"]["thread_count"] != t2["validation"]["thread_count"]


def test_partner_areas_are_assembly_level_only(env):
    out = build_partner_overview(1, env)
    for item in out["constituency_pressure"]:
        assert item["name"] in {"Belagavi Dakshin"}
    for item in out["issue_pressure"]:
        assert set(item) == {"title", "count"}
