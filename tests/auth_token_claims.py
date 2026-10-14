"""Test tokens must carry the same identity claims as production login."""
from core.session_auth import credential_binding
from datetime import datetime, timezone
from sqlalchemy import text


def identity_claims(engine, username):
    with engine.connect() as conn:
        row = conn.execute(text("SELECT username, password_hash, tenant_id, role FROM users WHERE username = :u"),
                           {"u": username}).mappings().one()
    return {"credential_state": credential_binding(row), "tid": int(row["tenant_id"] or 0), "role": row["role"],
            "iat": datetime.now(timezone.utc).timestamp()}


def credential_claims(engine, username):
    """Only add the binding; retain each test's intentional identity/expiry claims."""
    with engine.connect() as conn:
        row = conn.execute(text("SELECT username, password_hash FROM users WHERE username = :u"),
                           {"u": username}).mappings().first()
    return {"credential_state": credential_binding(row) if row else "unknown-user"}
