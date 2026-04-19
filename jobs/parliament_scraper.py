"""
jobs/parliament_scraper.py — Parliamentary data scraper (18th Lok Sabha)
                              Sourced from PRS India (prsindia.org)

Fetches the MP's full parliamentary track record from PRS India's MP Tracker.
PRS India serves all questions, debates, and attendance on a single HTML page
per MP — no API authentication, no session-by-session iteration needed.

Profile URL: https://prsindia.org/mptrack/18th-lok-sabha/{prs_slug}

Identity mapping (no numeric ID required):
  PRS uses name-based URL slugs (e.g. "atul-garg", "supriya-sule").
  Resolution order:
    1. Return stored tenants.prs_profile_slug if already set.
    2. Derive slug from mp_name (lowercase, hyphenated) → verify URL exists.
    3. Fall back to scanning PRS listing pages with fuzzy name+constituency match.
  Resolved slug is persisted in tenants.prs_profile_slug.

Data extracted per MP:
  Questions : date, title, type (starred/unstarred), ministry, PDF URL
  Debates   : date, title, debate type (Special Mention / Zero Hour / etc.)
  Zero Hour : split out from debates where debate_type == "Zero Hour"
  PMBs      : PRS shows count only — no record-level data; table left at 0

One HTTP request per MP fetches all sessions at once; date-to-session mapping
assigns each record to the correct 18th Lok Sabha session name.

Usage:
  from jobs.parliament_scraper import backfill_tenant, sync_all_active_tenants
  backfill_tenant(tenant_id=5)
  sync_all_active_tenants()

  # CLI
  python -m jobs.parliament_scraper --backfill-tenant 5
  python -m jobs.parliament_scraper --backfill-all
  python -m jobs.parliament_scraper --sync-all
"""

import os
import sys
import time
import hashlib
import logging
from datetime import datetime, date
from typing import Optional

import requests
from bs4 import BeautifulSoup
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import text
from sansadx_backend.db import SessionLocal, Tenant, TenantProfile, engine

logger = logging.getLogger("needle.parliament.scraper")


# ─────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────

PRS_BASE        = "https://prsindia.org"
PRS_PROFILE_URL = f"{PRS_BASE}/mptrack/18th-lok-sabha"
PRS_LISTING_URL = f"{PRS_BASE}/mptrack/18loksabha"

PRS_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer":         f"{PRS_BASE}/mptrack/",
}

REQUEST_TIMEOUT     = 20    # seconds per request
INTER_REQUEST_DELAY = 1.0   # polite crawl delay between requests
MAX_LISTING_PAGES   = 65    # ~543 MPs / 9 per page

# Honorifics to strip before deriving PRS slug
_HONORIFICS = {
    "shri", "smt", "dr", "adv", "prof", "mr", "mrs", "ms",
    "col", "capt", "lt", "maj", "brig", "ji", "kumar", "kumari",
}

# 18th Lok Sabha session date ranges — used to assign session_name to each record
LOK_SABHA_18_SESSIONS = [
    (1, "1st Session 2024",      date(2024, 6, 24),  date(2024, 7, 3)),
    (2, "Monsoon Session 2024",  date(2024, 7, 22),  date(2024, 8, 9)),
    (3, "Winter Session 2024",   date(2024, 11, 25), date(2024, 12, 20)),
    (4, "Budget Session 2025",   date(2025, 1, 31),  date(2025, 5, 4)),
    (5, "Monsoon Session 2025",  date(2025, 7, 21),  date(2025, 8, 22)),
    (6, "Winter Session 2025",   date(2025, 11, 24), date(2025, 12, 19)),
    (7, "Budget Session 2026",   date(2026, 1, 31),  date(2026, 5, 31)),  # approximate
]


# ─────────────────────────────────────────
# SESSION DATE MAPPER
# ─────────────────────────────────────────

def _date_to_session(d: Optional[date]) -> tuple[int, str]:
    """
    Map a date to the corresponding 18th Lok Sabha session.
    Returns (session_num, session_name).
    Records between sessions are assigned to the nearest past session.
    """
    if not d:
        return (0, "Unknown Session")
    for snum, sname, sstart, send in LOK_SABHA_18_SESSIONS:
        if sstart <= d <= send:
            return (snum, sname)
    # Between sessions — assign to nearest preceding session
    for snum, sname, sstart, send in reversed(LOK_SABHA_18_SESSIONS):
        if d >= sstart:
            return (snum, sname)
    return (LOK_SABHA_18_SESSIONS[0][0], LOK_SABHA_18_SESSIONS[0][1])


