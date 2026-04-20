"""
jobs/brain_indexer.py — Index/re-index all sources into memory_chunks.

Phase 2 of the Needle Brain. Takes raw rows from:

    parliamentary_questions
    parliamentary_debates
    zero_hour_submissions
    cases
    constituency_profiles  (filesystem JSON in /app/data/constituency_profiles/)
    schemes_db.json        (global)

…runs them through modules/brain_chunker, embeds via OpenAI text-
embedding-3-small, and upserts into memory_chunks (pgvector index).

Idempotent — re-runs only embed chunks whose content_hash changed.

CLI:
    python -m jobs.brain_indexer --init-schema
    python -m jobs.brain_indexer --tenant 5
    python -m jobs.brain_indexer --tenant 5 --source pq
    python -m jobs.brain_indexer --all
    python -m jobs.brain_indexer --schemes
    python -m jobs.brain_indexer --rebuild --tenant 5     # delete + reindex
    python -m jobs.brain_indexer --stats
"""

from __future__ import annotations

import os
import sys
import json
import time
import logging
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sansadx_backend.db import engine
from modules.brain_chunker import (
    chunk_pq_row, chunk_debate_row, chunk_zero_hour_row,
    chunk_constituency_profile, chunk_case_row, chunk_scheme,
    chunk_global_pq_row,
)
from modules.brain_embedder import embed_texts, to_vector_literal, EMBED_DIM, EMBED_MODEL

logger = logging.getLogger("needle.brain_indexer")


# ─────────────────────────────────────────────────────────────────────────
# SCHEMA
# ─────────────────────────────────────────────────────────────────────────

def _pgvector_available() -> bool:
    """
    Return True if the pgvector extension is installed and the vector type
    is usable.  Checks pg_extension (authoritative) then does a live cast
    to confirm the type is accessible in the current search_path.
    """
    try:
        with engine.connect() as conn:
            # Primary: is the extension registered?
            ext = conn.execute(text(
                "SELECT 1 FROM pg_extension WHERE extname = 'vector'"
            )).fetchone()
            if not ext:
                return False
            # Secondary: is the type actually castable (search_path check)?
            conn.execute(text("SELECT '[1,2,3]'::vector(3)"))
            return True
    except Exception:
        return False


