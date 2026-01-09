import pandas as pd
import json
from sqlalchemy import create_engine, text
from sansadx_backend.db import Base
import os

# --- CONFIGURATION ---

# 1. Source: Your Local Docker DB (Port 5435)
LOCAL_DB_URL = "postgresql://sansad_admin:secure_production_password@localhost:5435/sansadx_db"

# 2. Destination: Your Railway Public URL
RAILWAY_DB_URL = "postgresql://postgres:qavOCQWrfITqxVGUFHCVkSdosvHhmQHe@shortline.proxy.rlwy.net:57534/railway"

def fix_json_columns(df, columns):
    """Convert dictionary objects to JSON strings for Postgres"""
    for col in columns:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: json.dumps(x) if isinstance(x, (dict, list)) else x)
    return df

def deploy():
    print("🚀 Starting Deployment: Local Docker -> Railway Cloud...")

    # Connect to both
    print("1. Connecting to Local DB...")
    local_engine = create_engine(LOCAL_DB_URL)
    
    print("2. Connecting to Railway DB...")
    railway_engine = create_engine(RAILWAY_DB_URL)

    # --- RESET RAILWAY SCHEMA ---
    print("3. ⚠️  Wiping Railway Database to match Local Schema...")
    Base.metadata.drop_all(bind=railway_engine)
    Base.metadata.create_all(bind=railway_engine)
    print("   ✅ Railway tables re-created.")

    # --- MOVE DATA ---
    tables_to_move = ["tenants", "users", "cases"]

    with railway_engine.connect() as railway_conn:
        for table in tables_to_move:
            print(f"4. Moving table: '{table}'...")
            
            try:
                # Read from Local Docker
                df = pd.read_sql_table(table, local_engine)
                
                if df.empty:
                    print(f"   ⚠️  Table {table} is empty. Skipping.")
                    continue

                # Fix JSON Data Types
                if table == "tenants":
                    df = fix_json_columns(df, ["config"])
                elif table == "cases":
                    df = fix_json_columns(df, ["case_metadata"])
                
                # Write to Railway
                df.to_sql(table, railway_engine, if_exists='append', index=False)
                print(f"   ✅ Uploaded {len(df)} rows to Railway.")

                # Reset ID Counter on Railway
                print(f"   🔧 Resetting ID counter for {table}...")
                railway_conn.execute(text(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), coalesce(max(id)+1, 1), false) FROM {table};"))
                railway_conn.commit()

            except Exception as e:
                print(f"   ❌ FATAL ERROR moving {table}: {e}")
                return

    print("\n🎉 SUCCESS! Your Local Data is now Live on Railway.")

if __name__ == "__main__":
    deploy()