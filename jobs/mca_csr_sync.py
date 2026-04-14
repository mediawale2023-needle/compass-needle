"""
jobs/mca_csr_sync.py — Download and ingest the MCA annual CSR disclosure dataset.

MCA (Ministry of Corporate Affairs) publishes CSR filing data for all Schedule VII companies.

Data sources:
  1. MCA Company Data Portal:
     https://www.mca.gov.in/content/mca/global/en/data-and-reports/company-data.html
     File: "CSR Data" (CSV, updated annually)

  2. MCA21 eFiling portal (individual company lookup):
     https://efiling.mca.gov.in/eFiling/

  3. XBRL taxonomy filings (advanced, structured):
     https://www.mca.gov.in/content/mca/global/en/acts-rules/ebooks/xbrl.html

This job:
  1. Downloads the latest MCA CSR CSV (if URL provided via MCA_CSR_DOWNLOAD_URL env var)
  2. Parses and normalises all records
  3. Matches company names to existing csr_companies records
  4. Updates unspent_obligation_lakhs and spend fields
  5. Inserts new companies not yet in the DB

Schedule: Monthly (1st of each month at 00:00 AM)

Usage:
    python -m jobs.mca_csr_sync [--dry-run] [--csv /path/to/file.csv]
"""
import sys
import os
import re
import csv
import io
import logging
from datetime import datetime
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger("needle.jobs.mca_csr_sync")

# MCA dataset column headers (standard as of FY2023-24 release)
# Adjust if MCA changes their schema
MCA_COL_COMPANY = "COMPANY_NAME"
MCA_COL_CIN = "CIN"
MCA_COL_STATE = "STATE"
MCA_COL_SECTOR = "BUSINESS_SECTOR"
MCA_COL_OBLIGATION = "CSR_OBLIGATION_LAKHS"
MCA_COL_SPENT = "CSR_SPENT_LAKHS"
MCA_COL_UNSPENT = "CSR_UNSPENT_LAKHS"
MCA_COL_FY = "FINANCIAL_YEAR"


def _parse_amount(s: str) -> float | None:
    if not s:
        return None
    try:
        cleaned = re.sub(r"[^\d.]", "", str(s))
        return round(float(cleaned), 2) if cleaned else None
    except ValueError:
        return None


def _fuzzy_match(query: str, candidates: list[str], threshold: float = 0.80) -> str | None:
    """Find the best fuzzy match for query in candidates list."""
    q = query.lower().strip()
    best_score = 0.0
    best_match = None
    for c in candidates:
        score = SequenceMatcher(None, q, c.lower().strip()).ratio()
        if score > best_score:
            best_score = score
            best_match = c
    if best_score >= threshold:
        return best_match
    return None


def download_mca_csv() -> str | None:
    """
    Download MCA CSR CSV from the configured URL.
    Returns file path if successful, None otherwise.
    """
    url = os.getenv("MCA_CSR_DOWNLOAD_URL")
    if not url:
        logger.info("MCA_CSR_DOWNLOAD_URL not set — skipping download")
        return None

    try:
        import requests
        logger.info(f"Downloading MCA CSR dataset from {url}…")
        r = requests.get(url, timeout=120, stream=True)
        r.raise_for_status()
        out_path = "data/mca_csr_disclosures.csv"
        os.makedirs("data", exist_ok=True)
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                f.write(chunk)
        logger.info(f"Downloaded MCA CSV to {out_path} ({os.path.getsize(out_path)} bytes)")
        return out_path
    except Exception as e:
        logger.error(f"MCA CSV download failed: {e}")
        return None


