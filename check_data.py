import os
import sys
from sqlalchemy import create_engine, text

# Connect to Cloud
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)

def check_status():
    print("\n---------------------------------------")
    print("   🕵️‍♂️ DATABASE INVESTIGATION REPORT")
    print("---------------------------------------")
    
    with engine.connect() as conn:
        # 1. LIST ALL TENANTS (MPs)
        print("\n1. 🏢 TENANTS (MPs):")
        t_rows = conn.execute(text("SELECT id, name, whatsapp_number FROM tenants")).fetchall()
        for r in t_rows:
            print(f"   [ID: {r.id}] Name: {r.name} | WhatsApp: {r.whatsapp_number}")

        # 2. LIST ALL USERS
        print("\n2. 👤 USERS:")
        u_rows = conn.execute(text("SELECT id, username, tenant_id FROM users")).fetchall()
        for r in u_rows:
            print(f"   [ID: {r.id}] User: {r.username} --> Belongs to Tenant ID: {r.tenant_id}")

        # 3. COUNT CASES PER TENANT
        print("\n3. 📂 CASE COUNTS:")
        c_rows = conn.execute(text("SELECT tenant_id, COUNT(*) as count FROM cases GROUP BY tenant_id")).fetchall()
        if not c_rows:
            print("   ⚠️ NO CASES FOUND IN DATABASE!")
        for r in c_rows:
            print(f"   Tenant ID {r.tenant_id} has {r.count} Cases.")

    print("---------------------------------------\n")

if __name__ == "__main__":
    check_status()
