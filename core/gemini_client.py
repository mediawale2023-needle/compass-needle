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
        raw_client = genai.Client(
            api_key=api_key,
            http_options={"timeout": GEMINI_TIMEOUT_MS},
        )
        logger.info(f"Gemini client initialised (singleton, timeout={GEMINI_TIMEOUT_MS}ms)")
        _client = GeminiCircuitBreaker(raw_client)
        return _client
    except Exception as e:
        logger.error(f"Gemini client init failed: {e}")
        return None

import time

class CircuitBreakerOpenException(Exception):
    """Raised when the Gemini API circuit breaker is open."""
    pass

class GeminiCircuitBreaker:
    """
    Lightweight circuit breaker for Gemini. 
    State is shared globally since this is instanced as a singleton wrapper.
    """
    def __init__(self, real_client):
        self._real_client = real_client
        self._failures = 0
        self._last_failure_time = 0
        self._threshold = 3
        self._cooldown = 60  # seconds

    def _is_open(self):
        if self._failures >= self._threshold:
            if time.time() - self._last_failure_time > self._cooldown:
                # Half-open: allow a test request
                self._failures = self._threshold - 1 
                return False
            return True
        return False

    def _record_success(self):
        if self._failures > 0:
            logger.info("Gemini circuit breaker RESET (closed)")
            self._failures = 0

    def _record_failure(self):
        self._failures += 1
        self._last_failure_time = time.time()
        if self._failures >= self._threshold:
            logger.error(f"Gemini circuit breaker TRIPPED (open) for {self._cooldown}s")

    @property
    def models(self):
        breaker_self = self
        class ModelsProxy:
            def generate_content(self, *args, **kwargs):
                if breaker_self._is_open():
                    raise CircuitBreakerOpenException(f"Gemini generation skipped: Circuit breaker is OPEN ({breaker_self._failures} failures)")
                try:
                    resp = breaker_self._real_client.models.generate_content(*args, **kwargs)
                    breaker_self._record_success()
                    return resp
                except Exception as e:
                    logger.warning(f"Gemini API error inside circuit breaker: {e}")
                    breaker_self._record_failure()
                    raise
        return ModelsProxy()

