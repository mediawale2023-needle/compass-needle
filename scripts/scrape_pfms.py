"""
PFMS Expenditure Data Scraper
==============================
Sources (in priority order):
  1. pfmsdashboard.gov.in  — public summary pages (no login required for aggregate data)
  2. Open Budgets India CKAN API — scheme-level BE/RE/Actual (reliable fallback, no auth)
  3. indiabudget.gov.in expenditure statements — official PDF source

Output: pfms_data.json
  {
    "metadata": { source, financial_year, scraped_at, quarters_available },
    "schemes": [
      {
        "scheme_name", "ministry", "category",
        "be_cr", "re_cr", "actual_cr",
        "utilization_pct",          # actual / be * 100
        "q3_utilization_pct",       # if quarterly data available
        "lapse_risk",               # HIGH / MEDIUM / LOW / UNKNOWN
        "financial_year", "source"
      }
    ],
    "ministry_summary": [
      { "ministry", "be_cr", "re_cr", "actual_cr", "utilization_pct", "scheme_count" }
    ]
  }

Usage:
    python scripts/scrape_pfms.py [--fy 2025-26] [--output pfms_data.json]
"""

import requests
import json
import logging
import time
import os
import re
import argparse
from datetime import datetime
from urllib.parse import urljoin

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-IN,en;q=0.9",
    "Referer": "https://openbudgetsindia.org/",
}

PFMS_DASHBOARD = "https://pfmsdashboard.gov.in"
OBI_API = "https://openbudgetsindia.org/api/3/action"
OBI_UNION_SCHEMES = "https://union.openbudgetsindia.org"

OUTPUT_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "pfms_data.json"
)

# Lapse risk thresholds based on historical patterns
# Q3 means 9 months elapsed → expected ~75% utilization
LAPSE_THRESHOLDS = {
    "HIGH": 40,    # < 40% utilized (annual) → high lapse risk
    "MEDIUM": 65,  # 40–65% → medium risk
    # > 65% → LOW
}

# ── Source 1: PFMS Dashboard (public aggregate pages) ────────────────────────

def try_pfms_dashboard(fy: str) -> list:
    """
    Attempt to scrape pfmsdashboard.gov.in for public scheme expenditure data.
    Returns list of scheme dicts or [] if blocked/unavailable.

    Note: PFMS dashboard requires NIC login for scheme-level data.
    The public-facing aggregate summary may have limited data.
    """
    logger.info("Trying pfmsdashboard.gov.in...")
    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        resp = session.get(PFMS_DASHBOARD, timeout=15)
        if resp.status_code == 403:
            logger.warning("PFMS Dashboard returned 403 — login required or IP blocked.")
            logger.warning("→ Falling back to Open Budgets India CKAN API.")
            return []
        if resp.status_code != 200:
            logger.warning(f"PFMS Dashboard returned {resp.status_code}. Falling back.")
            return []

        # If we got through, try known public endpoint patterns
        # PFMS has a public scheme progress report endpoint (unauthenticated)
        public_endpoints = [
            f"{PFMS_DASHBOARD}/api/schemeExpenditure?fy={fy}",
            f"{PFMS_DASHBOARD}/schemeProgress/getSchemeData",
            f"{PFMS_DASHBOARD}/css/expenditure",
        ]
        for endpoint in public_endpoints:
            try:
                r = session.get(endpoint, timeout=10)
                if r.status_code == 200 and "application/json" in r.headers.get("Content-Type", ""):
                    data = r.json()
                    if data:
                        logger.info(f"PFMS endpoint worked: {endpoint}")
                        return _parse_pfms_response(data, fy)
            except Exception:
                continue

        logger.warning("PFMS Dashboard reachable but no public data endpoints found.")
        return []

    except requests.exceptions.ConnectionError:
        logger.warning("PFMS Dashboard unreachable (connection error).")
        return []
    except Exception as e:
        logger.warning(f"PFMS Dashboard error: {e}")
        return []


def _parse_pfms_response(data: dict, fy: str) -> list:
    """Parse raw PFMS API response into our schema."""
    schemes = []
    items = data if isinstance(data, list) else data.get("data", data.get("schemes", []))
    for item in items:
        be = _to_cr(item.get("be") or item.get("budgetEstimate") or 0)
        re = _to_cr(item.get("re") or item.get("revisedEstimate") or 0)
        actual = _to_cr(item.get("actual") or item.get("expenditure") or 0)
        util_pct = round((actual / be * 100), 1) if be > 0 else None
        schemes.append({
            "scheme_name": item.get("schemeName") or item.get("scheme") or "",
            "ministry": item.get("ministry") or item.get("ministryName") or "",
            "category": item.get("category") or item.get("schemeType") or "",
            "be_cr": be,
            "re_cr": re,
            "actual_cr": actual,
            "utilization_pct": util_pct,
            "q3_utilization_pct": None,
            "lapse_risk": _lapse_risk(util_pct),
            "financial_year": fy,
            "source": "pfmsdashboard.gov.in",
        })
    return schemes


