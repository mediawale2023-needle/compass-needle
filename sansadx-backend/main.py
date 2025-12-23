from fastapi import FastAPI, HTTPException, Depends, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc
import json
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

# --- MODULE IMPORTS ---
from db import SessionLocal, init_db, Case, Tenant, User
from jurisdiction import get_classification
from prompts import SYSTEM_PROMPT
from llm_client import call_sansadx_model
from twilio_client import send_whatsapp_message, send_typing_indicator # <--- NEW IMPORT

app = FastAPI(title="Needle SaaS Core", version="1.6 (Human Touch)")

# --- DATABASE DEPENDENCY ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.on_event("startup")
def on_startup():
    init_db()

# --- PYDANTIC MODELS ---
class SimulationRequest(BaseModel):
    message: str
    phone: str = "simulate"
    target_bot: str = "sim_ls" 

class LoginRequest(BaseModel):
    username: str
    password: str

class TenantCreate(BaseModel):
    name: str
    constituency: str
    whatsapp_number: str
    subscription_plan: str = "Pro"
    config: Dict[str, Any] = {"language": "English", "type": "LOK_SABHA", "map_enabled": True}

class TenantUpdate(BaseModel):
    name: Optional[str] = None
    subscription_plan: Optional[str] = None
    config: Optional[Dict[str, Any]] = None

# --- CORE LOGIC ---
def process_and_reply(user_message: str, user_phone: str, db: Session, target_bot_number: str = None, message_sid: str = None):
    # 1. 🚦 ROUTING LOGIC
    # Look up the Tenant based on the Bot Number receiving the message
    if target_bot_number:
        tenant = db.query(Tenant).filter(Tenant.whatsapp_number == target_bot_number).first()
    else:
        # Fallback (e.g., if testing without a bot number, default to first)
        tenant = db.query(Tenant).first()

    # If no tenant found (and no fallback), return error
    if not tenant:
        return Case(response_to_citizen="System Error: Unknown Bot Number.", category="error", status="error")

    print(f"📥 Processing for Tenant: {tenant.name} (ID: {tenant.id})")

    # 👇 NEW: TRIGGER TYPING INDICATOR
    # This tells the user "Suresh is typing..." while the AI thinks
    if message_sid:
        send_typing_indicator(message_sid)

    # 🧠 FETCH CONFIG & DYNAMIC KNOWLEDGE
    tenant_config = tenant.config or {}
    primary_lang = tenant_config.get("language", "English")
    supported_langs = tenant_config.get("supported_languages", [primary_lang])
    
    # Fetch the specific map knowledge for this MP
    jurisdiction_guide = tenant_config.get("jurisdiction_guide", "No specific location data available.")

    # 2. CONTEXT CHECK (Scoped to Tenant)
    existing_case = db.query(Case).filter(
        Case.tenant_id == tenant.id,  # Ensure we only check THIS client's history
        Case.user_phone == user_phone, 
        Case.status == "awaiting_info"
    ).order_by(desc(Case.created_at)).first()

    # 3. CONSTRUCT AI PROMPT
    rule_based = get_classification(user_message)
    
    language_directive = f"""
    CRITICAL LANGUAGE INSTRUCTIONS:
    - The MP's Default Language is: {primary_lang}
    - Supported Languages: {', '.join(supported_langs)}
    - IF user speaks Supported -> REPLY IN THAT LANGUAGE.
    - ELSE -> REPLY IN {primary_lang}.
    """

    # Inject the specific Jurisdiction Guide into the generic template
    base_prompt = SYSTEM_PROMPT.replace("{JURISDICTION_CONTEXT}", jurisdiction_guide)

    full_system_prompt = f"{base_prompt}\n\n{language_directive}\n\nContext: Rule-based suggests: {json.dumps(rule_based)}"

    # 4. AI PROCESSING
    try:
        llm_raw = call_sansadx_model(user_message, full_system_prompt)
        ai_data = json.loads(llm_raw)
        intent = ai_data.get("intent", "GRIEVANCE")
    except Exception as e:
        print(f"⚠️ AI Error: {e}")
        intent = "GRIEVANCE"
        ai_data = {"political_response": "System Error.", "grievance_data": {}}

    response_text = ai_data.get("political_response", "Namaste.")
    g_data = ai_data.get("grievance_data", {})

    # 5. SAVE TO DATABASE
    if intent == "GRIEVANCE":
        if existing_case:
            case = existing_case
            case.raw_message = f"{case.raw_message} . {user_message}"
            case.status = "new"
        else:
            case = Case(tenant_id=tenant.id, user_phone=user_phone, status="new")
            db.add(case)

        case.category = g_data.get("category", "General")
        case.location = g_data.get("location", "Unknown") 
        case.ward = g_data.get("ward", "Unknown") 
        case.response_to_citizen = response_text
        case.notes_for_staff = g_data.get("summary", "No summary")

        db.commit()
        db.refresh(case)

        if user_phone and "simulate" not in user_phone:
            send_whatsapp_message(user_phone, case.response_to_citizen)
        
        return case

    return Case(response_to_citizen=response_text, category="ignored", status="ignored")

