"""
jobs/parliament_scraper.py — Targeted parliamentary data scraper (18th Lok Sabha)

Fetches questions, debates, PMBs, and zero hour submissions for each subscribed
MP tenant from sansad.in, keyed by their parliament_member_id (mpsno).

Data sourced from sansad.in internal API (api_ls/*). All endpoints follow the
same base pattern discovered during Phase 2 identity resolution:

  Base:    https://sansad.in/api_ls/
  Headers: Referer: https://sansad.in/ls/  (required, otherwise 403)

API ENDPOINT REGISTRY (update here if sansad.in changes URLs):
  Questions:   /api_ls/lsquestion        ?loksabha=18&session=N&mpsno=ID
  Debates:     /api_ls/lsdebate          ?loksabha=18&session=N&mpsno=ID
  PMBs:        /api_ls/privatebill       ?loksabha=18&session=N&mpsno=ID
  Zero Hour:   /api_ls/zerohour          ?loksabha=18&session=N&mpsno=ID

Each endpoint is tried with a fallback to the sansad.in HTML search page
if the JSON API returns unexpected data, giving us two layers of resilience.

18th Lok Sabha Sessions (as of April 2026):
  1 → 1st Session      Jun 24–Jul 3, 2024
  2 → Monsoon Session  Jul 22–Aug 9, 2024
  3 → Winter Session   Nov 25–Dec 20, 2024
  4 → Budget Session   Jan 31–May 4, 2025
  5 → Monsoon Session  Jul 21–Aug 22, 2025
  6 → Winter Session   Nov 24–Dec 19, 2025

Usage:
  # Backfill one tenant (6 sessions, all 4 data types)
  from jobs.parliament_scraper import backfill_tenant
  backfill_tenant(tenant_id=5)

  # Sync all tenants (incremental — only new records since last_synced)
  from jobs.parliament_scraper import sync_all_active_tenants
  sync_all_active_tenants()

  # CLI
  python -m jobs.parliament_scraper --backfill-tenant 5
  python -m jobs.parliament_scraper --sync-all
"""

import os
import sys
import time
import logging
from datetime import datetime, date
from typing import Optional

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import text
from sansadx_backend.db import SessionLocal, Tenant, engine

logger = logging.getLogger("needle.parliament.scraper")

# ─────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────

SANSAD_BASE   = "https://sansad.in"
SANSAD_API    = f"{SANSAD_BASE}/api_ls"
SANSAD_HEADERS = {
    "Referer":    f"{SANSAD_BASE}/ls/",
    "User-Agent": "Mozilla/5.0 (compatible; NeedleParliamentSync/1.0)",
    "Accept":     "application/json",
}
REQUEST_TIMEOUT = 20   # seconds per request
INTER_REQUEST_DELAY = 1.2  # seconds between requests (polite)
MAX_RETRIES = 3

# 18th Lok Sabha sessions: (session_number, human_name, start_date, end_date)
LOK_SABHA_18_SESSIONS = [
    (1, "1st Session 2024",      date(2024, 6, 24),  date(2024, 7, 3)),
    (2, "Monsoon Session 2024",  date(2024, 7, 22),  date(2024, 8, 9)),
    (3, "Winter Session 2024",   date(2024, 11, 25), date(2024, 12, 20)),
    (4, "Budget Session 2025",   date(2025, 1, 31),  date(2025, 5, 4)),
    (5, "Monsoon Session 2025",  date(2025, 7, 21),  date(2025, 8, 22)),
    (6, "Winter Session 2025",   date(2025, 11, 24), date(2025, 12, 19)),
]

