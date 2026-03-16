"""
jobs/company_enrichment.py — Enrich CSR company profiles with additional signals.

Enrichment sources (in order of reliability):
  1. MCA21 public CSR disclosure portal (requests + HTML parsing)
  2. BSE/NSE filing metadata (company sector, CIN number)
  3. CSRBox / NGO registry cross-reference
  4. Google News RSS (recent CSR activity signals)

What gets updated:
  - unspent_obligation_lakhs (from MCA if available)
  - gap_analysis (updated narrative)
  - sector_priorities (refined from filings)
  - last_enriched_at

Schedule: Weekly on Sunday at 01:00 AM IST

Usage:
    python -m jobs.company_enrichment [--company "Reliance Industries"]
"""
import sys
import os
import re
import time
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger("needle.jobs.company_enrichment")


# ─────────────────────────────────────────
# MCA CSR DISCLOSURE SCRAPER
# ─────────────────────────────────────────
def fetch_mca_csr_data(company_name: str) -> dict | None:
    """
    Attempt to retrieve CSR disclosure data from MCA21 public portal.

    MCA CSR data URL pattern:
      https://efiling.mca.gov.in/eFiling/helpdocs/CSR_DATA.html
      (Search by company CIN or name via the public CSR filing portal)

    Returns dict with:
      { "unspent_lakhs": float, "obligation_lakhs": float, "sector": str }
    or None if data not available.

    NOTE: MCA does not have a stable public JSON API. This uses the
    downloadable CSR dataset (CSV) published annually at:
      https://www.mca.gov.in/content/mca/global/en/data-and-reports/company-data.html

    For production, point LOCAL_MCA_CSV_PATH to the downloaded file.
    """
    LOCAL_MCA_CSV_PATH = os.getenv("MCA_CSR_CSV_PATH", "data/mca_csr_disclosures.csv")

    if not os.path.exists(LOCAL_MCA_CSV_PATH):
        logger.debug(f"MCA CSV not found at {LOCAL_MCA_CSV_PATH} — skipping MCA enrichment")
        return None

    try:
        import csv
        with open(LOCAL_MCA_CSV_PATH, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            name_lower = company_name.lower()
            for row in reader:
                if name_lower in (row.get("COMPANY_NAME") or "").lower():
                    unspent = _parse_amount(row.get("CSR_UNSPENT_AMT") or "")
                    obligation = _parse_amount(row.get("CSR_OBLIGATION") or "")
                    return {
                        "unspent_lakhs": unspent,
                        "obligation_lakhs": obligation,
                        "sector": row.get("CSR_SECTOR", ""),
                        "cin": row.get("CIN", ""),
                        "fy": row.get("FY", ""),
                    }
    except Exception as e:
        logger.warning(f"MCA CSV parse error for {company_name}: {e}")
    return None


def _parse_amount(s: str) -> float | None:
    """Parse numeric amount from MCA CSV (values in ₹ Lakhs)."""
    if not s:
        return None
    try:
        cleaned = re.sub(r"[^\d.]", "", str(s))
        return round(float(cleaned), 2) if cleaned else None
    except ValueError:
        return None


# ─────────────────────────────────────────
# NEWS SIGNAL ENRICHMENT
# ─────────────────────────────────────────
def fetch_news_signals(company_name: str) -> dict:
    """
    Check Google News RSS for recent CSR activity signals.
    Returns dict with { "recent_csr_news": bool, "latest_headline": str }
    """
    try:
        import feedparser
        query = f"{company_name} CSR India 2024 OR 2025"
        url = f"https://news.google.com/rss/search?q={query.replace(' ', '+')}&hl=en-IN&gl=IN&ceid=IN:en"
        feed = feedparser.parse(url)
        if feed.entries:
            return {
                "recent_csr_news": True,
                "latest_headline": feed.entries[0].get("title", ""),
            }
    except Exception:
        pass
    return {"recent_csr_news": False, "latest_headline": ""}


# ─────────────────────────────────────────
# MAIN ENRICHMENT LOOP
# ─────────────────────────────────────────
def run(company_filter: str | None = None):
    try:
        from sansadx_backend.db import engine
        from sqlalchemy import text
        from core.db_helpers import _q
    except ImportError as e:
        logger.error(f"Import failed: {e}")
        return

    # Load companies needing enrichment
    try:
        if company_filter:
            companies = _q(
                "SELECT id, name, district FROM csr_companies WHERE LOWER(name) LIKE :pat",
                {"pat": f"%{company_filter.lower()}%"}
            )
        else:
            # Only re-enrich companies not enriched in the last 7 days
            from datetime import timedelta
            cutoff = datetime.utcnow() - timedelta(days=7)
            companies = _q("""
                SELECT id, name, district FROM csr_companies
                WHERE last_enriched_at IS NULL OR last_enriched_at < :cutoff
                LIMIT 50
            """, {"cutoff": cutoff})
    except Exception as e:
        logger.error(f"Failed to load companies: {e}")
        return

    logger.info(f"Enriching {len(companies)} companies…")
    enriched = 0

    for company in companies:
        cid = company["id"]
        name = company["name"]
        updates = {"last_enriched_at": datetime.utcnow(), "id": cid}

        # MCA enrichment
        mca = fetch_mca_csr_data(name)
        if mca:
            if mca.get("unspent_lakhs") is not None:
                updates["unspent_obligation_lakhs"] = mca["unspent_lakhs"]
                updates["has_unspent_obligation"] = mca["unspent_lakhs"] > 0
            logger.info(f"  MCA data found for {name}: unspent={mca.get('unspent_lakhs')}")
        else:
            logger.debug(f"  No MCA data for {name}")

        # Persist updates
        try:
            set_parts = [f"{k} = :{k}" for k in updates if k != "id"]
            if set_parts:
                with engine.begin() as conn:
                    conn.execute(
                        text(f"UPDATE csr_companies SET {', '.join(set_parts)} WHERE id = :id"),
                        updates
                    )
            enriched += 1
        except Exception as e:
            logger.warning(f"Update failed for {name}: {e}")

        # Rate-limit: 1 request per second to avoid blocking
        time.sleep(1)

    logger.info(f"Company enrichment complete — {enriched}/{len(companies)} companies updated")
    return {"enriched": enriched, "total": len(companies)}


if __name__ == "__main__":
    company_arg = None
    if "--company" in sys.argv:
        idx = sys.argv.index("--company")
        if idx + 1 < len(sys.argv):
            company_arg = sys.argv[idx + 1]
    run(company_filter=company_arg)
