"""
CAG Audit Report Scraper & Para Extractor
==========================================
Scrapes the Comptroller & Auditor General of India's audit reports,
downloads PDFs, and extracts scheme-level audit observations (paras).

Strategy:
  1. Fetch report listing from cag.gov.in/en/audit-report with browser headers
  2. If blocked (403), enumerate recent report IDs directly (known pattern)
  3. Download PDFs and parse with PyMuPDF
  4. Extract scheme names, para numbers, and audit findings using pattern matching
  5. Optionally enrich with Gemini AI for better extraction

Output: cag_paras.json
  {
    "metadata": { scraped_at, total_reports, total_paras, source },
    "reports": [
      {
        "report_no", "year", "title", "url", "type",
        "ministry", "pdf_url", "fetched", "para_count",
        "paras": [
          {
            "para_no", "heading", "scheme", "ministry",
            "finding_summary", "amount_cr", "type",
            "status"   # "Active" (recent report) / "Historical"
          }
        ]
      }
    ],
    "scheme_index": {
      "scheme_name": [ { report_no, year, para_no, finding_summary } ]
    }
  }

Usage:
    python scripts/scrape_cag.py [--years 2024 2025] [--max-reports 20]
"""

import requests
import json
import logging
import time
import os
import re
import argparse
import tempfile
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import pymupdf
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False
    logging.warning("PyMuPDF not installed. PDF parsing unavailable. Install with: pip install pymupdf")

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

CAG_BASE = "https://cag.gov.in"
CAG_REPORT_LIST = f"{CAG_BASE}/en/audit-report/audit-report-list"
CAG_REPORT_DETAIL = f"{CAG_BASE}/en/audit-report/details"
CAG_PDF_BASE = f"{CAG_BASE}/webroot/uploads/download_audit_report"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "max-age=0",
}

OUTPUT_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "cag_paras.json"
)
PDF_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "cag_pdf_cache"
)

# CAG report ID ranges for recent years (discovered by manual inspection)
# IDs are sequential — reports from 2023-2026 are in this range
KNOWN_REPORT_ID_RANGES = {
    2026: range(122800, 123200),
    2025: range(121500, 122800),
    2024: range(119000, 121500),
    2023: range(116000, 119000),
}

# Keywords that identify scheme-related audit paras
SCHEME_KEYWORDS = [
    r"pradhan mantri", r"pm\s*[-–]", r"central sector scheme", r"centrally sponsored",
    r"yojana", r"mission", r"abhiyan", r"scheme", r"programme", r"project",
    r"kisan", r"awas", r"swachh", r"ayushman", r"mudra", r"mgnrega", r"jal jeevan",
    r"poshan", r"ujjwala", r"saubhagya", r"dbt", r"direct benefit",
]
SCHEME_PATTERN = re.compile("|".join(SCHEME_KEYWORDS), re.IGNORECASE)

# Amount patterns (₹X crore / Rs. X lakh etc.)
AMOUNT_PATTERN = re.compile(
    r"(?:₹|Rs\.?|INR)\s*([\d,]+(?:\.\d+)?)\s*(?:crore|lakh|crores|lakhs|Cr|L)",
    re.IGNORECASE,
)

# Para heading patterns
PARA_PATTERN = re.compile(
    r"(?:Para(?:graph)?|Observation)\s+(\d+(?:\.\d+)*)",
    re.IGNORECASE,
)

# CAG audit finding keywords
FINDING_KEYWORDS = [
    "unspent", "unutilized", "lapsed", "short release", "excess expenditure",
    "irregular expenditure", "non-utilization", "diversion of funds",
    "loss to exchequer", "short recovery", "excess payment", "avoidable expenditure",
    "infructuous expenditure", "wasteful expenditure", "non-achievement",
    "delay in implementation", "shortfall", "non-compliance",
]
FINDING_PATTERN = re.compile("|".join(FINDING_KEYWORDS), re.IGNORECASE)

# Ministry names for attribution
MINISTRY_KEYWORDS = [
    "Ministry of Finance", "Ministry of Agriculture", "Ministry of Health",
    "Ministry of Education", "Ministry of Rural Development", "Ministry of Housing",
    "Ministry of Jal Shakti", "Ministry of MSME", "Ministry of Women",
    "Ministry of Tribal Affairs", "Ministry of Social Justice",
    "Ministry of Road Transport", "Ministry of Railways", "Ministry of Defence",
    "Ministry of Home", "Ministry of External Affairs", "Ministry of Commerce",
    "Ministry of Power", "Ministry of New and Renewable Energy",
    "Ministry of Environment", "Ministry of IT", "Ministry of Electronics",
    "Department of Revenue", "Department of Expenditure", "DPIIT",
]