def run(csv_path: str | None = None, dry_run: bool = False):
    """
    Main sync function.

    csv_path: Path to local CSV file (if None, tries to download)
    dry_run:  If True, print changes without writing to DB
    """
    try:
        from sansadx_backend.db import engine
        from sqlalchemy import text
        from core.db_helpers import _q
        from modules.csr_data_loader import make_slug, normalize_status, normalize_company_type
    except ImportError as e:
        logger.error(f"Import failed: {e}")
        return

    # Get the CSV path
    if not csv_path:
        csv_path = download_mca_csv()
    if not csv_path:
        csv_path = os.getenv("MCA_CSR_CSV_PATH", "data/mca_csr_disclosures.csv")
    if not os.path.exists(csv_path):
        logger.warning(f"MCA CSV not found at {csv_path}. Download manually from:")
        logger.warning("  https://www.mca.gov.in/content/mca/global/en/data-and-reports/company-data.html")
        logger.info("Skipping MCA sync — no data file available")
        return {"skipped": True, "reason": "MCA CSV file not found"}

    # Load existing company names for fuzzy matching
    existing = _q("SELECT id, name FROM csr_companies")
    name_to_id = {r["name"]: r["id"] for r in existing}
    existing_names = list(name_to_id.keys())

    now = datetime.utcnow()
    updated = inserted = skipped = 0

    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    logger.info(f"Loaded {len(rows)} rows from MCA CSV")

    for row in rows:
        company_name = (row.get(MCA_COL_COMPANY) or "").strip()
        if not company_name:
            skipped += 1
            continue

        obligation = _parse_amount(row.get(MCA_COL_OBLIGATION, ""))
        spent = _parse_amount(row.get(MCA_COL_SPENT, ""))
        unspent = _parse_amount(row.get(MCA_COL_UNSPENT, ""))
        sector = (row.get(MCA_COL_SECTOR) or "").strip()
        state = (row.get(MCA_COL_STATE) or "").strip()
        fy = (row.get(MCA_COL_FY) or "").strip()

        if dry_run:
            logger.info(f"[DRY RUN] {company_name} | spent={spent} | unspent={unspent} | sector={sector}")
            continue

        # Try exact match first, then fuzzy
        matched_id = name_to_id.get(company_name)
        matched_name = company_name
        if not matched_id:
            fuzzy = _fuzzy_match(company_name, existing_names)
            if fuzzy:
                matched_id = name_to_id[fuzzy]
                matched_name = fuzzy
                logger.debug(f"Fuzzy match: '{company_name}' → '{fuzzy}'")

        try:
            if matched_id:
                # Update existing company
                updates = {
                    "last_enriched_at": now,
                    "id": matched_id,
                }
                if unspent is not None:
                    updates["unspent_obligation_lakhs"] = unspent
                    updates["has_unspent_obligation"] = unspent > 0
                if spent is not None and fy:
                    # Map FY to spend column
                    fy_clean = fy.replace("-", "_").replace(" ", "_")
                    if "2022" in fy or "2023" in fy.split("-")[0]:
                        updates["spend_2022_23"] = spent
                    elif "2023" in fy or "2024" in fy.split("-")[0]:
                        updates["spend_2023_24"] = spent
                    elif "2024" in fy or "2025" in fy.split("-")[0]:
                        updates["spend_2024_25"] = spent

                set_parts = [f"{k} = :{k}" for k in updates if k != "id"]
                with engine.begin() as conn:
                    conn.execute(
                        text(f"UPDATE csr_companies SET {', '.join(set_parts)} WHERE id = :id"),
                        updates
                    )
                updated += 1
            else:
                # Insert new company from MCA data
                slug = make_slug(company_name)
                params = {
                    "name": company_name,
                    "slug": slug,
                    "state": state or "Unknown",
                    "district": "",
                    "company_type": "remote",
                    "sector": sector,
                    "sector_priorities": "[]",
                    "unspent_obligation_lakhs": unspent,
                    "has_unspent_obligation": bool(unspent and unspent > 0),
                    "status": "zero_spend" if (unspent and unspent > 0) else "active",
                    "last_enriched_at": now,
                    "created_at": now,
                }
                with engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO csr_companies
                            (name, slug, state, district, company_type, sector,
                             sector_priorities, unspent_obligation_lakhs, has_unspent_obligation,
                             status, last_enriched_at, created_at)
                        VALUES
                            (:name, :slug, :state, :district, :company_type, :sector,
                             :sector_priorities, :unspent_obligation_lakhs, :has_unspent_obligation,
                             :status, :last_enriched_at, :created_at)
                        ON CONFLICT (slug) DO NOTHING
                    """), params)
                inserted += 1
                # Register in lookup for subsequent iterations
                name_to_id[company_name] = -1  # placeholder
                existing_names.append(company_name)

        except Exception as e:
            logger.warning(f"Sync failed for '{company_name}': {e}")
            skipped += 1

    logger.info(f"MCA CSR sync complete — updated: {updated}, inserted: {inserted}, skipped: {skipped}")
    return {"updated": updated, "inserted": inserted, "skipped": skipped}


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    csv_arg = None
    if "--csv" in sys.argv:
        idx = sys.argv.index("--csv")
        if idx + 1 < len(sys.argv):
            csv_arg = sys.argv[idx + 1]
    run(csv_path=csv_arg, dry_run=dry)
