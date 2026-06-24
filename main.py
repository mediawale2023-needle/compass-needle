"""
main.py — Needle Parliamentary Intelligence Platform
Backend Entry Point (FastAPI)
"""
from sansadx_backend.ai_engine import ask_chatgpt_agent, detect_input_language, detect_input_language_confident, get_offensive_warning_reply
from sansadx_backend.unified_taxonomy import (
    build_taxonomy_fields,
    infer_personal_request_category,
    infer_silent_log_category,
)
import os
import re
import json
import hmac
import hashlib
import logging
import threading
import sentry_sdk
from difflib import SequenceMatcher
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, PlainTextResponse
from sqlalchemy import text
import requests as http_requests


def _utcnow():
    """Naive UTC timestamp for DB compatibility without deprecated utcnow()."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

# ─────────────────────────────────────────
# SECURITY CONFIG (optional — soft import)
# ─────────────────────────────────────────
try:
    from core.security_config import (
        ALLOWED_ORIGINS, CORS_ORIGIN_REGEX, SECURITY_HEADERS,
    )
except Exception:
    ALLOWED_ORIGINS = ["*"]
    CORS_ORIGIN_REGEX = None
    SECURITY_HEADERS = {}

# ─────────────────────────────────────────
# RATE LIMITING (optional — soft import)
# ─────────────────────────────────────────
try:
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from core.rate_limiter import limiter, RATE_WEBHOOK
    _rate_limiting_enabled = True
except Exception:
    _rate_limiting_enabled = False

# ─────────────────────────────────────────
# UNIFIED DB (single engine, single source)
# ─────────────────────────────────────────

# ─── Mandatory env var checks ───
META_APP_SECRET = os.getenv("META_APP_SECRET", "")
if not META_APP_SECRET:
    import sys
    logging.critical(
        "META_APP_SECRET is NOT set. WhatsApp webhook will reject ALL "
        "messages until it is configured. Get it from Meta App Dashboard → "
        "App Settings → Basic → App Secret."
    )


def _get_meta_app_secret() -> str:
    """Read the current webhook signing secret from env at request time."""
    return os.getenv("META_APP_SECRET", "") or META_APP_SECRET

from sansadx_backend.db import engine, init_db, get_phone_tenant_mapping, get_geo_overrides, get_tenant_phone_number_id, log_letterbox_activity

# ─────────────────────────────────────────
# GEOGRAPHY RESOLVER
# ─────────────────────────────────────────
try:
    from modules.geography_resolver import assembly_belongs_to_parliamentary, resolve_constituency, resolve_location
except ImportError:
    def resolve_constituency(text, tenant_id):
        return None, None
    def resolve_location(text, scope_parliamentary=None, tenant_id=None):
        return {"location_resolved": False}
    def assembly_belongs_to_parliamentary(assembly=None, parliamentary_constituency=None):
        return False

# ─────────────────────────────────────────
# SENTRY (optional monitoring)
# ─────────────────────────────────────────
sentry_dsn = os.getenv("SENTRY_DSN")
if sentry_dsn:
    sentry_sdk.init(
        dsn=sentry_dsn,
        traces_sample_rate=0.1,
        profiles_sample_rate=0.1,
    )

# ─────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("needle.backend")

# ─────────────────────────────────────────
# APP
# ─────────────────────────────────────────
app = FastAPI(title="Needle Backend", version="8.1")

# Rate limiter state
if _rate_limiting_enabled:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — use configured origins from security_config.
# For multi-tenant pilot we include known Railway frontends via ALLOWED_ORIGINS.
# Falls back to ["*"] only when ALLOWED_ORIGINS is not explicitly configured,
# which preserves backward-compatibility with existing single-MP deployments.
# Bearer token auth means CORS is defence-in-depth, not primary auth control.
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=CORS_ORIGIN_REGEX,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security headers middleware
if SECURITY_HEADERS:
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value
        return response

# ─────────────────────────────────────────
# API ROUTER (Next.js frontend endpoints)
# ─────────────────────────────────────────
from api_router import router as api_router
app.include_router(api_router, prefix="/api")

from admin_api import router as admin_router
app.include_router(admin_router, prefix="/api/admin")

# ─────────────────────────────────────────
# DATABASE INIT & MIGRATION LOCK
# ─────────────────────────────────────────
# Acquire a Postgres session-level advisory lock to prevent multiple
# Railway instances from running migrations concurrently.
#
# ⚠️  We use pg_TRY_advisory_lock (non-blocking) instead of pg_advisory_lock
# (blocking).  If a previous Railway instance crashed without releasing the lock
# (OOM kill, forced restart, SIGKILL), the lock stays held on the dead
# connection.  The blocking version would then hang here indefinitely — uvicorn
# never starts, the port never opens, and Railway reports "Connection timed out"
# on every request until the TCP keepalive timeout (~90s) finally clears the
# stale connection on the PostgreSQL side.
#
# With pg_try_advisory_lock:
#   - Returns TRUE  → lock acquired, proceed with migrations.
#   - Returns FALSE → another instance holds it (concurrent startup), skip
#     migrations here — they're all idempotent so this is safe.
import time as _time
from sqlalchemy import text as sa_text

# Retry connecting to Postgres at startup — Railway's internal network can take
# a few seconds to route the connection after a fresh deploy.
_startup_migration_lock_conn = None
_migration_lock_acquired = False
_DB_CONNECT_RETRIES = 10
_DB_CONNECT_DELAY   = 3   # seconds between attempts

for _attempt in range(1, _DB_CONNECT_RETRIES + 1):
    try:
        _startup_migration_lock_conn = engine.connect()
        _migration_lock_acquired = _startup_migration_lock_conn.execute(
            sa_text("SELECT pg_try_advisory_lock(77772024)")
        ).scalar()
        break
    except Exception as _conn_err:
        if _attempt < _DB_CONNECT_RETRIES:
            logger.warning(
                "DB connection attempt %d/%d failed: %s — retrying in %ds…",
                _attempt, _DB_CONNECT_RETRIES, _conn_err, _DB_CONNECT_DELAY,
            )
            _time.sleep(_DB_CONNECT_DELAY)
        else:
            logger.error(
                "DB unreachable after %d attempts (%s). Startup migrations will be skipped.",
                _DB_CONNECT_RETRIES, _conn_err,
            )

if _startup_migration_lock_conn is not None:
    if _migration_lock_acquired:
        logger.info("Acquired Postgres advisory lock (77772024) for safe startup migrations")
    else:
        logger.warning(
            "pg_try_advisory_lock(77772024) returned FALSE — another instance is running "
            "migrations concurrently.  Skipping migrations on this instance (all are idempotent)."
        )
else:
    logger.error("Skipping startup migrations — could not connect to Postgres after retries.")

try:
    init_db()
    logger.info("Database initialised.")
except Exception as _init_err:
    logger.error("init_db() failed (DB may be unreachable): %s", _init_err)

# ── Phase 1 Brain: ensure parliament answer-fetcher schema exists ─────────
# Creates prs_pdf_cache and adds question_pdf_url / real_question_number /
# answer_fetched_at / answer_fetch_status columns to parliamentary_questions.
# Also moves PDF URLs that earlier scraper runs stored inside question_text
# into the new question_pdf_url column.
try:
    from jobs.parliament_answer_fetcher import ensure_schema as _pq_ensure_schema, migrate_question_text_urls as _pq_migrate_urls
    _pq_ensure_schema()
    _moved = _pq_migrate_urls()
    if _moved:
        logger.info("Brain migration: moved %d question_text→question_pdf_url rows", _moved)
except Exception as _e:
    logger.warning("Brain schema migration skipped: %s", _e)

# ── Phase 2 Brain: ensure memory_chunks + pgvector ─────────────────────────
# Creates the unified semantic-memory store: memory_chunks (vector(1536))
# plus the pgvector extension and HNSW index. All chunks (PQs, debates,
# constituency profile, cases, schemes) are embedded with OpenAI text-
# embedding-3-small and queried by modules/brain_retriever.py.
try:
    from jobs.brain_indexer import ensure_schema as _brain_ensure_schema
    _brain_ensure_schema()
    logger.info("Brain schema (memory_chunks + pgvector) ensured.")
except Exception as _e:
    logger.warning("Brain schema setup skipped: %s", _e)

# On startup: seed DB from JSON files if present, purge deprecated generated
# geo_alias rows, and clean stale legacy generated geo_override rows. This is
# useful for first boot and maintenance, but expensive enough that production
# skips it unless explicitly enabled.
_run_geo_startup_sync = os.getenv("RUN_GEO_STARTUP_SYNC", "").lower() in {"1", "true", "yes"}
if os.getenv("ENV", "development") != "production":
    _run_geo_startup_sync = os.getenv("RUN_GEO_STARTUP_SYNC", "1").lower() in {"1", "true", "yes"}
try:
    if not _run_geo_startup_sync:
        logger.info("Geography startup sync skipped (set RUN_GEO_STARTUP_SYNC=true to enable).")
        raise RuntimeError("__skip_geo_startup_sync__")

    import pathlib as _pl
    from sansadx_backend.db import SessionLocal as _startup_SL, TenantOverride as _startup_TO, build_geography_key

    _sdb = _startup_SL()
    try:
        # ── Step 1: Seed DB from any JSON files present (idempotent) ─────────
        # Reads data/geography/<Constituency>/<Assembly>.json and upserts into DB.
        # On the very first deploy the files are in git; after that the DB is the
        # source of truth and the files are ephemeral.
        _geo_base = _pl.Path(__file__).parent / "data" / "geography"
        if _geo_base.exists():
            _seeded = 0
            for _parl_dir in sorted(_geo_base.iterdir()):
                if not _parl_dir.is_dir():
                    continue
                for _jf in sorted(_parl_dir.glob("*.json")):
                    _db_key = build_geography_key("mp", _parl_dir.name, _jf.stem)
                    # Only insert if not already in DB (don't overwrite admin edits)
                    _exists = _sdb.query(_startup_TO).filter(
                        _startup_TO.override_type == "geography_data",
                        _startup_TO.key == _db_key,
                    ).first()
                    if not _exists:
                        try:
                            _payload = _jf.read_text(encoding="utf-8")
                            _sdb.add(_startup_TO(
                                tenant_id=None,
                                override_type="geography_data",
                                key=_db_key,
                                value=_payload,
                            ))
                            _seeded += 1
                        except Exception:
                            pass
            if _seeded:
                _sdb.commit()
                logger.info(f"Geography startup: seeded {_seeded} new assembly files into DB")

    finally:
        _sdb.close()

    # ── Step 2: Purge deprecated generated geo_alias entries ──
    from modules.geography_resolver import auto_generate_overrides
    from sansadx_backend.db import cleanup_legacy_generated_geo_overrides
    _sync_result = auto_generate_overrides()
    logger.info(f"Geography alias purge result: {_sync_result}")
    _cleanup_result = cleanup_legacy_generated_geo_overrides()
    if _cleanup_result.get("deleted"):
        logger.info(
            "Geography startup cleanup removed %s legacy generated geo_override rows across %s tenants",
            _cleanup_result.get("deleted"),
            _cleanup_result.get("tenants"),
        )

except Exception as e:
    if str(e) != "__skip_geo_startup_sync__":
        logger.warning(f"Geography startup sync failed (non-critical): {e}")

# One-time production geography reset requested during the move to a
# manual-alias-only architecture. This wipes shared geography plus tenant-
# scoped geography helpers exactly once and records a DB marker so restarts do
# not repeat the delete.
_ONE_TIME_GEOGRAPHY_RESET_KEY = "manual-alias-reset-2026-06-05"
try:
    if os.getenv("ENV", "development").lower() == "production":
        from sansadx_backend.db import run_one_time_geography_reset

        _reset_result = run_one_time_geography_reset(_ONE_TIME_GEOGRAPHY_RESET_KEY)
        if _reset_result.get("applied"):
            logger.warning("One-time geography reset applied: %s", _reset_result.get("summary"))
        else:
            logger.info("One-time geography reset skipped: %s", _reset_result.get("reason"))
except Exception as e:
    logger.warning("One-time geography reset failed (non-critical): %s", e)

# ─── Migration: add tenant_id to archives table (idempotent) ───
try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE archives ADD COLUMN tenant_id INTEGER REFERENCES tenants(id)"))
        logger.info("Migration: added tenant_id column to archives table")
        # Backfill: set tenant_id from the users table.
        # ORDER BY created_at DESC ensures the most recent tenant association wins
        # if a user was ever re-assigned across tenants (prevents cross-tenant leak).
        conn.execute(text("""
            UPDATE archives SET tenant_id = (
                SELECT u.tenant_id FROM users u
                WHERE u.username = archives.user
                ORDER BY u.created_at DESC
                LIMIT 1
            ) WHERE tenant_id IS NULL
        """))
        logger.info("Migration: backfilled archives.tenant_id from users table")
except Exception:  # nosec B110 — idempotent migration; "column already exists" is expected
    pass

# ─── Migration: wa_message_dedup table (indexed webhook deduplication) ───
try:
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS wa_message_dedup (
                message_id   VARCHAR PRIMARY KEY,
                processed_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_wa_dedup_processed_at
            ON wa_message_dedup (processed_at)
        """))
        logger.info("Migration: wa_message_dedup table ready")
except Exception as e:
    logger.warning("wa_message_dedup migration skipped: %s", e)

# ─── Migration: durable inbound WhatsApp ledger ─────────────────────────────
try:
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS wa_inbound_messages (
                id SERIAL PRIMARY KEY,
                meta_message_id VARCHAR NOT NULL UNIQUE,
                tenant_id INTEGER REFERENCES tenants(id),
                sender_phone VARCHAR NOT NULL,
                receiver_number VARCHAR,
                message_type VARCHAR NOT NULL,
                status VARCHAR NOT NULL DEFAULT 'received',
                delivery_attempts INTEGER NOT NULL DEFAULT 1,
                retry_count INTEGER NOT NULL DEFAULT 0,
                case_id INTEGER REFERENCES cases(id),
                raw_payload TEXT NOT NULL,
                last_error TEXT,
                claimed_at TIMESTAMP,
                last_attempt_at TIMESTAMP,
                processed_at TIMESTAMP,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                last_received_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_wa_inbound_status_received
            ON wa_inbound_messages (status, last_received_at DESC)
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_wa_inbound_tenant_status
            ON wa_inbound_messages (tenant_id, status, created_at DESC)
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_wa_inbound_claimed_at
            ON wa_inbound_messages (claimed_at)
        """))
        logger.info("Migration: wa_inbound_messages table ready")
except Exception as e:
    logger.warning("wa_inbound_messages migration skipped: %s", e)

# ─── Startup: prune wa_message_dedup entries older than 30 days ───
# Meta never retries messages older than a few hours; 30 days is very conservative.
try:
    with engine.begin() as conn:
        _dedup_cutoff = _utcnow() - timedelta(days=30)
        _dedup_del = conn.execute(
            text("DELETE FROM wa_message_dedup WHERE processed_at < :cutoff"),
            {"cutoff": _dedup_cutoff},
        )
        if _dedup_del.rowcount:
            logger.info("Pruned %d stale wa_message_dedup entries", _dedup_del.rowcount)
except Exception as _dedup_prune_exc:
    logger.warning("wa_message_dedup prune failed (non-critical): %s", _dedup_prune_exc)

# ─── Startup: prune inbound WhatsApp ledger entries older than 45 days ──────
try:
    with engine.begin() as conn:
        _inbound_cutoff = _utcnow() - timedelta(days=45)
        _inbound_del = conn.execute(
            text("DELETE FROM wa_inbound_messages WHERE created_at < :cutoff"),
            {"cutoff": _inbound_cutoff},
        )
        if _inbound_del.rowcount:
            logger.info("Pruned %d stale wa_inbound_messages entries", _inbound_del.rowcount)
except Exception as _inbound_prune_exc:
    logger.warning("wa_inbound_messages prune failed (non-critical): %s", _inbound_prune_exc)

# ─── Migration: source media attachments for citizen WhatsApp cases ───
try:
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS case_media (
                id SERIAL PRIMARY KEY,
                tenant_id INTEGER NOT NULL REFERENCES tenants(id),
                case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                source VARCHAR NOT NULL DEFAULT 'whatsapp',
                media_type VARCHAR NOT NULL,
                mime_type VARCHAR NOT NULL,
                file_name VARCHAR,
                media_data BYTEA NOT NULL,
                caption TEXT,
                extracted_text TEXT,
                meta_message_id VARCHAR,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_case_media_case ON case_media (tenant_id, case_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_case_media_type ON case_media (media_type)"))
        logger.info("Migration: case_media table ready")
except Exception as _case_media_exc:
    logger.warning("case_media migration skipped: %s", _case_media_exc)

# ─── Migration: backfill is_deleted NULL → false on cases table ───
# Cases created before the is_deleted column existed have NULL, which causes
# is_deleted = false filters to miss them.  This one-time backfill is idempotent.
try:
    with engine.begin() as conn:
        _backfill = conn.execute(text("UPDATE cases SET is_deleted = false WHERE is_deleted IS NULL"))
        if _backfill.rowcount:
            logger.info("Migration: backfilled is_deleted NULL→false on %d cases", _backfill.rowcount)
except Exception as _bf_exc:
    logger.warning("is_deleted backfill failed (non-critical): %s", _bf_exc)

# ─── Migration: create token_blocklist table (idempotent) ───
try:
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS token_blocklist (
                id SERIAL PRIMARY KEY,
                username VARCHAR NOT NULL,
                revoked_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_token_blocklist_username
            ON token_blocklist (username)
        """))
        logger.info("Migration: token_blocklist table ready")
except Exception as e:
    logger.warning(f"token_blocklist migration skipped: {e}")

# ─── Migration: add missing columns to tenants table (idempotent) ───
for _col_sql in [
    "ALTER TABLE tenants ADD COLUMN tenant_type VARCHAR DEFAULT 'mp'",
    "ALTER TABLE tenants ADD COLUMN account_stage VARCHAR DEFAULT 'elected'",
    "ALTER TABLE tenants ADD COLUMN seat_type VARCHAR DEFAULT 'mp'",
    "ALTER TABLE tenants ADD COLUMN is_active BOOLEAN DEFAULT TRUE",
    "ALTER TABLE tenants ADD COLUMN onboarding_state JSON",
]:
    try:
        with engine.begin() as conn:
            conn.execute(text(_col_sql))
            logger.info(f"Migration: {_col_sql}")
    except Exception:  # nosec B110 — idempotent migration
        pass

# Backfill tenant_type for existing PR tenants
try:
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE tenants SET tenant_type = 'aspirant'
            WHERE tenant_type = 'mp'
              AND config::text LIKE '%"type": "PR"%'
        """))
except Exception:  # nosec B110 — idempotent migration
    pass

try:
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE tenants
            SET account_stage = CASE
                WHEN tenant_type = 'aspirant' THEN 'aspirant'
                ELSE 'elected'
            END
            WHERE account_stage IS NULL OR account_stage = ''
        """))
        conn.execute(text("""
            UPDATE tenants
            SET seat_type = CASE
                WHEN tenant_type = 'mla' THEN 'mla'
                ELSE 'mp'
            END
            WHERE seat_type IS NULL OR seat_type = ''
        """))
except Exception:  # nosec B110 — idempotent migration
    pass

# ─── Migration: add new columns for Phase 2-3 features (idempotent) ───
for _col_sql in [
    "ALTER TABLE cases ADD COLUMN assigned_to VARCHAR",
    "ALTER TABLE cases ADD COLUMN is_deleted BOOLEAN DEFAULT false",
    "ALTER TABLE cases ADD COLUMN deleted_at TIMESTAMP",
    "ALTER TABLE cases ADD COLUMN deleted_by VARCHAR",
    "ALTER TABLE cases ADD COLUMN case_ref VARCHAR",
]:
    try:
        with engine.begin() as conn:
            conn.execute(text(_col_sql))
            logger.info(f"Migration: {_col_sql}")
    except Exception:  # nosec B110 — idempotent migration
        pass

try:
    with engine.begin() as conn:
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_cases_case_ref ON cases (case_ref)"))
except Exception:  # nosec B110 — idempotent migration
    pass

# ─── Migration: add critical performance indexes (idempotent) ───
for _idx_sql in [
    "CREATE INDEX IF NOT EXISTS idx_cases_tenant_id ON cases (tenant_id)",
    "CREATE INDEX IF NOT EXISTS idx_cases_status ON cases (status)",
    "CREATE INDEX IF NOT EXISTS idx_cases_created_at ON cases (created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_cases_tenant_status ON cases (tenant_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_cases_tenant_created ON cases (tenant_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_cases_user_phone ON cases (user_phone)",
    # Per-contact lookups: dedup, contact-thread merge, daily rate limit, contact panel
    "CREATE INDEX IF NOT EXISTS idx_cases_tenant_phone_created ON cases (tenant_id, user_phone, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_cases_is_deleted ON cases (is_deleted)",
    "CREATE INDEX IF NOT EXISTS idx_spam_flags_tenant_phone ON spam_flags (tenant_id, phone)",
    "CREATE INDEX IF NOT EXISTS idx_token_blocklist_revoked_at ON token_blocklist (revoked_at)",
    # incident_clusters performance indexes
    "CREATE INDEX IF NOT EXISTS idx_incident_clusters_tenant ON incident_clusters (tenant_id)",
    "CREATE INDEX IF NOT EXISTS idx_incident_clusters_tenant_hazard ON incident_clusters (tenant_id, hazard_type)",
    "CREATE INDEX IF NOT EXISTS idx_incident_clusters_window ON incident_clusters (tenant_id, window_start DESC)",
    "CREATE INDEX IF NOT EXISTS idx_incident_clusters_level ON incident_clusters (alert_level)",
]:
    try:
        with engine.begin() as conn:
            conn.execute(text(_idx_sql))
    except Exception:  # nosec B110 — idempotent
        pass
logger.info("Performance indexes verified.")

# ─── Migration: retire legacy escalated case status ───
try:
    with engine.begin() as conn:
        result = conn.execute(
            text("UPDATE cases SET status = 'in_progress' WHERE status = 'escalated'")
        )
        if result.rowcount:
            logger.info("Migration: remapped legacy escalated cases to in_progress (rows updated: %d)", result.rowcount)
except Exception as e:
    logger.warning("legacy escalated-status remap skipped: %s", e)

# ─── Migration: create officers table (idempotent) ───
try:
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS officers (
                id SERIAL PRIMARY KEY,
                tenant_id INTEGER NOT NULL REFERENCES tenants(id),
                name VARCHAR NOT NULL,
                designation VARCHAR NOT NULL DEFAULT '',
                department VARCHAR DEFAULT '',
                email VARCHAR DEFAULT '',
                phone VARCHAR DEFAULT '',
                jurisdiction VARCHAR DEFAULT '',
                categories JSON,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_officers_tenant ON officers (tenant_id)"))
        logger.info("Migration: officers table ready")
except Exception as e:
    logger.warning(f"officers migration skipped: {e}")

# ─── Migration: create escalations table (idempotent) ───
try:
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS escalations (
                id SERIAL PRIMARY KEY,
                tenant_id INTEGER NOT NULL REFERENCES tenants(id),
                case_id INTEGER NOT NULL REFERENCES cases(id),
                officer_id INTEGER NOT NULL REFERENCES officers(id),
                letter_content TEXT DEFAULT '',
                deadline DATE,
                email_sent BOOLEAN DEFAULT FALSE,
                email_sent_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW(),
                created_by VARCHAR DEFAULT ''
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_escalations_case ON escalations (case_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_escalations_officer ON escalations (officer_id)"))
        logger.info("Migration: escalations table ready")
except Exception as e:
    logger.warning(f"escalations migration skipped: {e}")

# ─── Migration: backfill officers.is_active NULL → true ───
try:
    with engine.begin() as conn:
        result = conn.execute(text("UPDATE officers SET is_active = true WHERE is_active IS NULL"))
        logger.info(f"Migration: backfilled officers.is_active (rows updated: {result.rowcount})")
except Exception as e:
    logger.warning(f"officers backfill skipped: {e}")

# ─── Migration: add phone column to users table for PA WhatsApp identification ───
try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN phone VARCHAR"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_users_phone ON users (phone)"))
        logger.info("Migration: added phone column to users table")
except Exception:  # nosec B110 — idempotent migration
    pass

# ─── Migration: add new letterbox columns for digital dispatch intake system ───
for _col_sql in [
    "ALTER TABLE letterbox ADD COLUMN image_data BYTEA",
    "ALTER TABLE letterbox ADD COLUMN image_mime VARCHAR",
    "ALTER TABLE letterbox ADD COLUMN category VARCHAR",
    "ALTER TABLE letterbox ADD COLUMN ocr_text TEXT",
    "ALTER TABLE letterbox ADD COLUMN document_text TEXT",
    "ALTER TABLE letterbox ADD COLUMN diary_number VARCHAR",
    "ALTER TABLE letterbox ADD COLUMN source VARCHAR DEFAULT 'upload'",
    "ALTER TABLE letterbox ADD COLUMN sender_phone VARCHAR",
    "ALTER TABLE letterbox ADD COLUMN assigned_to VARCHAR",
    "ALTER TABLE letterbox ADD COLUMN date_of_letter DATE",
    "ALTER TABLE letterbox ADD COLUMN notes TEXT",
    "ALTER TABLE letterbox ADD COLUMN linked_letterbox_id INTEGER",
    "ALTER TABLE letterbox ADD COLUMN is_deleted BOOLEAN DEFAULT false",
]:
    try:
        with engine.begin() as conn:
            conn.execute(text(_col_sql))
            logger.info(f"Migration: {_col_sql}")
    except Exception:  # nosec B110 — idempotent migration
        pass

try:
    with engine.begin() as conn:
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS idx_letterbox_diary_number ON letterbox (diary_number) WHERE diary_number IS NOT NULL"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_letterbox_category ON letterbox (category)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_letterbox_source ON letterbox (source)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_letterbox_is_deleted ON letterbox (is_deleted)"))
        logger.info("Migration: letterbox indexes ready")
