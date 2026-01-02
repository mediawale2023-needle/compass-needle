from db import SessionLocal, User, Tenant

db = SessionLocal()
print("--- TENANTS ---")
for t in db.query(Tenant).all():
    print(f"ID: {t.id} | Name: {t.name}")

print("\n--- USERS ---")
for u in db.query(User).all():
    print(f"User: {u.username} | Pass: {u.password_hash} | Linked to Tenant ID: {u.tenant_id}")

db.close()