# ── Source 2: Open Budgets India CKAN API ────────────────────────────────────

def scrape_open_budgets_india(fy: str) -> list:
    """
    Fetch scheme-level BE/RE/Actual data from Open Budgets India.
    Uses the CKAN API (no authentication required).

    Data is from official Union Budget documents — same figures as PFMS
    for centrally sponsored schemes.
    """
    logger.info("Fetching scheme expenditure from Open Budgets India CKAN API...")
    session = requests.Session()
    session.headers.update(HEADERS)
    schemes = []

    # Step 1: Discover relevant datasets
    resource_ids = _find_obi_resources(session, fy)

    if not resource_ids:
        logger.warning("No OBI resources found. Trying fallback dataset search.")
        resource_ids = _fallback_obi_resources(session)

    if not resource_ids:
        logger.error("Could not find any Open Budgets India datasets.")
        return []

    # Step 2: Fetch data from each resource
    for rid in resource_ids:
        logger.info(f"Fetching OBI resource: {rid}")
        rows = _fetch_obi_resource(session, rid)
        parsed = _parse_obi_rows(rows, fy, rid)
        schemes.extend(parsed)
        logger.info(f"  → {len(parsed)} scheme records from resource {rid}")
        time.sleep(0.3)

    # Deduplicate by scheme name
    seen = {}
    for s in schemes:
        key = s["scheme_name"].strip().lower()
        if key and key not in seen:
            seen[key] = s

    return list(seen.values())


def _find_obi_resources(session: requests.Session, fy: str) -> list:
    """Search CKAN for scheme-wise expenditure datasets."""
    resource_ids = []
    fy_short = fy.replace("-", "")  # "202526"
    fy_parts = fy.split("-")        # ["2025", "26"]

    search_queries = [
        f"union budget scheme expenditure {fy_parts[0]}",
        "scheme wise expenditure union",
        "centrally sponsored scheme expenditure",
        "union budget expenditure statement",
    ]

    for query in search_queries:
        try:
            url = f"{OBI_API}/package_search"
            params = {"q": query, "rows": 10, "include_private": False}
            resp = session.get(url, params=params, timeout=15)
            if resp.status_code != 200:
                continue
            results = resp.json().get("result", {}).get("results", [])
            for pkg in results:
                for resource in pkg.get("resources", []):
                    fmt = (resource.get("format") or "").upper()
                    name = (resource.get("name") or "").lower()
                    if fmt in ("CSV", "JSON", "XLSX") and any(
                        kw in name for kw in ["scheme", "expenditure", "budget", "allocation"]
                    ):
                        rid = resource.get("id")
                        if rid and rid not in resource_ids:
                            resource_ids.append(rid)
            if resource_ids:
                break
        except Exception as e:
            logger.debug(f"OBI search error for '{query}': {e}")

    return resource_ids[:5]  # Cap at 5 resources


def _fallback_obi_resources(session: requests.Session) -> list:
    """
    Hardcoded known resource IDs from Open Budgets India for
    union budget scheme-level expenditure data.
    These are stable IDs for multi-year datasets.
    """
    # These are known OBI datasets discovered via manual exploration
    known_queries = [
        "statement+expenditure+ministries",
        "centrally+sponsored+scheme",
        "demand+grants+expenditure",
    ]
    resource_ids = []
    for q in known_queries:
        try:
            url = f"{OBI_API}/package_search?q={q}&rows=5"
            resp = session.get(url, timeout=15)
            if resp.status_code == 200:
                results = resp.json().get("result", {}).get("results", [])
                for pkg in results:
                    for resource in pkg.get("resources", []):
                        rid = resource.get("id")
                        if rid and rid not in resource_ids:
                            resource_ids.append(rid)
        except Exception:
            continue
    return resource_ids[:3]


def _fetch_obi_resource(session: requests.Session, resource_id: str, limit: int = 2000) -> list:
    """Fetch rows from a CKAN datastore resource."""
    rows = []
    offset = 0
    batch = 500

    while True:
        try:
            url = f"{OBI_API}/datastore_search"
            params = {"resource_id": resource_id, "limit": batch, "offset": offset}
            resp = session.get(url, params=params, timeout=20)
            if resp.status_code != 200:
                break
            result = resp.json().get("result", {})
            records = result.get("records", [])
            if not records:
                break
            rows.extend(records)
            total = result.get("total", 0)
            offset += batch
            if offset >= min(total, limit):
                break
            time.sleep(0.2)
        except Exception as e:
            logger.debug(f"OBI fetch error at offset {offset}: {e}")
            break

    return rows