# ─────────────────────────────────────────
# PRS SLUG RESOLUTION
# ─────────────────────────────────────────

def derive_prs_slug(name: str) -> str:
    """
    Derive a candidate PRS India profile slug from an MP name.
    PRS slugs are lowercase, all name parts joined with hyphens, honorifics removed.
      "Dr. Atul Garg"   → "atul-garg"
      "Supriya Sule"    → "supriya-sule"
      "Atul Kumar Singh" → "atul-kumar-singh"
    """
    words = name.lower().replace(".", " ").replace(",", " ").split()
    words = [w for w in words if w not in _HONORIFICS and len(w) > 1]
    return "-".join(words)


def verify_prs_slug(slug: str) -> bool:
    """Return True if the PRS profile page exists and has content for this slug."""
    url = f"{PRS_PROFILE_URL}/{slug}"
    try:
        resp = requests.get(
            url, headers=PRS_HEADERS,
            timeout=REQUEST_TIMEOUT, allow_redirects=True,
        )
        # Page must return 200 and contain actual MP data (>3 KB)
        return resp.status_code == 200 and len(resp.text) > 3000
    except Exception as e:
        logger.debug("verify_prs_slug(%s) error: %s", slug, e)
        return False


def find_prs_slug_from_listing(mp_name: str, constituency: str) -> Optional[str]:
    """
    Scan PRS listing pages to find the profile slug for an MP by fuzzy
    name + constituency matching.  Scores: 40% name + 60% constituency.
    Returns the best slug if score ≥ 70, else None.
    """
    def _norm(s: str) -> str:
        return s.lower().strip()

    mp_name_norm  = _norm(mp_name)
    const_norm    = _norm(constituency)
    best_slug     = None
    best_score    = 0.0

    for page in range(1, MAX_LISTING_PAGES + 1):
        url = f"{PRS_LISTING_URL}?page={page}"
        try:
            resp = requests.get(url, headers=PRS_HEADERS, timeout=REQUEST_TIMEOUT)
            if resp.status_code != 200:
                logger.debug("PRS listing page %d returned %d — stopping", page, resp.status_code)
                break

            soup  = BeautifulSoup(resp.text, "html.parser")
            cards = soup.find_all("div", class_="mp-card")
            if not cards:
                logger.debug("PRS listing page %d: no cards found — stopping", page)
                break

            for card in cards:
                a = card.find("a")
                if not a:
                    continue
                href  = a.get("href", "")
                slug  = href.rstrip("/").split("/")[-1]
                h3    = a.find("h3") or a.find("h2") or a.find("strong")
                if not h3:
                    continue
                card_name  = _norm(h3.get_text())
                paras      = card.find_all("p")
                card_const = _norm(paras[1].get_text()) if len(paras) > 1 else ""

                name_score  = SequenceMatcher(None, card_name, mp_name_norm).ratio() * 100
                const_score = SequenceMatcher(None, card_const, const_norm).ratio() * 100
                score       = 0.4 * name_score + 0.6 * const_score

                if score > best_score:
                    best_score = score
                    best_slug  = slug
                    if best_score >= 90:
                        logger.info(
                            "PRS listing scan: fast exit at page %d, slug=%s (score=%.1f)",
                            page, slug, score,
                        )
                        return best_slug

        except Exception as e:
            logger.warning("PRS listing page %d error: %s", page, e)
            break

        time.sleep(0.3)

    if best_score >= 70 and best_slug:
        logger.info("PRS listing scan: best slug=%s (score=%.1f)", best_slug, best_score)
        return best_slug

    logger.warning(
        "PRS listing scan: no match above 70 for '%s' / '%s' (best=%.1f)",
        mp_name, constituency, best_score,
    )
    return None


def _save_prs_slug(tenant_id: int, slug: str):
    """Persist prs_profile_slug to the tenants table."""
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE tenants SET prs_profile_slug = :slug WHERE id = :tid"),
            {"slug": slug, "tid": tenant_id},
        )


