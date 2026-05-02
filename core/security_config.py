"""
Security Configuration Module
Centralized security settings and utilities
"""

import os
import logging
from datetime import timedelta

logger = logging.getLogger("needle.security")

# ============================================
# JWT CONFIGURATION
# ============================================
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    logger.warning("JWT_SECRET not set — security_config running in dev mode")
    JWT_SECRET = None
elif len(JWT_SECRET) < 32:
    logger.warning("JWT_SECRET is shorter than 32 characters — insecure")

JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60  # 1 hour
JWT_REFRESH_EXPIRE_DAYS = 7

# ============================================
# CORS CONFIGURATION
# ============================================
# Known production frontends — always allowed regardless of env var
_KNOWN_FRONTENDS = [
    "https://compass-needle-production.up.railway.app",
    "https://admin-production.up.railway.app",
]

raw_origins = os.getenv("ALLOWED_ORIGINS", "")
if raw_origins:
    ALLOWED_ORIGINS = [o.strip() for o in raw_origins.split(",") if o.strip()]
    # Merge known frontends
    for fe in _KNOWN_FRONTENDS:
        if fe not in ALLOWED_ORIGINS:
            ALLOWED_ORIGINS.append(fe)
else:
    if os.getenv("ENV", "development") == "production":
        ALLOWED_ORIGINS = list(_KNOWN_FRONTENDS)
    else:
        ALLOWED_ORIGINS = [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3001",
            *_KNOWN_FRONTENDS,
        ]
# Never use empty list — would block all origins and break login
if not ALLOWED_ORIGINS:
    ALLOWED_ORIGINS = list(_KNOWN_FRONTENDS) if os.getenv("ENV", "development") == "production" else ["http://localhost:3000"]

# ============================================
# RATE LIMITING
# ============================================
RATE_LIMIT_LOGIN = "5/minute"  # 5 attempts per minute
RATE_LIMIT_API = "100/minute"  # 100 requests per minute
RATE_LIMIT_UPLOAD = "10/minute"  # 10 uploads per minute

# ============================================
# FILE UPLOAD SECURITY
# ============================================
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_UPLOAD_TYPES = {"application/pdf"}
UPLOAD_TEMP_DIR = "/tmp/needle_uploads"

# ============================================
# PASSWORD POLICY
# ============================================
MIN_PASSWORD_LENGTH = 8
REQUIRE_UPPERCASE = True
REQUIRE_NUMBERS = True
REQUIRE_SPECIAL_CHARS = False

# ============================================
# SESSION SECURITY
# ============================================
SESSION_TIMEOUT_MINUTES = 60
SECURE_COOKIES = os.getenv("ENV", "development") == "production"
HTTPONLY_COOKIES = True
SAMESITE_COOKIES = "Strict"

# ============================================
# LOGGING & MONITORING
# ============================================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
SENTRY_DSN = os.getenv("SENTRY_DSN")

# ============================================
# SECURITY HEADERS
# ============================================
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}

# ============================================
# VALIDATION RULES
# ============================================
USERNAME_PATTERN = r"^[a-zA-Z0-9._-]+$"
USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 255

# ============================================
# AUDIT LOGGING
# ============================================
AUDIT_LOG_ENABLED = True
AUDIT_LOG_RETENTION_DAYS = 90

def validate_jwt_secret():
    """Validate JWT secret on startup."""
    if not JWT_SECRET:
        logger.warning("JWT_SECRET is not set — skipping validation")
        return
    if len(JWT_SECRET) < 32:
        logger.error("JWT_SECRET is not properly configured")
        raise ValueError("JWT_SECRET must be set and at least 32 characters")
    logger.info("JWT secret validation passed")

def validate_cors_origins():
    """Validate CORS origins on startup."""
    if not ALLOWED_ORIGINS:
        logger.warning("No ALLOWED_ORIGINS configured, using defaults")
    logger.info(f"CORS origins configured: {len(ALLOWED_ORIGINS)} origin(s)")

def validate_security_config():
    """Run all security validations on startup."""
    validate_jwt_secret()
    validate_cors_origins()
    logger.info("Security configuration validated successfully")
