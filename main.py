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
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy import text
from twilio.rest import Client

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
app = FastAPI(title="Needle Backend", version="8.0")

# Rate limiter state
if _rate_limiting_enabled:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — use security config origins (falls back to ["*"] if config unavailable)
allow_creds = ALLOWED_ORIGINS != ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=allow_creds,
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
# TWILIO HELPER
# ─────────────────────────────────────────
def send_whatsapp_message(to_number: str, body_text: str):
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")

    if not account_sid or not auth_token:
        logger.error("Twilio credentials missing in environment variables.")
        return

    client = Client(account_sid, auth_token)
    try:
        formatted_to = to_number if to_number.startswith("whatsapp:") else f"whatsapp:{to_number}"
        client.messages.create(from_=from_number, body=body_text, to=formatted_to)
        logger.info(f"WhatsApp reply sent to {formatted_to}")
    except Exception as e:
        logger.error(f"Twilio send failed: {e}")


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
# WHATSAPP WEBHOOK
# ─────────────────────────────────────────
@app.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request):
    form_data = await request.form()
    sender = form_data.get("From", "").replace("whatsapp:", "")
    message_body = form_data.get("Body", "").strip()

    if not message_body:
        return {"status": "ignored"}

    receiver_number = form_data.get("To", "")
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
                lookup = text("SELECT tenant_id FROM users WHERE whatsapp_number = :num LIMIT 1")
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
    return {"status": "processed"}


# ─────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────
@app.get("/")
def health_check():
    return {"status": "active", "system": "Needle Backend V8"}