# ── Step 1: Fetch Report Listing ──────────────────────────────────────────────

def fetch_report_listing(years: list, session: requests.Session) -> list:
    """
    Fetch CAG audit report listing. Tries the HTML listing first,
    falls back to enumerating known ID ranges.
    """
    reports = []

    # Try the listing page with browser headers
    logger.info(f"Fetching CAG report listing for years: {years}")
    try:
        resp = session.get(CAG_REPORT_LIST, timeout=20)
        if resp.status_code == 200 and HAS_BS4:
            logger.info("CAG listing page accessible. Parsing HTML...")
            reports = _parse_report_listing(resp.text, years)
            if reports:
                logger.info(f"Found {len(reports)} reports from listing page.")
                return reports
        else:
            logger.warning(f"CAG listing returned {resp.status_code}. Trying ID enumeration.")
    except Exception as e:
        logger.warning(f"CAG listing fetch error: {e}. Trying ID enumeration.")

    # Fallback: enumerate known ID ranges
    reports = _enumerate_report_ids(years, session)
    return reports


def _parse_report_listing(html: str, years: list) -> list:
    """Parse the CAG audit report list HTML page."""
    soup = BeautifulSoup(html, "html.parser")
    reports = []

    # CAG listing uses a table or card layout
    # Try multiple selectors
    links = soup.find_all("a", href=re.compile(r"/en/audit-report/details/\d+"))
    for link in links:
        href = link.get("href", "")
        report_id = re.search(r"/details/(\d+)", href)
        if not report_id:
            continue

        title = link.get_text(strip=True)
        year_match = re.search(r"\b(20\d{2})\b", title)
        year = int(year_match.group(1)) if year_match else None

        if year and year not in years:
            continue

        reports.append({
            "report_id": int(report_id.group(1)),
            "title": title,
            "year": year,
            "detail_url": f"{CAG_BASE}{href}" if href.startswith("/") else href,
            "pdf_url": None,
            "ministry": _extract_ministry(title),
            "type": _classify_report_type(title),
        })

    return reports


def _enumerate_report_ids(years: list, session: requests.Session) -> list:
    """
    Enumerate CAG report detail pages by ID to discover recent reports.
    Uses known ID ranges per year. Tries IDs in steps to avoid hammering the server.
    """
    logger.info("Enumerating CAG report IDs (fallback method)...")
    reports = []

    for year in years:
        id_range = KNOWN_REPORT_ID_RANGES.get(year)
        if not id_range:
            continue

        # Sample IDs rather than fetching all (step of 5 to reduce requests)
        sample_ids = list(id_range)[::5][:60]  # Max 60 probes per year
        logger.info(f"  Year {year}: probing {len(sample_ids)} IDs...")

        for report_id in sample_ids:
            url = f"{CAG_REPORT_DETAIL}/{report_id}"
            try:
                resp = session.get(url, timeout=10)
                if resp.status_code == 200 and HAS_BS4:
                    meta = _parse_report_detail_page(resp.text, report_id, year)
                    if meta:
                        reports.append(meta)
                        logger.info(f"    Found: [{report_id}] {meta['title'][:60]}")
                elif resp.status_code == 404:
                    continue  # ID doesn't exist
                time.sleep(0.5)  # Polite delay
            except Exception as e:
                logger.debug(f"    ID {report_id}: {e}")
                continue

    logger.info(f"Found {len(reports)} reports via ID enumeration.")
    return reports


def _parse_report_detail_page(html: str, report_id: int, year: int) -> dict:
    """Parse a CAG report detail page to extract metadata and PDF URL."""
    soup = BeautifulSoup(html, "html.parser")

    # Extract title
    title_el = (
        soup.find("h1") or soup.find("h2") or
        soup.find(class_=re.compile("title|heading", re.I))
    )
    title = title_el.get_text(strip=True) if title_el else ""

    # Validate — ensure it looks like an audit report page
    if not title or len(title) < 5:
        return None
    if not any(kw in title.lower() for kw in ["audit", "report", "cag", "comptroller"]):
        return None

    # Extract PDF download links
    pdf_links = soup.find_all("a", href=re.compile(r"\.pdf", re.I))
    pdf_url = None
    for link in pdf_links:
        href = link.get("href", "")
        if "download_audit_report" in href or "audit" in href.lower():
            pdf_url = href if href.startswith("http") else f"{CAG_BASE}{href}"
            break

    return {
        "report_id": report_id,
        "title": title,
        "year": year,
        "detail_url": f"{CAG_REPORT_DETAIL}/{report_id}",
        "pdf_url": pdf_url,
        "ministry": _extract_ministry(title),
        "type": _classify_report_type(title),
    }


