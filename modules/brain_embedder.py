"""
modules/brain_embedder.py — OpenAI embeddings wrapper for Needle Brain.

Uses `text-embedding-3-small` (1536 dim, $0.02 / 1M tokens — extremely
cheap). Falls back to the EMERGENT_LLM_KEY when OPENAI_API_KEY is not set.

Public API:

    embed_texts(texts: list[str]) -> list[list[float]]
    embed_one(text: str)          -> list[float]

Both return None / empty in catastrophic failure cases. Internally:
  • Truncates each text to ≤ 8000 chars before sending (the model's hard
    limit is 8191 tokens; ~32K chars; we stay well under).
  • Batches up to 100 texts per request.
  • Retries with exponential backoff on transient errors.

Pure utility module — no DB writes.
"""

from __future__ import annotations

import os
import time
import logging
from typing import Optional

logger = logging.getLogger("needle.brain_embedder")

EMBED_MODEL    = "text-embedding-3-small"
EMBED_DIM      = 1536
MAX_BATCH      = 100
MAX_TEXT_CHARS = 30000     # well below 8191 tokens (~32K chars) hard limit
RETRY_ATTEMPTS = 4
RETRY_BACKOFF  = 1.6


# ─────────────────────────────────────────────────────────────────────────
# OpenAI client (lazy)
# ─────────────────────────────────────────────────────────────────────────

_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    try:
        from openai import OpenAI
    except ImportError:
        logger.error("openai package not available")
        return None

    key = os.environ.get("OPENAI_API_KEY") or os.environ.get("EMERGENT_LLM_KEY")
    if not key:
        logger.error("Neither OPENAI_API_KEY nor EMERGENT_LLM_KEY is set — "
                     "Brain embeddings disabled")
        return None

    base_url = None
    if not os.environ.get("OPENAI_API_KEY") and os.environ.get("EMERGENT_LLM_KEY"):
        # Use Emergent's compatible OpenAI proxy
        base_url = os.environ.get(
            "EMERGENT_LLM_BASE_URL",
            "https://integrations.emergentagent.com/llm",
        )

    try:
        if base_url:
            _client = OpenAI(api_key=key, base_url=base_url)
        else:
            _client = OpenAI(api_key=key)
    except Exception as e:
        logger.exception("Failed to construct OpenAI client: %s", e)
        return None
    return _client


# ─────────────────────────────────────────────────────────────────────────
# CORE
# ─────────────────────────────────────────────────────────────────────────

def _trim(t: str) -> str:
    if not t:
        return ""
    if len(t) > MAX_TEXT_CHARS:
        return t[:MAX_TEXT_CHARS]
    return t


def embed_texts(texts: list[str]) -> Optional[list[list[float]]]:
    """
    Embed a list of texts. Returns a parallel list of 1536-float vectors.
    Returns None on hard failure (no client, persistent API error).
    Items that are empty / whitespace-only get a None placeholder in the
    result list so the caller can keep the index alignment.
    """
    if not texts:
        return []

    client = _get_client()
    if not client:
        return None

    # Pre-process: trim and remember which indices are empty
    cleaned: list[str] = []
    empty_idx: set = set()
    for i, t in enumerate(texts):
        t = (t or "").strip()
        if not t:
            empty_idx.add(i)
            cleaned.append(" ")    # placeholder, will be discarded
        else:
            cleaned.append(_trim(t))

    out: list[Optional[list[float]]] = [None] * len(texts)

    # Batched request
    for batch_start in range(0, len(cleaned), MAX_BATCH):
        batch = cleaned[batch_start: batch_start + MAX_BATCH]
        vecs = _embed_one_batch_with_retry(client, batch)
        if vecs is None:
            logger.error("embed_texts: batch %d-%d failed permanently",
                         batch_start, batch_start + len(batch))
            return None
        for i, v in enumerate(vecs):
            global_idx = batch_start + i
            if global_idx in empty_idx:
                out[global_idx] = None
            else:
                out[global_idx] = v

    return out


def _embed_one_batch_with_retry(client, batch: list[str]) -> Optional[list[list[float]]]:
    last_err = None
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            resp = client.embeddings.create(model=EMBED_MODEL, input=batch)
            return [d.embedding for d in resp.data]
        except Exception as e:
            last_err = e
            sleep = RETRY_BACKOFF ** attempt
            logger.warning(
                "embeddings batch attempt %d/%d failed: %s — retry in %.1fs",
                attempt, RETRY_ATTEMPTS, e, sleep,
            )
            time.sleep(sleep)
    logger.error("embeddings batch giving up after %d attempts: %s",
                 RETRY_ATTEMPTS, last_err)
    return None


def embed_one(text: str) -> Optional[list[float]]:
    """Convenience: embed a single string."""
    if not text or not text.strip():
        return None
    res = embed_texts([text])
    if not res:
        return None
    return res[0]


# ─────────────────────────────────────────────────────────────────────────
# pgvector serialisation helper
# ─────────────────────────────────────────────────────────────────────────

def to_vector_literal(vec: list[float]) -> str:
    """Format a float list as a pgvector literal string '[0.1, 0.2, ...]'.
    Bind this in SQL with `:v::vector`."""
    if vec is None:
        return None
    return "[" + ",".join(f"{x:.7f}" for x in vec) + "]"
