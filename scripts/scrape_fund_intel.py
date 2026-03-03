"""
Parliamentary Fund Intelligence Scraper
Scrapes fund utilization Q&A from ePARLib (sansad.in) for FY 2025-26,
then uses AI to extract structured fund allocation/utilization data.

Usage:
    python scripts/scrape_fund_intel.py
"""
import os
import re
import json
import time
import requests
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
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


# ── Step 3: AI-parse Q&A titles for fund data ──────
def parse_with_ai(questions):
    """Use OpenAI/Groq to extract structured fund data from question titles.
    Since full answer PDFs need separate parsing, we start with titles
    which often contain scheme name, ministry, and fund context.
    """
    api_key = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
    api_base = "https://api.groq.com/openai/v1" if os.getenv("GROQ_API_KEY") else "https://api.openai.com/v1"
    model = "llama-3.3-70b-versatile" if os.getenv("GROQ_API_KEY") else "gpt-4o-mini"

    if not api_key:
        logger.warning("No AI API key found. Using title-based extraction only.")
        return extract_from_titles(questions)

    logger.info(f"Using AI ({model}) to parse {len(questions)} questions...")

    # Batch into groups of 20 for efficiency
    batch_size = 20
    results = []

    for i in range(0, len(questions), batch_size):
        batch = questions[i:i + batch_size]
        titles_text = "\n".join(
            f"{j+1}. [{q['date']}] {q['title']}"
            for j, q in enumerate(batch)
        )

        prompt = f"""Extract fund utilization data from these Indian Parliamentary Question titles.
For each question, extract:
- scheme_name: Name of the government scheme (if mentioned)
- ministry: Ministry responsible
- context: "allocation" or "utilization" or "expenditure" or "budget"
- financial_year: If mentioned (e.g., "2025-26")

Return ONLY valid JSON array. If a field is unknown, use null.
Questions:
{titles_text}"""

        try:
            resp = requests.post(
                f"{api_base}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "You are a data extraction assistant. Return ONLY valid JSON arrays."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0,
                    "max_tokens": 2000,
                },
                timeout=30,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]

            # Extract JSON from response
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                # Merge with original question data
                for j, item in enumerate(parsed):
                    if j < len(batch):
                        item["date"] = batch[j]["date"]
                        item["questionNo"] = batch[j]["questionNo"]
                        item["questionType"] = batch[j]["questionType"]
                        item["original_title"] = batch[j]["title"]
                results.extend(parsed)

        except Exception as e:
            logger.error(f"AI parsing failed for batch {i}: {e}")
            # Fallback to title-based extraction for this batch
            results.extend(extract_from_titles(batch))

        time.sleep(1)  # Rate limit

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

    # Build final structure
    fund_intel = {
        "metadata": {
            "source": "ePARLib (sansad.in) Parliamentary Q&A",
            "financial_year": "2025-26",
            "lok_sabha": 18,
            "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
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

    # 3. AI-parse for structured data
    parsed = parse_with_ai(questions)
    logger.info(f"Parsed {len(parsed)} structured records")

    # 4. Build fund_intel.json
    fund_intel = build_fund_intel(parsed, questions)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(fund_intel, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved fund intelligence to {OUTPUT_FILE}")
    logger.info(f"  Ministries: {len(fund_intel['ministries'])}")
    logger.info(f"  Total Q&As: {fund_intel['metadata']['total_fund_questions']}")
    logger.info(f"  Allocations: {len(fund_intel['existing_allocations'])}")


if __name__ == "__main__":
    main()
