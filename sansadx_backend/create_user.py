from db import SessionLocal, Tenant, User

db = SessionLocal()

# 1. Find the Tenant (Organization)
shettar_tenant = db.query(Tenant).filter(Tenant.name == "Hon. Jagdish Shettar").first()

if shettar_tenant:
    # 2. Check if user already exists
    existing_user = db.query(User).filter(User.username == "shettar").first()
    
    if not existing_user:
        # 3. Create the User linked to this Tenant
        new_user = User(
            tenant_id=shettar_tenant.id,
            username="shettar",
            password_hash="belgaum123",  # In real app, hash this!
            role="admin" # He is admin of his own account
        )
        db.add(new_user)
        db.commit()
        print(f"✅ User Created for {shettar_tenant.name}")
        print("👉 Username: shettar")
        print("👉 Password: belgaum123")
    else:
        print("⚡ User 'shettar' already exists.")
else:
    print("❌ Tenant 'Hon. Jagdish Shettar' not found. Run seed.py first.")

db.close()