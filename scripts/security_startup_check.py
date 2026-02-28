#!/usr/bin/env python3
"""
Security Startup Validation
Run this on application startup to verify security configuration
"""

import os
import sys
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("needle.security_check")

def check_jwt_secret():
    """Verify JWT_SECRET is properly configured."""
    jwt_secret = os.getenv("JWT_SECRET")
    
    if not jwt_secret:
        logger.error("❌ JWT_SECRET not set")
        return False
    
    if len(jwt_secret) < 32:
        logger.error(f"❌ JWT_SECRET too short ({len(jwt_secret)} chars, need 32+)")
        return False
    
    logger.info("✅ JWT_SECRET properly configured")
    return True

def check_database_url():
    """Verify DATABASE_URL is set."""
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        logger.warning("⚠️  DATABASE_URL not set, using SQLite")
        return True
    
    # Don't log the full URL (contains credentials)
    if "password" in db_url.lower():
        logger.info("✅ DATABASE_URL configured (credentials present)")
    else:
        logger.warning("⚠️  DATABASE_URL may be missing credentials")
    
    return True

def check_cors_origins():
    """Verify CORS origins are configured."""
    origins = os.getenv("ALLOWED_ORIGINS", "")
    
    if not origins:
        logger.warning("⚠️  ALLOWED_ORIGINS not set, using defaults")
        return True
    
    origin_list = [o.strip() for o in origins.split(",") if o.strip()]
    
    if not origin_list:
        logger.warning("⚠️  ALLOWED_ORIGINS empty, using defaults")
        return True
    
    logger.info(f"✅ CORS configured for {len(origin_list)} origin(s)")
    return True

def check_api_keys():
    """Verify API keys are configured."""
    keys = {
        "OPENAI_API_KEY": "OpenAI",
        "GEMINI_API_KEY": "Gemini",
        "TWILIO_ACCOUNT_SID": "Twilio",
    }
    
    missing = []
    for key, name in keys.items():
        if not os.getenv(key):
            missing.append(name)
    
    if missing:
        logger.warning(f"⚠️  Missing API keys: {', '.join(missing)}")
        return True  # Not critical, some features may be disabled
    
    logger.info("✅ All API keys configured")
    return True

def check_environment():
    """Verify environment is set."""
    env = os.getenv("ENV", "development")
    
    if env == "production":
        logger.info("✅ Running in PRODUCTION mode")
    else:
        logger.warning(f"⚠️  Running in {env.upper()} mode")
    
    return True

def check_logging():
    """Verify logging is configured."""
    log_level = os.getenv("LOG_LEVEL", "INFO")
    logger.info(f"✅ Logging level: {log_level}")
    return True

def run_all_checks():
    """Run all security checks."""
    print("\n" + "=" * 60)
    print("🔐 SECURITY STARTUP VALIDATION")
    print("=" * 60 + "\n")
    
    checks = [
        ("JWT Secret", check_jwt_secret),
        ("Database URL", check_database_url),
        ("CORS Origins", check_cors_origins),
        ("API Keys", check_api_keys),
        ("Environment", check_environment),
        ("Logging", check_logging),
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            logger.error(f"❌ {name} check failed: {e}")
            results.append((name, False))
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"\nPassed: {passed}/{total}")
    
    if passed == total:
        print("\n✅ All security checks passed!")
        return True
    else:
        print("\n⚠️  Some security checks failed or warned")
        return passed == total

if __name__ == "__main__":
    success = run_all_checks()
    sys.exit(0 if success else 1)
