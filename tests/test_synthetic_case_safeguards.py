import asyncio
import inspect
import json
import os
from collections import Counter

import pytest

os.environ.setdefault("JWT_SECRET", "test-secret-that-is-at-least-32-characters")
os.environ.setdefault("ADMIN_JWT_SECRET", "admin-test-secret-that-is-at-least-32-chars")

from modules.synthetic_cases import (
    SyntheticCaseActionBlocked,
    is_synthetic_case,
    require_operational_case,
    sql_is_live,
    sql_is_synthetic,
)
from scripts import tenant9_delhi_synthetic_cases as seed


@pytest.mark.parametrize("flag", ["synthetic_test_data", "synthetic_seed", "mock_seed"])
def test_explicit_provenance_flags_are_compatible(flag):
    assert is_synthetic_case({"case_metadata": {flag: True}})
    assert is_synthetic_case({"case_metadata": json.dumps({flag: True})})


def test_case_content_and_reference_patterns_never_imply_synthetic():
    case = {
        "case_ref": "SYN-T9-DL-001",
        "raw_message": "synthetic test complaint",
        "case_metadata": {"title": "TEST DATA", "synthetic_test_data": False},
    }
    assert not is_synthetic_case(case)
    require_operational_case(case, "send a message")


def test_synthetic_case_actions_fail_closed():
    with pytest.raises(SyntheticCaseActionBlocked, match="cannot send citizen notifications"):
        require_operational_case({"case_metadata": {"mock_seed": True}}, "send citizen notifications")


def test_sql_predicates_use_only_reliable_provenance_flags():
    predicate = sql_is_synthetic("c")
    assert all(flag in predicate for flag in ("synthetic_test_data", "synthetic_seed", "mock_seed"))
    assert "case_ref" not in predicate and "raw_message" not in predicate
    assert sql_is_live("c").startswith("NOT (")
    with pytest.raises(ValueError):
        sql_is_synthetic("c; DROP TABLE cases")


def test_tenant9_manifest_is_exact_and_taxonomy_catalogue_valid():
    manifest = seed.load_manifest()
    assert seed.validate_static_manifest(manifest) == []
    assert len(manifest["cases"]) == 20
    assert [item["case_ref"] for item in manifest["cases"]] == [
        f"SYN-T9-DL-{idx:03d}" for idx in range(1, 21)
    ]
    assert Counter(item["group"] for item in manifest["cases"]) == seed.EXPECTED_DISTRIBUTION
    assert {item["assembly"] for item in manifest["cases"]} == seed.EXPECTED_ASSEMBLIES
    assert all(item["created_at"].endswith("Z") for item in manifest["cases"])


def test_manifest_metadata_has_no_external_or_government_claims():
    manifest = seed.load_manifest()
    item = manifest["cases"][0]
    metadata = seed._metadata(manifest, item, "mp:New Delhi/Karol Bagh")
    assert metadata["synthetic_test_data"] is True
    assert metadata["external_actions_disabled"] is True
    assert metadata["suggestion_only_not_forwarded"] is True
    assert "government_reference" not in metadata


def test_production_guard_requires_exact_phrase_and_database(monkeypatch):
    class Result:
        def scalar_one(self):
            return "needle"
    class Conn:
        dialect = type("Dialect", (), {"name": "postgresql"})()
        def execute(self, *_args, **_kwargs):
            return Result()
    args = type("Args", (), {"execute": True, "rollback": False, "confirm_production": "", "confirm_database_name": ""})()
    monkeypatch.setenv("ENV", "production")
    with pytest.raises(seed.PreflightBlocked, match="exact --confirm-production"):
        seed._environment_guard(args, Conn())


def test_api_action_guard_is_tenant_scoped_and_blocks_before_side_effect(monkeypatch):
    import api_router
    observed = {}
    def fake_q_one(sql, params):
        observed.update(params)
        return {"id": params["cid"], "case_metadata": {"synthetic_test_data": True}}
    monkeypatch.setattr(api_router, "_q_one", fake_q_one)
    with pytest.raises(api_router.HTTPException) as exc:
        api_router._require_operational_case_id(9, 123, "record government references")
    assert exc.value.status_code == 409
    assert observed == {"cid": 123, "tid": 9}


def test_notify_endpoint_never_calls_whatsapp_for_synthetic_case(monkeypatch):
    import api_router
    monkeypatch.setattr(api_router, "get_tenant_or_fail", lambda _user: 9)
    monkeypatch.setattr(api_router, "_is_primary_workspace_user", lambda _user: True)
    monkeypatch.setattr(api_router, "_q_one", lambda *_args, **_kwargs: {
        "id": 1, "user_phone": "synthetic:test:tenant9:001",
        "case_metadata": {"synthetic_test_data": True},
    })
    request = type("Request", (), {"json": lambda self: {}})()
    with pytest.raises(api_router.HTTPException) as exc:
        asyncio.run(api_router.notify_citizen(1, request, None, {"tid": 9, "role": "owner"}))
    assert exc.value.status_code == 409


