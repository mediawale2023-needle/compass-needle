import sys
import os

# Ensure we import from the local folder
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db import SessionLocal, Tenant, User, init_db

def seed():
    print("🔄 Initializing 'needle.db' tables...")
    init_db()  # Creates tables in needle.db
    
    db = SessionLocal()

    # The Jurisdiction List (The Brain's Memory)
    real_jurisdiction_list = """
- Tilakwadi
- Shahapur
- Vadgaon
- Hindwadi
- Camp
- Khasa Bag
- Angol
- Udyambag
- Hanuman Nagar
- Attiwad
- Malmaruti
- Shivbasav Nagar
    """

    # Check/Create Tenant
    tenant = db.query(Tenant).filter(Tenant.id == 1).first()
    
    if not tenant:
        print("🌱 Creating Tenant...")
        tenant = Tenant(
            id=1,
            name="Jagdish Shettar",
            constituency="Belagavi",
            whatsapp_number="919999999999", 
            config={
                "type": "LOK_SABHA",
                "jurisdiction_guide": real_jurisdiction_list.strip()
            }
        )
        db.add(tenant)
    else:
        print("🛠  Fixing Existing Tenant Config...")
        new_config = tenant.config.copy() if tenant.config else {}
        new_config["jurisdiction_guide"] = real_jurisdiction_list.strip()
        tenant.config = new_config

    # Check/Create Admin User
    user = db.query(User).filter(User.username == "admin").first()
    if not user:
        print("👤 Creating Admin User...")
        user = User(
            username="admin",
            password_hash="password", 
            role="mp",
            tenant_id=1
        )
        db.add(user)

    db.commit()
    print("✅ SUCCESS: 'needle.db' is ready and populated!")
    db.close()

if __name__ == "__main__":
    seed()