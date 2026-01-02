import sys
import os
import json
import shutil
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from tempfile import NamedTemporaryFile

# =====================================
# PATH FIX (Ensures modules are found)
# =====================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

# =====================================
# FRAMEWORK IMPORTS
# =====================================
from fastapi import FastAPI, HTTPException, Depends, Form, File, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc
from dotenv import load_dotenv
import pdfplumber

load_dotenv()

# =====================================
# INTERNAL MODULE IMPORTS (ABSOLUTE)
# =====================================
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
    version="2.4 (Translation Bridge)"
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

class OnboardTenantRequest(BaseModel):
    name: str
    constituency: str
    whatsapp_number: str
    username: str
    password: str

# =====================================
# HELPER: PDF PARSER
# =====================================
def parse_polling_station_pdf(file_path: str):
    """Extracts polling station data from a PDF file."""
    stations = []
    print(f"📄 Parsing PDF: {file_path}")
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        clean_row = [str(cell).replace('\n', ' ').strip() for cell in row if cell]
                        if len(clean_row) >= 3 and clean_row[0].isdigit():
                            stations.append({
                                "station_number": clean_row[0],
                                "station_name": clean_row[1] if len(clean_row) > 1 else "",
                                "station_address": clean_row[2] if len(clean_row) > 2 else ""
                            })
    except Exception as e:
        print(f"❌ PDF Parsing Error: {e}")
    return stations

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

    # --- LANG FIX: INJECT "OPTIMISTIC" INSTRUCTION ---
    # We force the AI to assume the location is valid so it generates 
    # the success message in the correct language itself.
    lang_instruction = """
    \nIMPORTANT OVERRIDE: 
    If the user mentions a specific location/area name, even if it is NOT in the Jurisdiction List, 
    you must assume it is valid. 
    1. Set status to "COMPLETED".
    2. Generate a polite confirmation response in the USER'S LANGUAGE.
    3. Do not ask for clarification if a name is present.
    """
    
    system_prompt = SYSTEM_PROMPT.replace(
        "{JURISDICTION_CONTEXT}", jurisdiction_guide
    ) + lang_instruction

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

    # 🛡️ HALLUCINATION SHIELD
    ai_loc = grievance.get("location", "")

    if existing_case:
        case = existing_case
        case.raw_message += " | " + user_message
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
        loc_english = grievance.get("location_english", "")
        loc_native = grievance.get("location_native", "")
        ai_loc = grievance.get("location", "")
        
        search_term = loc_english if loc_english else (loc_native if loc_native else ai_loc)
        
        print(f"🌍 GEO BRIDGE ACTIVE:")
        print(f"   User Said: '{loc_native}'")
        print(f"   AI Translated: '{loc_english}'")
        
        geo_result = resolve_location(search_term, scope_parliamentary=None)
        
        final_place = None
        
        if geo_result.get("location_resolved"):
            print(f"   ✅ RESOLVED IN DB: {geo_result.get('matched_value')}")
            final_place = geo_result['matched_value']
            case.case_metadata = json.dumps(geo_result)
        
        elif search_term and len(search_term) > 2:
            print(f"   ⚠️ DB MATCH FAILED, USING AI EXTRACTION: {search_term}")
            final_place = search_term
            case.case_metadata = json.dumps({
                "location_resolved": False, 
                "source": "ai_fallback",
                "extracted_value": search_term
            })
        
        else:
            print(f"   ❌ LOCATION UNKNOWN")
            case.case_metadata = json.dumps({"location_resolved": False})

        # --- LANG FIX: DO NOT OVERWRITE RESPONSE ---
        if final_place:
            # We trust the AI's response because we forced it to be "COMPLETED" above.
            # This preserves the language (Hindi/Marathi/Kannada).
            # We only update the status to ensure it's recorded as new.
            case.status = "new"
            grievance["location"] = final_place
            
            # Note: We do NOT overwrite case.response_to_citizen with English anymore.
        # ----------------------------------

    db.commit()
    db.refresh(case)

    if user_phone and "simulate" not in user_phone:
        send_whatsapp_message(user_phone, response_text)

# =====================================
# ✅ NEW ENDPOINTS
# =====================================

@app.get("/tenant/config")
def get_tenant_config_endpoint(tenant_id: int = 1, db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant: return {}
    return {
        "id": tenant.id,
        "name": tenant.name,
        "constituency": tenant.constituency,
        "type": tenant.config.get("type", "LOK_SABHA"),
        "whatsapp_number": tenant.whatsapp_number
    }

@app.get("/cases")
def get_all_cases(tenant_id: int = 1, db: Session = Depends(get_db)):
    return db.query(Case).filter(Case.tenant_id == tenant_id).order_by(desc(Case.created_at)).all()

# =====================================
# AUTH & ADMIN ENDPOINTS
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

@app.post("/admin/onboard")
def onboard_tenant(data: OnboardTenantRequest, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.username == data.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already taken")

    last_tenant = db.query(Tenant).order_by(desc(Tenant.id)).first()
    new_id = (last_tenant.id + 1) if last_tenant else 1
    
    new_tenant = Tenant(
        id=new_id,
        name=data.name,
        constituency=data.constituency,
        whatsapp_number=data.whatsapp_number,
        config={
            "type": "LOK_SABHA",
            "jurisdiction_guide": f"Jurisdiction guide for {data.constituency}"
        }
    )
    db.add(new_tenant)
    db.flush()

    new_user = User(
        username=data.username,
        password_hash=data.password,
        role="mp",
        tenant_id=new_tenant.id
    )
    db.add(new_user)
    db.commit()
    
    return {
        "status": "success", 
        "message": f"Tenant '{data.name}' and User '{data.username}' created.",
        "tenant_id": new_tenant.id
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
    cases = db.query(Case).filter(Case.tenant_id == tenant_id).all()

    category_count = {}
    assembly_count = {}
    red_zones = []

    for c in cases:
        meta = {}
        if isinstance(c.case_metadata, str):
            try:
                meta = json.loads(c.case_metadata)
            except:
                meta = {}
        elif isinstance(c.case_metadata, dict):
            meta = c.case_metadata

        category = c.category or "General"
        category_count[category] = category_count.get(category, 0) + 1

        if meta.get("location_resolved"):
            assembly = meta.get("assembly_constituency")
            if assembly:
                assembly_count[assembly] = assembly_count.get(assembly, 0) + 1

    for assembly, count in assembly_count.items():
        if count >= 3:
            red_zones.append({
                "assembly_constituency": assembly,
                "count": count
            })

    return {
        "total_active_cases": len(cases),
        "category_breakdown": category_count,
        "assembly_breakdown": assembly_count,
        "red_zones": red_zones,
        "generated_at": now.isoformat()
    }

# =====================================
# PDF UPLOAD ENDPOINT
# =====================================
@app.post("/tenant/{tenant_id}/upload-polling-stations")
async def upload_polling_stations(
    tenant_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    print(f"📥 Receiving PDF upload for Tenant {tenant_id}: {file.filename}")
    
    with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        extracted_data = parse_polling_station_pdf(tmp_path)
    except Exception as e:
        os.remove(tmp_path)
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
    
    os.remove(tmp_path)

    if not extracted_data:
        raise HTTPException(status_code=400, detail="Could not extract any data. Check PDF format.")

    return {
        "status": "success",
        "tenant_id": tenant_id,
        "filename": file.filename,
        "stations_found": len(extracted_data),
        "sample_data": extracted_data[:5]
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