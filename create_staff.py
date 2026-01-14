import os
import sys
from sqlalchemy import create_engine, text

# --- CONFIGURATION ---
TENANT_ID = 2  # Jagdish Shettar's ID
# ---------------------

# Setup Database
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ Error: DATABASE_URL is missing.")
    sys.exit(1)

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)

def create_staff_user():
    print("\n---------------------------------------")
    print("   👤 ADD NEW STAFF MEMBER (Jagdish Shettar)")
    print("---------------------------------------")
    
    username = input("Enter new Username (e.g., pa_suresh): ").strip()
    if not username:
        print("❌ Username cannot be empty.")
        return

    password = input("Enter Password: ").strip()
    if not password:
        print("❌ Password cannot be empty.")
        return
    
    role = input("Enter Role (pa/staff/media) [default: pa]: ").strip() or "pa"

    try:
        with engine.connect() as conn:
            # Check if username exists
            exists = conn.execute(text("SELECT id FROM users WHERE username = :u"), {"u": username}).fetchone()
            if exists:
                print(f"❌ Error: User '{username}' already exists!")
                return

            # Insert new user linked to Tenant 2
            conn.execute(text("""
                INSERT INTO users (username, password_hash, role, tenant_id)
                VALUES (:u, :p, :r, :tid)
            """), {"u": username, "p": password, "r": role, "tid": TENANT_ID})
            
            conn.commit()
            print(f"\n✅ SUCCESS: User '{username}' created for Jagdish Shettar.")
            print(f"   They can log in immediately.")

    except Exception as e:
        print(f"❌ Database Error: {e}")

    print("---------------------------------------\n")

if __name__ == "__main__":
    create_staff_user()