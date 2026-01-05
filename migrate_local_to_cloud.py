import sqlite3
import pandas as pd
from sqlalchemy import create_engine, text

# 1. SETUP CONNECTIONS
# Local Database (Your Laptop)
LOCAL_DB = "needle.db"

# Cloud Database (Railway)
CLOUD_URL = "postgresql://postgres:qavOCQWrfITqxVGUFHCVkSdosvHhmQHe@shortline.proxy.rlwy.net:57534/railway"

def migrate():
    print("🚀 Starting Migration: Laptop -> Cloud")
    
    # --- STEP A: READ FROM LAPTOP ---
    print(f"📂 Reading data from local {LOCAL_DB}...")
    try:
        # Connect to SQLite
        local_conn = sqlite3.connect(LOCAL_DB)
        
        # Read Users
        try:
            users_df = pd.read_sql("SELECT * FROM users", local_conn)
            print(f"   Found {len(users_df)} Users.")
        except:
            users_df = pd.DataFrame()
            print("   No 'users' table found locally.")

        # Read Cases (Grievances)
        try:
            cases_df = pd.read_sql("SELECT * FROM cases", local_conn)
            print(f"   Found {len(cases_df)} Grievances.")
        except:
            # Fallback if table was named 'grievances' locally
            try:
                cases_df = pd.read_sql("SELECT * FROM grievances", local_conn)
                print(f"   Found {len(cases_df)} Grievances (from 'grievances' table).")
            except:
                cases_df = pd.DataFrame()
                print("   No 'cases' or 'grievances' table found locally.")
                
        local_conn.close()
        
    except Exception as e:
        print(f"❌ Error reading local DB: {e}")
        return

    # --- STEP B: UPLOAD TO CLOUD ---
    if users_df.empty and cases_df.empty:
        print("⚠️ No data found to migrate.")
        return

    print("☁️  Connecting to Railway Cloud...")
    try:
        engine = create_engine(CLOUD_URL)
        
        # 1. Upload Users
        if not users_df.empty:
            print("   Uploading Users...")
            # We use 'append' to add to existing data, or replace if you want a clean slate
            # 'if_exists="replace"' drops the table and recreates it (Safest to match local)
            users_df.to_sql('users', engine, if_exists='replace', index=False)
            
        # 2. Upload Cases
        if not cases_df.empty:
            print("   Uploading Cases...")
            cases_df.to_sql('cases', engine, if_exists='replace', index=False)
            
        print("✅ SUCCESS! Your local data is now on the Live Website.")
        
    except Exception as e:
        print(f"❌ Error uploading to Cloud: {e}")

if __name__ == "__main__":
    migrate()