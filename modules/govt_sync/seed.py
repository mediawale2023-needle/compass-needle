"""
modules/govt_sync/seed.py — Upserts govt_portals rows from the hand-curated
modules/data/govt_portals.json seed file into the database.

department_taxonomy and field_schema are treated as hand-verified data, not
something inferred at runtime — see field_schema.taxonomy_verified in the
seed file. Re-running this on every startup keeps the DB in sync with the
JSON file (which is what ops actually edits), without ever touching
per-case data (cases.govt_* columns are untouched by this seed).
"""
import json
import logging
import os

from sqlalchemy import text

logger = logging.getLogger("needle.govt_sync.seed")

_SEED_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "govt_portals.json")


def seed_govt_portals() -> int:
    from sansadx_backend.db import engine

    if not os.path.exists(_SEED_PATH):
        logger.warning(f"govt_portals seed file not found at {_SEED_PATH}")
        return 0

    with open(_SEED_PATH, "r", encoding="utf-8") as f:
        portals = json.load(f)

    count = 0
    with engine.begin() as conn:
        for p in portals:
            conn.execute(
                text("""
                    INSERT INTO govt_portals (
                        state, portal_name, portal_type, base_url, status_check_url,
                        status_check_mode, department_taxonomy, field_schema, otp_bound, active, is_primary,
                        verification_status, source_note
                    ) VALUES (
                        :state, :portal_name, :portal_type, :base_url, :status_check_url,
                        :status_check_mode, CAST(:department_taxonomy AS JSONB), CAST(:field_schema AS JSONB),
                        :otp_bound, :active, :is_primary, :verification_status, :source_note
                    )
                    ON CONFLICT (portal_name) DO UPDATE SET
                        state = EXCLUDED.state,
                        portal_type = EXCLUDED.portal_type,
                        base_url = EXCLUDED.base_url,
                        status_check_url = EXCLUDED.status_check_url,
                        status_check_mode = EXCLUDED.status_check_mode,
                        department_taxonomy = EXCLUDED.department_taxonomy,
                        field_schema = EXCLUDED.field_schema,
                        otp_bound = EXCLUDED.otp_bound,
                        verification_status = EXCLUDED.verification_status,
                        source_note = EXCLUDED.source_note
                        -- active/is_primary intentionally NOT overwritten on conflict — once a
                        -- portal row exists, enabled/primary is admin-managed operational state
                        -- (PATCH /admin/govt-portals/{id}), not something a reseed on every
                        -- startup should silently flip. verification_status/source_note are our
                        -- own research notes, not operational state, so those do stay in sync
                        -- with whatever's currently in the seed file.
                """),
                {
                    "state": p["state"],
                    "portal_name": p["portal_name"],
                    "portal_type": p.get("portal_type", "state_branded"),
                    "base_url": p.get("base_url"),
                    "status_check_url": p.get("status_check_url"),
                    "status_check_mode": p.get("status_check_mode", "login_required"),
                    "department_taxonomy": json.dumps(p.get("department_taxonomy", {})),
                    "field_schema": json.dumps(p.get("field_schema", {})),
                    "otp_bound": bool(p.get("otp_bound", True)),
                    "active": bool(p.get("active", True)),
                    "is_primary": bool(p.get("is_primary", True)),
                    "verification_status": p.get("verification_status", "unverified"),
                    "source_note": p.get("source_note"),
                },
            )
            count += 1
    return count
