from pathlib import Path

import yaml


WORKFLOW_PATH = Path(__file__).parents[1] / ".github/workflows/deploy-aws-ec2.yml"


def _workflow():
    # BaseLoader keeps the YAML 1.1 word "on" as a string for stable assertions.
    return yaml.load(WORKFLOW_PATH.read_text(), Loader=yaml.BaseLoader)


def test_backend_deployment_is_manual_only():
    workflow = _workflow()
    triggers = workflow["on"]
    assert set(triggers) == {"workflow_dispatch"}
    assert workflow["run-name"] == "Deploy backend @ ${{ inputs.target_sha }}"
    target = triggers["workflow_dispatch"]["inputs"]["target_sha"]
    assert target["required"] == "true"
    assert target["type"] == "string"


def test_target_revision_is_guarded_and_used_by_deployment():
    workflow = _workflow()
    prepare = workflow["jobs"]["prepare"]
    deploy = workflow["jobs"]["deploy"]
    validation = next(
        step["run"] for step in prepare["steps"] if step.get("name") == "Validate Target Revision"
    )
    remote_deploy = next(
        step for step in deploy["steps"] if step.get("name") == "Deploy Over SSH"
    )

    assert "merge-base --is-ancestor" in validation
    assert 'origin/main' in validation
    assert 'Backend, Frontend, Admin, And Browser Tests' in validation
    assert 'commits/${TARGET_SHA}/check-runs' in validation
    assert '.status != "completed" or .conclusion != "success"' in validation
    assert 'PRODUCT_TESTS_TOTAL' in validation
    assert 'PRODUCT_TESTS_UNSUCCESSFUL' in validation
    assert deploy["needs"] == "prepare"
    assert deploy["environment"] == "production"
    assert 'git reset --hard "$TARGET_SHA"' in remote_deploy["with"]["script"]
    assert remote_deploy["env"]["TARGET_SHA"] == "${{ needs.prepare.outputs.target_sha }}"


def test_health_check_and_failure_exit_are_preserved():
    deploy = _workflow()["jobs"]["deploy"]
    health = next(step["run"] for step in deploy["steps"] if step.get("name") == "Verify Backend Health")
    assert "https://api.theneedle.in/health" in health
    assert "Backend did not pass health check after deploy." in health
    assert "exit 1" in health