def resolve_prs_slug(tenant_id: int) -> Optional[str]:
    """
    Resolve and persist the PRS India profile slug for a tenant.
      1. Return stored prs_profile_slug if already set.
      2. Derive slug from mp_name → verify URL → save on success.
      3. Fall back to listing-page scan.
    Returns the slug string on success, None on failure.
    """
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            return None

        if tenant.prs_profile_slug:
            return tenant.prs_profile_slug

        profile      = db.query(TenantProfile).filter(TenantProfile.tenant_id == tenant_id).first()
        mp_name      = (profile.mp_name if profile else None) or tenant.name or ""
        constituency = (profile.constituency if profile else None) or tenant.constituency or ""
    finally:
        db.close()

    if not mp_name:
        logger.warning("resolve_prs_slug: tenant %d has no mp_name", tenant_id)
        return None

    # Step 1: derived slug
    candidate = derive_prs_slug(mp_name)
    logger.info("Trying derived PRS slug: %s (mp_name=%s)", candidate, mp_name)
    if verify_prs_slug(candidate):
        _save_prs_slug(tenant_id, candidate)
        logger.info("Tenant %d PRS slug confirmed: %s", tenant_id, candidate)
        return candidate

    time.sleep(INTER_REQUEST_DELAY)

    # Step 2: listing scan
    logger.info("Derived slug failed — scanning PRS listing for '%s' / '%s'", mp_name, constituency)
    found = find_prs_slug_from_listing(mp_name, constituency)
    if found:
        _save_prs_slug(tenant_id, found)
        logger.info("Tenant %d PRS slug (from listing): %s", tenant_id, found)
        return found

    logger.warning(
        "Could not resolve PRS slug for tenant %d (%s / %s)", tenant_id, mp_name, constituency
    )
    return None


# ─────────────────────────────────────────
# DATE PARSER
# ─────────────────────────────────────────

def _parse_date(val: str) -> Optional[date]:
    """Parse DD.MM.YYYY (PRS default) or ISO / other common formats."""
    if not val:
        return None
    val = str(val).strip()
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            continue
    return None


# ─────────────────────────────────────────
# QUESTION NUMBER — STABLE HASH
# ─────────────────────────────────────────

def _q_num(date_str: str, title: str, q_type: str) -> str:
    """
    Generate a stable 10-char hex 'question number' from date + title + type.
    PRS does not expose question numbers, so we use a deterministic hash for
    deduplication against the UNIQUE(tenant_id, session_name, question_number, question_type)
    constraint.
    """
    key = f"{date_str}:{title.lower()[:80]}:{q_type.lower()[:20]}"
    return hashlib.md5(key.encode()).hexdigest()[:10]


# ─────────────────────────────────────────
# HTML SECTION FINDER
# ─────────────────────────────────────────

def _find_section_table(soup: BeautifulSoup, keywords: list) -> Optional[object]:
    """
    Return the first <table> that immediately follows a heading whose text
    contains any of the given keywords (case-insensitive).
    Searches h1-h5, p, strong, b tags for the heading.
    """
    seen = set()
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "p", "strong", "b"]):
        text_lower = tag.get_text(strip=True).lower()
        if not any(kw in text_lower for kw in keywords):
            continue
        # Find the next <table> in the document after this heading
        tbl = tag.find_next_sibling("table") or tag.find_next("table")
        if tbl and id(tbl) not in seen:
            seen.add(id(tbl))
            return tbl
    return None


# ─────────────────────────────────────────
# TABLE PARSERS
# ─────────────────────────────────────────

def _parse_question_table(table) -> list:
    """
    Parse the PRS questions table.
    Columns: Date | Title (linked to PDF) | Type | Ministry
    """
    rows = []
    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 2:
            continue  # header or empty row

        date_str = tds[0].get_text(strip=True)
        d = _parse_date(date_str)
        if not d:
            continue  # skip non-data rows

        a       = tds[1].find("a")
        title   = (a.get_text(strip=True) if a else tds[1].get_text(strip=True))[:500]
        pdf_url = (a.get("href", "") if a else "")
        if pdf_url and not pdf_url.startswith("http"):
            pdf_url = PRS_BASE + pdf_url

        q_type   = tds[2].get_text(strip=True) if len(tds) > 2 else "Unstarred"
        ministry = tds[3].get_text(strip=True) if len(tds) > 3 else ""

        rows.append({
            "date":          d,
            "date_str":      date_str,
            "title":         title.strip(),
            "question_type": q_type.strip(),
            "ministry":      ministry.strip()[:200],
            "pdf_url":       pdf_url if pdf_url.startswith("http") else "",
        })
    return rows


