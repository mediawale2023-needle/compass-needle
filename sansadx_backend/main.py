from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
import sqlite3
import datetime
import json
import os
from .twilio_client import send_whatsapp_message, send_typing_indicator
from .ai_engine import ask_groq_agent

app = FastAPI()

# Database Path
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

@app.get("/", response_class=HTMLResponse)
def home():
    # 🔍 MINI DASHBOARD: Read DB and show HTML Table
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    rows = c.execute("SELECT * FROM grievances ORDER BY id DESC").fetchall()
    conn.close()

    html = """
    <html>
    <head>
        <title>MP Grievance Data (Live)</title>
        <style>
            body { font-family: sans-serif; padding: 20px; }
            table { border-collapse: collapse; width: 100%; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #f2f2f2; }
            tr:nth-child(even) { background-color: #f9f9f9; }
            .status-new { color: green; font-weight: bold; }
        </style>
    </head>
    <body>
        <h2>📊 Live Grievances (Direct from Railway)</h2>
        <table>
            <tr>
                <th>ID</th>
                <th>Date</th>
                <th>Category</th>
                <th>Location</th>
                <th>Status</th>
                <th>Message</th>
            </tr>
    """
    
    for row in rows:
        html += f"""
            <tr>
                <td>{row['id']}</td>
                <td>{row['date']}</td>
                <td>{row['category']}</td>
                <td>{row['location']}</td>
                <td class="status-new">{row['status']}</td>
                <td>{row['description']}</td>
            </tr>
        """
    
    html += "</table></body></html>"
    return html

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

    # 1. Ask AI (70B Model)
    ai_result = ask_groq_agent(message_body)
    print(f"🧠 RAW AI RESPONSE: {json.dumps(ai_result)}")

    # 2. Extract Data
    keys = {k.lower(): v for k, v in ai_result.items()}
    status = keys.get("status", "UNKNOWN").upper()
    political_response = keys.get("political_response", "Namaste. I have received your message.")
    grievance_data = keys.get("grievance_data", {})
    if not grievance_data: grievance_data = {}

    # 3. SAVE TO DB (Completed Only)
    if status == "COMPLETED":
        category = grievance_data.get("category", "Other")
        location = grievance_data.get("location_english") or grievance_data.get("location_native") or "Unknown"
        
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            current_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            c.execute("INSERT INTO grievances (date, sender, category, location, status, description) VALUES (?, ?, ?, ?, ?, ?)",
                      (current_date, sender, category, location, "New", message_body))
            conn.commit()
            conn.close()
            print(f"💾 SAVED: {category} in {location}")
        except Exception as e:
            print(f"❌ DB Error: {e}")

    # 4. Send Reply
    send_whatsapp_message(sender, political_response)

    return {"status": "processed"}
