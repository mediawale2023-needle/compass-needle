"""
Parliamentary Fund Intelligence Scraper
Scrapes fund utilization Q&A from ePARLib (sansad.in) for FY 2025-26,
then uses AI to extract structured fund allocation/utilization data.

Usage:
    python scripts/scrape_fund_intel.py
"""
import requests
import json
import logging
import time
import os
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

try:
    import pymupdf
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# ── Config ──────────────────────────────────────────
EPARLIB_BASE = "https://eparlib.sansad.in/restv3/fetch/all"
SANSAD_API = "https://sansad.in/api_ls"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Accept": "application/json",
    "Referer": "https://sansad.in/",
}

# FY 2025-26: March 2025 → February 2026
# We look at LS 18 sessions that fall within this range
FY_START = "2025-03-01"
FY_END = "2026-02-28"

# Keywords that indicate fund/utilization related questions
FUND_KEYWORDS = [
    "fund", "utilization", "utilisation", "allocation", "expenditure",
    "budget", "disbursement", "release", "sanction", "expenditure",
    "financial progress", "unspent", "unused", "lapsed",
]

OUTPUT_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fund_intel.json")
RAW_CACHE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "raw_qa_cache.json")
PDF_TEXT_CACHE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "pdf_text_cache.json")
AI_PARSE_CACHE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "ai_parse_cache.json")

# ── Step 1: Discover sessions in FY 2025-26 ────────
def get_sessions_in_range():
    """Get LS 18 sessions that fall within FY 2025-26."""
    logger.info("Fetching session data...")
    url = f"{SANSAD_API}/business/getAllLoksabhaAndSession"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    all_data = resp.json()

    # Find LS 18
    ls18 = None
    for ls in all_data:
        if ls.get("loksabha") == 18:
            ls18 = ls
            break

    if not ls18:
        logger.error("Lok Sabha 18 not found!")
        return []

    sessions_in_fy = []
    for session in ls18.get("sessions", []):
        # Check if session dates overlap with FY 2025-26
        dates = session.get("dates", [])
        if not dates:
            continue
        for d in dates:
            try:
                # Parse DD/MM/YYYY
                parts = d.split("/")
                iso = f"{parts[2]}-{parts[1]}-{parts[0]}"
                if FY_START <= iso <= FY_END:
                    sessions_in_fy.append({
                        "sessionNo": session["sessionNo"],
                        "period": session.get("sessionPeriod", []),
                    })
                    break
            except (IndexError, ValueError):
                continue

    logger.info(f"Found {len(sessions_in_fy)} sessions in FY 2025-26: {sessions_in_fy}")
    return sessions_in_fy


# ── Step 2: Scrape fund-related questions ───────────
def scrape_fund_questions(sessions):
    """Fetch questions from ePARLib for the given sessions, filtering for fund-related titles."""
    all_questions = []

    for sess in sessions:
        sess_no = sess["sessionNo"]
        logger.info(f"Scraping Session {sess_no}...")

        start = 0
        batch_size = 100
        total = None

        while True:
            params = {
                "collectionId": 3,  # Lok Sabha Questions
                "loksabhaNo": 18,
                "sessionNo": sess_no,
                "start": start,
                "rows": batch_size,
                "order": "desc",
            }
            try:
                resp = requests.get(EPARLIB_BASE, params=params, headers=HEADERS, timeout=30)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.error(f"Request failed at start={start}: {e}")
                break

            if total is None:
                total = int(data.get("rowsCount", 0))
                logger.info(f"  Session {sess_no}: {total} total questions")

            records = data.get("records", [])
            if not records:
                break

            # Filter for fund-related questions
            for rec in records:
                title = (rec.get("title") or "").lower()
                if any(kw in title for kw in FUND_KEYWORDS):
                    all_questions.append({
                        "title": rec.get("title", ""),
                        "date": rec.get("date", ""),
                        "session": sess_no,
                        "questionNo": rec.get("questionNo", ""),
                        "questionType": rec.get("questionType", ""),
                        "members": rec.get("members", []),
                        "files": rec.get("files", []),
                        "resourceId": rec.get("resourceId", ""),
                        "handle": rec.get("handle", ""),
                    })

            start += batch_size
            if start >= total:
                break

            # Rate limiting — be polite to government servers
            time.sleep(0.5)

    logger.info(f"Found {len(all_questions)} fund-related questions across all sessions")

    # If no sessions found in FY range, also try broader search
    if not sessions or not all_questions:
        logger.info("Trying broad search with field=ministry...")
        for page_start in range(0, 10000, 500):
            params = {
                "field": "ministry",
                "collectionId": 3,
                "loksabhaNo": 18,
                "start": page_start,
                "rows": 500,
                "order": "desc",
            }
            resp = requests.get(EPARLIB_BASE, params=params, headers=HEADERS, timeout=30)
            if resp.status_code != 200:
                break
            data = resp.json()
            records = data.get("records", [])
            if not records:
                break
            total = int(data.get("rowsCount", 0))
            logger.info(f"  Page {page_start}: {len(records)} records (total: {total})")
            for rec in records:
                title = (rec.get("title") or "").lower()
                date = rec.get("date", "")
                if any(kw in title for kw in FUND_KEYWORDS) and date >= FY_START:
                    ministry_list = rec.get("ministry", [])
                    ministry = ministry_list[0] if ministry_list else ""
                    all_questions.append({
                        "title": rec.get("title", ""),
                        "date": date,
                        "session": rec.get("sessionNo", ""),
                        "questionNo": rec.get("questionNo", ""),
                        "questionType": rec.get("questionType", ""),
                        "members": rec.get("members", []),
                        "files": rec.get("files", []),
                        "resourceId": rec.get("resourceId", ""),
                        "handle": rec.get("handle", ""),
                        "ministry": ministry,
                    })
            if page_start + 500 >= total:
                break
            time.sleep(0.5)
        logger.info(f"Broad search found {len(all_questions)} fund Q&As")

    return all_questions


