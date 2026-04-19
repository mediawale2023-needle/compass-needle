"""
jobs/parliament_answer_fetcher.py — Fetch Ministry answers for PRS-linked
parliamentary questions.

Phase 1 of the Needle "MP Brain". Completes the parliamentary record stored
by jobs/parliament_scraper.py by downloading the Ministry's consolidated
Q&A PDF and writing the actual `question_text` and `answer_text` into the
`parliamentary_questions` table.

Schema additions managed here (idempotent CREATE/ALTER on first run):

    parliamentary_questions
        + question_pdf_url          TEXT        — PDF URL (moved out of question_text)
        + real_question_number      VARCHAR(20) — actual LS/RS number (not our hash)
        + answer_fetched_at         TIMESTAMP
        + answer_fetch_status       VARCHAR(20) — ok | no_match | no_pdf | failed

    prs_pdf_cache
        pdf_url           TEXT PRIMARY KEY
        content_hash      VARCHAR(64)
        extracted_text    TEXT
        parsed_qas        JSONB
        extractor_method  VARCHAR(40)
        fetch_status      VARCHAR(20)
        error_message     TEXT
        pages             INT
        size_bytes        INT
        fetched_at        TIMESTAMP

Usage:
    from jobs.parliament_answer_fetcher import fetch_answers_for_tenant, get_coverage_stats

    # CLI
    python -m jobs.parliament_answer_fetcher --migrate
    python -m jobs.parliament_answer_fetcher --tenant 5
    python -m jobs.parliament_answer_fetcher --all
    python -m jobs.parliament_answer_fetcher --coverage
    python -m jobs.parliament_answer_fetcher --coverage --tenant 5
"""

from __future__ import annotations

import os
import sys
import json
import time
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sansadx_backend.db import engine
from modules.prs_answer_extractor import (
    extract_qas_from_pdf,
    match_qas_to_rows,
    polite_sleep,
)

logger = logging.getLogger("needle.parliament_answer_fetcher")


# ─────────────────────────────────────────────────────────────────────────
# SCHEMA (idempotent)
# ─────────────────────────────────────────────────────────────────────────

def ensure_schema():
    """
    Creates prs_pdf_cache and adds the new columns to parliamentary_questions
    if they don't already exist. Safe to run repeatedly.
    """
    with engine.begin() as conn:
        # prs_pdf_cache table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS prs_pdf_cache (
                pdf_url          TEXT PRIMARY KEY,
                content_hash     VARCHAR(64),
                extracted_text   TEXT,
                parsed_qas       JSONB,
                extractor_method VARCHAR(40),
                fetch_status     VARCHAR(20) NOT NULL DEFAULT 'pending',
                error_message    TEXT,
                pages            INT,
                size_bytes       INT,
                fetched_at       TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_prs_pdf_cache_status "
            "ON prs_pdf_cache (fetch_status)"
        ))

        # Augment parliamentary_questions
        conn.execute(text(
            "ALTER TABLE parliamentary_questions "
            "ADD COLUMN IF NOT EXISTS question_pdf_url TEXT"
        ))
        conn.execute(text(
            "ALTER TABLE parliamentary_questions "
            "ADD COLUMN IF NOT EXISTS real_question_number VARCHAR(20)"
        ))
        conn.execute(text(
            "ALTER TABLE parliamentary_questions "
            "ADD COLUMN IF NOT EXISTS answer_fetched_at TIMESTAMP"
        ))
        conn.execute(text(
            "ALTER TABLE parliamentary_questions "
            "ADD COLUMN IF NOT EXISTS answer_fetch_status VARCHAR(20)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_pq_answer_fetch_status "
            "ON parliamentary_questions (answer_fetch_status)"
        ))


def migrate_question_text_urls() -> int:
    """
    One-off migration: the current scraper writes the PDF URL into the
    `question_text` column. Move those URLs into `question_pdf_url` and
    null out `question_text` so it can be populated with real body text.

    Returns the number of rows updated. Idempotent — safe to re-run.
    """
    ensure_schema()
    with engine.begin() as conn:
        # Populate question_pdf_url from any row where it's null and
        # question_text looks like a URL.
        result = conn.execute(text("""
            UPDATE parliamentary_questions
               SET question_pdf_url = question_text,
                   question_text    = NULL
             WHERE question_pdf_url IS NULL
               AND question_text IS NOT NULL
               AND (question_text ILIKE 'http://%' OR question_text ILIKE 'https://%')
        """))
        moved = result.rowcount or 0
    logger.info("migrate_question_text_urls: %d rows migrated", moved)
    return moved


