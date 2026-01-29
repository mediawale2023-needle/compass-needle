import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load Environment
current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(current_dir, 'sansadx_backend', '.env')
load_dotenv(dotenv_path=env_path)

# Connect to DB
db_url = os.getenv("DATABASE_URL")
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

def check_user_details():
    if not db_url:
        print("❌ Error: No DATABASE_URL found.")
        return

    engine = create_engine(db_url)
    username = input("Enter the MP Username to check: ").strip()

    print(f"\n🔍 Checking database for user: '{username}'...")
    
    with engine.connect() as conn:
        # 1. Check USERS Table (This is what MP Dashboard reads)
        result = conn.execute(text("SELECT id, username, role, constituency FROM users WHERE username = :u"), {"u": username})
        user_row = result.fetchone()
        
        # 2. Check TENANTS Table (This is what Admin Panel often updates)
        tenant_row = None
        if user_row:
            # Get tenant_id from user table to find matching tenant
            # (We query user again to get tenant_id if needed, or join)
            t_res = conn.execute(text("SELECT t.id, t.name, t.constituency FROM tenants t JOIN users u ON u.tenant_id = t.id WHERE u.username = :u"), {"u": username})
            tenant_row = t_res.fetchone()

    print("\n--- 📊 DIAGNOSTIC RESULTS ---")
    
    if user_row:
        print(f"✅ User Found in DB (ID: {user_row[0]})")
        print(f"   • Username:     {user_row[1]}")
        print(f"   • Role:         {user_row[2]}")
        print(f"   • Constituency: '{user_row[3]}'")  # <--- CRITICAL CHECK
        
        if user_row[3] in [None, "", "India"]:
            print("\n❌ ISSUE DETECTED: User constituency is missing or default.")
            print("   The MP Dashboard will show 'India' because of this.")
        else:
            print("\n✅ DATA IS CORRECT. If Dashboard shows 'India', it is a caching issue.")
            
    else:
        print("❌ User not found in database.")

    if tenant_row:
        print(f"\n🏢 Linked Tenant (Organization)")
        print(f"   • Name:         {tenant_row[1]}")
        print(f"   • Constituency: '{tenant_row[2]}'")
        
        if user_row and user_row[3] != tenant_row[2]:
             print("\n⚠️ MISMATCH: User table and Tenant table have different locations!")
             print("   MP Dashboard reads 'User Table'. Admin Panel might be updating 'Tenant Table'.")

if __name__ == "__main__":
    check_user_details()