"""
Classification mode switch for the Briefcase taxonomy pipeline.

Modes:
  on     — taxonomy decisions (problem_domain/subdomain/convergence) are
           written to the case fields. Legacy behaviour.
  shadow — the taxonomy pipeline still runs on every message, but its output
           is stored ONLY inside case_metadata (``classification_shadow`` and
           the ``ai_category``/``ai_subcategory`` suggestion shown in the
           Briefcase triage banner). The case columns stay null and staff
           categorise manually. This is Phase-1 shadow mode from
           BRIEFCASE_INTELLIGENCE_ARCHITECTURE.md.

"off" is accepted as an alias of "shadow": the classification code is never
fully skipped, so re-enabling it later can be evaluated against the shadow
records gathered while it was dark.

Resolution order:
  1. Per-tenant override — a ``tenant_overrides`` row with
     ``override_type = 'classification_mode'`` and ``key = <tenant_id>``.
     Lets a pilot tenant flip back to ``on`` while everyone else stays shadow.
  2. ``CLASSIFICATION_MODE`` env var.
  3. Default: ``shadow``.

Intent lanes (emergency, personal request, greetings/silent-log, offensive)
are NOT governed by this switch — they are deterministic citizen-safety
routing, not taxonomy classification, and always stay on.
"""

from __future__ import annotations

import logging
import os
import time

logger = logging.getLogger("needle.classification_policy")

MODE_ON = "on"
MODE_SHADOW = "shadow"

_MODE_ALIASES = {
    "on": MODE_ON,
    "legacy": MODE_ON,
    "enabled": MODE_ON,
    "shadow": MODE_SHADOW,
    "off": MODE_SHADOW,
    "disabled": MODE_SHADOW,
    "hints_only": MODE_SHADOW,
}

_TENANT_CACHE_TTL_SECONDS = 60.0
_tenant_mode_cache: dict[int, tuple[float, str | None]] = {}


def _normalize_mode(raw) -> str | None:
    key = str(raw or "").strip().lower()
    return _MODE_ALIASES.get(key)


def default_classification_mode() -> str:
    """Global mode from the CLASSIFICATION_MODE env var (default: shadow)."""
    return _normalize_mode(os.environ.get("CLASSIFICATION_MODE")) or MODE_SHADOW


def _tenant_mode_override(tenant_id: int) -> str | None:
    """Per-tenant override from the tenant_overrides table, cached briefly.

    Any failure (no DB, table missing, bad value) falls back to None so the
    intake pipeline can never break because of this lookup.
    """
    now = time.monotonic()
    cached = _tenant_mode_cache.get(tenant_id)
    if cached and (now - cached[0]) < _TENANT_CACHE_TTL_SECONDS:
        return cached[1]

    mode: str | None = None
    try:
        from sansadx_backend.db import SessionLocal, TenantOverride

        db = SessionLocal()
        try:
            row = (
                db.query(TenantOverride)
                .filter(
                    TenantOverride.override_type == "classification_mode",
                    TenantOverride.key == str(tenant_id),
                )
                .order_by(TenantOverride.id.desc())
                .first()
            )
            if row:
                mode = _normalize_mode(row.value)
        finally:
            db.close()
    except Exception as exc:
        logger.debug("classification_mode tenant override lookup failed: %s", exc)

    _tenant_mode_cache[tenant_id] = (now, mode)
    return mode


def clear_classification_mode_cache() -> None:
    _tenant_mode_cache.clear()


def get_classification_mode(tenant_id: int | None = None) -> str:
    if tenant_id is not None:
        try:
            override = _tenant_mode_override(int(tenant_id))
        except Exception:
            override = None
        if override:
            return override
    return default_classification_mode()


def classification_writes_enabled(tenant_id: int | None = None) -> bool:
    """True when taxonomy decisions may be written to case fields."""
    return get_classification_mode(tenant_id) == MODE_ON
