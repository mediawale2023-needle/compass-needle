"""Shared, database-backed session checks for HTTP and WebSocket access."""
import math
import re
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import text


def utc_timestamp(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime):
        raise ValueError("Invalid session timestamp")
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.timestamp()


def token_revoked(query_one, username, issued_at):
    try:
        issued_at = float(issued_at)
        if not math.isfinite(issued_at) or issued_at <= 0:
            return True
        row = query_one(
            "SELECT revoked_at FROM token_blocklist WHERE username = :u ORDER BY revoked_at DESC LIMIT 1",
            {"u": username},
        )
        return bool(row and row.get("revoked_at") and issued_at <= utc_timestamp(row["revoked_at"]))
    except Exception:
        return True  # Missing/unreadable revocation state must fail closed.


def revoke_in_transaction(conn, username):
    conn.execute(text("INSERT INTO token_blocklist (username, revoked_at) VALUES (:u, :now)"),
                 {"u": username, "now": datetime.now(timezone.utc).replace(tzinfo=None)})


def require_active_account(query_one, user, *, require_tenant=True):
    # Legacy raw-SQL accounts have NULL is_active; preserve their existing login
    # contract. Both SQL booleans and SQLite integer FALSE must be rejected.
    if not user or user.get("is_active") in (False, 0):
        raise HTTPException(401, "Account unavailable. Please sign in again.")
    tid = user.get("tenant_id")
    if tid:
        tenant = query_one("SELECT id, is_active FROM tenants WHERE id = :tid", {"tid": tid})
        if not tenant or tenant.get("is_active") in (False, 0):
            raise HTTPException(401, "Account unavailable. Please sign in again.")
    elif require_tenant:
        raise HTTPException(403, "No tenant assigned")


def validate_session(query_one, payload, *, admin_roles=None):
    if admin_roles is not None and payload.get("role") not in admin_roles:
        raise HTTPException(403, "Admin access required")
    username = payload.get("sub")
    if not username or token_revoked(query_one, username, payload.get("iat")):
        raise HTTPException(401, "Session invalid. Please sign in again.")
    user = query_one("SELECT * FROM users WHERE username = :u", {"u": username})
    require_active_account(query_one, user, require_tenant=admin_roles is None)
    try:
        bound_tenant = int(payload["tid"] or 0) == int(user.get("tenant_id") or 0)
    except (KeyError, ValueError, TypeError):
        bound_tenant = False
    if not bound_tenant or payload.get("role") != user.get("role"):
        raise HTTPException(401, "Account authority changed. Please sign in again.")
    if admin_roles is not None and (user.get("role") not in admin_roles or payload.get("support_access")):
        raise HTTPException(403, "Admin access required")
    return user


# Support is deliberately limited to reviewed passive investigation routes.
# GET alone is insufficient: some legacy GET endpoints perform provider work.
SUPPORT_READ_PATHS = re.compile(
    r"/api/(?:auth/me|dashboard/(?:summary|overview)|cases(?:/\d+(?:/activity)?)?|profile|team|staff)\Z"
)


def validate_support(query_one, payload, user, method, path, admin_roles):
    row = query_one("SELECT * FROM support_access_requests WHERE request_key = :key",
                    {"key": payload.get("support_access_request_key")})
    try:
        valid = (
            row and row["status"] == "active"
            and row["target_username"] == user["username"]
            and int(row["tenant_id"]) == int(user["tenant_id"])
            and row.get("approved_by_username") == user["username"]
            and row.get("requested_by_admin_username") == payload.get("support_access_requested_by")
            and row.get("scope") == payload.get("support_access_scope") == "full_view"
            and not row.get("revoked_at") and not row.get("session_ended_at")
            and utc_timestamp(row["session_expires_at"]) > datetime.now(timezone.utc).timestamp()
            and row.get("launch_token_consumed_at")
        )
    except (KeyError, TypeError, ValueError):
        valid = False
    if not valid:
        raise HTTPException(401, "Support access has ended or is unavailable.")
    operator = query_one("SELECT * FROM users WHERE username = :u",
                         {"u": row["requested_by_admin_username"]})
    require_active_account(query_one, operator, require_tenant=False)
    # Bind revocation to the approval request as well as the issued token: an
    # operator logout racing with consumption must not mint a fresh capability.
    authorized_at = utc_timestamp(row["requested_at"])
    if (operator.get("role") not in admin_roles
            or token_revoked(query_one, operator["username"], authorized_at)
            or token_revoked(query_one, user["username"], authorized_at)):
        raise HTTPException(401, "Support operator access is unavailable.")
    if not ((method == "GET" and SUPPORT_READ_PATHS.fullmatch(path))
            or (method == "POST" and path == "/api/support-access/end")):
        raise HTTPException(403, "Support access is read-only; this action is unavailable.")
    return operator["username"]
