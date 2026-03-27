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

from sansadx_backend.db import engine, init_db, get_phone_tenant_mapping, get_geo_overrides

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

# CORS — fully open (we use Bearer tokens, not cookies, so CORS adds no security)
# This matches the proven working config from commit 34c7ff8a
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
# DATABASE INIT
# ─────────────────────────────────────────
init_db()
logger.info("Database initialised.")

# ─── Migration: add tenant_id to archives table (idempotent) ───
try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE archives ADD COLUMN tenant_id INTEGER REFERENCES tenants(id)"))
        logger.info("Migration: added tenant_id column to archives table")
        # Backfill: set tenant_id from the users table
        conn.execute(text("""
            UPDATE archives SET tenant_id = (
                SELECT u.tenant_id FROM users u WHERE u.username = archives.user LIMIT 1
            ) WHERE tenant_id IS NULL
        """))
        logger.info("Migration: backfilled archives.tenant_id from users table")
except Exception:  # nosec B110 — idempotent migration; "column already exists" is expected
    pass

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


# ─────────────────────────────────────────
# CONTEXT MEMORY (prevents repeated questions)
# ─────────────────────────────────────────
def get_user_context(phone_number: str) -> str:
    try:
        with engine.connect() as conn:
            query = text("""
                SELECT case_metadata FROM cases
                WHERE user_phone = :phone
                AND CAST(case_metadata AS TEXT) LIKE '%location_resolved": true%'
                ORDER BY created_at DESC LIMIT 1
            """)
            result = conn.execute(query, {"phone": phone_number}).fetchone()

            if result and result[0]:
                meta = result[0]
                if isinstance(meta, str):
                    meta = json.loads(meta)
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


def _resolve_tenant(receiver_number: str) -> int:
    """Resolve WhatsApp receiver number → tenant_id. Shared by text and image handlers."""
    current_tenant = 1
    try:
        phone_map = get_phone_tenant_mapping()
        if receiver_number in phone_map:
            return phone_map[receiver_number]
    except Exception:
        logger.warning("Tenant phone mapping lookup failed for %s", receiver_number)

    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT id FROM tenants WHERE whatsapp_number = :num LIMIT 1"),
                {"num": receiver_number}
            ).fetchone()
            if row:
                current_tenant = row[0]
    except Exception as exc:
        logger.warning(f"Tenant DB lookup failed: {exc}")
    return current_tenant


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


def _schedule_batch_flush(sender: str, tenant_id: int, receiver_number: str):
    """Reset the 45-second inactivity timer for this sender's batch."""
    key = (sender, tenant_id)
    with _batch_lock:
        existing = _batch_timers.get(key)
        if existing:
            existing.cancel()
        t = threading.Timer(
            BATCH_FLUSH_DELAY,
            _flush_letter_batch,
            args=(sender, tenant_id, receiver_number)
        )
        _batch_timers[key] = t
        t.daemon = True
        t.start()


def _flush_letter_batch(sender: str, tenant_id: int, receiver_number: str):
    """
    Process all accumulated pages in a batch as a single letterbox entry.
    Called either by the inactivity timer or immediately on 'DONE' command.
    """
    from modules.letterbox import download_meta_image, generate_diary_number, extract_letter_fields

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
            send_whatsapp_message(sender, "Sorry, could not retrieve the images. Please resend.")
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
            send_whatsapp_message(sender, "Sorry, there was a database error. Please contact support.")
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
        send_whatsapp_message(sender, confirm_msg)
    except Exception as exc:
        logger.warning(f"WhatsApp batch confirmation failed: {exc}")


