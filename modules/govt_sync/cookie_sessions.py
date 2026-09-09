"""Encrypted government-portal cookie session storage.

Tamil Nadu's authenticated status API accepts the same browser cookies a
staff member obtains by signing in normally. Those cookies are replayable
credentials, so this module is deliberately small and defensive:

* one Fernet key from GOVT_COOKIE_SESSION_KEY;
* encrypted cookie jar at rest;
* decrypted only inside this helper;
* tenant + portal scoped reads;
* no cookie values in logs, responses, tests, or audit payloads.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from cryptography.fernet import Fernet, InvalidToken


class CookieSessionKeyError(RuntimeError):
    """Encryption key is missing or invalid; callers must fail closed."""


class CookieSessionDecryptError(RuntimeError):
    """Stored cookie material could not be decrypted; callers must re-verify."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _fernet() -> Fernet:
    key = os.getenv("GOVT_COOKIE_SESSION_KEY", "").strip()
    if not key:
        raise CookieSessionKeyError("GOVT_COOKIE_SESSION_KEY is not configured")
    try:
        return Fernet(key.encode("ascii"))
    except Exception as exc:
        raise CookieSessionKeyError("GOVT_COOKIE_SESSION_KEY is invalid") from exc


def _json_expr(engine, bind_name: str) -> str:
    if getattr(getattr(engine, "dialect", None), "name", "") == "sqlite":
        return f":{bind_name}"
    return f"CAST(:{bind_name} AS JSONB)"


