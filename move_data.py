import pandas as pd
import json
from sqlalchemy import create_engine, text
from sansadx_backend.db import Base
import os

# --- CONFIGURATION ---
SQLITE_DB_PATH = os.path.join("sansadx_backend", "sql_app.db")
SQLITE_URL = f"sqlite:///{SQLITE_DB_PATH}"

# We use port 5435 as established
POSTGRES_URL = "postgresql://sansad_admin:secure_production_password@localhost:5435/sansadx_db"

def fix_json_columns(df, columns):
    """Convert dictionary objects to JSON strings for Postgres"""
    for col in columns:
        if col in df.columns:
            # Apply json.dumps only if the value is a dict, handle None/NaN safely
            df[col] = df[col].apply(lambda x: json.dumps(x) if isinstance(x, (dict, list)) else x)
    return df

def run_migration():
    print("🚀 Starting Robust Migration to Port 5435...")

    print(f"1. Connecting to SQLite at: {SQLITE_DB_PATH}")
    sqlite_engine = create_engine(SQLITE_URL)
    
    print("2. Connecting to PostgreSQL...")
    pg_engine = create_engine(POSTGRES_URL)

    # --- RESET SCHEMA (Crucial Step) ---
    print("3. Resetting Database Schema...")
    # This deletes old tables to ensure columns like 'response_to_citizen' are created correctly
    Base.metadata.drop_all(bind=pg_engine)
    Base.metadata.create_all(bind=pg_engine)
    print("   ✅ Fresh tables created.")

    # --- MOVE DATA ---
    tables_to_move = ["tenants", "users", "cases"]

    with pg_engine.connect() as pg_conn:
        for table in tables_to_move:
            print(f"4. Moving table: '{table}'...")
            
            try:
                # Read from SQLite
                df = pd.read_sql_table(table, sqlite_engine)
                
                if df.empty:
                    print(f"   ⚠️  Table {table} is empty. Skipping.")
                    continue

                # --- FIX DATA TYPES ---
                if table == "tenants":
                    df = fix_json_columns(df, ["config"])
                elif table == "cases":
                    df = fix_json_columns(df, ["case_metadata"])
                
                # Write to Postgres
                df.to_sql(table, pg_engine, if_exists='append', index=False)
                print(f"   ✅ Moved {len(df)} rows.")

                # Reset ID Counter
                print(f"   🔧 Resetting ID counter for {table}...")
                pg_conn.execute(text(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), coalesce(max(id)+1, 1), false) FROM {table};"))
                pg_conn.commit()

            except Exception as e:
                print(f"   ❌ FATAL ERROR moving {table}: {e}")
                # If tenants fail, we must stop, or users will fail too
                if table == "tenants":
                    print("   🛑 Stopping migration because Tenants failed (Parent table).")
                    return

    print("\n🎉 SUCCESS! Migration Complete.")

if __name__ == "__main__":
    if not os.path.exists(SQLITE_DB_PATH):
        print(f"❌ ERROR: Could not find {SQLITE_DB_PATH}")
    else:
        run_migration()