def _sweep_stale_batches():
    """
    On startup: flush any batches left pending from a previous server instance.
    Any batch whose last_image_at is > BATCH_FLUSH_DELAY seconds ago is processed.
    """
    try:
        stale_cutoff = datetime.utcnow() - timedelta(seconds=BATCH_FLUSH_DELAY)
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT sender_phone, tenant_id, receiver_number FROM letterbox_batches
                WHERE status = 'pending' AND last_image_at < :cutoff
            """), {"cutoff": stale_cutoff}).fetchall()
        for row in rows:
            logger.info(f"Startup sweep: flushing stale batch for {row[0]}, tenant={row[1]}")
            threading.Thread(
                target=_flush_letter_batch,
                args=(row[0], row[1], row[2]),
                daemon=True
            ).start()
    except Exception as exc:
        logger.warning(f"Stale batch sweep failed: {exc}")


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

    # PA whitelist check — sender must be a registered active user for this tenant
    try:
        with engine.connect() as conn:
            pa_row = conn.execute(
                text("""SELECT id, display_name FROM users
                        WHERE phone = :phone AND tenant_id = :tid AND is_active = true
                        LIMIT 1"""),
                {"phone": sender, "tid": current_tenant}
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
            send_whatsapp_message(sender, "Sorry, could not queue the image. Please resend.")
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

    # PA whitelist check
    try:
        with engine.connect() as conn:
            pa_row = conn.execute(
                text("SELECT id FROM users WHERE phone = :phone AND tenant_id = :tid AND is_active = true LIMIT 1"),
                {"phone": sender, "tid": current_tenant}
            ).fetchone()
    except Exception as exc:
        logger.error(f"PA check failed in MOVE handler: {exc}")
        return

    if not pa_row:
        logger.info(f"MOVE command from non-PA {sender} — ignored")
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
                send_whatsapp_message(sender, f"Could not find letter with ref {ref_upper}. Please check the diary number.")
                return
        label = "OUTBOX" if new_direction == "outbox" else "INBOX"
        send_whatsapp_message(sender, f"Done — {ref_upper} moved to {label}.")
        logger.info(f"MOVE: {ref_upper} → {new_direction} by PA {sender}, tenant {current_tenant}")
    except Exception as exc:
        logger.error(f"MOVE command DB update failed: {exc}")
        try:
            send_whatsapp_message(sender, "Sorry, could not update the letter. Please try again.")
        except Exception:
            pass


def _handle_pa_done_command(sender: str, receiver_number: str = ""):
    """
    PA typed DONE — immediately flush their pending batch without waiting for the timer.
    Silently ignored if sender is not a registered PA or has no pending batch.
    """
    if not receiver_number:
        receiver_number = os.getenv("WHATSAPP_PHONE_NUMBER_ID") or os.getenv("META_PHONE_NUMBER_ID", "")

    current_tenant = _resolve_tenant(receiver_number)

    # PA whitelist check
    try:
        with engine.connect() as conn:
            pa_row = conn.execute(
                text("SELECT id FROM users WHERE phone = :phone AND tenant_id = :tid AND is_active = true LIMIT 1"),
                {"phone": sender, "tid": current_tenant}
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
            send_whatsapp_message(sender, "No pending letter batch found. Send images first.")
        except Exception:
            pass
        return

    logger.info(f"DONE command from PA {sender} — flushing batch immediately")
    _flush_letter_batch(sender, current_tenant, receiver_number)


def _process_incoming_message(sender: str, message_body: str, receiver_number: str = ""):
    """Background task: AI processing + DB save + reply. Runs after 200 is returned to Meta."""
    if not receiver_number:
        receiver_number = os.getenv("WHATSAPP_PHONE_NUMBER_ID") or os.getenv("META_PHONE_NUMBER_ID", "")
    current_tenant = _resolve_tenant(receiver_number)

    logger.info(f"Incoming from {sender} → Tenant {current_tenant}")

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
        )
        return

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
                    "meta": json.dumps({"summary": message_body[:200]}),
                    "now": datetime.utcnow(),
                }
            )
            row = result.fetchone()
            case_id = row[0] if row else None
            logger.info(f"Saved raw grievance: case_id={case_id} tenant={current_tenant}")
    except Exception as e:
        logger.error(f"CRITICAL: DB save failed for raw grievance: {e}")
        # Even if DB fails, still try to acknowledge the citizen
        send_whatsapp_message(sender, "Thank you for contacting us. Your message has been received.")
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
        categories = grievance.get("categories", ["General"])
        category = categories[0] if isinstance(categories, list) and categories else "General"
        political_reply = ai_result.get("political_response", "Thank you for contacting us. Your message has been received.")

        location_name = grievance.get("location")
        final_constituency = None

        # Geo mapping — case-insensitive DB override first
        if location_name:
            lookup_key = str(location_name).lower().strip()
            try:
                geo_map = get_geo_overrides(current_tenant)
                geo_map_lower = {k.lower(): v for k, v in geo_map.items()}
                final_constituency = geo_map_lower.get(lookup_key)
                if final_constituency:
                    logger.info(f"Geo match: {lookup_key} → {final_constituency}")
            except Exception:
                logger.warning("Geo override lookup failed for tenant %s", current_tenant)

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

        send_whatsapp_message(sender, political_reply)

    except Exception as e:
        # AI failed — grievance is still saved as pending/Uncategorised
        logger.error(f"AI processing failed for case {case_id}: {e}")
        send_whatsapp_message(
            sender,
            "Thank you for contacting us. Your message has been received and will be reviewed by our team."
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
    msg_type = msg.get("type")
    sender = msg["from"]  # bare number e.g. "919876543210"

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
            background_tasks.add_task(_process_incoming_message, sender, message_body, display_number)
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
        return {"status": "ignored"}  # audio, video, documents, etc.


# ─────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────
@app.get("/")
def health_check():
    return {"status": "active", "system": "Needle Backend V8.1"}


# Recover any batches that were interrupted by a previous restart
_sweep_stale_batches()