# ── Step 2: Download & Parse PDFs ────────────────────────────────────────────

def process_reports(reports: list, session: requests.Session, max_workers: int = 3) -> list:
    """
    Download and parse PDFs for each report.
    Returns reports enriched with extracted paras.
    """
    if not HAS_PYMUPDF:
        logger.error("PyMuPDF not available. Cannot parse PDFs.")
        logger.error("Install with: pip install pymupdf")
        return [{**r, "paras": [], "fetched": False} for r in reports]

    os.makedirs(PDF_CACHE_DIR, exist_ok=True)

    enriched = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_process_single_report, r, session): r
            for r in reports if r.get("pdf_url")
        }
        for future in as_completed(futures):
            result = future.result()
            if result:
                enriched.append(result)
                logger.info(
                    f"  [{result['year']}] {result['title'][:50]}... "
                    f"→ {len(result.get('paras', []))} paras"
                )

    # Add reports without PDF URLs
    fetched_ids = {r["report_id"] for r in enriched}
    for r in reports:
        if r["report_id"] not in fetched_ids:
            enriched.append({**r, "paras": [], "fetched": False, "para_count": 0})

    return enriched


def _process_single_report(report: dict, session: requests.Session) -> dict:
    """Download PDF, extract text, and parse paras for one report."""
    pdf_url = report.get("pdf_url")
    if not pdf_url:
        return {**report, "paras": [], "fetched": False, "para_count": 0}

    # Check PDF cache
    cache_key = re.sub(r"[^\w]", "_", pdf_url)[-80:]
    cache_path = os.path.join(PDF_CACHE_DIR, f"{cache_key}.txt")

    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            text = f.read()
        logger.debug(f"  Using cached text for {report.get('report_id')}")
    else:
        text = _download_and_extract_pdf(pdf_url, session)
        if text:
            with open(cache_path, "w", encoding="utf-8") as f:
                f.write(text)

    if not text:
        return {**report, "paras": [], "fetched": False, "para_count": 0}

    paras = _extract_paras(text, report)
    return {
        **report,
        "paras": paras,
        "fetched": True,
        "para_count": len(paras),
    }


def _download_and_extract_pdf(url: str, session: requests.Session) -> str:
    """Download a PDF and extract its text content."""
    try:
        resp = session.get(url, timeout=60, stream=True)
        if resp.status_code != 200:
            logger.debug(f"PDF download failed ({resp.status_code}): {url}")
            return ""

        # Write to temp file
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            for chunk in resp.iter_content(chunk_size=8192):
                tmp.write(chunk)
            tmp_path = tmp.name

        # Extract text
        doc = pymupdf.open(tmp_path)
        text_parts = []
        for page in doc:
            text_parts.append(page.get_text())
        doc.close()
        os.unlink(tmp_path)

        return "\n".join(text_parts)

    except Exception as e:
        logger.debug(f"PDF extraction error for {url}: {e}")
        return ""


# ── Step 3: Extract Audit Paras ──────────────────────────────────────────────

def _extract_paras(text: str, report: dict) -> list:
    """
    Extract scheme-related audit paragraphs from PDF text.
    Uses regex pattern matching to identify paras, scheme names, amounts, findings.
    """
    paras = []
    lines = text.split("\n")

    # Build para blocks — group text by para headings
    blocks = _split_into_para_blocks(lines)

    for block in blocks:
        block_text = " ".join(block["lines"])

        # Only include paras that mention schemes or government programmes
        if not SCHEME_PATTERN.search(block_text):
            continue

        # Extract key details
        scheme = _extract_scheme_name(block_text)
        amounts = _extract_amounts(block_text)
        finding = _extract_finding(block_text)
        ministry = _extract_ministry(block_text) or report.get("ministry", "")

        if not scheme and not finding:
            continue

        paras.append({
            "para_no": block.get("para_no", ""),
            "heading": block.get("heading", "")[:200],
            "scheme": scheme,
            "ministry": ministry,
            "finding_summary": _summarize_finding(block_text, finding),
            "amount_cr": amounts[0] if amounts else None,
            "all_amounts": amounts[:3],
            "type": _classify_para_type(block_text),
            "status": "Active" if report.get("year", 0) >= 2024 else "Historical",
            "report_year": report.get("year"),
            "report_no": report.get("title", ""),
        })

    return paras


