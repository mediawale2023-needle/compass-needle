import sys
import os
from passlib.context import CryptContext

# --- 1. SETUP PATH TO FIND YOUR CODE ---
# We look for the 'sansadx_backend' folder relative to this script
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, 'sansadx_backend'))

try:
    # Attempt to import from your main app file
    from main import User, Tenant, SessionLocal
    from sqlalchemy.orm import Session
except ImportError as e:
    print("❌ CRITICAL ERROR: Could not find your database models.")
    print(f"Error details: {e}")
    print("Make sure this script is in the root folder (compass-needle), next to 'sansadx_backend'.")
    sys.exit(1)

# Password Hasher
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_mp():
    print("\n------------------------------------------------")
    print("   🏛️  NEEDLE: MP ONBOARDING WIZARD   ")
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
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        print(f"\n❌ Error: User with email {email} already exists!")
        return

    # 3. Create Tenant (The Organization)
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

    # 4. Create Admin User (The Person)
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
