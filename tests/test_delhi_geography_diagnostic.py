"""The Delhi geography production diagnostic must stay strictly read-only and must not itself trigger a deploy."""
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / ".github" / "diagnostics" / "diagnose_delhi_geography.sql"
WORKFLOW = ROOT / ".github" / "workflows" / "diagnose-delhi-geography.yml"
DEPLOY = ROOT / ".github" / "workflows" / "deploy-aws-ec2.yml"


def _statements():
    text = SQL.read_text(encoding="utf-8")
    text = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith(("--", "\\echo", "\\pset")))
    return text


def test_sql_is_wrapped_in_a_read_only_transaction_and_rolls_back():
    lines = [line for line in SQL.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(line == "BEGIN TRANSACTION READ ONLY;" for line in lines)
    assert lines[-1] == "ROLLBACK;"


def test_sql_contains_no_write_or_ddl_keywords():
    code = re.sub(r"'(?:[^']|'')*'", "''", _statements())  # ignore string literals
    for keyword in ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "GRANT", "COPY", "VACUUM"):
        assert not re.search(rf"\b{keyword}\b", code, re.IGNORECASE), keyword


def test_sql_never_selects_citizen_or_secret_columns():
    code = _statements().lower()
    for column in ("user_phone", "raw_message", "response_to_citizen", "notes_for_staff", "password", "token", "secret", "mp_name"):
        assert column not in code, column
    # Station payloads (`value`) may only be MEASURED or MATCHED, never returned as output.
    allowed = (
        r"length\(value\)", r"replace\(value,", r"value ~ ", r"delhi_rows\.value ILIKE",
        r"\(SELECT value FROM tenant_overrides WHERE override_type = 'geography_data' AND key ILIKE '%delhi%'\)",
    )
    stripped = _statements()
    for pattern in allowed:
        stripped = re.sub(pattern, "", stripped, flags=re.IGNORECASE)
    # what remains must not mention the column at all (ignoring the table-qualified ILIKE column names)
    assert not re.search(r"(?<![\w.])value(?![\w])", re.sub(r"tenant_overrides\.value", "", stripped)), "payload column leaked into output"


def test_workflow_is_manual_only_and_runs_just_this_sql():
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    triggers = workflow.get("on") or workflow.get(True)
    assert set(triggers) == {"workflow_dispatch"} and not (triggers["workflow_dispatch"] or {}).get("inputs")
    text = WORKFLOW.read_text(encoding="utf-8")
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    assert code.count("diagnose_delhi_geography.sql") == 1
    assert "BEGIN TRANSACTION READ ONLY" in code and "ROLLBACK" in code


def test_diagnostic_files_are_outside_the_production_deploy_paths():
    deploy = yaml.safe_load(DEPLOY.read_text(encoding="utf-8"))
    paths = (deploy.get("on") or deploy.get(True))["push"]["paths"]
    for changed in (".github/diagnostics/diagnose_delhi_geography.sql", ".github/workflows/diagnose-delhi-geography.yml"):
        assert not any(Path(changed).match(p) or changed.startswith(p.rstrip("*")) for p in paths if p != ".github/workflows/deploy-aws-ec2.yml"), changed
