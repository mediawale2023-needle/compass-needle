import sqlite3
import os

def fix_local_db():
    db_file = "sansadx.db"
    
    # Check if DB exists
    if not os.path.exists(db_file):
        print(f"❌ Error: '{db_file}' not found. Are you in the 'compass-needle' folder?")
        return

    print(f"🔌 Connecting to: {db_file}...")
    
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # 1. Add 'constituency' to 'users' table
        print("🛠️  Fixing 'users' table...")
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN constituency TEXT DEFAULT 'India'")
            print("   ✅ Success: Added 'constituency' column.")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("   ℹ️  Column 'constituency' already exists. (Good!)")
            else:
                print(f"   ❌ Error adding column: {e}")

        # 2. Add 'case_metadata' to 'cases' table (Prevent future errors)
        print("🛠️  Fixing 'cases' table...")
        try:
            cursor.execute("ALTER TABLE cases ADD COLUMN case_metadata JSON")
            print("   ✅ Success: Added 'case_metadata' column.")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("   ℹ️  Column 'case_metadata' already exists. (Good!)")
            else:
                print(f"   ❌ Error adding column: {e}")

        conn.commit()
        conn.close()
        print("\n✅ DATABASE REPAIR COMPLETE.")
        
    except Exception as e:
        print(f"❌ Critical Error: {e}")

if __name__ == "__main__":
    fix_local_db()