except Exception as e:
    logger.warning(f"Letterbox index migration skipped: {e}")

try:
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS letterbox_activity_log (
                id SERIAL PRIMARY KEY,
                tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                letterbox_id INTEGER NOT NULL REFERENCES letterbox(id) ON DELETE CASCADE,
                action_type VARCHAR(64) NOT NULL,
                actor_username VARCHAR(255),
                actor_channel VARCHAR(64) NOT NULL DEFAULT 'system',
                summary VARCHAR(500),
                details_json TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_letterbox_activity_letter ON letterbox_activity_log (letterbox_id, created_at DESC)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_letterbox_activity_tenant ON letterbox_activity_log (tenant_id, created_at DESC)"))
        logger.info("Migration: letterbox activity log ready")
except Exception as e:
    logger.warning(f"letterbox activity log migration skipped: {e}")

# ─── Migration: page_count column on letterbox ───
try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE letterbox ADD COLUMN page_count INTEGER DEFAULT 1"))
        logger.info("Migration: added page_count to letterbox")
except Exception:  # nosec B110 — idempotent
    pass

# ─── Migration: letterbox_pages table (stores pages 2+ of multi-page letters) ───
try:
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS letterbox_pages (
                id           SERIAL PRIMARY KEY,
                letterbox_id INTEGER NOT NULL REFERENCES letterbox(id) ON DELETE CASCADE,
                page_number  INTEGER NOT NULL,
                image_data   BYTEA   NOT NULL,
                image_mime   VARCHAR NOT NULL DEFAULT 'image/jpeg'
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_letterbox_pages_letter ON letterbox_pages (letterbox_id)"))
        logger.info("Migration: letterbox_pages table ready")
except Exception as e:
    logger.warning(f"letterbox_pages migration skipped: {e}")

# ─── Migration: letterbox_batches table (accumulates multi-page WhatsApp images) ───
try:
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS letterbox_batches (
                id              SERIAL PRIMARY KEY,
                tenant_id       INTEGER NOT NULL REFERENCES tenants(id),
                sender_phone    VARCHAR NOT NULL,
                receiver_number VARCHAR NOT NULL DEFAULT '',
                images          JSONB   NOT NULL DEFAULT '[]',
                direction_hint  VARCHAR,
                last_image_at   TIMESTAMP NOT NULL DEFAULT NOW(),
                status          VARCHAR NOT NULL DEFAULT 'pending',
                created_at      TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))
        conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_letterbox_batches_active
            ON letterbox_batches (sender_phone, tenant_id)
            WHERE status = 'pending'
        """))
        logger.info("Migration: letterbox_batches table ready")
except Exception as e:
    logger.warning(f"letterbox_batches migration skipped: {e}")

# ─── Migration: parliamentary data tables (18th Lok Sabha intelligence feed) ───
try:
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS parliamentary_questions (
                id              SERIAL PRIMARY KEY,
                tenant_id       INTEGER NOT NULL REFERENCES tenants(id),
                house           VARCHAR NOT NULL DEFAULT 'lok_sabha',
                session_name    VARCHAR NOT NULL,
                session_number  VARCHAR,
                question_number VARCHAR NOT NULL,
                question_type   VARCHAR NOT NULL,
                subject         VARCHAR,
                ministry        VARCHAR,
                question_text   TEXT,
                answer_text     TEXT,
                date_asked      DATE,
                scraped_at      TIMESTAMP NOT NULL DEFAULT NOW(),
                CONSTRAINT uq_pq_tenant_session_number_type
                    UNIQUE (tenant_id, session_name, question_number, question_type)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_pq_tenant ON parliamentary_questions (tenant_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_pq_tenant_session ON parliamentary_questions (tenant_id, session_name)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_pq_date ON parliamentary_questions (tenant_id, date_asked)"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS parliamentary_debates (
                id              SERIAL PRIMARY KEY,
                tenant_id       INTEGER NOT NULL REFERENCES tenants(id),
                house           VARCHAR NOT NULL DEFAULT 'lok_sabha',
                session_name    VARCHAR NOT NULL,
                date            DATE,
                topic           VARCHAR,
                bill_reference  VARCHAR,
                speech_excerpt  TEXT,
                full_speech_url VARCHAR,
                scraped_at      TIMESTAMP NOT NULL DEFAULT NOW(),
                CONSTRAINT uq_pd_tenant_session_date_topic
                    UNIQUE (tenant_id, session_name, date, topic)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_pd_tenant ON parliamentary_debates (tenant_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_pd_tenant_session ON parliamentary_debates (tenant_id, session_name)"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS private_members_bills (
                id              SERIAL PRIMARY KEY,
                tenant_id       INTEGER NOT NULL REFERENCES tenants(id),
                house           VARCHAR NOT NULL DEFAULT 'lok_sabha',
                session_name    VARCHAR NOT NULL,
                bill_number     VARCHAR NOT NULL,
                title           VARCHAR,
                subject         TEXT,
                date_introduced DATE,
                current_status  VARCHAR,
                bill_text_url   VARCHAR,
                scraped_at      TIMESTAMP NOT NULL DEFAULT NOW(),
                CONSTRAINT uq_pmb_tenant_session_bill
                    UNIQUE (tenant_id, session_name, bill_number)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_pmb_tenant ON private_members_bills (tenant_id)"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS zero_hour_submissions (
                id           SERIAL PRIMARY KEY,
                tenant_id    INTEGER NOT NULL REFERENCES tenants(id),
                house        VARCHAR NOT NULL DEFAULT 'lok_sabha',
                session_name VARCHAR NOT NULL,
                date         DATE,
                subject      VARCHAR,
                text_excerpt TEXT,
                scraped_at   TIMESTAMP NOT NULL DEFAULT NOW(),
                CONSTRAINT uq_zh_tenant_session_date_subject
                    UNIQUE (tenant_id, session_name, date, subject)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_zh_tenant ON zero_hour_submissions (tenant_id)"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS parliament_backfill_jobs (
                id              SERIAL PRIMARY KEY,
                tenant_id       INTEGER NOT NULL REFERENCES tenants(id),
                session_name    VARCHAR NOT NULL,
                data_type       VARCHAR NOT NULL,
                status          VARCHAR NOT NULL DEFAULT 'pending',
                records_fetched INTEGER NOT NULL DEFAULT 0,
                error_message   TEXT,
                started_at      TIMESTAMP,
                completed_at    TIMESTAMP,
                created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
                CONSTRAINT uq_pbj_tenant_session_type
                    UNIQUE (tenant_id, session_name, data_type)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_pbj_tenant ON parliament_backfill_jobs (tenant_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_pbj_status ON parliament_backfill_jobs (status)"))

        logger.info("Migration: parliamentary data tables ready")
except Exception as e:
    logger.warning(f"Parliamentary tables migration skipped: {e}")

# ── Scheme Intelligence tables ────────────────────────────────────────────────
try:
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS prs_schemes (
                id              SERIAL PRIMARY KEY,
                name            VARCHAR(300) NOT NULL,
                full_name       VARCHAR(500),
                ministry        VARCHAR(300),
                aliases         TEXT[]       DEFAULT '{}',
                first_seen      DATE,
                last_seen       DATE,
                answer_count    INTEGER      DEFAULT 0,
                created_at      TIMESTAMP    DEFAULT NOW(),
                updated_at      TIMESTAMP    DEFAULT NOW(),
                UNIQUE(name)
            )
        """))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_prs_schemes_ministry ON prs_schemes (LOWER(ministry))"
        ))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS scheme_intelligence_cache (
                id              SERIAL PRIMARY KEY,
                scheme_name     VARCHAR(300) NOT NULL UNIQUE,
                ministry        VARCHAR(300),
                structured_intel JSONB,
                generated_at    TIMESTAMP,
                pq_count_at_gen INTEGER      DEFAULT 0,
                is_stale        BOOLEAN      DEFAULT false,
                error           TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS scheme_mentions (
                id              SERIAL PRIMARY KEY,
                pq_id           BIGINT NOT NULL REFERENCES global_parliamentary_questions(id) ON DELETE CASCADE,
                scheme_id       INTEGER NOT NULL REFERENCES prs_schemes(id) ON DELETE CASCADE,
                matched_text    VARCHAR(500),
                source          VARCHAR(20) NOT NULL DEFAULT 'rule',
                confidence      NUMERIC(4, 3) NOT NULL DEFAULT 1.0,
                created_at      TIMESTAMP DEFAULT NOW(),
                UNIQUE (pq_id, scheme_id)
            )
        """))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_scheme_mentions_scheme ON scheme_mentions (scheme_id)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_scheme_mentions_pq ON scheme_mentions (pq_id)"
        ))
    logger.info("Migration: prs_schemes + scheme_intelligence_cache ready")
except Exception as e:
    logger.warning(f"Scheme intelligence tables migration skipped: {e}")

# Migration: state-aware scheme intelligence cache (per-state briefs)
try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE scheme_intelligence_cache ADD COLUMN IF NOT EXISTS state VARCHAR(100) NOT NULL DEFAULT ''"))
        conn.execute(text("ALTER TABLE scheme_intelligence_cache DROP CONSTRAINT IF EXISTS scheme_intelligence_cache_scheme_name_key"))
        conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'sic_scheme_state_uq'
                ) THEN
                    ALTER TABLE scheme_intelligence_cache
                    ADD CONSTRAINT sic_scheme_state_uq UNIQUE (scheme_name, state);
                END IF;
            END$$
        """))
    logger.info("Migration: scheme_intelligence_cache state column ready")
    if os.getenv("MARK_SCHEME_BRIEFS_STALE_ON_STARTUP", "").lower() in {"1", "true", "yes"}:
        # One-off maintenance switch for regenerating scheme briefs after format changes.
        with engine.begin() as conn:
            conn.execute(text("UPDATE scheme_intelligence_cache SET is_stale = true WHERE structured_intel IS NOT NULL AND is_stale = false"))
        logger.info("Migration: existing scheme briefs marked stale for regeneration")
except Exception as e:
    logger.warning(f"scheme_intelligence_cache state migration skipped: {e}")

# Migration: prs_profile_slug on tenants (PRS India identity for data scraping)
try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS prs_profile_slug VARCHAR(200)"))
    logger.info("Migration: tenants.prs_profile_slug ready")
except Exception as e:
    logger.warning(f"prs_profile_slug migration skipped: {e}")

# Migration: SansadAI issue intelligence cache (ministry + topic + state)
try:
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS issue_intelligence_cache (
                id               SERIAL PRIMARY KEY,
                ministry         VARCHAR(300) NOT NULL,
                topic            VARCHAR(120) NOT NULL,
                state            VARCHAR(100) NOT NULL DEFAULT '',
                structured_intel JSONB,
                generated_at     TIMESTAMP,
                pq_count_at_gen  INTEGER DEFAULT 0,
                is_stale         BOOLEAN DEFAULT false,
                error            TEXT,
                created_at       TIMESTAMP DEFAULT NOW(),
                UNIQUE (ministry, topic, state)
            )
        """))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_issue_intel_ministry_topic ON issue_intelligence_cache (LOWER(ministry), topic)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_issue_intel_state ON issue_intelligence_cache (state)"
        ))
    logger.info("Migration: issue_intelligence_cache ready")
except Exception as e:
    logger.warning(f"SansadAI issue intelligence cache migration skipped: {e}")

# Migration: topic column on global_parliamentary_questions for fixed 12-topic taxonomy
try:
    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE global_parliamentary_questions ADD COLUMN IF NOT EXISTS topic VARCHAR(60)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_gpq_topic ON global_parliamentary_questions (topic) "
            "WHERE topic IS NOT NULL"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_gpq_ministry_topic ON global_parliamentary_questions "
            "(LOWER(ministry), topic) WHERE topic IS NOT NULL"
        ))
    logger.info("Migration: global_parliamentary_questions.topic column ready")
except Exception as e:
    logger.warning(f"global_parliamentary_questions topic migration skipped: {e}")

# Seed CSR company profiles from static JSON files when explicitly requested.
try:
    _seed_csr_on_startup = os.getenv("SEED_CSR_ON_STARTUP", "").lower() in {"1", "true", "yes"}
    if os.getenv("ENV", "development") != "production":
        _seed_csr_on_startup = os.getenv("SEED_CSR_ON_STARTUP", "1").lower() in {"1", "true", "yes"}
    if _seed_csr_on_startup:
        from modules.csr_data_loader import seed_csr_companies
        seed_csr_companies()
    else:
        logger.info("CSR company seed skipped (set SEED_CSR_ON_STARTUP=true to enable).")
except Exception as _csr_seed_err:
    logger.warning(f"CSR company seed failed (non-fatal): {_csr_seed_err}")


# ─────────────────────────────────────────
# EMERGENCY ESCALATION BACKGROUND CHECKER
# ─────────────────────────────────────────
# Runs every 5 minutes. Promotes T2 clusters to T3 when the PA has not
# acknowledged within the configured escalation_wait_minutes window.
def _run_escalation_check():
    """
    Fix 7: wrapped in pg_try_advisory_xact_lock so only one Railway instance
    runs the escalation check at a time. Lock is transaction-scoped and
    released automatically when the engine.begin() block exits — no
    risk of stale lock after crash or connection pool recycling.
    Lock ID 77772025 (distinct from startup migration lock 77772024).
    """
    try:
        from modules.emergency_intake import escalate_pending_clusters
        if engine.dialect.name == "postgresql":
            with engine.begin() as _esc_conn:
                _lock_acquired = _esc_conn.execute(
                    sa_text("SELECT pg_try_advisory_xact_lock(77772025)")
                ).scalar()
                if not _lock_acquired:
                    logger.info(
                        "Skipping emergency escalation cycle — another instance holds advisory lock 77772025"
                    )
                    return
                escalate_pending_clusters()
        else:
            escalate_pending_clusters()
    except Exception as _esc_exc:
        logger.warning("Escalation check error (non-blocking): %s", _esc_exc)
    finally:
        t = threading.Timer(300, _run_escalation_check)
        t.daemon = True
        t.start()

_escalation_timer = threading.Timer(300, _run_escalation_check)
_escalation_timer.daemon = True
_escalation_timer.start()
logger.info("Emergency escalation checker started (interval: 5 min)")


# ─────────────────────────────────────────
# MORNING DIGEST ENDPOINT
# ─────────────────────────────────────────
@app.post("/internal/morning-digest")
async def trigger_morning_digest(request: Request):
    """
    Trigger the T0 morning digest manually or via Railway cron.

    Fix 8: DIGEST_TOKEN is now mandatory. If the env var is not set the
    endpoint returns 503 rather than accepting unauthenticated calls,
    preventing the endpoint from being used to spam all tenant PAs.
    Set DIGEST_TOKEN to a random secret and pass it as X-Digest-Token.
    """
    _digest_token = os.getenv("DIGEST_TOKEN", "").strip()
    if not _digest_token:
        raise HTTPException(status_code=503, detail="DIGEST_TOKEN is not configured")
    provided = request.headers.get("X-Digest-Token", "")
    if not provided or provided != _digest_token:
        raise HTTPException(status_code=403, detail="Invalid digest token")
    try:
        from jobs.t0_morning_digest import run_morning_digest
        result = run_morning_digest()
        return {"ok": True, "result": result}
    except Exception as exc:
        logger.error("Morning digest endpoint error: %s", exc)
        raise HTTPException(status_code=500, detail="Digest failed")


# ─────────────────────────────────────────
# SPAM & ABUSE DETECTION
# ─────────────────────────────────────────
# Keyword list covers English threats + transliterated Hindi/Marathi/Kannada abuse.
# All matching is done on lowercase normalised text so "KILL" == "kill".
_ABUSE_KEYWORDS = [
    # English — threats and explicit abuse
    "i will kill", "i'll kill", "going to kill", "will shoot", "will bomb",
    "death threat", "kill you", "kill him", "kill her", "kill them",
    "bomb blast", "blow up", "terrorist attack", "suicide bomb",
    "rape you", "rape her", "will rape",
    # English — generic hate/slurs (kept to severe cases to minimise false positives)
    "fuck you", "motherfucker", "son of a bitch",
    # Transliterated Hindi/Marathi/Kannada (common severe abuse)
    "madarchod", "maderchod", "bhen chod", "behenchod", "bhenchod",
    "chutiya", "chutiye", "bhosadike", "bhosadi", "gandu", "ganduon",
    "randi", "haramzada", "haramkhor", "kutiya", "harami",
    "mc bc", "bc mc",
]

# Coordinated flood: 20+ unique phones, identical fingerprint, within 60 min
_FLOOD_WINDOW_MINUTES = 60
_FLOOD_THRESHOLD = 20
_FLOOD_FINGERPRINT_LEN = 60     # chars of normalised text used for matching
_FLOOD_MIN_MESSAGE_LEN = 20    # messages shorter than this are too vague to match
_CONTACT_BUFFER_WINDOW_HOURS = 24
_CONTACT_THREAD_HIGH_FREQUENCY_DISTINCT = 6
_CONTACT_THREAD_SPAM_SUSPECTED_DISTINCT = 10
_CONTACT_BUFFER_STATUS = "contact_buffered"
_CONTACT_BUFFER_SIMILARITY = 0.9
# Tiered follow-up thresholds: citizens who send messages quickly are more
# likely continuing a conversation than filing an unrelated complaint.
_FOLLOWUP_SIMILARITY_SHORT_WINDOW = 0.55   # within 30 min
_FOLLOWUP_SIMILARITY_MEDIUM_WINDOW = 0.70  # within 2 h
_FOLLOWUP_SHORT_WINDOW_MINUTES = 30
_FOLLOWUP_MEDIUM_WINDOW_HOURS = 2
_LOW_INFORMATION_FOLLOWUPS = {
    "hello",
    "hi",
    "hello?",
    "hi?",
    "reply",
    "please reply",
    "pls reply",
    "plz reply",
    "any update",
    "update",
    "status",
    "what happened",
    "kya hua",
}
_contact_buffer_release_timers: dict[int, threading.Timer] = {}
_contact_buffer_release_lock = threading.Lock()

# Test/QA phone numbers exempt from frequency-based spam gates (content dedup,
# coordinated-flood, per-phone daily rate limit). Content-based abuse detection
# still applies. Seeded with a built-in default and extended via the
# SPAM_EXEMPT_NUMBERS env var (comma-separated bare numbers, e.g.
# "9650787758,9123456789"); non-digit characters and country-code prefixes are
# ignored when matching.
_SPAM_EXEMPT_DEFAULTS = {"9650787758"}
_SPAM_EXEMPT_NUMBERS = _SPAM_EXEMPT_DEFAULTS | {
    re.sub(r"\D", "", n)
    for n in os.getenv("SPAM_EXEMPT_NUMBERS", "").split(",")
    if re.sub(r"\D", "", n)
}


def _is_spam_exempt(phone: str) -> bool:
    """True if this phone is allowlisted from frequency-based spam checks."""
    digits = re.sub(r"\D", "", phone or "")
    return any(digits.endswith(n) for n in _SPAM_EXEMPT_NUMBERS)


def _normalise(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _contact_issue_fingerprint(text: str) -> str:
    return _normalise(text or "")[:240]


def _contact_thread_state_for_count(distinct_issue_count: int) -> str:
    if distinct_issue_count >= _CONTACT_THREAD_SPAM_SUSPECTED_DISTINCT:
        return "spam_suspected"
    if distinct_issue_count >= _CONTACT_THREAD_HIGH_FREQUENCY_DISTINCT:
        return "high_frequency"
    if distinct_issue_count > 1:
        return "valid_multi_issue"
    return "normal"


def _count_contact_thread_messages(meta: dict | None) -> int:
    payload = dict(meta or {})
    total = len(payload.get("contact_message_events") or [])
    for item in payload.get("contact_thread_items") or []:
        total += 1
        total += len(item.get("contact_message_events") or [])
    return total + 1


def _update_contact_thread_meta(
    meta: dict | None,
    *,
    distinct_issue_count: int | None = None,
    last_activity_at: str | None = None,
) -> dict:
    updated = dict(meta or {})
    if distinct_issue_count is None:
        distinct_issue_count = 1 + len(updated.get("contact_thread_items") or [])
    state = _contact_thread_state_for_count(int(distinct_issue_count))
    updated["distinct_issue_count"] = int(distinct_issue_count)
    updated["contact_thread_state"] = state
    updated["contact_thread_last_activity_at"] = last_activity_at or _utcnow().isoformat()
    updated["contact_thread_message_count"] = _count_contact_thread_messages(updated)
    return updated


def _is_low_information_followup(text: str) -> bool:
    normalised = _normalise(text or "")
    if not normalised:
        return True
    if normalised in _LOW_INFORMATION_FOLLOWUPS:
        return True
    if len(normalised) <= 12 and all(tok in {"hi", "hello", "reply", "update", "pls", "plz", "please"} for tok in normalised.split()):
        return True
    return False


def _message_similarity(left: str, right: str) -> float:
    left_norm = _contact_issue_fingerprint(left)
    right_norm = _contact_issue_fingerprint(right)
    if not left_norm or not right_norm:
        return 0.0
    if left_norm == right_norm:
        return 1.0
    if left_norm in right_norm or right_norm in left_norm:
        shorter = min(len(left_norm), len(right_norm))
        longer = max(len(left_norm), len(right_norm))
        if longer > 0 and shorter / longer >= 0.72:
            return 0.96
    return SequenceMatcher(None, left_norm, right_norm).ratio()


def _parse_case_meta(meta_value):
    if isinstance(meta_value, dict):
        return dict(meta_value)
    try:
        return json.loads(meta_value or "{}")
    except Exception:
        return {}


def _append_contact_message_event(case_id: int, message_body: str, *, event_type: str, detected_language: str = "") -> None:
    event_created_at = _utcnow().isoformat()
    event = {
        "message": (message_body or "").strip()[:2000],
        "event_type": event_type,
        "created_at": event_created_at,
    }
    if detected_language:
        event["detected_language"] = detected_language

    try:
        with engine.begin() as conn:
            row = conn.execute(
                text("SELECT case_metadata FROM cases WHERE id = :cid"),
                {"cid": case_id},
            ).fetchone()
            if not row:
                return
            meta = _parse_case_meta(row[0])
            events = list(meta.get("contact_message_events") or [])
            events.append(event)
            meta["contact_message_events"] = events[-25:]
            meta["contact_last_message_at"] = event["created_at"]
            meta = _update_contact_thread_meta(meta, last_activity_at=event_created_at)
            conn.execute(
                text("UPDATE cases SET case_metadata = :meta, updated_at = :now WHERE id = :cid"),
                {"meta": json.dumps(meta), "now": _utcnow(), "cid": case_id},
            )
    except Exception as exc:
        logger.warning("Failed to append contact message event for case %s: %s", case_id, exc)


def _iso_or_now(value) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    text_value = str(value or "").strip()
    return text_value or _utcnow().isoformat()


def _thread_issue_from_row(row: dict) -> dict:
    meta = _parse_case_meta(row.get("case_metadata"))
    return {
        "issue_id": str(meta.get("thread_issue_id") or f"case-{row.get('id')}-root"),
        "raw_message": row.get("raw_message") or "",
        "category": row.get("category") or meta.get("problem_domain") or "Uncategorised",
        "problem_domain": row.get("problem_domain") or meta.get("problem_domain"),
        "problem_subdomain": row.get("problem_subdomain") or meta.get("problem_subdomain"),
        "convergence_program_type": row.get("convergence_program_type") or meta.get("convergence_program_type"),
        "status": row.get("status") or "new",
        "matched_value": meta.get("matched_value") or "",
        "assembly_constituency": meta.get("assembly_constituency") or "",
        "detected_language": meta.get("detected_language") or meta.get("language") or "",
        "summary": meta.get("summary") or "",
        "thread_state": meta.get("contact_thread_state") or "normal",
        "created_at": str(meta.get("thread_issue_created_at") or _iso_or_now(row.get("created_at"))),
        "last_message_at": str(meta.get("thread_issue_last_message_at") or _iso_or_now(row.get("updated_at") or row.get("created_at"))),
        "contact_message_events": list(meta.get("contact_message_events") or []),
    }


def _thread_issue_similarity(message_body: str, issue: dict | None) -> float:
    if not issue:
        return 0.0
    best = _message_similarity(message_body, issue.get("raw_message") or "")
    for event in issue.get("contact_message_events") or []:
        best = max(best, _message_similarity(message_body, event.get("message") or ""))
    return best


def _contact_thread_id_from_row(row: dict | None) -> str:
    row = dict(row or {})
    meta = _parse_case_meta(row.get("case_metadata"))
    thread_id = str(meta.get("contact_thread_id") or "").strip()
    if thread_id:
        return thread_id
    return f"legacy-case-{row.get('id')}"


def _contact_thread_started_at_from_row(row: dict | None) -> str:
    row = dict(row or {})
    meta = _parse_case_meta(row.get("case_metadata"))
    return str(meta.get("contact_thread_started_at") or _iso_or_now(row.get("created_at")))


def _thread_sort_timestamp(row: dict | None) -> datetime:
    row = dict(row or {})
    value = row.get("updated_at") or row.get("created_at") or _utcnow()
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return _utcnow()


def _recent_contact_thread_cases(phone: str, tenant_id: int, *, now: datetime | None = None) -> list[dict]:
    now = now or _utcnow()
    cutoff = now - timedelta(hours=_CONTACT_BUFFER_WINDOW_HOURS)
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT id, category, status, raw_message, created_at, updated_at, case_metadata,
                           problem_domain, problem_subdomain, convergence_program_type, location, assembly
                    FROM cases
                    WHERE tenant_id = :tid
                      AND user_phone = :phone
                      AND created_at >= :cutoff
                      AND (is_deleted = false OR is_deleted IS NULL)
                      AND COALESCE(status, '') != :buffer_status
                      AND COALESCE(category, '') NOT IN ('Spam', 'Spam (Offensive)')
                      AND COALESCE(status, '') NOT IN ('offensive', 'closed')
                    ORDER BY COALESCE(updated_at, created_at) DESC, id DESC
                    """
                ),
                {"tid": tenant_id, "phone": phone, "cutoff": cutoff, "buffer_status": _CONTACT_BUFFER_STATUS},
            ).mappings().all()
        return [dict(row) for row in rows]
    except Exception as exc:
        logger.warning("Recent contact-window lookup failed for %s/%s: %s", tenant_id, phone, exc)
        return []