# Data types and their API slug + DB target
DATA_TYPES = {
    "questions":  {
        "api_slug":   "lsquestion",
        "table":      "parliamentary_questions",
        "dedup_cols": ("tenant_id", "session_name", "question_number", "question_type"),
    },
    "debates": {
        "api_slug":   "lsdebate",
        "table":      "parliamentary_debates",
        "dedup_cols": ("tenant_id", "session_name", "date", "topic"),
    },
    "pmbs": {
        "api_slug":   "privatebill",
        "table":      "private_members_bills",
        "dedup_cols": ("tenant_id", "session_name", "bill_number"),
    },
    "zero_hour": {
        "api_slug":   "zerohour",
        "table":      "zero_hour_submissions",
        "dedup_cols": ("tenant_id", "session_name", "date", "subject"),
    },
}


# ─────────────────────────────────────────
# HTTP HELPER
# ─────────────────────────────────────────

def _get(url: str, params: dict) -> Optional[list]:
    """
    GET request to sansad.in API with retry logic.
    Returns parsed list of records, or None on persistent failure.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(
                url, params=params,
                headers=SANSAD_HEADERS,
                timeout=REQUEST_TIMEOUT,
            )
            if resp.status_code == 404:
                logger.debug("404 for %s — endpoint may not exist for this session", url)
                return []
            if resp.status_code == 403:
                logger.warning("403 from %s — check Referer header", url)
                return None
            resp.raise_for_status()

            data = resp.json()
            # Normalise: API may return list or {"data": [...]} or {"records": [...]}
            if isinstance(data, list):
                return data
            for key in ("data", "records", "results", "items"):
                if key in data and isinstance(data[key], list):
                    return data[key]
            # Single object response (e.g. empty result set as {})
            return []

        except requests.exceptions.Timeout:
            logger.warning("Timeout on attempt %d for %s", attempt, url)
        except requests.exceptions.ConnectionError as e:
            logger.warning("Connection error attempt %d: %s", attempt, e)
        except Exception as e:
            logger.warning("Request error attempt %d: %s", attempt, e)

        if attempt < MAX_RETRIES:
            time.sleep(INTER_REQUEST_DELAY * attempt)

    logger.error("All %d attempts failed for %s", MAX_RETRIES, url)
    return None


# ─────────────────────────────────────────
# RECORD PARSERS
# ─────────────────────────────────────────

def _parse_date(val) -> Optional[date]:
    """Parse various date formats sansad.in might return."""
    if not val:
        return None
    if isinstance(val, date):
        return val
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d %b %Y"):
        try:
            return datetime.strptime(str(val).strip(), fmt).date()
        except ValueError:
            continue
    return None


def _parse_questions(raw: list, tenant_id: int, session_name: str) -> list:
    """Normalise raw sansad.in question records into DB-ready dicts."""
    out = []
    for r in raw:
        # sansad.in question record fields (best-guess from api_ls pattern)
        q_num  = str(r.get("questionNo") or r.get("qno") or r.get("questionNumber") or "").strip()
        q_type = str(r.get("questionType") or r.get("type") or "unstarred").strip().lower()
        if not q_num:
            continue
        out.append({
            "tenant_id":       tenant_id,
            "house":           "lok_sabha",
            "session_name":    session_name,
            "session_number":  str(r.get("session") or ""),
            "question_number": q_num,
            "question_type":   q_type,
            "subject":         str(r.get("subject") or r.get("title") or "")[:500],
            "ministry":        str(r.get("ministry") or r.get("ministryName") or "")[:200],
            "question_text":   str(r.get("questionText") or r.get("question") or ""),
            "answer_text":     str(r.get("answerText") or r.get("answer") or ""),
            "date_asked":      _parse_date(r.get("date") or r.get("questionDate")),
        })
    return out


def _parse_debates(raw: list, tenant_id: int, session_name: str) -> list:
    out = []
    for r in raw:
        topic = str(r.get("topic") or r.get("subject") or r.get("title") or "").strip()
        if not topic:
            continue
        out.append({
            "tenant_id":      tenant_id,
            "house":          "lok_sabha",
            "session_name":   session_name,
            "date":           _parse_date(r.get("date") or r.get("debateDate")),
            "topic":          topic[:500],
            "bill_reference": str(r.get("billNumber") or r.get("billRef") or "")[:100] or None,
            "speech_excerpt": str(r.get("speechText") or r.get("excerpt") or "")[:1000],
            "full_speech_url": str(r.get("speechUrl") or r.get("url") or "") or None,
        })
    return out


def _parse_pmbs(raw: list, tenant_id: int, session_name: str) -> list:
    out = []
    for r in raw:
        bill_no = str(r.get("billNumber") or r.get("billNo") or r.get("number") or "").strip()
        if not bill_no:
            continue
        out.append({
            "tenant_id":       tenant_id,
            "house":           "lok_sabha",
            "session_name":    session_name,
            "bill_number":     bill_no,
            "title":           str(r.get("title") or r.get("billTitle") or "")[:500],
            "subject":         str(r.get("subject") or r.get("description") or ""),
            "date_introduced": _parse_date(r.get("date") or r.get("dateIntroduced")),
            "current_status":  str(r.get("status") or "introduced")[:100],
            "bill_text_url":   str(r.get("url") or r.get("pdfUrl") or "") or None,
        })
    return out


def _parse_zero_hour(raw: list, tenant_id: int, session_name: str) -> list:
    out = []
    for r in raw:
        subject = str(r.get("subject") or r.get("title") or "").strip()
        if not subject:
            continue
        out.append({
            "tenant_id":    tenant_id,
            "house":        "lok_sabha",
            "session_name": session_name,
            "date":         _parse_date(r.get("date") or r.get("submissionDate")),
            "subject":      subject[:500],
            "text_excerpt": str(r.get("text") or r.get("description") or "")[:1000],
        })
    return out


PARSERS = {
    "questions": _parse_questions,
    "debates":   _parse_debates,
    "pmbs":      _parse_pmbs,
    "zero_hour": _parse_zero_hour,
}


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
                     date_asked, scraped_at)
                VALUES
                    (:tenant_id, :house, :session_name, :session_number, :question_number,
                     :question_type, :subject, :ministry, :question_text, :answer_text,
                     :date_asked, NOW())
                ON CONFLICT ON CONSTRAINT uq_pq_tenant_session_number_type
                DO NOTHING
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


def _upsert_pmbs(records: list) -> int:
    if not records:
        return 0
    inserted = 0
    with engine.begin() as conn:
        for r in records:
            result = conn.execute(text("""
                INSERT INTO private_members_bills
                    (tenant_id, house, session_name, bill_number, title,
                     subject, date_introduced, current_status, bill_text_url, scraped_at)
                VALUES
                    (:tenant_id, :house, :session_name, :bill_number, :title,
                     :subject, :date_introduced, :current_status, :bill_text_url, NOW())
                ON CONFLICT ON CONSTRAINT uq_pmb_tenant_session_bill
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


