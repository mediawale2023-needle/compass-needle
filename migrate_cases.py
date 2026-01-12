import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# --- CONFIGURATION ---
TARGET_TENANT_ID = 2  # We are forcing data into Jagdish Shettar (ID 2)

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
# We define Case locally to avoid import errors if file paths vary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey

Base = declarative_base()
class Case(Base):
    __tablename__ = "cases"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer) # We just need the ID here
    user_phone = Column(String)
    raw_message = Column(Text)
    category = Column(String)
    status = Column(String)
    location = Column(String)
    ward = Column(String)
    is_critical = Column(Boolean)
    response_to_citizen = Column(Text)
    notes_for_staff = Column(Text)
    created_at = Column(DateTime)
    # We ignore relationships for raw migration

def migrate_cases():
    print("---------------------------------------")
    print(f"   📦 MIGRATING CASES TO TENANT ID: {TARGET_TENANT_ID}")
    print("---------------------------------------")

    source_session = SessionSource()
    dest_session = SessionDest()

    # 1. READ ALL CASES FROM LOCAL BACKUP
    try:
        local_cases = source_session.query(Case).all()
    except Exception as e:
        print(f"❌ Error reading local DB: {e}")
        return

    if not local_cases:
        print("⚠️ No cases found in sansadx.db to migrate!")
        return

    print(f"🔍 Found {len(local_cases)} Cases in local backup.")

    # 2. INSERT INTO CLOUD
    count = 0
    for old_case in local_cases:
        new_case = Case(
            tenant_id=TARGET_TENANT_ID,  # FORCE LINK TO JAGDISH SHETTAR
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
    print(f"✅ SUCCESS! {count} Cases migrated to Cloud.")
    print("---------------------------------------")

if __name__ == "__main__":
    migrate_cases()