def _group_recent_contact_thread_cases(rows: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for row in rows or []:
        grouped.setdefault(_contact_thread_id_from_row(row), []).append(dict(row))
    groups = []
    for thread_id, cases in grouped.items():
        cases_sorted = sorted(cases, key=_thread_sort_timestamp, reverse=True)
        groups.append(
            {
                "thread_id": thread_id,
                "cases": cases_sorted,
                "latest_case": cases_sorted[0] if cases_sorted else None,
            }
        )
    groups.sort(key=lambda item: _thread_sort_timestamp(item.get("latest_case")), reverse=True)
    return groups


def _aggregate_contact_thread_distinct_count(cases: list[dict]) -> int:
    if not cases:
        return 0
    distinct = len(cases)
    max_meta_count = distinct
    for case in cases:
        meta = _parse_case_meta(case.get("case_metadata"))
        max_meta_count = max(max_meta_count, int(meta.get("distinct_issue_count") or 0))
        max_meta_count = max(max_meta_count, len(cases) + len(meta.get("contact_thread_spam_messages") or []))
    return max_meta_count


def _collect_contact_thread_spam_messages(cases: list[dict]) -> list[dict]:
    messages = []
    for case in cases or []:
        meta = _parse_case_meta(case.get("case_metadata"))
        for item in meta.get("contact_thread_spam_messages") or []:
            if item:
                messages.append(dict(item))
    messages.sort(key=lambda item: str(item.get("created_at") or ""))
    return messages[-25:]


def _set_contact_thread_state_on_meta(
    meta: dict | None,
    *,
    thread_id: str,
    thread_started_at: str,
    distinct_issue_count: int,
    last_activity_at: str | None = None,
) -> dict:
    updated = dict(meta or {})
    updated["contact_thread_id"] = thread_id
    updated["contact_thread_started_at"] = thread_started_at
    updated["contact_thread_anchor_case_id"] = updated.get("contact_thread_anchor_case_id")
    return _update_contact_thread_meta(
        updated,
        distinct_issue_count=distinct_issue_count,
        last_activity_at=last_activity_at,
    )


def _apply_contact_thread_group_state(
    cases: list[dict],
    *,
    thread_id: str,
    thread_started_at: str,
    distinct_issue_count: int,
    last_activity_at: str | None = None,
) -> None:
    if not cases:
        return
    try:
        with engine.begin() as conn:
            for case in cases:
                meta = _parse_case_meta(case.get("case_metadata"))
                meta = _set_contact_thread_state_on_meta(
                    meta,
                    thread_id=thread_id,
                    thread_started_at=thread_started_at,
                    distinct_issue_count=distinct_issue_count,
                    last_activity_at=last_activity_at,
                )
                conn.execute(
                    text("UPDATE cases SET case_metadata = :meta WHERE id = :cid"),
                    {"meta": json.dumps(meta), "cid": case["id"]},
                )
    except Exception as exc:
        logger.warning("Failed to update contact thread state for %s: %s", thread_id, exc)


def _mark_contact_thread_spam_suppressed(
    case_row: dict,
    *,
    message_body: str,
    language_hint: str,
    projected_distinct_count: int,
) -> None:
    meta = _parse_case_meta(case_row.get("case_metadata"))
    now_iso = _utcnow().isoformat()
    spam_messages = list(meta.get("contact_thread_spam_messages") or [])
    spam_messages.append(
        {
            "message": (message_body or "").strip()[:500],
            "created_at": now_iso,
            **({"detected_language": language_hint} if language_hint else {}),
        }
    )
    meta["contact_thread_spam_messages"] = spam_messages[-10:]
    meta["contact_thread_overflow_count"] = int(meta.get("contact_thread_overflow_count") or 0) + 1
    meta["contact_thread_spam_flagged"] = True
    meta["contact_thread_last_overflow_at"] = now_iso
    meta["contact_intake_action"] = "spam_suspected"
    meta = _set_contact_thread_state_on_meta(
        meta,
        thread_id=_contact_thread_id_from_row(case_row),
        thread_started_at=_contact_thread_started_at_from_row(case_row),
        distinct_issue_count=projected_distinct_count,
        last_activity_at=now_iso,
    )
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE cases SET raw_message = :msg, case_metadata = :meta, updated_at = :now WHERE id = :cid"),
            {"msg": message_body, "meta": json.dumps(meta), "now": _utcnow(), "cid": case_row["id"]},
        )


def _create_raw_contact_case(
    *,
    tenant_id: int,
    sender: str,
    message_body: str,
    msg_id: str = "",
    media_source: dict | None = None,
    thread_meta: dict | None = None,
) -> int | None:
    case_id = None
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                INSERT INTO cases
                (tenant_id, user_phone, category, raw_message, status, case_metadata, is_critical, created_at)
                VALUES (:tid, :phone, 'Uncategorised', :msg, 'pending', :meta, false, :now)
                RETURNING id
                """
            ),
            {
                "tid": tenant_id,
                "phone": sender,
                "msg": message_body,
                "meta": json.dumps(
                    {
                        "summary": message_body[:200],
                        "wa_msg_id": msg_id,
                        "source_media": bool(media_source),
                        "source_media_type": media_source.get("media_type") if media_source else "",
                        **(thread_meta or {}),
                    }
                ),
                "now": datetime.utcnow(),
            },
        )
        row = result.fetchone()
        case_id = row[0] if row else None
        if case_id and media_source:
            conn.execute(
                text(
                    """
                    INSERT INTO case_media (
                        tenant_id, case_id, source, media_type, mime_type,
                        file_name, media_data, caption, extracted_text,
                        meta_message_id, created_at
                    ) VALUES (
                        :tid, :cid, 'whatsapp', :media_type, :mime_type,
                        :file_name, :media_data, :caption, :extracted_text,
                        :meta_message_id, :now
                    )
                    """
                ),
                {
                    "tid": tenant_id,
                    "cid": case_id,
                    "media_type": media_source.get("media_type", "media"),
                    "mime_type": media_source.get("mime_type", "application/octet-stream"),
                    "file_name": f"whatsapp-{media_source.get('media_type', 'media')}-{msg_id or case_id}",
                    "media_data": media_source.get("media_bytes", b""),
                    "caption": media_source.get("caption", ""),
                    "extracted_text": media_source.get("extracted_text", ""),
                    "meta_message_id": media_source.get("meta_message_id") or msg_id,
                    "now": datetime.utcnow(),
                },
            )
    return case_id


def _recent_contact_thread_case(phone: str, tenant_id: int, *, now: datetime | None = None) -> dict | None:
    now = now or _utcnow()
    cutoff = now - timedelta(hours=_CONTACT_BUFFER_WINDOW_HOURS)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT id, category, status, raw_message, created_at, case_metadata,
                           problem_domain, problem_subdomain, convergence_program_type
                    FROM cases
                    WHERE tenant_id = :tid
                      AND user_phone = :phone
                      AND created_at >= :cutoff
                      AND (is_deleted = false OR is_deleted IS NULL)
                      AND COALESCE(status, '') != :buffer_status
                      AND COALESCE(category, '') NOT IN ('Spam', 'Spam (Offensive)')
                      AND COALESCE(status, '') NOT IN ('offensive', 'closed')
                    ORDER BY COALESCE(updated_at, created_at) DESC, id DESC
                    LIMIT 1
                    """
                ),
                {"tid": tenant_id, "phone": phone, "cutoff": cutoff, "buffer_status": _CONTACT_BUFFER_STATUS},
            ).mappings().first()
        return dict(row) if row else None
    except Exception as exc:
        logger.warning("Recent contact-window lookup failed for %s/%s: %s", tenant_id, phone, exc)
        return None


def _promote_archived_thread_issue(case_row: dict, archived_index: int, message_body: str, language_hint: str = "") -> bool:
    meta = _parse_case_meta(case_row.get("case_metadata"))
    archived_items = list(meta.get("contact_thread_items") or [])
    if archived_index < 0 or archived_index >= len(archived_items):
        return False

    now_iso = _utcnow().isoformat()
    current_issue = _thread_issue_from_row(case_row)
    matched_issue = dict(archived_items.pop(archived_index))
    matched_events = list(matched_issue.get("contact_message_events") or [])
    matched_events.append({
        "message": (message_body or "").strip()[:2000],
        "event_type": "duplicate_followup",
        "created_at": now_iso,
        **({"detected_language": language_hint} if language_hint else {}),
    })
    matched_issue["contact_message_events"] = matched_events[-25:]
    matched_issue["last_message_at"] = now_iso

    archived_items.append(current_issue)
    meta["contact_thread_items"] = archived_items
    meta["contact_message_events"] = matched_issue["contact_message_events"]
    meta["thread_issue_id"] = matched_issue.get("issue_id")
    meta["thread_issue_created_at"] = matched_issue.get("created_at") or now_iso
    meta["thread_issue_last_message_at"] = now_iso
    meta["latest_thread_message_at"] = now_iso
    meta["matched_value"] = matched_issue.get("matched_value") or ""
    meta["assembly_constituency"] = matched_issue.get("assembly_constituency") or ""
    meta["detected_language"] = matched_issue.get("detected_language") or meta.get("detected_language") or language_hint
    meta["language"] = meta["detected_language"]
    meta["summary"] = matched_issue.get("summary") or meta.get("summary") or message_body[:100]
    meta = _update_contact_thread_meta(meta, last_activity_at=now_iso)

    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE cases
                    SET raw_message = :raw_message,
                        category = :category,
                        problem_domain = :problem_domain,
                        problem_subdomain = :problem_subdomain,
                        convergence_program_type = :convergence_program_type,
                        status = :status,
                        case_metadata = :meta,
                        updated_at = :now
                    WHERE id = :cid
                    """
                ),
                {
                    "raw_message": message_body,
                    "category": matched_issue.get("category") or "Uncategorised",
                    "problem_domain": matched_issue.get("problem_domain"),
                    "problem_subdomain": matched_issue.get("problem_subdomain"),
                    "convergence_program_type": matched_issue.get("convergence_program_type"),
                    "status": matched_issue.get("status") or "new",
                    "meta": json.dumps(meta),
                    "now": _utcnow(),
                    "cid": case_row["id"],
                },
            )
        return True
    except Exception as exc:
        logger.warning("Failed to promote archived thread issue for case %s: %s", case_row.get("id"), exc)
        return False


def _find_matching_contact_issue(recent_cases: list[dict], message_body: str) -> dict | None:
    best_match = None
    best_score = 0.0
    for row in recent_cases:
        score = _message_similarity(message_body, row.get("raw_message") or "")
        if score >= _CONTACT_BUFFER_SIMILARITY and score > best_score:
            best_match = row
            best_score = score
    return best_match


def _contact_window_root_case(recent_cases: list[dict]) -> dict | None:
    for row in recent_cases:
        if str(row.get("status") or "").strip().lower() != _CONTACT_BUFFER_STATUS:
            return row
    return recent_cases[0] if recent_cases else None


def _effective_similarity_threshold(latest_case_row: dict | None) -> float:
    """
    Return a lower similarity threshold when the most recent case in this thread
    is very recent.  Citizens who send follow-up messages quickly are more likely
    to be contextually continuing a conversation than filing an unrelated complaint.

    Thresholds:
      ≤ 30 min  → 0.55  (short-burst follow-up)
      ≤ 2 h    → 0.70  (medium-window follow-up)
      > 2 h    → 0.90  (standard dedup gate)
    """
    if not latest_case_row:
        return _CONTACT_BUFFER_SIMILARITY
    try:
        case_time = latest_case_row.get("updated_at") or latest_case_row.get("created_at")
        if isinstance(case_time, str):
            case_time = datetime.fromisoformat(case_time.replace("Z", "+00:00")).replace(tzinfo=None)
        if isinstance(case_time, datetime):
            age_minutes = (_utcnow() - case_time).total_seconds() / 60
            if age_minutes <= _FOLLOWUP_SHORT_WINDOW_MINUTES:
                return _FOLLOWUP_SIMILARITY_SHORT_WINDOW
            if age_minutes <= _FOLLOWUP_MEDIUM_WINDOW_HOURS * 60:
                return _FOLLOWUP_SIMILARITY_MEDIUM_WINDOW
    except Exception:
        pass
    return _CONTACT_BUFFER_SIMILARITY


def _get_thread_context_summary(recent_cases: list[dict]) -> str:
    """
    Build a brief plain-text summary of the 1–2 most recent distinct complaints
    in this citizen's thread.  Injected into the AI classification prompt so
    follow-up messages are classified with conversational context rather than
    in isolation.
    """
    if not recent_cases:
        return ""
    snippets: list[str] = []
    for case in recent_cases[:2]:
        raw = (case.get("raw_message") or "").strip()[:200]
        if not raw:
            continue
        domain = case.get("problem_domain") or ""
        subdomain = case.get("problem_subdomain") or ""
        location = ""
        try:
            meta = _parse_case_meta(case.get("case_metadata"))
            location = meta.get("matched_value") or ""
        except Exception:
            pass
        line = f'- "{raw}"'
        if domain:
            line += f"  [{domain}" + (f" / {subdomain}" if subdomain else "") + "]"
        if location:
            line += f"  (location: {location})"
        snippets.append(line)
    return "\n".join(snippets)


def _buffered_release_epoch(root_case: dict | None, *, now: datetime | None = None) -> int:
    now = now or _utcnow()
    root_created = root_case.get("created_at") if root_case else None
    if isinstance(root_created, str):
        try:
            root_created = datetime.fromisoformat(root_created.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            root_created = None
    if not isinstance(root_created, datetime):
        root_created = now
    release_at = root_created + timedelta(hours=_CONTACT_BUFFER_WINDOW_HOURS)
    return int(release_at.replace(tzinfo=timezone.utc).timestamp())


def _cancel_buffered_release(case_id: int | None) -> None:
    if not case_id:
        return
    with _contact_buffer_release_lock:
        timer = _contact_buffer_release_timers.pop(int(case_id), None)
    if timer:
        timer.cancel()


def _schedule_buffered_release(case_id: int | None, release_after_epoch: int | None) -> None:
    if not case_id or not release_after_epoch:
        return
    _cancel_buffered_release(case_id)
    now_epoch = int(datetime.now(timezone.utc).timestamp())
    delay = max(5, int(release_after_epoch) - now_epoch)
    timer = threading.Timer(delay, _release_due_buffered_contact_cases, args=(int(case_id),))
    timer.daemon = True
    with _contact_buffer_release_lock:
        _contact_buffer_release_timers[int(case_id)] = timer
    timer.start()


def _release_due_buffered_contact_cases(case_id: int | None = None) -> None:
    now_epoch = int(datetime.now(timezone.utc).timestamp())
    params = {"now_epoch": now_epoch}
    where_case = ""
    if case_id is not None:
        params["case_id"] = int(case_id)
        where_case = "AND id = :case_id"

    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    f"""
                    SELECT id, tenant_id, user_phone, raw_message, category, status,
                           problem_domain, problem_subdomain, convergence_program_type,
                           case_metadata
                    FROM cases
                    WHERE status = :buffer_status
                      AND COALESCE((case_metadata::jsonb ->> 'contact_release_after_epoch')::bigint, 0) <= :now_epoch
                      AND (is_deleted = false OR is_deleted IS NULL)
                      {where_case}
                    ORDER BY created_at ASC
                    LIMIT 25
                    """
                ),
                {**params, "buffer_status": _CONTACT_BUFFER_STATUS},
            ).mappings().all()
    except Exception as exc:
        logger.warning("Buffered contact-case release sweep failed: %s", exc)
        return

    for row in rows:
        _cancel_buffered_release(row["id"])
        meta = _parse_case_meta(row.get("case_metadata"))
        if meta.get("contact_buffer_overflow_flagged"):
            try:
                with engine.begin() as conn:
                    meta["contact_buffer_released_at"] = _utcnow().isoformat()
                    conn.execute(
                        text(
                            """
                            UPDATE cases
                            SET category = 'Spam',
                                status = 'new',
                                case_metadata = :meta,
                                updated_at = :now
                            WHERE id = :cid
                            """
                        ),
                        {"meta": json.dumps(meta), "now": _utcnow(), "cid": row["id"]},
                    )
            except Exception as exc:
                logger.warning("Failed to finalise buffered spam case %s: %s", row["id"], exc)
            continue

        release_status = str(meta.get("contact_buffer_release_status") or "new").strip().lower() or "new"
        ack_message = str(meta.get("contact_buffer_ack_message") or "")
        enrichment = {
            "status": release_status,
            "category": row.get("category") or meta.get("problem_domain") or "Uncategorised",
            "detected_language": meta.get("detected_language") or meta.get("language") or "Hindi",
            "meta_data": {k: v for k, v in meta.items() if not str(k).startswith("contact_buffer_")},
            "problem_domain": row.get("problem_domain") or meta.get("problem_domain"),
            "problem_subdomain": row.get("problem_subdomain") or meta.get("problem_subdomain"),
            "convergence_program_type": row.get("convergence_program_type") or meta.get("convergence_program_type"),
            "is_emergency_complaint": False,
            "emergency_keyword_match": False,
            "political_reply": ack_message,
            "final_constituency": meta.get("assembly_constituency"),
            "citizen_ack_message": ack_message,
        }
        _save_case_enrichment_and_respond(
            case_id=row["id"],
            sender=row["user_phone"],
            current_tenant=row["tenant_id"],
            message_body=row.get("raw_message") or "",
            wa_phone_id=get_tenant_phone_number_id(row["tenant_id"]),
            enrichment=enrichment,
        )


def _is_abusive(message_body: str) -> tuple:
    """Returns (True, reason) if the message contains severe abuse keywords."""
    normalised = _normalise(message_body)
    for kw in _ABUSE_KEYWORDS:
        if kw in normalised:
            return True, f"Matched abuse keyword: '{kw}'"
    return False, ""


def _is_coordinated_flood(message_body: str, tenant_id: int) -> tuple:
    """
    Returns (True, reason) if 20+ UNIQUE phone numbers sent a near-identical
    message to the same MP (tenant) in the last 60 minutes.
    Fingerprint = first 60 chars of normalised text.
    """
    normalised = _normalise(message_body)
    fingerprint = normalised[:_FLOOD_FINGERPRINT_LEN]
    if len(fingerprint) < _FLOOD_MIN_MESSAGE_LEN:
        return False, ""  # too short to reliably fingerprint

    window_start = datetime.utcnow() - timedelta(minutes=_FLOOD_WINDOW_MINUTES)
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT user_phone, raw_message
                    FROM cases
                    WHERE tenant_id = :tid AND created_at >= :window
                    LIMIT 5000
                """),
                {"tid": tenant_id, "window": window_start},
            ).fetchall()

        matching_phones = {
            phone
            for phone, msg in rows
            if _normalise(msg or "")[:_FLOOD_FINGERPRINT_LEN] == fingerprint
        }
        if len(matching_phones) >= _FLOOD_THRESHOLD:
            return True, (
                f"Coordinated flood detected: {len(matching_phones)} unique phones "
                f"sent near-identical messages within {_FLOOD_WINDOW_MINUTES} min"
            )
    except Exception as exc:
        logger.warning(f"Flood detection query failed: {exc}")
    return False, ""


def _save_spam_flag(tenant_id: int, phone: str, flag_type: str, reason: str, message_body: str):
    """Insert a row into spam_flags. Fire-and-forget — failure is logged, not raised."""
    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO spam_flags
                        (tenant_id, phone, flag_type, flag_reason, message_preview, created_at)
                    VALUES (:tid, :phone, :ftype, :reason, :preview, :now)
                """),
                {
                    "tid": tenant_id,
                    "phone": phone,
                    "ftype": flag_type,
                    "reason": reason,
                    "preview": message_body[:120],
                    "now": datetime.utcnow(),
                },
            )
    except Exception as exc:
        logger.warning(f"spam_flags insert failed: {exc}")


# ─────────────────────────────────────────
# META CLOUD API HELPER (shared module)
# ─────────────────────────────────────────
from modules.whatsapp import send_whatsapp_message  # noqa: E402
from modules.letterbox import download_meta_media  # noqa: E402
from modules.whatsapp_media_intake import normalize_media_complaint  # noqa: E402
from modules.case_query_parser import parse_query
from modules.case_query_engine import query_cases
from modules.briefcase_rules import apply_civic_rules
from modules.staff_schedule_parser import parse_staff_schedule_message
from modules.whatsapp_geography import finalize_geography_decision
from modules.geography_policy import location_required_for_domain
from modules.localized_replies import (
    DETAILS_REQUEST_STATUSES,
    ensure_ji_prefix,
    get_awaiting_location_reply,
    get_details_request_reply,
    get_generic_ack_reply,
    get_greeting_reply,
    get_location_update_reply,
    get_missing_location_reply,
    get_personal_request_reply,
    get_rate_limit_reply,
    get_review_ack_reply,
    get_unsupported_message_reply,
    normalize_language_name,
)
from modules.case_query_formatter import format_cases_for_whatsapp, format_clarification_request

_SILENT_LOG_CATEGORIES = {
    "political / support message",
    "community / event invitation",
    "media / press outreach",
    "donation / sponsorship request",
    "suggestion / idea",
    "spam / promotional / irrelevant",
}

# Greetings are non-grievance but DO get a warm reply (not silent), so they are
# tracked separately from the silent-log categories above.
_GREETING_CATEGORIES = {"greetings", "greeting"}


# ─────────────────────────────────────────
# CONTEXT MEMORY (prevents repeated questions)
# ─────────────────────────────────────────
def get_user_context(phone_number: str) -> str:
    try:
        with engine.connect() as conn:
            # Use JSONB operator instead of CAST+LIKE for correctness and performance.
            # Falls back to text search for SQLite (dev/test environments).
            try:
                query = text("""
                    SELECT case_metadata FROM cases
                    WHERE user_phone = :phone
                      AND (case_metadata->>'location_resolved')::boolean = true
                    ORDER BY created_at DESC LIMIT 1
                """)
                result = conn.execute(query, {"phone": phone_number}).fetchone()
            except Exception:
                # SQLite fallback (development only)
                query = text("""
                    SELECT case_metadata FROM cases
                    WHERE user_phone = :phone
                    ORDER BY created_at DESC LIMIT 1
                """)
                result = conn.execute(query, {"phone": phone_number}).fetchone()

            if result and result[0]:
                meta = result[0]
                if isinstance(meta, str):
                    meta = json.loads(meta)
                if not meta.get("location_resolved"):
                    return ""
                loc = meta.get("matched_value", "")
                const = meta.get("assembly_constituency", "")
                if loc or const:
                    return f"KNOWN USER CONTEXT: User is from Location: {loc}, Constituency: {const}. DO NOT ask for location."
    except Exception as e:
        logger.warning(f"Context fetch error: {e}")
    return ""


def get_pending_incomplete_case(phone: str, tenant_id: int):
    """
    Returns the most recent clarification-pending case for this phone/tenant
    created within the last 30 minutes, or None if no such case exists.
    """
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT id, case_metadata, category, raw_message, status
                    FROM cases
                    WHERE user_phone = :phone
                      AND tenant_id = :tid
                      AND (
                        status = 'awaiting_location'
                        OR status = 'incomplete'
                        OR case_metadata::jsonb ->> 'clarification_follow_up_pending' = 'true'
                      )
                      AND created_at >= NOW() - INTERVAL '30 minutes'
                      AND (is_deleted = false OR is_deleted IS NULL)
                    ORDER BY created_at DESC LIMIT 1
                """),
                {"phone": phone, "tid": tenant_id}
            ).fetchone()
            if row:
                meta = row[1]
                if isinstance(meta, str):
                    meta = json.loads(meta)
                return {"id": row[0], "meta": meta, "category": row[2], "raw_message": row[3], "status": row[4]}
    except Exception as e:
        logger.warning("Pending incomplete case lookup failed: %s", e)
    return None


