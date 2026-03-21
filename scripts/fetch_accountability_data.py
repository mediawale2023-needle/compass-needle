#!/usr/bin/env python3
"""
Fetch and refresh accountability_data.json from Open Budgets India (OBI).

Open Budgets India CKAN API: https://openbudgetsindia.org/api/3/action/
Key datasets:
  - Union Budget Expenditure by Demand/Head (annual BE/RE/Actual)
  - Resource_id varies per fiscal year — check https://openbudgetsindia.org/dataset

Usage:
    python scripts/fetch_accountability_data.py
    python scripts/fetch_accountability_data.py --fy 2023-24
    python scripts/fetch_accountability_data.py --dry-run

The script:
1. Fetches ministry-level BE/RE/Actual from OBI CKAN API
2. Merges with existing accountability_data.json (preserves manual entries)
3. Updates trend arrays
4. Writes updated accountability_data.json

NOTE: OBI only has ANNUAL data (post year-end actuals, typically 6-9 months lag).
For within-year quarterly actuals, PFMS integration is required (no public API yet).
"""

import argparse
import json
import os
import sys
from datetime import datetime

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests")
    sys.exit(1)

OBI_BASE = "https://openbudgetsindia.org/api/3/action"
# Known resource IDs for Union Budget expenditure datasets on OBI
# Run fetch_obi_datasets() to discover current resource IDs
OBI_DATASET_SLUGS = {
    "2023-24": "union-budget-2023-24-expenditure",
    "2022-23": "union-budget-2022-23-expenditure",
    "2021-22": "union-budget-2021-22-expenditure",
}

ACCOUNTABILITY_FILE = os.path.join(os.path.dirname(__file__), "..", "accountability_data.json")


