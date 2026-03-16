"""
jobs/csrbox_sync.py — Sync historical CSR grant data from CSR Box and Tracxn CSR Database.

Data sources:
  1. CSR Box India (csrbox.org)
     - CSR grant search: https://csrbox.org/India_CSR_project_search.php
     - Company CSR profiles with project listings

  2. Tracxn CSR Database (tracxn.com)
     - CSR intelligence data (requires paid subscription)
     - Alternative: data.gov.in CSR project filings

  3. MCA CSR Project Filings (public)
     - Companies are required to file Form CSR-1 and CSR-2 with MCA
     - MCA portal: https://efiling.mca.gov.in/

Updates:
  - data/csrbox_grants.json (historical grant records, aggregates)

Schedule: Monthly (1st of each month at 05:00 IST)

Usage:
    python -m jobs.csrbox_sync [--company "Tata Trusts"] [--district Gadchiroli] [--dry-run]

Environment variables:
    CSRBOX_SESSION_COOKIE  — Session cookie from csrbox.org (for scraping)
    TRACXN_API_KEY         — Tracxn API key (premium)
    DATA_GOV_IN_API_KEY    — For MCA CSR project data via data.gov.in
"""
import sys
import os
import json
import re
import time
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger("needle.jobs.csrbox_sync")

CSRBOX_GRANTS_PATH = "data/csrbox_grants.json"
DATA_GOV_BASE = "https://api.data.gov.in/resource"
CSRBOX_SEARCH_URL = "https://csrbox.org/India_CSR_project_search.php"

# data.gov.in resource ID for MCA CSR project data
MCA_CSR_PROJECTS_RESOURCE = "8b6c1f22-9d3e-4a0b-c7f1-3e6d0a4b5f95"


def _to_float(s) -> float | None:
    if s is None:
        return None
    try:
        return round(float(re.sub(r"[^\d.]", "", str(s))), 2)
    except (ValueError, TypeError):
        return None


def scrape_csrbox_company(company_name: str) -> list[dict]:
    """
    Scrape CSR Box for project listings for a given company.

    CSR Box has a public project search at:
    https://csrbox.org/India_CSR_project_search.php

    Returns list of project dicts.
    """
    try:
        import requests
        from bs4 import BeautifulSoup

        session_cookie = os.getenv("CSRBOX_SESSION_COOKIE")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Referer": "https://csrbox.org/",
        }
        if session_cookie:
            headers["Cookie"] = f"PHPSESSID={session_cookie}"

        params = {
            "company_name": company_name,
            "state": "Maharashtra",
            "submit": "Search",
        }

        r = requests.get(CSRBOX_SEARCH_URL, params=params, headers=headers, timeout=20)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "lxml")
        projects = []

        # Parse project table (CSR Box table structure)
        table = soup.find("table", {"id": "project_table"}) or soup.find("table", {"class": "table"})
        if not table:
            return []

        headers_row = table.find("tr")
        col_names = [th.get_text(strip=True).lower() for th in headers_row.find_all(["th", "td"])]

        for row in table.find_all("tr")[1:]:
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cells) < 4:
                continue

            project = {}
            for i, col in enumerate(col_names[:len(cells)]):
                project[col] = cells[i] if i < len(cells) else ""

            # Normalise fields
            normalized = {
                "company": company_name,
                "sector": project.get("sector", ""),
                "district": project.get("district", "") or project.get("location", ""),
                "amount_lakhs": _to_float(project.get("amount") or project.get("budget")),
                "fy": project.get("fy") or project.get("financial year", ""),
                "project_type": project.get("project") or project.get("project name", ""),
                "implementing_agency": project.get("implementing agency", ""),
                "status": project.get("status", "Active"),
                "source": "csrbox",
                "fetched_at": datetime.utcnow().isoformat(),
            }
            if normalized.get("district") or normalized.get("amount_lakhs"):
                projects.append(normalized)

        logger.info(f"  CSR Box: found {len(projects)} projects for {company_name}")
        return projects

    except Exception as e:
        logger.debug(f"CSR Box scrape failed for {company_name}: {e}")
        return []


