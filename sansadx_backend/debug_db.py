from db import SessionLocal, Tenant, User, Case

def investigate():
    db = SessionLocal()
    print("\n🕵️‍♀️ --- DATABASE INVESTIGATION ---\n")

    # 1. Who are the MPs?
    print("🏢 TENANTS (Offices):")
    tenants = db.query(Tenant).all()
    for t in tenants:
        print(f"   [ID: {t.id}] {t.name} (Phone: {t.whatsapp_number})")

    # 2. Who are the Users?
    print("\n👤 USERS (Logins):")
    users = db.query(User).all()
    for u in users:
        print(f"   - {u.username} maps to Tenant ID: {u.tenant_id}")

    # 3. Where is the Data?
    print("\n📨 GRIEVANCES (Cases):")
    cases = db.query(Case).all()
    if not cases:
        print("   ❌ NO DATA FOUND IN DATABASE.")
    else:
        for c in cases:
            print(f"   - Case #{c.id}: '{c.raw_message[:30]}...' belongs to TENANT ID: {c.tenant_id}")

    db.close()

if __name__ == "__main__":
    investigate()