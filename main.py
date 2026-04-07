"""
main.py — Needle Parliamentary Intelligence Platform
Backend Entry Point (FastAPI)
"""
from sansadx_backend.ai_engine import ask_chatgpt_agent
import os
import re
import json
import hmac
import hashlib
import logging
import threading
import sentry_sdk
from datetime import datetime, timedelta
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, PlainTextResponse
from sqlalchemy import text
import requests as http_requests

# ─────────────────────────────────────────
# SECURITY CONFIG (optional — soft import)
# ─────────────────────────────────────────
try:
    from core.security_config import (
        ALLOWED_ORIGINS, SECURITY_HEADERS,
    )
except Exception:
    ALLOWED_ORIGINS = ["*"]
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

from sansadx_backend.db import engine, init_db, get_phone_tenant_mapping, get_geo_overrides, get_tenant_phone_number_id

# ─────────────────────────────────────────
# GEOGRAPHY RESOLVER
# ─────────────────────────────────────────
try:
    from modules.geography_resolver import resolve_constituency
except ImportError:
    def resolve_constituency(text, tenant_id):
        return None, None

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
from sqlalchemy import text as sa_text
_startup_migration_lock_conn = engine.connect()
_migration_lock_acquired = _startup_migration_lock_conn.execute(
    sa_text("SELECT pg_try_advisory_lock(77772024)")
).scalar()
if _migration_lock_acquired:
    logger.info("Acquired Postgres advisory lock (77772024) for safe startup migrations")
else:
    logger.warning(
        "pg_try_advisory_lock(77772024) returned FALSE — another instance is running "
        "migrations concurrently.  Skipping migrations on this instance (all are idempotent)."
    )

init_db()
logger.info("Database initialised.")

