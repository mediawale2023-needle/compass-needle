"""
jobs/dmf_nabard_sync.py — Sync District Mineral Foundation (DMF) and NABARD District Credit Plan data.

Data sources:
  1. State DMF Portals (Maharashtra)
     - Maharashtra DMF Trust portal: https://mahaDMF.maharashtra.gov.in/
     - National DMF dashboard (MoMSP): https://dmftrust.mospi.gov.in/
     - data.gov.in DMF corpus data: resource ID varies by state

  2. NABARD District Credit Plans
     - NABARD State Focus Paper (Maharashtra): https://www.nabard.org/auth/writereaddata/CareerNotices/
     - NABARD DCP PDFs: https://www.nabard.org/content.aspx?id=591
     - data.gov.in NABARD credit data: resource ID 4b9d1f22-8c3e-4a0b-b7f1-2e6c9d0a3f84

Updates:
  - data/dmf_district_data.json   (corpus, inflow, unspent, utilisation)
  - data/nabard_credit_plans.json (potential credit, actual disbursed, credit gap)

Schedule: Quarterly (1st of April, July, October, January at 03:00 IST)

Usage:
    python -m jobs.dmf_nabard_sync [--district Chandrapur] [--source dmf|nabard|all] [--dry-run]

Environment variables:
    DATA_GOV_IN_API_KEY    — Required for data.gov.in API access
    NABARD_DCP_CSV_PATH    — Local path to NABARD DCP CSV (if pre-downloaded)
    DMF_PORTAL_STATE_CODE  — State code for DMF portal (Maharashtra = MH)
"""
import sys
import os
import json
import re
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger("needle.jobs.dmf_nabard_sync")

DMF_DATA_PATH = "data/dmf_district_data.json"
NABARD_DATA_PATH = "data/nabard_credit_plans.json"
DATA_GOV_BASE = "https://api.data.gov.in/resource"
DMF_TRUST_API = "https://dmftrust.mospi.gov.in/dmf-api/district"  # MoMSP National DMF Dashboard

# data.gov.in resource IDs
DMF_RESOURCE_ID = "9b7c2e84-1f6a-4b9d-8c3e-a12f7d8e9b01"   # DMF district corpus
NABARD_RESOURCE_ID = "4b9d1f22-8c3e-4a0b-b7f1-2e6c9d0a3f84"  # NABARD DCP data

MAHARASHTRA_MINING_DISTRICTS = [
    "Chandrapur", "Gadchiroli", "Nagpur", "Wardha",
    "Yavatmal", "Amravati", "Bhandara", "Gondia"
]


def _api_key() -> str | None:
    return os.getenv("DATA_GOV_IN_API_KEY")


def _to_float(s) -> float | None:
    if s is None:
        return None
    try:
        return round(float(re.sub(r"[^\d.]", "", str(s))), 2)
    except (ValueError, TypeError):
        return None


def fetch_dmf_from_datagov(state: str = "Maharashtra") -> list[dict]:
    """Fetch DMF corpus data from data.gov.in."""
    key = _api_key()
    if not key:
        logger.warning("DATA_GOV_IN_API_KEY not set")
        return []

    try:
        import requests
        params = {
            "api-key": key,
            "format": "json",
            "limit": 100,
            "filters[state]": state,
        }
        r = requests.get(f"{DATA_GOV_BASE}/{DMF_RESOURCE_ID}", params=params, timeout=30)
        r.raise_for_status()
        return r.json().get("records", [])
    except Exception as e:
        logger.error(f"DMF data.gov.in fetch failed: {e}")
        return []


