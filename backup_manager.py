import shutil
import os
import glob
from datetime import datetime

# CONFIG
SOURCE_DB = "sansadx_backend/needle.db"
BACKUP_DIR = "backups"
MAX_BACKUPS = 5

def create_backup():
    if not os.path.exists(SOURCE_DB):
        print(f"⚠️ Warning: Database not found at {SOURCE_DB}")
        return

    # 1. Create Backup Folder
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)

    # 2. Make Copy
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    dest = os.path.join(BACKUP_DIR, f"needle_backup_{timestamp}.db")
    shutil.copy2(SOURCE_DB, dest)
    print(f"🛡️ Database Backup Created: {dest}")

    # 3. Cleanup Old Backups
    files = glob.glob(os.path.join(BACKUP_DIR, "needle_backup_*.db"))
    files.sort(key=os.path.getmtime) # Sort by age
    
    while len(files) > MAX_BACKUPS:
        oldest = files.pop(0)
        os.remove(oldest)
        print(f"🧹 Removed old backup: {oldest}")

if __name__ == "__main__":
    create_backup()