def fetch_mca_csr_projects(state: str = "Maharashtra") -> list[dict]:
    """
    Fetch CSR project filings from data.gov.in (MCA CSR Form-2 data).

    MCA mandates Form CSR-2 filings from FY2020-21 onwards.
    Returns list of project records.
    """
    key = os.getenv("DATA_GOV_IN_API_KEY")
    if not key:
        logger.warning("DATA_GOV_IN_API_KEY not set")
        return []

    try:
        import requests
        params = {
            "api-key": key,
            "format": "json",
            "limit": 500,
            "filters[STATE]": state,
        }
        r = requests.get(
            f"{DATA_GOV_BASE}/{MCA_CSR_PROJECTS_RESOURCE}",
            params=params,
            timeout=30
        )
        r.raise_for_status()
        records = r.json().get("records", [])
        logger.info(f"  MCA CSR projects: fetched {len(records)} from data.gov.in")
        return records

    except Exception as e:
        logger.error(f"MCA CSR projects fetch failed: {e}")
        return []


def _normalise_mca_record(rec: dict) -> dict:
    """Normalise a data.gov.in MCA CSR project record to our grant schema."""
    return {
        "grant_id": f"MCA-{rec.get('CIN', 'UNK')}-{rec.get('SR_NO', '0')}",
        "company": (rec.get("COMPANY_NAME") or "").strip(),
        "implementing_agency": (rec.get("IMPLEMENTING_AGENCY") or "").strip(),
        "sector": (rec.get("CSR_SECTOR") or rec.get("SCHEDULE_VII_ACTIVITY") or "").strip(),
        "district": (rec.get("DISTRICT") or rec.get("LOCATION") or "").strip(),
        "amount_lakhs": _to_float(rec.get("AMOUNT_SPENT_LAKHS") or rec.get("PROJECT_BUDGET")),
        "fy": (rec.get("FINANCIAL_YEAR") or "").strip(),
        "project_type": (rec.get("PROJECT_TITLE") or rec.get("PROJECT_NAME") or "").strip(),
        "beneficiaries": int(rec.get("BENEFICIARY_COUNT") or 0),
        "status": "Active",
        "source": "mca_form_csr2",
        "cin": (rec.get("CIN") or "").strip(),
    }


def _dedup_grants(existing: list[dict], new: list[dict]) -> tuple[list[dict], int]:
    """
    Merge new grants into existing list, deduplicating by grant_id.
    Returns (merged_list, added_count).
    """
    existing_ids = {g.get("grant_id") for g in existing if g.get("grant_id")}
    added = 0
    merged = list(existing)

    for grant in new:
        gid = grant.get("grant_id")
        if gid and gid in existing_ids:
            continue
        merged.append(grant)
        if gid:
            existing_ids.add(gid)
        added += 1

    return merged, added


def update_aggregates(db: dict) -> dict:
    """Recompute sector and district aggregate summaries from grants list."""
    from collections import defaultdict

    sector_totals: dict[str, dict] = defaultdict(lambda: {"total_grants": 0, "total_value_cr": 0.0})
    district_totals: dict[str, dict] = defaultdict(lambda: {"total_grants": 0, "total_value_cr": 0.0})

    for grant in db.get("grants", []):
        sector = grant.get("sector") or "Other"
        district = grant.get("district") or "Unknown"
        amount_cr = (grant.get("amount_lakhs") or 0) / 100

        sector_totals[sector]["total_grants"] += 1
        sector_totals[sector]["total_value_cr"] = round(
            sector_totals[sector]["total_value_cr"] + amount_cr, 2
        )

        district_totals[district]["total_grants"] += 1
        district_totals[district]["total_value_cr"] = round(
            district_totals[district]["total_value_cr"] + amount_cr, 2
        )

    db["aggregates_by_sector"] = [
        {
            "sector": sector,
            "total_grants": data["total_grants"],
            "total_value_cr": data["total_value_cr"],
            "avg_grant_lakhs": round(
                (data["total_value_cr"] * 100) / data["total_grants"], 1
            ) if data["total_grants"] else 0,
        }
        for sector, data in sorted(sector_totals.items(), key=lambda x: -x[1]["total_value_cr"])
    ]

    db["aggregates_by_district"] = [
        {
            "district": district,
            "total_grants": data["total_grants"],
            "total_value_cr": data["total_value_cr"],
        }
        for district, data in sorted(district_totals.items(), key=lambda x: -x[1]["total_value_cr"])
        if district not in ("Unknown", "")
    ]

    total_cr = sum(g.get("amount_lakhs", 0) or 0 for g in db.get("grants", [])) / 100
    db["metadata"]["total_grants"] = len(db.get("grants", []))
    db["metadata"]["total_value_cr"] = round(total_cr, 2)
    db["metadata"]["last_updated"] = datetime.utcnow().strftime("%Y-%m-%d")

    return db