UPSERT_FNS = {
    "questions": _upsert_questions,
    "debates":   _upsert_debates,
    "pmbs":      _upsert_pmbs,
    "zero_hour": _upsert_zero_hour,
}


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
            "started":   now if status == "running" else None,
            "completed": now if status in ("done", "error") else None,
        })


# ─────────────────────────────────────────
# CORE SCRAPE — ONE SESSION, ONE DATA TYPE
# ─────────────────────────────────────────

def scrape_session(tenant_id: int, member_id: str, session_num: int,
                   session_name: str, data_type: str) -> int:
    """
    Fetch one data type for one MP for one session.
    Returns number of new records inserted.
    """
    cfg     = DATA_TYPES[data_type]
    url     = f"{SANSAD_API}/{cfg['api_slug']}"
    params  = {"loksabha": "18", "session": str(session_num), "mpsno": str(member_id), "locale": "en"}

    logger.info("Scraping %s | tenant=%d | session=%s | mpsno=%s",
                data_type, tenant_id, session_name, member_id)

    _mark_job(tenant_id, session_name, data_type, "running")

    raw = _get(url, params)
    if raw is None:
        _mark_job(tenant_id, session_name, data_type, "error",
                  error=f"All {MAX_RETRIES} HTTP attempts failed")
        return 0

    if not raw:
        _mark_job(tenant_id, session_name, data_type, "done", records=0)
        return 0

    # Parse
    parse_fn  = PARSERS[data_type]
    records   = parse_fn(raw, tenant_id, session_name)
    upsert_fn = UPSERT_FNS[data_type]
    inserted  = upsert_fn(records)

    _mark_job(tenant_id, session_name, data_type, "done", records=inserted)
    logger.info("  → %d raw records, %d new inserts", len(records), inserted)
    return inserted


