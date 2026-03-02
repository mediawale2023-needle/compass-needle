"""
One-time migration: read tenant_overrides.json and insert into tenant_overrides DB table.
Run: python scripts/migrate_overrides_to_db.py
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sansadx_backend.db import init_db, save_overrides_to_db

JSON_PATHS = ["tenant_overrides.json", "/app/tenant_overrides.json"]


def main():
    init_db()
    data = None
    for path in JSON_PATHS:
        if os.path.exists(path):
            with open(path, "r") as f:
                data = json.load(f)
            print(f"Loaded overrides from {path}")
            break

    if not data:
        print("No tenant_overrides.json found — nothing to migrate.")
        return

    save_overrides_to_db(data)

    # Count what was migrated
    phone_count = sum(1 for k in data if k != "geo_overrides")
    geo_count = sum(
        len(mappings) for mappings in data.get("geo_overrides", {}).values()
    )
    print(f"Migrated {phone_count} phone mappings and {geo_count} geo overrides to DB.")


if __name__ == "__main__":
    main()
