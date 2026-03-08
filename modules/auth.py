"""
Auth utilities — tenant isolation helpers.

get_tenant_or_fail() replaces the dangerous user.get('tenant_id', 1) pattern
that could silently default to tenant 1 if tenant_id is missing.
"""
from fastapi import HTTPException


def get_tenant_or_fail(user_data: dict) -> int:
    """Extract tenant_id from user data or raise 403.

    This MUST be used instead of user.get('tenant_id', 1) to prevent
    silent cross-tenant data leakage when tenant_id is missing or NULL.
    """
    tid = user_data.get("tenant_id")
    if tid is None:
        raise HTTPException(403, "No tenant assigned")
    return int(tid)