def ensure_schema():
    """
    Enable pgvector + create memory_chunks.  Idempotent.

    Design rules so Railway / hosted Postgres never leaves an aborted txn:
      • Each DDL that can fail independently goes in its OWN engine.begin().
      • The core CREATE TABLE never references 'vector' directly — the
        embedding column is added / altered in a separate step so the table
        is always created even when pgvector is not (yet) installed.
      • Call ensure_schema() again after enabling the extension and it will
        ADD the vector column without recreating the table.

    How to enable pgvector on Railway:
      Railway Dashboard → your Postgres service → Query tab → run:
          CREATE EXTENSION IF NOT EXISTS vector;
      Then re-run indexing — this function will auto-add the vector column.
    """
    # ── 1. Try to create extension (may fail without superuser) ───────────
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        logger.info("ensure_schema: pgvector extension enabled.")
    except Exception as e:
        logger.warning(
            "ensure_schema: CREATE EXTENSION vector failed — "
            "pgvector may not be installed on this Postgres. "
            "Enable it in Railway Dashboard → Postgres → Query tab, then re-run. "
            "Error: %s", e,
        )

    # ── 2. Core table WITHOUT the vector column ────────────────────────────
    # This always succeeds regardless of pgvector availability.
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS memory_chunks (
                id              BIGSERIAL PRIMARY KEY,
                tenant_id       INTEGER,
                source_type     VARCHAR(40)  NOT NULL,
                source_table    VARCHAR(60)  NOT NULL,
                source_id       VARCHAR(120) NOT NULL,
                title           TEXT,
                content         TEXT         NOT NULL,
                content_hash    VARCHAR(64)  NOT NULL,
                metadata        JSONB,
                ministry        VARCHAR(160),
                date_ref        DATE,
                topic_tags      TEXT[],
                embed_model     VARCHAR(60),
                indexed_at      TIMESTAMP    NOT NULL DEFAULT NOW(),
                UNIQUE (source_type, source_id, content_hash)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_mc_tenant   ON memory_chunks (tenant_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_mc_type     ON memory_chunks (source_type)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_mc_min      ON memory_chunks (LOWER(ministry))"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_mc_date     ON memory_chunks (date_ref)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_mc_table_id ON memory_chunks (source_table, source_id)"))

    # ── 3. Add / upgrade the embedding column — only if pgvector is live ──
    if not _pgvector_available():
        logger.warning(
            "ensure_schema: pgvector not available — memory_chunks created "
            "WITHOUT embedding column. Semantic search will not work until "
            "you enable the extension and re-run indexing."
        )
        return

    # Check whether the column already exists and what type it has
    try:
        with engine.connect() as conn:
            col = conn.execute(text("""
                SELECT data_type, udt_name
                  FROM information_schema.columns
                 WHERE table_name = 'memory_chunks'
                   AND column_name = 'embedding'
            """)).fetchone()
    except Exception:
        col = None

    if col is None:
        # Column doesn't exist yet — add it
        try:
            with engine.begin() as conn:
                conn.execute(text(
                    f"ALTER TABLE memory_chunks "
                    f"ADD COLUMN IF NOT EXISTS embedding vector({EMBED_DIM})"
                ))
            logger.info("ensure_schema: embedding vector(%d) column added.", EMBED_DIM)
        except Exception as e:
            logger.error("ensure_schema: could not add embedding column: %s", e)
            return
    elif col[1] != "vector":
        # Column exists but is TEXT (legacy) — convert it
        logger.info("ensure_schema: converting embedding column from TEXT to vector(%d)", EMBED_DIM)
        try:
            with engine.begin() as conn:
                conn.execute(text(
                    f"ALTER TABLE memory_chunks "
                    f"ALTER COLUMN embedding TYPE vector({EMBED_DIM}) "
                    f"USING embedding::vector({EMBED_DIM})"
                ))
        except Exception as e:
            logger.warning("ensure_schema: TEXT→vector conversion failed: %s", e)

    # Reset the module-level flag so next _upsert_chunks call re-verifies
    global _embedding_col_checked
    _embedding_col_checked = False

    # ── 4. Vector ANN index — isolated (heavy op, only runs once) ─────────
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_mc_embedding_hnsw
                  ON memory_chunks
                  USING hnsw (embedding vector_cosine_ops)
            """))
        logger.info("ensure_schema: HNSW index ready.")
    except Exception as e:
        logger.warning("HNSW unavailable, trying ivfflat: %s", e)
        try:
            with engine.begin() as conn:
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_mc_embedding_ivf
                      ON memory_chunks
                      USING ivfflat (embedding vector_cosine_ops)
                      WITH (lists = 100)
                """))
            logger.info("ensure_schema: ivfflat index ready.")
        except Exception as e2:
            logger.warning("ivfflat also unavailable — seq scan will be used: %s", e2)


# ─────────────────────────────────────────────────────────────────────────
# DEDUP / UPSERT HELPERS
# ─────────────────────────────────────────────────────────────────────────

