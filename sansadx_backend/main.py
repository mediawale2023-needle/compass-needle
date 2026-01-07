from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import os
import json
import datetime
from sqlalchemy import create_engine, text
from .twilio_client import send_whatsapp_message, send_typing_indicator
from .ai_engine import ask_groq_agent

app = FastAPI()

# --- 1. CONNECT TO THE PERMANENT DATABASE (Postgres) ---
# We use the DATABASE_URL provided by Railway
DB_URL = os.getenv("DATABASE_URL")

# Fallback for local testing if needed, but in Prod this uses Postgres
if not DB_URL:
    print("⚠️ WARNING: No DATABASE_URL found. Using local temp file (Data will be lost on restart).")
    engine = create_engine("sqlite:///./temp_local.db")
else:
    # Fix URL format for SQLAlchemy (Postgres requires 'postgresql://')
    if DB_URL.startswith("postgres://"):
        DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DB_URL)

# --- 2. MEMORY SYSTEM (Context Manager) ---
def get_user_context(phone_number):
    """
    Checks DB to see if we already know this user's location/constituency.
    Returns a context string to feed into the AI.
    """
    try:
        with engine.connect() as conn:
            # Look for the most recent message from this user that had a valid location
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
    
    return "" # No context found, treat as new user

# --- 3. WHATSAPP WEBHOOK ---
@app.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request):
    form_data = await request.form()
    sender = form_data.get("From", "").replace("whatsapp:", "") # Clean number
    message_body = form_data.get("Body", "").strip()
    message_sid = form_data.get("MessageSid")

    if not message_body: return {"status": "ignored"}

    print(f"📩 Incoming from {sender}: {message_body}")
    
    # Send "Typing..." status to WhatsApp so user knows we are thinking
    try:
        send_typing_indicator(message_sid)
    except:
        pass

    # A. FETCH CONTEXT (The Memory Fix)
    # We check if we know this person BEFORE asking the AI
    user_context = get_user_context(sender)
    
    # B. PREPARE PROMPT
    # We combine the User's Message + The Hidden Context
    full_prompt = f"{user_context}\n\nUSER MESSAGE: {message_body}"

    # C. ASK AI AGENT
    ai_result = ask_groq_agent(full_prompt)
    print(f"🧠 AI Response: {json.dumps(ai_result)}")

    # D. EXTRACT & NORMALIZE DATA
    # Ensure keys exist even if AI missed them
    grievance = ai_result.get("grievance_data", {}) or {}
    
    category = grievance.get("category", "General")
    status = ai_result.get("status", "new").lower()
    political_reply = ai_result.get("political_response", "Thank you. We have received your message.")
    
    # Location Logic
    specific_loc = grievance.get("location_english") or grievance.get("location_native") or ""
    assembly = grievance.get("constituency") or ""
    
    # Construct Metadata JSON (Standard Format for Dashboard)
    # We set 'location_resolved' to True only if we actually got data
    has_location = bool(specific_loc or assembly)
    
    meta_data = {
        "user_intent": ai_result.get("user_intent", "complaint"),
        "location_resolved": has_location, 
        "matched_value": specific_loc,
        "assembly_constituency": assembly,
        "summary": grievance.get("summary", message_body)
    }

    # E. SAVE TO POSTGRES (The Persistence Fix)
    # We write to the 'cases' table so the Dashboard sees it immediately
    try:
        with engine.begin() as conn: # Transactional save
            conn.execute(
                text("""
                    INSERT INTO cases 
                    (tenant_id, user_phone, category, raw_message, status, case_metadata, created_at, updated_at)
                    VALUES (:tid, :phone, :cat, :msg, :stat, :meta, NOW(), NOW())
                """),
                {
                    "tid": 1, # Default Tenant
                    "phone": sender,
                    "cat": category,
                    "msg": message_body,
                    "stat": status,
                    "meta": json.dumps(meta_data)
                }
            )
            print(f"✅ Saved to Postgres: {sender} | {category}")
            
    except Exception as e:
        print(f"❌ DB Save Failed: {e}")

    # F. REPLY TO USER
    send_whatsapp_message("whatsapp:" + sender, political_reply)

    return {"status": "processed"}

# --- 4. OPTIONAL: SIMPLE HEALTH CHECK ---
@app.get("/")
def health_check():
    return {"status": "active", "system": "Needle Backend V2 (Postgres)"}