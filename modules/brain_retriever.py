"""
modules/brain_retriever.py — Semantic retrieval over the Needle Brain.

Given a free-text query and a tenant_id, returns the top-K most relevant
chunks from `memory_chunks`, optionally filtered by source_type / ministry
/ date / cross-tenant scope.

Used by:
  • api_router.py drafter (letter / PQ generation)  → context block
  • api_router.py copilot  (chat + analyse)         → grounded answers
  • admin_api.py brain playground                   → debugging UI

Public API:

    retrieve(
        tenant_id,
        query_text,
        source_types = None,          # None = all
        k             = 12,
        ministry      = None,
        include_global= True,         # also pull tenant_id IS NULL chunks (schemes)
        include_cross_mp = False,     # Phase 4: pull other MPs' PQs/answers
        date_after    = None,         # YYYY-MM-DD
    ) -> list[ChunkResult]

    format_for_prompt(chunks, label="REFERENCE MATERIAL") -> str

A ChunkResult dict has:

    id, source_type, source_table, source_id, title, content,
    metadata, ministry, date_ref, topic_tags, score, citation
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import text

logger = logging.getLogger("needle.brain_retriever")

DEFAULT_K          = 12
MAX_K              = 50
DISTANCE_THRESHOLD = 0.55      # cosine distance <= 0.55 is broadly relevant


# Lazy DB engine import (so this module is importable in test contexts)
def _engine():
    from sansadx_backend.db import engine
    return engine


# ─────────────────────────────────────────────────────────────────────────
# CORE
# ─────────────────────────────────────────────────────────────────────────

def retrieve(
    tenant_id: Optional[int],
    query_text: str,
    source_types: Optional[list[str]] = None,
    k: int = DEFAULT_K,
    ministry: Optional[str] = None,
    include_global: bool = True,
    include_cross_mp: bool = False,
    date_after: Optional[str] = None,
) -> list[dict]:
    """
    Run semantic similarity search. See module docstring for full contract.
    Returns a list of ChunkResult dicts ordered by descending relevance.

    Returns [] when:
      • Embeddings are unavailable (no API key)
      • The query embedding fails
      • No chunks pass the distance threshold
    """
    if not query_text or not query_text.strip():
        return []

    from modules.brain_embedder import embed_one, to_vector_literal

    qvec = embed_one(query_text.strip()[:4000])
    if not qvec:
        logger.warning("retrieve: query embedding failed for %r",
                       (query_text or "")[:80])
        return []

    qvec_lit = to_vector_literal(qvec)
    k = max(1, min(int(k or DEFAULT_K), MAX_K))

    # Build dynamic WHERE clause
    where = ["embedding IS NOT NULL"]
    params: dict = {"qvec": qvec_lit, "k": k}

    if include_cross_mp:
        # No tenant restriction at all — for "what have all MPs asked about X"
        pass
    elif tenant_id is not None and include_global:
        where.append("(tenant_id = :tid OR tenant_id IS NULL)")
        params["tid"] = tenant_id
    elif tenant_id is not None:
        where.append("tenant_id = :tid")
        params["tid"] = tenant_id
    elif include_global:
        where.append("tenant_id IS NULL")

    if source_types:
        where.append("source_type = ANY(:stypes)")
        params["stypes"] = list(source_types)

    if ministry:
        where.append("LOWER(ministry) LIKE LOWER(:min)")
        params["min"] = f"%{ministry}%"

    if date_after:
        where.append("date_ref >= :dafter")
        params["dafter"] = date_after

    sql = f"""
        SELECT
            id, tenant_id, source_type, source_table, source_id,
            title, content, metadata, ministry, date_ref, topic_tags,
            (embedding <=> CAST(:qvec AS vector)) AS distance
          FROM memory_chunks
         WHERE {' AND '.join(where)}
      ORDER BY embedding <=> CAST(:qvec AS vector)
         LIMIT :k
    """

    try:
        with _engine().connect() as conn:
            rows = conn.execute(text(sql), params).mappings().all()
    except Exception as e:
        logger.exception("retrieve: SQL failed (pgvector ext missing?): %s", e)
        return []

    results = []
    for r in rows:
        d = dict(r)
        dist = float(d.pop("distance") or 1.0)
        d["score"] = round(1.0 - dist, 4)         # convert cosine distance → similarity
        if dist > DISTANCE_THRESHOLD * 1.2:        # very loose cutoff
            continue
        d["citation"] = _build_citation(d)
        results.append(d)
    return results


def _build_citation(c: dict) -> str:
    """Human-readable citation for a chunk, used in the prompt."""
    st = c.get("source_type") or ""
    md = c.get("metadata") or {}
    if st == "pq_qa":
        qn = md.get("real_question_number") or md.get("question_number") or ""
        return (
            f"PQ #{qn} ({(md.get('question_type') or '').title()}) — "
            f"{md.get('ministry') or ''} — {c.get('date_ref') or ''}"
        ).strip(" —")
    if st == "global_pq_qa":
        mp  = md.get("mp_name") or md.get("prs_slug") or "Unknown MP"
        pty = md.get("party") or ""
        con = md.get("constituency") or ""
        attr = f"{mp} ({pty}, {con})" if pty else mp
        return (
            f"Cross-MP PQ — {md.get('ministry') or ''} — {c.get('date_ref') or ''} "
            f"[{attr}]"
        ).strip()
    if st == "debate_speech":
        return f"Debate: {md.get('topic') or c.get('title')} — {c.get('date_ref') or ''}".strip(" —")
    if st == "zero_hour":
        return f"Zero Hour ({c.get('date_ref') or ''}): {md.get('subject') or ''}".strip()
    if st.startswith("const_"):
        sub = st.replace("const_", "")
        return f"Constituency Profile / {sub} — {md.get('constituency') or ''}".strip()
    if st == "case_summary":
        return f"Citizen grievance #{c.get('source_id')} ({md.get('category') or ''})"
    if st == "scheme":
        return f"Scheme: {md.get('name') or c.get('title')} — {md.get('ministry') or ''}".strip(" —")
    return c.get("title") or st


def format_for_prompt(chunks: list[dict], label: str = "REFERENCE MATERIAL") -> str:
    """
    Stitch retrieved chunks into a single, citation-numbered block ready to
    paste into a drafter / copilot prompt:

        ### REFERENCE MATERIAL
        [1] PQ #6230 (Unstarred) — Food Processing Industries — 2026-04-02
            QUESTION: ...
            ANSWER: ...

        [2] Constituency Profile / challenge — Belagavi
            CHALLENGE: Mahadayi / Kalasa Banduri Water Dispute ...

    Drafter prompts should instruct the LLM to reference [n] when citing
    facts.
    """
    if not chunks:
        return ""
    lines = [f"### {label}", ""]
    for i, c in enumerate(chunks, start=1):
        cite = c.get("citation") or c.get("title") or c.get("source_type")
        body = (c.get("content") or "").strip()
        # Trim the per-chunk preview so the whole block stays manageable
        if len(body) > 1200:
            body = body[:1200] + " […]"
        lines.append(f"[{i}] {cite}")
        # Indent body for readability
        for ln in body.split("\n"):
            lines.append(f"    {ln}")
        lines.append("")
    return "\n".join(lines).strip()


# ─────────────────────────────────────────────────────────────────────────
# CONVENIENCE: pre-baked retrieval profiles for drafter / copilot
# ─────────────────────────────────────────────────────────────────────────

DRAFT_LETTER_SOURCES = [
    "pq_qa",
    "const_challenge", "const_priority", "const_overview", "const_economy",
    "case_summary",
    "scheme",
]

DRAFT_PQ_SOURCES = [
    "pq_qa",
    "global_pq_qa",           # Phase 4: other MPs' PQs + ministry answers
    "const_challenge", "const_priority",
    "scheme",
    "debate_speech",
]

COPILOT_SOURCES = [
    "pq_qa",
    "global_pq_qa",           # Phase 4: cross-MP intelligence
    "const_challenge", "const_priority", "const_overview",
    "const_political", "const_assembly", "const_economy",
    "const_social", "const_culture", "const_fact",
    "case_summary",
    "scheme",
    "debate_speech",
    "zero_hour",
]


def retrieve_for_draft_letter(tenant_id: int, subject: str, key_points: str,
                              ministry: Optional[str] = None,
                              k: int = 10) -> list[dict]:
    """Drafter helper. Combines subject + key_points as the query."""
    q = (subject or "").strip()
    if key_points:
        q += "\n" + key_points
    return retrieve(
        tenant_id=tenant_id,
        query_text=q,
        source_types=DRAFT_LETTER_SOURCES,
        ministry=ministry,
        k=k,
    )


def retrieve_for_draft_pq(tenant_id: int, subject: str, ministry: str,
                          include_cross_mp: bool = True,
                          k: int = 12) -> list[dict]:
    """
    Drafter helper for new PQ generation. Pulls:
      • this MP's prior PQs on same subject (avoid duplication)
      • OPTIONALLY other MPs' PQs + ministry answers on same subject (Phase 4)
      • constituency challenges / priorities, schemes
    """
    return retrieve(
        tenant_id=tenant_id,
        query_text=f"{subject} | {ministry}",
        source_types=DRAFT_PQ_SOURCES,
        ministry=ministry,
        k=k,
        include_cross_mp=include_cross_mp,
    )


def retrieve_for_copilot(tenant_id: int, query: str, k: int = 12) -> list[dict]:
    """Copilot chat helper. Wide net, all source types, includes globals."""
    return retrieve(
        tenant_id=tenant_id,
        query_text=query,
        source_types=COPILOT_SOURCES,
        k=k,
    )
