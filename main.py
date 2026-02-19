from sansadx_backend.ai_engine import ask_chatgpt_agent  # <--- Updated from groq
import os
import json  # <--- Added missing import for metadata handling
import sentry_sdk
from fastapi import FastAPI, Depends, HTTPException, Request
from sqlalchemy import create_engine, text  # <--- Added 'text'
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from twilio.rest import Client # <--- Added for direct Twilio support

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
        client.messages.create(from_=from_number, body=body_text, to=to_number)
        print(f"📤 Reply sent to {to_number}")
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

    if not message_body: return {"status": "ignored"}

    print(f"📩 Incoming from {sender}: {message_body}")

    # A. GET CONTEXT & ASK AI
    user_context = get_user_context(sender)
    full_prompt = f"{user_context}\n\nUSER MESSAGE: {message_body}"
    
    # Call the AI Engine (OpenAI v3.0)
    ai_result = ask_chatgpt_agent(full_prompt, tenant_id=1)

    # FIX: Safety check to handle cases where ai_result might be returned as a string
    if isinstance(ai_result, str):
        try:
            ai_result = json.loads(ai_result)
        except:
            ai_result = {"status": "INCOMPLETE", "political_response": ai_result, "grievance_data": {}}

    # B. DATA PREP (INTENT & CONSTITUENCY HANDLING)
    grievance = ai_result.get("grievance_data", {}) or {}
    
    # 1. Capture the status from OpenAI
    status = str(ai_result.get("status", "new")).lower()
    
    # 2. Capture Category (Handling the list from v3.0 schema)
    categories = grievance.get("categories", ["General"])
    category = categories[0] if isinstance(categories, list) and categories else "General"
    
    political_reply = ai_result.get("political_response", "Thank you.")

    # 3. Capture Constituency
    final_constituency = (
        grievance.get("assembly_constituency") or 
        grievance.get("constituency") or 
        ai_result.get("constituency") or 
        ai_result.get("assembly_constituency") or 
        None
    )

    # 4. Pack Metadata for the Dashboard
    meta_data = {
        "user_intent": status,
        "location_resolved": status == "completed", 
        "matched_value": grievance.get("location") or "",
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
                    "tid": 1,
                    "phone": sender,
                    "cat": category,
                    "msg": message_body,
                    "stat": status,
                    "meta": json.dumps(meta_data)
                }
            )
            print(f"✅ Saved Status: '{status}' | Constituency: '{final_constituency}'")
    except Exception as e:
        print(f"❌ DB Save Failed: {e}")

    # D. SEND REPLY
    try:
        send_whatsapp_message("whatsapp:" + sender, political_reply)
    except Exception as e:
        print(f"⚠️ Reply function error: {e}")
        
    return {"status": "processed"}

@app.get("/")
def health_check():
    return {"status": "active", "system": "Needle Backend V7 (OpenAI 3.0 Ready)"}