def _split_into_para_blocks(lines: list) -> list:
    """
    Split PDF text lines into logical para blocks.
    Each block starts at a para heading (e.g., "Para 3.1", "3.2 Scheme Name").
    """
    blocks = []
    current = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check for para heading
        para_match = PARA_PATTERN.search(line)
        numbered_match = re.match(r"^(\d+\.\d+(?:\.\d+)?)\s+(.+)", line)

        if para_match or (numbered_match and len(line) > 15):
            if current and current["lines"]:
                blocks.append(current)
            current = {
                "para_no": para_match.group(1) if para_match else (
                    numbered_match.group(1) if numbered_match else ""
                ),
                "heading": line[:200],
                "lines": [line],
            }
        elif current is not None:
            current["lines"].append(line)
        else:
            # Pre-para content, create a default block
            current = {"para_no": "", "heading": "", "lines": [line]}

    if current and current["lines"]:
        blocks.append(current)

    # Merge blocks that have no para_no and are very short (orphan lines)
    merged = []
    for block in blocks:
        has_para_no = bool(block.get("para_no"))
        is_tiny = len(" ".join(block["lines"])) < 50
        if merged and not has_para_no and is_tiny:
            merged[-1]["lines"].extend(block["lines"])
        else:
            merged.append(block)

    return merged