# ─────────────────────────────────────────────────────────────────────────
# PDF CACHE ACCESSORS
# ─────────────────────────────────────────────────────────────────────────

def _get_cached(url: str) -> Optional[dict]:
    row = None
    with engine.connect() as conn:
        r = conn.execute(
            text("SELECT * FROM prs_pdf_cache WHERE pdf_url = :u"),
            {"u": url},
        ).mappings().fetchone()
        row = dict(r) if r else None
    if not row:
        return None
    # parsed_qas is JSONB; psycopg2 returns it already-decoded on SQLAlchemy 2.x
    pq = row.get("parsed_qas")
    if isinstance(pq, str):
        try:
            row["parsed_qas"] = json.loads(pq)
        except Exception:
            row["parsed_qas"] = []
    return row


def _save_cache(url: str, result: dict):
    """Store extractor output in prs_pdf_cache (overwrite on re-run)."""
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO prs_pdf_cache (
                pdf_url, content_hash, extracted_text, parsed_qas,
                extractor_method, fetch_status, error_message,
                pages, size_bytes, fetched_at
            )
            VALUES (
                :url, :hash, :text, CAST(:qas AS JSONB),
                :method, :status, :err,
                :pages, :size, NOW()
            )
            ON CONFLICT (pdf_url) DO UPDATE SET
                content_hash     = EXCLUDED.content_hash,
                extracted_text   = EXCLUDED.extracted_text,
                parsed_qas       = EXCLUDED.parsed_qas,
                extractor_method = EXCLUDED.extractor_method,
                fetch_status     = EXCLUDED.fetch_status,
                error_message    = EXCLUDED.error_message,
                pages            = EXCLUDED.pages,
                size_bytes       = EXCLUDED.size_bytes,
                fetched_at       = NOW()
        """), {
            "url":    url,
            "hash":   result.get("content_hash") or "",
            "text":   (result.get("extracted_text") or "")[:500_000],
            "qas":    json.dumps(result.get("parsed_qas") or [])[:2_000_000],
            "method": result.get("method") or "",
            "status": result.get("status") or "unknown",
            "err":    (result.get("error") or "")[:500] if result.get("error") else None,
            "pages":  result.get("pages") or 0,
            "size":   result.get("size_bytes") or 0,
        })


def get_or_fetch_pdf(url: str, allow_ocr: bool = True,
                    force: bool = False) -> dict:
    """
    Cache-aware fetch. Returns the extractor result dict.
    If cached and status == 'ok', reuses the cached entry.
    """
    if not force:
        cached = _get_cached(url)
        if cached and cached.get("fetch_status") == "ok":
            return {
                "status":             "ok",
                "method":             cached.get("extractor_method"),
                "pages":              cached.get("pages") or 0,
                "size_bytes":         cached.get("size_bytes") or 0,
                "content_hash":       cached.get("content_hash") or "",
                "extracted_text":     "",   # not returned from cache by default
                "extracted_text_len": len(cached.get("extracted_text") or ""),
                "parsed_qas":         cached.get("parsed_qas") or [],
                "error":              None,
                "cached":             True,
            }

    result = extract_qas_from_pdf(url, allow_ocr=allow_ocr)
    # Persist raw text only if success and size is sane
    result["extracted_text"] = ""  # we don't need to keep this outside cache
    _save_cache(url, result)
    # Be polite if we actually hit the network
    polite_sleep()
    return result


# ─────────────────────────────────────────────────────────────────────────
# UPDATE DB ROWS WITH MATCHED Q&A
# ─────────────────────────────────────────────────────────────────────────

def _apply_matches_to_db(matches: dict) -> int:
    """
    Write matched question_text + answer_text to parliamentary_questions.
    `matches` = {db_row_id: {parsed_qa, score, match_basis}}.
    Returns the count of rows updated.
    """
    if not matches:
        return 0
    updated = 0
    with engine.begin() as conn:
        for row_id, m in matches.items():
            pqa = m["parsed_qa"]
            q_text = (pqa.get("question_text") or "").strip()
            a_text = (pqa.get("answer_text") or "").strip()
            real_num = (pqa.get("question_number") or "").strip() or None
            ministry = (pqa.get("ministry") or "").strip() or None
            status = "ok" if a_text else "no_answer_in_pdf"
            conn.execute(text("""
                UPDATE parliamentary_questions
                   SET question_text        = COALESCE(NULLIF(:qt, ''),   question_text),
                       answer_text          = COALESCE(NULLIF(:at, ''),   answer_text),
                       real_question_number = COALESCE(:rn, real_question_number),
                       ministry             = COALESCE(NULLIF(:mn, ''),  ministry),
                       answer_fetched_at    = NOW(),
                       answer_fetch_status  = :status
                 WHERE id = :rid
            """), {
                "qt":     q_text,
                "at":     a_text,
                "rn":     real_num,
                "mn":     ministry,
                "status": status,
                "rid":    row_id,
            })
            updated += 1
    return updated


def _mark_rows_status(row_ids: list[int], status: str):
    if not row_ids:
        return
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE parliamentary_questions
               SET answer_fetched_at   = NOW(),
                   answer_fetch_status = :s
             WHERE id = ANY(:ids)
        """), {"s": status, "ids": row_ids})


