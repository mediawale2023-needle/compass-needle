import os
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load real DB URL properly using the venv's dotenv
load_dotenv()

from sansadx_backend.db import SessionLocal, Tenant, User, Case

MOCK_CATEGORIES = ["Water", "Electricity", "Roads", "Sanitation", "Health", "Education", "Police", "Pensions"]
MOCK_LOCATIONS = ["Camp", "Deccan", "Shivajinagar", "Kothrud", "Wakad", "Hinjewadi"]
MOCK_STATUSES = ["new", "in_progress", "resolved", "escalated", "closed"]

MOCK_MESSAGES = [
    "There is a huge pothole taking up half the road near the main market. Several accidents have happened.",
    "Streetlights have not been working for the past two weeks in my lane. It's very unsafe at night.",
    "No drinking water supply since yesterday. We have been buying tankers.",
    "The local government hospital does not have stock of essential medicines for diabetes.",
    "Garbage truck has not visited our society for 4 days. It is stinking everywhere.",
    "Urgent: Pension has not been credited this month for elderly folks in this area.",
    "Traffic police are constantly harassing vendors near the square. Please intervene.",
    "Primary school roof is leaking heavily during the monsoon rains.",
    "Open manhole near the playground, a child almost fell inside yesterday.",
    "Repeated power cuts every afternoon for 3 hours, ruining work from home."
]

def generate_mock_cases():
    from sqlalchemy import text
    db = SessionLocal()
    try:
        result = db.execute(text("SELECT id, tenant_id, username FROM users WHERE username ILIKE '%sanket%' OR display_name ILIKE '%Sanket%' LIMIT 1")).fetchone()
        
        if not result:
            print("❌ User named 'Sanket' not found at all. Cannot proceed.")
            return
            
        user_id = result[0]
        tenant_id = result[1]
        username = result[2]
        
        # Auto-fix: if Sanket has no tenant (due to a previous crash), create one NOW!
        if not tenant_id:
            print(f"⚠️ User '{username}' has no tenant ID! Creating a PR Tenant automatically to fix this...")
            res = db.execute(text("""
                INSERT INTO tenants (name, constituency, subscription_plan, config, is_active, tenant_type) 
                VALUES ('Sanket PR', 'General', 'pro', '{"type": "PR"}', true, 'aspirant') 
                RETURNING id
            """))
            tenant_id = res.fetchone()[0]
            db.execute(text("UPDATE users SET tenant_id = :tid, role = 'pr' WHERE id = :uid"), {"tid": tenant_id, "uid": user_id})
            db.commit()
            print(f"✅ Fixed: Created Tenant ID {tenant_id} and linked it to '{username}'.")
            
        print(f"✅ Ready for user {username} (Tenant ID: {tenant_id}). Generating 15 cases...")

        now = datetime.utcnow()
        for i in range(15):
            days_ago = random.randint(0, 14)
            created = now - timedelta(days=days_ago)
            is_critical = random.random() < 0.2
            
            db.execute(text("""
                INSERT INTO cases (
                    tenant_id, user_phone, raw_message, category, status, 
                    location, assembly_constituency, is_critical, created_at, updated_at
                ) VALUES (
                    :tenant_id, :phone, :msg, :cat, :status, 
                    :loc, :assembly, :crit, :created, :updated
                )
            """), {
                "tenant_id": tenant_id,
                "phone": f"+91{random.randint(9000000000, 9999999999)}",
                "msg": random.choice(MOCK_MESSAGES),
                "cat": random.choice(MOCK_CATEGORIES),
                "status": random.choice(MOCK_STATUSES),
                "loc": random.choice(MOCK_LOCATIONS),
                "assembly": "General",
                "crit": is_critical,
                "created": created,
                "updated": created + timedelta(hours=random.randint(1, 48))
            })

        db.commit()
        print("✅ 15 MOCK CASES INSERTED SUCCESSFULLY!")
        
        total = db.execute(text("SELECT COUNT(*) FROM cases WHERE tenant_id = :tid"), {"tid": tenant_id}).scalar()
        print(f"📊 Total cases for this tenant: {total}")

    finally:
        db.close()

if __name__ == "__main__":
    generate_mock_cases()
