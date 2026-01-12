import sys
import os
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, text
from sqlalchemy.orm import sessionmaker, declarative_base
from passlib.context import CryptContext

# --- CONFIGURATION ---
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ Error: DATABASE_URL is missing.")
    sys.exit(1)

Base = declarative_base()

# --- DEFINITIONS ---
class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    party = Column(String)
    constituency = Column(String)
    subscription_status = Column(String, default="active")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    full_name = Column(String)
    role = Column(String)
    tenant_id = Column(Integer, ForeignKey("tenants.id"))

# --- CONNECT ---
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def reset_and_create():
    print("\n------------------------------------------------")
    print("   🔧 NEEDLE: DATABASE REPAIR & ONBOARDING   ")
    print("------------------------------------------------")
    
    # 1. DROP OLD TABLES (The Fix)
    print("🗑️  Dropping old/broken tables...")
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS users CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS tenants CASCADE;"))
        conn.commit()
    print("✅ Old tables deleted.")

    # 2. CREATE NEW TABLES
    print("🏗️  Creating fresh tables...")
    Base.metadata.create_all(bind=engine)
    print("✅ New Schema applied (email column added).")

    # 3. ONBOARDING WIZARD
    db = SessionLocal()
    
    mp_name = input("\nEnter MP Name (e.g., Piyush Goyal): ").strip()
    if not mp_name: return
    party_name = input("Enter Party Name (e.g., BJP): ").strip()
    constituency = input("Enter Constituency: ").strip()
    email = input("Enter Admin Email: ").strip()
    password = input("Enter Admin Password: ").strip()

    # 4. Create Data
    print(f"\n⚙️  Creating Tenant for {mp_name}...")
    new_tenant = Tenant(name=mp_name, party=party_name, constituency=constituency, subscription_status="active")
    db.add(new_tenant)
    db.commit()
    db.refresh(new_tenant)

    print(f"👤 Creating Admin User ({email})...")
    hashed_password = pwd_context.hash(password)
    new_user = User(email=email, hashed_password=hashed_password, full_name=f"Office of {mp_name}", role="admin", tenant_id=new_tenant.id)
    db.add(new_user)
    db.commit()
    
    print("\n✅ SUCCESS! DATABASE FIXED & MP ADDED.")
    print("------------------------------------------------")

if __name__ == "__main__":
    reset_and_create()
