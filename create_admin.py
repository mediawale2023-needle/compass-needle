import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 1. SETUP PATHS (Critical to find the right DB)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "sansadx_backend")
sys.path.append(BACKEND_DIR)

# 2. IMPORT FROM YOUR CODE
try:
    from db import User, Tenant, Base
except ImportError:
    print("❌ Error: Could not find 'db.py'. Make sure you run this from the project root.")
    sys.exit(1)

# 3. CONNECT TO DATABASE
DB_PATH = os.path.join(BACKEND_DIR, "needle.db")
engine = create_engine(f"sqlite:///{DB_PATH}")
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

print(f"🔌 Connecting to: {DB_PATH}")

# 4. CREATE TENANT (If missing)
tenant = db.query(Tenant).first()
if not tenant:
    print("⚠️ No Tenant found. Creating 'Default Constituency'...")
    tenant = Tenant(
        name="Needle HQ",
        constituency="Headquarters",
        whatsapp_number="14155238886", # Sandbox Number
        config={"type": "LOK_SABHA"}
    )
    db.add(tenant)
    db.commit()
    print("✅ Tenant Created.")

# 5. CREATE ADMIN USER
username = "admin"
password = "password"

user = db.query(User).filter(User.username == username).first()
if user:
    print(f"ℹ️ User '{username}' already exists. Updating password...")
    user.password_hash = password # Resetting password
    user.tenant_id = tenant.id
else:
    print(f"🆕 Creating new user '{username}'...")
    user = User(
        username=username,
        password_hash=password,
        role="admin",
        tenant_id=tenant.id
    )
    db.add(user)

db.commit()
print(f"🎉 SUCCESS! Login with -> Username: {username} | Password: {password}")