# ─────────────────────────────────────────────────────────────────────────
# TENANT-LEVEL ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────────────

def _fetch_rows_needing_answers(tenant_id: Optional[int],
                                limit_rows: Optional[int] = None) -> list[dict]:
    where = "(answer_text IS NULL OR answer_text = '') AND question_pdf_url IS NOT NULL AND question_pdf_url <> ''"
    params: dict = {}
    if tenant_id:
        where += " AND tenant_id = :tid"
        params["tid"] = tenant_id
    if limit_rows:
        params["lim"] = limit_rows
    limit_sql = " LIMIT :lim" if limit_rows else ""
    sql = f"""
        SELECT id, tenant_id, session_name, question_number, question_type,
               subject, ministry, question_pdf_url, real_question_number
          FROM parliamentary_questions
         WHERE {where}
         ORDER BY date_asked DESC NULLS LAST, id
         {limit_sql}
    """
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]


def fetch_answers_for_tenant(
    tenant_id: int,
    max_pdfs: Optional[int] = None,
    allow_ocr: bool = True,
    force: bool = False,
    max_rows: Optional[int] = None,
) -> dict:
    """
    Backfill answers for one tenant.

    Args:
        tenant_id: DB tenant id
        max_pdfs:  Cap the number of unique PDFs processed in this run
        allow_ocr: If False, skip Gemini OCR fallback (pdfplumber-only)
        force:     Ignore cache; re-download + re-extract every PDF
        max_rows:  Cap the number of DB rows considered

    Returns summary dict.
    """
    ensure_schema()

    rows = _fetch_rows_needing_answers(tenant_id, limit_rows=max_rows)
    if not rows:
        return {
            "tenant_id":         tenant_id,
            "rows_considered":   0,
            "unique_pdfs":       0,
            "pdfs_processed":    0,
            "pdfs_failed":       0,
            "rows_updated":      0,
            "rows_unmatched":    0,
            "started_at":        datetime.utcnow().isoformat() + "Z",
            "finished_at":       datetime.utcnow().isoformat() + "Z",
        }

    # Group rows by PDF URL (many questions share one daily PDF)
    by_url: dict[str, list[dict]] = {}
    for r in rows:
        u = (r.get("question_pdf_url") or "").strip()
        if u:
            by_url.setdefault(u, []).append(r)

    unique_urls = list(by_url.keys())
    if max_pdfs:
        unique_urls = unique_urls[:max_pdfs]

    started = datetime.utcnow()
    pdfs_processed = 0
    pdfs_failed    = 0
    rows_updated   = 0
    rows_unmatched = 0

    logger.info(
        "fetch_answers_for_tenant(%s): %d rows across %d unique PDFs (cap=%s)",
        tenant_id, len(rows), len(unique_urls), max_pdfs,
    )

    for i, url in enumerate(unique_urls, start=1):
        urow_ids = [r["id"] for r in by_url[url]]
        try:
            result = get_or_fetch_pdf(url, allow_ocr=allow_ocr, force=force)
        except Exception as e:
            logger.exception("PDF %s unexpected error: %s", url, e)
            pdfs_failed += 1
            _mark_rows_status(urow_ids, "failed")
            continue

        if result.get("status") != "ok" or not result.get("parsed_qas"):
            pdfs_failed += 1
            _mark_rows_status(urow_ids, "no_pdf" if result.get("error") == "download_failed" else "failed")
            continue

        pdfs_processed += 1
        matches = match_qas_to_rows(result["parsed_qas"], by_url[url])
        if matches:
            rows_updated += _apply_matches_to_db(matches)

        # Rows that had no match — mark as no_match
        unmatched_ids = [rid for rid in urow_ids if rid not in matches]
        rows_unmatched += len(unmatched_ids)
        _mark_rows_status(unmatched_ids, "no_match")

        if i % 5 == 0 or i == len(unique_urls):
            logger.info(
                "  … progress: %d/%d PDFs done, %d rows updated, %d unmatched",
                i, len(unique_urls), rows_updated, rows_unmatched,
            )

    finished = datetime.utcnow()
    summary = {
        "tenant_id":       tenant_id,
        "rows_considered": len(rows),
        "unique_pdfs":     len(unique_urls),
        "pdfs_processed":  pdfs_processed,
        "pdfs_failed":     pdfs_failed,
        "rows_updated":    rows_updated,
        "rows_unmatched":  rows_unmatched,
        "started_at":      started.isoformat() + "Z",
        "finished_at":     finished.isoformat() + "Z",
        "duration_sec":    round((finished - started).total_seconds(), 2),
    }
    logger.info("fetch_answers_for_tenant done: %s", summary)
    return summary


