"""
jobs/bse_nse_sync.py — Sync company market cap and financial health indicators from BSE/NSE.

Data sources:
  1. BSE India API (bseindia.com)
     - Company search: https://api.bseindia.com/BseIndiaAPI/api/ComHeader/w?quotetype=EQ&scripcode={bse_code}
     - Quote data:    https://api.bseindia.com/BseIndiaAPI/api/getScripHeaderData/w?Scrip_Cd={bse_code}

  2. NSE India API (nseindia.com)
     - Company info:  https://www.nseindia.com/api/quote-equity?symbol={nse_symbol}
     - Market cap:    https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%2050

  3. Yahoo Finance (fallback, no auth required)
     - Quote:         https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.NS

Updates:
  - csr_db.json: Market_Cap_Cr, net_profit fields

Schedule: Weekly (Monday 06:00 IST — post market weekend reset)

Usage:
    python -m jobs.bse_nse_sync [--company "Reliance Industries"] [--dry-run]

Environment variables:
    NSE_SESSION_COOKIE   — Session cookie from nseindia.com (for NSE API access)
    BSE_API_KEY          — BSE data API key (if using premium BSE feed)
"""
import sys
import os
import json
import time
import logging
import re
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger("needle.jobs.bse_nse_sync")

CSR_DB_PATH = "csr_db.json"

# Yahoo Finance symbol map (symbol.NS for NSE, symbol.BO for BSE)
YAHOO_SYMBOLS = {
    "Reliance Foundation":   "RELIANCE.NS",
    "Tata Trusts":           "TATAMOTORS.NS",
    "Infosys Foundation":    "INFY.NS",
    "HDFC Bank Parivartan":  "HDFCBANK.NS",
    "Wipro Foundation":      "WIPRO.NS",
    "HCL Foundation":        "HCLTECH.NS",
    "Mahindra & Mahindra":   "M&M.NS",
    "JSW Steel":             "JSWSTEEL.NS",
    "Sun Pharma":            "SUNPHARMA.NS",
    "Bajaj Auto":            "BAJAJ-AUTO.NS",
    "UltraTech Cement":      "ULTRACEMCO.NS",
    "SBI Foundation":        "SBIN.NS",
    "Tata Motors":           "TATAMOTORS.NS",
    "Kirloskar Industries":  "KIRLOSIND.NS",
    "Sanghi Cement":         "SANGHIIND.NS",
}

BSE_CODES = {
    "Reliance Foundation":   "500325",
    "Infosys Foundation":    "500209",
    "HDFC Bank Parivartan":  "500180",
    "Wipro Foundation":      "507685",
    "HCL Foundation":        "532281",
    "Mahindra & Mahindra":   "500520",
    "JSW Steel":             "500228",
    "Sun Pharma":            "524715",
    "Bajaj Auto":            "532977",
    "UltraTech Cement":      "532538",
    "SBI Foundation":        "500112",
    "Tata Motors":           "500570",
    "Kirloskar Industries":  "500243",
    "Sanghi Cement":         "526521",
}


def fetch_yahoo_finance(symbol: str) -> dict | None:
    """
    Fetch market cap and key financials from Yahoo Finance chart API.

    Returns dict with market_cap_cr, pe_ratio, or None on failure.
    """
    try:
        import requests
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
        }
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()

        meta = data.get("chart", {}).get("result", [{}])[0].get("meta", {})
        market_cap = meta.get("marketCap")  # in INR (not crore)
        regular_price = meta.get("regularMarketPrice")

        if market_cap:
            market_cap_cr = round(market_cap / 1e7, 0)  # convert to crore
            return {
                "market_cap_cr": market_cap_cr,
                "current_price": regular_price,
                "currency": meta.get("currency", "INR"),
                "exchange": meta.get("exchangeName"),
                "fetched_at": datetime.utcnow().isoformat(),
            }
    except Exception as e:
        logger.debug(f"Yahoo Finance fetch failed for {symbol}: {e}")
    return None


def fetch_bse_company(bse_code: str) -> dict | None:
    """
    Fetch company data from BSE India public API.

    BSE API requires session cookies for some endpoints.
    Returns dict with market_cap_cr, company_name, sector or None on failure.
    """
    try:
        import requests
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.bseindia.com/",
            "Accept": "application/json",
        }
        url = f"https://api.bseindia.com/BseIndiaAPI/api/ComHeader/w?quotetype=EQ&scripcode={bse_code}"
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()

        if data:
            mktcap = data.get("MktCapFull") or data.get("MarketCap")
            if mktcap:
                # BSE returns market cap in crore
                return {
                    "market_cap_cr": float(str(mktcap).replace(",", "")),
                    "company_name": data.get("LongName"),
                    "sector": data.get("Sector"),
                }
    except Exception as e:
        logger.debug(f"BSE fetch failed for {bse_code}: {e}")
    return None


