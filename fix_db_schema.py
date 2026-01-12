import os
import sys
from sqlalchemy import create_engine, text

# --- SETUP CONNECTION ---
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ Error: DATABASE_URL is missing.")
    sys.exit(1)

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)

def add_missing_column():
    print("---------------------------------------")
    print("   🔧 FIXING DATABASE SCHEMA")
    print("---------------------------------------")
    
    with engine.connect() as conn:
        try:
            # 1. Add 'case_metadata' column (Stores Red Zone info)
            print("   ↳ Adding 'case_metadata' column...")
            conn.execute(text("ALTER TABLE cases ADD COLUMN IF NOT EXISTS case_metadata TEXT;"))
            
            # 2. Add 'notes_for_staff' (Just in case it's missing too)
            print("   ↳ Adding 'notes_for_staff' column...")
            conn.execute(text("ALTER TABLE cases ADD COLUMN IF NOT EXISTS notes_for_staff TEXT;"))

            conn.commit()
            print("   ✅ SUCCESS: Columns added.")
            
        except Exception as e:
            print(f"   ❌ Error updating schema: {e}")

    print("---------------------------------------")

if __name__ == "__main__":
    add_missing_column()