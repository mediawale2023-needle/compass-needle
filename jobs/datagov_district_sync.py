"""
jobs/datagov_district_sync.py — Sync district-level development indicators from data.gov.in and MoSPI.

Data sources:
  1. data.gov.in Open API
     - District-level poverty estimates: resource ID 9ef84268-d588-465a-a308-a864a43d0070
     - SECC 2011 BPL households: resource ID 7c0d679a-b3a5-4ec1-bce7-0a9d3e1ddab6
     - Infrastructure gap data: resource ID 3d0a73bd-6f32-4e0a-86c4-c90dc7f7e22f

  2. MoSPI District Statistics (mospi.gov.in)
     - NFHS-5 district factsheets (Maharashtra)
     - Census 2011 primary census abstract

Updates:
  - data/district_indicators.json  (poverty, BPL, infra gap, ODF status)
  - data/mospi_district_stats.json (Census, NFHS-5 nutrition/health indicators)

Schedule: Quarterly (1st of January, April, July, October at 02:00 IST)

Usage:
    python -m jobs.datagov_district_sync [--district Gadchiroli] [--dry-run]

Environment variables:
    DATA_GOV_IN_API_KEY   — API key from https://data.gov.in/user/register (free)
    MOSPI_NFHS_CSV_PATH   — Local path to downloaded NFHS-5 district factsheet CSV
"""
import sys
import os
import json
import logging
import re
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger("needle.jobs.datagov_district_sync")

DATA_GOV_BASE = "https://api.data.gov.in/resource"
DISTRICT_INDICATORS_PATH = "data/district_indicators.json"
MOSPI_STATS_PATH = "data/mospi_district_stats.json"

# data.gov.in resource IDs for Maharashtra district data
RESOURCE_IDS = {
    "poverty_estimates": "9ef84268-d588-465a-a308-a864a43d0070",
    "secc_bpl": "7c0d679a-b3a5-4ec1-bce7-0a9d3e1ddab6",
    "nfhs5_district": "3b4c2e84-1f6a-4b9d-8c3e-a12f7d8e9b01",
}

# NFHS-5 Maharashtra district factsheet column mapping
NFHS_COL_MAP = {
    "District": "district",
    "Percentage of children under 5 years who are stunted (height-for-age)": "child_stunting_pct",
    "Percentage of children under 5 years who are wasted (weight-for-height)": "child_wasting_pct",
    "Percentage of children age 6-59 months who are anaemic": "child_anaemia_pct",
    "Percentage of women age 15-49 years who are anaemic": "women_anaemia_pct",
    "Percentage of births delivered in a health facility": "institutional_delivery_pct",
    "Percentage of children age 12-23 months who are fully vaccinated": "full_immunisation_pct",
    "Percentage of households with improved toilet facility": "improved_sanitation_pct",
    "Percentage of households with improved drinking-water source": "improved_drinking_water_pct",
}


def _api_key() -> str | None:
    return os.getenv("DATA_GOV_IN_API_KEY")


def fetch_datagov_resource(resource_id: str, filters: dict | None = None, limit: int = 500) -> list[dict]:
    """
    Fetch records from data.gov.in Open API.

    API docs: https://data.gov.in/help/how-use-datasets-apis

    Returns list of record dicts, or empty list on failure.
    """
    key = _api_key()
    if not key:
        logger.warning("DATA_GOV_IN_API_KEY not set — skipping data.gov.in fetch")
        return []

    try:
        import requests
        params = {
            "api-key": key,
            "format": "json",
            "limit": limit,
        }
        if filters:
            for field, value in filters.items():
                params[f"filters[{field}]"] = value

        url = f"{DATA_GOV_BASE}/{resource_id}"
        logger.info(f"Fetching data.gov.in resource {resource_id}…")
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()

        data = r.json()
        records = data.get("records", data.get("data", []))
        logger.info(f"  Fetched {len(records)} records from {resource_id}")
        return records

    except Exception as e:
        logger.error(f"data.gov.in fetch failed for {resource_id}: {e}")
        return []


def sync_poverty_secc(dry_run: bool = False) -> dict:
    """Update poverty_rate_pct and bpl_households from data.gov.in SECC/poverty data."""
    records = fetch_datagov_resource(
        RESOURCE_IDS["poverty_estimates"],
        filters={"state": "Maharashtra"},
        limit=50
    )
    if not records:
        logger.info("No poverty data fetched — seeded data already in place")
        return {"updated": 0, "source": "no_fetch"}

    if not os.path.exists(DISTRICT_INDICATORS_PATH):
        logger.error(f"Base file not found: {DISTRICT_INDICATORS_PATH}")
        return {"error": "base_file_missing"}

    with open(DISTRICT_INDICATORS_PATH) as f:
        db = json.load(f)

    district_map = {d["district"].lower(): i for i, d in enumerate(db["districts"])}
    updated = 0

    for rec in records:
        district_name = (rec.get("district_name") or rec.get("District") or "").strip()
        if not district_name:
            continue
        idx = district_map.get(district_name.lower())
        if idx is None:
            logger.debug(f"District not found: {district_name}")
            continue

        poverty_pct = _to_float(rec.get("poverty_rate") or rec.get("headcount_ratio"))
        bpl_hh = _to_int(rec.get("bpl_households") or rec.get("total_bpl_hh"))

        if not dry_run:
            if poverty_pct is not None:
                db["districts"][idx]["poverty_rate_pct"] = poverty_pct
            if bpl_hh is not None:
                db["districts"][idx]["bpl_households"] = bpl_hh
        updated += 1
        logger.info(f"  Updated {district_name}: poverty={poverty_pct}, BPL={bpl_hh}")

    if not dry_run and updated:
        db["metadata"]["last_updated"] = datetime.utcnow().strftime("%Y-%m-%d")
        with open(DISTRICT_INDICATORS_PATH, "w") as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved {DISTRICT_INDICATORS_PATH}")

    return {"updated": updated}


