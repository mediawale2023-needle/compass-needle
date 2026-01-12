import os
import sys
sys.path.append(os.getcwd())
from sansadx_backend.db import Base, engine, Tenant, User
from sqlalchemy.orm import sessionmaker

def create_super_admin():
    print("---------------------------------------")
    print("   👑 CREATING SUPER ADMIN (SANKET)")
    print("---------------------------------------")

    # Wipe and Recreate
    print("🧹 Refreshing Database...")
    try:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Warning: {e}")

    # Connect
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    # Create Tenant
    print("🏢 Creating Tenant...")
    system_tenant = Tenant(
        name="Needle HQ",
        constituency="System",
        whatsapp_number="system_admin_hq",
        subscription_plan="SuperAdmin"
    )
    db.add(system_tenant)
    db.commit()

    # Create User
    print("👤 Creating Admin User...")
    admin_user = User(
        tenant_id=system_tenant.id,
        username="snktj1@gmail.com",
        password_hash="ss@123",
        role="admin"
    )
    db.add(admin_user)
    db.commit()

    print("\n✅ SUCCESS! Login with: snktj1@gmail.com / ss@123")
    print("---------------------------------------")

if __name__ == "__main__":
    create_super_admin()
