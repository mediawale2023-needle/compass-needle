#!/usr/bin/env python3
"""
Password Migration Script
Migrates plaintext passwords to bcrypt hashes
Run this ONCE before deploying to production
"""

import os
import sys
import bcrypt
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

def migrate_passwords():
    """Migrate all plaintext passwords to bcrypt hashes."""
    
    # Get database URL
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ DATABASE_URL not set")
        return False
    
    # Fix PostgreSQL URL if needed
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    
    try:
        engine = create_engine(db_url)
        print("✅ Connected to database")
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        return False
    
    try:
        with engine.connect() as conn:
            # Get all users with passwords
            result = conn.execute(text("SELECT id, username, password_hash FROM users"))
            users = result.fetchall()
            
            if not users:
                print("✅ No users found")
                return True
            
            print(f"Found {len(users)} users to check")
            
            migrated = 0
            skipped = 0
            
            for user_id, username, password_hash in users:
                if not password_hash:
                    print(f"  ⚠️  {username}: No password hash")
                    skipped += 1
                    continue
                
                # Check if already hashed (bcrypt hashes start with $2a$ or $2b$)
                if password_hash.startswith("$2a$") or password_hash.startswith("$2b$"):
                    print(f"  ✅ {username}: Already hashed")
                    skipped += 1
                    continue
                
                # Hash the plaintext password
                try:
                    hashed = bcrypt.hashpw(password_hash.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                    
                    # Update database
                    with engine.begin() as tx:
                        tx.execute(
                            text("UPDATE users SET password_hash = :hash WHERE id = :id"),
                            {"hash": hashed, "id": user_id}
                        )
                    
                    print(f"  ✅ {username}: Migrated to bcrypt")
                    migrated += 1
                except Exception as e:
                    print(f"  ❌ {username}: Migration failed - {e}")
                    skipped += 1
            
            print(f"\n📊 Migration Summary:")
            print(f"   Migrated: {migrated}")
            print(f"   Skipped:  {skipped}")
            print(f"   Total:    {len(users)}")
            
            if migrated > 0:
                print("\n✅ Password migration completed successfully!")
                return True
            else:
                print("\n⚠️  No passwords were migrated")
                return True
                
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

if __name__ == "__main__":
    print("🔐 Password Migration Script")
    print("=" * 50)
    print("\n⚠️  WARNING: This script will modify your database!")
    print("Make sure you have a backup before proceeding.\n")
    
    response = input("Continue? (yes/no): ").strip().lower()
    if response != "yes":
        print("Cancelled.")
        sys.exit(0)
    
    success = migrate_passwords()
    sys.exit(0 if success else 1)