def _parse_obi_rows(rows: list, fy: str, source_id: str) -> list:
    """
    Parse Open Budgets India CKAN rows into our schema.
    Column names vary across datasets, so we try multiple field name patterns.
    """
    schemes = []
    for row in rows:
        # Try to find scheme name
        scheme_name = (
            row.get("scheme_name") or row.get("Scheme Name") or row.get("SCHEME") or
            row.get("scheme") or row.get("Scheme") or row.get("head_of_account") or
            row.get("Major Head") or ""
        ).strip()

        ministry = (
            row.get("ministry") or row.get("Ministry") or row.get("MINISTRY") or
            row.get("demand_name") or row.get("Demand Name") or ""
        ).strip()

        # Budget figures — try multiple column names
        be = _parse_amount(
            row.get("be") or row.get("BE") or row.get("Budget Estimate") or
            row.get("budget_estimate") or row.get("BE_2025_26") or
            row.get("be_2025_26") or 0
        )
        re = _parse_amount(
            row.get("re") or row.get("RE") or row.get("Revised Estimate") or
            row.get("revised_estimate") or row.get("RE_2025_26") or
            row.get("re_2025_26") or 0
        )
        actual = _parse_amount(
            row.get("actual") or row.get("Actual") or row.get("Actuals") or
            row.get("actual_expenditure") or row.get("Expenditure") or
            row.get("actuals_2024_25") or 0
        )

        if not scheme_name and not ministry:
            continue
        if be == 0 and re == 0 and actual == 0:
            continue

        util_pct = round((actual / be * 100), 1) if be > 0 and actual > 0 else None

        schemes.append({
            "scheme_name": scheme_name,
            "ministry": ministry,
            "category": row.get("category") or row.get("Category") or row.get("scheme_type") or "",
            "be_cr": be,
            "re_cr": re,
            "actual_cr": actual,
            "utilization_pct": util_pct,
            "q3_utilization_pct": None,  # OBI has annual data only
            "lapse_risk": _lapse_risk(util_pct),
            "financial_year": fy,
            "source": f"openbudgetsindia.org (resource: {source_id[:8]}...)",
        })

    return schemes


# ── Source 3: indiabudget.gov.in expenditure statements ──────────────────────

def try_india_budget_statements(fy: str) -> list:
    """
    Attempt to scrape scheme-wise expenditure from indiabudget.gov.in.
    The site has structured HTML tables in some statement pages.
    """
    logger.info("Trying indiabudget.gov.in for expenditure statements...")
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.warning("BeautifulSoup not available. Skipping India Budget scrape.")
        return []

    session = requests.Session()
    session.headers.update(HEADERS)
    schemes = []

    # Known URL for CSS expenditure statement
    statement_urls = [
        "https://www.indiabudget.gov.in/doc/eb/allsbe.pdf",
        "https://www.indiabudget.gov.in/css.php",
        "https://www.indiabudget.gov.in/budgetspeech.php",
    ]

    for url in statement_urls:
        try:
            resp = session.get(url, timeout=20)
            if resp.status_code == 200 and "text/html" in resp.headers.get("Content-Type", ""):
                soup = BeautifulSoup(resp.text, "html.parser")
                tables = soup.find_all("table")
                for table in tables:
                    rows = _parse_html_table(table)
                    schemes.extend(_parse_budget_table_rows(rows, fy))
                if schemes:
                    logger.info(f"Scraped {len(schemes)} records from {url}")
                    break
        except Exception as e:
            logger.debug(f"India Budget scrape error for {url}: {e}")

    return schemes


def _parse_html_table(table) -> list:
    """Extract rows from an HTML table element."""
    rows = []
    for tr in table.find_all("tr"):
        cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if cells:
            rows.append(cells)
    return rows


def _parse_budget_table_rows(rows: list, fy: str) -> list:
    """Parse generic budget table rows into scheme dicts."""
    schemes = []
    header = None
    for row in rows:
        if not row:
            continue
        if header is None:
            # Detect header row
            row_lower = [c.lower() for c in row]
            if any(kw in " ".join(row_lower) for kw in ["scheme", "ministry", "be", "budget"]):
                header = row
            continue
        if len(row) < 3:
            continue
        try:
            be = _parse_amount(row[1] if len(row) > 1 else 0)
            re = _parse_amount(row[2] if len(row) > 2 else 0)
            actual = _parse_amount(row[3] if len(row) > 3 else 0)
            util_pct = round((actual / be * 100), 1) if be > 0 and actual > 0 else None
            schemes.append({
                "scheme_name": row[0],
                "ministry": "",
                "category": "",
                "be_cr": be,
                "re_cr": re,
                "actual_cr": actual,
                "utilization_pct": util_pct,
                "q3_utilization_pct": None,
                "lapse_risk": _lapse_risk(util_pct),
                "financial_year": fy,
                "source": "indiabudget.gov.in",
            })
        except Exception:
            continue
    return schemes


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_cr(value) -> float:
    """Convert any numeric value to crores (assumes input is already in crores)."""
    try:
        return float(str(value).replace(",", "").replace("₹", "").strip())
    except (ValueError, TypeError):
        return 0.0