def _hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _existing_hashes(source_table: str, source_ids: list[str]) -> set:
    """Return content_hashes already in memory_chunks for this batch."""
    if not source_ids:
        return set()
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT content_hash FROM memory_chunks
             WHERE source_table = :st AND source_id = ANY(:ids)
        """), {"st": source_table, "ids": source_ids}).all()
    return {r[0] for r in rows}


def _delete_for_source(source_table: str, source_id: str):
    """Remove all chunks for a particular source row before re-inserting."""
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM memory_chunks WHERE source_table=:st AND source_id LIKE :sid"),
            {"st": source_table, "sid": f"{source_id}%"},
        )


def _delete_for_tenant(tenant_id: int):
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM memory_chunks WHERE tenant_id = :tid"),
            {"tid": tenant_id},
        )


def _ensure_embedding_column():
    """
    Verify the embedding column exists and is of type vector.
    Called once before the first INSERT attempt.  Raises RuntimeError with
    a clear action message if pgvector is not enabled so the admin UI can
    surface it instead of showing a cryptic Postgres error.
    """
    if not _pgvector_available():
        raise RuntimeError(
            "pgvector extension is not enabled on this Postgres instance. "
            "Go to Railway Dashboard → your Postgres service → Query tab and run:\n"
            "    CREATE EXTENSION IF NOT EXISTS vector;\n"
            "Then click 'Embed global PQs' again."
        )
    # Attempt to add the column if missing (handles fresh deploys)
    try:
        with engine.connect() as conn:
            col = conn.execute(text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name='memory_chunks' AND column_name='embedding'"
            )).fetchone()
        if not col:
            with engine.begin() as conn:
                conn.execute(text(
                    f"ALTER TABLE memory_chunks "
                    f"ADD COLUMN IF NOT EXISTS embedding vector({EMBED_DIM})"
                ))
            logger.info("_ensure_embedding_column: embedding column added.")
    except Exception as e:
        raise RuntimeError(
            f"Could not add embedding column to memory_chunks: {e}\n"
            "Ensure pgvector is enabled: CREATE EXTENSION IF NOT EXISTS vector;"
        ) from e


_embedding_col_checked = False   # module-level flag so we only check once per process


def _upsert_chunks(chunks: list[dict], embeddings: list[Optional[list[float]]]) -> int:
    """Insert (or skip-on-conflict) chunks with their embeddings."""
    if not chunks:
        return 0

    global _embedding_col_checked
    if not _embedding_col_checked:
        _ensure_embedding_column()   # raises RuntimeError with clear message if missing
        _embedding_col_checked = True

    inserted = 0
    sql = text("""
        INSERT INTO memory_chunks (
            tenant_id, source_type, source_table, source_id,
            title, content, content_hash, metadata,
            ministry, date_ref, topic_tags,
            embedding, embed_model, indexed_at
        ) VALUES (
            :tid, :stype, :stbl, :sid,
            :title, :content, :hash, CAST(:meta AS JSONB),
            :ministry, :dateref, :tags,
            CAST(:emb AS vector), :model, NOW()
        )
        ON CONFLICT (source_type, source_id, content_hash) DO UPDATE
            SET indexed_at  = NOW(),
                embedding   = EXCLUDED.embedding,
                metadata    = EXCLUDED.metadata,
                ministry    = EXCLUDED.ministry,
                date_ref    = EXCLUDED.date_ref,
                topic_tags  = EXCLUDED.topic_tags
    """)
    with engine.begin() as conn:
        for c, vec in zip(chunks, embeddings):
            if vec is None:
                continue
            res = conn.execute(sql, {
                "tid":      c.get("tenant_id"),
                "stype":    c["source_type"],
                "stbl":     c["source_table"],
                "sid":      c["source_id"],
                "title":    c.get("title") or "",
                "content":  c["content"],
                "hash":     _hash(c["content"]),
                "meta":     json.dumps(c.get("metadata") or {}),
                "ministry": c.get("ministry"),
                "dateref":  c.get("date_ref"),
                "tags":     c.get("topic_tags") or [],
                "emb":      to_vector_literal(vec),
                "model":    EMBED_MODEL,
            })
            inserted += res.rowcount or 0
    return inserted


# ─────────────────────────────────────────────────────────────────────────
# PER-SOURCE INDEXERS
# ─────────────────────────────────────────────────────────────────────────

def _index_collection(chunks: list[dict], desc: str) -> dict:
    """Embed + upsert a list of chunks. Skips chunks whose hash already
    exists (idempotent re-runs are cheap)."""
    if not chunks:
        return {"chunks_proposed": 0, "chunks_new": 0, "embeddings_made": 0,
                "chunks_inserted": 0}

    # Compute hashes, drop chunks already indexed (same source_id + hash)
    by_table: dict = {}
    for c in chunks:
        by_table.setdefault(c["source_table"], []).append(c["source_id"])

    existing: set = set()
    for tbl, ids in by_table.items():
        existing |= _existing_hashes(tbl, ids)

    new_chunks: list[dict] = []
    for c in chunks:
        h = _hash(c["content"])
        if h in existing:
            continue
        new_chunks.append(c)

    if not new_chunks:
        logger.info(
            "[%s] all %d chunks already indexed (idempotent skip)",
            desc, len(chunks),
        )
        return {"chunks_proposed": len(chunks), "chunks_new": 0,
                "embeddings_made": 0, "chunks_inserted": 0}

    logger.info("[%s] embedding %d new chunks (skipped %d cached)",
                desc, len(new_chunks), len(chunks) - len(new_chunks))

    vecs = embed_texts([c["content"] for c in new_chunks])
    if vecs is None:
        logger.error("[%s] embedding API failed — skipping", desc)
        return {"chunks_proposed": len(chunks), "chunks_new": len(new_chunks),
                "embeddings_made": 0, "chunks_inserted": 0,
                "error": "embedding_failed"}

    inserted = _upsert_chunks(new_chunks, vecs)
    logger.info("[%s] upserted %d chunks", desc, inserted)
    return {"chunks_proposed": len(chunks), "chunks_new": len(new_chunks),
            "embeddings_made": sum(1 for v in vecs if v is not None),
            "chunks_inserted": inserted}


def index_pqs_for_tenant(tenant_id: int) -> dict:
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT * FROM parliamentary_questions
             WHERE tenant_id = :tid
               AND ((question_text IS NOT NULL AND question_text <> '')
                 OR (answer_text   IS NOT NULL AND answer_text   <> ''))
        """), {"tid": tenant_id}).mappings().all()
    chunks: list[dict] = []
    for r in rows:
        chunks.extend(chunk_pq_row(dict(r)))
    return _index_collection(chunks, f"pq[tenant={tenant_id}]")


