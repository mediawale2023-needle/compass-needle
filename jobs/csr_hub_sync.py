"""
jobs/csr_hub_sync.py — Sync sector benchmarks from National CSR Hub and PM CARES Fund data.

Data sources:
  1. National CSR Hub (TISS Mumbai)
     - CSR Activity Database: https://www.nationalcsrhub.in/
     - Annual CSR report search by sector/state

  2. MCA Annual Report on CSR (Schedule VII companies)
     - MCA portal: https://www.mca.gov.in/content/mca/global/en/data-and-reports/company-data.html
     - CSR summary data: Total spend, unspent obligations, sector-wise breakdown

  3. PM CARES Fund
     - Audited accounts: https://www.pmcares.gov.in/en/
     - Annual receipt and disbursement data

Updates:
  - data/csr_hub_benchmarks.json (sector benchmarks, PM CARES, unspent analysis)

Schedule: Annually (July 1st at 04:00 IST — post-FY data release)

Usage:
    python -m jobs.csr_hub_sync [--fy 2023-24] [--dry-run]

Environment variables:
    MCA_CSR_SUMMARY_CSV_PATH  — Path to MCA CSR summary CSV (sector-wise totals)
    NATIONAL_CSR_HUB_API_KEY  — API key for nationalcsrhub.in (if available)
"""
import sys
import os
import json
import re
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger("needle.jobs.csr_hub_sync")

CSR_HUB_PATH = "data/csr_hub_benchmarks.json"

# MCA sector name → our internal sector name mapping
MCA_SECTOR_MAP = {
    "education": "Education",
    "health": "Health",
    "healthcare": "Health",
    "rural development": "Rural Development",
    "environment": "Environment / Sustainability",
    "environmental sustainability": "Environment / Sustainability",
    "livelihood": "Livelihood / Skill Development",
    "skill development": "Livelihood / Skill Development",
    "vocational skills": "Livelihood / Skill Development",
    "water": "Water & Sanitation",
    "sanitation": "Water & Sanitation",
    "water sanitation": "Water & Sanitation",
    "sports": "Sports / Culture / Heritage",
    "culture": "Sports / Culture / Heritage",
    "heritage": "Sports / Culture / Heritage",
    "women": "Women Empowerment",
    "gender": "Women Empowerment",
    "disaster": "Disaster Relief / PM CARES",
    "pm cares": "Disaster Relief / PM CARES",
}


def _to_float(s) -> float | None:
    if s is None:
        return None
    try:
        return round(float(re.sub(r"[^\d.]", "", str(s))), 2)
    except (ValueError, TypeError):
        return None


def scrape_mca_csr_summary(fy: str = "2023-24") -> dict | None:
    """
    Scrape MCA's publicly available CSR summary data.

    MCA publishes annual CSR data at:
    https://www.mca.gov.in/content/mca/global/en/data-and-reports/company-data.html

    Returns dict with total_spend_cr, sector_breakdown, top_companies.
    """
    try:
        import requests
        from bs4 import BeautifulSoup

        url = "https://www.mca.gov.in/content/mca/global/en/data-and-reports/company-data.html"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
        }
        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "lxml")

        # Look for CSR data links / tables
        result = {"fy": fy, "scraped_at": datetime.utcnow().isoformat()}

        # Find total CSR spend if present in page
        for tag in soup.find_all(["td", "span", "div", "p"]):
            text = tag.get_text(strip=True)
            if "total csr" in text.lower() and "crore" in text.lower():
                total_match = re.search(r"[\d,]+\.?\d*", text)
                if total_match:
                    result["total_spend_cr"] = _to_float(total_match.group())
                    logger.info(f"  Found total CSR spend: ₹{result['total_spend_cr']} Cr")

        return result if len(result) > 2 else None

    except Exception as e:
        logger.debug(f"MCA CSR summary scrape failed: {e}")
        return None


