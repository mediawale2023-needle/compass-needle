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
    for column in ("user_phone", "raw_message", "response_to_citizen", "notes_for_staff", "password", "token", "secret", "mp_name",
                   "phone", "mobile", "email", "contact", "display_name", "username", "last_login"):
        assert column not in code.replace("whatsapp_number is not null", ""), column
    # A phone number may only ever be tested for presence, never returned.
    assert not re.search(r"(?<![a-z_])whatsapp_number(?![a-z_])(?!\s+is\s+not\s+null)", code), "whatsapp_number must only appear as 'IS NOT NULL'"
    # Station payloads (`value`) may only be MEASURED or MATCHED, never returned as output.
    allowed = (
        r"length\(value\)", r"replace\(value,", r"value !?~ ", r"delhi_rows\.value ILIKE",
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


# ---- hardening required by the PR #160 approval conditions ----

import hashlib


def _workflow():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _steps():
    return _workflow()["jobs"]["diagnose"]["steps"]


def _step(name_fragment):
    return next(step for step in _steps() if name_fragment in step.get("name", ""))


def test_workflow_pins_the_exact_sql_by_sha256():
    pinned = _workflow()["jobs"]["diagnose"]["env"]["EXPECTED_SQL_SHA256"]
    assert pinned == hashlib.sha256(SQL.read_bytes()).hexdigest(), "SQL changed: update EXPECTED_SQL_SHA256 in the workflow (a reviewed edit)"
    assert _steps()[1]["name"].startswith("Validate Diagnostic SQL"), "validation must run before any secret is used"


def test_sql_uses_only_allow_listed_psql_meta_commands():
    allowed = {"\\echo", "\\pset", "\\gset", "\\if", "\\else", "\\endif"}
    found = {m.group(0).strip().strip(";") for m in re.finditer(r"(?:^|[\s;])\\[A-Za-z!?]+", SQL.read_text(encoding="utf-8"), re.MULTILINE)}
    assert found <= allowed, found - allowed


def test_third_party_actions_that_receive_secrets_are_pinned_to_commit_shas():
    for step in _steps():
        uses = step.get("uses")
        if uses:
            assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", uses), f"{uses} is not pinned to a full commit SHA"


def test_permissions_are_minimal_and_checkout_keeps_no_token():
    workflow = _workflow()
    assert workflow["permissions"] == {"contents": "read"}
    assert "permissions" not in workflow["jobs"]["diagnose"] or workflow["jobs"]["diagnose"]["permissions"] == {"contents": "read"}
    assert _step("Checkout")["with"]["persist-credentials"] is False


def test_nothing_attacker_controlled_reaches_a_shell():
    text_ = WORKFLOW.read_text(encoding="utf-8")
    code = "\n".join(line for line in text_.splitlines() if not line.lstrip().startswith("#"))
    for expression in re.findall(r"\$\{\{(.*?)\}\}", code):
        assert re.fullmatch(r"\s*(secrets\.(AWS_ACCESS_KEY_ID|AWS_SECRET_ACCESS_KEY|AWS_EC2_HOST|AWS_EC2_USER|AWS_EC2_SSH_KEY)|env\.AWS_REGION|steps\.ssh_ip\.outputs\.runner_ip)\s*", expression), expression
    assert "github.event" not in code and "inputs" not in code.replace("workflow_dispatch", "")


def test_server_side_read_only_is_enforced_for_psql():
    ssh = _step("Run Read-Only Diagnostic")["with"]["script"]
    assert 'PGOPTIONS="-c default_transaction_read_only=on"' in ssh and "ON_ERROR_STOP=1" in ssh
    assert ssh.count("psql") == 1 and not re.search(r"psql[^\n]*\s-[fc]\b", ssh)  # one psql, no -f/-c: fed only from the validated, decoded file on stdin


def test_ssh_is_opened_for_exactly_the_runner_slash_32_and_validated():
    allow = _step("Allow SSH")["run"]
    assert "CidrIp=${RUNNER_IP}/32" in allow and "FromPort=22,ToPort=22" in allow
    assert "0.0.0.0" not in WORKFLOW.read_text(encoding="utf-8")
    assert "[0-9]{1,3}" in allow, "runner IP must be validated before it is used"
    assert allow.index('echo "runner_ip=$RUNNER_IP"') < allow.index("authorize-security-group-ingress"), "record the IP before opening so cleanup always knows it"


def test_ssh_cleanup_is_unconditional_and_cannot_fail_silently():
    cleanup = _step("Remove GitHub Runner SSH Access")
    assert cleanup["if"].replace(" ", "").startswith("always()")
    assert _steps()[-1]["name"] == cleanup["name"], "cleanup must be the last step"
    run = cleanup["run"]
    assert "|| true" not in run, "a failed revoke must not be swallowed"
    assert "revoke-security-group-ingress" in run and "${CIDR}" in run and "/32" in run
    assert "exit 1" in run and "describe-security-groups" in run, "revoke is verified, and failure fails the job"


def test_section_three_lists_no_seat_names():
    sql = SQL.read_text(encoding="utf-8")
    section = sql[sql.index("=== 3."):sql.index("=== 4.")]
    assert "GROUP BY" not in section and "split_part(key, '/', 1)  " not in section.replace("COUNT(DISTINCT split_part(key, '/', 1))", "")
    assert "AGGREGATE ONLY" in section
