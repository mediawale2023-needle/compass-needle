"""
jobs/global_parliament_crawler.py — Phase 4: Cross-MP Parliament Intelligence

Crawls the PRS India listing page to discover all ~543 18th Lok Sabha MPs,
then scrapes and stores each MP's parliamentary questions into a shared global
corpus — independent of Needle's tenant subscriptions.

This is the data foundation for cross-MP intelligence:
  "What has the Ministry of Education said this year about NEP?"
  → retrieves answers from 5+ different MPs' questions, with citations.

Tables managed here (all idempotent):
  global_mp_registry           — one row per discovered MP
  global_parliamentary_questions — their PQs + answers + topic tags

The global PQs are indexed into memory_chunks (tenant_id=NULL) by
jobs/brain_indexer.py::index_global_pqs(), making them retrievable
by modules/brain_retriever.py when include_cross_mp=True.

LLM auto-tagging (GPT-4o-mini):
  Each question's subject + ministry → 3-5 semantic topic tags stored in
  global_parliamentary_questions.topic_tags. Falls back to rule-based tags
  (from brain_chunker._topic_tags_from_subject) if OpenAI is unavailable.

Usage:
  # Full discovery + crawl (run once, then nightly incremental)
  python -m jobs.global_parliament_crawler --discover
  python -m jobs.global_parliament_crawler --crawl-all
  python -m jobs.global_parliament_crawler --crawl-pending --limit 50
  python -m jobs.global_parliament_crawler --tag-untagged
  python -m jobs.global_parliament_crawler --stats

  # Programmatic (called from admin API + brain_indexer)
  from jobs.global_parliament_crawler import (
      ensure_schema, discover_all_mps, crawl_mp, crawl_all_pending,
      llm_tag_batch, get_stats,
  )
"""

from __future__ import annotations

import os
import re
import sys
import json
import time
import hashlib
import logging
from datetime import date, datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import text
from sansadx_backend.db import engine

logger = logging.getLogger("needle.global_crawler")

# ── Reuse PRS constants + helpers from parliament_scraper ──────────────────────
from jobs.parliament_scraper import (
    PRS_BASE, PRS_PROFILE_URL, PRS_LISTING_URL, PRS_HEADERS,
    REQUEST_TIMEOUT, INTER_REQUEST_DELAY, MAX_LISTING_PAGES,
    scrape_prs_profile, _date_to_session, _q_num,
)
from modules.brain_chunker import _topic_tags_from_subject

# ── Config ─────────────────────────────────────────────────────────────────────
LLM_TAG_BATCH_SIZE   = 40     # subjects per GPT call
LLM_TAG_MAX_PER_RUN  = 2000   # safety cap per invocation
CRAWL_DELAY          = 1.2    # seconds between MP profile fetches
LISTING_DELAY        = 0.4    # seconds between listing page fetches


# ─────────────────────────────────────────────────────────────────────────────
# SCHEMA
# ─────────────────────────────────────────────────────────────────────────────