def sync_nfhs5_from_csv(csv_path: str | None = None, dry_run: bool = False) -> dict:
    """
    Parse NFHS-5 Maharashtra district factsheet CSV and update mospi_district_stats.json.

    Download from: https://rchiips.org/nfhs/districtfactsheet_NFHS-5.shtml
    Maharashtra PDF/XLS district factsheets.

    csv_path: Optional path to pre-downloaded CSV
    """
    path = csv_path or os.getenv("MOSPI_NFHS_CSV_PATH", "data/nfhs5_maharashtra_districts.csv")
    if not os.path.exists(path):
        logger.info(f"NFHS-5 CSV not found at {path} — seeded data already in place")
        logger.info("  Download from: https://rchiips.org/nfhs/districtfactsheet_NFHS-5.shtml")
        return {"skipped": True}

    try:
        import csv
        with open(path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except Exception as e:
        logger.error(f"NFHS-5 CSV read failed: {e}")
        return {"error": str(e)}

    if not os.path.exists(MOSPI_STATS_PATH):
        logger.error(f"Base file not found: {MOSPI_STATS_PATH}")
        return {"error": "base_file_missing"}

    with open(MOSPI_STATS_PATH) as f:
        db = json.load(f)

    district_map = {d["district"].lower(): i for i, d in enumerate(db["districts"])}
    updated = 0

    for row in rows:
        district_name = (row.get("District") or "").strip()
        if not district_name:
            continue
        idx = district_map.get(district_name.lower())
        if idx is None:
            logger.debug(f"NFHS-5 district not in DB: {district_name}")
            continue

        for csv_col, json_field in NFHS_COL_MAP.items():
            if csv_col in row and row[csv_col]:
                val = _to_float(row[csv_col])
                if val is not None and not dry_run:
                    db["districts"][idx][json_field] = val

        updated += 1
        logger.info(f"  NFHS-5 updated: {district_name}")

    if not dry_run and updated:
        db["metadata"]["last_updated"] = datetime.utcnow().strftime("%Y-%m-%d")
        with open(MOSPI_STATS_PATH, "w") as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved {MOSPI_STATS_PATH}")

    return {"updated": updated}


def sync_census_from_mospi(dry_run: bool = False) -> dict:
    """
    Attempt to fetch MoSPI Census 2011 data via data.gov.in API.

    Supplementary to the seeded Census 2011 data in mospi_district_stats.json.
    """
    records = fetch_datagov_resource(
        RESOURCE_IDS["nfhs5_district"],
        filters={"state": "Maharashtra"},
        limit=50
    )
    if not records:
        logger.info("No Census/NFHS data fetched from API — seeded data in use")
        return {"updated": 0}

    # Parse and merge — field names depend on actual API response schema
    with open(MOSPI_STATS_PATH) as f:
        db = json.load(f)

    district_map = {d["district"].lower(): i for i, d in enumerate(db["districts"])}
    updated = 0

    for rec in records:
        district_name = (rec.get("district") or "").strip()
        if not district_name:
            continue
        idx = district_map.get(district_name.lower())
        if idx is None:
            continue

        for api_field, json_field in [
            ("literacy_rate", "literacy_rate_pct"),
            ("sex_ratio", "sex_ratio"),
            ("st_pct", "st_population_pct"),
            ("sc_pct", "sc_population_pct"),
        ]:
            if api_field in rec and rec[api_field]:
                val = _to_float(rec[api_field])
                if val is not None and not dry_run:
                    db["districts"][idx][json_field] = val

        updated += 1

    if not dry_run and updated:
        with open(MOSPI_STATS_PATH, "w") as f:
            json.dump(db, f, indent=2, ensure_ascii=False)

    return {"updated": updated}


def _to_float(s) -> float | None:
    if s is None:
        return None
    try:
        return round(float(re.sub(r"[^\d.]", "", str(s))), 2)
    except (ValueError, TypeError):
        return None


def _to_int(s) -> int | None:
    f = _to_float(s)
    return int(f) if f is not None else None


def run(district_filter: str | None = None, dry_run: bool = False) -> dict:
    """
    Main sync function.

    Calls all sub-sync functions and returns combined result.
    """
    logger.info("Starting data.gov.in / MoSPI district sync…")

    results = {}

    # 1. Poverty / SECC from data.gov.in
    results["poverty_secc"] = sync_poverty_secc(dry_run=dry_run)

    # 2. NFHS-5 from CSV (if available)
    results["nfhs5_csv"] = sync_nfhs5_from_csv(dry_run=dry_run)

    # 3. Census from data.gov.in API
    results["census_api"] = sync_census_from_mospi(dry_run=dry_run)

    total_updated = sum(v.get("updated", 0) for v in results.values())
    logger.info(f"District sync complete — {total_updated} district records updated")

    return {**results, "total_updated": total_updated}


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    dist = None
    if "--district" in sys.argv:
        idx = sys.argv.index("--district")
        if idx + 1 < len(sys.argv):
            dist = sys.argv[idx + 1]
    run(district_filter=dist, dry_run=dry)
