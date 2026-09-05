"""
modules/govt_sync/status_attempts.py — Postgres-backed persistence for
InteractiveStatusCheckMixin attempts (currently Karnataka iPGRS and
Maharashtra Aaple Sarkar).

Replaces the process-local, in-memory `_attempts` dict each adapter used to
keep for itself. That dict required whichever worker called start() to be
the same worker that later received advance() — true only under
modules/govt_sync/browser_session.py's single-worker `backend_govt_live`
routing. Moving this state to `govt_status_check_attempts` removes that
requirement: any worker can read/write any attempt.

This module owns ONLY the persistence mechanics (create/load/update-stage/
delete). It knows nothing about CAPTCHA, OTP, cookies' meaning, or any
portal-specific protocol — that stays entirely inside each adapter, exactly
as before. Same separation of concerns as modules/govt_sync/otp_sessions.py
(the equivalent module for Rajasthan's govt_otp_sessions).

SECURITY: cookies/csrf_token/token/cid are short-lived, portal-issued
correlation state — the same sensitivity class already established for
Rajasthan's govt_otp_sessions.transaction_number/session_id. Never return
any of these four fields from an API response, never log them verbatim.
Callers should only ever surface attempt_id, stage, and whatever
CAPTCHA/OTP challenge the adapter itself constructs.

CONCURRENCY: update_attempt_stage() and delete_attempt() are single atomic
SQL statements (UPDATE/DELETE ... WHERE ... RETURNING), not a read-then-
write pair — so two near-simultaneous requests against the same attempt_id
can never both succeed. Exactly one statement affects a row; the other
affects zero rows and its caller treats that as "already consumed / not
found," matching the existing fail-closed behavior for an unknown attempt.
No explicit row lock or transaction spanning a government-portal HTTP call
is used or needed — the network call itself always happens outside any
transaction, same as before this module existed.

EXPIRY: lazy, via a bound cutoff timestamp in the WHERE clause of every
read/consume operation (never string-interpolated into SQL) — an attempt
older than its TTL is simply invisible to load_attempt(), identical in
effect to today's `_gc_expired()` dict-pruning. No background sweep is
introduced by this module; an abandoned row is left in place until some
future housekeeping pass, which is an accepted, deliberate limitation
matching the small-scale reality of this data (a handful of rows, each
existing for at most ~10 minutes).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _json_expr(engine, bind_name: str) -> str:
    if getattr(getattr(engine, "dialect", None), "name", "") == "sqlite":
        return f":{bind_name}"
    return f"CAST(:{bind_name} AS JSONB)"


def _decode_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


def _json_param(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def create_attempt(
    *,
    attempt_id: str,
    tenant_id: int,
    case_id: int,
    adapter_key: str,
    reference_number: str,
    mobile_or_email: str,
    cookies: dict,
    csrf_token: str | None = None,
    stage: int = 0,
    token: str | None = None,
    cid: str | None = None,
) -> None:
    """Creates a new attempt row. Mirrors start()'s `_attempts[attempt_id] = ...`."""
    from sansadx_backend.db import engine
    from sqlalchemy import text

    cookies_expr = _json_expr(engine, "cookies")
    now = _utcnow()
    with engine.begin() as conn:
        conn.execute(
            text(
                f"""
                INSERT INTO govt_status_check_attempts (
                    attempt_id, tenant_id, case_id, adapter_key, reference_number,
                    mobile_or_email, cookies, csrf_token, stage, token, cid,
                    created_at, last_activity_at
                ) VALUES (
                    :attempt_id, :tenant_id, :case_id, :adapter_key, :reference_number,
                    :mobile_or_email, {cookies_expr}, :csrf_token, :stage, :token, :cid,
                    :created_at, :last_activity_at
                )
                """
            ),
            {
                "attempt_id": attempt_id,
                "tenant_id": tenant_id,
                "case_id": case_id,
                "adapter_key": adapter_key,
                "reference_number": reference_number,
                "mobile_or_email": mobile_or_email,
                "cookies": _json_param(cookies),
                "csrf_token": csrf_token,
                "stage": stage,
                "token": token,
                "cid": cid,
                "created_at": now,
                "last_activity_at": now,
            },
        )


def load_attempt(attempt_id: str, tenant_id: int, case_id: int, ttl_seconds: int) -> dict | None:
    """Tenant/case/TTL-scoped read. A mismatched tenant/case, an unknown
    attempt_id, and a genuinely expired attempt all return None —
    indistinguishable from each other, exactly like today's in-memory
    `if not stored or stored.tenant_id != ... or stored.case_id != ...`."""
    from core.db_helpers import _q_one

    cutoff = _utcnow() - timedelta(seconds=ttl_seconds)
    row = _q_one(
        """
        SELECT attempt_id, tenant_id, case_id, adapter_key, reference_number,
               mobile_or_email, cookies, csrf_token, stage, token, cid,
               created_at, last_activity_at
        FROM govt_status_check_attempts
        WHERE attempt_id = :attempt_id AND tenant_id = :tenant_id AND case_id = :case_id
          AND last_activity_at > :cutoff
        """,
        {"attempt_id": attempt_id, "tenant_id": tenant_id, "case_id": case_id, "cutoff": cutoff},
    )
    if not row:
        return None
    row = dict(row)
    row["cookies"] = _decode_json(row.get("cookies")) or {}
    return row


def update_attempt_stage(
    attempt_id: str,
    *,
    expected_stage: int,
    stage: int,
    cookies: dict,
    csrf_token: str | None,
    token: str | None = None,
    cid: str | None = None,
) -> bool:
    """Atomically advances an attempt to the next stage, only if it is still
    at `expected_stage` — a concurrent duplicate advance() for the same
    attempt_id can only win this once; the loser's UPDATE affects zero rows.
    Returns True iff this call's UPDATE actually changed a row.
    Mirrors Maharashtra's in-place `stored.cookies = ...; stored.stage = ...`
    mutation, made atomic and worker-independent."""
    from sansadx_backend.db import engine
    from sqlalchemy import text

    cookies_expr = _json_expr(engine, "cookies")
    with engine.begin() as conn:
        result = conn.execute(
            text(
                f"""
                UPDATE govt_status_check_attempts
                SET cookies = {cookies_expr}, csrf_token = :csrf_token, stage = :stage,
                    token = COALESCE(:token, token), cid = COALESCE(:cid, cid),
                    last_activity_at = :now
                WHERE attempt_id = :attempt_id AND stage = :expected_stage
                RETURNING attempt_id
                """
            ),
            {
                "cookies": _json_param(cookies),
                "csrf_token": csrf_token,
                "stage": stage,
                "token": token,
                "cid": cid,
                "now": _utcnow(),
                "attempt_id": attempt_id,
                "expected_stage": expected_stage,
            },
        )
        return result.first() is not None


def delete_attempt(attempt_id: str) -> bool:
    """Atomically consumes (removes) an attempt — used on both success and
    failure, matching every `del _attempts[...]`/`_attempts.pop(...)` exit
    path in both adapters today. Returns True iff this call's DELETE
    actually removed a row, so a caller can tell "I consumed it" apart from
    "someone/something already had" (a concurrent duplicate request, or an
    attempt that already expired) — the latter should be treated the same
    as an unknown/expired attempt, never as a second success."""
    from sansadx_backend.db import engine
    from sqlalchemy import text

    with engine.begin() as conn:
        result = conn.execute(
            text("DELETE FROM govt_status_check_attempts WHERE attempt_id = :attempt_id RETURNING attempt_id"),
            {"attempt_id": attempt_id},
        )
        return result.first() is not None
