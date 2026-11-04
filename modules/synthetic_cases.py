"""Canonical synthetic-case provenance and fail-closed safeguards.

Only explicit metadata written by trusted seed tooling is accepted.  Case
content and reference-number patterns are deliberately ignored so genuine
citizen cases can never be reclassified by a heuristic.
"""
from __future__ import annotations

import json
from typing import Any, Mapping


PROVENANCE_FLAGS = ("synthetic_test_data", "synthetic_seed", "mock_seed")
CANONICAL_FLAG = "synthetic_test_data"
# Contact sentinel written by trusted seed tooling for synthetic_test_data rows. It
# is not a dialable address, so it doubles as a transport-level kill switch.
SYNTHETIC_PHONE_PREFIX = "synthetic:"


class SyntheticCaseActionBlocked(ValueError):
    pass


def parse_case_metadata(value: Any) -> dict:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (TypeError, ValueError):
            return {}
    return {}


def _explicit_true(value: Any) -> bool:
    return value is True or (isinstance(value, str) and value.strip().lower() == "true")


def is_synthetic_metadata(value: Any) -> bool:
    metadata = parse_case_metadata(value)
    return any(_explicit_true(metadata.get(flag)) for flag in PROVENANCE_FLAGS)


def is_synthetic_case(case: Mapping[str, Any] | None) -> bool:
    return bool(case) and is_synthetic_metadata(case.get("case_metadata"))


def is_synthetic_recipient(address: Any) -> bool:
    """True for the non-dialable sentinel contact used by synthetic_test_data rows."""
    return isinstance(address, str) and address.strip().lower().startswith(SYNTHETIC_PHONE_PREFIX)


def require_operational_case(case: Mapping[str, Any] | None, action: str) -> None:
    if is_synthetic_case(case):
        raise SyntheticCaseActionBlocked(
            f"Synthetic test cases cannot {action}."
        )


def sql_is_synthetic(alias: str = "c") -> str:
    """PostgreSQL predicate. ``alias`` is code-owned, never request-owned."""
    if not alias.replace("_", "").isalnum():
        raise ValueError("unsafe SQL alias")
    # ->> yields the text 'true' on PostgreSQL but the integer 1 on SQLite, so compare
    # the text form against both. A mismatch can only classify a row as synthetic
    # (hidden from live views), never the reverse.
    expressions = [
        f"LOWER(CAST(COALESCE({alias}.case_metadata->>'{flag}', 'false') AS TEXT)) IN ('true', '1')"
        for flag in PROVENANCE_FLAGS
    ]
    return "(" + " OR ".join(expressions) + ")"


def sql_is_live(alias: str = "c") -> str:
    return f"NOT {sql_is_synthetic(alias)}"


def append_data_scope_condition(conditions: list[str], scope: str, alias: str = "c") -> None:
    if scope == "live":
        conditions.append(sql_is_live(alias))
    elif scope == "test":
        conditions.append(sql_is_synthetic(alias))
    elif scope != "all":
        raise ValueError("data scope must be live, test, or all")
