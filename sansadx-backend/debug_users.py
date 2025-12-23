from db import SessionLocal, User

db = SessionLocal()
users = db.query(User).all()

print(f"--- 🔍 FOUND {len(users)} USERS IN DB ---")
for u in users:
    print(f"👤 User: {u.username} | 🔑 Pass: {u.password_hash} | 🏢 Tenant ID: {u.tenant_id}")

db.close()