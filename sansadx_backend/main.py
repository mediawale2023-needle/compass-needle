from fastapi import FastAPI, Request, Form
import sqlite3
import datetime
import json
from .twilio_client import send_whatsapp_message, send_typing_indicator
from .ai_engine import ask_groq_agent

app = FastAPI()

# Database Setup
def init_db():
    try:
        conn = sqlite3.connect('sansadx.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS grievances
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      date TEXT,
                      sender TEXT,
                      category TEXT,
                      location TEXT,
                      status TEXT,
                      description TEXT)''')
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️ DB Init Error: {e}")

init_db()

@app.get("/")
def home():
    return {"status": "online", "message": "Needle Backend V3 (Debug Mode)"}

@app.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request):
    form_data = await request.form()
    
    sender = form_data.get("From")
    message_body = form_data.get("Body", "").strip()
    message_sid = form_data.get("MessageSid")

    if not message_body:
        return {"status": "ignored"}

    print(f"📩 Incoming: {message_body} from {sender}")
    send_typing_indicator(message_sid)

    # 1. Ask AI
    ai_result = ask_groq_agent(message_body)
    
    # 🔍 DEBUG: Print the RAW JSON to logs
    print(f"🧠 RAW AI RESPONSE: {json.dumps(ai_result)}")

    # 2. Extract Response (With Safety Nets)
    # Check for keys case-insensitively
    keys = {k.lower(): v for k, v in ai_result.items()}
    
    reply_text = keys.get("political_response")
    status = keys.get("status", "UNKNOWN")
    grievance_data = keys.get("grievance_data", {})

    # 🛡️ SAFETY NET: If reply is too short or missing, force a fallback
    if not reply_text or len(reply_text) < 10:
        print("⚠️ Warning: AI returned a bad response. Using Fallback.")
        if status == "COMPLETED":
            cat = grievance_data.get("category", "issue")
            loc = grievance_data.get("location_english", "your area")
            reply_text = f"Ji, I have noted the {cat} complaint in {loc}. You will be updated soon."
        elif status == "INCOMPLETE":
            reply_text = "Ji, I received your message. Could you please provide the exact location (Colony or Ward name)?"
        else:
            reply_text = "Namaste. I have received your message and will look into it."

    # 3. SAVE TO DB
    if status.upper() == "COMPLETED":
        # Handle case where grievance_data might be inside the 'data' key or direct
        if not grievance_data:
            grievance_data = keys.get("data", {})
            
        category = grievance_data.get("category", "Other")
        location = grievance_data.get("location_english", "Unknown")
        
        try:
            conn = sqlite3.connect('sansadx.db')
            c = conn.cursor()
            current_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            c.execute("INSERT INTO grievances (date, sender, category, location, status, description) VALUES (?, ?, ?, ?, ?, ?)",
                      (current_date, sender, category, location, "New", message_body))
            conn.commit()
            conn.close()
            print(f"💾 SAVED TO DB: {category} in {location}")
        except Exception as e:
            print(f"❌ DB Error: {e}")

    # 4. Send Reply
    send_whatsapp_message(sender, reply_text)

    return {"status": "processed"}
