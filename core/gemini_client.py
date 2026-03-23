"""
Gemini AI Client — singleton module.

All Gemini AI calls should import `get_gemini_client` from here
instead of instantiating `genai.Client` per-request.
"""
import os
import logging

logger = logging.getLogger("needle.gemini")

_client = None


def get_gemini_client():
    """Return a cached Gemini client. Creates one on first call."""
    global _client
    if _client is not None:
        return _client

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    try:
        from google import genai
        from google.genai import types as genai_types
        _client = genai.Client(
            api_key=api_key,
            http_options=genai_types.HttpOptions(timeout=30_000),  # 30 s hard limit
        )
        logger.info("Gemini client initialised (singleton, 30 s timeout)")
        return _client
    except Exception as e:
        logger.error(f"Gemini client init failed: {e}")
        return None