# ─────────────────────────────────────────
# WHATSAPP WEBHOOK (Meta Cloud API)
# ─────────────────────────────────────────
_webhook_decorate = limiter.limit(RATE_WEBHOOK) if _rate_limiting_enabled else (lambda f: f)


@app.get("/whatsapp/webhook")
async def verify_webhook(request: Request):
    """Meta webhook verification handshake (one-time setup)."""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if mode == "subscribe" and token == os.getenv("META_VERIFY_TOKEN"):
        logger.info("Meta webhook verified successfully.")
        return PlainTextResponse(challenge)
    logger.warning(f"Webhook verification failed — mode={mode}, token_match={token == os.getenv('META_VERIFY_TOKEN')}")
    raise HTTPException(status_code=403, detail="Verification failed")


def _resolve_tenant(receiver_number: str) -> int | None:
    """Resolve WhatsApp receiver number → tenant_id.

    FAIL-SAFE: returns None when the number cannot be matched to any tenant.
    Callers MUST check for None and drop the message rather than defaulting.
    Only falls back to tenant_id=1 when receiver_number is empty/None
    (single-tenant deployments that never set WHATSAPP_PHONE_NUMBER_ID).

    Resolution order:
      1. In-memory phone_mapping from DB (TenantOverride)
      2. Direct tenant.whatsapp_number match in DB
      3. None (fail-safe — caller drops message)
    """
    # Empty receiver_number = single-tenant deployment without phone routing
    if not receiver_number:
        logger.debug("_resolve_tenant: no receiver_number — falling back to tenant_id=1 (single-tenant mode)")
        return 1

    # 1. DB phone mapping (overrides table)
    try:
        phone_map = get_phone_tenant_mapping()
        if receiver_number in phone_map:
            return phone_map[receiver_number]
    except Exception as exc:
        logger.warning("Tenant phone mapping lookup failed for %s: %s", receiver_number, exc)

    # 2. Direct whatsapp_number match on tenants table
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT id FROM tenants WHERE whatsapp_number = :num AND is_active = true LIMIT 1"),
                {"num": receiver_number}
            ).fetchone()
            if row:
                return row[0]
    except Exception as exc:
        logger.warning("Tenant DB lookup failed for %s: %s", receiver_number, exc)

    # 3. No match — fail-safe: drop the message
    logger.critical(
        "TENANT_RESOLUTION_FAILED: receiver_number='%s' matched no tenant. "
        "Message will be DROPPED. Verify WHATSAPP_PHONE_NUMBER_ID env var and "
        "tenant_overrides configuration match this number exactly (include country code).",
        receiver_number,
    )
    return None


def _get_registered_staff_sender(sender: str, tenant_id: int) -> dict | None:
    """Return the matching active staff/PA user for a WhatsApp sender, if any."""
    sender_digits = re.sub(r"\D", "", sender or "")
    sender_bare = sender_digits[2:] if sender_digits.startswith("91") and len(sender_digits) == 12 else sender_digits
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT id, username, display_name, phone FROM users
                    WHERE tenant_id = :tid
                      AND is_active = true
                      AND phone IS NOT NULL
                """),
                {"tid": tenant_id},
            ).fetchall()
        for row in rows:
            _id, username, display_name, phone = row
            staff_digits = re.sub(r"\D", "", phone or "")
            staff_bare = staff_digits[2:] if staff_digits.startswith("91") and len(staff_digits) == 12 else staff_digits
            if sender in {phone, staff_digits, staff_bare} or sender_digits in {staff_digits, staff_bare} or sender_bare == staff_bare:
                return {
                    "id": _id,
                    "username": username,
                    "display_name": display_name,
                    "phone": phone,
                }
        return None
    except Exception as exc:
        logger.warning("Staff sender lookup failed: %s", exc)
        return None


def _is_registered_staff_sender(sender: str, tenant_id: int) -> bool:
    """Return True when a WhatsApp sender is an active staff/PA user."""
    return bool(_get_registered_staff_sender(sender, tenant_id))


def _save_staff_schedule_entry(tenant_id: int, created_by: str, parsed: dict) -> dict | None:
    try:
        scheduled_for = parsed.get("scheduled_for") or _utcnow().date().isoformat()
        start_time = parsed.get("start_time")
        end_time = parsed.get("end_time")

        def _combine(target_date: str, time_text: str | None):
            if not time_text:
                return None
            try:
                date_part = datetime.fromisoformat(target_date).date()
                hour_text, minute_text = str(time_text).split(":", 1)
                return datetime(
                    date_part.year,
                    date_part.month,
                    date_part.day,
                    int(hour_text),
                    int(minute_text),
                )
            except Exception:
                return None

        starts_at = None if parsed.get("is_all_day") else _combine(scheduled_for, start_time)
        ends_at = None if parsed.get("is_all_day") else _combine(scheduled_for, end_time)
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    INSERT INTO dashboard_engagements (
                        tenant_id, entry_type, title, notes, location, scheduled_for,
                        starts_at, ends_at, calendar_url, is_all_day, created_by
                    )
                    VALUES (
                        :tenant_id, :entry_type, :title, :notes, :location, :scheduled_for,
                        :starts_at, :ends_at, :calendar_url, :is_all_day, :created_by
                    )
                    RETURNING id, entry_type, title, notes, location, scheduled_for,
                              starts_at, ends_at, calendar_url, is_all_day, created_by
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "entry_type": parsed.get("entry_type") or "schedule",
                    "title": parsed.get("title") or "",
                    "notes": parsed.get("notes"),
                    "location": parsed.get("location"),
                    "scheduled_for": scheduled_for,
                    "starts_at": starts_at,
                    "ends_at": ends_at,
                    "calendar_url": parsed.get("calendar_url"),
                    "is_all_day": bool(parsed.get("is_all_day")),
                    "created_by": created_by,
                },
            ).mappings().first()
        return dict(row) if row else None
    except Exception as exc:
        logger.error("Staff schedule save failed: %s", exc)
        return None


def _format_staff_schedule_confirmation(item: dict | None) -> str:
    item = item or {}
    title = item.get("title") or "Schedule item"
    scheduled_for = item.get("scheduled_for")
    starts_at = item.get("starts_at")
    location = item.get("location")
    entry_type = item.get("entry_type") or "schedule"

    if hasattr(scheduled_for, "strftime"):
        date_label = scheduled_for.strftime("%d %b")
    else:
        date_label = str(scheduled_for) if scheduled_for else "today"
    if hasattr(starts_at, "strftime"):
        time_label = starts_at.strftime("%H:%M")
    else:
        time_label = ""

    bits = [f"✅ Saved to schedule: {title}"]
    meta = []
    if entry_type == "note":
        meta.append("note")
    elif time_label:
        meta.append(f"{date_label}, {time_label}")
    else:
        meta.append(date_label)
    if location:
        meta.append(str(location))
    if meta:
        bits.append(" | ".join(meta))
    return "\n".join(bits)


def _finalize_whatsapp_geography_decision(
    *,
    grievance: dict,
    ai_result: dict,
    status: str,
    political_reply: str,
    detected_language: str,
    message_body: str,
    current_tenant: int,
    is_emergency_complaint: bool,
    location_required: bool = True,
    resolver_message_body: str | None = None,
    resolver_fallback_message_body: str | None = None,
) -> dict:
    try:
        from sansadx_backend.db import get_tenant_constituency
    except Exception:
        get_tenant_constituency = lambda _tenant_id: None

    return finalize_geography_decision(
        grievance=grievance,
        ai_result=ai_result,
        status=status,
        political_reply=political_reply,
        detected_language=detected_language,
        message_body=message_body,
        resolver_message_body=resolver_message_body,
        resolver_fallback_message_body=resolver_fallback_message_body,
        current_tenant=current_tenant,
        is_emergency_complaint=is_emergency_complaint,
        location_required=location_required,
        resolve_location_fn=resolve_location,
        resolve_constituency_fn=resolve_constituency,
        get_tenant_constituency_fn=get_tenant_constituency,
        assembly_belongs_to_parliamentary_fn=assembly_belongs_to_parliamentary,
    )


# ─────────────────────────────────────────
# MULTI-PAGE LETTER BATCH SYSTEM
# ─────────────────────────────────────────
# PA sends multiple images for a single multi-page letter.
# Each image is queued in DB. After BATCH_FLUSH_DELAY seconds of
# inactivity (or an explicit "DONE" command), all pages are processed
# together as one letterbox entry.

BATCH_FLUSH_DELAY = 60  # seconds of silence before auto-processing

_batch_timers: dict = {}
_batch_lock = threading.Lock()


def _add_to_batch(tenant_id: int, sender: str, receiver_number: str,
                  media_id: str, mime_type: str, direction_hint: str | None) -> int:
    """
    Append one image to the pending batch for this sender.
    Creates the batch row if it doesn't exist.
    Returns the new page count.
    """
    with engine.begin() as conn:
        row = conn.execute(text("""
            SELECT id, images, direction_hint FROM letterbox_batches
            WHERE sender_phone = :phone AND tenant_id = :tid AND status = 'pending'
            LIMIT 1
        """), {"phone": sender, "tid": tenant_id}).fetchone()

        new_image = {"media_id": media_id, "mime_type": mime_type}

        if row:
            images = list(row[1]) if row[1] else []
            images.append(new_image)
            # Keep the first caption's direction_hint; later pages usually have no caption
            effective_hint = row[2] or direction_hint
            conn.execute(text("""
                UPDATE letterbox_batches
                SET images = :imgs, last_image_at = :now, direction_hint = :hint
                WHERE id = :id
            """), {"imgs": json.dumps(images), "now": datetime.utcnow(),
                   "hint": effective_hint, "id": row[0]})
            return len(images)
        else:
            conn.execute(text("""
                INSERT INTO letterbox_batches
                    (tenant_id, sender_phone, receiver_number, images, direction_hint, last_image_at)
                VALUES (:tid, :phone, :recv, :imgs, :hint, :now)
            """), {
                "tid":  tenant_id,
                "phone": sender,
                "recv": receiver_number,
                "imgs": json.dumps([new_image]),
                "hint": direction_hint,
                "now":  datetime.utcnow(),
            })
            return 1


import asyncio
from fastapi.concurrency import run_in_threadpool

async def _delayed_flush_letter_batch(sender: str, tenant_id: int, receiver_number: str):
    """
    Async wrapper for flush. Sleeps non-blocking, then runs the blocking
    flush in the FastAPI threadpool. Replaces threading.Timer.
    """
    await asyncio.sleep(BATCH_FLUSH_DELAY)
    await run_in_threadpool(_flush_letter_batch, sender, tenant_id, receiver_number)

def _schedule_batch_flush(sender: str, tenant_id: int, receiver_number: str):
    """
    Schedule a delayed flush of this sender's letter batch.
    Called from a sync background thread — posts the coroutine onto the
    running FastAPI event loop so it executes after BATCH_FLUSH_DELAY seconds.
    """
    try:
        loop = asyncio.get_event_loop()
        asyncio.run_coroutine_threadsafe(
            _delayed_flush_letter_batch(sender, tenant_id, receiver_number),
            loop,
        )
        logger.info(
            "Batch flush scheduled for %s (tenant=%s) in %ds",
            sender, tenant_id, BATCH_FLUSH_DELAY,
        )
    except Exception as exc:
        logger.warning("Could not schedule batch flush for %s: %s — falling back to immediate flush", sender, exc)
        # Fallback: flush synchronously right now rather than lose the letter
        _flush_letter_batch(sender, tenant_id, receiver_number)


def _flush_letter_batch(sender: str, tenant_id: int, receiver_number: str):
    """
    Process all accumulated pages in a batch as a single letterbox entry.
    Called either by the inactivity timer or immediately on 'DONE' command.
    """
    from modules.letterbox import download_meta_image, generate_diary_number, extract_letter_fields
    _wa_phone_id = get_tenant_phone_number_id(tenant_id)

    # Cancel any pending timer
    key = (sender, tenant_id)
    with _batch_lock:
        t = _batch_timers.pop(key, None)
        if t:
            t.cancel()

    # Claim the batch atomically
    try:
        with engine.begin() as conn:
            batch = conn.execute(text("""
                UPDATE letterbox_batches SET status = 'processing'
                WHERE sender_phone = :phone AND tenant_id = :tid AND status = 'pending'
                RETURNING id, images, direction_hint
            """), {"phone": sender, "tid": tenant_id}).fetchone()
    except Exception as exc:
        logger.error(f"Failed to claim letterbox batch for {sender}: {exc}")
        return

    if not batch:
        return  # already processed or no batch

    batch_id, images_json, direction_hint = batch
    images = list(images_json) if images_json else []
    if not images:
        return

    page_count = len(images)
    logger.info(f"Flushing batch id={batch_id}: {page_count} page(s) from {sender}, tenant={tenant_id}")

    # ── Download all page images from Meta ──
    page_bytes: list[tuple[bytes, str]] = []
    for img in images:
        try:
            b, m = download_meta_image(img["media_id"])
            page_bytes.append((b, m))
        except Exception as exc:
            logger.warning(f"Failed to download page {img['media_id']}: {exc}")

    if not page_bytes:
        logger.error(f"All image downloads failed for batch {batch_id}")
        try:
            send_whatsapp_message(sender, "Sorry, could not retrieve the images. Please resend.", _wa_phone_id)
        except Exception:
            pass
        try:
            with engine.begin() as conn:
                conn.execute(text("UPDATE letterbox_batches SET status = 'failed' WHERE id = :id"),
                             {"id": batch_id})
        except Exception:
            pass
        return

    first_bytes, first_mime = page_bytes[0]
    extra_pages = page_bytes[1:] if len(page_bytes) > 1 else None

    # ── Save raw entry immediately (source of truth) ──
    letter_id = None
    diary_number = None
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                INSERT INTO letterbox (
                    tenant_id, direction, image_data, image_mime, page_count,
                    status, source, sender_phone, created_at,
                    citizen_name, issue_summary, urgency_level
                ) VALUES (
                    :tid, :dir, :img, :mime, :pages,
                    'processing', 'whatsapp', :phone, :now,
                    '[NOT FOUND]', '[Processing...]', 'Normal'
                ) RETURNING id
            """), {
                "tid":   tenant_id,
                "dir":   direction_hint or "inbox",
                "img":   first_bytes,
                "mime":  first_mime,
                "pages": page_count,
                "phone": sender,
                "now":   datetime.utcnow(),
            })
            letter_id = result.fetchone()[0]
            diary_number = generate_diary_number(letter_id)
            conn.execute(text("UPDATE letterbox SET diary_number = :dn WHERE id = :lid"),
                         {"dn": diary_number, "lid": letter_id})
        logger.info(f"Multi-page letter saved: id={letter_id}, diary={diary_number}, pages={page_count}")
    except Exception as exc:
        logger.error(f"CRITICAL: Failed to save batch letter to DB: {exc}")
        try:
            send_whatsapp_message(sender, "Sorry, there was a database error. Please contact support.", _wa_phone_id)
        except Exception:
            pass
        return

    # ── Save additional pages to letterbox_pages ──
    if extra_pages:
        try:
            with engine.begin() as conn:
                for i, (pb, pm) in enumerate(extra_pages, start=2):
                    conn.execute(text("""
                        INSERT INTO letterbox_pages (letterbox_id, page_number, image_data, image_mime)
                        VALUES (:lid, :pnum, :data, :mime)
                    """), {"lid": letter_id, "pnum": i, "data": pb, "mime": pm})
        except Exception as exc:
            logger.error(f"Failed to save extra pages for letter {letter_id}: {exc}")

    # ── Gemini extraction (all pages in one call) ──
    extracted = extract_letter_fields(
        first_bytes, first_mime, tenant_id,
        direction_hint=direction_hint,
        extra_pages=extra_pages
    )

    # ── Update letterbox row ──
    try:
        if extracted:
            final_direction = extracted.get("direction", direction_hint or "inbox")
            final_status = "new" if final_direction == "inbox" else "sent"
            with engine.begin() as conn:
                conn.execute(text("""
                    UPDATE letterbox SET
                        direction      = :dir,
                        citizen_name   = :name,
                        village        = :village,
                        phone_number   = :phone,
                        issue_summary  = :subject,
                        category       = :category,
                        urgency_level  = :priority,
                        ocr_text       = :ocr,
                        date_of_letter = :dol,
                        status         = :status
                    WHERE id = :lid
                """), {
                    "dir":      final_direction,
                    "name":     extracted.get("sender_name", "[NOT FOUND]"),
                    "village":  extracted.get("village", "[NOT FOUND]"),
                    "phone":    extracted.get("phone_number", "[NOT FOUND]"),
                    "subject":  extracted.get("subject", "[NOT FOUND]"),
                    "category": extracted.get("category", "General / Other"),
                    "priority": extracted.get("priority", "Normal"),
                    "ocr":      extracted.get("ocr_text", ""),
                    "dol":      extracted.get("date_of_letter") or None,
                    "status":   final_status,
                    "lid":      letter_id,
                })
        else:
            final_direction = direction_hint or "inbox"
            with engine.begin() as conn:
                conn.execute(text("""
                    UPDATE letterbox SET status = 'needs_review',
                        issue_summary = '[OCR failed — please review manually]'
                    WHERE id = :lid
                """), {"lid": letter_id})
    except Exception as exc:
        logger.error(f"Failed to update letter {letter_id} post-extraction: {exc}")
        final_direction = direction_hint or "inbox"

    try:
        log_letterbox_activity(
            tenant_id=tenant_id,
            letterbox_id=letter_id,
            action_type="created",
            actor_username=sender,
            actor_channel="whatsapp_pa",
            summary=f"WhatsApp {final_direction} letter captured",
            details={
                "source": "whatsapp",
                "direction": final_direction,
                "page_count": page_count,
                "sender_phone": sender,
                "ocr_success": bool(extracted),
            },
        )
    except Exception:
        pass

    # Mark batch done
    try:
        with engine.begin() as conn:
            conn.execute(text("UPDATE letterbox_batches SET status = 'done' WHERE id = :id"),
                         {"id": batch_id})
    except Exception:
        pass

    # ── Confirm to PA ──
    direction_label = "INBOX" if final_direction == "inbox" else "OUTBOX"
    pages_label = f"{page_count} page{'s' if page_count > 1 else ''}"
    if extracted:
        confirm_msg = (
            f"Saved to {direction_label} — Ref: {diary_number} ({pages_label})\n"
            f"{'Sender' if final_direction == 'inbox' else 'Recipient'}: "
            f"{extracted.get('sender_name', '[Unknown]')}\n"
            f"Category: {extracted.get('category', 'General / Other')}\n"
            f"Summary: {extracted.get('subject', '')[:120]}\n\n"
            f"If direction is wrong: MOVE {diary_number} {'OUT' if final_direction == 'inbox' else 'IN'}"
        )
    else:
        confirm_msg = (
            f"Letter saved ({pages_label}) — Ref: {diary_number}\n"
            f"OCR could not read clearly. Open Letterbox dashboard to fill in details."
        )
    try:
        send_whatsapp_message(sender, confirm_msg, _wa_phone_id)
    except Exception as exc:
        logger.warning(f"WhatsApp batch confirmation failed: {exc}")


def _sweep_stale_batches():
    """
    On startup: recover letterbox batches interrupted by a previous server crash or deploy.

    Two recovery paths:
    1. 'pending' batches older than BATCH_FLUSH_DELAY — timer never fired (normal restart).
    2. 'processing' batches older than 10 minutes — thread was killed mid-OCR (crash/OOM).
       These are reset to 'pending' first so _flush_letter_batch can claim them cleanly.
    """
    try:
        stale_cutoff = datetime.utcnow() - timedelta(seconds=BATCH_FLUSH_DELAY)
        processing_stuck_cutoff = datetime.utcnow() - timedelta(minutes=10)

        # ── Path 2: reset stuck 'processing' batches so they can be reclaimed ──
        try:
            with engine.begin() as _rst_conn:
                _stuck = _rst_conn.execute(
                    text("""
                        UPDATE letterbox_batches
                        SET status = 'pending'
                        WHERE status = 'processing'
                          AND last_image_at < :cutoff
                        RETURNING sender_phone, tenant_id
                    """),
                    {"cutoff": processing_stuck_cutoff},
                )
                stuck_rows = _stuck.fetchall()
                if stuck_rows:
                    logger.warning(
                        "Startup sweep: reset %d stuck 'processing' batches to 'pending': %s",
                        len(stuck_rows),
                        [(r[0], r[1]) for r in stuck_rows],
                    )
        except Exception as _rst_exc:
            logger.warning("Stuck-processing batch reset failed: %s", _rst_exc)

        # ── Path 1 + 2 combined: flush all pending batches older than threshold ──
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT sender_phone, tenant_id, receiver_number FROM letterbox_batches
                WHERE status = 'pending' AND last_image_at < :cutoff
            """), {"cutoff": stale_cutoff}).fetchall()
        for row in rows:
            logger.info(f"Startup sweep: flushing stale batch for {row[0]}, tenant={row[1]}")
            import asyncio
            from fastapi.concurrency import run_in_threadpool
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(run_in_threadpool(_flush_letter_batch, row[0], row[1], row[2]))
            except RuntimeError:
                # Fallback if somehow called outside event loop
                from concurrent.futures import ThreadPoolExecutor
                ThreadPoolExecutor(max_workers=1).submit(_flush_letter_batch, row[0], row[1], row[2])
    except Exception as exc:
        logger.warning(f"Stale batch sweep failed: {exc}")


def _sweep_pending_citizen_acks():
    """
    On startup: retry WhatsApp ACK sends that failed during a previous run.

    When send_whatsapp_message() throws during the human-review gate, the case is
    flagged with citizen_ack_pending=true in its metadata.  This sweep finds those
    cases (created within the last 24 hours, to avoid spamming old cases), retries
    the send, and clears the flag on success.

    Runs once at startup; a separate periodic call can be added via a cron job if
    needed.  Failures are logged but never raise — startup must not be blocked.
    """
    try:
        cutoff = datetime.utcnow() - timedelta(hours=24)
        with engine.connect() as _ack_scan_conn:
            pending_acks = _ack_scan_conn.execute(
                text("""
                    SELECT id, tenant_id, case_metadata
                    FROM cases
                    WHERE case_metadata::jsonb ->> 'citizen_ack_pending' = 'true'
                      AND created_at >= :cutoff
                    LIMIT 50
                """),
                {"cutoff": cutoff},
            ).fetchall()
    except Exception as _scan_exc:
        logger.warning("Pending ACK sweep query failed: %s", _scan_exc)
        return

    if not pending_acks:
        return

    logger.info("ACK sweep: found %d cases with pending citizen acknowledgment", len(pending_acks))
    for _row in pending_acks:
        _case_id, _tenant_id, _meta_raw = _row
        try:
            _meta = _meta_raw if isinstance(_meta_raw, dict) else json.loads(_meta_raw or "{}")
            _phone = _meta.get("citizen_phone", "")
            if not _phone:
                logger.warning("ACK sweep: case %s has citizen_ack_pending but no citizen_phone — skipping", _case_id)
                continue
            _wa_pid = get_tenant_phone_number_id(_tenant_id)
            send_whatsapp_message(_phone, _REVIEW_GENERIC_ACK, _wa_pid)
            # Clear the flag on success
            with engine.begin() as _clr_conn:
                _clr_conn.execute(
                    text("""
                        UPDATE cases
                        SET case_metadata = case_metadata - 'citizen_ack_pending'
                        WHERE id = :cid
                    """),
                    {"cid": _case_id},
                )
            logger.info("ACK sweep: retried and cleared citizen_ack_pending for case %s", _case_id)
        except Exception as _ack_retry_exc:
            logger.warning("ACK sweep: retry failed for case %s: %s", _case_id, _ack_retry_exc)


_CAPTION_INBOX_KEYWORDS  = {"in", "inbox", "received", "incoming"}
_CAPTION_OUTBOX_KEYWORDS = {"out", "outbox", "sent", "dispatch", "dispatched"}


def _parse_direction_hint(caption: str) -> str | None:
    """Return 'inbox', 'outbox', or None based on the PA's WhatsApp caption."""
    word = caption.strip().lower().split()[0] if caption.strip() else ""
    if word in _CAPTION_INBOX_KEYWORDS:
        return "inbox"
    if word in _CAPTION_OUTBOX_KEYWORDS:
        return "outbox"
    return None  # let AI classify