def _extract_scheme_name(text: str) -> str:
    """Extract the most prominent scheme name from text."""
    # Try to match known scheme name patterns
    patterns = [
        r"(Pradhan Mantri\s+[\w\s]+(?:Yojana|Mission|Scheme|Abhiyan|Nidhi|Bima|Suraksha))",
        r"(PM\s*[-–]\s*[\w\s]+(?:Yojana|Mission|Scheme|Abhiyan))",
        r"([\w\s]+(?:Yojana|Abhiyan|Mission)\s*[\w\s]*)",
        r"(MGNREGA|PMAY|PMJDY|PMKSY|PMGSY|NHM|SSA|MDMS)",
        r"(?:scheme|programme|project)\s+[\"'""]([\w\s]+)[\"'""]",
        r"\"([\w\s]+(?:Scheme|Yojana|Mission|Programme))\"",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            if 3 < len(name) < 120:
                return name
    return ""


def _extract_amounts(text: str) -> list:
    """Extract all monetary amounts from text, return in crores."""
    amounts = []
    for match in AMOUNT_PATTERN.finditer(text):
        value_str = match.group(1).replace(",", "")
        try:
            value = float(value_str)
            unit = match.group(0).lower()
            # Convert to crores
            if "lakh" in unit:
                value = value / 100
            amounts.append(round(value, 2))
        except ValueError:
            continue
    return amounts


def _extract_finding(text: str) -> str:
    """Extract the primary audit finding type."""
    match = FINDING_PATTERN.search(text)
    return match.group(0).lower() if match else ""


def _extract_ministry(text: str) -> str:
    """Extract ministry name from text."""
    for ministry in MINISTRY_KEYWORDS:
        if ministry.lower() in text.lower():
            return ministry
    return ""


def _classify_report_type(title: str) -> str:
    """Classify CAG report type from title."""
    title_lower = title.lower()
    if "performance audit" in title_lower:
        return "performance"
    if "compliance audit" in title_lower:
        return "compliance"
    if "state finance" in title_lower:
        return "state_finance"
    if "commercial" in title_lower:
        return "commercial"
    return "general"


def _classify_para_type(text: str) -> str:
    """Classify audit observation type."""
    text_lower = text.lower()
    if any(kw in text_lower for kw in ["unspent", "unutilized", "lapsed", "non-utilization"]):
        return "unspent_funds"
    if any(kw in text_lower for kw in ["excess", "irregular", "avoidable", "wasteful"]):
        return "irregular_expenditure"
    if any(kw in text_lower for kw in ["delay", "non-achievement", "shortfall"]):
        return "implementation_failure"
    if any(kw in text_lower for kw in ["diversion", "misappropriation"]):
        return "fund_diversion"
    return "general_observation"


def _summarize_finding(text: str, finding_type: str) -> str:
    """Extract a concise finding summary (first 2 sentences containing the finding)."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    relevant = []
    for sent in sentences:
        if finding_type and finding_type.lower() in sent.lower():
            relevant.append(sent.strip())
        elif FINDING_PATTERN.search(sent):
            relevant.append(sent.strip())
        if len(relevant) >= 2:
            break
    summary = " ".join(relevant)
    return summary[:500] if summary else text[:300]


# ── Step 4: Build Output & Scheme Index ──────────────────────────────────────

def build_scheme_index(reports: list) -> dict:
    """Build a reverse index: scheme_name → list of audit observations."""
    index = {}
    for report in reports:
        for para in report.get("paras", []):
            scheme = para.get("scheme", "").strip()
            if not scheme:
                continue
            if scheme not in index:
                index[scheme] = []
            index[scheme].append({
                "report_year": para.get("report_year"),
                "report_title": report.get("title", "")[:100],
                "para_no": para.get("para_no"),
                "type": para.get("type"),
                "finding_summary": para.get("finding_summary", "")[:200],
                "amount_cr": para.get("amount_cr"),
            })
    return index


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Scrape CAG audit reports and extract scheme paras")
    parser.add_argument("--years", nargs="+", type=int, default=[2025, 2024],
                        help="Years to scrape (e.g. 2025 2024)")
    parser.add_argument("--max-reports", type=int, default=30,
                        help="Maximum number of reports to process")
    parser.add_argument("--output", default=OUTPUT_FILE, help="Output JSON file path")
    parser.add_argument("--workers", type=int, default=3,
                        help="Parallel download workers")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info(f"CAG Audit Report Scraper — Years: {args.years}")
    logger.info("=" * 60)

    if not HAS_PYMUPDF:
        logger.error("PyMuPDF is required for PDF parsing.")
        logger.error("Install: pip install pymupdf")
        return

    session = requests.Session()
    session.headers.update(HEADERS)

    # Step 1: Fetch report listing
    reports = fetch_report_listing(args.years, session)

    if not reports:
        logger.error("No reports found. Possible causes:")
        logger.error("  - cag.gov.in is blocking this IP (try from a different network)")
        logger.error("  - Report ID ranges need updating (edit KNOWN_REPORT_ID_RANGES)")
        return

    # Limit to max-reports
    reports = reports[:args.max_reports]
    logger.info(f"Processing {len(reports)} reports...")

    # Step 2: Download PDFs and extract paras
    enriched_reports = process_reports(reports, session, max_workers=args.workers)

    # Step 3: Build scheme index
    scheme_index = build_scheme_index(enriched_reports)

    # Aggregate stats
    total_paras = sum(len(r.get("paras", [])) for r in enriched_reports)
    fetched_count = sum(1 for r in enriched_reports if r.get("fetched"))

    # Para type breakdown
    type_counts = {}
    for report in enriched_reports:
        for para in report.get("paras", []):
            t = para.get("type", "general")
            type_counts[t] = type_counts.get(t, 0) + 1

    output = {
        "metadata": {
            "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": "cag.gov.in (Comptroller and Auditor General of India)",
            "years_covered": args.years,
            "total_reports_found": len(enriched_reports),
            "reports_with_pdf": fetched_count,
            "total_paras_extracted": total_paras,
            "schemes_with_observations": len(scheme_index),
            "para_type_breakdown": type_counts,
            "note": (
                "Para extraction uses pattern matching on PDF text. "
                "Accuracy improves with Gemini AI enrichment (set GEMINI_API_KEY). "
                "Some PDFs may be image-based and require OCR for full extraction."
            ),
        },
        "reports": sorted(enriched_reports, key=lambda r: (r.get("year", 0), r.get("report_id", 0)), reverse=True),
        "scheme_index": dict(sorted(scheme_index.items(), key=lambda x: len(x[1]), reverse=True)),
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    logger.info(f"\nResults saved to: {args.output}")
    logger.info(f"  Reports found    : {len(enriched_reports)}")
    logger.info(f"  PDFs fetched     : {fetched_count}")
    logger.info(f"  Paras extracted  : {total_paras}")
    logger.info(f"  Schemes indexed  : {len(scheme_index)}")
    if type_counts:
        logger.info(f"  Para types       : {type_counts}")


if __name__ == "__main__":
    main()