def fetch_obi_datasets(search_term="union budget expenditure"):
    """List available datasets matching search_term on Open Budgets India."""
    url = f"{OBI_BASE}/package_search"
    try:
        resp = requests.get(url, params={"q": search_term, "rows": 20}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        datasets = data.get("result", {}).get("results", [])
        print(f"\nFound {len(datasets)} datasets for '{search_term}':")
        for d in datasets:
            print(f"  - {d.get('name')}: {d.get('title')}")
            for r in d.get("resources", []):
                print(f"      resource_id={r.get('id')} format={r.get('format')}")
        return datasets
    except Exception as e:
        print(f"WARNING: Could not reach Open Budgets India: {e}")
        return []


def fetch_ministry_expenditure(resource_id, fy_label, limit=500):
    """
    Fetch ministry-level expenditure from an OBI CKAN datastore resource.
    Returns list of dicts with ministry/BE/RE/Actual fields.
    """
    url = f"{OBI_BASE}/datastore_search"
    try:
        resp = requests.get(url, params={"resource_id": resource_id, "limit": limit}, timeout=30)
        resp.raise_for_status()
        records = resp.json().get("result", {}).get("records", [])
        print(f"  Fetched {len(records)} records for FY {fy_label} from OBI")
        return records
    except Exception as e:
        print(f"  WARNING: Could not fetch resource {resource_id}: {e}")
        return []


def normalize_ministry_name(raw):
    """Normalize raw ministry name to match accountability_data.json keys."""
    if not raw:
        return ""
    name = raw.upper().strip()
    for prefix in ["MINISTRY OF ", "MINISTRY FOR ", "DEPARTMENT OF "]:
        name = name.replace(prefix, "")
    name = name.replace("&", "AND").replace("  ", " ").strip()
    return name


def parse_crore_value(val):
    """Parse a budget value to float in Crore. OBI values may be in Lakh or Crore."""
    if val is None:
        return None
    try:
        v = float(str(val).replace(",", ""))
        return round(v, 2)
    except (ValueError, TypeError):
        return None


def update_trend(existing_trend, fy, be_cr, re_cr, actual_cr):
    """Add or update a trend entry for a given fiscal year."""
    util_pct = None
    if actual_cr is not None and re_cr and re_cr > 0:
        util_pct = round((actual_cr / re_cr) * 100, 1)

    new_entry = {
        "fy": fy,
        "be_cr": be_cr,
        "re_cr": re_cr,
        "actual_cr": actual_cr,
        "util_pct": util_pct,
    }
    # Replace existing or append
    for i, entry in enumerate(existing_trend):
        if entry.get("fy") == fy:
            existing_trend[i] = new_entry
            return existing_trend
    existing_trend.append(new_entry)
    existing_trend.sort(key=lambda x: x.get("fy", ""))
    # Keep only last 3 years
    return existing_trend[-3:]


def compute_lapse_risk(trend):
    """Flag lapse risk if last 2 available actuals are both below 80% of RE."""
    actuals = [t for t in trend if t.get("util_pct") is not None]
    if len(actuals) < 2:
        return False
    last_two = actuals[-2:]
    return all(t["util_pct"] < 80 for t in last_two)


def main():
    parser = argparse.ArgumentParser(description="Refresh accountability_data.json from Open Budgets India")
    parser.add_argument("--fy", default=None, help="Fiscal year to fetch (e.g. 2023-24). Default: all available")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and print but do not write to file")
    parser.add_argument("--list-datasets", action="store_true", help="List available OBI datasets and exit")
    args = parser.parse_args()

    if args.list_datasets:
        fetch_obi_datasets()
        return

    # Load existing accountability data
    acc_path = os.path.abspath(ACCOUNTABILITY_FILE)
    if not os.path.exists(acc_path):
        print(f"ERROR: {acc_path} not found. Run from repo root.")
        sys.exit(1)

    with open(acc_path, "r", encoding="utf-8") as f:
        acc_data = json.load(f)

    print(f"Loaded {len(acc_data['ministries'])} ministries from {acc_path}")

    # Build a lookup for quick ministry matching
    ministry_map = {normalize_ministry_name(m["ministry"]): m for m in acc_data["ministries"]}

    fiscal_years = [args.fy] if args.fy else list(OBI_DATASET_SLUGS.keys())
    updated_count = 0

    for fy in fiscal_years:
        slug = OBI_DATASET_SLUGS.get(fy)
        if not slug:
            print(f"  No known resource ID for FY {fy}. Use --list-datasets to find it.")
            continue

        print(f"\nFetching OBI data for FY {fy} (slug: {slug})...")
        # First discover the resource_id from the dataset
        try:
            pkg_resp = requests.get(f"{OBI_BASE}/package_show", params={"id": slug}, timeout=15)
            pkg_resp.raise_for_status()
            pkg = pkg_resp.json().get("result", {})
            resources = pkg.get("resources", [])
            csv_resources = [r for r in resources if r.get("format", "").upper() in ("CSV", "JSON")]
            if not csv_resources:
                print(f"  No CSV/JSON resources found for {slug}")
                continue
            resource_id = csv_resources[0]["id"]
        except Exception as e:
            print(f"  Could not fetch package {slug}: {e}")
            continue

        records = fetch_ministry_expenditure(resource_id, fy)
        if not records:
            continue

        # OBI field names vary — try to detect BE/RE/Actual columns
        if records:
            sample = records[0]
            print(f"  Sample record fields: {list(sample.keys())[:10]}")

        for record in records:
            # Try common field name patterns
            raw_ministry = (
                record.get("ministry") or record.get("Ministry") or
                record.get("demand_description") or record.get("Demand Description") or ""
            )
            norm = normalize_ministry_name(raw_ministry)

            # Match to existing ministry
            matched_key = None
            for key in ministry_map:
                if key in norm or norm in key:
                    matched_key = key
                    break

            if not matched_key:
                continue

            m_entry = ministry_map[matched_key]

            # Extract BE/RE/Actual — field names vary by OBI dataset
            be_cr = parse_crore_value(
                record.get("be_cr") or record.get("BE") or record.get("budget_estimate")
            )
            re_cr = parse_crore_value(
                record.get("re_cr") or record.get("RE") or record.get("revised_estimate")
            )
            actual_cr = parse_crore_value(
                record.get("actual") or record.get("Actuals") or record.get("actual_expenditure")
            )

            if not any([be_cr, re_cr, actual_cr]):
                continue

            m_entry["trend"] = update_trend(m_entry.get("trend", []), fy, be_cr, re_cr, actual_cr)

            # Recompute lapse risk from trend
            if not m_entry.get("lapse_risk_reason"):
                m_entry["lapse_risk"] = compute_lapse_risk(m_entry["trend"])

            updated_count += 1

    # Update metadata timestamp
    acc_data["metadata"]["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    acc_data["metadata"]["last_refresh_source"] = "Open Budgets India CKAN API"

    print(f"\nUpdated {updated_count} ministry records.")

    if args.dry_run:
        print("DRY RUN — not writing to file.")
        print(json.dumps(acc_data, indent=2)[:2000] + "\n...")
    else:
        with open(acc_path, "w", encoding="utf-8") as f:
            json.dump(acc_data, f, indent=2, ensure_ascii=False)
        print(f"Written to {acc_path}")


if __name__ == "__main__":
    main()
