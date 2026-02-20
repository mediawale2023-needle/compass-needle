from sansadx_backend.ai_engine import ask_chatgpt_agent  # <--- Updated from groq
import os
import json  # <--- Added missing import for metadata handling
import sentry_sdk
from fastapi import FastAPI, Depends, HTTPException, Request
from sqlalchemy import create_engine, text  # <--- Added 'text'
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from twilio.rest import Client # <--- Added for direct Twilio support

# --- TAD NECESSARY: Import Geography Resolver ---
try:
    from modules.geography_resolver import resolve_constituency
except ImportError:
    def resolve_constituency(text, tenant_id): return None, None

# Initialize Sentry
sentry_sdk.init(
    dsn="https://d3ce9f7d4b46c5a117e372925acfdbf2@o4510685197434880.ingest.us.sentry.io/4510685203857408",
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
)
# ----------------------------

app = FastAPI()

# ==========================================
# 0. TWILIO HELPER (DIRECT DEFINITION TO FIX IMPORT ERROR)
# ==========================================
def send_whatsapp_message(to_number, body_text):
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
    
    if not account_sid or not auth_token:
        print("❌ Twilio credentials missing in Environment Variables")
        return

    client = Client(account_sid, auth_token)
    try:
        # Ensure to_number has the whatsapp: prefix
        formatted_to = to_number if to_number.startswith("whatsapp:") else f"whatsapp:{to_number}"
        client.messages.create(from_=from_number, body=body_text, to=formatted_to)
        print(f"📤 Reply sent to {formatted_to}")
    except Exception as e:
        print(f"❌ Twilio Send Failed: {e}")

# ==========================================
# 1. DATABASE CONNECTION
# ==========================================
DB_URL = os.getenv("DATABASE_URL")
if not DB_URL:
    print("⚠️ WARNING: No DATABASE_URL found. Using local temp file.")
    engine = create_engine("sqlite:///./temp_local.db")
else:
    # Fix for Heroku/Railway Postgres URLs
    if DB_URL.startswith("postgres://"):
        DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DB_URL)

