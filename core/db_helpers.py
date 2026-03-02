"""
Shared database helper functions.
Used by api_router.py and admin_api.py.
"""
import json
from sqlalchemy import text
from sansadx_backend.db import engine


def _q(query: str, params: dict = None):
    with engine.connect() as conn:
        result = conn.execute(text(query), params or {})
        if result.returns_rows:
            return [dict(row._mapping) for row in result]
    return []


def _q_one(query: str, params: dict = None):
    rows = _q(query, params)
    return rows[0] if rows else None


def _parse_meta(meta):
    if meta is None:
        return {}
    if isinstance(meta, dict):
        return meta
    try:
        return json.loads(meta)
    except Exception:
        return {}