def _process_pa_letter(sender: str, media_id: str, mime_type: str, receiver_number: str = "", caption: str = ""):
    """
    Background task: PA sends a photo of a physical letter via WhatsApp.

    Each image is added to a DB-backed batch for this sender.
    After BATCH_FLUSH_DELAY seconds of inactivity (or explicit DONE command),
    _flush_letter_batch processes all pages together as one letterbox entry.

    This naturally handles single-page letters (batch of 1) and multi-page letters.
    """

    if not receiver_number:
        receiver_number = os.getenv("WHATSAPP_PHONE_NUMBER_ID") or os.getenv("META_PHONE_NUMBER_ID", "")

    current_tenant = _resolve_tenant(receiver_number)
    if current_tenant is None:
        logger.error(
            "_process_pa_letter: tenant resolution returned None for receiver=%s sender=%s — dropping image",
            receiver_number, sender
        )
        return
    _wa_phone_id = get_tenant_phone_number_id(current_tenant)

    # PA whitelist check — sender must be a registered active user for this tenant
    try:
        with engine.connect() as conn:
            _bare = sender[2:] if sender.startswith("91") and len(sender) == 12 else sender
            pa_row = conn.execute(
                text("""SELECT id, display_name FROM users
                        WHERE (phone = :phone OR phone = :bare) AND tenant_id = :tid AND is_active = true
                        LIMIT 1"""),
                {"phone": sender, "bare": _bare, "tid": current_tenant}
            ).fetchone()
    except Exception as exc:
        logger.error(f"PA check DB query failed: {exc}")
        return

    if not pa_row:
        logger.info(f"Image from {sender} — not a registered PA for tenant {current_tenant}, ignoring")
        return

    pa_name = pa_row[1] or "Staff"
    direction_hint = _parse_direction_hint(caption)
    logger.info(f"PA image received: sender={sender} ({pa_name}), tenant={current_tenant}, "
                f"media_id={media_id}, caption_hint={direction_hint or 'auto-classify'}")

    # Add this image to the pending batch (creates batch if first image)
    try:
        page_count = _add_to_batch(current_tenant, sender, receiver_number,
                                   media_id, mime_type, direction_hint)
    except Exception as exc:
        logger.error(f"Failed to add image to batch: {exc}")
        try:
            send_whatsapp_message(sender, "Sorry, could not queue the image. Please resend.", _wa_phone_id)
        except Exception:
            pass
        return

    _schedule_batch_flush(sender, current_tenant, receiver_number)