# --- SELF-HEALING: ENSURE TABLE EXISTS ---
def init_db():
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS cases (
                    id SERIAL PRIMARY KEY,
                    tenant_id INTEGER DEFAULT 1,
                    user_phone TEXT,
                    category TEXT,
                    raw_message TEXT,
                    status TEXT,
                    case_metadata TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """))
            print("✅ Database: 'cases' table verified.")
    except Exception as e:
        print(f"❌ Database Init Failed: {e}")

init_db()

# ==========================================
# 2. CONTEXT MEMORY (PREVENTS REPEATED QUESTIONS)
# ==========================================
def get_user_context(phone_number):
    try:
        with engine.connect() as conn:
            # FIX: Added CAST to TEXT for PostgreSQL compatibility with LIKE operator
            query = text("""
                SELECT case_metadata FROM cases 
                WHERE user_phone = :phone 
                AND CAST(case_metadata AS TEXT) LIKE '%location_resolved": true%'
                ORDER BY created_at DESC LIMIT 1
            """)
            result = conn.execute(query, {"phone": phone_number}).fetchone()
            
            if result and result[0]:
                # --- TAD NECESSARY FIX: Handle both dict and string types ---
                meta = result[0]
                if isinstance(meta, str):
                    meta = json.loads(meta)
                
                loc = meta.get("matched_value", "")
                const = meta.get("assembly_constituency", "")
                if loc or const:
                    return f"KNOWN USER CONTEXT: User is from Location: {loc}, Constituency: {const}. DO NOT ask for location."
    except Exception as e:
        print(f"⚠️ Context Fetch Error: {e}")
    return ""

# ==========================================
# 3. WHATSAPP WEBHOOK (THE CORE LOGIC)
# ==========================================
@app.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request):
    form_data = await request.form()
    sender = form_data.get("From", "").replace("whatsapp:", "")
    message_body = form_data.get("Body", "").strip()
    
    # --- TAD NECESSARY: Dynamic Tenant Lookup with Local Override ---
    receiver_number = form_data.get("To", "")
    current_tenant = 1 # Default fallback
    overrides_data = {}
    
    # Check JSON Override first
    try:
        if os.path.exists("tenant_overrides.json"):
            with open("tenant_overrides.json", "r") as f:
                overrides_data = json.load(f)
                if receiver_number in overrides_data:
                    current_tenant = overrides_data[receiver_number]
                    print(f"⚡ JSON Override Match: {receiver_number} -> Tenant {current_tenant}")
                else:
                    raise Exception("No JSON Match")
    except:
        # Fallback to DB
        try:
            with engine.connect() as conn:
                lookup_query = text("SELECT tenant_id FROM users WHERE whatsapp_number = :num LIMIT 1")
                tenant_record = conn.execute(lookup_query, {"num": receiver_number}).fetchone()
                if tenant_record:
                    current_tenant = tenant_record[0]
        except Exception as e:
            print(f"⚠️ Tenant Database Lookup Failed: {e}")

    if not message_body: return {"status": "ignored"}

    print(f"📩 Incoming from {sender} to {receiver_number} (Resolved Tenant: {current_tenant})")

    # A. GET CONTEXT & ASK AI
    user_context = get_user_context(sender)
    full_prompt = f"{user_context}\n\nUSER MESSAGE: {message_body}"
    
    # Pass the resolved dynamic tenant_id to the AI Engine
    ai_result = ask_chatgpt_agent(full_prompt, tenant_id=current_tenant)

    if isinstance(ai_result, str):
        try:
            ai_result = json.loads(ai_result)
        except:
            ai_result = {"status": "INCOMPLETE", "political_response": ai_result, "grievance_data": {}}

    # B. DATA PREP (INTENT & CONSTITUENCY HANDLING)
    grievance = ai_result.get("grievance_data", {}) or {}
    status = str(ai_result.get("status", "new")).lower()
    categories = grievance.get("categories", ["General"])
    category = categories[0] if isinstance(categories, list) and categories else "General"
    political_reply = ai_result.get("political_response", "Thank you.")
    
    location_name = grievance.get("location")
    final_constituency = None

    # --- TAD NECESSARY: Case-Insensitive JSON Lookup ---
    if location_name and overrides_data:
        lookup_key = str(location_name).lower().strip()
        geo_map = overrides_data.get("geo_overrides", {}).get(str(current_tenant), {})
        final_constituency = geo_map.get(lookup_key)
        
        if final_constituency:
            print(f"🎯 Local Map Match: {lookup_key} -> {final_constituency}")

    # Fallback logic
    if not final_constituency:
        final_constituency = (
            grievance.get("assembly_constituency") or 
            grievance.get("constituency") or 
            ai_result.get("constituency") or 
            ai_result.get("assembly_constituency")
        )
        if (not final_constituency or final_constituency == "Unknown") and location_name:
            _, resolved_const = resolve_constituency(location_name, current_tenant)
            final_constituency = resolved_const if resolved_const != "Unknown" else None

    if not final_constituency:
        final_constituency = "Unknown"

    meta_data = {
        "user_intent": status,
        "location_resolved": bool(location_name and final_constituency != "Unknown"), 
        "matched_value": location_name or "",
        "assembly_constituency": final_constituency,
        "summary": grievance.get("summary", message_body[:100])
    }

    # C. SAVE TO POSTGRES
    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO cases 
                    (tenant_id, user_phone, category, raw_message, status, case_metadata, created_at)
                    VALUES (:tid, :phone, :cat, :msg, :stat, :meta, NOW())
                """),
                {
                    "tid": current_tenant, 
                    "phone": sender,
                    "cat": category,
                    "msg": message_body,
                    "stat": status,
                    "meta": json.dumps(meta_data)
                }
            )
            print(f"✅ Saved Status: '{status}' | Tenant: {current_tenant} | Constituency: '{final_constituency}'")
    except Exception as e:
        print(f"❌ DB Save Failed: {e}")

    # --- TAD NECESSARY: MP's Standardized Professional Response ---
    if status == "completed":
        is_hindi_script = any(ord(char) > 127 for char in message_body)
        if is_hindi_script:
            political_reply = f"आपकी समस्या (क्षेत्र: {final_constituency}) नोट कर ली गई है। उचित कार्यवाही के लिए इसे संबंधित विभाग को भेज दिया गया है। अपडेट आपको यहीं प्राप्त होगा।"
        else:
            political_reply = f"Aapki samasya (Constituency: {final_constituency}) note kar li gayi hai. Isse department ko bhej diya gaya hai. Aapko jald hi update milega."

    # --- TAD NECESSARY: EXECUTE SEND ---
    send_whatsapp_message(sender, political_reply)
        
    return {"status": "processed"}

@app.get("/")
def health_check():
    return {"status": "active", "system": "Needle Backend V7 (Deterministic Geo-Mapping)"}