def parse_mca_sector_csv(csv_path: str) -> dict | None:
    """
    Parse locally downloaded MCA CSR sector summary CSV.

    Expected columns: Sector, Total_Amount_Cr, Company_Count, YoY_Change_Pct
    """
    if not os.path.exists(csv_path):
        return None

    try:
        import csv
        sector_data = {}
        with open(csv_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sector_raw = (row.get("Sector") or row.get("CSR_Sector") or "").lower().strip()
                sector_name = MCA_SECTOR_MAP.get(sector_raw, sector_raw.title())
                spend = _to_float(row.get("Total_Amount_Cr") or row.get("amount"))
                count = _to_float(row.get("Company_Count"))
                yoy = _to_float(row.get("YoY_Change_Pct"))

                if sector_name and spend:
                    sector_data[sector_name] = {
                        "spend_cr": spend,
                        "company_count": int(count) if count else None,
                        "yoy_growth_pct": yoy,
                    }

        logger.info(f"Parsed {len(sector_data)} sectors from MCA CSV")
        return sector_data

    except Exception as e:
        logger.error(f"MCA sector CSV parse failed: {e}")
        return None


def fetch_pm_cares_data() -> dict | None:
    """
    Fetch PM CARES Fund receipt/disbursement from published audited accounts.

    PM CARES publishes annual audited accounts at:
    https://www.pmcares.gov.in/en/web/page/audited_annual_accounts
    """
    try:
        import requests
        from bs4 import BeautifulSoup

        url = "https://www.pmcares.gov.in/en/web/page/audited_annual_accounts"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")

        result = {"scraped_at": datetime.utcnow().isoformat()}

        # Find amount tables in audited accounts links
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
                if len(cells) >= 2:
                    label = cells[0].lower()
                    if "total receipt" in label or "total contribution" in label:
                        val = _to_float(cells[-1])
                        if val:
                            result["latest_receipt_cr"] = val
                    elif "total disburs" in label or "total expenditure" in label:
                        val = _to_float(cells[-1])
                        if val:
                            result["latest_disbursed_cr"] = val

        return result if len(result) > 1 else None

    except Exception as e:
        logger.debug(f"PM CARES fetch failed: {e}")
        return None


def run(fy: str = "2023-24", dry_run: bool = False) -> dict:
    """Main sync function."""
    logger.info(f"Starting CSR Hub / PM CARES sync for FY{fy}…")

    if not os.path.exists(CSR_HUB_PATH):
        logger.error(f"CSR Hub data file not found: {CSR_HUB_PATH}")
        return {"error": "file_missing"}

    with open(CSR_HUB_PATH) as f:
        db = json.load(f)

    updated_sections = []

    # 1. Try MCA sector CSV (local file)
    csv_path = os.getenv("MCA_CSR_SUMMARY_CSV_PATH", "data/mca_csr_sector_summary.csv")
    sector_data = parse_mca_sector_csv(csv_path)

    if sector_data:
        sector_map = {s["sector"]: i for i, s in enumerate(db["sector_benchmarks"])}
        for sector_name, data in sector_data.items():
            idx = sector_map.get(sector_name)
            if idx is None:
                logger.debug(f"New sector from MCA: {sector_name}")
                continue
            if not dry_run:
                if data.get("spend_cr"):
                    db["sector_benchmarks"][idx]["spend_cr"] = data["spend_cr"]
                if data.get("yoy_growth_pct") is not None:
                    db["sector_benchmarks"][idx]["yoy_growth_pct"] = data["yoy_growth_pct"]
        updated_sections.append("sector_benchmarks")
        logger.info(f"Updated {len(sector_data)} sector benchmarks from MCA CSV")

    # 2. Try scraping MCA website
    mca_summary = scrape_mca_csr_summary(fy=fy)
    if mca_summary and mca_summary.get("total_spend_cr"):
        if not dry_run:
            db["metadata"]["total_india_csr_spend_cr"] = mca_summary["total_spend_cr"]
            db["metadata"]["reference_fy"] = fy
            db["metadata"]["last_updated"] = datetime.utcnow().strftime("%Y-%m-%d")
        updated_sections.append("metadata_total_spend")
        logger.info(f"Updated total India CSR spend: ₹{mca_summary['total_spend_cr']} Cr")

    # 3. Fetch PM CARES data
    pm_cares = fetch_pm_cares_data()
    if pm_cares:
        if not dry_run:
            if pm_cares.get("latest_receipt_cr"):
                # Add to PM CARES history
                db["pm_cares_fund"]["latest_receipt_cr"] = pm_cares["latest_receipt_cr"]
            if pm_cares.get("latest_disbursed_cr"):
                db["pm_cares_fund"]["latest_disbursed_cr"] = pm_cares["latest_disbursed_cr"]
        updated_sections.append("pm_cares")
        logger.info(f"Updated PM CARES data")

    if not dry_run and updated_sections:
        db["metadata"]["last_updated"] = datetime.utcnow().strftime("%Y-%m-%d")
        with open(CSR_HUB_PATH, "w") as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved {CSR_HUB_PATH}")

    logger.info(f"CSR Hub sync complete — updated sections: {updated_sections}")
    return {"updated_sections": updated_sections, "fy": fy}


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    fy_arg = "2023-24"
    if "--fy" in sys.argv:
        idx = sys.argv.index("--fy")
        if idx + 1 < len(sys.argv):
            fy_arg = sys.argv[idx + 1]
    run(fy=fy_arg, dry_run=dry)
