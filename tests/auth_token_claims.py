"""Test tokens must carry the same identity claims as production login."""
from datetime import datetime, timezone
from sqlalchemy import text


def identity_claims(engine, username):
    with engine.connect() as conn:
        row = conn.execute(text("SELECT tenant_id, role FROM users WHERE username = :u"),
                           {"u": username}).mappings().one()
    return {"tid": int(row["tenant_id"] or 0), "role": row["role"],
            "iat": datetime.now(timezone.utc).timestamp()}