def fetch_nse_company(nse_symbol: str, session_cookie: str | None = None) -> dict | None:
    """
    Fetch company data from NSE India API.

    NSE requires a valid session cookie. Obtain by visiting nseindia.com in browser.
    Set NSE_SESSION_COOKIE env var.
    """
    try:
        import requests

        # First get session cookies via homepage
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "en-US,en;q=0.9",
        })

        if session_cookie:
            session.cookies.set("nsit", session_cookie)
        else:
            # Warm session
            session.get("https://www.nseindia.com", timeout=10)

        url = f"https://www.nseindia.com/api/quote-equity?symbol={nse_symbol.upper()}"
        r = session.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()

        info = data.get("info", {})
        mktcap_str = info.get("marketCap", "")
        if mktcap_str:
            mktcap_cr = _parse_cr(str(mktcap_str))
            return {
                "market_cap_cr": mktcap_cr,
                "company_name": info.get("companyName"),
                "sector": info.get("industry"),
                "pe_ratio": _to_float(info.get("pe")),
            }
    except Exception as e:
        logger.debug(f"NSE fetch failed for {nse_symbol}: {e}")
    return None


def _parse_cr(s: str) -> float | None:
    """Parse market cap string to crore (handles Cr, Lakh Cr, etc.)."""
    s = s.replace(",", "").strip()
    try:
        if "lakh cr" in s.lower():
            return round(float(re.sub(r"[^\d.]", "", s)) * 100000, 0)
        if "cr" in s.lower():
            return round(float(re.sub(r"[^\d.]", "", s)), 0)
        return round(float(re.sub(r"[^\d.]", "", s)) / 1e7, 0)
    except (ValueError, TypeError):
        return None


def _to_float(s) -> float | None:
    if s is None:
        return None
    try:
        return round(float(re.sub(r"[^\d.]", "", str(s))), 2)
    except (ValueError, TypeError):
        return None


def run(company_filter: str | None = None, dry_run: bool = False) -> dict:
    """
    Main sync function.

    For each company in csr_db.json with a BSE/NSE code, fetch live market cap
    and update the record.

    Priority order: Yahoo Finance → BSE API → NSE API
    """
    if not os.path.exists(CSR_DB_PATH):
        logger.error(f"CSR DB not found: {CSR_DB_PATH}")
        return {"error": "csr_db_not_found"}

    with open(CSR_DB_PATH) as f:
        csr = json.load(f)

    # Build unique company set
    seen_companies = set()
    company_records: dict[str, list] = {}
    for record in csr:
        company = record.get("Company", "")
        if company not in seen_companies:
            seen_companies.add(company)
            company_records[company] = []
        company_records[company].append(record)

    nse_session = os.getenv("NSE_SESSION_COOKIE")
    updated = skipped = failed = 0

    for company, records in company_records.items():
        if company_filter and company_filter.lower() not in company.lower():
            continue

        yahoo_sym = YAHOO_SYMBOLS.get(company)
        bse_code = BSE_CODES.get(company)
        nse_sym = records[0].get("NSE_Symbol") if records else None

        data = None

        # Try Yahoo Finance first (no auth needed)
        if yahoo_sym:
            data = fetch_yahoo_finance(yahoo_sym)
            if data:
                logger.info(f"  {company}: market cap ₹{data['market_cap_cr']:,.0f} Cr (Yahoo)")

        # Try BSE
        if not data and bse_code:
            data = fetch_bse_company(bse_code)
            if data:
                logger.info(f"  {company}: market cap ₹{data['market_cap_cr']:,.0f} Cr (BSE)")

        # Try NSE
        if not data and nse_sym:
            data = fetch_nse_company(nse_sym, nse_session)
            if data:
                logger.info(f"  {company}: market cap ₹{data['market_cap_cr']:,.0f} Cr (NSE)")

        if not data:
            logger.debug(f"  {company}: no market data fetched")
            skipped += 1
            continue

        # Apply to all records for this company
        if not dry_run:
            for rec in records:
                if data.get("market_cap_cr") is not None:
                    rec["Market_Cap_Cr"] = data["market_cap_cr"]
                rec["Last_Enriched_At"] = datetime.utcnow().strftime("%Y-%m-%d")
        updated += 1
        time.sleep(0.5)  # Rate limit

    if not dry_run and updated:
        with open(CSR_DB_PATH, "w") as f:
            json.dump(csr, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved {CSR_DB_PATH}")

    logger.info(f"BSE/NSE sync complete — updated: {updated}, skipped: {skipped}, failed: {failed}")
    return {"updated": updated, "skipped": skipped, "failed": failed}


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    company_arg = None
    if "--company" in sys.argv:
        idx = sys.argv.index("--company")
        if idx + 1 < len(sys.argv):
            company_arg = sys.argv[idx + 1]
    run(company_filter=company_arg, dry_run=dry)