def _parse_debate_table(table) -> list:
    """
    Parse the PRS debates table.
    Columns: Date | Title (linked to PDF or /mptrack/debatenotfound) | Debate Type
    """
    rows = []
    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 2:
            continue

        date_str = tds[0].get_text(strip=True)
        d = _parse_date(date_str)
        if not d:
            continue

        a    = tds[1].find("a")
        title   = (a.get_text(strip=True) if a else tds[1].get_text(strip=True))[:500]
        href    = a.get("href", "") if a else ""
        pdf_url = ""
        if href and "debatenotfound" not in href:
            pdf_url = href if href.startswith("http") else (PRS_BASE + href)

        debate_type = tds[2].get_text(strip=True) if len(tds) > 2 else "Debate"

        rows.append({
            "date":        d,
            "date_str":    date_str,
            "title":       title.strip(),
            "debate_type": debate_type.strip()[:100],
            "pdf_url":     pdf_url[:500],
        })
    return rows


# ─────────────────────────────────────────
# PRS PROFILE FETCHER
# ─────────────────────────────────────────

def scrape_prs_profile(prs_slug: str) -> dict:
    """
    Fetch and parse https://prsindia.org/mptrack/18th-lok-sabha/{prs_slug}.
    Returns {"questions": [...], "debates": [...]}
    Raises requests.HTTPError on non-200 response.
    """
    url  = f"{PRS_PROFILE_URL}/{prs_slug}"
    resp = requests.get(url, headers=PRS_HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # Use specific phrases from PRS section headings to avoid matching the
    # summary stat h4 elements ("No. of Questions", "No. of Debates") that
    # appear earlier in the page and would redirect to the wrong table.
    questions_table = _find_section_table(soup, ["questions details", "questions asked"])
    debates_table   = _find_section_table(soup, ["participated in", "debates ("])

    questions = _parse_question_table(questions_table) if questions_table else []
    debates   = _parse_debate_table(debates_table)     if debates_table   else []

    logger.info("PRS %s: %d questions, %d debates parsed", prs_slug, len(questions), len(debates))
    return {"questions": questions, "debates": debates}


# ─────────────────────────────────────────
# DB WRITERS
# ─────────────────────────────────────────

def _upsert_questions(records: list) -> int:
    if not records:
        return 0
    inserted = 0
    with engine.begin() as conn:
        for r in records:
            result = conn.execute(text("""
                INSERT INTO parliamentary_questions
                    (tenant_id, house, session_name, session_number, question_number,
                     question_type, subject, ministry, question_text, answer_text,
                     question_pdf_url,
                     date_asked, scraped_at)
                VALUES
                    (:tenant_id, :house, :session_name, :session_number, :question_number,
                     :question_type, :subject, :ministry, :question_text, :answer_text,
                     :question_pdf_url,
                     :date_asked, NOW())
                ON CONFLICT ON CONSTRAINT uq_pq_tenant_session_number_type
                DO UPDATE SET
                    question_pdf_url = COALESCE(EXCLUDED.question_pdf_url, parliamentary_questions.question_pdf_url)
            """), r)
            inserted += result.rowcount
    return inserted


def _upsert_debates(records: list) -> int:
    if not records:
        return 0
    inserted = 0
    with engine.begin() as conn:
        for r in records:
            result = conn.execute(text("""
                INSERT INTO parliamentary_debates
                    (tenant_id, house, session_name, date, topic,
                     bill_reference, speech_excerpt, full_speech_url, scraped_at)
                VALUES
                    (:tenant_id, :house, :session_name, :date, :topic,
                     :bill_reference, :speech_excerpt, :full_speech_url, NOW())
                ON CONFLICT ON CONSTRAINT uq_pd_tenant_session_date_topic
                DO NOTHING
            """), r)
            inserted += result.rowcount
    return inserted


def _upsert_zero_hour(records: list) -> int:
    if not records:
        return 0
    inserted = 0
    with engine.begin() as conn:
        for r in records:
            result = conn.execute(text("""
                INSERT INTO zero_hour_submissions
                    (tenant_id, house, session_name, date, subject,
                     text_excerpt, scraped_at)
                VALUES
                    (:tenant_id, :house, :session_name, :date, :subject,
                     :text_excerpt, NOW())
                ON CONFLICT ON CONSTRAINT uq_zh_tenant_session_date_subject
                DO NOTHING
            """), r)
            inserted += result.rowcount
    return inserted


# ─────────────────────────────────────────
# BACKFILL JOB TRACKER
# ─────────────────────────────────────────

def _mark_job(tenant_id: int, session_name: str, data_type: str, status: str,
              records: int = 0, error: str = None):
    """Upsert a backfill job progress record."""
    now = datetime.utcnow()
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO parliament_backfill_jobs
                (tenant_id, session_name, data_type, status, records_fetched,
                 error_message, started_at, completed_at, created_at)
            VALUES
                (:tid, :sname, :dtype, :status, :recs,
                 :err, :started, :completed, NOW())
            ON CONFLICT ON CONSTRAINT uq_pbj_tenant_session_type
            DO UPDATE SET
                status          = EXCLUDED.status,
                records_fetched = parliament_backfill_jobs.records_fetched + EXCLUDED.records_fetched,
                error_message   = EXCLUDED.error_message,
                started_at      = COALESCE(parliament_backfill_jobs.started_at, EXCLUDED.started_at),
                completed_at    = EXCLUDED.completed_at
        """), {
            "tid":       tenant_id,
            "sname":     session_name,
            "dtype":     data_type,
            "status":    status,
            "recs":      records,
            "err":       error,
            "started":   now if status == "running"              else None,
            "completed": now if status in ("done", "error")      else None,
        })


def _mark_all_sessions(tenant_id: int, data_type: str,
                       status: str, counts: dict = None):
    """Mark all 18th LS sessions for a given data_type."""
    counts = counts or {}
    for _, sname, _, _ in LOK_SABHA_18_SESSIONS:
        _mark_job(tenant_id, sname, data_type, status,
                  records=counts.get(sname, 0))


# ─────────────────────────────────────────
# CORE SCRAPE FOR ONE TENANT
# ─────────────────────────────────────────

def scrape_tenant(tenant_id: int, prs_slug: str,
                  since_date: Optional[date] = None) -> dict:
    """
    Fetch and store all parliamentary data for one tenant from PRS India.

    Args:
        tenant_id:  DB tenant id
        prs_slug:   PRS India profile slug (e.g. "atul-garg")
        since_date: If set, skip records older than this date (incremental sync).

    Returns summary: {
        "questions_inserted": N, "debates_inserted": N, "zero_hour_inserted": N
    }
    """
    # Mark all session/type combos as running
    for dt in ("questions", "debates", "pmbs", "zero_hour"):
        _mark_all_sessions(tenant_id, dt, "running")

    try:
        data = scrape_prs_profile(prs_slug)
    except Exception as e:
        err_msg = str(e)
        logger.error("PRS fetch failed for slug=%s tenant=%d: %s", prs_slug, tenant_id, err_msg)
        for dt in ("questions", "debates", "pmbs", "zero_hour"):
            _mark_all_sessions(tenant_id, dt, "error",
                               counts={s[1]: 0 for s in LOK_SABHA_18_SESSIONS})
        return {"questions_inserted": 0, "debates_inserted": 0, "zero_hour_inserted": 0,
                "error": err_msg}

    # ── Build question records ─────────────────────────────────────
    q_records    = []
    q_by_session = {}
    for q in data["questions"]:
        d = q["date"]
        if since_date and d < since_date:
            continue
        snum, sname = _date_to_session(d)
        q_by_session[sname] = q_by_session.get(sname, 0) + 1
        q_records.append({
            "tenant_id":       tenant_id,
            "house":           "lok_sabha",
            "session_name":    sname,
            "session_number":  str(snum),
            "question_number": _q_num(q["date_str"], q["title"], q["question_type"]),
            "question_type":   q["question_type"].lower(),
            "subject":         q["title"],
            "ministry":        q["ministry"],
            # Phase 1 Brain: PDF URL goes into its own column. The actual
            # question_text / answer_text are populated later by the
            # jobs/parliament_answer_fetcher.py worker.
            "question_pdf_url": q.get("pdf_url", ""),
            "question_text":   "",
            "answer_text":     "",
            "date_asked":      d,
        })

    # ── Split debates into regular debates vs zero-hour ───────────
    deb_records = []
    zh_records  = []
    deb_by_session = {}
    zh_by_session  = {}

    for deb in data["debates"]:
        d = deb["date"]
        if since_date and d < since_date:
            continue
        snum, sname = _date_to_session(d)
        dtype = deb["debate_type"].lower()

        if "zero hour" in dtype or "zero-hour" in dtype:
            zh_by_session[sname] = zh_by_session.get(sname, 0) + 1
            zh_records.append({
                "tenant_id":    tenant_id,
                "house":        "lok_sabha",
                "session_name": sname,
                "date":         d,
                "subject":      deb["title"],
                "text_excerpt": "",
            })
        else:
            deb_by_session[sname] = deb_by_session.get(sname, 0) + 1
            deb_records.append({
                "tenant_id":      tenant_id,
                "house":          "lok_sabha",
                "session_name":   sname,
                "date":           d,
                "topic":          deb["title"],
                "bill_reference": deb["debate_type"],   # e.g. "Special Mention"
                "speech_excerpt": "",
                "full_speech_url": deb.get("pdf_url") or None,
            })

    # ── Upsert ────────────────────────────────────────────────────
    q_ins  = _upsert_questions(q_records)
    d_ins  = _upsert_debates(deb_records)
    zh_ins = _upsert_zero_hour(zh_records)

    # ── Mark jobs done ────────────────────────────────────────────
    _mark_all_sessions(tenant_id, "questions", "done", q_by_session)
    _mark_all_sessions(tenant_id, "debates",   "done", deb_by_session)
    _mark_all_sessions(tenant_id, "zero_hour", "done", zh_by_session)
    _mark_all_sessions(tenant_id, "pmbs",      "done", {})  # PRS: count only

    logger.info(
        "scrape_tenant(%d, %s): %d questions, %d debates, %d zero-hour inserted",
        tenant_id, prs_slug, q_ins, d_ins, zh_ins,
    )
    return {
        "questions_inserted": q_ins,
        "debates_inserted":   d_ins,
        "zero_hour_inserted": zh_ins,
    }


# ─────────────────────────────────────────
# BACKFILL — ONE TENANT
# ─────────────────────────────────────────

def backfill_tenant(tenant_id: int, data_types: list = None,
                    sessions: list = None) -> dict:
    """
    Run the full historical backfill for one tenant from PRS India.

    data_types and sessions args are accepted for API compatibility but
    ignored — PRS delivers all data types and all sessions in one page fetch.

    Returns a summary dict.
    """
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            return {"error": f"Tenant {tenant_id} not found"}
        if tenant.parliament_sync_status not in ("active", "auto_matched"):
            return {
                "error": (
                    f"Tenant {tenant_id} sync status is '{tenant.parliament_sync_status}' "
                    "— confirm MP identity first via the Parliament Sync screen."
                )
            }
        prs_slug = tenant.prs_profile_slug
    finally:
        db.close()

    # Resolve PRS slug if not yet set
    if not prs_slug:
        logger.info("Tenant %d: no prs_profile_slug — resolving now …", tenant_id)
        prs_slug = resolve_prs_slug(tenant_id)
        if not prs_slug:
            return {
                "error": (
                    f"Could not resolve PRS India profile for tenant {tenant_id}. "
                    "The MP name may not exactly match PRS records. "
                    "Set prs_profile_slug manually via the admin parliament sync screen."
                )
            }

    logger.info("Starting backfill: tenant=%d prs_slug=%s", tenant_id, prs_slug)
    result = scrape_tenant(tenant_id, prs_slug)

    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE tenants
            SET parliament_last_synced = NOW(),
                parliament_sync_status = 'active'
            WHERE id = :tid
        """), {"tid": tenant_id})

    logger.info("Backfill complete for tenant %d: %s", tenant_id, result)
    return result


