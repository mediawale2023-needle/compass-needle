import sys
import os
import json
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

# =====================================
# PATH FIX (Ensures modules are found)
# =====================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

# =====================================
# FRAMEWORK IMPORTS
# =====================================
from fastapi import FastAPI, HTTPException, Depends, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc
from dotenv import load_dotenv

load_dotenv()

# =====================================
# INTERNAL MODULE IMPORTS (ABSOLUTE)
# =====================================
# ✅ FIXED: No dots here
from db import SessionLocal, init_db, Case, Tenant, User
from jurisdiction import get_classification
from prompts import SYSTEM_PROMPT
from llm_client import call_sansadx_model
from twilio_client import send_whatsapp_message, send_typing_indicator

# Graceful import for geography (optional module)
try:
    from geography_resolver import (
        load_geography_index,
        enrich_grievance_with_location,
        get_index_stats,
        reload_index,
        resolve_location
    )
    GEO_ENABLED = True
except ImportError:
    print("⚠️ Geography Resolver not found. Running in basic mode.")
    GEO_ENABLED = False

# =====================================
# APP INIT
# =====================================
app = FastAPI(
    title="Needle SaaS Core",
    version="1.8 (Stable Backend)"
)

# =====================================
# DB DEPENDENCY
# =====================================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# =====================================
# STARTUP
# =====================================
@app.on_event("startup")
def on_startup():
    init_db()
    if GEO_ENABLED:
        load_geography_index()
        print(f"📍 Geography Loaded: {get_index_stats()}")

# =====================================
# MODELS
# =====================================
class SimulationRequest(BaseModel):
    message: str
    phone: str = "simulate"
    target_bot: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

# =====================================
# CORE PROCESSOR
# =====================================
def process_and_reply(
    user_message: str,
    user_phone: str,
    db: Session,
    target_bot_number: Optional[str] = None,
    message_sid: Optional[str] = None
):
    tenant = None

    if target_bot_number:
        tenant = db.query(Tenant).filter(
            Tenant.whatsapp_number == target_bot_number
        ).first()

    if not tenant:
        tenant = db.query(Tenant).first()

    if not tenant:
        return

    if message_sid:
        send_typing_indicator(message_sid)

    tenant_config = tenant.config or {}
    jurisdiction_guide = tenant_config.get("jurisdiction_guide", "")

    existing_case = db.query(Case).filter(
        Case.tenant_id == tenant.id,
        Case.user_phone == user_phone,
        Case.status == "awaiting_info"
    ).order_by(desc(Case.created_at)).first()

    rule_based = get_classification(user_message)

    system_prompt = SYSTEM_PROMPT.replace(
        "{JURISDICTION_CONTEXT}", jurisdiction_guide
    )

    final_prompt = f"{system_prompt}\n{json.dumps(rule_based)}"

    try:
        llm_raw = call_sansadx_model(user_message, final_prompt)
        ai_data = json.loads(llm_raw)
    except Exception:
        ai_data = {}

    response_text = ai_data.get(
        "political_response",
        "Ji, aapka sandesh mil gaya hai. Hum is par kaam kar rahe hain."
    )

    grievance = ai_data.get("grievance_data", {})
    category = grievance.get("category", "General")

    if existing_case:
        case = existing_case
        case.raw_message += " " + user_message
        case.status = "new"
    else:
        case = Case(
            tenant_id=tenant.id,
            user_phone=user_phone,
            raw_message=user_message,
            status="new"
        )
        db.add(case)

    case.category = category
    case.response_to_citizen = response_text
    case.notes_for_staff = grievance.get("summary", "")

    # 🌍 GEOGRAPHY ENRICHMENT
    if GEO_ENABLED:
        geo_input = {
            "raw_message": user_message,
            "location": grievance.get("location", "")
        }
        enriched = enrich_grievance_with_location(geo_input)
        geo = enriched.get("geography", {})
        case.metadata = json.dumps(geo)

    db.commit()
    db.refresh(case)

    if user_phone and "simulate" not in user_phone:
        send_whatsapp_message(user_phone, response_text)

# =====================================
# AUTH
# =====================================
@app.post("/auth/login")
def login(creds: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == creds.username).first()
    if not user or user.password_hash != creds.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return {
        "username": user.username,
        "role": user.role,
        "tenant_id": user.tenant_id
    }

# =====================================
# DASHBOARD SUMMARY
# =====================================
@app.get("/dashboard/summary")
def dashboard_summary(
    tenant_id: int,
    db: Session = Depends(get_db)
):
    now = datetime.utcnow()
    since = now - timedelta(hours=24)

    cases = db.query(Case).filter(
        Case.tenant_id == tenant_id,
        Case.status == "new",
        Case.created_at >= since
    ).all()

    category_count = {}
    assembly_count = {}
    red_zones = []

    for c in cases:
        meta = {}
        if isinstance(c.metadata, str):
            try:
                meta = json.loads(c.metadata)
            except:
                meta = {}

        if not meta.get("location_resolved"):
            continue

        assembly = meta.get("assembly_constituency")
        category = c.category or "General"

        if assembly:
            assembly_count[assembly] = assembly_count.get(assembly, 0) + 1

        category_count[category] = category_count.get(category, 0) + 1

    for assembly, count in assembly_count.items():
        if count >= 3:
            red_zones.append({
                "assembly_constituency": assembly,
                "count": count
            })

    return {
        "category_breakdown": category_count,
        "assembly_breakdown": assembly_count,
        "red_zones": red_zones,
        "generated_at": now.isoformat()
    }

# =====================================
# WHATSAPP WEBHOOK
# =====================================
@app.post("/whatsapp/webhook")
async def whatsapp_webhook(
    Body: str = Form(""),
    From: str = Form(...),
    To: str = Form(...),
    MessageSid: str = Form(...),
    db: Session = Depends(get_db)
):
    if not Body:
        return {"status": "empty"}

    bot = To.replace("whatsapp:", "")
    process_and_reply(
        Body,
        From,
        db,
        target_bot_number=bot,
        message_sid=MessageSid
    )
    return {"status": "ok"}

# =====================================
# GEOGRAPHY ENDPOINTS
# =====================================
@app.get("/geography/stats")
def geography_stats():
    if not GEO_ENABLED: return {"status": "disabled"}
    return get_index_stats()

@app.post("/geography/reload")
def geography_reload():
    if not GEO_ENABLED: return {"status": "disabled"}
    reload_index()
    return get_index_stats()

@app.post("/geography/resolve")
def geography_test(text: str):
    if not GEO_ENABLED: return {"status": "disabled"}
    return resolve_location(text)

# =====================================
# HEALTH CHECK
# =====================================
@app.get("/")
def home():
    return {"status": "Needle backend running"}