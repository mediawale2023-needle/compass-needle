"""
tests/test_govt_sync_import_cycles.py — regression guard against the
Tamil Nadu status/adapters circular import.

THE BUG THIS PREVENTS: `modules/govt_sync/adapters/tamil_nadu_http.py` used
to import `_ACTION_TAKEN_UNAVAILABLE` from
`modules/govt_sync/status/tamil_nadu.py`, while that module imports
`normalize_status_keywords` from `modules/govt_sync/adapters/base.py`.
Because importing `..adapters.base` runs the adapters package's
`__init__.py` (which imports tamil_nadu_http), the result was a real cycle:

    status.tamil_nadu -> adapters.base -> adapters/__init__
        -> adapters.tamil_nadu_http -> status.tamil_nadu

Importing anything under `modules.govt_sync.status.*` FIRST therefore
raised `ImportError: cannot import name '_ACTION_TAKEN_UNAVAILABLE' from
partially initialized module ...`, while importing the adapters package
first worked — making it depend purely on import/test-collection order.
That is exactly why it surfaced in CI (which runs test files individually)
but not in every local run.

WHY SUBPROCESSES: Python caches modules in `sys.modules` for the lifetime
of the interpreter. Once ANY earlier test in the same pytest process has
imported the adapters package, the cycle is masked and an in-process
assertion would pass even against the broken code. Each case below
therefore runs in a genuinely fresh interpreter via `subprocess`, which is
the only way this regression can be detected reliably.

These tests assert ONLY that the imports succeed in both orders — no
implementation details, no constant values, nothing that would couple this
guard to Tamil Nadu behavior.
"""
import os
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Minimal env these modules' import chain expects (JWT_SECRET is validated
# at import time by api_router's config, and several modules read a DB URL).
_ENV = {
    **os.environ,
    "JWT_SECRET": "test-secret-key-32-characters-minimum-ok",
    "DATABASE_URL": "sqlite:///./test_govt_sync_import_cycles.db",
    "ENV": "test",
    "OPENAI_API_KEY": "sk-test-fake-key-for-testing",
}


def _import_in_fresh_process(*module_names: str) -> subprocess.CompletedProcess:
    """Imports the given modules, in the given order, in a brand-new
    interpreter with an empty module cache."""
    script = "\n".join(f"import {name}" for name in module_names)
    return subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        env=_ENV,
        capture_output=True,
        text=True,
        timeout=120,
    )


@pytest.mark.parametrize(
    "first,second",
    [
        # The order that used to fail: status package reached first.
        ("modules.govt_sync.status.tn_network_diagnostic", "modules.govt_sync.adapters.tamil_nadu_http"),
        # The reverse order, which happened to work before — asserted too so
        # a future "fix" can't trade one broken direction for the other.
        ("modules.govt_sync.adapters.tamil_nadu_http", "modules.govt_sync.status.tn_network_diagnostic"),
    ],
)
def test_govt_sync_status_and_adapters_import_in_either_order(first, second):
    result = _import_in_fresh_process(first, second)
    assert result.returncode == 0, (
        f"Importing {first} then {second} in a fresh interpreter failed — "
        f"this usually means a circular import was reintroduced between "
        f"modules.govt_sync.status.* and modules.govt_sync.adapters.*\n"
        f"stderr:\n{result.stderr}"
    )
    assert "ImportError" not in result.stderr
    assert "circular import" not in result.stderr


@pytest.mark.parametrize(
    "module_name",
    [
        "modules.govt_sync.status.tamil_nadu",
        "modules.govt_sync.status.tn_network_diagnostic",
        "modules.govt_sync.status.tn_http_replay_diagnostic",
        "modules.govt_sync.status.tn_diagnostic_runtime_gate",
        "modules.govt_sync.status.tn_phase2_evidence_envelope",
        "modules.govt_sync.adapters.tamil_nadu_http",
    ],
)
def test_each_tamil_nadu_module_imports_standalone_in_a_fresh_process(module_name):
    """Every TN status/adapter module must be importable as the very first
    govt_sync module in a fresh interpreter. Each of these was a real CI
    collection failure before the constant moved to the neutral module."""
    result = _import_in_fresh_process(module_name)
    assert result.returncode == 0, (
        f"{module_name} could not be imported first in a fresh interpreter.\n"
        f"stderr:\n{result.stderr}"
    )
    assert "ImportError" not in result.stderr