def ensure_schema():
    """Create global tables if they don't exist. Idempotent."""
    with engine.begin() as conn:

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS global_mp_registry (
                id              SERIAL PRIMARY KEY,
                prs_slug        VARCHAR(120) UNIQUE NOT NULL,
                mp_name         VARCHAR(200),
                party           VARCHAR(120),
                constituency    VARCHAR(200),
                state           VARCHAR(120),
                house           VARCHAR(20)  DEFAULT 'lok_sabha',
                scrape_status   VARCHAR(20)  DEFAULT 'pending',
                questions_count INTEGER      DEFAULT 0,
                last_scraped_at TIMESTAMP,
                created_at      TIMESTAMP    DEFAULT NOW()
            )
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS global_parliamentary_questions (
                id                  BIGSERIAL PRIMARY KEY,
                global_mp_id        INTEGER REFERENCES global_mp_registry(id) ON DELETE CASCADE,
                prs_slug            VARCHAR(120) NOT NULL,
                house               VARCHAR(20)  DEFAULT 'lok_sabha',
                session_name        VARCHAR(80),
                question_number     VARCHAR(40),
                question_type       VARCHAR(20),
                subject             TEXT,
                ministry            VARCHAR(200),
                question_pdf_url    TEXT,
                question_text       TEXT,
                answer_text         TEXT,
                date_asked          DATE,
                topic_tags          TEXT[],
                tags_source         VARCHAR(20),
                answer_fetched_at   TIMESTAMP,
                answer_fetch_status VARCHAR(20),
                scraped_at          TIMESTAMP DEFAULT NOW(),
                UNIQUE (prs_slug, session_name, question_number, question_type)
            )
        """))

        # Indexes for fast ministry/session/tag lookups
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_gpq_slug     ON global_parliamentary_questions (prs_slug)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_gpq_ministry ON global_parliamentary_questions (LOWER(ministry))"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_gpq_session  ON global_parliamentary_questions (session_name)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_gpq_date     ON global_parliamentary_questions (date_asked)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_gmp_status   ON global_mp_registry (scrape_status)"
        ))

    logger.info("global_mp_registry + global_parliamentary_questions schema ensured.")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — DISCOVER ALL MPs FROM PRS LISTING
# ─────────────────────────────────────────────────────────────────────────────

# Regex that matches PRS 18th Lok Sabha profile URLs so we can extract slugs
# from any link on the page regardless of CSS class structure.
_PROFILE_HREF_RE = re.compile(
    r"/mptrack/18(?:th-lok-sabha|loksabha)/([a-z0-9][a-z0-9\-]+[a-z0-9])",
    re.IGNORECASE,
)


def _parse_listing_page(html: str) -> list[dict]:
    """
    Parse one PRS MP listing page.  Returns list of:
      {prs_slug, mp_name, party, constituency, state}

    Strategy (in order):
      1. Classic div.mp-card structure (old PRS layout)
      2. Any other common card class patterns (member-card, mp_item, etc.)
      3. Fallback: extract every <a> whose href matches the profile URL pattern
         and pull name/meta from surrounding markup.

    Handles JS-rendered pages that return near-empty HTML by returning []
    and logging a clear diagnostic message.
    """
    soup = BeautifulSoup(html, "html.parser")

    # ── 0. JS-rendered guard ───────────────────────────────────────────────
    # If the response body is very short it's almost certainly a JS SPA shell.
    if len(html) < 4_000:
        logger.warning(
            "_parse_listing_page: HTML too short (%d chars) — "
            "page may require JavaScript rendering. "
            "Run scripts/diagnose_prs_listing.py locally to inspect.",
            len(html),
        )
        return []

    mps: list[dict] = []
    seen_slugs: set[str] = set()

    # ── 1. Classic card selector cascade ──────────────────────────────────
    card_selectors = [
        ("div", "mp-card"),
        ("div", "member-card"),
        ("div", "mp_card"),
        ("div", "mp-item"),
        ("div", "member-item"),
        ("article", "mp-card"),
        ("li", "mp-card"),
        ("li", "member-card"),
    ]

    cards = []
    for tag, cls in card_selectors:
        cards = soup.find_all(tag, class_=cls)
        if cards:
            logger.debug("_parse_listing_page: matched selector %s.%s → %d cards",
                         tag, cls, len(cards))
            break

    if cards:
        for card in cards:
            a = card.find("a", href=_PROFILE_HREF_RE)
            if not a:
                # Try any <a> and test href separately
                a = card.find("a")
            if not a:
                continue
            href = a.get("href", "")
            m = _PROFILE_HREF_RE.search(href)
            if not m:
                continue
            slug = m.group(1).lower()
            if slug in seen_slugs:
                continue
            seen_slugs.add(slug)

            # Name — h3 > h2 > strong > a-text
            h = a.find(["h3", "h2", "h1"]) or card.find(["h3", "h2", "h1"])
            if not h:
                h = a.find("strong") or card.find("strong")
            mp_name = h.get_text(strip=True) if h else a.get_text(strip=True)

            paras = [p.get_text(strip=True) for p in card.find_all("p")]
            party        = paras[0] if len(paras) > 0 else ""
            constituency = paras[1] if len(paras) > 1 else ""
            state        = paras[2] if len(paras) > 2 else ""

            # Sometimes party/constituency are in spans rather than paragraphs
            if not party:
                spans = [s.get_text(strip=True) for s in card.find_all("span")]
                party        = spans[0] if len(spans) > 0 else ""
                constituency = spans[1] if len(spans) > 1 else ""
                state        = spans[2] if len(spans) > 2 else ""

            mps.append({
                "prs_slug": slug,
                "mp_name":  mp_name,
                "party":    party,
                "constituency": constituency,
                "state":    state,
            })
        if mps:
            return mps

    # ── 2. Fallback: direct href extraction from ALL links ─────────────────
    # Works even when the card wrapper class has changed.  We collect every
    # unique profile-URL slug and try to infer name from surrounding text.
    logger.info(
        "_parse_listing_page: no cards matched — falling back to href extraction "
        "(HTML size %d). Run scripts/diagnose_prs_listing.py to see actual structure.",
        len(html),
    )
    for a in soup.find_all("a", href=_PROFILE_HREF_RE):
        href = a.get("href", "")
        m = _PROFILE_HREF_RE.search(href)
        if not m:
            continue
        slug = m.group(1).lower()
        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)

        # Name: try heading inside the link, then the link text itself
        h = a.find(["h3", "h2", "h1", "strong"])
        mp_name = h.get_text(strip=True) if h else a.get_text(strip=True)
        # Remove junk like "Read More" from link text
        if mp_name.lower() in ("", "read more", "view profile", "details"):
            mp_name = slug.replace("-", " ").title()

        # Look for party/constituency in the parent container
        parent = a.parent
        paras  = [p.get_text(strip=True) for p in parent.find_all("p")]
        spans  = [s.get_text(strip=True) for s in parent.find_all("span")]
        meta   = paras or spans
        party        = meta[0] if len(meta) > 0 else ""
        constituency = meta[1] if len(meta) > 1 else ""
        state        = meta[2] if len(meta) > 2 else ""

        mps.append({
            "prs_slug": slug,
            "mp_name":  mp_name,
            "party":    party,
            "constituency": constituency,
            "state":    state,
        })

    if not mps:
        # Log the first 1 KB of body so admins can diagnose manually
        body_preview = soup.get_text(separator=" ", strip=True)[:800]
        logger.warning(
            "_parse_listing_page: zero MPs extracted. "
            "Page body preview: %s …", body_preview
        )

    return mps


def seed_from_file(filepath: str) -> dict:
    """
    Seed global_mp_registry from a local JSON file when PRS scraping is
    unavailable (e.g. the site requires JS rendering).

    The file should be a JSON array of objects with at minimum a 'prs_slug' key.
    Other optional keys: mp_name, party, constituency, state.

    Create the seed file with scripts/diagnose_prs_listing.py or manually.

    Returns: {"seeded": N, "new": N}
    """
    ensure_schema()

    with open(filepath, encoding="utf-8") as f:
        rows = json.load(f)

    if not isinstance(rows, list):
        raise ValueError("Seed file must be a JSON array")

    seeded  = 0
    new_cnt = 0
    with engine.begin() as conn:
        for mp in rows:
            slug = (mp.get("prs_slug") or "").strip()
            if not slug:
                continue
            res = conn.execute(text("""
                INSERT INTO global_mp_registry
                    (prs_slug, mp_name, party, constituency, state, house)
                VALUES
                    (:prs_slug, :mp_name, :party, :constituency, :state, 'lok_sabha')
                ON CONFLICT (prs_slug) DO UPDATE SET
                    mp_name      = EXCLUDED.mp_name,
                    party        = EXCLUDED.party,
                    constituency = EXCLUDED.constituency,
                    state        = EXCLUDED.state
            """), {
                "prs_slug":     slug,
                "mp_name":      mp.get("mp_name", slug.replace("-", " ").title()),
                "party":        mp.get("party", ""),
                "constituency": mp.get("constituency", ""),
                "state":        mp.get("state", ""),
            })
            seeded += 1
            if res.rowcount == 1:
                new_cnt += 1

    logger.info("seed_from_file: %d seeded (%d new) from %s", seeded, new_cnt, filepath)
    return {"seeded": seeded, "new": new_cnt}


def discover_all_mps(force: bool = False) -> dict:
    """
    Crawl all PRS listing pages and upsert into global_mp_registry.
    Safe to re-run — existing rows are updated only if force=True or new data differs.

    Tries page=0, page=1 … MAX_LISTING_PAGES.  Stops when a page returns no MPs.

    Returns: {"discovered": N, "new": N, "pages_scanned": N,
              "hint": str}    ← hint is set if discovery fails so the caller
                                 can surface it in the admin UI.
    """
    ensure_schema()

    discovered = 0
    new_count  = 0
    pages_done = 0
    hint       = ""

    logger.info("Discovering MPs from PRS listing (max %d pages)…", MAX_LISTING_PAGES)

    # PRS sometimes paginates from page=0, sometimes from page=1.
    # Try page=0 first; if it returns MPs, use 0-based pagination.
    page_offset = 1   # default: start at page=1

    for page in range(page_offset, MAX_LISTING_PAGES + page_offset):
        url = f"{PRS_LISTING_URL}?page={page}"
        try:
            resp = requests.get(url, headers=PRS_HEADERS, timeout=REQUEST_TIMEOUT)
            if resp.status_code in (404, 410):
                logger.info("Listing page %d returned %d — stopping.", page, resp.status_code)
                break
            resp.raise_for_status()

            mps = _parse_listing_page(resp.text)

            if not mps:
                if page == page_offset and len(resp.text) > 4000:
                    # Got a real page but zero MPs on page 1 — site structure changed.
                    # Try page=0 in case pagination is 0-based.
                    url0 = f"{PRS_LISTING_URL}?page=0"
                    resp0 = requests.get(url0, headers=PRS_HEADERS, timeout=REQUEST_TIMEOUT)
                    mps0  = _parse_listing_page(resp0.text) if resp0.ok else []
                    if mps0:
                        logger.info("Listing is 0-based — switching to page=0 start.")
                        page_offset = 0
                        mps = mps0
                    else:
                        hint = (
                            "PRS listing page returned HTML but no MP cards could be parsed. "
                            "The site layout may have changed (JS rendering, new CSS class names). "
                            "Run: python scripts/diagnose_prs_listing.py  to inspect the actual "
                            "HTML structure, then update _parse_listing_page() accordingly."
                        )
                        logger.warning(hint)
                        break
                elif mps is not None:
                    logger.info("Listing page %d: no MPs found — end of listing.", page)
                    break

            pages_done += 1
            discovered += len(mps)

            with engine.begin() as conn:
                for mp in mps:
                    result = conn.execute(text("""
                        INSERT INTO global_mp_registry
                            (prs_slug, mp_name, party, constituency, state, house)
                        VALUES
                            (:prs_slug, :mp_name, :party, :constituency, :state, 'lok_sabha')
                        ON CONFLICT (prs_slug) DO UPDATE SET
                            mp_name      = EXCLUDED.mp_name,
                            party        = EXCLUDED.party,
                            constituency = EXCLUDED.constituency,
                            state        = EXCLUDED.state
                    """), mp)
                    if result.rowcount == 1:
                        new_count += 1

            logger.info("Page %d: %d MPs found (total so far: %d)",
                        page, len(mps), discovered)
            time.sleep(LISTING_DELAY)

        except Exception as e:
            logger.warning("Listing page %d error: %s", page, e)
            hint = f"Request error on page {page}: {e}"
            break

    if not hint and discovered == 0:
        hint = (
            "Zero MPs discovered. Most likely cause: the PRS listing page now "
            "requires JavaScript to render MP cards, so a plain HTTP GET returns "
            "an empty shell. "
            "Quick fix: run  python scripts/diagnose_prs_listing.py  from your "
            "local terminal, paste the output, and the parser will be updated."
        )
        logger.warning(hint)

    logger.info("Discovery complete: %d MPs across %d pages (%d new)",
                discovered, pages_done, new_count)
    return {
        "discovered":   discovered,
        "new":          new_count,
        "pages_scanned": pages_done,
        "hint":         hint,
    }


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — CRAWL ONE MP
# ─────────────────────────────────────────────────────────────────────────────

def _upsert_global_questions(global_mp_id: int, prs_slug: str,
                             records: list) -> int:
    """Upsert PQ records into global_parliamentary_questions."""
    if not records:
        return 0
    inserted = 0
    with engine.begin() as conn:
        for r in records:
            res = conn.execute(text("""
                INSERT INTO global_parliamentary_questions
                    (global_mp_id, prs_slug, house, session_name, question_number,
                     question_type, subject, ministry, question_pdf_url,
                     question_text, answer_text, date_asked,
                     topic_tags, tags_source, scraped_at)
                VALUES
                    (:global_mp_id, :prs_slug, :house, :session_name, :question_number,
                     :question_type, :subject, :ministry, :question_pdf_url,
                     :question_text, :answer_text, :date_asked,
                     :topic_tags, :tags_source, NOW())
                ON CONFLICT (prs_slug, session_name, question_number, question_type)
                DO UPDATE SET
                    subject          = EXCLUDED.subject,
                    ministry         = EXCLUDED.ministry,
                    question_pdf_url = COALESCE(EXCLUDED.question_pdf_url,
                                               global_parliamentary_questions.question_pdf_url)
            """), r)
            inserted += res.rowcount
    return inserted


def crawl_mp(prs_slug: str, global_mp_id: Optional[int] = None,
             skip_if_done: bool = True) -> dict:
    """
    Scrape one MP's PQs from PRS India and store in global_parliamentary_questions.

    Args:
        prs_slug:      PRS profile slug, e.g. "supriya-sule"
        global_mp_id:  DB id from global_mp_registry (resolved if None)
        skip_if_done:  skip MPs whose scrape_status is already 'done'

    Returns summary dict.
    """
    ensure_schema()

    # Resolve global_mp_id if not provided
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id, scrape_status FROM global_mp_registry WHERE prs_slug = :s"),
            {"s": prs_slug},
        ).mappings().fetchone()

    if not row:
        logger.warning("crawl_mp: %s not in global_mp_registry — run discover first", prs_slug)
        return {"error": f"{prs_slug} not in registry"}

    global_mp_id   = global_mp_id or row["id"]
    scrape_status  = row["scrape_status"]

    if skip_if_done and scrape_status == "done":
        logger.debug("crawl_mp: %s already done, skipping", prs_slug)
        return {"skipped": True, "prs_slug": prs_slug}

    # Mark as running
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE global_mp_registry
            SET scrape_status = 'running'
            WHERE id = :id
        """), {"id": global_mp_id})

    try:
        data = scrape_prs_profile(prs_slug)
    except Exception as e:
        logger.error("crawl_mp: PRS fetch failed for %s: %s", prs_slug, e)
        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE global_mp_registry
                SET scrape_status = 'failed', last_scraped_at = NOW()
                WHERE id = :id
            """), {"id": global_mp_id})
        return {"prs_slug": prs_slug, "error": str(e)}

    # Build records
    q_records = []
    for q in data.get("questions", []):
        d = q.get("date")
        _, sname = _date_to_session(d)
        qnum = _q_num(q.get("date_str", ""), q.get("title", ""), q.get("question_type", ""))
        subject  = q.get("title", "")
        ministry = q.get("ministry", "")
        tags = _topic_tags_from_subject(f"{subject} {ministry}")

        q_records.append({
            "global_mp_id":     global_mp_id,
            "prs_slug":         prs_slug,
            "house":            "lok_sabha",
            "session_name":     sname,
            "question_number":  qnum,
            "question_type":    (q.get("question_type") or "").lower(),
            "subject":          subject,
            "ministry":         ministry,
            "question_pdf_url": q.get("pdf_url") or None,
            "question_text":    "",
            "answer_text":      "",
            "date_asked":       d,
            "topic_tags":       tags,
            "tags_source":      "rule",
        })

    inserted = _upsert_global_questions(global_mp_id, prs_slug, q_records)

    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE global_mp_registry
            SET scrape_status   = 'done',
                questions_count = :cnt,
                last_scraped_at = NOW()
            WHERE id = :id
        """), {"id": global_mp_id, "cnt": inserted})

    logger.info("crawl_mp(%s): %d questions inserted", prs_slug, inserted)

    # Trigger incremental scheme extraction + staleness marking for new PQs
    if inserted > 0:
        try:
            from jobs.extract_prs_schemes import run_extraction
            run_extraction(full=False)
        except Exception as _se:
            logger.warning("Post-crawl scheme extraction failed (non-fatal): %s", _se)

    return {"prs_slug": prs_slug, "questions_inserted": inserted}


