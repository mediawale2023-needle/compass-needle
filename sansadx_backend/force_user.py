import sys
from db import SessionLocal, User, Tenant

def run_fix():
    print("🚀 STARTING DATABASE FIX...")
    db = SessionLocal()

    # 1. FIX TENANT
    tenant = db.query(Tenant).filter(Tenant.id == 4).first()
    if not tenant:
        print("⚠️ Tenant missing. Creating...")
        tenant = Tenant(
            id=4, 
            name="Jagdish Shettar", 
            constituency="Belgaum", 
            whatsapp_number="+919999999999",
            config={"type": "LOK_SABHA"}
        )
        db.add(tenant)
        db.commit()
    else:
        print("✅ Tenant exists.")

    # 2. FIX USER
    user = db.query(User).filter(User.username == "shettar").first()
    if user:
        print(f"⚠️ User found. Updating password...")
        user.password_hash = "123"  # FORCE SIMPLE PASSWORD
        db.commit()
    else:
        print("⚠️ User missing. Creating...")
        user = User(
            username="shettar", 
            password_hash="123", 
            role="mp", 
            tenant_id=4
        )
        db.add(user)
        db.commit()

    print("\n" + "="*40)
    print("✅ SUCCESS! LOGIN DETAILS:")
    print("👤 Username: shettar")
    print("🔑 Password: 123")
    print("="*40)
    db.close()

if __name__ == "__main__":
    run_fix()