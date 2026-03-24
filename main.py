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
except Exception:
    pass  # Column already exists — expected on subsequent deploys

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

# ─── Migration: add tenant_type column to tenants table (idempotent) ───
try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE tenants ADD COLUMN tenant_type VARCHAR DEFAULT 'mp'"))
        logger.info("Migration: added tenant_type column to tenants table")
        # Backfill: mark PR tenants based on config->type
        conn.execute(text("""
            UPDATE tenants SET tenant_type = 'aspirant'
            WHERE tenant_type = 'mp'
              AND config::text LIKE '%"type": "PR"%'
        """))
        logger.info("Migration: backfilled tenant_type for existing PR tenants")
except Exception:
    pass  # Column already exists — expected on subsequent deploys

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
# META CLOUD API HELPER
# ─────────────────────────────────────────
def send_whatsapp_message(to_number: str, body_text: str):
    """Send a WhatsApp reply via Meta Cloud API."""
    phone_number_id = os.getenv("META_PHONE_NUMBER_ID")
    access_token = os.getenv("META_ACCESS_TOKEN")

    if not phone_number_id or not access_token:
        logger.error("META_PHONE_NUMBER_ID or META_ACCESS_TOKEN not set.")
        return

    # Strip any whatsapp: prefix — Meta uses bare numbers
    to_number = to_number.replace("whatsapp:", "")

    url = f"https://graph.facebook.com/v21.0/{phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": body_text},
    }
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    try:
        resp = http_requests.post(url, json=payload, headers=headers, timeout=10)
        if resp.ok:
            logger.info(f"WhatsApp reply sent to {to_number} (id={resp.json().get('messages', [{}])[0].get('id')})")
        else:
            logger.error(f"Meta send failed: {resp.status_code} {resp.text}")
    except Exception as e:
        logger.error(f"Meta send error: {e}")


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


def _process_incoming_message(sender: str, message_body: str, receiver_number: str = ""):
    """Background task: AI processing + DB save + reply. Runs after 200 is returned to Meta."""
    if not receiver_number:
        receiver_number = os.getenv("META_PHONE_NUMBER_ID", "")
    current_tenant = 1

    # Tenant lookup — DB overrides first, then users table
    try:
        phone_map = get_phone_tenant_mapping()
        if receiver_number in phone_map:
            current_tenant = phone_map[receiver_number]
            logger.info(f"DB override match: {receiver_number} → Tenant {current_tenant}")
    except Exception:
        pass

    if current_tenant == 1:
        try:
            with engine.connect() as conn:
                lookup = text("SELECT id AS tenant_id FROM tenants WHERE whatsapp_number = :num LIMIT 1")
                tenant_record = conn.execute(lookup, {"num": receiver_number}).fetchone()
                if tenant_record:
                    current_tenant = tenant_record[0]
        except Exception as e:
            logger.warning(f"Tenant DB lookup failed: {e}")

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
                pass

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
    if msg.get("type") != "text":
        return {"status": "ignored"}  # ignore images/audio for now

    sender = msg["from"]          # bare number e.g. "919876543210"
    message_body = msg["text"]["body"].strip()

    if not message_body:
        return {"status": "ignored"}

    # Extract the real business phone number from Meta metadata for tenant routing
    # Meta sends it as bare digits (e.g. "15551636821"), we normalise to "+15551636821"
    display_number = entry.get("metadata", {}).get("display_phone_number", "")
    if display_number and not display_number.startswith("+"):
        display_number = f"+{display_number}"

    # Return 200 to Meta immediately — process AI + send reply in background
    background_tasks.add_task(_process_incoming_message, sender, message_body, display_number)
    return {"status": "received"}


# ─────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────
@app.get("/")
def health_check():
    return {"status": "active", "system": "Needle Backend V8.1"}