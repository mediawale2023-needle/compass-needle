from db import SessionLocal, Case

db = SessionLocal()

# Delete ALL rows in the 'cases' table
num_deleted = db.query(Case).delete()
db.commit()

print(f"🧹 Cleaned up! Deleted {num_deleted} old cases.")
print("✨ Dashboard is now empty.")

db.close()