def crawl_all_pending(limit: Optional[int] = None,
                      include_failed: bool = False) -> dict:
    """
    Crawl all MPs whose scrape_status is 'pending' (or 'failed' if include_failed).
    Rate-limited politely. Designed for nightly cron.

    Returns: {"crawled": N, "inserted_total": N, "errors": [...]}
    """
    ensure_schema()

    statuses = ["pending"]
    if include_failed:
        statuses.append("failed")

    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT id, prs_slug FROM global_mp_registry
            WHERE scrape_status = ANY(:statuses)
            ORDER BY id
            LIMIT :lim
        """), {"statuses": statuses, "lim": limit or 10000}).mappings().all()

    if not rows:
        logger.info("crawl_all_pending: nothing to crawl.")
        return {"crawled": 0, "inserted_total": 0, "errors": []}

    logger.info("crawl_all_pending: %d MPs to crawl", len(rows))

    crawled  = 0
    inserted = 0
    errors   = []

    for i, row in enumerate(rows):
        result = crawl_mp(row["prs_slug"], global_mp_id=row["id"], skip_if_done=True)
        if result.get("error"):
            errors.append({"prs_slug": row["prs_slug"], "error": result["error"]})
        elif not result.get("skipped"):
            crawled  += 1
            inserted += result.get("questions_inserted", 0)
            logger.info("[%d/%d] %s → %d Qs", i + 1, len(rows),
                        row["prs_slug"], result.get("questions_inserted", 0))

        time.sleep(CRAWL_DELAY)

    logger.info("crawl_all_pending done: %d crawled, %d Qs inserted, %d errors",
                crawled, inserted, len(errors))
    return {"crawled": crawled, "inserted_total": inserted, "errors": errors}


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — LLM AUTO-TAGGING (GPT-4o-mini)
# ─────────────────────────────────────────────────────────────────────────────

_TAG_SYSTEM = """\
You receive a JSON array of parliamentary questions. Each has an "id", "subject", and "ministry".
Return a JSON array with exactly the same ids and a "tags" key containing 3-6 lowercase topic tags.
Tags should be specific and useful for retrieval — e.g. "drinking_water", "northeast_india",
"jal_jeevan_mission", "farmer_subsidy", "nep_implementation", "coastal_erosion".
Prefer specific over generic. Never use tags like "india", "parliament", "ministry".
Output ONLY valid JSON — no markdown, no explanation."""

_TAG_USER = "Questions:\n{batch_json}\n\nReturn tagged JSON array."


def _openai_tag_batch(subjects: list[dict]) -> Optional[list[dict]]:
    """
    Call GPT-4o-mini to tag a batch of {id, subject, ministry} dicts.
    Returns list of {id, tags} or None on failure.
    Retries once on rate-limit (429) with a 20-second back-off.
    """
    try:
        from openai import OpenAI, RateLimitError
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            return None
        client = OpenAI(api_key=key, timeout=60.0)
        batch_json = json.dumps(subjects, ensure_ascii=False)

        def _call():
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": _TAG_SYSTEM},
                    {"role": "user",   "content": _TAG_USER.format(batch_json=batch_json)},
                ],
                temperature=0,
                response_format={"type": "json_object"},
                max_tokens=800,
            )
            return resp.choices[0].message.content or ""

        try:
            raw = _call()
        except RateLimitError:
            logger.info("LLM tag: rate limited — waiting 20s before retry")
            time.sleep(20)
            raw = _call()

        # Model may return {"questions": [...]} or just [...]
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return parsed
        for key_try in ("questions", "items", "results", "data"):
            if key_try in parsed and isinstance(parsed[key_try], list):
                return parsed[key_try]
        if "id" in parsed and "tags" in parsed:
            return [parsed]
        return None
    except Exception as e:
        logger.warning("LLM tag batch failed: %s", e)
        return None


def llm_tag_batch(limit: int = LLM_TAG_MAX_PER_RUN,
                  _progress: Optional[dict] = None) -> dict:
    """
    Find global PQs with tags_source='rule' or no tags and re-tag with GPT-4o-mini.
    Writes updated tags back to global_parliamentary_questions.
    Falls back gracefully to rule-based tags when OpenAI is unavailable.

    Returns: {"tagged": N, "batches": N, "skipped": N}
    """
    ensure_schema()

    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT id, subject, ministry
            FROM global_parliamentary_questions
            WHERE (tags_source IS NULL OR tags_source = 'rule')
              AND subject IS NOT NULL AND subject != ''
            ORDER BY id
            LIMIT :lim
        """), {"lim": limit}).mappings().all()

    if not rows:
        return {"tagged": 0, "batches": 0, "skipped": 0}

    logger.info("llm_tag_batch: %d questions to tag", len(rows))

    if _progress is not None:
        _progress["total"] = len(rows)
        _progress["done"]  = 0
        _progress["label"] = "tagging"

    tagged_count  = 0
    batch_count   = 0
    skip_count    = 0

    for batch_start in range(0, len(rows), LLM_TAG_BATCH_SIZE):
        batch = list(rows[batch_start: batch_start + LLM_TAG_BATCH_SIZE])
        subjects = [
            {"id": r["id"],
             "subject": (r["subject"] or "")[:200],
             "ministry": (r["ministry"] or "")[:80]}
            for r in batch
        ]

        tagged = _openai_tag_batch(subjects)

        if tagged:
            batch_count += 1
            id_to_tags = {}
            for item in tagged:
                if isinstance(item, dict) and "id" in item and "tags" in item:
                    id_to_tags[item["id"]] = item["tags"]

            with engine.begin() as conn:
                for item_id, tags in id_to_tags.items():
                    if isinstance(tags, list) and tags:
                        conn.execute(text("""
                            UPDATE global_parliamentary_questions
                            SET topic_tags = :tags, tags_source = 'llm'
                            WHERE id = :id
                        """), {"id": item_id, "tags": tags})
                        tagged_count += 1
        else:
            skip_count += len(batch)
            logger.debug("llm_tag_batch: batch %d skipped (OpenAI unavailable)",
                         batch_start // LLM_TAG_BATCH_SIZE + 1)

        if _progress is not None:
            _progress["done"] = min(batch_start + LLM_TAG_BATCH_SIZE, len(rows))

        time.sleep(1.5)   # respect OpenAI RPM limits (60 req/min → ~1s min)

    logger.info("llm_tag_batch: %d tagged, %d batches, %d skipped",
                tagged_count, batch_count, skip_count)
    return {"tagged": tagged_count, "batches": batch_count, "skipped": skip_count}


# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — FETCH ANSWERS FOR GLOBAL PQs
# Reuses parliament_answer_fetcher's prs_pdf_cache so PDFs already fetched
# for any tenant are served from cache — no duplicate downloads.
# ─────────────────────────────────────────────────────────────────────────────

# Common English + parliamentary stopwords stripped before matching
_STOPWORDS = frozenset(
    "a an the and or of in on at to by for is are was were be been being "
    "with from that this has have had will would could should may might "
    "their its it he she we they do does did not no per cent whether "
    "state please kindly furnished details particulars information "
    "government india minister ministry hon ble shri smt dr prof km "
    "also any all year years since till date thereof regard regarding".split()
)

_RE_NORM = re.compile(r"[^a-z0-9 ]+")


def _stem(w: str) -> str:
    """Very light stemming to equate plural/verb forms (railways→railway)."""
    if len(w) <= 4:
        return w
    for suffix in ("ations", "tion", "ment", "ness", "ings", "ing", "ers", "ies"):
        if w.endswith(suffix) and len(w) - len(suffix) >= 3:
            return w[: -len(suffix)]
    if w.endswith("s") and len(w) > 4:
        return w[:-1]
    return w


def _key_words(s: str) -> frozenset[str]:
    """Normalise → strip stopwords → stem → return word set."""
    s = _RE_NORM.sub(" ", (s or "").lower())
    return frozenset(
        _stem(w) for w in s.split()
        if len(w) > 2 and w not in _STOPWORDS
    )


def _coverage(db_words: frozenset, text: str) -> float:
    """
    What fraction of DB subject words appear anywhere in `text` (after stemming)?

    This is the primary matching signal for global PQs because:
      • DB subject  = short PRS profile title  e.g. "Water Supply in Rural Areas"
      • PDF text    = full question block, which always contains the subject
                      heading verbatim plus the question body

    Example:
      db_words  = {water, suppl, rural, area}        (stemmed)
      text      = "WATER SUPPLY IN RURAL AREAS\nWill the Minister..."
      text_words = {water, suppl, rural, area, will, minister, ...}
      coverage  = 4/4 = 1.0  ✓
    """
    if not db_words or not text:
        return 0.0
    text_words = _key_words(text)
    hits = sum(1 for w in db_words if w in text_words)
    return hits / len(db_words)


def _match_global_qas(
    parsed_qas: list[dict],
    db_rows: list[dict],
    min_coverage: float = 0.30,   # ≥30% of DB subject words must appear in Q text
) -> dict:
    """
    Match PDF-extracted Q&A blocks to global_parliamentary_questions rows.

    Root cause of previous no_match: _guess_subject() in prs_answer_extractor
    returns "Will the Minister of X be pleased to state..." rather than the
    actual subject heading ("WATER SUPPLY IN RURAL AREAS"), so subject-to-subject
    similarity is near-zero even for perfectly matching records.

    Fix: match DB subject words against the FULL question_text of each parsed
    block. The actual subject heading is always present in question_text verbatim,
    so word-coverage is near 1.0 for matching records.

    Strategy:
      1. Single-row group → auto-assign best-coverage block (avoids needing
         exact subject match when only one row needs filling)
      2. Multi-row groups → assign each row to best-coverage block ≥ min_coverage

    Returns: { db_row_id: {"parsed_qa": {...}, "score": float, "match_basis": str} }
    """
    if not parsed_qas or not db_rows:
        return {}

    matches: dict = {}

    # Pre-compute stemmed DB subject words and full-text corpus per parsed block
    # Use question_text (full body) — subject heading is always in it
    qa_full_texts = [
        (qa.get("question_text") or "") + " " + (qa.get("subject") or "")
        for qa in parsed_qas
    ]

    # ── 1. Single-row group: assign best coverage block unconditionally ────────
    if len(db_rows) == 1:
        row    = db_rows[0]
        db_w   = _key_words(row.get("subject") or "")
        best_i = 0
        best_s = 0.0
        for i, full_text in enumerate(qa_full_texts):
            cov = _coverage(db_w, full_text) if db_w else 0.5
            if cov > best_s:
                best_s = cov
                best_i = i
        matches[row["id"]] = {
            "parsed_qa":   parsed_qas[best_i],
            "score":       round(best_s, 3),
            "match_basis": "single_row_best_coverage",
        }
        return matches

    # ── 2. Multi-row group: question-number first, then subject coverage ─────────
    # Pre-extract question numbers from parsed QAs for fast lookup
    qa_numbers = []
    for qa in parsed_qas:
        raw = (qa.get("question_number") or qa.get("subject") or "")
        # extract leading digits e.g. "1234", "Q.1234", "*1234"
        import re as _re
        m = _re.search(r'\b(\d{1,5})\b', str(raw))
        qa_numbers.append(m.group(1) if m else None)

    for row in db_rows:
        db_qnum = str(row.get("question_number") or "").strip().lstrip("*").lstrip("†")
        db_w    = _key_words(row.get("subject") or "")

        # Priority 1: exact question-number match
        num_idx = -1
        if db_qnum:
            for i, qn in enumerate(qa_numbers):
                if qn and qn == db_qnum:
                    num_idx = i
                    break

        if num_idx >= 0:
            matches[row["id"]] = {
                "parsed_qa":   parsed_qas[num_idx],
                "score":       1.0,
                "match_basis": "question_number",
            }
            continue

        # Priority 2: subject-word coverage
        if not db_w:
            # No subject to match on — assign highest-scoring block
            best_i = max(range(len(qa_full_texts)),
                         key=lambda i: len(_key_words(qa_full_texts[i])),
                         default=0)
            matches[row["id"]] = {
                "parsed_qa":   parsed_qas[best_i],
                "score":       0.3,
                "match_basis": "no_subject_fallback",
            }
            continue

        best_idx   = -1
        best_score = -1.0

        for i, full_text in enumerate(qa_full_texts):
            cov = _coverage(db_w, full_text)
            if cov > best_score:
                best_score = cov
                best_idx   = i

        if best_idx >= 0 and best_score >= min_coverage:
            matches[row["id"]] = {
                "parsed_qa":   parsed_qas[best_idx],
                "score":       round(best_score, 3),
                "match_basis": "text_coverage",
            }

    return matches


def _apply_global_matches(matches: dict) -> int:
    """
    Write matched question_text + answer_text back to global_parliamentary_questions.
    `matches` = {db_row_id: {parsed_qa, score, match_basis}}
    Returns count of rows updated.
    """
    if not matches:
        return 0
    updated = 0
    with engine.begin() as conn:
        for row_id, m in matches.items():
            pqa    = m.get("parsed_qa") or {}
            q_text = (pqa.get("question_text") or "").strip()
            a_text = (pqa.get("answer_text")   or "").strip()
            status = "ok" if a_text else "no_answer_in_pdf"
            conn.execute(text("""
                UPDATE global_parliamentary_questions
                   SET question_text       = COALESCE(NULLIF(:qt, ''), question_text),
                       answer_text         = COALESCE(NULLIF(:at, ''), answer_text),
                       answer_fetched_at   = NOW(),
                       answer_fetch_status = :status
                 WHERE id = :id
            """), {"qt": q_text, "at": a_text, "status": status, "id": row_id})
            updated += 1
    return updated


def _mark_global_rows_status(row_ids: list[int], status: str):
    if not row_ids:
        return
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE global_parliamentary_questions
               SET answer_fetched_at   = NOW(),
                   answer_fetch_status = :s
             WHERE id = ANY(:ids)
        """), {"s": status, "ids": row_ids})


def fetch_global_answers(
    limit:       int = 500,
    prs_slug:    Optional[str] = None,
    allow_ocr:   bool = False,
    force:       bool = False,
    max_pdfs:    Optional[int] = None,
    _progress:   Optional[dict] = None,
) -> dict:
    """
    Backfill answer_text for global_parliamentary_questions rows that have a
    question_pdf_url but no answer yet.

    Uses the shared prs_pdf_cache (from parliament_answer_fetcher) so any
    PDF already downloaded for a per-tenant MP is served from cache instantly —
    no re-downloading.

    Args:
        limit:     Max DB rows to consider per run (default 500)
        prs_slug:  Restrict to one MP's questions (for targeted backfill)
        allow_ocr: Enable Gemini Vision OCR for scanned/Hindi-font PDFs
        force:     Ignore PDF cache and re-download everything
        max_pdfs:  Hard cap on unique PDFs fetched in this run

    Returns:
        {rows_considered, unique_pdfs, pdfs_processed, pdfs_from_cache,
         pdfs_failed, rows_updated, rows_unmatched}
    """
    ensure_schema()

    # Import cache-aware fetcher from parliament_answer_fetcher
    try:
        from jobs.parliament_answer_fetcher import (
            get_or_fetch_pdf,
            ensure_schema as _ensure_paf_schema,
        )
        _ensure_paf_schema()   # make sure prs_pdf_cache table exists
    except ImportError as e:
        return {"error": f"parliament_answer_fetcher not available: {e}"}

    from collections import defaultdict

    # Do NOT auto-reset no_match rows here — rows that consistently fail the
    # subject-coverage threshold would loop infinitely (PDF cached-ok → reset →
    # re-queue → fail match → no_match → repeat). Re-matching should be triggered
    # explicitly via the /brain/global-rematch endpoint after matcher improvements.

    # Build WHERE clause
    where_parts = [
        "question_pdf_url IS NOT NULL",
        "question_pdf_url != ''",
        "(answer_text IS NULL OR answer_text = '')",
        "(answer_fetch_status IS NULL OR answer_fetch_status NOT IN ('ok', 'failed', 'no_pdf', 'no_parse', 'no_answer_in_pdf'))",
    ]
    params: dict = {"lim": limit}
    if prs_slug:
        where_parts.append("prs_slug = :slug")
        params["slug"] = prs_slug

    with engine.connect() as conn:
        rows = conn.execute(text(f"""
            SELECT id, prs_slug, subject, ministry,
                   question_number, question_type,
                   session_name, date_asked, question_pdf_url
              FROM global_parliamentary_questions
             WHERE {' AND '.join(where_parts)}
             ORDER BY date_asked DESC NULLS LAST
             LIMIT :lim
        """), params).mappings().all()

    rows = [dict(r) for r in rows]
    if not rows:
        logger.info("fetch_global_answers: nothing to fetch (all answers present)")
        return {
            "rows_considered": 0, "unique_pdfs": 0,
            "pdfs_processed": 0, "pdfs_from_cache": 0,
            "pdfs_failed": 0, "rows_updated": 0, "rows_unmatched": 0,
        }

    # Group by PDF URL — one PDF covers multiple questions on the same session day
    by_url: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        url = (r["question_pdf_url"] or "").strip()
        if url:
            by_url[url].append(r)

    unique_urls = list(by_url.keys())
    if max_pdfs:
        unique_urls = unique_urls[:max_pdfs]

    logger.info(
        "fetch_global_answers: %d rows across %d unique PDFs (cap=%s, ocr=%s)",
        len(rows), len(unique_urls), max_pdfs, allow_ocr,
    )

    if _progress is not None:
        _progress["total"] = len(unique_urls)
        _progress["done"]  = 0
        _progress["label"] = "fetching PDFs"

    pdfs_processed  = 0
    pdfs_from_cache = 0
    pdfs_failed     = 0
    rows_updated    = 0
    rows_unmatched  = 0

    for i, url in enumerate(unique_urls, start=1):
        group_rows = by_url[url]
        row_ids    = [r["id"] for r in group_rows]

        try:
            result = get_or_fetch_pdf(url, allow_ocr=allow_ocr, force=force)
        except Exception as e:
            logger.warning("fetch_global_answers: PDF %s error: %s", url, e)
            pdfs_failed += 1
            _mark_global_rows_status(row_ids, "failed")
            continue

        if result.get("status") != "ok":
            pdfs_failed += 1
            status = "no_pdf" if (result.get("error") == "download_failed") else "failed"
            _mark_global_rows_status(row_ids, status)
            continue

        if not result.get("parsed_qas"):
            # PDF was downloaded and parsed but had no question headers.
            # Mark as no_parse so we don't retry endlessly.
            pdfs_failed += 1
            _mark_global_rows_status(row_ids, "no_parse")
            continue

        if result.get("cached"):
            pdfs_from_cache += 1
        else:
            pdfs_processed  += 1

        matches = _match_global_qas(result["parsed_qas"], group_rows)
        if matches:
            rows_updated += _apply_global_matches(matches)

        unmatched_ids = [rid for rid in row_ids if rid not in matches]
        rows_unmatched += len(unmatched_ids)
        _mark_global_rows_status(unmatched_ids, "no_match")

        if _progress is not None:
            _progress["done"] = i

        if i % 10 == 0 or i == len(unique_urls):
            logger.info(
                "  … %d/%d PDFs (%d cached), %d rows updated, %d unmatched",
                i, len(unique_urls), pdfs_from_cache, rows_updated, rows_unmatched,
            )

    summary = {
        "rows_considered":  len(rows),
        "unique_pdfs":      len(unique_urls),
        "pdfs_processed":   pdfs_processed,
        "pdfs_from_cache":  pdfs_from_cache,
        "pdfs_failed":      pdfs_failed,
        "rows_updated":     rows_updated,
        "rows_unmatched":   rows_unmatched,
    }
    logger.info("fetch_global_answers done: %s", summary)
    return summary


def get_answer_coverage() -> dict:
    """Quick coverage stats for global_parliamentary_questions."""
    ensure_schema()
    with engine.connect() as conn:
        r = conn.execute(text("""
            SELECT
                COUNT(*)                                                    AS total,
                COUNT(*) FILTER (WHERE answer_text IS NOT NULL AND answer_text != '')
                                                                           AS with_answers,
                COUNT(*) FILTER (WHERE question_pdf_url IS NOT NULL AND question_pdf_url != '')
                                                                           AS with_pdf_url,
                COUNT(*) FILTER (WHERE answer_fetch_status IN ('ok','ok_raw')) AS fetch_ok,
                COUNT(*) FILTER (WHERE answer_fetch_status = 'no_match')   AS no_match,
                COUNT(*) FILTER (WHERE answer_fetch_status = 'failed')     AS failed,
                COUNT(*) FILTER (WHERE answer_fetch_status = 'no_pdf')     AS no_pdf,
                COUNT(*) FILTER (WHERE answer_fetch_status = 'no_parse')   AS no_parse,
                COUNT(*) FILTER (WHERE answer_fetch_status IS NULL)        AS pending
              FROM global_parliamentary_questions
        """)).mappings().fetchone()
    row = dict(r) if r else {}
    total    = int(row.get("total") or 0)
    with_ans = int(row.get("with_answers") or 0)
    return {
        **{k: int(v or 0) for k, v in row.items()},
        "pct_covered": round(with_ans / total * 100, 1) if total else 0.0,
    }


# ─────────────────────────────────────────────────────────────────────────────
# STATS
# ─────────────────────────────────────────────────────────────────────────────

def get_stats() -> dict:
    """Return a summary of the global corpus."""
    ensure_schema()
    with engine.connect() as conn:
        reg = conn.execute(text("""
            SELECT
                COUNT(*)                                       AS total_mps,
                COUNT(*) FILTER (WHERE scrape_status='done')   AS done,
                COUNT(*) FILTER (WHERE scrape_status='pending') AS pending,
                COUNT(*) FILTER (WHERE scrape_status='failed')  AS failed,
                COUNT(*) FILTER (WHERE scrape_status='running') AS running
            FROM global_mp_registry
        """)).mappings().fetchone()

        pqs = conn.execute(text("""
            SELECT
                COUNT(*)                                          AS total_questions,
                COUNT(*) FILTER (WHERE answer_text != '' AND answer_text IS NOT NULL)
                                                                  AS with_answers,
                COUNT(*) FILTER (WHERE tags_source = 'llm')       AS llm_tagged,
                COUNT(*) FILTER (WHERE tags_source = 'rule')      AS rule_tagged,
                COUNT(DISTINCT ministry)                           AS ministries,
                MIN(date_asked)                                    AS earliest,
                MAX(date_asked)                                    AS latest
            FROM global_parliamentary_questions
        """)).mappings().fetchone()

    return {
        "registry": dict(reg) if reg else {},
        "questions": dict(pqs) if pqs else {},
    }


def get_ministry_breakdown(limit: int = 30) -> list[dict]:
    """Top ministries by question count in the global corpus."""
    ensure_schema()
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT ministry, COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE answer_text != '' AND answer_text IS NOT NULL) AS with_answers
            FROM global_parliamentary_questions
            WHERE ministry IS NOT NULL AND ministry != ''
            GROUP BY ministry
            ORDER BY total DESC
            LIMIT :lim
        """), {"lim": limit}).mappings().all()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    import argparse
    ap = argparse.ArgumentParser(description="Needle Global Parliament Crawler (Phase 4)")
    ap.add_argument("--discover",      action="store_true",
                    help="Discover all ~543 MPs from PRS listing and upsert into global_mp_registry")
    ap.add_argument("--crawl-all",     action="store_true",
                    help="Crawl all pending MPs (full run)")
    ap.add_argument("--crawl-pending", action="store_true",
                    help="Crawl pending/failed MPs up to --limit")
    ap.add_argument("--crawl-mp",      metavar="SLUG",
                    help="Crawl a single MP by prs_slug")
    ap.add_argument("--tag-untagged",  action="store_true",
                    help="LLM-tag questions that only have rule-based tags")
    ap.add_argument("--fetch-answers", action="store_true",
                    help="Fetch Ministry answers for global PQs with PDF URLs")
    ap.add_argument("--fetch-slug",    metavar="SLUG",
                    help="Fetch answers only for this prs_slug")
    ap.add_argument("--stats",         action="store_true",
                    help="Print global corpus stats")
    ap.add_argument("--limit",         type=int, default=100,
                    help="Max MPs/questions to process (default 100)")
    ap.add_argument("--include-failed", action="store_true",
                    help="Re-attempt previously failed MPs")
    args = ap.parse_args()

    if args.stats:
        import pprint
        pprint.pprint(get_stats())
        pprint.pprint({"top_ministries": get_ministry_breakdown(15)})

    elif args.discover:
        result = discover_all_mps()
        print(json.dumps(result, indent=2))

    elif args.crawl_all:
        result = crawl_all_pending(limit=None, include_failed=args.include_failed)
        print(json.dumps(result, default=str, indent=2))

    elif args.crawl_pending:
        result = crawl_all_pending(limit=args.limit, include_failed=args.include_failed)
        print(json.dumps(result, default=str, indent=2))

    elif args.crawl_mp:
        result = crawl_mp(args.crawl_mp, skip_if_done=False)
        print(json.dumps(result, default=str, indent=2))

    elif args.tag_untagged:
        result = llm_tag_batch(limit=args.limit)
        print(json.dumps(result, indent=2))

    elif args.fetch_answers:
        result = fetch_global_answers(limit=args.limit, prs_slug=args.fetch_slug)
        print(json.dumps(result, default=str, indent=2))

    else:
        ap.print_help()