# ── Step 2.5: Extract text from PDFs ───────────────
def extract_pdf_texts(questions):
    """Download PDFs and extract text using PyMuPDF. Cache results."""
    os.makedirs(os.path.dirname(PDF_TEXT_CACHE), exist_ok=True)
    cache = {}
    if os.path.exists(PDF_TEXT_CACHE):
        try:
            with open(PDF_TEXT_CACHE, "r") as f:
                cache = json.load(f)
        except Exception:
            pass

    if not HAS_PYMUPDF:
        logger.warning("PyMuPDF not installed, skipping PDF text extraction.")
        return cache

    to_fetch = []
    for q in questions:
        qno = q.get("questionNo")
        if not qno or qno in cache:
            continue
        if q.get("files") and len(q["files"]) > 0:
            to_fetch.append((qno, q["files"][0]))

    if not to_fetch:
        logger.info("All PDFs already in text cache.")
        return cache

    logger.info(f"Extracting text from {len(to_fetch)} new PDFs...")
    
    def fetch_pdf(item):
        qno, url = item
        try:
            resp = requests.get(url, timeout=15, headers=HEADERS)
            if resp.status_code == 200:
                doc = pymupdf.open(stream=resp.content, filetype="pdf")
                text = ""
                for page in doc:
                    text += page.get_text()
                doc.close()
                return qno, text
        except Exception as e:
            logger.debug(f"Failed to fetch PDF for {qno}: {e}")
        return qno, None

    # Fetch concurrently to save time
    with ThreadPoolExecutor(max_workers=5) as executor:
        for qno, text in executor.map(fetch_pdf, to_fetch):
            if text:
                cache[qno] = text

    # Save cache
    with open(PDF_TEXT_CACHE, "w") as f:
        json.dump(cache, f, ensure_ascii=False)
        
    return cache


# ── Step 3: AI-parse for fund data ─────────────────
def parse_with_ai(questions, pdf_texts):
    """Use Gemini to extract structured fund data from PDF texts.
    Falls back to title parsing if AI is not available.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or not HAS_GENAI:
        logger.warning("No Gemini API key or SDK found. Using title-based extraction only.")
        return extract_from_titles(questions)

    logger.info(f"Using Gemini AI to parse {len(questions)} PDF answers...")

    # Load AI cache so we don't re-parse same questions
    ai_cache = {}
    if os.path.exists(AI_PARSE_CACHE):
        try:
            with open(AI_PARSE_CACHE, "r") as f:
                ai_cache = json.load(f)
        except Exception:
            pass

    client = genai.Client(api_key=api_key)
    results = []

    for i, q in enumerate(questions):
        qno = q.get("questionNo")
        
        # Check cache
        if qno in ai_cache:
            item = ai_cache[qno]
            # Ensure basic fields exist
            item["date"] = q["date"]
            item["questionNo"] = q["questionNo"]
            item["ministry"] = q.get("ministry")
            results.append(item)
            continue

        text = pdf_texts.get(qno)
        if not text:
            logger.debug(f"No PDF text for Q{qno}, falling back to title")
            fallback = extract_from_titles([q])[0]
            ai_cache[qno] = fallback
            results.append(fallback)
            continue

        prompt = f"""You are a financial data extractor analyzing an Indian Parliamentary Question and its official answer.
Extract fund allocation and utilization data precisely.

