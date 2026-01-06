from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
import sqlite3
import datetime
import json
import os
from .twilio_client import send_whatsapp_message, send_typing_indicator
from .ai_engine import ask_groq_agent

app = FastAPI()

# 🛠️ DATABASE CONFIGURATION
# We use the current directory to ensure permissions work on Railway
DB_PATH = "sansadx.db"

def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # Create table with flexible columns
        c.execute('''CREATE TABLE IF NOT EXISTS grievances
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      date TEXT,
                      sender TEXT,
                      category TEXT,
                      location TEXT,
                      status TEXT,
                      ai_response TEXT,
                      original_message TEXT)''')
        conn.commit()
        conn.close()
        print(f"✅ Database initialized at: {os.path.abspath(DB_PATH)}")
    except Exception as e:
        print(f"❌ DB Init Error: {e}")

init_db()

# 📊 1. THE DASHBOARD (Frontend)
@app.get("/", response_class=HTMLResponse)
def dashboard():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    # Get all rows, newest first
    rows = c.execute("SELECT * FROM grievances ORDER BY id DESC").fetchall()
    conn.close()

    # Simple, clean HTML UI
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>MP SansadX - Live Dashboard</title>
        <meta http-equiv="refresh" content="10"> <style>
            body { font-family: -apple-system, sans-serif; background: #f4f4f9; padding: 20px; }
            .container { max-width: 1000px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
            h2 { color: #333; border-bottom: 2px solid #0070f3; padding-bottom: 10px; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th { background: #0070f3; color: white; padding: 12px; text-align: left; }
            td { padding: 12px; border-bottom: 1px solid #ddd; color: #333; }
            tr:hover { background: #f1f1f1; }
            .tag { padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }
            .COMPLETED { background: #d4edda; color: #155724; }
            .INCOMPLETE { background: #fff3cd; color: #856404; }
            .OFFENSIVE { background: #f8d7da; color: #721c24; }
            .NEW { background: #cce5ff; color: #004085; }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>🇮🇳 MP Grievance Dashboard (Live)</h2>
            <p>Showing live data from Railway Database.</p>
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Time</th>
                        <th>Sender</th>
                        <th>Category / Location</th>
                        <th>Status</th>
                        <th>Message</th>
                    </tr>
                </thead>
                <tbody>
    """
    
    for row in rows:
        status_class = row['status'] if row['status'] in ['COMPLETED', 'INCOMPLETE', 'OFFENSIVE'] else 'NEW'
        html += f"""
            <tr>
                <td>#{row['id']}</td>
                <td>{row['date'].split(' ')[1]}</td>
                <td>{row['sender']}</td>
                <td>
                    <b>{row['category']}</b><br>
                    📍 {row['location']}
                </td>
                <td><span class="tag {status_class}">{row['status']}</span></td>
                <td>{row['original_message']}</td>
            </tr>
        """
    
    html += """
                </tbody>
            </table>
        </div>
    </body>
    </html>
    """
    return html

# 🔌 2. API ENDPOINT (For External Apps)
@app.get("/api/grievances")
def get_grievances_json():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM grievances ORDER BY id DESC").fetchall()
    conn.close()
    return {"data": [dict(row) for row in rows]}

# 📩 3. WHATSAPP WEBHOOK (The Processor)
@app.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request):
    form_data = await request.form()
    sender = form_data.get("From")
    message_body = form_data.get("Body", "").strip()
    message_sid = form_data.get("MessageSid")

    if not message_body: return {"status": "ignored"}

    print(f"📩 Incoming from {sender}: {message_body}")
    send_typing_indicator(message_sid)

    # 1. Ask AI (Llama 70B)
    ai_result = ask_groq_agent(message_body)
    print(f"🧠 AI: {json.dumps(ai_result)}")

    # 2. Extract Data
    keys = {k.lower(): v for k, v in ai_result.items()}
    status = keys.get("status", "PROCESSING").upper()
    political_response = keys.get("political_response", "Namaste. Message received.")
    grievance_data = keys.get("grievance_data", {}) or {}

    category = grievance_data.get("category", "General")
    # Smart Location Fallback
    location = grievance_data.get("location_english") or grievance_data.get("location_native") or "Unknown"

    # 3. 💾 SAVE TO DB (FORCE SAVE - NO CONDITIONS)
    # We save EVERY message so you can see it in the dashboard, even if AI fails.
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        current_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        c.execute("""INSERT INTO grievances 
                     (date, sender, category, location, status, ai_response, original_message) 
                     VALUES (?, ?, ?, ?, ?, ?, ?)""",
                  (current_date, sender, category, location, status, political_response, message_body))
        
        conn.commit()
        conn.close()
        print(f"✅ SAVED TO DB: {status} - {location}")
    except Exception as e:
        print(f"❌ DB SAVE FAILED: {e}")

    # 4. Reply to User
    send_whatsapp_message(sender, political_response)

    return {"status": "processed"}
