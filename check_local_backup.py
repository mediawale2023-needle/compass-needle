import sqlite3

def check_local_backup():
    print("---------------------------------------")
    print("   🗄️ CHECKING LOCAL BACKUP (SANSADX.DB)")
    print("---------------------------------------")
    
    try:
        conn = sqlite3.connect("sansadx.db")
        cursor = conn.cursor()
        
        # Count Total Cases
        try:
            count = cursor.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
            print(f"✅ Total Cases Found locally: {count}")
        except:
            print("❌ 'cases' table not found in sansadx.db")
            return
        
        # See which Tenant owns them
        rows = cursor.execute("SELECT tenant_id, COUNT(*) FROM cases GROUP BY tenant_id").fetchall()
        for r in rows:
            print(f"   -> Tenant ID {r[0]} owns {r[1]} cases.")
            
        conn.close()
    except Exception as e:
        print(f"❌ Error reading file: {e}")

if __name__ == "__main__":
    check_local_backup()
