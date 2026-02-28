"""
db.py — Compatibility shim.
All models and utilities now live in sansadx_backend/db.py.
This file re-exports everything so old imports still work.
"""
from sansadx_backend.db import (
    engine,
    SessionLocal,
    Base,
    init_db,
    hash_password,
    verify_password,
    get_db,
    Tenant,
    User,
    Case,
    TenantProfile,
    Archive,
    DNASample,
    ActivityHistory,
)