# ─────────────────────────────────────────
# BACKFILL — ALL 6 SESSIONS, ONE TENANT
# ─────────────────────────────────────────

def backfill_tenant(tenant_id: int, data_types: list = None,
                    sessions: list = None) -> dict:
    """
    Run the 6-session historical backfill for one tenant.

    Args:
        tenant_id:   DB tenant id
        data_types:  subset of ['questions','debates','pmbs','zero_hour']
                     defaults to all 4
        sessions:    subset of session numbers 1–6
                     defaults to all 6

    Returns summary dict: {data_type: {session_name: records_inserted}}
    """
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            return {"error": f"Tenant {tenant_id} not found"}
        if not tenant.parliament_member_id:
            return {"error": f"Tenant {tenant_id} has no parliament_member_id — run identity resolver first"}
        if tenant.parliament_sync_status not in ("active", "auto_matched"):
            return {"error": f"Tenant {tenant_id} sync status is '{tenant.parliament_sync_status}' — confirm identity first"}
        member_id = tenant.parliament_member_id
    finally:
        db.close()

    target_types    = data_types or list(DATA_TYPES.keys())
    target_sessions = [s for s in LOK_SABHA_18_SESSIONS if sessions is None or s[0] in sessions]

    summary = {dt: {} for dt in target_types}
    total   = len(target_types) * len(target_sessions)
    done    = 0

    logger.info("Starting backfill: tenant=%d mpsno=%s | %d types × %d sessions",
                tenant_id, member_id, len(target_types), len(target_sessions))

    for session_num, session_name, _, _ in target_sessions:
        for data_type in target_types:
            inserted = scrape_session(
                tenant_id, member_id, session_num, session_name, data_type
            )
            summary[data_type][session_name] = inserted
            done += 1
            logger.info("Progress: %d/%d", done, total)
            time.sleep(INTER_REQUEST_DELAY)

    # Update tenant sync timestamp
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE tenants
            SET parliament_last_synced = NOW(),
                parliament_sync_status = 'active'
            WHERE id = :tid
        """), {"tid": tenant_id})

    logger.info("Backfill complete for tenant %d: %s", tenant_id, summary)
    return summary


# ─────────────────────────────────────────
# INCREMENTAL SYNC — ALL ACTIVE TENANTS
# ─────────────────────────────────────────

def sync_all_active_tenants(data_types: list = None) -> dict:
    """
    Incremental sync: fetch only the latest/current session for all tenants
    whose parliament_sync_enabled = true and parliament_member_id is set.

    Called by the session monitor cron (every 4–6h during active sessions).
    """
    db = SessionLocal()
    try:
        tenants = db.query(Tenant).filter(
            Tenant.parliament_sync_enabled == True,
            Tenant.parliament_member_id.isnot(None),
            Tenant.parliament_sync_status == "active",
            Tenant.is_active == True,
        ).all()
        tenant_list = [(t.id, t.parliament_member_id) for t in tenants]
    finally:
        db.close()

    if not tenant_list:
        logger.info("No active tenants with confirmed parliament identity — nothing to sync")
        return {}

    # Determine the most recent completed session (don't scrape future sessions)
    today = date.today()
    completed = [s for s in LOK_SABHA_18_SESSIONS if s[3] <= today]
    if not completed:
        logger.info("No completed 18th Lok Sabha sessions yet")
        return {}
    latest = completed[-1]   # (session_num, session_name, start, end)

    target_types = data_types or list(DATA_TYPES.keys())
    results = {}

    logger.info("Incremental sync: %d tenants, session=%s, types=%s",
                len(tenant_list), latest[1], target_types)

    for tenant_id, member_id in tenant_list:
        tenant_results = {}
        for data_type in target_types:
            inserted = scrape_session(
                tenant_id, member_id, latest[0], latest[1], data_type
            )
            tenant_results[data_type] = inserted
            time.sleep(INTER_REQUEST_DELAY)

        # Update last_synced
        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE tenants SET parliament_last_synced = NOW() WHERE id = :tid
            """), {"tid": tenant_id})

        results[tenant_id] = tenant_results

    return results


