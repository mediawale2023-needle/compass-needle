import os
from sqlalchemy import create_engine, text

# --- CONNECTION ---
# This connects to your Railway Database
DATABASE_URL = "postgresql://postgres:qavOCQWrfITqxVGUFHCVkSdosvHhmQHe@shortline.proxy.rlwy.net:57534/railway"

engine = create_engine(DATABASE_URL)
print("🚀 Connecting to Railway Database...")

with engine.connect() as conn:
    # 1. Create User Table & Admin Account
    print("👤 Creating Admin User...")
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            tenant_id INTEGER DEFAULT 1
        );
        -- Insert Admin if not exists
        INSERT INTO users (username, password, role, tenant_id) 
        VALUES ('admin', 'password', 'admin', 1)
        ON CONFLICT (username) DO NOTHING;
    """))

    # 2. Create Cases Table & Grievance Data (SansadX)
    print("📝 Restoring SansadX Messages...")
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS cases (
            id SERIAL PRIMARY KEY,
            tenant_id INTEGER DEFAULT 1,
            user_phone TEXT,
            category TEXT,
            raw_message TEXT,
            status TEXT DEFAULT 'new',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            case_metadata TEXT
        );
        -- Insert Sample Cases
        INSERT INTO cases (tenant_id, user_phone, category, raw_message, status)
        VALUES 
        (1, '9980012345', 'Water', 'Severe water shortage in Gandhinagar area of Hubli.', 'new'),
        (1, '9980054321', 'Roads', 'Potholes near the main bus stand are causing accidents.', 'progress'),
        (1, '9980099887', 'Electricity', 'Transformer blown in Vidyanagar 2nd cross.', 'new');
    """))
    
    conn.commit()

print("✅ DONE! You can now log in as 'admin' with password 'password'.")