def _process_pa_letter_pdf(
    sender: str,
    media_id: str,
    mime_type: str,
    receiver_number: str = "",
    caption: str = "",
):
    """
    Background task: PA sends a PDF of a letter via WhatsApp.

    PDFs are saved as a single Letterbox entry immediately instead of using the
    multi-image batch flow. Caption-based direction hints still apply.
    """
    from modules.letterbox import (
        count_pdf_pages,
        download_meta_media,
        extract_letter_fields,
        generate_diary_number,
    )

    if not receiver_number:
        receiver_number = os.getenv("WHATSAPP_PHONE_NUMBER_ID") or os.getenv("META_PHONE_NUMBER_ID", "")

    current_tenant = _resolve_tenant(receiver_number)
    if current_tenant is None:
        logger.error(
            "_process_pa_letter_pdf: tenant resolution returned None for receiver=%s sender=%s — dropping PDF",
            receiver_number,
            sender,
        )
        return
    _wa_phone_id = get_tenant_phone_number_id(current_tenant)

    try:
        with engine.connect() as conn:
            _bare = sender[2:] if sender.startswith("91") and len(sender) == 12 else sender
            pa_row = conn.execute(
                text("""SELECT id, display_name FROM users
                        WHERE (phone = :phone OR phone = :bare) AND tenant_id = :tid AND is_active = true
                        LIMIT 1"""),
                {"phone": sender, "bare": _bare, "tid": current_tenant}
            ).fetchone()
    except Exception as exc:
        logger.error(f"PA check DB query failed for PDF intake: {exc}")
        return

    if not pa_row:
        logger.info(f"PDF from {sender} — not a registered PA for tenant {current_tenant}, sending unsupported prompt")
        _handle_unsupported_message_type(sender, "document", receiver_number)
        return

    pa_name = pa_row[1] or "Staff"
    direction_hint = _parse_direction_hint(caption)
    logger.info(
        "PA PDF received: sender=%s (%s), tenant=%s, media_id=%s, caption_hint=%s",
        sender,
        pa_name,
        current_tenant,
        media_id,
        direction_hint or "auto-classify",
    )

    try:
        pdf_bytes, resolved_mime = download_meta_media(media_id)
    except Exception as exc:
        logger.error(f"Failed to download PA PDF {media_id}: {exc}")
        try:
            send_whatsapp_message(sender, "Sorry, could not retrieve the PDF. Please resend it.", _wa_phone_id)
        except Exception:
            pass
        return

    page_count = count_pdf_pages(pdf_bytes)
    letter_id = None
    diary_number = None
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                INSERT INTO letterbox (
                    tenant_id, direction, image_data, image_mime, page_count,
                    status, source, sender_phone, created_at,
                    citizen_name, issue_summary, urgency_level
                ) VALUES (
                    :tid, :dir, :img, :mime, :pages,
                    'processing', 'whatsapp', :phone, :now,
                    '[NOT FOUND]', '[Processing...]', 'Normal'
                ) RETURNING id
            """), {
                "tid": current_tenant,
                "dir": direction_hint or "inbox",
                "img": pdf_bytes,
                "mime": resolved_mime or mime_type or "application/pdf",
                "pages": page_count,
                "phone": sender,
                "now": datetime.utcnow(),
            })
            letter_id = result.fetchone()[0]
            diary_number = generate_diary_number(letter_id)
            conn.execute(
                text("UPDATE letterbox SET diary_number = :dn WHERE id = :lid"),
                {"dn": diary_number, "lid": letter_id},
            )
        logger.info("PDF letter saved: id=%s, diary=%s, pages=%s", letter_id, diary_number, page_count)
    except Exception as exc:
        logger.error(f"CRITICAL: Failed to save PDF letter to DB: {exc}")
        try:
            send_whatsapp_message(sender, "Sorry, there was a database error. Please contact support.", _wa_phone_id)
        except Exception:
            pass
        return

    extracted = extract_letter_fields(
        pdf_bytes,
        resolved_mime or mime_type or "application/pdf",
        current_tenant,
        direction_hint=direction_hint,
    )

    try:
        if extracted:
            final_direction = extracted.get("direction", direction_hint or "inbox")
            final_status = "new" if final_direction == "inbox" else "sent"
            with engine.begin() as conn:
                conn.execute(text("""
                    UPDATE letterbox SET
                        direction      = :dir,
                        citizen_name   = :name,
                        village        = :village,
                        phone_number   = :phone,
                        issue_summary  = :subject,
                        category       = :category,
                        urgency_level  = :priority,
                        ocr_text       = :ocr,
                        status         = :status,
                        date_of_letter = :dol
                    WHERE id = :lid
                """), {
                    "dir": final_direction,
                    "name": extracted.get("sender_name", "[NOT FOUND]"),
                    "village": extracted.get("village", "[NOT FOUND]"),
                    "phone": extracted.get("phone_number", "[NOT FOUND]"),
                    "subject": extracted.get("subject", "[NOT FOUND]"),
                    "category": extracted.get("category", "General / Other"),
                    "priority": extracted.get("priority", "Normal"),
                    "ocr": extracted.get("ocr_text", ""),
                    "status": final_status,
                    "dol": extracted.get("date_of_letter") or None,
                    "lid": letter_id,
                })
        else:
            final_direction = direction_hint or "inbox"
            final_status = "sent" if final_direction == "outbox" else "needs_review"
            fallback_summary = "[OCR failed — outbox PDF saved]" if final_direction == "outbox" else "[OCR failed — please review manually]"
            with engine.begin() as conn:
                conn.execute(text("""
                    UPDATE letterbox SET
                        direction = :dir,
                        status = :status,
                        issue_summary = :summary
                    WHERE id = :lid
                """), {
                    "dir": final_direction,
                    "status": final_status,
                    "summary": fallback_summary,
                    "lid": letter_id,
                })
    except Exception as exc:
        logger.error(f"Failed to update PDF letter {letter_id} post-extraction: {exc}")
        final_direction = direction_hint or "inbox"

    try:
        log_letterbox_activity(
            tenant_id=current_tenant,
            letterbox_id=letter_id,
            action_type="created",
            actor_username=sender,
            actor_channel="whatsapp_pa",
            summary=f"WhatsApp PDF saved to {final_direction}",
            details={
                "source": "whatsapp",
                "direction": final_direction,
                "mime_type": resolved_mime or mime_type or "application/pdf",
                "page_count": page_count,
                "sender_phone": sender,
                "ocr_success": bool(extracted),
            },
        )
    except Exception:
        pass

    direction_label = "INBOX" if final_direction == "inbox" else "OUTBOX"
    pages_label = f"{page_count} page{'s' if page_count != 1 else ''}"
    if extracted:
        confirm_msg = (
            f"Saved PDF to {direction_label} — Ref: {diary_number} ({pages_label})\n"
            f"{'Sender' if final_direction == 'inbox' else 'Recipient'}: "
            f"{extracted.get('sender_name', '[Unknown]')}\n"
            f"Category: {extracted.get('category', 'General / Other')}\n"
            f"Summary: {extracted.get('subject', '')[:120]}\n\n"
            f"If direction is wrong: MOVE {diary_number} {'OUT' if final_direction == 'inbox' else 'IN'}"
        )
    else:
        confirm_msg = (
            f"PDF saved to {direction_label} — Ref: {diary_number} ({pages_label})\n"
            f"OCR could not read clearly. Open Letterbox dashboard to review the document."
        )
    try:
        send_whatsapp_message(sender, confirm_msg, _wa_phone_id)
    except Exception as exc:
        logger.warning(f"WhatsApp PDF confirmation failed: {exc}")


_MOVE_PATTERN = re.compile(
    r'^\s*move\s+([\w/]+)\s+(in|out|inbox|outbox)\s*$',
    re.IGNORECASE
)


def _handle_pa_move_command(sender: str, diary_ref: str, direction_str: str, receiver_number: str = ""):
    """
    Background task: PA sent a text command to correct a letter's direction.
    Format: MOVE MP/2026/0042 OUT  or  MOVE 0042 IN

    Only works for registered PA senders. Silently ignored for non-PAs.
    """
    if not receiver_number:
        receiver_number = os.getenv("WHATSAPP_PHONE_NUMBER_ID") or os.getenv("META_PHONE_NUMBER_ID", "")

    current_tenant = _resolve_tenant(receiver_number)
    if current_tenant is None:
        logger.error(
            "_handle_pa_move_command: tenant resolution returned None for receiver=%s — dropping MOVE command",
            receiver_number
        )
        return
    _wa_phone_id = get_tenant_phone_number_id(current_tenant)

    # PA whitelist check
    try:
        with engine.connect() as conn:
            _bare = sender[2:] if sender.startswith("91") and len(sender) == 12 else sender
            pa_row = conn.execute(
                text("SELECT id FROM users WHERE (phone = :phone OR phone = :bare) AND tenant_id = :tid AND is_active = true LIMIT 1"),
                {"phone": sender, "bare": _bare, "tid": current_tenant}
            ).fetchone()
    except Exception as exc:
        logger.error(f"PA check failed in MOVE handler: {exc}")
        return

    if not pa_row:
        # Not a PA — treat the full original message as a citizen grievance instead of silently dropping it.
        # Re-build the original message text (best-effort) so it enters the grievance flow.
        logger.info(f"MOVE command from non-PA {sender} — routing as citizen grievance instead")
        original_message = f"MOVE {diary_ref} {direction_str}"
        _process_incoming_message(sender, original_message, receiver_number)
        return

    new_direction = "outbox" if direction_str.lower() in ("out", "outbox") else "inbox"

    # Normalise diary ref — accept "0042" or "MP/2026/0042"
    ref_upper = diary_ref.upper()
    if "/" not in ref_upper:
        year = datetime.utcnow().year
        ref_upper = f"MP/{year}/{ref_upper.zfill(4)}"

    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("""UPDATE letterbox SET direction = :dir
                        WHERE diary_number = :ref AND tenant_id = :tid
                        AND (is_deleted IS NULL OR is_deleted = false)"""),
                {"dir": new_direction, "ref": ref_upper, "tid": current_tenant}
            )
            if result.rowcount == 0:
                send_whatsapp_message(sender, f"Could not find letter with ref {ref_upper}. Please check the diary number.", _wa_phone_id)
                return
            linked_row = conn.execute(
                text("SELECT id FROM letterbox WHERE diary_number = :ref AND tenant_id = :tid LIMIT 1"),
                {"ref": ref_upper, "tid": current_tenant},
            ).fetchone()
        label = "OUTBOX" if new_direction == "outbox" else "INBOX"
        if linked_row:
            try:
                log_letterbox_activity(
                    tenant_id=current_tenant,
                    letterbox_id=linked_row[0],
                    action_type="direction_changed",
                    actor_username=sender,
                    actor_channel="whatsapp_pa",
                    summary=f"Direction corrected to {label}",
                    details={"direction": new_direction, "diary_number": ref_upper},
                )
            except Exception:
                pass
        send_whatsapp_message(sender, f"Done — {ref_upper} moved to {label}.", _wa_phone_id)
        logger.info(f"MOVE: {ref_upper} → {new_direction} by PA {sender}, tenant {current_tenant}")
    except Exception as exc:
        logger.error(f"MOVE command DB update failed: {exc}")
        try:
            send_whatsapp_message(sender, "Sorry, could not update the letter. Please try again.", _wa_phone_id)
        except Exception:
            pass


def _handle_unsupported_message_type(sender: str, msg_type: str, receiver_number: str = ""):
    """
    Citizen sent a non-text/image message (audio, video, sticker, document, etc.).
    Previously these were silently dropped. Now we send a polite prompt so the
    citizen knows we received something and how to re-send.
    """
    if not receiver_number:
        receiver_number = os.getenv("WHATSAPP_PHONE_NUMBER_ID") or os.getenv("META_PHONE_NUMBER_ID", "")
    current_tenant = _resolve_tenant(receiver_number)
    if current_tenant is None:
        return
    _wa_phone_id = get_tenant_phone_number_id(current_tenant)
    reply = get_unsupported_message_reply("English")
    try:
        send_whatsapp_message(sender, reply, _wa_phone_id)
        logger.info("Unsupported message type '%s' from %s — sent re-send prompt", msg_type, sender)
    except Exception as exc:
        logger.warning("Could not send unsupported-type reply to %s: %s", sender, exc)


def _process_citizen_media_complaint(
    sender: str,
    media_id: str,
    mime_type: str,
    receiver_number: str = "",
    caption: str = "",
    media_type: str = "media",
    msg_id: str = "",
    wa_reply_to_msg_id: str = "",
    inbound_ledger_id: int | None = None,
    existing_case_id: int | None = None,
):
    """
    Citizen sent image/PDF/audio. Download, normalize to grievance text, then
    hand off to the exact same text pipeline used by normal WhatsApp complaints.
    """
    if not receiver_number:
        receiver_number = os.getenv("WHATSAPP_PHONE_NUMBER_ID") or os.getenv("META_PHONE_NUMBER_ID", "")
    current_tenant = _resolve_tenant(receiver_number)
    if current_tenant is None:
        logger.error(
            "_process_citizen_media_complaint: tenant resolution failed receiver=%s sender=%s",
            receiver_number,
            sender,
        )
        return

    _wa_phone_id = get_tenant_phone_number_id(current_tenant)
    try:
        media_bytes, resolved_mime = download_meta_media(media_id)
    except Exception as exc:
        logger.error("Citizen %s download failed for %s media %s: %s", sender, media_type, media_id, exc)
        try:
            send_whatsapp_message(sender, get_unsupported_message_reply("English"), _wa_phone_id)
        except Exception:
            pass
        return

    normalized = normalize_media_complaint(
        media_bytes,
        resolved_mime or mime_type or "application/octet-stream",
        tenant_id=current_tenant,
        media_type=media_type,
        caption=caption,
    )
    if not normalized.ok or not normalized.text:
        logger.warning(
            "Citizen media could not be normalized: sender=%s type=%s error=%s",
            sender,
            media_type,
            normalized.error,
        )
        if media_type in {"image", "document"}:
            fallback_text = (
                caption.strip()
                or f"WhatsApp {media_type} complaint received. Text could not be extracted automatically."
            )
            try:
                case_id = existing_case_id
                with engine.begin() as conn:
                    if not case_id:
                        result = conn.execute(
                            text("""
                                INSERT INTO cases (
                                    tenant_id, user_phone, category, raw_message, status,
                                    case_metadata, is_critical, created_at
                                ) VALUES (
                                    :tid, :phone, 'Document / Attachment Only', :msg, 'incomplete',
                                    :meta, false, :now
                                ) RETURNING id
                            """),
                            {
                                "tid": current_tenant,
                                "phone": sender,
                                "msg": fallback_text,
                                "meta": json.dumps({
                                    "summary": fallback_text[:200],
                                    "wa_msg_id": msg_id,
                                    "source_media": True,
                                    "source_media_type": media_type,
                                    "media_extraction_failed": True,
                                    "media_extraction_error": normalized.error,
                                }),
                                "now": datetime.utcnow(),
                            },
                        )
                        case_id = result.fetchone()[0]
                    else:
                        conn.execute(
                            text("""
                                UPDATE cases
                                SET category = 'Document / Attachment Only',
                                    raw_message = :msg,
                                    status = 'incomplete',
                                    case_metadata = :meta
                                WHERE id = :cid
                            """),
                            {
                                "cid": case_id,
                                "msg": fallback_text,
                                "meta": json.dumps({
                                    "summary": fallback_text[:200],
                                    "wa_msg_id": msg_id,
                                    "source_media": True,
                                    "source_media_type": media_type,
                                    "media_extraction_failed": True,
                                    "media_extraction_error": normalized.error,
                                }),
                            },
                        )

                    existing_media = conn.execute(
                        text("""
                            SELECT id FROM case_media
                            WHERE case_id = :cid AND meta_message_id = :meta_message_id
                            LIMIT 1
                        """),
                        {"cid": case_id, "meta_message_id": msg_id},
                    ).fetchone()
                    if not existing_media:
                        conn.execute(
                            text("""
                                INSERT INTO case_media (
                                    tenant_id, case_id, source, media_type, mime_type,
                                    file_name, media_data, caption, extracted_text,
                                    meta_message_id, created_at
                                ) VALUES (
                                    :tid, :cid, 'whatsapp', :media_type, :mime_type,
                                    :file_name, :media_data, :caption, '',
                                    :meta_message_id, :now
                                )
                            """),
                            {
                                "tid": current_tenant,
                                "cid": case_id,
                                "media_type": media_type,
                                "mime_type": resolved_mime or mime_type or "application/octet-stream",
                                "file_name": f"whatsapp-{media_type}-{msg_id or case_id}",
                                "media_data": media_bytes,
                                "caption": caption,
                                "meta_message_id": msg_id,
                                "now": datetime.utcnow(),
                            },
                        )
                if inbound_ledger_id and case_id:
                    _set_inbound_ledger_case_id(inbound_ledger_id, case_id)
                _fallback_lang = detect_input_language(fallback_text)
                send_whatsapp_message(sender, get_details_request_reply(_fallback_lang, fallback_text), _wa_phone_id)
            except Exception as exc:
                logger.error("Failed to save unreadable citizen media case: %s", exc)
                try:
                    send_whatsapp_message(sender, get_unsupported_message_reply("English"), _wa_phone_id)
                except Exception:
                    pass
            return
        try:
            send_whatsapp_message(sender, get_unsupported_message_reply("English"), _wa_phone_id)
        except Exception:
            pass
        return

    message_body = normalized.text
    if caption.strip() and caption.strip().lower() not in message_body.lower():
        message_body = f"{message_body}\n\nCaption: {caption.strip()}"
    location_hint_parts = [
        part.strip()
        for part in [normalized.mentioned_location_roman, normalized.mentioned_location_original]
        if part and part.strip()
    ]
    location_hint = " / ".join(dict.fromkeys(location_hint_parts))
    resolver_message_body = message_body
    resolver_fallback_message_body = ""
    if location_hint and location_hint.lower() not in message_body.lower():
        resolver_message_body = f"{message_body}\n\nLocation: {location_hint}"
    english_support_text = (getattr(normalized, "english_support_text", "") or "").strip()
    if english_support_text:
        resolver_fallback_message_body = english_support_text
        if location_hint and location_hint.lower() not in resolver_fallback_message_body.lower():
            resolver_fallback_message_body = f"{resolver_fallback_message_body}\n\nLocation: {location_hint}"

    logger.info(
        "Citizen media routed to grievance pipeline: sender=%s tenant=%s type=%s chars=%s",
        sender,
        current_tenant,
        media_type,
        len(message_body),
    )
    media_source = None
    if media_type in {"image", "document", "audio"}:
        media_source = {
            "media_bytes": media_bytes,
            "mime_type": resolved_mime or mime_type or "application/octet-stream",
            "media_type": media_type,
            "caption": caption,
            "extracted_text": normalized.text,
            "raw_transcript": getattr(normalized, "raw_text", "") or normalized.text,
            "english_support_text": getattr(normalized, "english_support_text", "") or "",
            "transcript_provider": getattr(normalized, "transcript_provider", "") or "",
            "normalization_notes": getattr(normalized, "normalization_notes", None),
            "mentioned_location_original": normalized.mentioned_location_original,
            "mentioned_location_roman": normalized.mentioned_location_roman,
            "meta_message_id": msg_id,
        }
    _process_incoming_message(
        sender,
        message_body,
        receiver_number,
        msg_id,
        media_source=media_source,
        language_hint=normalized.extracted_language,
        resolver_message_body=resolver_message_body,
        resolver_fallback_message_body=resolver_fallback_message_body,
        wa_reply_to_msg_id=wa_reply_to_msg_id,
        inbound_ledger_id=inbound_ledger_id,
        existing_case_id=existing_case_id,
    )


# Categories that require human PA review before the AI reply is sent to citizen.
# Cases in these categories are saved with status='pending_review'; the AI-generated
# reply is stored in case_metadata but NOT sent automatically.
# Stored lowercase — compared with category.lower().strip() so GPT variants like
# "Law and Order", "EMERGENCY", or "law and order" all match correctly.
_REVIEW_REQUIRED_CATEGORIES = {"law & order", "law and order", "emergency", "political", "legal"}
_REVIEW_GENERIC_ACK = get_review_ack_reply("English")


def _handle_pa_done_command(sender: str, receiver_number: str = ""):
    """
    PA typed DONE — immediately flush their pending batch without waiting for the timer.
    Silently ignored if sender is not a registered PA or has no pending batch.
    """
    if not receiver_number:
        receiver_number = os.getenv("WHATSAPP_PHONE_NUMBER_ID") or os.getenv("META_PHONE_NUMBER_ID", "")

    current_tenant = _resolve_tenant(receiver_number)
    if current_tenant is None:
        logger.error(
            "_handle_pa_done_command: tenant resolution returned None for receiver=%s — dropping DONE command",
            receiver_number
        )
        return
    _wa_phone_id = get_tenant_phone_number_id(current_tenant)

    # PA whitelist check
    try:
        with engine.connect() as conn:
            _bare = sender[2:] if sender.startswith("91") and len(sender) == 12 else sender
            pa_row = conn.execute(
                text("SELECT id FROM users WHERE (phone = :phone OR phone = :bare) AND tenant_id = :tid AND is_active = true LIMIT 1"),
                {"phone": sender, "bare": _bare, "tid": current_tenant}
            ).fetchone()
    except Exception as exc:
        logger.error(f"PA check failed in DONE handler: {exc}")
        return

    if not pa_row:
        return  # not a PA — fall through silently (message already sent to citizen flow)

    # Check if there's actually a pending batch
    try:
        with engine.connect() as conn:
            batch = conn.execute(text("""
                SELECT id FROM letterbox_batches
                WHERE sender_phone = :phone AND tenant_id = :tid AND status = 'pending'
                LIMIT 1
            """), {"phone": sender, "tid": current_tenant}).fetchone()
    except Exception as exc:
        logger.error(f"Batch check failed in DONE handler: {exc}")
        return

    if not batch:
        try:
            send_whatsapp_message(sender, "No pending letter batch found. Send images first.", _wa_phone_id)
        except Exception:
            pass
        return

    logger.info(f"DONE command from PA {sender} — flushing batch immediately")
    _flush_letter_batch(sender, current_tenant, receiver_number)


# ── Tenant config TTL cache ───────────────────────────────────────────────────
# Avoids a DB round-trip on every incoming message just to read daily_case_limit.
# Cache is per-process, keyed by tenant_id, expires after 5 minutes.
_tenant_config_cache: dict = {}  # {tenant_id: (daily_limit, cached_at)}
_TENANT_CONFIG_TTL = 300  # seconds


def _get_tenant_daily_limit(tenant_id: int) -> int:
    """Return the configured daily case limit for this tenant, using a 5-min TTL cache."""
    _DAILY_LIMIT_DEFAULT = 20
    cached = _tenant_config_cache.get(tenant_id)
    if cached:
        limit_val, cached_at = cached
        if (datetime.utcnow() - cached_at).total_seconds() < _TENANT_CONFIG_TTL:
            return limit_val
    # Cache miss or expired — fetch from DB
    try:
        with engine.connect() as _cfg_conn:
            row = _cfg_conn.execute(
                text("SELECT config FROM tenants WHERE id = :tid LIMIT 1"),
                {"tid": tenant_id},
            ).fetchone()
        limit = _DAILY_LIMIT_DEFAULT
        if row and row[0]:
            cfg = row[0] if isinstance(row[0], dict) else json.loads(row[0] or "{}")
            limit = int(cfg.get("daily_case_limit", _DAILY_LIMIT_DEFAULT))
    except Exception as _cfg_exc:
        logger.warning("Tenant config fetch failed for tenant %s: %s", tenant_id, _cfg_exc)
        limit = _DAILY_LIMIT_DEFAULT
    _tenant_config_cache[tenant_id] = (limit, datetime.utcnow())
    return limit


def _resolve_citizen_reply_language(message_body: str, ai_result: dict | None = None, language_hint: str = "") -> str:
    # 1. An explicit per-number tenant language override always wins.
    hinted_language = normalize_language_name(language_hint, "")
    if hinted_language:
        return hinted_language

    # 2. Trust the rule-based detector ONLY when it is confident (real markers
    #    matched). It is high-precision but cannot enumerate every way citizens
    #    romanize their language, so a non-confident "English"/"Hindi" guess must
    #    not override the LLM's far broader detection.
    rule_lang, rule_confident = detect_input_language_confident(message_body)
    if rule_confident:
        return rule_lang

    # 3. Defer to the language the AI engine resolved (GPT's own detection of the
    #    citizen's romanized/mixed message). Fall back to the rule guess only if
    #    no AI result is available (pre-AI / AI-failure paths).
    ai_lang = normalize_language_name((ai_result or {}).get("detected_language", ""), "")
    return ai_lang or rule_lang


def _resolve_citizen_ack_message(
    *,
    status: str,
    category: str | None,
    detected_language: str,
    message_body: str,
    location_name: str | None = None,
) -> str:
    """
    Return the exact WhatsApp text citizens should receive for intake.

    AI is useful for classification/extraction, but citizen acknowledgments must
    stay deterministic so repeated complaints do not receive different wording.
    """
    normalized_status = str(status or "").lower().strip()

    if normalized_status == "offensive":
        return get_offensive_warning_reply(detected_language, message_body)

    # Greetings are non-grievance but get a warm reply inviting the concern.
    # Checked before status-based branches so a greeting the AI marked
    # 'irrelevant' still gets the greeting reply, not the review acknowledgement.
    if str(category or "").lower().strip() in _GREETING_CATEGORIES:
        return get_greeting_reply(detected_language, message_body)

    if str(category or "").lower().strip() in _SILENT_LOG_CATEGORIES:
        return ""

    if normalized_status == "awaiting_location":
        return get_generic_ack_reply(detected_language, message_body)

    if normalized_status in DETAILS_REQUEST_STATUSES:
        return get_details_request_reply(detected_language, message_body)

    if normalized_status == "irrelevant":
        return get_review_ack_reply(detected_language, message_body)

    if str(category or "").lower().strip() == "personal request":
        return get_personal_request_reply(detected_language, message_body)

    return get_generic_ack_reply(detected_language, message_body)


_CLARIFICATION_DELAY_SECONDS = max(120, int(os.getenv("CITIZEN_CLARIFICATION_DELAY_SECONDS", "150") or "150"))
_clarification_followup_timers: dict[int, threading.Timer] = {}
_clarification_followup_lock = threading.Lock()


def _needs_delayed_clarification(status: str) -> bool:
    normalized = str(status or "").lower().strip()
    return normalized == "awaiting_location" or normalized in DETAILS_REQUEST_STATUSES


def _clarification_kind_for_status(status: str) -> str | None:
    normalized = str(status or "").lower().strip()
    if normalized == "awaiting_location":
        return "missing_location"
    if normalized in DETAILS_REQUEST_STATUSES:
        return "missing_details"
    return None


def _apply_clarification_metadata(
    meta_data: dict,
    *,
    status: str,
    sender: str,
    detected_language: str,
) -> tuple[dict, bool]:
    meta = dict(meta_data or {})
    follow_up_kind = _clarification_kind_for_status(status)
    if not follow_up_kind:
        for key in (
            "clarification_follow_up_pending",
            "clarification_follow_up_sent",
            "clarification_follow_up_kind",
            "clarification_follow_up_after_epoch",
            "clarification_follow_up_sent_at",
            "clarification_follow_up_resolved_at",
        ):
            meta.pop(key, None)
        meta.pop("citizen_phone", None)
        return meta, False

    meta["clarification_follow_up_pending"] = True
    meta["clarification_follow_up_sent"] = False
    meta["clarification_follow_up_kind"] = follow_up_kind
    meta["clarification_follow_up_after_epoch"] = int(_utcnow().timestamp()) + _CLARIFICATION_DELAY_SECONDS
    meta["citizen_phone"] = sender
    meta["clarification_language"] = detected_language
    return meta, True


def _build_clarification_follow_up_message(meta: dict, raw_message: str) -> str:
    detected_language = normalize_language_name(meta.get("clarification_language", ""), "Hindi")
    follow_up_kind = str(meta.get("clarification_follow_up_kind") or "").strip().lower()
    if follow_up_kind == "missing_location":
        location_hint = str(meta.get("matched_value") or "").strip()
        if location_hint:
            return get_awaiting_location_reply(location_hint, detected_language, raw_message)
        return get_missing_location_reply(detected_language, raw_message)
    return get_details_request_reply(detected_language, raw_message)


def _cancel_case_clarification_follow_up(case_id: int | None) -> None:
    if not case_id:
        return
    with _clarification_followup_lock:
        timer = _clarification_followup_timers.pop(int(case_id), None)
    if timer:
        timer.cancel()


def _send_due_case_clarification_followups(case_id: int | None = None) -> None:
    now_epoch = int(_utcnow().timestamp())
    params = {"now_epoch": now_epoch}
    where_case = ""
    if case_id is not None:
        params["case_id"] = int(case_id)
        where_case = "AND id = :case_id"
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(f"""
                    SELECT id, tenant_id, user_phone, raw_message, case_metadata
                    FROM cases
                    WHERE case_metadata::jsonb ->> 'clarification_follow_up_pending' = 'true'
                      AND COALESCE(case_metadata::jsonb ->> 'clarification_follow_up_sent', 'false') <> 'true'
                      AND COALESCE((case_metadata::jsonb ->> 'clarification_follow_up_after_epoch')::bigint, 0) <= :now_epoch
                      AND (is_deleted = false OR is_deleted IS NULL)
                      {where_case}
                    ORDER BY created_at ASC
                    LIMIT 25
                """),
                params,
            ).fetchall()
    except Exception as exc:
        logger.warning("Clarification follow-up sweep failed: %s", exc)
        return

    for row in rows:
        _case_id, _tenant_id, _phone, _raw_message, _meta_raw = row
        try:
            meta = _meta_raw if isinstance(_meta_raw, dict) else json.loads(_meta_raw or "{}")
            reply = _build_clarification_follow_up_message(meta, _raw_message or "")
            _wa_pid = get_tenant_phone_number_id(_tenant_id)
            send_whatsapp_message(_phone, reply, _wa_pid)
            meta["clarification_follow_up_sent"] = True
            meta["clarification_follow_up_sent_at"] = _utcnow().isoformat()
            with engine.begin() as conn:
                conn.execute(
                    text("""
                        UPDATE cases
                        SET case_metadata = :meta
                        WHERE id = :cid
                    """),
                    {"meta": json.dumps(meta), "cid": _case_id},
                )
            _cancel_case_clarification_follow_up(_case_id)
            logger.info("Clarification follow-up sent for case %s", _case_id)
        except Exception as exc:
            logger.warning("Clarification follow-up send failed for case %s: %s", _case_id, exc)


def _schedule_case_clarification_follow_up(case_id: int | None, delay_seconds: int | None = None) -> None:
    if not case_id:
        return
    _cancel_case_clarification_follow_up(case_id)
    delay = max(5, int(delay_seconds or _CLARIFICATION_DELAY_SECONDS))
    timer = threading.Timer(delay, _send_due_case_clarification_followups, args=(int(case_id),))
    timer.daemon = True
    with _clarification_followup_lock:
        _clarification_followup_timers[int(case_id)] = timer
    timer.start()


def _run_citizen_case_enrichment(
    *,
    sender: str,
    message_body: str,
    resolver_message_body: str | None,
    resolver_fallback_message_body: str | None,
    current_tenant: int,
    language_hint: str,
    media_source: dict | None = None,
    thread_context: str = "",
) -> dict:
    user_context = get_user_context(sender)
    context_parts: list[str] = []
    if user_context:
        context_parts.append(user_context)
    if thread_context:
        context_parts.append(
            "PRIOR COMPLAINTS FROM THIS CITIZEN (same 24h thread):\n"
            + thread_context
            + "\n\nUse this context to improve classification — if the new message "
            "continues or references a prior complaint, align the category and domain accordingly."
        )
    full_context = "\n\n".join(context_parts)
    full_prompt = (
        f"{full_context}\n\nUSER MESSAGE: {message_body}"
        if full_context
        else f"USER MESSAGE: {message_body}"
    )
    ai_result = ask_chatgpt_agent(full_prompt, tenant_id=current_tenant)

    if isinstance(ai_result, str):
        try:
            ai_result = json.loads(ai_result)
        except Exception:
            ai_result = {"status": "INCOMPLETE", "political_response": ai_result, "grievance_data": {}}

    grievance = ai_result.get("grievance_data", {}) or {}
    status = str(ai_result.get("status", "new")).lower()
    detected_language = _resolve_citizen_reply_language(message_body, ai_result, language_hint)
    problem_domain = grievance.get("problem_domain")
    problem_subdomain = grievance.get("problem_subdomain")
    convergence_program_type = grievance.get("convergence_program_type")
    categories = grievance.get("categories", [problem_domain] if problem_domain else [])
    category = (
        ai_result.get("case_category")
        or problem_domain
        or (categories[0] if isinstance(categories, list) and categories else None)
        or "Uncategorised"
    )
    is_personal_request = str(category or "").lower().strip() == "personal request"

    _emergency_keyword_match = False
    try:
        from modules.emergency_keywords import detect_emergency_severity
        _emergency_keyword_match = detect_emergency_severity(message_body)
    except Exception as _em_kw_exc:
        logger.warning("Emergency keyword detection failed (non-blocking): %s", _em_kw_exc)

    is_emergency_complaint = bool(
        ai_result.get("is_critical", False) or status == "emergency" or _emergency_keyword_match
    )
    if is_emergency_complaint:
        category = "Emergency"
        if isinstance(categories, list):
            categories = ["Emergency", *[c for c in categories if c != "Emergency"]]
        else:
            categories = ["Emergency"]

    # ── Deterministic intent safety net ──────────────────────────────────────
    # Personal-request / silent-log routing must NOT depend on the AI engine's
    # internal status gates or on its JSON parsing succeeding. ask_chatgpt_agent
    # runs these same detectors, but if it raised and fell back to a generic-ack
    # default, or a status gate skipped them, the citizen would wrongly get the
    # generic acknowledgement. Re-check the actual transcript here so private/
    # discretionary asks reliably get the office-contact reply. Emergencies always
    # take precedence and are never reclassified.
    if not is_emergency_complaint:
        try:
            _intent_blob = (message_body or "").lower()
            if not is_personal_request and infer_personal_request_category(_intent_blob):
                category = "Personal Request"
                is_personal_request = True
                if str(status).lower() == "awaiting_location":
                    status = "new"
            else:
                _silent_category = infer_silent_log_category(_intent_blob)
                if _silent_category and str(category or "").lower().strip() not in {"personal request"}:
                    category = _silent_category
                    if str(status).lower() == "awaiting_location":
                        status = "new"
        except Exception as _intent_exc:
            logger.warning("Intent safety-net check failed (non-blocking): %s", _intent_exc)

    # Civic grievances must never be swallowed by the no-reply "silent log"
    # lane. The AI/tone detector can occasionally label terse complaints as
    # media/support traffic, but deterministic civic rules are higher authority
    # for the final category that drives acknowledgement sending.
    if not is_emergency_complaint and not is_personal_request and str(status).lower() != "offensive":
        try:
            _civic_rule = apply_civic_rules(message_body or "")
            if _civic_rule:
                _civic_fields = build_taxonomy_fields(
                    problem_domain=_civic_rule.get("problem_domain"),
                    problem_subdomain=_civic_rule.get("problem_subdomain"),
                    raw_text=message_body or "",
                    scheme=grievance.get("scheme"),
                    department=grievance.get("department"),
                )
                grievance.update(_civic_fields)
                problem_domain = _civic_fields.get("problem_domain")
                problem_subdomain = _civic_fields.get("problem_subdomain")
                convergence_program_type = _civic_fields.get("convergence_program_type")
                categories = _civic_fields.get("categories", [problem_domain] if problem_domain else [])
                category = problem_domain or category
                if str(status).lower() == "irrelevant":
                    status = "new"
        except Exception as _civic_exc:
            logger.warning("Civic category reconciliation failed (non-blocking): %s", _civic_exc)

    political_reply = ai_result.get("political_response", get_generic_ack_reply(detected_language, message_body))
    ai_language = normalize_language_name(ai_result.get("detected_language", ""), "")
    if language_hint and ai_language and ai_language != detected_language:
        political_reply = get_generic_ack_reply(detected_language, message_body)

    geo_decision = _finalize_whatsapp_geography_decision(
        grievance=grievance,
        ai_result=ai_result,
        status=status,
        political_reply=political_reply,
        detected_language=detected_language,
        message_body=message_body,
        resolver_message_body=resolver_message_body,
        resolver_fallback_message_body=resolver_fallback_message_body,
        current_tenant=current_tenant,
        is_emergency_complaint=is_emergency_complaint,
        location_required=False if is_personal_request else location_required_for_domain(category),
    )
    grievance = geo_decision["grievance"]
    status = geo_decision["status"]
    political_reply = geo_decision["political_reply"]
    location_name = geo_decision["location_name"]
    final_constituency = geo_decision["final_constituency"]
    citizen_ack_message = _resolve_citizen_ack_message(
        status=status,
        category=category,
        detected_language=detected_language,
        message_body=message_body,
        location_name=location_name,
    )

    # TEMP DIAGNOSTIC (grep: INTENT_DIAG) — remove once voice-note intent routing
    # is verified in production. Ties the message source to the final ack decision.
    logger.info(
        "INTENT_DIAG source=%s media_type=%s status=%s category=%s is_personal=%s ack=%r msg=%r",
        "media" if media_source else "text",
        media_source.get("media_type") if media_source else "",
        status,
        category,
        is_personal_request,
        (citizen_ack_message or "")[:120],
        (message_body or "")[:240],
    )

    if location_name and not final_constituency:
        lookup_key = str(location_name).lower().strip()
        combined_geo = {}
        try:
            geo_map = get_geo_overrides(current_tenant)
            combined_geo.update(geo_map)
        except Exception:
            logger.warning("Geo override lookup failed for tenant %s", current_tenant)

        try:
            import glob as _glob
            tenant_const = None
            try:
                from sansadx_backend.db import SessionLocal as _SL2, Tenant as _T2
                _db2 = _SL2()
                try:
                    _t2 = _db2.query(_T2).filter(_T2.id == current_tenant).first()
                    if _t2:
                        tenant_const = _t2.constituency
                finally:
                    _db2.close()
            except Exception:
                pass

            if tenant_const:
                for base in ["data/geography", "/app/data/geography"]:
                    const_dir = os.path.join(base, tenant_const)
                    if not os.path.isdir(const_dir):
                        if os.path.isdir(base):
                            for d in os.listdir(base):
                                if d.lower() == tenant_const.lower() and os.path.isdir(os.path.join(base, d)):
                                    const_dir = os.path.join(base, d)
                                    break
                            else:
                                continue
                        else:
                            continue

                    for fpath in _glob.glob(os.path.join(const_dir, "*.json")):
                        assembly_name = os.path.splitext(os.path.basename(fpath))[0]
                        try:
                            with open(fpath, "r") as gf:
                                stations = json.load(gf)
                            if isinstance(stations, list):
                                for station in stations:
                                    if isinstance(station, dict):
                                        loc = station.get("locality", "").strip()
                                        if loc and loc not in combined_geo:
                                            combined_geo[loc] = assembly_name
                        except Exception:
                            pass
                    break
        except Exception as e:
            logger.warning(f"Geography file scan failed in main.py: {e}")

        combined_lower = {k.lower(): v for k, v in combined_geo.items()}
        final_constituency = combined_lower.get(lookup_key)
        if not final_constituency:
            import re as _re
            for geo_key, geo_val in combined_lower.items():
                if len(geo_key) >= 4:
                    word_pattern = r'\b' + _re.escape(geo_key) + r'\b'
                    if _re.search(word_pattern, lookup_key):
                        final_constituency = geo_val
                        break
        if not final_constituency:
            best_match = None
            best_match_len = 0
            for geo_key, geo_val in combined_lower.items():
                if len(geo_key) >= 5 and geo_key in lookup_key and len(geo_key) > best_match_len:
                    best_match = geo_val
                    best_match_len = len(geo_key)
                    best_match_key = geo_key
            if best_match:
                final_constituency = best_match
        if not final_constituency and len(lookup_key) >= 5:
            import difflib
            candidate_keys = [
                k for k in combined_lower.keys()
                if len(k) >= 5 and 0.7 <= len(k)/len(lookup_key) <= 1.3
            ]
            if candidate_keys:
                matches = difflib.get_close_matches(lookup_key, candidate_keys, n=1, cutoff=0.85)
                if matches:
                    final_constituency = combined_lower[matches[0]]

    raw_summary = (grievance.get("summary") or "").strip()
    fallback_summary = ""
    if not raw_summary or raw_summary.lower() == (message_body or "").strip().lower():
        summary_bits = []
        if problem_domain and str(problem_domain).lower() not in {"general", "uncategorised"}:
            summary_bits.append(str(problem_domain))
        if problem_subdomain:
            summary_bits.append(str(problem_subdomain))
        if location_name:
            summary_bits.append(f"location {location_name}")
        if final_constituency and final_constituency != "Unknown":
            summary_bits.append(f"assembly {final_constituency}")
        if grievance.get("person"):
            summary_bits.append(f"mentions {grievance.get('person')}")
        if grievance.get("department"):
            summary_bits.append(f"department {grievance.get('department')}")
        if grievance.get("scheme"):
            summary_bits.append(f"scheme {grievance.get('scheme')}")
        if summary_bits:
            fallback_summary = f"Case classified as {' · '.join(summary_bits)}."
    effective_summary = raw_summary or fallback_summary or message_body[:100]

    meta_data = {
        "detected_language": detected_language,
        "language": detected_language,
        "user_intent": status,
        "location_resolved": bool(location_name and final_constituency != "Unknown"),
        "matched_value": location_name or "",
        "assembly_constituency": final_constituency,
        "geography_confidence": grievance.get("geography_confidence", "unknown"),
        "geography_source": grievance.get("geography_source", "unknown"),
        "geography_locked": bool(grievance.get("geography_locked")),
        "needs_geography_review": bool(grievance.get("needs_geography_review")),
        "geography_review_reason": grievance.get("geography_review_reason", ""),
        "geography_diagnostics": grievance.get("geography_diagnostics", {}),
        "summary": effective_summary,
        "ai_category": problem_domain,
        "ai_subcategory": problem_subdomain,
        "ai_confidence": grievance.get("ai_confidence"),
        "categories": categories if isinstance(categories, list) else [category],
        "problem_domain": problem_domain,
        "problem_subdomain": problem_subdomain,
        "convergence_program_type": convergence_program_type,
        "person": grievance.get("person"),
        "department": grievance.get("department"),
        "scheme": grievance.get("scheme"),
        "source_media": bool(media_source),
        "source_media_type": media_source.get("media_type") if media_source else "",
        "source_media_caption": media_source.get("caption", "") if media_source else "",
        "source_media_raw_transcript": media_source.get("raw_transcript", "") if media_source else "",
        "source_media_english_support_text": media_source.get("english_support_text", "") if media_source else "",
        "source_media_transcript_provider": media_source.get("transcript_provider", "") if media_source else "",
        "source_media_normalization_notes": media_source.get("normalization_notes") if media_source else None,
        "is_silent_log_category": str(category or "").lower().strip() in _SILENT_LOG_CATEGORIES,
        "contact_thread_started_at": _utcnow().isoformat(),
        "contact_thread_last_activity_at": _utcnow().isoformat(),
        "contact_thread_state": "normal",
        "distinct_issue_count": 1,
        "contact_intake_action": "new_case",
    }

    return {
        "ai_result": ai_result,
        "grievance": grievance,
        "status": status,
        "detected_language": detected_language,
        "problem_domain": problem_domain,
        "problem_subdomain": problem_subdomain,
        "convergence_program_type": convergence_program_type,
        "categories": categories,
        "category": category,
        "is_personal_request": is_personal_request,
        "is_emergency_complaint": is_emergency_complaint,
        "emergency_keyword_match": _emergency_keyword_match,
        "political_reply": political_reply,
        "location_name": location_name,
        "final_constituency": final_constituency,
        "citizen_ack_message": citizen_ack_message,
        "meta_data": meta_data,
    }


def _save_case_enrichment_and_respond(
    *,
    case_id: int,
    sender: str,
    current_tenant: int,
    message_body: str,
    wa_phone_id: str,
    enrichment: dict,
    raw_message_override: str | None = None,
    citizen_ack_override: str | None = None,
) -> None:
    status = enrichment["status"]
    category = enrichment["category"]
    detected_language = enrichment["detected_language"]
    reply_text = citizen_ack_override if citizen_ack_override is not None else enrichment["citizen_ack_message"]
    meta_data, clarification_needed = _apply_clarification_metadata(
        enrichment["meta_data"],
        status=status,
        sender=sender,
        detected_language=detected_language,
    )
    meta_data.pop("contact_buffer_release_status", None)
    meta_data.pop("contact_buffer_ack_message", None)
    meta_data.pop("contact_release_after_epoch", None)
    meta_data.pop("contact_buffer_root_case_id", None)
    meta_data.pop("contact_buffered", None)
    meta_data.pop("contact_buffer_overflow_flagged", None)
    meta_data["contact_buffer_released_at"] = _utcnow().isoformat()
    meta_data["citizen_ack_sent"] = bool(reply_text)
    meta_data["citizen_ack_last_action"] = meta_data.get("contact_intake_action") or "unknown"
    enrichment["meta_data"] = meta_data

    try:
        sql = """
            UPDATE cases
            SET category = :cat,
                problem_domain = :problem_domain,
                problem_subdomain = :problem_subdomain,
                convergence_program_type = :convergence_program_type,
                status = :stat,
                case_metadata = :meta,
                is_critical = :crit
        """
        params = {
            "cat": category,
            "problem_domain": enrichment["problem_domain"],
            "problem_subdomain": enrichment["problem_subdomain"],
            "convergence_program_type": enrichment["convergence_program_type"],
            "stat": status,
            "meta": json.dumps(meta_data),
            "crit": enrichment["is_emergency_complaint"],
            "cid": case_id,
        }
        if raw_message_override is not None:
            sql += ", raw_message = :raw_message"
            params["raw_message"] = raw_message_override
        sql += " WHERE id = :cid"

        with engine.begin() as conn:
            conn.execute(text(sql), params)
            logger.info("AI updated case %s: status='%s' category='%s' constituency='%s'", case_id, status, category, enrichment["final_constituency"])
    except Exception as e:
        logger.error(f"DB update failed for case {case_id}: {e}")

    _is_critical_case = enrichment["is_emergency_complaint"]
    if _is_critical_case or status == "emergency" or enrichment["emergency_keyword_match"]:
        try:
            from modules.emergency_intake import process_emergency_case
            process_emergency_case(
                case_id=case_id,
                tenant_id=current_tenant,
                message_body=message_body,
                sender_phone=sender,
                assembly=enrichment["final_constituency"],
                ward=None,
                category=category,
                problem_domain=enrichment["problem_domain"] or "",
                status=status,
            )
        except Exception as _em_exc:
            logger.warning("Emergency intake failed (non-blocking): %s", _em_exc)

    _is_review_category = category.lower().strip() in _REVIEW_REQUIRED_CATEGORIES
    _is_silent_log_category = category.lower().strip() in _SILENT_LOG_CATEGORIES
    if (_is_review_category or _is_critical_case) and status not in ("awaiting_location",):
        try:
            with engine.begin() as _rv_conn:
                _rv_meta = {**meta_data, "ai_reply_pending_review": enrichment["political_reply"]}
                _rv_conn.execute(
                    text("""
                        UPDATE cases
                        SET status = 'pending_review', case_metadata = :meta
                        WHERE id = :cid
                    """),
                    {"meta": json.dumps(_rv_meta), "cid": case_id}
                )
        except Exception as _rv_exc:
            logger.error("Failed to set pending_review status for case %s: %s", case_id, _rv_exc)

        if _is_critical_case:
            _cancel_case_clarification_follow_up(case_id)
            return

        if reply_text:
            try:
                send_whatsapp_message(sender, reply_text, wa_phone_id)
            except Exception as _rv_send_exc:
                logger.error("Failed to send review ack to %s (case=%s): %s", sender, case_id, _rv_send_exc)
                try:
                    with engine.begin() as _ack_conn:
                        _ack_conn.execute(
                            text("""
                                UPDATE cases
                                SET case_metadata = case_metadata || :patch::jsonb
                                WHERE id = :cid
                            """),
                            {"patch": json.dumps({"citizen_ack_pending": True, "citizen_phone": sender}), "cid": case_id},
                        )
                except Exception as _ack_flag_exc:
                    logger.error("Failed to set citizen_ack_pending flag on case %s: %s", case_id, _ack_flag_exc)
        _cancel_case_clarification_follow_up(case_id)
        return

    if _is_silent_log_category and status != "offensive":
        _cancel_case_clarification_follow_up(case_id)
        return

    try:
        if reply_text:
            send_whatsapp_message(sender, reply_text, wa_phone_id)
    except Exception as send_exc:
        logger.error(
            "WHATSAPP_SEND_FAILED: could not reply to %s (case=%s) — %s. "
            "Check META_ACCESS_TOKEN and per-tenant Phone Number ID configuration.",
            sender, case_id, send_exc,
        )

    if clarification_needed:
        _schedule_case_clarification_follow_up(case_id)
    else:
        _cancel_case_clarification_follow_up(case_id)


def _buffer_distinct_contact_case(
    *,
    sender: str,
    message_body: str,
    current_tenant: int,
    wa_phone_id: str,
    language_hint: str,
    resolver_message_body: str | None,
    resolver_fallback_message_body: str | None,
    root_case: dict | None,
    media_source: dict | None = None,
) -> bool:
    enrichment = _run_citizen_case_enrichment(
        sender=sender,
        message_body=message_body,
        resolver_message_body=resolver_message_body,
        resolver_fallback_message_body=resolver_fallback_message_body,
        current_tenant=current_tenant,
        language_hint=language_hint,
        media_source=media_source,
    )

    if enrichment["is_emergency_complaint"]:
        return False

    buffered_case_id = None
    release_after_epoch = _buffered_release_epoch(root_case)
    meta_data = dict(enrichment["meta_data"] or {})
    meta_data["contact_buffered"] = True
    meta_data["contact_buffer_root_case_id"] = root_case.get("id") if root_case else None
    meta_data["contact_release_after_epoch"] = release_after_epoch
    meta_data["contact_buffer_release_status"] = enrichment["status"]
    meta_data["contact_buffer_ack_message"] = enrichment["citizen_ack_message"]
    meta_data.setdefault("contact_message_events", [])

    try:
        with engine.begin() as conn:
            result = conn.execute(
                text(
                    """
                    INSERT INTO cases
                        (tenant_id, user_phone, category, raw_message, status, case_metadata,
                         is_critical, created_at, problem_domain, problem_subdomain,
                         convergence_program_type)
                    VALUES
                        (:tid, :phone, :cat, :msg, :status, :meta,
                         false, :now, :problem_domain, :problem_subdomain,
                         :convergence_program_type)
                    RETURNING id
                    """
                ),
                {
                    "tid": current_tenant,
                    "phone": sender,
                    "cat": enrichment["category"],
                    "msg": message_body,
                    "status": _CONTACT_BUFFER_STATUS,
                    "meta": json.dumps(meta_data),
                    "now": _utcnow(),
                    "problem_domain": enrichment["problem_domain"],
                    "problem_subdomain": enrichment["problem_subdomain"],
                    "convergence_program_type": enrichment["convergence_program_type"],
                },
            )
            row = result.fetchone()
            buffered_case_id = row[0] if row else None
        logger.info(
            "Buffered distinct citizen complaint for delayed release: case=%s root_case=%s sender=%s tenant=%s release_after=%s",
            buffered_case_id,
            root_case.get("id") if root_case else None,
            sender,
            current_tenant,
            release_after_epoch,
        )
        _schedule_buffered_release(buffered_case_id, release_after_epoch)
    except Exception as exc:
        logger.error("Failed to create buffered contact case for %s/%s: %s", current_tenant, sender, exc)
        return False

    return True


def _process_incoming_message(
    sender: str,
    message_body: str,
    receiver_number: str = "",
    msg_id: str = "",
    media_source: dict | None = None,
    language_hint: str = "",
    resolver_message_body: str | None = None,
    resolver_fallback_message_body: str | None = None,
    wa_reply_to_msg_id: str = "",
    inbound_ledger_id: int | None = None,
    existing_case_id: int | None = None,
):
    """Background task: AI processing + DB save + reply. Runs after 200 is returned to Meta."""
    if not receiver_number:
        receiver_number = os.getenv("WHATSAPP_PHONE_NUMBER_ID") or os.getenv("META_PHONE_NUMBER_ID", "")
    current_tenant = _resolve_tenant(receiver_number)
    if current_tenant is None:
        logger.error(
            "_process_incoming_message: tenant resolution returned None for receiver=%s sender=%s — dropping message",
            receiver_number, sender
        )
        return
    _wa_phone_id = get_tenant_phone_number_id(current_tenant)

    resolver_message_body = resolver_message_body or message_body
    resolver_fallback_message_body = resolver_fallback_message_body or ""

    logger.info(f"Incoming from {sender} → Tenant {current_tenant}")
    sender_digits = re.sub(r"\D", "", sender or "")
    sender_bare = sender_digits[2:] if sender_digits.startswith("91") and len(sender_digits) == 12 else sender_digits

    # ── Staff query routing (check BEFORE spam / citizen flow) ───────────────
    # If the sender's phone is a registered staff user for this tenant,
    # treat their message as a case query, not a citizen grievance.
    # Uses the same users.phone lookup as the PA letter intake system.
    staff_row = _get_registered_staff_sender(sender, current_tenant)

    if staff_row:
        logger.info(
            "Staff message from %s (user_id=%s, tenant=%s): %r",
            sender, staff_row["id"], current_tenant, message_body[:80],
        )

        # Check for emergency cluster acknowledgment (ACK <id> or ACK)
        try:
            from modules.emergency_intake import handle_pa_acknowledgment
            if handle_pa_acknowledgment(sender, current_tenant, message_body):
                send_whatsapp_message(sender, "✅ Emergency alert acknowledged.", _wa_phone_id)
                return
        except Exception as _ack_exc:
            logger.warning("PA ACK check failed (non-blocking): %s", _ack_exc)

        try:
            parsed_schedule = parse_staff_schedule_message(message_body)
        except Exception as _schedule_exc:
            logger.warning("Staff schedule parse failed (non-blocking): %s", _schedule_exc)
            parsed_schedule = None

        if parsed_schedule:
            created_item = _save_staff_schedule_entry(
                current_tenant,
                staff_row.get("username") or staff_row.get("display_name") or sender,
                parsed_schedule,
            )
            if created_item:
                send_whatsapp_message(
                    sender,
                    _format_staff_schedule_confirmation(created_item),
                    _wa_phone_id,
                )
                return
            send_whatsapp_message(
                sender,
                "⚠️ I understood that as a schedule item, but could not save it. Please try again.",
                _wa_phone_id,
            )
            return

        try:
            filters  = parse_query(message_body, tenant_id=current_tenant)
            # Only ask for clarification if query has NO filters at all
            # (no location, no constituency, no status, no issue_type, and default 7-day window
            #  with a message that looks too short/generic to be intentional)
            has_any_filter = (
                filters.get("location") or
                filters.get("constituency") or
                filters.get("status") or
                filters.get("issue_type") or
                filters.get("days", 7) != 7 or
                len(message_body.strip()) > 10
            )
            if not has_any_filter:
                reply = format_clarification_request()
            else:
                result = query_cases(filters, tenant_id=current_tenant)
                reply  = format_cases_for_whatsapp(result)
        except Exception as _qe:
            logger.error("Case query pipeline error: %s", _qe)
            reply = "⚠️ Something went wrong processing your query. Please try again."
        send_whatsapp_message(sender, reply, _wa_phone_id)
        return  # Do NOT fall through to citizen grievance flow

    # ── Content-based dedup (citizens only — staff already returned above) ───
    # Same sender + same text within 10 min = duplicate re-send, ignore it.
    # Allowlisted test numbers are exempt so repeated test sends are not dropped.
    if not _is_spam_exempt(sender):
        try:
            with engine.connect() as _dd_conn:
                _dup = _dd_conn.execute(
                    text("""
                        SELECT 1 FROM cases
                        WHERE user_phone = :phone
                          AND raw_message = :body
                          AND created_at >= NOW() - INTERVAL '10 minutes'
                        LIMIT 1
                    """),
                    {"phone": sender, "body": message_body},
                ).fetchone()
            if _dup:
                logger.info("Content dedup: identical message from %s within 10 min — ignored", sender)
                return
        except Exception as _ce:
            logger.warning("Content dedup check failed (non-blocking): %s", _ce)

    # ── Spam / abuse detection (pre-AI, no token cost) ───────────
    # Allowlisted test numbers skip the frequency-based coordinated-flood check
    # but still have content-based abuse detection applied.
    _spam_exempt = _is_spam_exempt(sender)
    is_abuse, abuse_reason = _is_abusive(message_body)
    is_flood, flood_reason = (
        (False, "") if _spam_exempt
        else _is_coordinated_flood(message_body, current_tenant)
    )

    if is_abuse or is_flood:
        flag_type   = "abuse_keyword"    if is_abuse else "coordinated_flood"
        flag_reason = abuse_reason       if is_abuse else flood_reason
        spam_cat    = "Spam (Offensive)" if is_abuse else "Spam"
        _detected_lang = detect_input_language(message_body)
        _reply_text = (
            get_offensive_warning_reply(_detected_lang, message_body)
            if is_abuse
            else get_review_ack_reply(_detected_lang, message_body)
        )
        logger.warning(f"Spam flag [{flag_type}] from {sender}: {flag_reason}")

        try:
            with engine.begin() as conn:
                conn.execute(
                    text("""
                        INSERT INTO cases
                            (tenant_id, user_phone, category, raw_message,
                             status, case_metadata, is_critical, created_at)
                        VALUES (:tid, :phone, :cat, :msg,
                                :status, :meta, false, :now)
                    """),
                    {
                        "tid":   current_tenant,
                        "phone": sender,
                        "cat":   spam_cat,
                        "msg":   message_body,
                        "status": "offensive" if is_abuse else "new",
                        "meta":  json.dumps({"spam_flagged": True, "flag_reason": flag_reason}),
                        "now":   datetime.utcnow(),
                    },
                )
            logger.info(f"Saved spam case: category='{spam_cat}' tenant={current_tenant}")
        except Exception as exc:
            logger.error(f"Spam case DB save failed: {exc}")

        _save_spam_flag(current_tenant, sender, flag_type, flag_reason, message_body)
        if is_abuse:
            send_whatsapp_message(
                sender,
                _reply_text,
                _wa_phone_id,
            )
        return

    # ── Per-phone daily case creation rate limit ─────────────────────────────
    # Prevents fake-complaint floods: default 20 cases/phone/day, configurable
    # via tenant.config["daily_case_limit"].
    #
    # Tenant config is fetched once and cached per-process for 5 minutes.
    # This eliminates one DB round-trip on every single incoming message without
    # sacrificing responsiveness to admin config changes (max 5 min stale).
    _DAILY_LIMIT_DEFAULT = 20
    try:
        _daily_limit = _get_tenant_daily_limit(current_tenant)

        with engine.connect() as _cnt_conn:
            _count_row = _cnt_conn.execute(
                text("""
                    SELECT COUNT(*) FROM cases
                    WHERE user_phone = :phone
                      AND tenant_id = :tid
                      AND created_at >= NOW() - INTERVAL '24 hours'
                      AND category NOT IN ('Spam', 'Spam (Offensive)')
                """),
                {"phone": sender, "tid": current_tenant}
            ).fetchone()
        _today_count = _count_row[0] if _count_row else 0

        # Allowlisted test numbers are exempt from the per-phone daily limit.
        if not _spam_exempt and _today_count >= _daily_limit:
            logger.warning(
                "Per-phone rate limit hit: phone=%s tenant=%s count=%d limit=%d",
                sender, current_tenant, _today_count, _daily_limit
            )
            with engine.begin() as _spam_r_conn:
                _spam_r_conn.execute(
                    text("""
                        INSERT INTO cases
                            (tenant_id, user_phone, category, raw_message,
                             status, case_metadata, is_critical, is_deleted, created_at)
                        VALUES (:tid, :phone, 'Spam', :msg,
                                'new', :meta, false, false, :now)
                    """),
                    {
                        "tid": current_tenant, "phone": sender, "msg": message_body,
                        "meta": json.dumps({"spam_flagged": True, "flag_reason": f"Daily limit {_daily_limit} exceeded ({_today_count} today)", "wa_msg_id": msg_id}),
                        "now": datetime.utcnow(),
                    }
                )
            _detected_lang = detect_input_language(message_body)
            send_whatsapp_message(
                sender,
                get_rate_limit_reply(_detected_lang, message_body),
                _wa_phone_id,
            )
            return
    except Exception as _rate_exc:
        logger.warning("Per-phone rate limit check failed (non-blocking): %s", _rate_exc)

    # ── INTERCEPT: clarification follow-up on an existing case ─────────────────
    # If this sender has a recent case that is still waiting on location or
    # more detail, treat the next inbound message as clarification and enrich
    # the original case instead of creating a second complaint row.
    _pending = get_pending_incomplete_case(sender, current_tenant)
    if _pending:
        _followup_text = message_body.strip()
        _pending_meta = dict(_pending["meta"] or {})
        _followup_kind = str(_pending_meta.get("clarification_follow_up_kind") or "").strip().lower()
        _combined_message = (_pending.get("raw_message") or "").strip()
        if _combined_message:
            _combined_message += f"\n\nAdditional citizen clarification: {_followup_text}"
        else:
            _combined_message = _followup_text

        _resolver_followup = resolver_message_body.strip()
        if _followup_kind == "missing_location":
            _resolver_combined = f"{_combined_message}\n\nLocation: {_resolver_followup or _followup_text}"
        else:
            _resolver_combined = _combined_message

        try:
            enrichment = _run_citizen_case_enrichment(
                sender=sender,
                message_body=_combined_message,
                resolver_message_body=_resolver_combined,
                resolver_fallback_message_body=resolver_fallback_message_body,
                current_tenant=current_tenant,
                language_hint=language_hint,
            )
            enrichment["meta_data"]["clarification_source_case_id"] = _pending["id"]
            enrichment["meta_data"]["clarification_reply_text"] = _followup_text[:500]
            enrichment["meta_data"]["clarification_reply_at"] = _utcnow().isoformat()
            enrichment["meta_data"]["contact_intake_action"] = "clarification_reply"

            _ack_override = None
            if _followup_kind == "missing_location" and enrichment.get("location_name") and enrichment.get("final_constituency") not in {None, "", "Unknown"}:
                _ack_override = get_location_update_reply(
                    enrichment["location_name"],
                    enrichment["detected_language"],
                    _followup_text,
                )

            _save_case_enrichment_and_respond(
                case_id=_pending["id"],
                sender=sender,
                current_tenant=current_tenant,
                message_body=_combined_message,
                wa_phone_id=_wa_phone_id,
                enrichment=enrichment,
                raw_message_override=_combined_message,
                citizen_ack_override=_ack_override,
            )
            return
        except Exception as _followup_exc:
            logger.error("Failed to process clarification follow-up for case %s: %s", _pending["id"], _followup_exc)

    recent_contact_cases = _recent_contact_thread_cases(sender, current_tenant)
    recent_thread_groups = _group_recent_contact_thread_cases(recent_contact_cases)
    active_thread = recent_thread_groups[0] if recent_thread_groups else None

    if active_thread and active_thread.get("latest_case"):
        root_contact_case = active_thread["latest_case"]
        root_meta = _parse_case_meta(root_contact_case.get("case_metadata"))
        archived_items = list(root_meta.get("contact_thread_items") or [])

        # Gracefully keep the old metadata-only thread path for already-open legacy threads.
        if len(active_thread["cases"]) == 1 and archived_items:
            current_issue = _thread_issue_from_row(root_contact_case)
            now_iso = _utcnow().isoformat()

            if _is_low_information_followup(message_body):
                logger.info(
                    "Contact-thread low-information follow-up ignored on legacy case %s for sender=%s tenant=%s",
                    root_contact_case["id"],
                    sender,
                    current_tenant,
                )
                _append_contact_message_event(
                    root_contact_case["id"],
                    message_body,
                    event_type="low_information_noise",
                    detected_language=language_hint,
                )
                return

            current_score = _thread_issue_similarity(message_body, current_issue)
            best_archived_index = -1
            best_archived_score = 0.0
            for idx, item in enumerate(archived_items):
                score = _thread_issue_similarity(message_body, item)
                if score > best_archived_score:
                    best_archived_score = score
                    best_archived_index = idx

            if current_score >= _CONTACT_BUFFER_SIMILARITY or best_archived_score >= _CONTACT_BUFFER_SIMILARITY:
                if best_archived_score > current_score and best_archived_index >= 0:
                    logger.info(
                        "Contact-thread follow-up promoted archived issue on legacy case %s for sender=%s tenant=%s",
                        root_contact_case["id"],
                        sender,
                        current_tenant,
                    )
                    _promote_archived_thread_issue(root_contact_case, best_archived_index, message_body, language_hint)
                else:
                    logger.info(
                        "Contact-thread duplicate merged into current legacy issue on case %s for sender=%s tenant=%s",
                        root_contact_case["id"],
                        sender,
                        current_tenant,
                    )
                    _append_contact_message_event(
                        root_contact_case["id"],
                        message_body,
                        event_type="duplicate_followup",
                        detected_language=language_hint,
                    )
                    try:
                        with engine.begin() as conn:
                            conn.execute(
                                text("UPDATE cases SET raw_message = :msg, updated_at = :now WHERE id = :cid"),
                                {"msg": message_body, "now": _utcnow(), "cid": root_contact_case["id"]},
                            )
                    except Exception as exc:
                        logger.warning("Failed to bump latest message timestamp for legacy case %s: %s", root_contact_case["id"], exc)
                return

            distinct_count = 1 + len(archived_items)
            projected_distinct_count = distinct_count + 1
            if projected_distinct_count >= _CONTACT_THREAD_SPAM_SUSPECTED_DISTINCT:
                logger.warning(
                    "Legacy contact-thread spam-suspected threshold reached: sender=%s tenant=%s distinct_count=%s",
                    sender,
                    current_tenant,
                    projected_distinct_count,
                )
                try:
                    _mark_contact_thread_spam_suppressed(
                        root_contact_case,
                        message_body=message_body,
                        language_hint=language_hint,
                        projected_distinct_count=projected_distinct_count,
                    )
                    _save_spam_flag(
                        current_tenant,
                        sender,
                        "contact_thread_spam_suspected",
                        f"Distinct complaint count reached {projected_distinct_count} in {_CONTACT_BUFFER_WINDOW_HOURS}h thread",
                        message_body,
                    )
                except Exception as exc:
                    logger.error("Failed to persist legacy contact-thread spam-suspected marker: %s", exc)
                return

            enrichment = _run_citizen_case_enrichment(
                sender=sender,
                message_body=message_body,
                resolver_message_body=resolver_message_body,
                resolver_fallback_message_body=resolver_fallback_message_body,
                current_tenant=current_tenant,
                language_hint=language_hint,
                media_source=media_source,
            )
            previous_issue = _thread_issue_from_row(root_contact_case)
            archived_items.append(previous_issue)
            enrichment["meta_data"]["contact_thread_started_at"] = str(root_meta.get("contact_thread_started_at") or _iso_or_now(root_contact_case.get("created_at")))
            enrichment["meta_data"]["contact_thread_items"] = archived_items
            enrichment["meta_data"]["thread_issue_id"] = f"case-{root_contact_case['id']}-{int(_utcnow().timestamp() * 1000)}"
            enrichment["meta_data"]["thread_issue_created_at"] = now_iso
            enrichment["meta_data"]["thread_issue_last_message_at"] = now_iso
            enrichment["meta_data"]["latest_thread_message_at"] = now_iso
            enrichment["meta_data"]["contact_message_events"] = []
            enrichment["meta_data"]["contact_intake_action"] = "thread_distinct_issue"
            enrichment["meta_data"] = _update_contact_thread_meta(
                enrichment["meta_data"],
                distinct_issue_count=projected_distinct_count,
                last_activity_at=now_iso,
            )
            enrichment["citizen_ack_message"] = ""

            _save_case_enrichment_and_respond(
                case_id=root_contact_case["id"],
                sender=sender,
                current_tenant=current_tenant,
                message_body=message_body,
                wa_phone_id=_wa_phone_id,
                enrichment=enrichment,
                raw_message_override=message_body,
                citizen_ack_override="",
            )
            return

        thread_cases = list(active_thread["cases"])
        latest_case = root_contact_case
        thread_id = _contact_thread_id_from_row(latest_case)
        thread_started_at = _contact_thread_started_at_from_row(latest_case)
        now_iso = _utcnow().isoformat()

        if _is_low_information_followup(message_body):
            logger.info(
                "Contact-thread low-information follow-up ignored on thread=%s sender=%s tenant=%s",
                thread_id,
                sender,
                current_tenant,
            )
            _append_contact_message_event(
                latest_case["id"],
                message_body,
                event_type="low_information_noise",
                detected_language=language_hint,
            )
            return

        best_case = None
        best_score = 0.0
        for case_row in thread_cases:
            score = _thread_issue_similarity(message_body, _thread_issue_from_row(case_row))
            if score > best_score:
                best_score = score
                best_case = case_row

        if best_case and best_score >= _CONTACT_BUFFER_SIMILARITY:
            logger.info(
                "Contact-thread duplicate merged into case %s on thread=%s sender=%s tenant=%s",
                best_case["id"],
                thread_id,
                sender,
                current_tenant,
            )
            _append_contact_message_event(
                best_case["id"],
                message_body,
                event_type="duplicate_followup",
                detected_language=language_hint,
            )
            try:
                with engine.begin() as conn:
                    conn.execute(
                        text("UPDATE cases SET raw_message = :msg, updated_at = :now WHERE id = :cid"),
                        {"msg": message_body, "now": _utcnow(), "cid": best_case["id"]},
                    )
            except Exception as exc:
                logger.warning("Failed to bump latest message timestamp for case %s: %s", best_case["id"], exc)
            return

        distinct_count = _aggregate_contact_thread_distinct_count(thread_cases)
        projected_distinct_count = distinct_count + 1
        if projected_distinct_count >= _CONTACT_THREAD_SPAM_SUSPECTED_DISTINCT:
            logger.warning(
                "Contact-thread spam-suspected threshold reached: sender=%s tenant=%s distinct_count=%s thread=%s",
                sender,
                current_tenant,
                projected_distinct_count,
                thread_id,
            )
            try:
                _mark_contact_thread_spam_suppressed(
                    latest_case,
                    message_body=message_body,
                    language_hint=language_hint,
                    projected_distinct_count=projected_distinct_count,
                )
                _apply_contact_thread_group_state(
                    thread_cases,
                    thread_id=thread_id,
                    thread_started_at=thread_started_at,
                    distinct_issue_count=projected_distinct_count,
                    last_activity_at=now_iso,
                )
                _save_spam_flag(
                    current_tenant,
                    sender,
                    "contact_thread_spam_suspected",
                    f"Distinct complaint count reached {projected_distinct_count} in {_CONTACT_BUFFER_WINDOW_HOURS}h thread",
                    message_body,
                )
            except Exception as exc:
                logger.error("Failed to persist contact-thread spam-suspected marker: %s", exc)
            return

        enrichment = _run_citizen_case_enrichment(
            sender=sender,
            message_body=message_body,
            resolver_message_body=resolver_message_body,
            resolver_fallback_message_body=resolver_fallback_message_body,
            current_tenant=current_tenant,
            language_hint=language_hint,
            media_source=media_source,
        )
        enrichment["meta_data"]["contact_intake_action"] = "thread_distinct_issue"
        enrichment["meta_data"]["contact_message_events"] = []
        enrichment["meta_data"] = _set_contact_thread_state_on_meta(
            enrichment["meta_data"],
            thread_id=thread_id,
            thread_started_at=thread_started_at,
            distinct_issue_count=projected_distinct_count,
            last_activity_at=now_iso,
        )
        enrichment["citizen_ack_message"] = ""

        new_case_id = _create_raw_contact_case(
            tenant_id=current_tenant,
            sender=sender,
            message_body=message_body,
            msg_id=msg_id,
            media_source=media_source,
            thread_meta={
                "contact_thread_id": thread_id,
                "contact_thread_started_at": thread_started_at,
            },
        )
        if not new_case_id:
            logger.error("Failed to create distinct thread case for sender=%s tenant=%s thread=%s", sender, current_tenant, thread_id)
            return

        _save_case_enrichment_and_respond(
            case_id=new_case_id,
            sender=sender,
            current_tenant=current_tenant,
            message_body=message_body,
            wa_phone_id=_wa_phone_id,
            enrichment=enrichment,
        )
        refreshed_cases = _recent_contact_thread_cases(sender, current_tenant)
        for group in _group_recent_contact_thread_cases(refreshed_cases):
            if group.get("thread_id") == thread_id:
                _apply_contact_thread_group_state(
                    group.get("cases") or [],
                    thread_id=thread_id,
                    thread_started_at=thread_started_at,
                    distinct_issue_count=projected_distinct_count,
                    last_activity_at=now_iso,
                )
                break
        return

    # ── STEP 1: Save raw grievance to DB immediately ────────────
    # This ensures the message is never lost, even if AI fails.
    case_id = existing_case_id
    if not case_id:
        try:
            case_id = _create_raw_contact_case(
                tenant_id=current_tenant,
                sender=sender,
                message_body=message_body,
                msg_id=msg_id,
                media_source=media_source,
            )
            logger.info(f"Saved raw grievance: case_id={case_id} tenant={current_tenant}")
            if case_id and media_source:
                logger.info("Saved source media for case_id=%s type=%s", case_id, media_source.get("media_type"))
            if inbound_ledger_id and case_id:
                _set_inbound_ledger_case_id(inbound_ledger_id, case_id)
        except Exception as e:
            logger.error(f"CRITICAL: DB save failed for raw grievance: {e}")
            # Even if DB fails, still try to acknowledge the citizen
            _detected_lang = detect_input_language(message_body)
            send_whatsapp_message(sender, get_generic_ack_reply(_detected_lang, message_body), _wa_phone_id)
            raise

    # ── STEP 2: AI classification (if this fails, the grievance is still saved) ──
    try:
        enrichment = _run_citizen_case_enrichment(
            sender=sender,
            message_body=message_body,
            resolver_message_body=resolver_message_body,
            resolver_fallback_message_body=resolver_fallback_message_body,
            current_tenant=current_tenant,
            language_hint=language_hint,
            media_source=media_source,
        )
        sender_digits = re.sub(r"\D", "", sender or "")[-12:] or "anon"
        thread_id = f"ct-{current_tenant}-{sender_digits}-{case_id}"
        enrichment["meta_data"] = _set_contact_thread_state_on_meta(
            enrichment["meta_data"],
            thread_id=thread_id,
            thread_started_at=_utcnow().isoformat(),
            distinct_issue_count=1,
            last_activity_at=_utcnow().isoformat(),
        )
        enrichment["meta_data"]["contact_thread_anchor_case_id"] = case_id
        _save_case_enrichment_and_respond(
            case_id=case_id,
            sender=sender,
            current_tenant=current_tenant,
            message_body=message_body,
            wa_phone_id=_wa_phone_id,
            enrichment=enrichment,
        )

    except Exception as e:
        # AI failed — grievance is still saved as pending/Uncategorised
        logger.error(f"AI processing failed for case {case_id}: {e}")
        try:
            _detected_lang = detect_input_language(message_body)
            send_whatsapp_message(
                sender,
                get_generic_ack_reply(_detected_lang, message_body),
                _wa_phone_id,
            )
        except Exception as send_exc:
            logger.error(
                "WHATSAPP_SEND_FAILED: could not send fallback reply to %s — %s. "
                "Check META_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID env vars, "
                "or set the Meta Phone Number ID via Admin → MP → WhatsApp Configuration.",
                sender, send_exc,
            )


_INBOUND_RECEIVED_RETRY_SECONDS = 30
_INBOUND_PROCESSING_STALE_SECONDS = 10 * 60
_INBOUND_SWEEP_INTERVAL_SECONDS = 2 * 60


def _build_inbound_payload_snapshot(entry: dict, msg: dict) -> dict:
    metadata = dict((entry or {}).get("metadata") or {})
    return {
        "entry_metadata": metadata,
        "message": dict(msg or {}),
    }


def _parse_inbound_payload_snapshot(raw_payload: str | dict | None) -> dict:
    if isinstance(raw_payload, dict):
        return dict(raw_payload)
    try:
        parsed = json.loads(raw_payload or "{}")
    except Exception:
        parsed = {}
    return parsed if isinstance(parsed, dict) else {}


def _record_inbound_ledger_row(
    *,
    meta_message_id: str,
    tenant_id: int | None,
    sender_phone: str,
    receiver_number: str,
    message_type: str,
    payload_snapshot: dict,
) -> dict | None:
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    INSERT INTO wa_inbound_messages (
                        meta_message_id, tenant_id, sender_phone, receiver_number,
                        message_type, status, delivery_attempts, retry_count,
                        raw_payload, created_at, updated_at, last_received_at
                    ) VALUES (
                        :meta_message_id, :tenant_id, :sender_phone, :receiver_number,
                        :message_type, 'received', 1, 0,
                        :raw_payload, :now, :now, :now
                    )
                    ON CONFLICT (meta_message_id) DO UPDATE
                    SET tenant_id = COALESCE(EXCLUDED.tenant_id, wa_inbound_messages.tenant_id),
                        sender_phone = EXCLUDED.sender_phone,
                        receiver_number = EXCLUDED.receiver_number,
                        message_type = EXCLUDED.message_type,
                        raw_payload = EXCLUDED.raw_payload,
                        delivery_attempts = wa_inbound_messages.delivery_attempts + 1,
                        updated_at = EXCLUDED.updated_at,
                        last_received_at = EXCLUDED.last_received_at
                    RETURNING id, meta_message_id, tenant_id, sender_phone, receiver_number,
                              message_type, status, delivery_attempts, retry_count, case_id
                    """
                ),
                {
                    "meta_message_id": meta_message_id,
                    "tenant_id": tenant_id,
                    "sender_phone": sender_phone,
                    "receiver_number": receiver_number,
                    "message_type": message_type,
                    "raw_payload": json.dumps(payload_snapshot, ensure_ascii=False),
                    "now": _utcnow(),
                },
            ).mappings().first()
        return dict(row) if row else None
    except Exception as exc:
        logger.error("Failed to persist inbound WhatsApp ledger row for %s: %s", meta_message_id, exc)
        raise