# ─────────────────────────────────────────
# INCREMENTAL SYNC — ALL ACTIVE TENANTS
# ─────────────────────────────────────────

def sync_all_active_tenants(data_types: list = None) -> dict:
    """
    Incremental sync: fetch PRS data for all active tenants and insert
    only records newer than their parliament_last_synced timestamp.
    Called by the session monitor cron during active Lok Sabha sessions.
    """
    db = SessionLocal()
    try:
        tenants = db.query(Tenant).filter(
            Tenant.parliament_sync_enabled == True,
            Tenant.prs_profile_slug.isnot(None),
            Tenant.parliament_sync_status == "active",
            Tenant.is_active == True,
        ).all()
        tenant_list = [
            (t.id, t.prs_profile_slug, t.parliament_last_synced)
            for t in tenants
        ]
    finally:
        db.close()

    if not tenant_list:
        logger.info("No active tenants with PRS profile slug — nothing to sync")
        return {}

    results = {}
    logger.info("Incremental sync: %d tenants", len(tenant_list))

    for tenant_id, prs_slug, last_synced in tenant_list:
        since = last_synced.date() if last_synced else None
        logger.info("Syncing tenant=%d prs_slug=%s since=%s", tenant_id, prs_slug, since)
        result = scrape_tenant(tenant_id, prs_slug, since_date=since)

        with engine.begin() as conn:
            conn.execute(
                text("UPDATE tenants SET parliament_last_synced = NOW() WHERE id = :tid"),
                {"tid": tenant_id},
            )

        results[tenant_id] = result
        time.sleep(INTER_REQUEST_DELAY)

    return results