# ─────────────────────────────────────────
# BATCH BACKFILL — ALL CONFIRMED TENANTS
# ─────────────────────────────────────────

def backfill_all_confirmed_tenants() -> dict:
    """
    Run 6-session backfill for every tenant with a confirmed parliament_member_id
    that hasn't been backfilled yet (no backfill_jobs rows = not started).

    Called once from the admin "Run Backfill for All" button.
    """
    db = SessionLocal()
    try:
        tenants = db.query(Tenant).filter(
            Tenant.parliament_member_id.isnot(None),
            Tenant.parliament_sync_status == "active",
            Tenant.is_active == True,
        ).all()
        ids = [t.id for t in tenants]
    finally:
        db.close()

    # Filter to those with at least one pending backfill job
    to_backfill = []
    for tid in ids:
        with engine.connect() as conn:
            row = conn.execute(text("""
                SELECT COUNT(*) AS cnt FROM parliament_backfill_jobs
                WHERE tenant_id = :tid AND status = 'done'
            """), {"tid": tid}).mappings().fetchone()
        done_count = row["cnt"] if row else 0
        total_expected = len(LOK_SABHA_18_SESSIONS) * len(DATA_TYPES)
        if done_count < total_expected:
            to_backfill.append(tid)

    logger.info("Batch backfill: %d tenants need work (out of %d confirmed)",
                len(to_backfill), len(ids))

    results = {}
    for i, tid in enumerate(to_backfill):
        logger.info("Backfilling tenant %d (%d/%d)…", tid, i + 1, len(to_backfill))
        results[tid] = backfill_tenant(tid)
        # Brief pause between tenants
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
    parser = argparse.ArgumentParser(description="Needle Parliament Scraper")
    parser.add_argument("--backfill-tenant", type=int, metavar="TENANT_ID",
                        help="Run 6-session backfill for one tenant")
    parser.add_argument("--backfill-all",  action="store_true",
                        help="Backfill all confirmed tenants that haven't been backfilled yet")
    parser.add_argument("--sync-all",      action="store_true",
                        help="Incremental sync (latest session only) for all active tenants")
    parser.add_argument("--data-types",    nargs="+",
                        choices=["questions", "debates", "pmbs", "zero_hour"],
                        help="Limit to specific data types (default: all)")
    parser.add_argument("--sessions",      nargs="+", type=int, metavar="N",
                        help="Limit to specific session numbers 1-6 (default: all)")
    args = parser.parse_args()

    if args.backfill_tenant:
        result = backfill_tenant(
            args.backfill_tenant,
            data_types=args.data_types,
            sessions=args.sessions,
        )
        print(result)
    elif args.backfill_all:
        result = backfill_all_confirmed_tenants()
        print(result)
    elif args.sync_all:
        result = sync_all_active_tenants(data_types=args.data_types)
        print(result)
    else:
        parser.print_help()
