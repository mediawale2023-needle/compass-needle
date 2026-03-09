import os
import sys

# Add backend to path so we can import if needed 
sys.path.append("/Users/sanketjadhav/Desktop/compass-needle/")

# Manually parse .env to get DATABASE_URL
env_file = "/Users/sanketjadhav/Desktop/compass-needle/.env"
db_url = ""
if os.path.exists(env_file):
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith("DATABASE_URL="):
                db_url = line.split("=", 1)[1].strip('"\'')

if not db_url:
    print("Could not find DATABASE_URL in .env")
    sys.exit(1)

if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

try:
    from sqlalchemy import create_engine, text
except ImportError:
    print("sqlalchemy not found")
    sys.exit(1)

engine = create_engine(db_url)

try:
    with engine.begin() as conn:
        users = conn.execute(text("SELECT username, tenant_id FROM users WHERE tenant_id IS NOT NULL")).fetchall()
        
        updated_history = 0
        updated_archives = 0
        
        for u in users:
            username = u[0]
            tid = u[1]
            
            # Update activity_history
            res = conn.execute(
                text("UPDATE activity_history SET tenant_id = :tid WHERE username = :u AND tenant_id != :tid"),
                {"tid": tid, "u": username}
            )
            updated_history += res.rowcount
            
        print(f"Successfully migrated {updated_history} activity_history records to correct tenant IDs.")
except Exception as e:
    print(f"Error executing DB migration: {e}")
