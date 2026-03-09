"""
Security Event Logger — emits structured security events to both
Python logging and Sentry for alerting.

Events are tagged with:
- security.event_type: e.g. "tenant_missing", "jwt_invalid", "auth_failed"
- security.severity: "critical", "high", "medium", "low"

In the Sentry dashboard, create an alert rule:
  IF tag[security.event_type] IS SET → Send Slack/Email notification.
"""
import logging
from typing import Optional

logger = logging.getLogger("needle.security")

# Try to import Sentry; if not available, events are still logged.
try:
    import sentry_sdk
    _sentry_available = True
except ImportError:
    _sentry_available = False


def log_security_event(
    event_type: str,
    message: str,
    *,
    severity: str = "high",
    user_id: Optional[str] = None,
    tenant_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    extra: Optional[dict] = None,
):
    """Log a security event to Python logger + Sentry.

    Args:
        event_type: Short tag, e.g. "tenant_missing", "jwt_invalid"
        message: Human-readable description
        severity: "critical" | "high" | "medium" | "low"
        user_id: Username or user identifier (if available)
        tenant_id: Relevant tenant ID (if available)
        ip_address: Client IP (if available)
        extra: Any additional context
    """
    log_data = {
        "event_type": event_type,
        "severity": severity,
        "user_id": user_id,
        "tenant_id": tenant_id,
        "ip_address": ip_address,
        **(extra or {}),
    }

    # Python structured log (always fires)
    log_line = f"SECURITY [{severity.upper()}] {event_type}: {message} | {log_data}"
    if severity in ("critical", "high"):
        logger.warning(log_line)
    else:
        logger.info(log_line)

    # Sentry event (fires if SDK available and DSN configured)
    if _sentry_available:
        with sentry_sdk.new_scope() as scope:
            scope.set_tag("security.event_type", event_type)
            scope.set_tag("security.severity", severity)
            if user_id:
                scope.set_user({"username": user_id})
            if tenant_id is not None:
                scope.set_tag("tenant_id", str(tenant_id))
            if ip_address:
                scope.set_tag("client_ip", ip_address)
            scope.set_context("security_event", log_data)

            # Use capture_message (not capture_exception) so it appears
            # as a distinct Sentry issue, easy to alert on.
            sentry_sdk.capture_message(
                f"[SECURITY] {event_type}: {message}",
                level="warning" if severity in ("critical", "high") else "info",
            )
"""
Sentry Alert Setup (one-time, in the Sentry dashboard):

1. Go to Alerts → Create Alert → Issues
2. Condition: "An event's tags match: security.event_type IS SET"
3. Action: Send notification via Slack / Email
4. Rate limit: At most once per 5 minutes (to avoid noise)

This will fire whenever get_tenant_or_fail blocks a user or
a JWT token is invalid — the exact events that matter for pilot monitoring.
"""