def _set_inbound_ledger_case_id(inbound_ledger_id: int, case_id: int) -> None:
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE wa_inbound_messages
                    SET case_id = COALESCE(case_id, :case_id),
                        updated_at = :now
                    WHERE id = :inbound_id
                    """
                ),
                {"case_id": case_id, "inbound_id": inbound_ledger_id, "now": _utcnow()},
            )
    except Exception as exc:
        logger.warning("Failed to attach case_id=%s to inbound ledger row %s: %s", case_id, inbound_ledger_id, exc)


def _claim_inbound_ledger_row(inbound_ledger_id: int) -> dict | None:
    stale_cutoff = _utcnow() - timedelta(seconds=_INBOUND_PROCESSING_STALE_SECONDS)
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    UPDATE wa_inbound_messages
                    SET status = 'processing',
                        claimed_at = :now,
                        last_attempt_at = :now,
                        updated_at = :now,
                        last_error = NULL,
                        retry_count = CASE
                            WHEN status = 'received' THEN COALESCE(retry_count, 0)
                            ELSE COALESCE(retry_count, 0) + 1
                        END
                    WHERE id = :inbound_id
                      AND (
                          status = 'received'
                          OR status = 'failed'
                          OR (status = 'processing' AND claimed_at IS NOT NULL AND claimed_at < :stale_cutoff)
                      )
                    RETURNING *
                    """
                ),
                {"inbound_id": inbound_ledger_id, "now": _utcnow(), "stale_cutoff": stale_cutoff},
            ).mappings().first()
        return dict(row) if row else None
    except Exception as exc:
        logger.warning("Failed to claim inbound ledger row %s: %s", inbound_ledger_id, exc)
        return None