# ─────────────────────────────────────────
# BATCH BACKFILL — ALL CONFIRMED TENANTS
# ─────────────────────────────────────────

def backfill_all_confirmed_tenants() -> dict:
    """
    Run full backfill for every confirmed tenant that hasn't been fully backfilled.
    Called from the admin "Run Backfill for All" button.
    """
    db = SessionLocal()
    try:
        tenants = db.query(Tenant).filter(
            Tenant.parliament_sync_status == "active",
            Tenant.is_active == True,
        ).all()
        ids = [t.id for t in tenants]
    finally:
        db.close()

    # Filter to tenants that need backfill (fewer done jobs than expected)
    expected_done = len(LOK_SABHA_18_SESSIONS) * 4   # 7 sessions × 4 types
    to_backfill = []
    for tid in ids:
        with engine.connect() as conn:
            row = conn.execute(text("""
                SELECT COUNT(*) AS cnt FROM parliament_backfill_jobs
                WHERE tenant_id = :tid AND status = 'done'
            """), {"tid": tid}).mappings().fetchone()
        done_count = row["cnt"] if row else 0
        if done_count < expected_done:
            to_backfill.append(tid)

    logger.info(
        "Batch backfill: %d tenants need work (out of %d confirmed)",
        len(to_backfill), len(ids),
    )

    results = {}
    for i, tid in enumerate(to_backfill):
        logger.info("Backfilling tenant %d (%d/%d)…", tid, i + 1, len(to_backfill))
        results[tid] = backfill_tenant(tid)
        if i < len(to_backfill) - 1:
            time.sleep(2.0)

    return results


# ─────────────────────────────────────────
# CLI RUNNER
# ─────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    import argparse
    parser = argparse.ArgumentParser(description="Needle Parliament Scraper (PRS India)")
    parser.add_argument("--backfill-tenant", type=int, metavar="TENANT_ID",
                        help="Run full backfill for one tenant")
    parser.add_argument("--backfill-all", action="store_true",
                        help="Backfill all confirmed tenants that are not yet fully filled")
    parser.add_argument("--sync-all", action="store_true",
                        help="Incremental sync (records since last_synced) for all active tenants")
    parser.add_argument("--resolve-slug", type=int, metavar="TENANT_ID",
                        help="Resolve and save PRS profile slug for one tenant (no scrape)")
    args = parser.parse_args()

    if args.resolve_slug:
        slug = resolve_prs_slug(args.resolve_slug)
        print(f"Resolved: {slug}" if slug else "Could not resolve PRS slug.")

    elif args.backfill_tenant:
        result = backfill_tenant(args.backfill_tenant)
        print(result)

    elif args.backfill_all:
        result = backfill_all_confirmed_tenants()
        print(result)

    elif args.sync_all:
        result = sync_all_active_tenants()
        print(result)

    else:
        parser.print_help()