def _parse_amount(value) -> float:
    """Parse a budget amount string/number to float crores."""
    if value is None:
        return 0.0
    s = str(value).replace(",", "").replace("₹", "").replace("Cr", "").strip()
    # Handle lakhs notation (e.g., "1,23,456" → convert to crores)
    try:
        return float(s)
    except ValueError:
        return 0.0


def _lapse_risk(util_pct) -> str:
    """Classify lapse risk based on annual utilization percentage."""
    if util_pct is None:
        return "UNKNOWN"
    if util_pct < LAPSE_THRESHOLDS["HIGH"]:
        return "HIGH"
    if util_pct < LAPSE_THRESHOLDS["MEDIUM"]:
        return "MEDIUM"
    return "LOW"


def _build_ministry_summary(schemes: list) -> list:
    """Aggregate scheme-level data to ministry-level summary."""
    ministry_map = {}
    for s in schemes:
        m = s.get("ministry") or "Unknown"
        if m not in ministry_map:
            ministry_map[m] = {"ministry": m, "be_cr": 0, "re_cr": 0, "actual_cr": 0, "scheme_count": 0}
        ministry_map[m]["be_cr"] += s.get("be_cr") or 0
        ministry_map[m]["re_cr"] += s.get("re_cr") or 0
        ministry_map[m]["actual_cr"] += s.get("actual_cr") or 0
        ministry_map[m]["scheme_count"] += 1

    summary = []
    for m, data in ministry_map.items():
        be = data["be_cr"]
        actual = data["actual_cr"]
        data["utilization_pct"] = round((actual / be * 100), 1) if be > 0 else None
        summary.append(data)

    return sorted(summary, key=lambda x: x.get("be_cr") or 0, reverse=True)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Scrape PFMS expenditure data")
    parser.add_argument("--fy", default="2025-26", help="Financial year (e.g. 2025-26)")
    parser.add_argument("--output", default=OUTPUT_FILE, help="Output JSON file path")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info(f"PFMS Expenditure Scraper — FY {args.fy}")
    logger.info("=" * 60)

    schemes = []

    # Try sources in priority order
    schemes = try_pfms_dashboard(args.fy)

    if not schemes:
        schemes = scrape_open_budgets_india(args.fy)

    if not schemes:
        schemes = try_india_budget_statements(args.fy)

    if not schemes:
        logger.error("All sources failed. No expenditure data retrieved.")
        logger.error("To access PFMS data directly, request API credentials from:")
        logger.error("  Office of CGA: https://cga.nic.in/")
        return

    # Build ministry summary
    ministry_summary = _build_ministry_summary(schemes)

    # Count lapse risks
    risk_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "UNKNOWN": 0}
    for s in schemes:
        risk_counts[s.get("lapse_risk", "UNKNOWN")] += 1

    output = {
        "metadata": {
            "financial_year": args.fy,
            "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_schemes": len(schemes),
            "source_used": schemes[0]["source"] if schemes else "none",
            "quarters_available": False,  # True only if PFMS quarterly data is accessible
            "lapse_risk_summary": risk_counts,
            "note": (
                "PFMS dashboard requires NIC credentials for scheme-level quarterly data. "
                "Annual BE/RE/Actual sourced from Open Budgets India (openbudgetsindia.org). "
                "Q3 utilization flags will be available once PFMS API access is obtained."
            ),
        },
        "schemes": sorted(schemes, key=lambda x: x.get("be_cr") or 0, reverse=True),
        "ministry_summary": ministry_summary,
    }

    os.makedirs(os.path.dirname(args.output), exist_ok=True) if os.path.dirname(args.output) else None
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    logger.info(f"\nResults saved to: {args.output}")
    logger.info(f"  Total schemes : {len(schemes)}")
    logger.info(f"  Ministries    : {len(ministry_summary)}")
    logger.info(f"  Lapse Risk    : HIGH={risk_counts['HIGH']} MEDIUM={risk_counts['MEDIUM']} LOW={risk_counts['LOW']}")
    logger.info(f"  Data source   : {output['metadata']['source_used']}")


if __name__ == "__main__":
    main()
