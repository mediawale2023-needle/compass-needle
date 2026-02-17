import os
import json
import random
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION ---
# Ensure this matches the logic in your app
DB_URL = os.getenv("DATABASE_URL", "sqlite:///sansadx.db")
if DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)

print(f"🔌 Connecting to: {DB_URL}")
engine = create_engine(DB_URL)

# --- MOCK DATA GENERATOR ---
LOCATIONS = ["Attiwad", "Mutnal", "Sambre", "Tilakwadi", "Kakati", "Vadgaon"]
CATEGORIES = ["Roads", "Water", "Electricity", "Health", "Education", "Police"]
STATUSES = ["new", "progress", "closed", "escalated"]
INTENTS = ["complaint", "emergency", "request", "greeting"]

# Realistic Messages
TEMPLATES = [
    ("Roads", "complaint", "The main road in {loc} has huge potholes. Dangerous for bikes."),
    ("Water", "complaint", "No water supply in {loc} for last 3 days. Please help."),
    ("Electricity", "complaint", "Transformer blew up in {loc} colony. No power since last night."),
    ("Health", "emergency", "Urgent! Ambulance needed in {loc} near primary school."),
    ("Education", "request", "Can we get a new computer lab for the {loc} government school?"),
    ("Police", "complaint", "Too much illegal parking causing jams in {loc} market."),
    ("Roads", "progress", "Work started on {loc} highway but stopped halfway."),
    ("Water", "closed", "Thank you, water tanker arrived in {loc} today."),
    ("Electricity", "new", "Streetlights not working in {loc} sector 4.")
]

def generate_mock_cases(n=25):
    with engine.begin() as conn:
        # Optional: Clear old data to start fresh
        # conn.execute(text("DELETE FROM cases WHERE tenant_id = 1")) 
        
        print(f"🚀 Injecting {n} records...")
        
        for _ in range(n):
            # Pick random attributes
            cat, intent, msg_template = random.choice(TEMPLATES)
            loc = random.choice(LOCATIONS)
            status = random.choice(STATUSES)
            
            # Create Message
            raw_msg = msg_template.format(loc=loc)
            
            # Random Time (last 7 days)
            days_ago = random.randint(0, 7)
            created_at = datetime.now() - timedelta(days=days_ago, hours=random.randint(0, 23))
            
            # JSON Metadata (Critical for v2 features)
            meta = {
                "user_intent": intent,
                "location_resolved": loc,
                "sentiment": "negative" if intent == "complaint" else "neutral",
                "priority": "high" if intent == "emergency" else "normal"
            }
            
            # Insert SQL
            sql = text("""
                INSERT INTO cases 
                (tenant_id, user_phone, raw_message, category, status, created_at, case_metadata)
                VALUES 
                (:tid, :phone, :msg, :cat, :stat, :time, :meta)
            """)
            
            conn.execute(sql, {
                "tid": 1,
                "phone": f"+91{random.randint(7000000000, 9999999999)}",
                "msg": raw_msg,
                "cat": cat,
                "stat": status,
                "time": created_at,
                "meta": json.dumps(meta) # Must allow JSON string for SQLite/Postgres compatibility
            })
            
    print("✅ Success! Database seeded.")

if __name__ == "__main__":
    try:
        generate_mock_cases()
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Tip: Make sure your 'cases' table exists and has a 'case_metadata' column.")