Return ONLY ONE valid JSON object with these exact keys (use null if not found):
- scheme_name: Full official name of the central government scheme being discussed (null if no specific scheme)
- financial_year: The FY referenced, e.g. "2024-25" (null if not stated)
- allocation_cr: Budget allocated/sanctioned in ₹ Crore as a number. Convert from lakhs (÷100) if stated in lakhs. null if not found.
- utilization_cr: Amount utilized/spent/released/disbursed so far in ₹ Crore as a number. null if not found.
- utilization_pct: Percentage of allocation utilized if explicitly stated as a %, else null.
- as_of_date: Date up to which utilization figure is valid, e.g. "2025-12-31". null if not stated.
- be_cr: Budget Estimate (BE) in ₹ Crore if separately mentioned. null otherwise.
- re_cr: Revised Estimate (RE) in ₹ Crore if mentioned. null otherwise.
- state: State name if the data is state-specific, else "India".
- tags: Array of applicable tags from: ["utilization", "unspent", "allocation", "release", "delay", "budget", "general"].
  Rules: include "unspent" if funds were unused/lapsed/returned; "utilization" if utilization % or amount is discussed;
  "allocation" if allocation/sanction amounts are the focus; "release" if fund release/disbursement is discussed;
  "delay" if delay in release or implementation is mentioned; "budget" if BE/RE/actuals are compared.
- context: One of "utilization" | "allocation" | "expenditure" | "budget" | "fund" | "release" | "general"

Rules:
- All monetary values must be plain numbers in Crores (no ₹ symbol, no commas).
- If the answer mentions multiple schemes, extract data for the most prominently discussed one.
- Do not guess or infer values not explicitly stated in the text.

