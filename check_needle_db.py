import sqlite3
import os

def check_needle():
    db_file = "needle.db"
    print(f"---------------------------------------")
    print(f"   🗄️ CHECKING {db_file}")
    print(f"---------------------------------------")
    
    if not os.path.exists(db_file):
        print(f"❌ {db_file} does not exist in this folder.")
        return

    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # Check 'cases' table
        try:
            count = cursor.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
            print(f"✅ Found 'cases' table: {count} records.")
        except:
            print("❌ No 'cases' table found.")

        # Check 'grievances' table (Alternative name)
        try:
            g_count = cursor.execute("SELECT COUNT(*) FROM grievances").fetchone()[0]
            print(f"✅ Found 'grievances' table: {g_count} records.")
        except:
            print("❌ No 'grievances' table found.")
            
        conn.close()
    except Exception as e:
        print(f"❌ Error reading DB: {e}")

if __name__ == "__main__":
    check_needle()
