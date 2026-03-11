"""
Rate limiting configuration using SlowAPI.
"""
import os
import logging
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request
import jwt
from jwt.exceptions import PyJWTError as JWTError

logger = logging.getLogger("needle.rate_limiter")

JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"


def _get_key(request: Request) -> str:
    """Extract username from JWT for authenticated endpoints, or IP for anonymous."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer ") and JWT_SECRET:
        token = auth[7:]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            username = payload.get("sub")
            if username:
                return username
        except JWTError:
            pass
    return get_remote_address(request)


limiter = Limiter(key_func=_get_key)

# Rate limit strings
RATE_AI = "3/minute"
RATE_LOGIN = "5/minute"
RATE_WEBHOOK = "20/minute"
RATE_GENERAL = "100/minute"