def run(company_filter: str | None = None, district_filter: str | None = None,
        dry_run: bool = False) -> dict:
    """
    Main sync function.

    1. Scrapes CSR Box for each company in csr_db.json
    2. Fetches MCA CSR Form-2 data from data.gov.in
    3. Merges and deduplicates into csrbox_grants.json
    4. Recomputes aggregates
    """
    if not os.path.exists(CSRBOX_GRANTS_PATH):
        logger.error(f"CSRBox grants file not found: {CSRBOX_GRANTS_PATH}")
        return {"error": "file_missing"}

    with open(CSRBOX_GRANTS_PATH) as f:
        db = json.load(f)

    total_added = 0

    # Load company list from csr_db.json
    csr_db_path = "csr_db.json"
    if os.path.exists(csr_db_path):
        with open(csr_db_path) as f:
            csr = json.load(f)
        companies = list({r["Company"] for r in csr if r.get("Company")})
    else:
        companies = []

    # 1. Scrape CSR Box
    for company in companies:
        if company_filter and company_filter.lower() not in company.lower():
            continue

        projects = scrape_csrbox_company(company)

        if district_filter:
            projects = [p for p in projects if district_filter.lower() in (p.get("district") or "").lower()]

        if projects and not dry_run:
            # Assign grant IDs
            for i, p in enumerate(projects):
                if not p.get("grant_id"):
                    p["grant_id"] = f"CSR-BOX-{company[:8].replace(' ', '')}-{i+1:03d}"

            db["grants"], added = _dedup_grants(db["grants"], projects)
            total_added += added
            if added:
                logger.info(f"  {company}: +{added} grants from CSR Box")

        time.sleep(1)  # Rate limit

    # 2. Fetch MCA data.gov.in CSR projects
    mca_records = fetch_mca_csr_projects()
    if mca_records:
        mca_grants = [_normalise_mca_record(r) for r in mca_records]

        if district_filter:
            mca_grants = [g for g in mca_grants if district_filter.lower() in (g.get("district") or "").lower()]
        if company_filter:
            mca_grants = [g for g in mca_grants if company_filter.lower() in (g.get("company") or "").lower()]

        if not dry_run:
            db["grants"], added = _dedup_grants(db["grants"], mca_grants)
            total_added += added
            if added:
                logger.info(f"  MCA Form CSR-2: +{added} grants from data.gov.in")

    # 3. Recompute aggregates
    if not dry_run and total_added:
        db = update_aggregates(db)
        with open(CSRBOX_GRANTS_PATH, "w") as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved {CSRBOX_GRANTS_PATH}")

    logger.info(f"CSRBox sync complete — {total_added} new grants added")
    return {
        "added": total_added,
        "total_grants": len(db.get("grants", [])),
    }


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    company_arg = None
    district_arg = None
    if "--company" in sys.argv:
        idx = sys.argv.index("--company")
        if idx + 1 < len(sys.argv):
            company_arg = sys.argv[idx + 1]
    if "--district" in sys.argv:
        idx = sys.argv.index("--district")
        if idx + 1 < len(sys.argv):
            district_arg = sys.argv[idx + 1]
    run(company_filter=company_arg, district_filter=district_arg, dry_run=dry)
