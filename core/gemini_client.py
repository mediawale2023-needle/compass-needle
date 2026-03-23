"""
Gemini AI Client — singleton module.

All Gemini AI calls should import `get_gemini_client` from here
instead of instantiating `genai.Client` per-request.
"""
import os
import logging

logger = logging.getLogger("needle.gemini")

_client = None

# 30-second timeout for all Gemini API calls (in milliseconds).
# Prevents a slow/hanging Gemini response from blocking the entire API.
GEMINI_TIMEOUT_MS = 30_000


def get_gemini_client():
    """Return a cached Gemini client with a 30s timeout. Creates one on first call."""
    global _client
    if _client is not None:
        return _client

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    try:
        from google import genai
        _client = genai.Client(
            api_key=api_key,
            http_options={"timeout": GEMINI_TIMEOUT_MS},
        )
        logger.info(f"Gemini client initialised (singleton, timeout={GEMINI_TIMEOUT_MS}ms)")
        return _client
    except Exception as e:
        logger.error(f"Gemini client init failed: {e}")
        return None

