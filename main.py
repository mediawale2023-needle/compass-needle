from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import os
import json
import datetime
from sqlalchemy import create_engine, text
# Now this import works because we are in the root folder!
from modules.twilio_client import send_whatsapp_message, send_typing_indicator
from modules.ai_engine import ask_groq_agent

app = FastAPI()

# --- 1. CONNECT TO DATABASE ---
DB_URL = os.getenv("DATABASE_URL")
if not DB_URL:
    print("⚠️ WARNING: No DATABASE_URL found. Using local temp file.")
    engine = create_engine("sqlite:///./temp_local.db")
else:
    if DB_URL.startswith("postgres://"):
        DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DB_URL)

# --- 1.1 SELF-HEALING: ENSURE TABLE EXISTS ---
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

# --- 2. MEMORY SYSTEM ---
def get_user_context(phone_number):
    try:
        with engine.connect() as conn:
            query = text("""
                SELECT case_metadata FROM cases 
                WHERE user_phone = :phone 
                AND case_metadata LIKE '%location_resolved": true%'
                ORDER BY created_at DESC LIMIT 1
            """)
            result = conn.execute(query, {"phone": phone_number}).fetchone()
            
            if result and result[0]:
                meta = json.loads(result[0])
                loc = meta.get("matched_value", "")
                const = meta.get("assembly_constituency", "")
                if loc or const:
                    return f"KNOWN USER CONTEXT: User is from Location: {loc}, Constituency: {const}. DO NOT ask for location."
    except Exception as e:
        print(f"⚠️ Context Fetch Error: {e}")
    return ""

# --- 3. WHATSAPP WEBHOOK ---
@app.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request):
    form_data = await request.form()
    sender = form_data.get("From", "").replace("whatsapp:", "")
    message_body = form_data.get("Body", "").strip()

    if not message_body: return {"status": "ignored"}

    print(f"📩 Incoming from {sender}: {message_body}")

    # A. AI PROCESSING
    user_context = get_user_context(sender)
    full_prompt = f"{user_context}\n\nUSER MESSAGE: {message_body}"
    ai_result = ask_groq_agent(full_prompt)

    # B. DATA PREP
    grievance = ai_result.get("grievance_data", {}) or {}
    category = grievance.get("category", "General")
    political_reply = ai_result.get("political_response", "Thank you.")
    status = ai_result.get("status", "new").lower()
    
    meta_data = {
        "user_intent": ai_result.get("user_intent", "complaint"),
        "location_resolved": bool(grievance.get("location_english")), 
        "matched_value": grievance.get("location_english") or "",
        "assembly_constituency": grievance.get("constituency") or "",
        "summary": grievance.get("summary", message_body)
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
            print(f"✅ Saved to Postgres: {sender}")
    except Exception as e:
        print(f"❌ DB Save Failed: {e}")

    send_whatsapp_message("whatsapp:" + sender, political_reply)
    return {"status": "processed"}

@app.get("/")
def health_check():
    return {"status": "active", "system": "Needle Backend V5 (Root Fix)"}