from db import SessionLocal, User, Tenant

db = SessionLocal()

# 1. Find the Tenant
tenant = db.query(Tenant).filter(Tenant.name == "Hon. Jagdish Shettar").first()

if not tenant:
    print("❌ Error: Tenant 'Hon. Jagdish Shettar' not found. Run seed.py first.")
else:
    # 2. Delete existing 'shettar' user if he exists
    old_user = db.query(User).filter(User.username == "shettar").first()
    if old_user:
        db.delete(old_user)
        db.commit()
        print("🗑️  Deleted old 'shettar' user.")

    # 3. Create Fresh User
    new_user = User(
        tenant_id=tenant.id,
        username="shettar",
        password_hash="belgaum123",  # <--- GUARANTEED PASSWORD
        role="mp"
    )
    
    db.add(new_user)
    db.commit()
    
    print("------------------------------------------------")
    print("✅ USER RESET SUCCESSFUL")
    print(f"🏢 Organization: {tenant.name} (ID: {tenant.id})")
    print("👤 Username: shettar")
    print("🔑 Password: belgaum123")
    print("------------------------------------------------")

db.close()