def fetch_answers_for_all_tenants(
    max_pdfs_per_tenant: Optional[int] = None,
    allow_ocr: bool = True,
) -> dict:
    """
    Run the answer fetcher for every tenant that has at least one row needing
    answers. Sequential (polite to PRS / Lok Sabha servers).
    """
    ensure_schema()
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT DISTINCT tenant_id
              FROM parliamentary_questions
             WHERE (answer_text IS NULL OR answer_text = '')
               AND question_pdf_url IS NOT NULL
               AND question_pdf_url <> ''
             ORDER BY tenant_id
        """)).mappings().all()
    tids = [r["tenant_id"] for r in rows]

    out = {}
    for tid in tids:
        logger.info("▶ fetch_answers_for_tenant(%s)", tid)
        out[tid] = fetch_answers_for_tenant(
            tid, max_pdfs=max_pdfs_per_tenant, allow_ocr=allow_ocr,
        )
        time.sleep(1.0)
    return {"tenants_processed": len(tids), "per_tenant": out}


# ─────────────────────────────────────────────────────────────────────────
# COVERAGE STATS
# ─────────────────────────────────────────────────────────────────────────

def get_coverage_stats(tenant_id: Optional[int] = None) -> dict:
    """
    Return answer-coverage stats for a tenant (or all tenants).

    {
      "tenant_id":      int | None,
      "total":          int,
      "with_answer":    int,
      "with_pdf_url":   int,
      "no_pdf_url":     int,
      "pending":        int,
      "failed":         int,
      "no_match":       int,
      "pct_covered":    float
    }
    """
    ensure_schema()
    where = "1=1"
    params: dict = {}
    if tenant_id:
        where = "tenant_id = :tid"
        params["tid"] = tenant_id

    sql = f"""
        SELECT
            COUNT(*)                                                         AS total,
            COUNT(*) FILTER (WHERE answer_text IS NOT NULL AND answer_text <> '') AS with_answer,
            COUNT(*) FILTER (WHERE question_pdf_url IS NOT NULL AND question_pdf_url <> '') AS with_pdf_url,
            COUNT(*) FILTER (WHERE question_pdf_url IS NULL OR question_pdf_url = '')      AS no_pdf_url,
            COUNT(*) FILTER (WHERE answer_fetch_status IS NULL)              AS pending,
            COUNT(*) FILTER (WHERE answer_fetch_status = 'failed')           AS failed,
            COUNT(*) FILTER (WHERE answer_fetch_status = 'no_match')         AS no_match,
            COUNT(*) FILTER (WHERE answer_fetch_status = 'no_pdf')           AS no_pdf
          FROM parliamentary_questions
         WHERE {where}
    """
    with engine.connect() as conn:
        r = conn.execute(text(sql), params).mappings().fetchone()
    row = dict(r) if r else {}

    total = int(row.get("total") or 0)
    with_ans = int(row.get("with_answer") or 0)
    pct = round((with_ans / total * 100), 1) if total else 0.0

    return {
        "tenant_id":    tenant_id,
        "total":        total,
        "with_answer":  with_ans,
        "with_pdf_url": int(row.get("with_pdf_url") or 0),
        "no_pdf_url":   int(row.get("no_pdf_url") or 0),
        "pending":      int(row.get("pending") or 0),
        "failed":       int(row.get("failed") or 0),
        "no_match":     int(row.get("no_match") or 0),
        "no_pdf":       int(row.get("no_pdf") or 0),
        "pct_covered":  pct,
    }


def get_coverage_stats_per_tenant() -> list[dict]:
    """Return coverage stats for every tenant with parliamentary questions."""
    ensure_schema()
    sql = """
        SELECT
            pq.tenant_id,
            t.name AS tenant_name,
            COUNT(*)                                                         AS total,
            COUNT(*) FILTER (WHERE pq.answer_text IS NOT NULL AND pq.answer_text <> '')   AS with_answer,
            COUNT(*) FILTER (WHERE pq.question_pdf_url IS NOT NULL AND pq.question_pdf_url <> '') AS with_pdf_url,
            COUNT(*) FILTER (WHERE pq.answer_fetch_status IS NULL)           AS pending,
            COUNT(*) FILTER (WHERE pq.answer_fetch_status = 'failed')        AS failed,
            COUNT(*) FILTER (WHERE pq.answer_fetch_status = 'no_match')      AS no_match
          FROM parliamentary_questions pq
          LEFT JOIN tenants t ON t.id = pq.tenant_id
      GROUP BY pq.tenant_id, t.name
      ORDER BY pq.tenant_id
    """
    with engine.connect() as conn:
        rows = conn.execute(text(sql)).mappings().all()
    out = []
    for r in rows:
        total = int(r.get("total") or 0)
        w = int(r.get("with_answer") or 0)
        out.append({
            "tenant_id":   r["tenant_id"],
            "tenant_name": r.get("tenant_name") or "",
            "total":       total,
            "with_answer": w,
            "with_pdf_url": int(r.get("with_pdf_url") or 0),
            "pending":     int(r.get("pending") or 0),
            "failed":      int(r.get("failed") or 0),
            "no_match":    int(r.get("no_match") or 0),
            "pct_covered": round(w / total * 100, 1) if total else 0.0,
        })
    return out


# ─────────────────────────────────────────────────────────────────────────
# CLI RUNNER
# ─────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    import argparse
    ap = argparse.ArgumentParser(description="Needle Parliamentary Answer Fetcher")
    ap.add_argument("--migrate", action="store_true",
                    help="Create/alter schema + one-off migrate existing URL data")
    ap.add_argument("--tenant", type=int, metavar="TENANT_ID",
                    help="Fetch answers for one tenant")
    ap.add_argument("--all", action="store_true",
                    help="Fetch answers for every tenant with missing answers")
    ap.add_argument("--max-pdfs", type=int, default=None,
                    help="Cap the number of unique PDFs processed per tenant")
    ap.add_argument("--no-ocr", action="store_true",
                    help="Skip Gemini Vision OCR fallback (pdfplumber only)")
    ap.add_argument("--force", action="store_true",
                    help="Ignore cache; re-fetch every PDF")
    ap.add_argument("--coverage", action="store_true",
                    help="Print coverage stats")
    args = ap.parse_args()

    if args.migrate:
        ensure_schema()
        moved = migrate_question_text_urls()
        print(f"Schema ensured. Rows migrated (question_text→pdf_url): {moved}")
        sys.exit(0)

    if args.coverage:
        if args.tenant:
            print(json.dumps(get_coverage_stats(args.tenant), indent=2))
        else:
            print(json.dumps(get_coverage_stats_per_tenant(), indent=2))
        sys.exit(0)

    if args.tenant:
        result = fetch_answers_for_tenant(
            args.tenant,
            max_pdfs=args.max_pdfs,
            allow_ocr=not args.no_ocr,
            force=args.force,
        )
        print(json.dumps(result, indent=2))
    elif args.all:
        result = fetch_answers_for_all_tenants(
            max_pdfs_per_tenant=args.max_pdfs,
            allow_ocr=not args.no_ocr,
        )
        print(json.dumps(result, indent=2, default=str))
    else:
        ap.print_help()