Parliamentary Q&A Text:
{text[:8000]}
"""
        
        try:
            resp = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=genai.types.GenerateContentConfig(temperature=0.1)
            )
            content = resp.text
            
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                parsed["date"] = q["date"]
                parsed["questionNo"] = qno
                parsed["original_title"] = q["title"]
                parsed["ministry"] = q.get("ministry")
                
                ai_cache[qno] = parsed
                results.append(parsed)
            else:
                logger.warning(f"No JSON found in response for Q{qno}")
                fallback = extract_from_titles([q])[0]
                ai_cache[qno] = fallback
                results.append(fallback)
                
        except Exception as e:
            logger.error(f"AI parsing failed for Q{qno}: {e}")
            fallback = extract_from_titles([q])[0]
            ai_cache[qno] = fallback
            results.append(fallback)

        time.sleep(0.5)  # Rate limit
        
        # Save cache every 10 updates
        if i > 0 and i % 10 == 0:
            with open(AI_PARSE_CACHE, "w") as f:
                json.dump(ai_cache, f, ensure_ascii=False)

    # Final cache save
    with open(AI_PARSE_CACHE, "w") as f:
        json.dump(ai_cache, f, ensure_ascii=False)

    return results


def extract_from_titles(questions):
    """Fallback: extract data from titles using regex patterns."""
    results = []
    for q in questions:
        title = q["title"]
        result = {
            "scheme_name": None,
            "ministry": q.get("ministry", None),
            "context": None,
            "financial_year": None,
            "date": q.get("date", ""),
            "questionNo": q.get("questionNo", ""),
            "questionType": q.get("questionType", ""),
            "original_title": title,
        }

        # Detect context
        title_lower = title.lower()
        if "utiliz" in title_lower or "utilis" in title_lower:
            result["context"] = "utilization"
        elif "alloc" in title_lower:
            result["context"] = "allocation"
        elif "expenditure" in title_lower:
            result["context"] = "expenditure"
        elif "budget" in title_lower:
            result["context"] = "budget"
        elif "fund" in title_lower:
            result["context"] = "fund"

        # Detect FY
        fy_match = re.search(r'20\d{2}-\d{2}', title)
        if fy_match:
            result["financial_year"] = fy_match.group()

        results.append(result)

    return results


# ── Step 4: Build fund_intel.json ───────────────────
def build_fund_intel(parsed_data, raw_questions):
    """Build the final fund_intel.json from parsed Q&A data."""

    # Aggregate by ministry and scheme
    ministry_data = {}
    for item in parsed_data:
        ministry = item.get("ministry") or "Unknown"
        scheme = item.get("scheme_name") or "General"

        if ministry not in ministry_data:
            ministry_data[ministry] = {
                "ministry": ministry,
                "total_questions": 0,
                "schemes": {},
                "questions": [],
            }

        ministry_data[ministry]["total_questions"] += 1
        ministry_data[ministry]["questions"].append({
            "title": item.get("original_title", ""),
            "date": item.get("date", ""),
            "context": item.get("context"),
            "financial_year": item.get("financial_year"),
            "questionNo": item.get("questionNo"),
            "scheme_name": item.get("scheme_name"),
            "allocation_cr": item.get("allocation_cr"),
            "utilization_cr": item.get("utilization_cr"),
            "utilization_pct": item.get("utilization_pct"),
            "as_of_date": item.get("as_of_date"),
            "be_cr": item.get("be_cr"),
            "re_cr": item.get("re_cr"),
            "state": item.get("state"),
            "tags": item.get("tags", []),
        })

        if scheme != "General" and scheme:
            if scheme not in ministry_data[ministry]["schemes"]:
                ministry_data[ministry]["schemes"][scheme] = {
                    "question_count": 0,
                    "contexts": [],
                }
            ministry_data[ministry]["schemes"][scheme]["question_count"] += 1
            if item.get("context"):
                ministry_data[ministry]["schemes"][scheme]["contexts"].append(item["context"])

    # Also merge with existing schemes data for allocation numbers
    schemes_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "schemes.json")
    existing_schemes = {}
    if os.path.exists(schemes_path):
        with open(schemes_path) as f:
            for s in json.load(f):
                existing_schemes[s["Scheme"]] = s

    # Enrich each ministry with tag_counts and severity_score
    TAG_WEIGHTS = {"unspent": 3, "delay": 2, "utilization": 1, "allocation": 1, "release": 1, "budget": 1, "general": 0}
    for m in ministry_data.values():
        tag_counts = {}
        for q in m["questions"]:
            for tag in (q.get("tags") or []):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        m["tag_counts"] = tag_counts
        # Severity = weighted sum of tags, normalised to 0–100
        raw_score = sum(TAG_WEIGHTS.get(t, 0) * cnt for t, cnt in tag_counts.items())
        m["severity_score"] = min(100, round(raw_score / max(m["total_questions"], 1) * 25))

    # Build final structure
    fund_intel = {
        "metadata": {
            "source": "ePARLib (sansad.in) Parliamentary Q&A",
            "financial_year": "2025-26",
            "lok_sabha": 18,
            "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "enriched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_fund_questions": len(parsed_data),
        },
        "ministries": list(ministry_data.values()),
        "existing_allocations": [
            {
                "scheme": name,
                "ministry": data.get("Ministry"),
                "allocation": data.get("Budget_Alloc"),
                "status": data.get("Budget_Status"),
            }
            for name, data in existing_schemes.items()
            if data.get("Budget_Alloc") and data["Budget_Alloc"] != "Check Dept"
        ],
    }

    return fund_intel


# ── Main ────────────────────────────────────────────
def main():
    logger.info("=" * 60)
    logger.info("Parliamentary Fund Intelligence Scraper")
    logger.info(f"Target: FY 2025-26 ({FY_START} to {FY_END})")
    logger.info("=" * 60)

    # 1. Discover sessions
    sessions = get_sessions_in_range()

    # 2. Scrape fund-related questions
    questions = scrape_fund_questions(sessions)

    if not questions:
        logger.warning("No fund-related questions found. Trying broader search...")
        # Try without session filter
        params = {
            "collectionId": 3,
            "loksabhaNo": 18,
            "start": 0,
            "rows": 5000,
            "order": "desc",
        }
        resp = requests.get(EPARLIB_BASE, params=params, headers=HEADERS, timeout=60)
        if resp.status_code == 200:
            data = resp.json()
            for rec in data.get("records", []):
                title = (rec.get("title") or "").lower()
                if any(kw in title for kw in FUND_KEYWORDS):
                    questions.append({
                        "title": rec.get("title", ""),
                        "date": rec.get("date", ""),
                        "session": rec.get("sessionNo", ""),
                        "questionNo": rec.get("questionNo", ""),
                        "questionType": rec.get("questionType", ""),
                        "members": rec.get("members", []),
                        "files": rec.get("files", []),
                        "resourceId": rec.get("resourceId", ""),
                    })
        logger.info(f"Broad search found {len(questions)} fund-related questions")

    # Cache raw Q&A data
    os.makedirs(os.path.dirname(RAW_CACHE), exist_ok=True)
    with open(RAW_CACHE, "w") as f:
        json.dump(questions, f, indent=2, ensure_ascii=False)
    logger.info(f"Cached {len(questions)} raw Q&As to {RAW_CACHE}")

    # 3. Extract text from Answer PDFs
    pdf_texts = extract_pdf_texts(questions)
    
    # 4. AI-parse for structured data
    parsed = parse_with_ai(questions, pdf_texts)
    logger.info(f"Parsed {len(parsed)} structured records")

    # 5. Build fund_intel.json
    fund_intel = build_fund_intel(parsed, questions)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(fund_intel, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved fund intelligence to {OUTPUT_FILE}")
    logger.info(f"  Ministries: {len(fund_intel['ministries'])}")
    logger.info(f"  Total Q&As: {fund_intel['metadata']['total_fund_questions']}")
    logger.info(f"  Allocations: {len(fund_intel['existing_allocations'])}")


if __name__ == "__main__":
    main()
