import sqlite3
import pandas as pd

conn = sqlite3.connect("sansadx.db")
try:
    df = pd.read_sql_query("SELECT id, username, password_hash, role, constituency FROM users", conn)
    if df.empty:
        print("❌ No users found in the database.")
    else:
        print("\n📊 CURRENT USERS IN DB:")
        print(df.to_string(index=False))
except Exception as e:
    print(f"❌ Error: {e}")
finally:
    conn.close()