def _mark_inbound_ledger_processed(inbound_ledger_id: int) -> None:
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE wa_inbound_messages
                    SET status = 'processed',
                        processed_at = :now,
                        updated_at = :now,
                        last_error = NULL
                    WHERE id = :inbound_id
                    """
                ),
                {"inbound_id": inbound_ledger_id, "now": _utcnow()},
            )
    except Exception as exc:
        logger.warning("Failed to mark inbound ledger row %s processed: %s", inbound_ledger_id, exc)


def _mark_inbound_ledger_failed(inbound_ledger_id: int, error_text: str) -> None:
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE wa_inbound_messages
                    SET status = 'failed',
                        updated_at = :now,
                        last_error = :error_text
                    WHERE id = :inbound_id
                    """
                ),
                {
                    "inbound_id": inbound_ledger_id,
                    "now": _utcnow(),
                    "error_text": (error_text or "")[:4000],
                },
            )
    except Exception as exc:
        logger.warning("Failed to mark inbound ledger row %s failed: %s", inbound_ledger_id, exc)


def _dispatch_inbound_ledger_row(row: dict) -> None:
    payload = _parse_inbound_payload_snapshot(row.get("raw_payload"))
    message = dict(payload.get("message") or {})
    metadata = dict(payload.get("entry_metadata") or {})

    sender = str(row.get("sender_phone") or message.get("from") or "").strip()
    if not sender:
        return

    receiver_number = str(row.get("receiver_number") or metadata.get("display_phone_number") or "").strip()
    if receiver_number and not receiver_number.startswith("+"):
        receiver_number = f"+{receiver_number}"

    current_tenant = row.get("tenant_id")
    if current_tenant is None and receiver_number:
        current_tenant = _resolve_tenant(receiver_number)

    msg_type = str(row.get("message_type") or message.get("type") or "").strip().lower()
    msg_id = str(row.get("meta_message_id") or message.get("id") or "").strip()
    inbound_ledger_id = int(row["id"])
    existing_case_id = row.get("case_id")

    if msg_type == "text":
        message_body = str(message.get("text", {}).get("body", "")).strip()
        if message_body.upper() == "DONE":
            _handle_pa_done_command(sender, receiver_number)
            return

        move_match = _MOVE_PATTERN.match(message_body)
        if move_match:
            _handle_pa_move_command(sender, move_match.group(1), move_match.group(2), receiver_number)
            return

        _process_incoming_message(
            sender,
            message_body,
            receiver_number,
            msg_id,
            inbound_ledger_id=inbound_ledger_id,
            existing_case_id=existing_case_id,
        )
        return

    if msg_type == "image":
        media_id = message.get("image", {}).get("id")
        resolved_mime = message.get("image", {}).get("mime_type", "image/jpeg")
        caption = message.get("image", {}).get("caption", "") or ""
        if media_id and current_tenant is not None and _is_registered_staff_sender(sender, current_tenant):
            _process_pa_letter(sender, media_id, resolved_mime, receiver_number, caption)
            return
        if media_id:
            _process_citizen_media_complaint(
                sender,
                media_id,
                resolved_mime,
                receiver_number,
                caption,
                "image",
                msg_id,
                inbound_ledger_id=inbound_ledger_id,
                existing_case_id=existing_case_id,
            )
            return
        _handle_unsupported_message_type(sender, msg_type, receiver_number)
        return

    if msg_type == "document":
        document = message.get("document", {}) or {}
        media_id = document.get("id")
        resolved_mime = document.get("mime_type", "application/octet-stream")
        caption = document.get("caption", "") or ""
        if (
            media_id
            and resolved_mime == "application/pdf"
            and current_tenant is not None
            and _is_registered_staff_sender(sender, current_tenant)
        ):
            _process_pa_letter_pdf(sender, media_id, resolved_mime, receiver_number, caption)
            return
        if media_id and resolved_mime == "application/pdf":
            _process_citizen_media_complaint(
                sender,
                media_id,
                resolved_mime,
                receiver_number,
                caption,
                "document",
                msg_id,
                inbound_ledger_id=inbound_ledger_id,
                existing_case_id=existing_case_id,
            )
            return
        _handle_unsupported_message_type(sender, msg_type, receiver_number)
        return

    if msg_type == "audio":
        audio = message.get("audio", {}) or {}
        media_id = audio.get("id")
        resolved_mime = audio.get("mime_type", "audio/ogg")
        if media_id:
            _process_citizen_media_complaint(
                sender,
                media_id,
                resolved_mime,
                receiver_number,
                "",
                "audio",
                msg_id,
                inbound_ledger_id=inbound_ledger_id,
                existing_case_id=existing_case_id,
            )
            return
        _handle_unsupported_message_type(sender, msg_type, receiver_number)
        return

    _handle_unsupported_message_type(sender, msg_type or "unknown", receiver_number)


def _process_inbound_ledger_row(inbound_ledger_id: int) -> bool:
    claimed_row = _claim_inbound_ledger_row(inbound_ledger_id)
    if not claimed_row:
        return False

    try:
        _dispatch_inbound_ledger_row(claimed_row)
        _mark_inbound_ledger_processed(inbound_ledger_id)
        return True
    except Exception as exc:
        logger.exception("Inbound ledger processing failed for row %s", inbound_ledger_id)
        _mark_inbound_ledger_failed(inbound_ledger_id, str(exc))
        return False


def _sweep_pending_inbound_ledger_rows(limit: int = 25) -> int:
    now = _utcnow()
    received_cutoff = now - timedelta(seconds=_INBOUND_RECEIVED_RETRY_SECONDS)
    stale_processing_cutoff = now - timedelta(seconds=_INBOUND_PROCESSING_STALE_SECONDS)
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT id
                    FROM wa_inbound_messages
                    WHERE (
                        status = 'received'
                        AND last_received_at <= :received_cutoff
                    ) OR (
                        status = 'processing'
                        AND claimed_at IS NOT NULL
                        AND claimed_at <= :stale_processing_cutoff
                    )
                    ORDER BY last_received_at ASC, id ASC
                    LIMIT :limit
                    """
                ),
                {
                    "received_cutoff": received_cutoff,
                    "stale_processing_cutoff": stale_processing_cutoff,
                    "limit": int(limit),
                },
            ).fetchall()
    except Exception as exc:
        logger.warning("Inbound ledger sweep query failed: %s", exc)
        return 0

    rescued = 0
    for (inbound_id,) in rows:
        if _process_inbound_ledger_row(int(inbound_id)):
            rescued += 1
    if rescued:
        logger.info("Inbound ledger sweep rescued %d rows", rescued)
    return rescued


def _schedule_inbound_ledger_sweep() -> None:
    try:
        _sweep_pending_inbound_ledger_rows()
    finally:
        timer = threading.Timer(_INBOUND_SWEEP_INTERVAL_SECONDS, _schedule_inbound_ledger_sweep)
        timer.daemon = True
        timer.start()


def _start_inbound_ledger_sweeper() -> None:
    logger.info("Inbound WhatsApp ledger sweeper enabled — checking every %ds", _INBOUND_SWEEP_INTERVAL_SECONDS)
    timer = threading.Timer(_INBOUND_SWEEP_INTERVAL_SECONDS, _schedule_inbound_ledger_sweep)
    timer.daemon = True
    timer.start()


@app.post("/whatsapp/webhook")
@_webhook_decorate
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    # ── Validate Meta signature (X-Hub-Signature-256) — MANDATORY ──
    meta_app_secret = _get_meta_app_secret()
    if not meta_app_secret:
        logger.error("Webhook rejected: META_APP_SECRET not configured")
        raise HTTPException(status_code=503, detail="Webhook not configured")

    raw_body = await request.body()
    signature_header = request.headers.get("X-Hub-Signature-256", "")
    if not signature_header.startswith("sha256="):
        logger.warning("Webhook rejected: missing X-Hub-Signature-256 header")
        raise HTTPException(status_code=403, detail="Invalid signature")
    expected = "sha256=" + hmac.new(
        meta_app_secret.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature_header, expected):
        logger.warning("Webhook rejected: signature mismatch")
        raise HTTPException(status_code=403, detail="Invalid signature")
    try:
        data = json.loads(raw_body)
    except json.JSONDecodeError:
        logger.warning("Webhook rejected: invalid JSON body")
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # Meta sends a status update or a real message — ignore status pings
    try:
        entry = data["entry"][0]["changes"][0]["value"]
    except (KeyError, IndexError):
        return {"status": "ignored"}

    messages = entry.get("messages")
    if not messages:
        return {"status": "ignored"}  # delivery receipt / status update

    msg = messages[0]
    msg_id = str(msg.get("id") or "").strip()
    msg_type = str(msg.get("type") or "unknown").strip().lower()
    sender = msg.get("from", "").strip()  # bare number e.g. "919876543210"
    if not sender:
        return {"status": "ignored"}

    # Extract business phone number for tenant routing
    display_number = entry.get("metadata", {}).get("display_phone_number", "")
    if display_number and not display_number.startswith("+"):
        display_number = f"+{display_number}"
    current_tenant = _resolve_tenant(display_number) if display_number else None
    synthetic_msg_id = msg_id or f"synthetic:{hashlib.sha256(raw_body).hexdigest()}"
    inbound_row = _record_inbound_ledger_row(
        meta_message_id=synthetic_msg_id,
        tenant_id=current_tenant,
        sender_phone=sender,
        receiver_number=display_number,
        message_type=msg_type or "unknown",
        payload_snapshot=_build_inbound_payload_snapshot(entry, msg),
    )
    if not inbound_row:
        raise HTTPException(status_code=500, detail="Failed to persist inbound message")

    background_tasks.add_task(_process_inbound_ledger_row, int(inbound_row["id"]))
    return {"status": "received"}


# ─────────────────────────────────────────
# HEALTH CHECKS
# ─────────────────────────────────────────
@app.get("/")
def root():
    return {"status": "active", "system": "Needle Backend V8.1"}


@app.get("/health")
def health():
    """Basic liveness check — returns 200 if the process is running."""
    return {"status": "ok", "system": "Needle Backend V8.2", "timestamp": datetime.utcnow().isoformat(), "routes": ["profile-generate"]}


@app.get("/health/db")
def health_db():
    """Database connectivity check. Returns 200 if DB is reachable, 503 otherwise."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as exc:
        logger.error("Health/DB check failed: %s", exc)
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": "unreachable"}
        )


@app.get("/health/ai")
def health_ai():
    """AI provider availability check. Returns 200 if both OpenAI and Gemini keys are configured."""
    checks = {}
    openai_key = os.getenv("OPENAI_API_KEY")
    gemini_key  = os.getenv("GEMINI_API_KEY")

    checks["openai"] = "configured" if openai_key else "missing_key"
    checks["gemini"] = "configured" if gemini_key else "missing_key"

    all_ok = all(v == "configured" for v in checks.values())
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={"status": "ok" if all_ok else "degraded", "providers": checks}
    )


# ─── Migration: add composite unique constraint to contacts (idempotent) ───
# Prevents race-condition duplicate contacts (tenant_id, phone) pairs.
# The UNIQUE INDEX approach is idempotent — safe to run on every startup.
try:
    with engine.begin() as conn:
        conn.execute(sa_text("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_contacts_tenant_phone
            ON contacts (tenant_id, phone)
        """))
        logger.info("Migration: contacts(tenant_id, phone) unique index verified")
except Exception as _contact_exc:
    logger.warning("contacts unique index migration skipped: %s", _contact_exc)

# ─── Startup: prune token_blocklist entries older than 8h (JWT max age) ───
# Prevents unbounded table growth. Safe to run on every startup — only
# deletes rows that are guaranteed to have expired JWTs by now.
try:
    with engine.begin() as conn:
        cutoff = _utcnow() - timedelta(hours=9)  # 1h buffer beyond JWT_EXPIRE_HOURS=8
        result = conn.execute(
            text("DELETE FROM token_blocklist WHERE revoked_at < :cutoff"),
            {"cutoff": cutoff},
        )
        if result.rowcount:
            logger.info("Pruned %d expired token_blocklist entries", result.rowcount)
except Exception as _prune_exc:
    logger.warning("token_blocklist prune failed (non-critical): %s", _prune_exc)

# ─── Release Migration Lock ───
# Only call pg_advisory_unlock if this instance actually acquired it.
# If _migration_lock_acquired is False we never held the lock, so just close
# the connection; calling unlock without holding the lock is a no-op but
# produces a confusing log line.
try:
    if _migration_lock_acquired:
        _startup_migration_lock_conn.execute(sa_text("SELECT pg_advisory_unlock(77772024)"))
        logger.info("Released Postgres advisory lock (77772024)")
    _startup_migration_lock_conn.close()
except Exception as _lock_exc:
    logger.warning("Failed to cleanly release migration lock (auto-releases on connection close anyway): %s", _lock_exc)

@app.on_event("startup")
async def startup_jobs():
    """Run non-blocking cleanup sweeps on startup via FastAPI threadpool."""
    from fastapi.concurrency import run_in_threadpool
    await run_in_threadpool(_sweep_stale_batches)
    await run_in_threadpool(_sweep_pending_citizen_acks)
    await run_in_threadpool(_send_due_case_clarification_followups)
    await run_in_threadpool(_sweep_pending_inbound_ledger_rows)
    _start_inbound_ledger_sweeper()
    _start_keep_alive()


# ─────────────────────────────────────────
# RAILWAY KEEP-ALIVE (hobby plan anti-sleep)
# ─────────────────────────────────────────
_KEEP_ALIVE_INTERVAL = 4 * 60  # 4 minutes — Railway sleeps after ~5 min inactivity


def _keep_alive_ping():
    """Self-ping /health to prevent Railway hobby plan from sleeping."""
    railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN")
    custom_url = os.getenv("KEEP_ALIVE_URL")
    url = custom_url or (f"https://{railway_domain}/health" if railway_domain else None)
    if not url:
        return
    try:
        resp = http_requests.get(url, timeout=10)
        logger.debug("Keep-alive ping → %s  [%d]", url, resp.status_code)
    except Exception as exc:
        logger.warning("Keep-alive ping failed: %s", exc)
    finally:
        t = threading.Timer(_KEEP_ALIVE_INTERVAL, _keep_alive_ping)
        t.daemon = True
        t.start()


def _start_keep_alive():
    railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN")
    custom_url = os.getenv("KEEP_ALIVE_URL")
    if not railway_domain and not custom_url:
        logger.info("Keep-alive disabled (RAILWAY_PUBLIC_DOMAIN not set). Set KEEP_ALIVE_URL to enable.")
        return
    logger.info("Keep-alive enabled — pinging every %ds", _KEEP_ALIVE_INTERVAL)
    t = threading.Timer(_KEEP_ALIVE_INTERVAL, _keep_alive_ping)
    t.daemon = True
    t.start()