def test_background_poller_query_excludes_all_synthetic_provenance(monkeypatch):
    from modules.govt_sync import poller
    captured = {}
    def fake_q(sql, params):
        captured["sql"] = sql
        captured["params"] = params
        return []
    monkeypatch.setattr(poller, "_q", fake_q)
    assert poller.poll_all_pending() == {"pending": 0, "checked": 0, "changed": 0}
    assert all(flag in captured["sql"] for flag in ("synthetic_test_data", "synthetic_seed", "mock_seed"))


def test_execute_and_rollback_paths_use_managed_transactions():
    source = (seed.ROOT / "scripts" / "tenant9_delhi_synthetic_cases.py").read_text(encoding="utf-8")
    assert "with engine.begin() as conn:" in source
    assert "rollback_preflight(conn, manifest, args.allow_worksheet_artifacts)" in source
    assert "case_activity_log" in source and "govt_submission_log" in source


def _synthetic_tn_case(*_args, **_kwargs):
    return {"id": 22, "govt_status": "submitted", "govt_reference_number": "TN123",
            "case_metadata": {"synthetic_test_data": True}}


def test_tamil_nadu_status_helpers_refuse_synthetic_cases(monkeypatch):
    import types
    import api_router
    session = types.SimpleNamespace(tenant_id=1, case_id=22, portal={})
    monkeypatch.setattr("modules.govt_sync.browser_session.get_live_session", lambda _sid: session)
    monkeypatch.setattr("modules.govt_sync.browser_session.find_live_session_for_case", lambda _tid, _cid: session)
    monkeypatch.setattr(api_router, "_q_one", _synthetic_tn_case)
    for call in (
        lambda: api_router._get_tamil_nadu_live_status_context(22, "sess", {"tenant_id": 1}),
        lambda: api_router._get_tamil_nadu_live_status_context_for_case(22, {"tenant_id": 1}),
    ):
        with pytest.raises(api_router.HTTPException) as exc:
            call()
        assert exc.value.status_code == 409


def test_government_otp_anchor_case_can_never_be_synthetic():
    import api_router
    for handler in (api_router.govt_otp_send, api_router.govt_otp_verify):
        source = inspect.getsource(handler)
        assert "sql_is_live('cases')" in source, handler.__name__


def test_follow_up_sweep_and_brain_indexer_select_live_cases_only():
    import main
    from jobs import brain_indexer
    assert 'sql_is_live("cases")' in inspect.getsource(main._send_due_case_clarification_followups)
    assert "sql_is_live" in inspect.getsource(brain_indexer.index_cases_for_tenant)


def test_seeded_assembly_survives_the_read_path_even_when_the_resolver_disagrees(monkeypatch):
    import api_router
    item = next(c for c in seed.load_manifest()["cases"] if c["assembly"] == "R K Puram")
    meta = seed._metadata(seed.load_manifest(), item, "mp:New Delhi/R K Puram")
    # A resolver that would "correct" the assembly from the complaint text must not be consulted.
    monkeypatch.setattr(api_router, "resolve_location", lambda *a, **k: {"location_resolved": True, "matched_value": "Elsewhere", "assembly_constituency": "Wrong Assembly"})
    monkeypatch.setattr(api_router, "assembly_belongs_to_parliamentary", lambda *a, **k: False)
    case = {"raw_message": item["description"], "location": item["locality"], "assembly": item["assembly"], "case_metadata": meta}
    result = api_router._apply_tenant_safe_case_geography(case, "New Delhi", 9)
    assert (result["assembly"], result["location"]) == ("R K Puram", item["locality"])


def test_dry_run_report_contains_no_identifying_values():
    report = seed.redacted_report({
        "tenant": {"id": 9, "name": "Bansuri Swaraj"}, "geography_keys": {a: f"mp:New Delhi/{a}" for a in seed.EXPECTED_ASSEMBLIES},
        "counts": {"total": 0, "active": 0, "deleted": 0, "government_linked": 0},
    })
    blob = json.dumps(report)
    assert "Bansuri" not in blob and "mp:" not in blob and report["geography_segments_verified"] == 10


def test_production_dry_run_workflow_can_only_ever_dry_run():
    text_ = (seed.ROOT / ".github" / "workflows" / "tenant9-synthetic-dry-run.yml").read_text(encoding="utf-8")
    code = "\n".join(line for line in text_.splitlines() if not line.lstrip().startswith("#"))
    assert "--dry-run" in code
    assert "--execute" not in code and "--rollback" not in code
    assert "inputs:" not in code, "no workflow input may be able to change the mode"
    assert code.count("tenant9_delhi_synthetic_cases.py") == 1