# On startup: seed DB from JSON files, reconstruct files from DB, sync geo_overrides.
# This two-way sync ensures geography data is ALWAYS durable:
#   - JSON files committed to git → seeded into DB on first deploy (permanent)
#   - DB rows → reconstructed as JSON files on every future deploy (no git needed)
#   - Admin-entered data via API → stored in DB → reconstructed on next deploy
try:
    import pathlib as _pl
    from sansadx_backend.db import SessionLocal as _startup_SL, TenantOverride as _startup_TO, Tenant as _startup_T

    _sdb = _startup_SL()
    try:
        # ── Step 1: Seed DB from any JSON files present (idempotent) ─────────
        # Reads data/geography/<Constituency>/<Assembly>.json and upserts into DB.
        # On the very first deploy the files are in git; after that the DB is the
        # source of truth and the files are ephemeral.
        _geo_base = _pl.Path(__file__).parent / "data" / "geography"
        if _geo_base.exists():
            # Build constituency → tenant_id map
            _c2t = {}
            for _t in _sdb.query(_startup_T).all():
                if _t.constituency and _t.constituency != "System":
                    _c2t[_t.constituency.lower()] = _t.id

            _seeded = 0
            for _parl_dir in sorted(_geo_base.iterdir()):
                if not _parl_dir.is_dir():
                    continue
                for _jf in sorted(_parl_dir.glob("*.json")):
                    _db_key = f"{_parl_dir.name}/{_jf.stem}"
                    # Only insert if not already in DB (don't overwrite admin edits)
                    _exists = _sdb.query(_startup_TO).filter(
                        _startup_TO.override_type == "geography_data",
                        _startup_TO.key == _db_key,
                    ).first()
                    if not _exists:
                        try:
                            _payload = _jf.read_text(encoding="utf-8")
                            _tid = _c2t.get(_parl_dir.name.lower())
                            _sdb.add(_startup_TO(
                                tenant_id=_tid,
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

        # ── Step 2: Reconstruct JSON files from DB ────────────────────────────
        # On clean deploys the git files may not be present; DB rows rebuild them.
        _geo_rows = _sdb.query(_startup_TO).filter(
            _startup_TO.override_type == "geography_data"
        ).all()
        _files_written = 0
        for _row in _geo_rows:
            _parts = _row.key.split("/", 1)
            if len(_parts) != 2:
                continue
            _pc, _ac = _parts
            _dest = _geo_base / _pc
            _dest.mkdir(parents=True, exist_ok=True)
            try:
                _data = json.loads(_row.value) if isinstance(_row.value, str) else _row.value
                with open(_dest / f"{_ac}.json", "w", encoding="utf-8") as _f:
                    json.dump(_data, _f, indent=2, ensure_ascii=False)
                _files_written += 1
            except Exception:
                pass
        if _files_written:
            logger.info(f"Geography startup: reconstructed {_files_written} assembly files from DB")

    finally:
        _sdb.close()

    # ── Step 3: Sync JSON files → DB geo_override lookup entries ─────────────
    from modules.geography_resolver import auto_generate_overrides
    _sync_result = auto_generate_overrides()
    logger.info(f"Geography overrides synced to DB: {_sync_result}")

except Exception as e:
    logger.warning(f"Geography startup sync failed (non-critical): {e}")

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

# ─── Startup: prune wa_message_dedup entries older than 30 days ───
# Meta never retries messages older than a few hours; 30 days is very conservative.
try:
    with engine.begin() as conn:
        _dedup_cutoff = datetime.utcnow() - timedelta(days=30)
        _dedup_del = conn.execute(
            text("DELETE FROM wa_message_dedup WHERE processed_at < :cutoff"),
            {"cutoff": _dedup_cutoff},
        )
        if _dedup_del.rowcount:
            logger.info("Pruned %d stale wa_message_dedup entries", _dedup_del.rowcount)
except Exception as _dedup_prune_exc:
    logger.warning("wa_message_dedup prune failed (non-critical): %s", _dedup_prune_exc)

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
    "CREATE INDEX IF NOT EXISTS idx_cases_is_deleted ON cases (is_deleted)",
    "CREATE INDEX IF NOT EXISTS idx_spam_flags_tenant_phone ON spam_flags (tenant_id, phone)",
    "CREATE INDEX IF NOT EXISTS idx_token_blocklist_revoked_at ON token_blocklist (revoked_at)",
]:
    try:
        with engine.begin() as conn:
            conn.execute(text(_idx_sql))
    except Exception:  # nosec B110 — idempotent
        pass
logger.info("Performance indexes verified.")

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
    "ALTER TABLE letterbox ADD COLUMN diary_number VARCHAR",
    "ALTER TABLE letterbox ADD COLUMN source VARCHAR DEFAULT 'upload'",
    "ALTER TABLE letterbox ADD COLUMN sender_phone VARCHAR",
    "ALTER TABLE letterbox ADD COLUMN assigned_to VARCHAR",
    "ALTER TABLE letterbox ADD COLUMN date_of_letter DATE",
    "ALTER TABLE letterbox ADD COLUMN notes TEXT",
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

# Seed CSR company profiles from static JSON files on startup
try:
    from modules.csr_data_loader import seed_csr_companies
    seed_csr_companies()
except Exception as _csr_seed_err:
    logger.warning(f"CSR company seed failed (non-fatal): {_csr_seed_err}")



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


def _normalise(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


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
from modules.case_query_parser import parse_query
from modules.case_query_engine import query_cases
from modules.localized_replies import get_awaiting_location_reply
from modules.case_query_formatter import format_cases_for_whatsapp, format_clarification_request


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

# DEPRECATED: threading.Timer based scheduling removed in favor of BackgroundTasks async sleeper.
def _schedule_batch_flush(sender: str, tenant_id: int, receiver_number: str):
    pass


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
                        status         = 'new'
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
        label = "OUTBOX" if new_direction == "outbox" else "INBOX"
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
    reply = (
        "Thank you for reaching out 🙏\n\n"
        "We received your message but couldn’t read it as text. "
        "Please type your complaint or request and send it as a text message so we can help you faster."
    )
    try:
        send_whatsapp_message(sender, reply, _wa_phone_id)
        logger.info("Unsupported message type '%s' from %s — sent re-send prompt", msg_type, sender)
    except Exception as exc:
        logger.warning("Could not send unsupported-type reply to %s: %s", sender, exc)


# Categories that require human PA review before the AI reply is sent to citizen.
# Cases in these categories are saved with status='pending_review'; the AI-generated
# reply is stored in case_metadata but NOT sent automatically.
# Stored lowercase — compared with category.lower().strip() so GPT variants like
# "Law and Order", "EMERGENCY", or "law and order" all match correctly.
_REVIEW_REQUIRED_CATEGORIES = {"law & order", "law and order", "emergency", "political", "legal"}
_REVIEW_GENERIC_ACK = (
    "Thank you for reaching out 🙏\n\n"
    "Your complaint has been received and is being reviewed by our team. "
    "We will follow up with you shortly."
)


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


def _process_incoming_message(sender: str, message_body: str, receiver_number: str = "", msg_id: str = ""):
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

    logger.info(f"Incoming from {sender} → Tenant {current_tenant}")

    # ── Staff query routing (check BEFORE spam / citizen flow) ───────────────
    # If the sender's phone is a registered staff user for this tenant,
    # treat their message as a case query, not a citizen grievance.
    # Uses the same users.phone lookup as the PA letter intake system.
    try:
        with engine.connect() as conn:
            # Match on both bare number and with country-code prefix (91XXXXXXXXXX vs XXXXXXXXXX)
            sender_bare = sender[2:] if sender.startswith("91") and len(sender) == 12 else sender
            staff_row = conn.execute(
                text("""
                    SELECT id, display_name FROM users
                    WHERE (phone = :phone OR phone = :bare) AND tenant_id = :tid AND is_active = true
                    LIMIT 1
                """),
                {"phone": sender, "bare": sender_bare, "tid": current_tenant},
            ).fetchone()
    except Exception as _staff_exc:
        logger.warning("Staff lookup failed: %s", _staff_exc)
        staff_row = None

    if staff_row:
        logger.info(
            "Staff query from %s (user_id=%s, tenant=%s): %r",
            sender, staff_row[0], current_tenant, message_body[:80],
        )
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

    # ── Spam / abuse detection (pre-AI, no token cost) ───────────
    is_abuse, abuse_reason = _is_abusive(message_body)
    is_flood, flood_reason = _is_coordinated_flood(message_body, current_tenant)

    if is_abuse or is_flood:
        flag_type   = "abuse_keyword"    if is_abuse else "coordinated_flood"
        flag_reason = abuse_reason       if is_abuse else flood_reason
        spam_cat    = "Spam (Offensive)" if is_abuse else "Spam"
        logger.warning(f"Spam flag [{flag_type}] from {sender}: {flag_reason}")

        try:
            with engine.begin() as conn:
                conn.execute(
                    text("""
                        INSERT INTO cases
                            (tenant_id, user_phone, category, raw_message,
                             status, case_metadata, is_critical, created_at)
                        VALUES (:tid, :phone, :cat, :msg,
                                'new', :meta, false, :now)
                    """),
                    {
                        "tid":   current_tenant,
                        "phone": sender,
                        "cat":   spam_cat,
                        "msg":   message_body,
                        "meta":  json.dumps({"spam_flagged": True, "flag_reason": flag_reason}),
                        "now":   datetime.utcnow(),
                    },
                )
            logger.info(f"Saved spam case: category='{spam_cat}' tenant={current_tenant}")
        except Exception as exc:
            logger.error(f"Spam case DB save failed: {exc}")

        _save_spam_flag(current_tenant, sender, flag_type, flag_reason, message_body)
        send_whatsapp_message(
            sender,
            "Thank you for contacting us. Your message has been received and will be reviewed by our team.",
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

        if _today_count >= _daily_limit:
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
            send_whatsapp_message(
                sender,
                "We've received multiple messages from your number today. Our team will review and follow up. 🙏",
                _wa_phone_id,
            )
            return
    except Exception as _rate_exc:
        logger.warning("Per-phone rate limit check failed (non-blocking): %s", _rate_exc)

    # ── STEP 1: Save raw grievance to DB immediately ────────────
    # This ensures the message is never lost, even if AI fails.
    case_id = None
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("""
                    INSERT INTO cases
                    (tenant_id, user_phone, category, raw_message, status, case_metadata, is_critical, created_at)
                    VALUES (:tid, :phone, 'Uncategorised', :msg, 'pending', :meta, false, :now)
                    RETURNING id
                """),
                {
                    "tid": current_tenant,
                    "phone": sender,
                    "msg": message_body,
                    "meta": json.dumps({"summary": message_body[:200], "wa_msg_id": msg_id}),
                    "now": datetime.utcnow(),
                }
            )
            row = result.fetchone()
            case_id = row[0] if row else None
            logger.info(f"Saved raw grievance: case_id={case_id} tenant={current_tenant}")
    except Exception as e:
        logger.error(f"CRITICAL: DB save failed for raw grievance: {e}")
        # Even if DB fails, still try to acknowledge the citizen
        send_whatsapp_message(sender, "Thank you for contacting us. Your message has been received.", _wa_phone_id)
        return

    # ── STEP 2: AI classification (if this fails, the grievance is still saved) ──
    try:
        user_context = get_user_context(sender)
        full_prompt = f"{user_context}\n\nUSER MESSAGE: {message_body}"
        ai_result = ask_chatgpt_agent(full_prompt, tenant_id=current_tenant)

        if isinstance(ai_result, str):
            try:
                ai_result = json.loads(ai_result)
            except Exception:
                ai_result = {"status": "INCOMPLETE", "political_response": ai_result, "grievance_data": {}}

        # Parse AI result
        grievance = ai_result.get("grievance_data", {}) or {}
        status = str(ai_result.get("status", "new")).lower()
        detected_language = ai_result.get("detected_language", "")
        categories = grievance.get("categories", ["General"])
        category = categories[0] if isinstance(categories, list) and categories else "General"
        political_reply = ai_result.get("political_response", "Thank you for contacting us. Your message has been received.")

        location_name = grievance.get("location")
        final_constituency = None

        # Geo mapping — DB overrides + geography JSON files
        if location_name:
            lookup_key = str(location_name).lower().strip()
            # Build combined rules: geo_overrides + geography JSON files
            combined_geo = {}
            try:
                geo_map = get_geo_overrides(current_tenant)
                combined_geo.update(geo_map)
            except Exception:
                logger.warning("Geo override lookup failed for tenant %s", current_tenant)

            # Also scan geography JSON files for locality→assembly mapping
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
                            # Case-insensitive fallback
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

            # Now do STRICT 4-tier matching against combined_geo
            # Priority: Exact > Word Boundary > Substring (key in input only) > Strict Fuzzy (85%)
            combined_lower = {k.lower(): v for k, v in combined_geo.items()}
            
            # 1. Exact match (highest priority)
            final_constituency = combined_lower.get(lookup_key)
            if final_constituency:
                logger.info(f"Geo exact match: '{lookup_key}' → {final_constituency}")
            
            # 2. Word boundary match — key appears as complete word in user input
            # Prevents "hosur" matching "gilihosur" or "chandanhosur"
            if not final_constituency:
                import re as _re
                for geo_key, geo_val in combined_lower.items():
                    if len(geo_key) >= 4:
                        word_pattern = r'\b' + _re.escape(geo_key) + r'\b'
                        if _re.search(word_pattern, lookup_key):
                            final_constituency = geo_val
                            logger.info(f"Geo word boundary match: '{geo_key}' in '{lookup_key}' → {geo_val}")
                            break
            
            # 3. Substring match — ONLY if geo_key is contained in lookup_key (not reverse)
            # This prevents "hosur" from matching "chandanhosur" when user just says "hosur"
            # Prefer longer matches (more specific)
            if not final_constituency:
                best_match = None
                best_match_len = 0
                for geo_key, geo_val in combined_lower.items():
                    # Only match if key is at least 5 chars and fully contained in user input
                    if len(geo_key) >= 5 and geo_key in lookup_key:
                        if len(geo_key) > best_match_len:
                            best_match = geo_val
                            best_match_len = len(geo_key)
                            best_match_key = geo_key
                if best_match:
                    final_constituency = best_match
                    logger.info(f"Geo substring match: '{best_match_key}' ({best_match_len} chars) in '{lookup_key}' → {final_constituency}")
            
            # 4. Strict fuzzy match (85% cutoff, min 5 chars, similar lengths)
            if not final_constituency and len(lookup_key) >= 5:
                import difflib
                # Only consider keys of similar length (±30%) to prevent wild mismatches
                candidate_keys = [
                    k for k in combined_lower.keys()
                    if len(k) >= 5 and 0.7 <= len(k)/len(lookup_key) <= 1.3
                ]
                if candidate_keys:
                    matches = difflib.get_close_matches(lookup_key, candidate_keys, n=1, cutoff=0.85)
                    if matches:
                        final_constituency = combined_lower[matches[0]]
                        logger.info(f"Geo fuzzy match (85%): '{lookup_key}' ≈ '{matches[0]}' → {final_constituency}")

        # Fallback geo resolution
        if not final_constituency:
            final_constituency = (
                grievance.get("assembly_constituency") or
                grievance.get("constituency") or
                ai_result.get("constituency") or
                ai_result.get("assembly_constituency")
            )
            if (not final_constituency or final_constituency == "Unknown") and location_name:
                _, resolved = resolve_constituency(location_name, current_tenant)
                final_constituency = resolved if resolved and resolved != "Unknown" else None

        if not final_constituency:
            final_constituency = "Unknown"

        # If location couldn't be verified against geography list, hold the case
        # and replace the AI's "noted" reply with a localized clarification request
        if final_constituency == "Unknown" and location_name:
            status = "awaiting_location"
            political_reply = get_awaiting_location_reply(location_name, detected_language)

        meta_data = {
            "user_intent": status,
            "location_resolved": bool(location_name and final_constituency != "Unknown"),
            "matched_value": location_name or "",
            "assembly_constituency": final_constituency,
            "summary": grievance.get("summary", message_body[:100])
        }

        # ── STEP 3: Update the saved case with AI results ──
        try:
            with engine.begin() as conn:
                conn.execute(
                    text("""
                        UPDATE cases
                        SET category = :cat, status = :stat, case_metadata = :meta,
                            is_critical = :crit
                        WHERE id = :cid
                    """),
                    {
                        "cat": category,
                        "stat": status,
                        "meta": json.dumps(meta_data),
                        "crit": ai_result.get("is_critical", False) or (status == "emergency"),
                        "cid": case_id,
                    }
                )
                logger.info(f"AI updated case {case_id}: status='{status}' category='{category}' constituency='{final_constituency}'")
        except Exception as e:
            logger.error(f"DB update failed for case {case_id}: {e}")

        # ── Human review gate ─────────────────────────────────────────────
        # Sensitive cases (Law & Order, Emergency, Political, is_critical) are
        # held for PA review before the AI reply is sent to the citizen.
        # The citizen gets only a generic acknowledgment.
        # The AI-generated reply is stored in case_metadata for PA to see.
        _is_review_category = category.lower().strip() in _REVIEW_REQUIRED_CATEGORIES
        _is_critical_case = bool(ai_result.get("is_critical", False) or status == "emergency")

        if (_is_review_category or _is_critical_case) and status not in ("awaiting_location",):
            # Store the AI reply so PA can view and approve it from the dashboard
            try:
                with engine.begin() as _rv_conn:
                    _rv_meta = {**meta_data, "ai_reply_pending_review": political_reply}
                    _rv_conn.execute(
                        text("""
                            UPDATE cases
                            SET status = 'pending_review', case_metadata = :meta
                            WHERE id = :cid
                        """),
                        {"meta": json.dumps(_rv_meta), "cid": case_id}
                    )
                logger.info(
                    "REVIEW_REQUIRED: case_id=%s tenant=%s category=%s is_critical=%s — held for PA review",
                    case_id, current_tenant, category, _is_critical_case
                )
            except Exception as _rv_exc:
                logger.error("Failed to set pending_review status for case %s: %s", case_id, _rv_exc)

            # Send only generic ack — NOT the AI-generated political reply.
            # On failure, flag the case so the startup sweep can retry the ACK.
            try:
                send_whatsapp_message(sender, _REVIEW_GENERIC_ACK, _wa_phone_id)
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
            return  # Done — do not fall through to the regular send below

        try:
            send_whatsapp_message(sender, political_reply, _wa_phone_id)
        except Exception as send_exc:
            logger.error(
                "WHATSAPP_SEND_FAILED: could not reply to %s (case=%s) — %s. "
                "Check META_ACCESS_TOKEN and per-tenant Phone Number ID configuration.",
                sender, case_id, send_exc,
            )

    except Exception as e:
        # AI failed — grievance is still saved as pending/Uncategorised
        logger.error(f"AI processing failed for case {case_id}: {e}")
        try:
            send_whatsapp_message(
                sender,
                "Thank you for contacting us. Your message has been received and will be reviewed by our team.",
                _wa_phone_id,
            )
        except Exception as send_exc:
            logger.error(
                "WHATSAPP_SEND_FAILED: could not send fallback reply to %s — %s. "
                "Check META_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID env vars, "
                "or set the Meta Phone Number ID via Admin → MP → WhatsApp Configuration.",
                sender, send_exc,
            )


@app.post("/whatsapp/webhook")
@_webhook_decorate
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    # ── Validate Meta signature (X-Hub-Signature-256) — MANDATORY ──
    if not META_APP_SECRET:
        logger.error("Webhook rejected: META_APP_SECRET not configured")
        raise HTTPException(status_code=503, detail="Webhook not configured")

    raw_body = await request.body()
    signature_header = request.headers.get("X-Hub-Signature-256", "")
    if not signature_header.startswith("sha256="):
        logger.warning("Webhook rejected: missing X-Hub-Signature-256 header")
        raise HTTPException(status_code=403, detail="Invalid signature")
    expected = "sha256=" + hmac.new(
        META_APP_SECRET.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature_header, expected):
        logger.warning("Webhook rejected: signature mismatch")
        raise HTTPException(status_code=403, detail="Invalid signature")
    data = json.loads(raw_body)

    # Meta sends a status update or a real message — ignore status pings
    try:
        entry = data["entry"][0]["changes"][0]["value"]
    except (KeyError, IndexError):
        return {"status": "ignored"}

    messages = entry.get("messages")
    if not messages:
        return {"status": "ignored"}  # delivery receipt / status update

    msg = messages[0]
    msg_id = msg.get("id", "")  # Meta message ID — unique per message

    # ── Deduplication: atomic INSERT gate on wa_message_dedup ───────────────
    # Uses INSERT ON CONFLICT DO NOTHING + rowcount check instead of a
    # SELECT-then-INSERT pattern, which has a race window during the 5-7s
    # background task execution.  Two simultaneous webhook calls for the same
    # msg_id will both attempt the INSERT; exactly one will get rowcount=1
    # (the winner) and the other will get rowcount=0 (duplicate — rejected here,
    # before a background task is ever dispatched).
    if msg_id:
        try:
            with engine.begin() as _dg_conn:
                _dg_ins = _dg_conn.execute(
                    text("""
                        INSERT INTO wa_message_dedup (message_id, processed_at)
                        VALUES (:mid, :now)
                        ON CONFLICT (message_id) DO NOTHING
                    """),
                    {"mid": msg_id, "now": datetime.utcnow()},
                )
            if _dg_ins.rowcount == 0:
                logger.info("Webhook dedup: message_id=%s already claimed — ignoring retry", msg_id)
                return {"status": "ignored"}
        except Exception as dedup_exc:
            logger.warning("Dedup gate insert failed (non-blocking): %s", dedup_exc)

    msg_type = msg.get("type")
    sender = msg["from"]  # bare number e.g. "919876543210"

    # ── Content-based dedup: same sender + same text within 10 min = duplicate ──
    # Catches re-sends by the user and any rare duplicate Meta deliveries with
    # different message IDs (e.g. after a webhook retry with a regenerated ID).
    # Skipped for registered staff/PA numbers — they query repeatedly on purpose.
    if msg_type == "text":
        _raw_body = (msg.get("text") or {}).get("body", "").strip()
        if _raw_body:
            try:
                _is_staff_sender = False
                _resolved_tenant = _resolve_tenant(
                    entry.get("metadata", {}).get("display_phone_number", "") or
                    os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
                )
                if _resolved_tenant:
                    _bare_sender = sender[2:] if sender.startswith("91") and len(sender) == 12 else sender
                    with engine.connect() as _sc:
                        _is_staff_sender = bool(_sc.execute(
                            text("SELECT 1 FROM users WHERE (phone = :p OR phone = :b) AND tenant_id = :tid AND is_active = true LIMIT 1"),
                            {"p": sender, "b": _bare_sender, "tid": _resolved_tenant},
                        ).fetchone())
            except Exception:
                _is_staff_sender = False

            if not _is_staff_sender:
                try:
                    with engine.connect() as conn:
                        _dup = conn.execute(
                            text("""
                                SELECT 1 FROM cases
                                WHERE user_phone = :phone
                                  AND raw_message = :body
                                  AND created_at >= NOW() - INTERVAL '10 minutes'
                                LIMIT 1
                            """),
                            {"phone": sender, "body": _raw_body},
                        ).fetchone()
                    if _dup:
                        logger.info("Content dedup: identical message from %s within 10 min — ignored", sender)
                        return {"status": "ignored"}
                except Exception as _ce:
                    logger.warning("Content dedup check failed (non-blocking): %s", _ce)

    # Extract business phone number for tenant routing
    display_number = entry.get("metadata", {}).get("display_phone_number", "")
    if display_number and not display_number.startswith("+"):
        display_number = f"+{display_number}"

    if msg_type == "text":
        message_body = msg["text"]["body"].strip()
        if not message_body:
            return {"status": "ignored"}
        # DONE command — immediately flush any pending batch for this PA
        if message_body.upper() == "DONE":
            background_tasks.add_task(_handle_pa_done_command, sender, display_number)
            return {"status": "received"}
        # MOVE correction command
        move_match = _MOVE_PATTERN.match(message_body)
        if move_match:
            background_tasks.add_task(
                _handle_pa_move_command,
                sender, move_match.group(1), move_match.group(2), display_number
            )
        else:
            background_tasks.add_task(_process_incoming_message, sender, message_body, display_number, msg_id)
        return {"status": "received"}

    elif msg_type == "image":
        # PA letter intake — staff photographs a physical letter and sends via WhatsApp
        media_id = msg.get("image", {}).get("id")
        resolved_mime = msg.get("image", {}).get("mime_type", "image/jpeg")
        caption = msg.get("image", {}).get("caption", "") or ""
        if media_id:
            background_tasks.add_task(_process_pa_letter, sender, media_id, resolved_mime, display_number, caption)
        return {"status": "received"}

    else:
        # ── Non-text/image message (audio, video, sticker, document, etc.) ──
        # Previously these were silently ignored — citizens got no response.
        # Now we send a polite prompt to re-send as text so they're not lost.
        background_tasks.add_task(_handle_unsupported_message_type, sender, msg_type, display_number)
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
    return {"status": "ok", "system": "Needle Backend V8.1", "timestamp": datetime.utcnow().isoformat()}


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
        cutoff = datetime.utcnow() - timedelta(hours=9)  # 1h buffer beyond JWT_EXPIRE_HOURS=8
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