# --- 🔐 AUTHENTICATION ENDPOINT ---
@app.post("/auth/login")
def login(creds: LoginRequest, db: Session = Depends(get_db)):
    """Checks DB for user and returns their Role + Tenant ID"""
    user = db.query(User).filter(User.username == creds.username).first()
    
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    # Simple password check
    if user.password_hash != creds.password:
        raise HTTPException(status_code=401, detail="Incorrect password")
    
    return {
        "status": "success",
        "username": user.username,
        "role": user.role,        
        "tenant_id": user.tenant_id
    }

# --- ADMIN ENDPOINTS ---

@app.post("/admin/tenants")
def create_tenant(tenant: TenantCreate, db: Session = Depends(get_db)):
    existing = db.query(Tenant).filter(Tenant.whatsapp_number == tenant.whatsapp_number).first()
    if existing:
        raise HTTPException(status_code=400, detail="WhatsApp Number already registered.")
    
    new_tenant = Tenant(
        name=tenant.name,
        constituency=tenant.constituency,
        whatsapp_number=tenant.whatsapp_number,
        subscription_plan=tenant.subscription_plan,
        config=tenant.config 
    )
    db.add(new_tenant)
    db.commit()
    db.refresh(new_tenant)
    return {"status": "created", "id": new_tenant.id}

@app.patch("/admin/tenants/{tenant_id}")
def update_tenant(tenant_id: int, update_data: TenantUpdate, db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Client not found")
    
    if update_data.name: tenant.name = update_data.name
    if update_data.subscription_plan: tenant.subscription_plan = update_data.subscription_plan
    if update_data.config is not None: tenant.config = update_data.config
        
    db.commit()
    return {"status": "updated", "id": tenant.id}

@app.get("/admin/tenants")
def list_tenants(db: Session = Depends(get_db)):
    return db.query(Tenant).all()

@app.get("/admin/stats")
def global_stats(db: Session = Depends(get_db)):
    return {
        "clients": db.query(Tenant).count(),
        "total_grievances": db.query(Case).count(),
        "system_health": "100%"
    }

@app.get("/tenant/config")
def get_tenant_config(db: Session = Depends(get_db)):
    tenant = db.query(Tenant).first()
    if not tenant: return {}
    return tenant.config

# --- STANDARD ENDPOINTS ---

@app.get("/")
def home():
    return {"status": "Needle SaaS Backend Online"}

# UPDATED WEBHOOK FOR ROUTING & TYPING
@app.post("/whatsapp/webhook")
async def whatsapp_webhook(
    Body: str = Form(""), 
    From: str = Form(...), 
    To: str = Form(...), 
    MessageSid: str = Form(...),  # <--- NEW: Capture Message ID for typing
    db: Session = Depends(get_db)
):
    if not Body: return {"status": "no_content"}
    
    # Clean the bot number (remove "whatsapp:" prefix)
    bot_number = To.replace("whatsapp:", "")
    
    # Pass MessageSid to the processor
    process_and_reply(Body, From, db, target_bot_number=bot_number, message_sid=MessageSid)
    return {"status": "processed"}

# UPDATED SIMULATOR FOR ROUTING
@app.post("/analyze")
def simulate(payload: SimulationRequest, db: Session = Depends(get_db)):
    # Pass target_bot to routing logic (message_sid is None for simulation)
    case = process_and_reply(payload.message, payload.phone, db, target_bot_number=payload.target_bot, message_sid=None)
    
    if case.status == "error":
        return {"status": "error", "response_to_citizen": case.response_to_citizen}

    return {"status": "success", "id": case.id, "response_to_citizen": case.response_to_citizen}

@app.get("/cases")
def list_cases(db: Session = Depends(get_db)):
    return db.query(Case).order_by(Case.created_at.desc()).all()