def _json_param(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _decode_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


def encrypt_cookie_jar(cookie_jar: list[dict]) -> str:
    payload = json.dumps(cookie_jar or [], sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return _fernet().encrypt(payload).decode("ascii")


def decrypt_cookie_jar(encrypted_cookie_jar: str) -> list[dict]:
    try:
        data = _fernet().decrypt((encrypted_cookie_jar or "").encode("ascii"))
    except InvalidToken as exc:
        raise CookieSessionDecryptError("Stored government portal session requires re-verification") from exc
    except CookieSessionKeyError:
        raise
    except Exception as exc:
        raise CookieSessionDecryptError("Stored government portal session requires re-verification") from exc
    decoded = json.loads(data.decode("utf-8"))
    return decoded if isinstance(decoded, list) else []


@dataclass
class CookieSession:
    id: int
    tenant_id: int
    portal_id: int
    cookie_jar: list[dict]
    ticket_mappings: dict[str, str]
    captured_at: datetime | None
    last_used_at: datetime | None
    last_auth_failed_at: datetime | None
    requires_verification: bool
    expires_at: datetime | None


def _row_to_session(row: dict) -> CookieSession:
    return CookieSession(
        id=row["id"],
        tenant_id=row["tenant_id"],
        portal_id=row["portal_id"],
        cookie_jar=decrypt_cookie_jar(row.get("encrypted_cookie_jar") or ""),
        ticket_mappings=_decode_json(row.get("ticket_mappings")) or {},
        captured_at=row.get("captured_at"),
        last_used_at=row.get("last_used_at"),
        last_auth_failed_at=row.get("last_auth_failed_at"),
        requires_verification=bool(row.get("requires_verification")),
        expires_at=row.get("expires_at"),
    )


def store_cookie_session(
    *,
    tenant_id: int,
    portal_id: int,
    cookie_jar: list[dict],
    ticket_mappings: dict[str, str] | None = None,
    expires_at: datetime | None = None,
) -> None:
    from sansadx_backend.db import engine
    from sqlalchemy import text

    encrypted = encrypt_cookie_jar(cookie_jar)
    mappings_expr = _json_expr(engine, "ticket_mappings")
    now = _utcnow()
    with engine.begin() as conn:
        conn.execute(
            text(
                f"""
                INSERT INTO govt_cookie_sessions (
                    tenant_id, portal_id, encrypted_cookie_jar, ticket_mappings,
                    captured_at, last_used_at, last_auth_failed_at,
                    requires_verification, expires_at, updated_at
                ) VALUES (
                    :tenant_id, :portal_id, :encrypted_cookie_jar, {mappings_expr},
                    :captured_at, NULL, NULL, false, :expires_at, :updated_at
                )
                ON CONFLICT (tenant_id, portal_id) DO UPDATE SET
                    encrypted_cookie_jar = EXCLUDED.encrypted_cookie_jar,
                    ticket_mappings = EXCLUDED.ticket_mappings,
                    captured_at = EXCLUDED.captured_at,
                    last_auth_failed_at = NULL,
                    requires_verification = false,
                    expires_at = EXCLUDED.expires_at,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "tenant_id": tenant_id,
                "portal_id": portal_id,
                "encrypted_cookie_jar": encrypted,
                "ticket_mappings": _json_param(ticket_mappings or {}),
                "captured_at": now,
                "expires_at": expires_at,
                "updated_at": now,
            },
        )


def load_cookie_session(tenant_id: int, portal_id: int) -> CookieSession | None:
    from core.db_helpers import _q_one

    row = _q_one(
        """
        SELECT id, tenant_id, portal_id, encrypted_cookie_jar, ticket_mappings,
               captured_at, last_used_at, last_auth_failed_at,
               requires_verification, expires_at
        FROM govt_cookie_sessions
        WHERE tenant_id = :tenant_id AND portal_id = :portal_id
        """,
        {"tenant_id": tenant_id, "portal_id": portal_id},
    )
    if not row or row.get("requires_verification"):
        return None
    return _row_to_session(dict(row))


def mark_cookie_session_used(tenant_id: int, portal_id: int) -> None:
    from sansadx_backend.db import engine
    from sqlalchemy import text

    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE govt_cookie_sessions SET last_used_at = :now, updated_at = :now "
                "WHERE tenant_id = :tenant_id AND portal_id = :portal_id"
            ),
            {"tenant_id": tenant_id, "portal_id": portal_id, "now": _utcnow()},
        )


def mark_cookie_session_auth_failed(tenant_id: int, portal_id: int) -> None:
    from sansadx_backend.db import engine
    from sqlalchemy import text

    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE govt_cookie_sessions SET last_auth_failed_at = :now, "
                "requires_verification = true, updated_at = :now "
                "WHERE tenant_id = :tenant_id AND portal_id = :portal_id"
            ),
            {"tenant_id": tenant_id, "portal_id": portal_id, "now": _utcnow()},
        )


def cookie_session_state(tenant_id: int, portal_id: int) -> dict:
    from core.db_helpers import _q_one

    row = _q_one(
        """
        SELECT captured_at, last_used_at, last_auth_failed_at, requires_verification, expires_at
        FROM govt_cookie_sessions
        WHERE tenant_id = :tenant_id AND portal_id = :portal_id
        """,
        {"tenant_id": tenant_id, "portal_id": portal_id},
    )
    if not row:
        return {"status": "not_started", "captured_at": None, "last_used_at": None, "last_auth_failed_at": None, "expires_at": None}
    status = "needs_verification" if row.get("requires_verification") else "verified"
    return {
        "status": status,
        "captured_at": row.get("captured_at"),
        "last_used_at": row.get("last_used_at"),
        "last_auth_failed_at": row.get("last_auth_failed_at"),
        "expires_at": row.get("expires_at"),
    }


def cookies_to_header(cookie_jar: list[dict], base_domain: str) -> str:
    host = (base_domain or "").lower()
    parts = []
    for cookie in cookie_jar or []:
        name = cookie.get("name")
        value = cookie.get("value")
        domain = str(cookie.get("domain") or "").lstrip(".").lower()
        if not name or value is None:
            continue
        if domain and host and not (host == domain or host.endswith("." + domain)):
            continue
        parts.append(f"{name}={value}")
    return "; ".join(parts)


def derive_cookie_expiry(cookie_jar: list[dict]) -> datetime | None:
    expiries = []
    for cookie in cookie_jar or []:
        exp = cookie.get("expires")
        try:
            exp_f = float(exp)
        except Exception:
            continue
        if exp_f > 0:
            expiries.append(exp_f)
    if not expiries:
        return None
    return datetime.fromtimestamp(min(expiries), tz=timezone.utc).replace(tzinfo=None)