def fetch_dmf_from_trust_portal(district: str) -> dict | None:
    """
    Fetch DMF data from MoMSP National DMF Dashboard.

    Portal: https://dmftrust.mospi.gov.in/
    This endpoint provides district-level DMF corpus, expenditure and project counts.
    """
    try:
        import requests
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
            "Referer": "https://dmftrust.mospi.gov.in/",
        }
        params = {
            "state": "Maharashtra",
            "district": district,
        }
        r = requests.get(DMF_TRUST_API, params=params, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()

        if isinstance(data, list) and data:
            rec = data[0]
        elif isinstance(data, dict):
            rec = data
        else:
            return None

        return {
            "dmf_corpus_cr": _to_float(rec.get("total_corpus") or rec.get("corpus_amount")),
            "annual_inflow_cr": _to_float(rec.get("annual_receipt") or rec.get("fy_receipt")),
            "spent_till_date_cr": _to_float(rec.get("total_expenditure") or rec.get("spent_amount")),
            "active_projects": int(rec.get("project_count", 0) or 0),
        }
    except Exception as e:
        logger.debug(f"DMF Trust portal fetch failed for {district}: {e}")
        return None


def sync_dmf(district_filter: str | None = None, dry_run: bool = False) -> dict:
    """Update DMF corpus and utilisation data."""
    if not os.path.exists(DMF_DATA_PATH):
        logger.error(f"DMF data file not found: {DMF_DATA_PATH}")
        return {"error": "file_missing"}

    with open(DMF_DATA_PATH) as f:
        db = json.load(f)

    district_map = {d["district"].lower(): i for i, d in enumerate(db["districts"])}
    updated = 0

    # Try national DMF dashboard for each district
    for district_name in MAHARASHTRA_MINING_DISTRICTS:
        if district_filter and district_filter.lower() not in district_name.lower():
            continue

        idx = district_map.get(district_name.lower())
        if idx is None:
            logger.debug(f"District {district_name} not in DMF database")
            continue

        live = fetch_dmf_from_trust_portal(district_name)

        if not live:
            logger.debug(f"No live DMF data for {district_name} — using seeded data")
            continue

        if not dry_run:
            record = db["districts"][idx]
            if live.get("dmf_corpus_cr") is not None:
                record["dmf_corpus_cr"] = live["dmf_corpus_cr"]
            if live.get("annual_inflow_cr") is not None:
                record["annual_inflow_cr"] = live["annual_inflow_cr"]
            if live.get("spent_till_date_cr") is not None:
                record["spent_till_date_cr"] = live["spent_till_date_cr"]
            if live.get("active_projects"):
                record["active_projects"] = live["active_projects"]

            # Recompute derived fields
            corpus = record["dmf_corpus_cr"]
            spent = record["spent_till_date_cr"]
            if corpus and spent:
                record["unspent_balance_cr"] = round(corpus - spent, 2)
                record["utilisation_pct"] = round((spent / corpus) * 100, 1)

        updated += 1
        logger.info(f"  DMF updated: {district_name} corpus={live.get('dmf_corpus_cr')} Cr")

    # Also try data.gov.in batch fetch
    datagov_records = fetch_dmf_from_datagov()
    for rec in datagov_records:
        district_name = (rec.get("district_name") or "").strip()
        idx = district_map.get(district_name.lower())
        if idx is None:
            continue
        if district_filter and district_filter.lower() not in district_name.lower():
            continue

        if not dry_run:
            record = db["districts"][idx]
            corpus = _to_float(rec.get("total_corpus_cr") or rec.get("dmf_corpus"))
            spent = _to_float(rec.get("total_spent_cr") or rec.get("expenditure"))
            if corpus:
                record["dmf_corpus_cr"] = corpus
            if spent:
                record["spent_till_date_cr"] = spent
            if corpus and spent:
                record["unspent_balance_cr"] = round(corpus - spent, 2)
                record["utilisation_pct"] = round((spent / corpus) * 100, 1)
        updated += 1

    if not dry_run and updated:
        db["metadata"]["last_updated"] = datetime.utcnow().strftime("%Y-%m-%d")
        # Recompute state summary
        total_corpus = sum(d.get("dmf_corpus_cr", 0) for d in db["districts"])
        total_unspent = sum(d.get("unspent_balance_cr", 0) for d in db["districts"])
        avg_util = round(
            sum(d.get("utilisation_pct", 0) for d in db["districts"]) / len(db["districts"]), 1
        )
        db["state_summary"]["total_dmf_corpus_cr"] = total_corpus
        db["state_summary"]["total_unspent_cr"] = total_unspent
        db["state_summary"]["average_utilisation_pct"] = avg_util

        with open(DMF_DATA_PATH, "w") as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved {DMF_DATA_PATH}")

    return {"updated": updated}


def sync_nabard(district_filter: str | None = None, dry_run: bool = False) -> dict:
    """
    Update NABARD District Credit Plan data.

    Sources:
    1. data.gov.in NABARD credit data
    2. NABARD DCP CSV (if pre-downloaded via NABARD_DCP_CSV_PATH)
    """
    if not os.path.exists(NABARD_DATA_PATH):
        logger.error(f"NABARD data file not found: {NABARD_DATA_PATH}")
        return {"error": "file_missing"}

    with open(NABARD_DATA_PATH) as f:
        db = json.load(f)

    district_map = {d["district"].lower(): i for i, d in enumerate(db["districts"])}

    # Try local CSV first
    csv_path = os.getenv("NABARD_DCP_CSV_PATH", "data/nabard_dcp_maharashtra.csv")
    updated_csv = _sync_nabard_from_csv(csv_path, db, district_map, district_filter, dry_run)

    # Try data.gov.in API
    key = _api_key()
    updated_api = 0
    if key:
        try:
            import requests
            params = {
                "api-key": key,
                "format": "json",
                "limit": 100,
                "filters[state]": "Maharashtra",
            }
            r = requests.get(f"{DATA_GOV_BASE}/{NABARD_RESOURCE_ID}", params=params, timeout=30)
            r.raise_for_status()
            records = r.json().get("records", [])

            for rec in records:
                district_name = (rec.get("district_name") or "").strip()
                idx = district_map.get(district_name.lower())
                if idx is None:
                    continue
                if district_filter and district_filter.lower() not in district_name.lower():
                    continue

                if not dry_run:
                    entry = db["districts"][idx]
                    potential = _to_float(rec.get("potential_credit_cr"))
                    actual = _to_float(rec.get("actual_credit_cr"))
                    if potential:
                        entry["potential_credit_cr"] = potential
                    if actual:
                        entry["actual_credit_disbursed_cr"] = actual
                    if potential and actual:
                        entry["credit_gap_cr"] = round(potential - actual, 2)
                        entry["credit_deposit_ratio"] = round((actual / potential) * 100, 1)
                updated_api += 1
        except Exception as e:
            logger.error(f"NABARD data.gov.in fetch failed: {e}")

    total_updated = updated_csv + updated_api
    if not dry_run and total_updated:
        db["metadata"]["last_updated"] = datetime.utcnow().strftime("%Y-%m-%d")
        with open(NABARD_DATA_PATH, "w") as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved {NABARD_DATA_PATH}")

    return {"updated": total_updated, "csv_updates": updated_csv, "api_updates": updated_api}


def _sync_nabard_from_csv(csv_path, db, district_map, district_filter, dry_run) -> int:
    if not os.path.exists(csv_path):
        logger.info(f"NABARD DCP CSV not found at {csv_path}")
        logger.info("  Download from: https://www.nabard.org/content.aspx?id=591")
        return 0

    try:
        import csv
        with open(csv_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except Exception as e:
        logger.error(f"NABARD CSV read error: {e}")
        return 0

    updated = 0
    for row in rows:
        district_name = (row.get("District") or row.get("district_name") or "").strip()
        idx = district_map.get(district_name.lower())
        if idx is None:
            continue
        if district_filter and district_filter.lower() not in district_name.lower():
            continue

        if not dry_run:
            entry = db["districts"][idx]
            for csv_col, json_field in [
                ("Potential_Credit_Cr", "potential_credit_cr"),
                ("Actual_Disbursed_Cr", "actual_credit_disbursed_cr"),
                ("Credit_Gap_Cr", "credit_gap_cr"),
                ("CD_Ratio", "credit_deposit_ratio"),
                ("KCC_Coverage_Pct", "kcc_coverage_pct"),
                ("SHG_Linkage_Cr", "shg_bank_linkage_cr"),
            ]:
                if csv_col in row and row[csv_col]:
                    val = _to_float(row[csv_col])
                    if val is not None:
                        entry[json_field] = val
        updated += 1
        logger.info(f"  NABARD CSV updated: {district_name}")

    return updated


def run(district_filter: str | None = None, source: str = "all", dry_run: bool = False) -> dict:
    """
    Main sync function.

    source: "dmf", "nabard", or "all" (default)
    """
    logger.info(f"Starting DMF/NABARD sync (source={source})…")

    results = {}

    if source in ("all", "dmf"):
        results["dmf"] = sync_dmf(district_filter=district_filter, dry_run=dry_run)

    if source in ("all", "nabard"):
        results["nabard"] = sync_nabard(district_filter=district_filter, dry_run=dry_run)

    total = sum(v.get("updated", 0) for v in results.values())
    logger.info(f"DMF/NABARD sync complete — {total} records updated")
    return {**results, "total_updated": total}


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    dist = None
    src = "all"
    if "--district" in sys.argv:
        idx = sys.argv.index("--district")
        if idx + 1 < len(sys.argv):
            dist = sys.argv[idx + 1]
    if "--source" in sys.argv:
        idx = sys.argv.index("--source")
        if idx + 1 < len(sys.argv):
            src = sys.argv[idx + 1]
    run(district_filter=dist, source=src, dry_run=dry)
