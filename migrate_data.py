import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# --- 1. SETUP CONNECTIONS ---
SOURCE_URL = "sqlite:///./sansadx.db"
engine_source = create_engine(SOURCE_URL)
SessionSource = sessionmaker(bind=engine_source)

DEST_URL = os.getenv("DATABASE_URL")
if not DEST_URL:
    print("❌ Error: DATABASE_URL is missing.")
    sys.exit(1)

if DEST_URL.startswith("postgres://"):
    DEST_URL = DEST_URL.replace("postgres://", "postgresql://", 1)

engine_dest = create_engine(DEST_URL)
SessionDest = sessionmaker(bind=engine_dest)

# --- 2. IMPORT MODELS ---
sys.path.append(os.getcwd())
from sansadx_backend.db import Tenant, User, Case

def migrate():
    print("---------------------------------------")
    print("   📦 MIGRATION: RESTORING JAGDISH SHETTAR")
    print("---------------------------------------")

    source_session = SessionSource()
    dest_session = SessionDest()

    local_tenants = source_session.query(Tenant).all()
    if not local_tenants:
        print("⚠️ No data found in sansadx.db!")
        return

    for old_tenant in local_tenants:
        print(f"\nProcessing Backup: {old_tenant.name} ({old_tenant.whatsapp_number})")

        if "System" in old_tenant.name or "Admin" in old_tenant.name:
            continue

        # --- CHECK COLLISION ---
        existing_cloud_tenant = dest_session.query(Tenant).filter(
            Tenant.whatsapp_number == old_tenant.whatsapp_number
        ).first()

        new_id = None

        if existing_cloud_tenant:
            print(f"   ⚠️ Number held by: {existing_cloud_tenant.name}")
            print(f"   🔄 OVERWRITING: Changing Name to '{old_tenant.name}'...")
            
            # 🟢 FORCE UPDATE THE TENANT DETAILS TO MATCH BACKUP
            existing_cloud_tenant.name = old_tenant.name
            existing_cloud_tenant.constituency = old_tenant.constituency
            existing_cloud_tenant.subscription_plan = old_tenant.subscription_plan
            existing_cloud_tenant.config = old_tenant.config
            
            dest_session.commit()
            new_id = existing_cloud_tenant.id
            print(f"   ✅ Tenant Updated to: {old_tenant.name}")
        else:
            # Create New Tenant
            new_tenant = Tenant(
                name=old_tenant.name,
                constituency=old_tenant.constituency,
                whatsapp_number=old_tenant.whatsapp_number,
                subscription_plan=old_tenant.subscription_plan,
                config=old_tenant.config,
                is_active=old_tenant.is_active,
                created_at=old_tenant.created_at
            )
            dest_session.add(new_tenant)
            dest_session.commit()
            dest_session.refresh(new_tenant)
            new_id = new_tenant.id
            print(f"   ✅ Created New Tenant: {old_tenant.name}")

        # --- MIGRATE USERS ---
        local_users = source_session.query(User).filter(User.tenant_id == old_tenant.id).all()
        for old_user in local_users:
            exists = dest_session.query(User).filter(User.username == old_user.username).first()
            if not exists:
                new_user = User(
                    tenant_id=new_id,
                    username=old_user.username,
                    password_hash=old_user.password_hash,
                    role=old_user.role
                )
                dest_session.add(new_user)
                print(f"   👤 Restored User: {old_user.username}")
            else:
                print(f"   ⚠️ User {old_user.username} exists. Skipped.")
        
        dest_session.commit()

        # --- MIGRATE CASES ---
        local_cases = source_session.query(Case).filter(Case.tenant_id == old_tenant.id).all()
        count = 0
        for old_case in local_cases:
            new_case = Case(
                tenant_id=new_id,
                user_phone=old_case.user_phone,
                raw_message=old_case.raw_message,
                category=old_case.category,
                status=old_case.status,
                location=old_case.location,
                ward=old_case.ward,
                is_critical=old_case.is_critical,
                response_to_citizen=old_case.response_to_citizen,
                notes_for_staff=old_case.notes_for_staff,
                created_at=old_case.created_at
            )
            dest_session.add(new_case)
            count += 1
        
        dest_session.commit()
        print(f"   📂 Restored {count} Cases.")

    print("\n---------------------------------------")
    print("✅ JAGDISH SHETTAR RESTORED SUCCESSFULLY.")
    print("---------------------------------------")

if __name__ == "__main__":
    migrate()