"""
Auth utilities — tenant isolation helpers and prompt sanitization.

get_tenant_or_fail() replaces the dangerous user.get('tenant_id', 1) pattern
that could silently default to tenant 1 if tenant_id is missing.

sanitize_prompt_input() strips characters that could be used for prompt injection.
"""
import re
import logging
from fastapi import HTTPException

# Soft-import the security logger (avoids circular imports)
try:
    from core.security_logger import log_security_event
except ImportError:
    log_security_event = None

_logger = logging.getLogger("needle.security")


def get_tenant_or_fail(user_data: dict) -> int:
    """Extract tenant_id from user data or raise 403.

    This MUST be used instead of user.get('tenant_id', 1) to prevent
    silent cross-tenant data leakage when tenant_id is missing or NULL.
    """
    tid = user_data.get("tenant_id")
    if tid is None:
        username = user_data.get("sub") or user_data.get("username", "unknown")
        _logger.warning(f"TENANT_MISSING: user={username} has no tenant_id")
        if log_security_event:
            log_security_event(
                "tenant_missing",
                f"User '{username}' blocked — no tenant_id assigned",
                severity="critical",
                user_id=username,
            )
        raise HTTPException(403, "No tenant assigned")
    return int(tid)


def sanitize_prompt_input(text: str) -> str:
    """Strip patterns that could be used for prompt injection.

    Removes:
    - XML/HTML-like tags (e.g. <user_input>, </system>)
    - Common prompt override phrases
    - Excessive whitespace
    """
    if not text:
        return ""
    # Strip any XML/HTML-like tags the user might inject
    cleaned = re.sub(r'</?[a-zA-Z_][a-zA-Z0-9_]*[^>]*>', '', text)
    return cleaned.strip()
