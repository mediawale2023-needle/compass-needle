"""
One-time migration: Create tenant_profiles table and seed Shettar's profile.

Usage:
    python migrate_tenant_profiles.py
"""
import json
import os
import sys
from dotenv import load_dotenv

load_dotenv()

from db import SessionLocal, TenantProfile, Tenant, init_db


def main():
    # 1. Create table
    print("Creating tenant_profiles table...")
    init_db()
    print("  Done.")

    # 2. Seed from tenant_profile.json
    json_path = "tenant_profile.json"
    if not os.path.exists(json_path):
        print(f"  {json_path} not found — skipping seed.")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        profile = json.load(f)

    constituency = profile.get("constituency", "")
    mp_name = profile.get("mp_name", "")

    if not mp_name:
        print("  No mp_name in tenant_profile.json — skipping seed.")
        return

    db = SessionLocal()
    try:
        # Find the tenant whose name or constituency matches
        tenant = (
            db.query(Tenant)
            .filter(
                (Tenant.constituency == constituency) | (Tenant.name == mp_name)
            )
            .first()
        )

        if not tenant:
            print(f"  No tenant found matching constituency='{constituency}' or name='{mp_name}'.")
            print("  Skipping seed. Create the MP via admin dashboard first.")
            return

        # Check if profile already exists
        existing = db.query(TenantProfile).filter(
            TenantProfile.tenant_id == tenant.id
        ).first()

        if existing:
            print(f"  Profile already exists for tenant {tenant.id} ({tenant.name}). Skipping.")
            return

        # Build profile_data from extra fields
        profile_data = {
            "key_facts": profile.get("key_facts", []),
            "languages": profile.get("languages", ["English", "Hindi"]),
            "vocabulary_guide": profile.get("vocabulary_guide", {}),
            "sovereignty_rules": profile.get("sovereignty_rules", ""),
            "alt_names": [],
        }

        # Auto-detect alt_names for common cases
        if constituency.lower() in ("belagavi", "belgaum"):
            profile_data["alt_names"] = ["Belagavi", "Belgaum"]

        new_profile = TenantProfile(
            tenant_id=tenant.id,
            mp_name=mp_name,
            constituency=constituency,
            state=profile.get("state", ""),
            house=profile.get("house", "Lok Sabha"),
            party=profile.get("party", "Independent"),
            profile_data=profile_data,
        )
        db.add(new_profile)
        db.commit()
        print(f"  Seeded profile for tenant {tenant.id}: {mp_name} ({constituency})")

    except Exception as e:
        db.rollback()
        print(f"  Error: {e}")
    finally:
        db.close()

    print("Migration complete.")


if __name__ == "__main__":
    main()
