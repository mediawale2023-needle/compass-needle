import sys
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# 1. SETUP PATHS
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "sansadx_backend")
DB_PATH = os.path.join(BACKEND_DIR, "needle.db")

print(f"🔍 Reading Database at: {DB_PATH}")

if not os.path.exists(DB_PATH):
    print("❌ ERROR: Database file not found!")
    sys.exit(1)

# 2. CONNECT
engine = create_engine(f"sqlite:///{DB_PATH}")
Session = sessionmaker(bind=engine)
session = Session()

# 3. LIST ALL USERS
print("\n--- 👥 EXISTING USERS ---")
try:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT id, username, role FROM users"))
        users = result.fetchall()
        
        found_jagdish = False
        if not users:
            print("⚠️  NO USERS FOUND. Database is empty.")
        else:
            for u in users:
                print(f"👤 User: {u[1]} | Role: {u[2]} | ID: {u[0]}")
                if "jagdish" in u[1].lower() or "shettar" in u[1].lower():
                    found_jagdish = True
                    target_user = u[1]

    # 4. FIX JAGDISH SHETTAR
    print("\n--- 🛠️ REPAIRING LOGIN ---")
    if found_jagdish:
        # Reset Password
        sql = text("UPDATE users SET password_hash = '12345' WHERE username = :u")
        with engine.connect() as conn:
            conn.execute(sql, {"u": target_user})
            conn.commit()
        print(f"✅ SUCCESS: Password for '{target_user}' has been reset to: 12345")
    else:
        # Create User if missing
        print("⚠️  User 'Jagdish Shettar' not found. Creating him now...")
        # Get Tenant ID 1
        sql_create = text("INSERT INTO users (username, password_hash, role, tenant_id) VALUES ('Jagdish Shettar', '12345', 'mp', 1)")
        try:
            with engine.connect() as conn:
                conn.execute(sql_create)
                conn.commit()
            print("✅ SUCCESS: Created User 'Jagdish Shettar' with password: 12345")
        except Exception as e:
            print(f"❌ Failed to create user. Ensure a Tenant (ID=1) exists first. Error: {e}")

except Exception as e:
    print(f"❌ Database Error: {e}")

print("\n🚀 TRY LOGGING IN NOW!")