def index_debates_for_tenant(tenant_id: int) -> dict:
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT * FROM parliamentary_debates WHERE tenant_id = :tid"),
            {"tid": tenant_id},
        ).mappings().all()
    chunks: list[dict] = []
    for r in rows:
        chunks.extend(chunk_debate_row(dict(r)))
    return _index_collection(chunks, f"debate[tenant={tenant_id}]")


def index_zero_hour_for_tenant(tenant_id: int) -> dict:
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT * FROM zero_hour_submissions WHERE tenant_id = :tid"),
            {"tid": tenant_id},
        ).mappings().all()
    chunks: list[dict] = []
    for r in rows:
        chunks.extend(chunk_zero_hour_row(dict(r)))
    return _index_collection(chunks, f"zero_hour[tenant={tenant_id}]")


def index_cases_for_tenant(tenant_id: int) -> dict:
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT * FROM cases
             WHERE tenant_id = :tid
               AND (is_deleted IS NULL OR is_deleted = false)
               AND raw_message IS NOT NULL AND raw_message <> ''
        """), {"tid": tenant_id}).mappings().all()
    chunks: list[dict] = []
    for r in rows:
        chunks.extend(chunk_case_row(dict(r)))
    return _index_collection(chunks, f"case[tenant={tenant_id}]")


def index_constituency_profile_for_tenant(tenant_id: int) -> dict:
    """Read the JSON profile from data/constituency_profiles/, if any."""
    profile_dir = Path(__file__).parent.parent / "data" / "constituency_profiles"
    if not profile_dir.is_dir():
        return {"chunks_proposed": 0, "chunks_new": 0, "embeddings_made": 0,
                "chunks_inserted": 0, "note": "no profile dir"}
    found_profile: Optional[dict] = None
    for p in profile_dir.glob("*.json"):
        try:
            data = json.loads(p.read_text())
        except Exception:
            continue
        meta = data.get("meta") or {}
        if int(meta.get("tenant_id") or 0) == tenant_id:
            found_profile = data
            break
    if not found_profile:
        return {"chunks_proposed": 0, "chunks_new": 0, "embeddings_made": 0,
                "chunks_inserted": 0, "note": "no profile for tenant"}
    chunks = chunk_constituency_profile(tenant_id, found_profile)
    return _index_collection(chunks, f"const_profile[tenant={tenant_id}]")


def index_schemes_global() -> dict:
    """Index schemes_db.json as global chunks (tenant_id=NULL)."""
    p = Path(__file__).parent.parent / "schemes_db.json"
    if not p.is_file():
        return {"chunks_proposed": 0, "chunks_new": 0, "embeddings_made": 0,
                "chunks_inserted": 0, "note": "no schemes_db.json"}
    try:
        schemes = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        logger.exception("schemes_db.json load failed: %s", e)
        return {"chunks_proposed": 0, "chunks_new": 0, "embeddings_made": 0,
                "chunks_inserted": 0, "error": str(e)}
    chunks: list[dict] = []
    for s in schemes:
        chunks.extend(chunk_scheme(s))
    return _index_collection(chunks, "schemes[global]")


# ─────────────────────────────────────────────────────────────────────────
# GLOBAL CORPUS — Phase 4
# ─────────────────────────────────────────────────────────────────────────

_INDEX_BATCH = 2000   # rows per embed batch for progress granularity

def index_global_pqs(limit: Optional[int] = None,
                     only_with_answers: bool = False,
                     rebuild: bool = False,
                     _progress: Optional[dict] = None) -> dict:
    """
    Index global_parliamentary_questions into memory_chunks (tenant_id=NULL).

    Each row is joined with global_mp_registry to get mp_name/party/constituency
    so the chunk clearly attributes the question to its author.

    Args:
        limit:             cap how many rows to process (None = all)
        only_with_answers: skip rows where answer_text is empty
        rebuild:           delete all existing global_pq_qa chunks first
        _progress:         optional dict updated with {done, total, label}

    The operation is idempotent — only re-embeds when content_hash changes.
    """
    ensure_schema()

    if rebuild:
        with engine.begin() as conn:
            conn.execute(text(
                "DELETE FROM memory_chunks WHERE source_type = 'global_pq_qa'"
            ))
        logger.info("index_global_pqs: deleted existing global_pq_qa chunks (rebuild=True)")

    # Ensure global tables exist
    try:
        from jobs.global_parliament_crawler import ensure_schema as _gc_schema
        _gc_schema()
    except Exception as e:
        logger.warning("global_parliament_crawler schema ensure failed: %s", e)

    # Join PQs with registry for MP attribution
    answer_filter = "AND gpq.answer_text IS NOT NULL AND gpq.answer_text != ''" if only_with_answers else ""
    limit_clause  = f"LIMIT {int(limit)}" if limit else ""

    sql = f"""
        SELECT gpq.id, gpq.prs_slug, gpq.house, gpq.session_name,
               gpq.question_number, gpq.question_type, gpq.subject,
               gpq.ministry, gpq.question_pdf_url,
               gpq.question_text, gpq.answer_text, gpq.date_asked,
               gpq.topic_tags,
               gmp.mp_name, gmp.party, gmp.constituency, gmp.state
          FROM global_parliamentary_questions gpq
          JOIN global_mp_registry gmp ON gmp.id = gpq.global_mp_id
         WHERE gpq.subject IS NOT NULL AND gpq.subject != ''
           {answer_filter}
         ORDER BY gpq.id
         {limit_clause}
    """

    try:
        with engine.connect() as conn:
            rows = conn.execute(text(sql)).mappings().all()
    except Exception as e:
        logger.exception("index_global_pqs: query failed (tables may not exist yet): %s", e)
        return {"chunks_proposed": 0, "chunks_new": 0, "embeddings_made": 0,
                "chunks_inserted": 0, "error": str(e)}

    if not rows:
        return {"chunks_proposed": 0, "chunks_new": 0, "embeddings_made": 0,
                "chunks_inserted": 0, "note": "no global PQs found"}

    logger.info("index_global_pqs: %d rows to process", len(rows))

    if _progress is not None:
        _progress["total"] = len(rows)
        _progress["done"]  = 0
        _progress["label"] = "embedding"

    # Process in batches so progress updates are meaningful
    totals = {"chunks_proposed": 0, "chunks_new": 0, "embeddings_made": 0, "chunks_inserted": 0}
    for batch_start in range(0, len(rows), _INDEX_BATCH):
        batch_rows = rows[batch_start: batch_start + _INDEX_BATCH]
        chunks: list[dict] = []
        for r in batch_rows:
            row_dict = dict(r)
            mp_info = {
                "mp_name":      row_dict.pop("mp_name", ""),
                "party":        row_dict.pop("party", ""),
                "constituency": row_dict.pop("constituency", ""),
                "state":        row_dict.pop("state", ""),
                "prs_slug":     row_dict.get("prs_slug", ""),
            }
            chunks.extend(chunk_global_pq_row(row_dict, mp_info))

        res = _index_collection(chunks, f"global_pqs[{batch_start}:{batch_start+len(batch_rows)}]")
        for k in totals:
            totals[k] += res.get(k, 0)

        if _progress is not None:
            _progress["done"] = min(batch_start + _INDEX_BATCH, len(rows))

    return totals


# ─────────────────────────────────────────────────────────────────────────
# TENANT-LEVEL ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────────────

def index_tenant(tenant_id: int,
                 sources: Optional[list[str]] = None,
                 rebuild: bool = False) -> dict:
    """
    Index all sources for one tenant. `sources` filters which to run;
    None = all. `rebuild=True` deletes existing chunks first.
    """
    ensure_schema()
    if rebuild:
        _delete_for_tenant(tenant_id)

    SOURCE_FUNCS = {
        "pq":         index_pqs_for_tenant,
        "debate":     index_debates_for_tenant,
        "zero_hour":  index_zero_hour_for_tenant,
        "case":       index_cases_for_tenant,
        "profile":    index_constituency_profile_for_tenant,
    }

    if sources:
        sources = [s for s in sources if s in SOURCE_FUNCS]
    else:
        sources = list(SOURCE_FUNCS.keys())

    started = datetime.utcnow()
    per_source = {}
    for s in sources:
        try:
            per_source[s] = SOURCE_FUNCS[s](tenant_id)
        except Exception as e:
            logger.exception("index source=%s failed: %s", s, e)
            per_source[s] = {"error": str(e)}

    finished = datetime.utcnow()
    return {
        "tenant_id":   tenant_id,
        "sources":     per_source,
        "started_at":  started.isoformat() + "Z",
        "finished_at": finished.isoformat() + "Z",
        "duration_sec": round((finished - started).total_seconds(), 2),
    }


def index_all_tenants(sources: Optional[list[str]] = None,
                      rebuild: bool = False) -> dict:
    ensure_schema()
    with engine.connect() as conn:
        tenant_ids = [r[0] for r in conn.execute(
            text("SELECT id FROM tenants WHERE is_active = true ORDER BY id")
        ).all()]
    out = {}
    for tid in tenant_ids:
        logger.info("▶ indexing tenant %s", tid)
        out[tid] = index_tenant(tid, sources=sources, rebuild=rebuild)
        time.sleep(0.5)
    return {"tenants_processed": len(tenant_ids), "per_tenant": out}


# ─────────────────────────────────────────────────────────────────────────
# STATS
# ─────────────────────────────────────────────────────────────────────────

def get_stats(tenant_id: Optional[int] = None) -> dict:
    ensure_schema()
    where = ""
    params: dict = {}
    if tenant_id:
        where = "WHERE tenant_id = :tid"
        params["tid"] = tenant_id
    sql = f"""
        SELECT source_type,
               COUNT(*)              AS chunk_count,
               MAX(indexed_at)       AS last_indexed
          FROM memory_chunks
        {where}
      GROUP BY source_type
      ORDER BY source_type
    """
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
        total_row = conn.execute(text(
            f"SELECT COUNT(*) AS total, MAX(indexed_at) AS last FROM memory_chunks {where}"
        ), params).mappings().fetchone()

    per_type = {r["source_type"]: {"count": r["chunk_count"],
                                   "last_indexed": str(r["last_indexed"]) if r["last_indexed"] else None}
                for r in rows}
    total = int(total_row["total"]) if total_row else 0
    last = str(total_row["last"]) if total_row and total_row["last"] else None
    return {"tenant_id": tenant_id, "total_chunks": total,
            "last_indexed": last, "per_source_type": per_type}


def get_stats_per_tenant() -> list[dict]:
    ensure_schema()
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT mc.tenant_id, t.name AS tenant_name,
                   COUNT(*) AS total_chunks,
                   MAX(mc.indexed_at) AS last_indexed
              FROM memory_chunks mc
         LEFT JOIN tenants t ON t.id = mc.tenant_id
          GROUP BY mc.tenant_id, t.name
          ORDER BY mc.tenant_id NULLS LAST
        """)).mappings().all()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    import argparse
    ap = argparse.ArgumentParser(description="Needle Brain Indexer (Phase 2)")
    ap.add_argument("--init-schema", action="store_true",
                    help="Create the memory_chunks table + pgvector extension")
    ap.add_argument("--tenant", type=int, help="Index one tenant by ID")
    ap.add_argument("--all", action="store_true", help="Index every active tenant")
    ap.add_argument("--schemes", action="store_true",
                    help="Index global schemes_db.json")
    ap.add_argument("--source", action="append",
                    choices=["pq", "debate", "zero_hour", "case", "profile"],
                    help="Limit to specific source types (can repeat)")
    ap.add_argument("--rebuild", action="store_true",
                    help="Delete existing tenant chunks before reindex")
    ap.add_argument("--stats", action="store_true",
                    help="Print indexing stats and exit")
    args = ap.parse_args()

    if args.init_schema:
        ensure_schema()
        print("Brain schema ensured (pgvector + memory_chunks).")
        sys.exit(0)

    if args.stats:
        if args.tenant:
            print(json.dumps(get_stats(args.tenant), indent=2, default=str))
        else:
            print(json.dumps({
                "global": get_stats(None),
                "per_tenant": get_stats_per_tenant(),
            }, indent=2, default=str))
        sys.exit(0)

    if args.schemes:
        print(json.dumps(index_schemes_global(), indent=2, default=str))
        sys.exit(0)

    if args.tenant:
        print(json.dumps(
            index_tenant(args.tenant, sources=args.source, rebuild=args.rebuild),
            indent=2, default=str,
        ))
    elif args.all:
        print(json.dumps(
            index_all_tenants(sources=args.source, rebuild=args.rebuild),
            indent=2, default=str,
        ))
    else:
        ap.print_help()
