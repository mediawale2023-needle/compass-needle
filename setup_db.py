import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 1. Point to the correct folder
sys.path.append(os.path.join(os.getcwd(), "sansadx_backend"))

# 2. Import the DB models
# This will fail if the path is wrong, so we force the path above
try:
    from sansadx_backend.db import Base, engine, init_db
except ImportError:
    # Fallback if running from inside the folder
    sys.path.append(os.getcwd())
    from sansadx_backend.db import Base, engine, init_db

print("🔄 Initializing Database Tables...")

# 3. Force Create Tables
# We manually set the DB path to ensure it matches the dashboard
db_path = "sqlite:///sansadx_backend/needle.db"
print(f"📂 Target Database: {db_path}")

# Override engine to point to the exact same file the dashboard uses
custom_engine = create_engine(db_path)

# Create tables
Base.metadata.create_all(bind=custom_engine)

print("✅ Tables Created Successfully: cases, tenants, users")
print("🚀 You can now run 'npm run dev' again.")