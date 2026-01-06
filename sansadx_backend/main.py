from fastapi import FastAPI, Request, Form
import sqlite3
import datetime
import json
import os
from .twilio_client import send_whatsapp_message, send_typing_indicator
from .ai_engine import ask_groq_agent

app = FastAPI()

# 🛠️ CRITICAL FIX: Point to the Root Database
# Go up one level (..) to escape 'sansadx_backend' folder
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'sansadx.db'))

def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
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
        print(f"✅ Database connected at: {DB_PATH}")
    except Exception as e:
        print(f"⚠️ DB Init Error: {e}")

init_db()

@app.get("/")
def home():
    return {"status": "online", "message": "Needle Backend V10 (Root DB Fix)"}

@app.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request):
    form_data = await request.form()
    
    sender = form_data.get("From")
    message_body = form_data.get("Body", "").strip()
    message_sid = form_data.get("MessageSid")

    if not message_body:
        return {"status": "ignored"}

    print(f"�� Incoming: {message_body} from {sender}")
    send_typing_indicator(message_sid)

    # 1. Ask AI (The 70B Brain)
    ai_result = ask_groq_agent(message_body)
    print(f"🧠 RAW AI RESPONSE: {json.dumps(ai_result)}")

    # 2. Extract Data (Safely)
    # Convert keys to lowercase to be safe
    keys = {k.lower(): v for k, v in ai_result.items()}
    
    status = keys.get("status", "UNKNOWN").upper()
    political_response = keys.get("political_response", "Namaste. I have received your message.")
    
    grievance_data = keys.get("grievance_data", {})
    if not grievance_data: grievance_data = {} # Safety

    # 3. SAVE TO DB (Only if Completed)
    if status == "COMPLETED":
        category = grievance_data.get("category", "Other")
        # Prefer English location, fallback to native, fallback to Unknown
        location = grievance_data.get("location_english") or grievance_data.get("location_native") or "Unknown"
        
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            current_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            c.execute("INSERT INTO grievances (date, sender, category, location, status, description) VALUES (?, ?, ?, ?, ?, ?)",
                      (current_date, sender, category, location, "New", message_body))
            conn.commit()
            conn.close()
            print(f"💾 SAVED TO ROOT DB ({DB_PATH}): {category} in {location}")
        except Exception as e:
            print(f"❌ DB Write Error: {e}")

    # 4. Send Reply
    send_whatsapp_message(sender, political_response)

    return {"status": "processed"}
