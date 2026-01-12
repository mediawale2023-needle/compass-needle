import sys
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base
from passlib.context import CryptContext

# --- CONFIGURATION ---
# We use the URL passed from the command line
import os
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ Error: DATABASE_URL is missing.")
    sys.exit(1)

# --- STANDALONE MODEL DEFINITIONS (To avoid importing main.py) ---
Base = declarative_base()

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

# --- SETUP CONNECTION ---
try:
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
except Exception as e:
    print(f"❌ Connection Failed: {e}")
    sys.exit(1)

def create_mp():
    print("\n------------------------------------------------")
    print("   ⚡ NEEDLE FAST ONBOARDING (STANDALONE)   ")
    print("------------------------------------------------")
    
    db = SessionLocal()

    # 1. Gather Input
    mp_name = input("Enter MP Name (e.g., Piyush Goyal): ").strip()
    if not mp_name: return
    
    party_name = input("Enter Party Name (e.g., BJP): ").strip()
    constituency = input("Enter Constituency (e.g., Mumbai North): ").strip()
    email = input("Enter Admin Email (e.g., admin@piyushgoyal.in): ").strip()
    password = input("Enter Admin Password: ").strip()

    # 2. Check if Email exists
    try:
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            print(f"\n❌ Error: User with email {email} already exists!")
            return
    except Exception as e:
        print(f"❌ Database Query Failed: {e}")
        print("Check if your IP is allowed or if the Database URL is correct.")
        return

    # 3. Create Tenant
    print(f"\n⚙️  Creating Tenant for {mp_name}...")
    new_tenant = Tenant(
        name=mp_name,
        party=party_name,
        constituency=constituency,
        subscription_status="active"
    )
    db.add(new_tenant)
    db.commit()
    db.refresh(new_tenant)

    # 4. Create User
    print(f"👤 Creating Admin User ({email})...")
    hashed_password = pwd_context.hash(password)
    
    new_user = User(
        email=email,
        hashed_password=hashed_password,
        full_name=f"Office of {mp_name}",
        role="admin",
        tenant_id=new_tenant.id
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    print("\n✅ SUCCESS! MP ONBOARDED.")
    print("------------------------------------------------")
    print(f"Tenant ID: {new_tenant.id}")
    print(f"User ID:   {new_user.id}")
    print(f"Login:     {email}")
    print("------------------------------------------------")

if __name__ == "__main__":
    create_mp()
