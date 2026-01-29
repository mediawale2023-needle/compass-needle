import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# --- 1. LOAD ENV (From Backend Folder) ---
current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(current_dir, 'sansadx_backend', '.env')
load_dotenv(dotenv_path=env_path)

# --- 2. CONNECT TO DATABASE ---
db_url = os.getenv("DATABASE_URL")
if not db_url:
    print("❌ Error: No DATABASE_URL found. Check your .env file.")
    sys.exit(1)

# Fix URL for SQLAlchemy
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

def fix_schema():
    engine = create_engine(db_url)
    print("🔌 Connecting to Railway Database...")

    try:
        with engine.connect() as conn:
            # Add the Column
            print("🛠️  Adding 'constituency' column...")
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS constituency TEXT DEFAULT 'India';"))
            conn.commit()
            
            print("✅ SUCCESS: Column 'constituency' added successfully!")
            print("👉 You can now go to the Settings page and update your profile.")
            
    except Exception as e:
        print(f"❌ Migration Failed: {e}")

if __name__ == "__main__":
    fix_schema()