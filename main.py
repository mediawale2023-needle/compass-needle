"""
main.py — Needle Parliamentary Intelligence Platform
Backend Entry Point (FastAPI)
"""
from sansadx_backend.ai_engine import ask_chatgpt_agent
import os
import json
import logging
import sentry_sdk
from datetime import datetime
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

    url = f"https://graph.facebook.com/v19.0/{phone_number_id}/messages"
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

    # Get context & call AI
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
    political_reply = ai_result.get("political_response", "Thank you.")

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

    # Save to database
    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO cases
                    (tenant_id, user_phone, category, raw_message, status, case_metadata, is_critical, created_at)
                    VALUES (:tid, :phone, :cat, :msg, :stat, :meta, :crit, :now)
                """),
                {
                    "tid": current_tenant,
                    "phone": sender,
                    "cat": category,
                    "msg": message_body,
                    "stat": status,
                    "meta": json.dumps(meta_data),
                    "crit": ai_result.get("is_critical", False) or (status == "emergency"),
                    "now": datetime.utcnow(),
                }
            )
            logger.info(f"Saved: status='{status}' tenant={current_tenant} constituency='{final_constituency}'")
    except Exception as e:
        logger.error(f"DB save failed: {e}")

    send_whatsapp_message(sender, political_reply)


@app.post("/whatsapp/webhook")
@_webhook_decorate
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()

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