"""Per-tenant communication language resolution.

Every MP/MLA office operates in a different linguistic context. Layer-1
heuristics (modules/case_comment_heuristics.py) must only load phrase
dictionaries for the languages a given office actually uses, both to stay
fast and to avoid false-positive matches from an unrelated language's
vocabulary. This module resolves that 3-4 language set per tenant:

1. Explicit override: tenants.config["communication_languages"], settable by
   ops for an office that wants something different from the state default.
2. State-based default: looked up from tenant_profiles.state.
3. Safe fallback: [Hindi, Hinglish, English] if state is unknown/unset — the
   most broadly useful combination nationally.

Language names match the canonical vocabulary in modules/localized_replies.py
(_LANG_ALIASES) so results plug directly into existing template lookups.
"""
from sansadx_backend.db import SessionLocal, Tenant, TenantProfile

# Default communication languages by state/UT. Every state includes English
# and Hinglish (Roman-script transliteration is near-universal in WhatsApp
# traffic) alongside its principal regional language(s).
STATE_DEFAULT_LANGUAGES: dict[str, list[str]] = {
    "andhra pradesh": ["Telugu", "English", "Hindi", "Hinglish"],
    "arunachal pradesh": ["Hindi", "English", "Hinglish"],
    "assam": ["Assamese", "Hindi", "English", "Hinglish"],
    "bihar": ["Hindi", "English", "Hinglish"],
    "chhattisgarh": ["Hindi", "English", "Hinglish"],
    "goa": ["Marathi", "English", "Hindi", "Hinglish"],
    "gujarat": ["Gujarati", "Hindi", "English", "Hinglish"],
    "haryana": ["Hindi", "English", "Hinglish"],
    "himachal pradesh": ["Hindi", "English", "Hinglish"],
    "jharkhand": ["Hindi", "English", "Hinglish"],
    "karnataka": ["Kannada", "English", "Hindi", "Hinglish"],
    "kerala": ["Malayalam", "English", "Hindi"],
    "madhya pradesh": ["Hindi", "English", "Hinglish"],
    "maharashtra": ["Marathi", "Hindi", "English", "Hinglish"],
    "manipur": ["Hindi", "English", "Hinglish"],
    "meghalaya": ["Hindi", "English", "Hinglish"],
    "mizoram": ["Hindi", "English", "Hinglish"],
    "nagaland": ["Hindi", "English", "Hinglish"],
    "odisha": ["Odia", "Hindi", "English", "Hinglish"],
    "punjab": ["Punjabi", "Hindi", "English", "Hinglish"],
    "rajasthan": ["Hindi", "English", "Hinglish"],
    "sikkim": ["Hindi", "English", "Hinglish"],
    "tamil nadu": ["Tamil", "English", "Hindi"],
    "telangana": ["Telugu", "English", "Hindi", "Hinglish"],
    "tripura": ["Bengali", "Hindi", "English", "Hinglish"],
    "uttar pradesh": ["Hindi", "English", "Hinglish"],
    "uttarakhand": ["Hindi", "English", "Hinglish"],
    "west bengal": ["Bengali", "Hindi", "English", "Hinglish"],
    # Union territories
    "andaman and nicobar islands": ["Hindi", "English", "Hinglish"],
    "chandigarh": ["Punjabi", "Hindi", "English", "Hinglish"],
    "dadra and nagar haveli and daman and diu": ["Gujarati", "Hindi", "English", "Hinglish"],
    "delhi": ["Hindi", "English", "Hinglish"],
    "jammu and kashmir": ["Urdu", "Hindi", "English", "Hinglish"],
    "ladakh": ["Urdu", "Hindi", "English", "Hinglish"],
    "lakshadweep": ["Malayalam", "English", "Hindi"],
    "puducherry": ["Tamil", "English", "Hindi"],
}

FALLBACK_LANGUAGES = ["Hindi", "Hinglish", "English"]

_tenant_language_cache: dict[int, list[str]] = {}


def _sanitize_language_list(raw) -> list[str] | None:
    if not isinstance(raw, list):
        return None
    cleaned = [str(v).strip() for v in raw if str(v or "").strip()]
    return cleaned or None


def resolve_tenant_languages(tenant_id: int) -> list[str]:
    """Return the 3-4 canonical language names configured for a tenant.

    Cached in-process per tenant_id: this is called on every inbound
    message and the underlying config changes rarely. Call
    clear_tenant_language_cache() after an admin edits a tenant's state or
    communication_languages override.
    """
    if tenant_id in _tenant_language_cache:
        return _tenant_language_cache[tenant_id]

    languages = _resolve_uncached(tenant_id)
    _tenant_language_cache[tenant_id] = languages
    return languages


def _resolve_uncached(tenant_id: int) -> list[str]:
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if tenant:
            override = _sanitize_language_list((tenant.config or {}).get("communication_languages"))
            if override:
                return override

        profile = db.query(TenantProfile).filter(TenantProfile.tenant_id == tenant_id).first()
        state = str(getattr(profile, "state", "") or "").strip().lower()
        if state and state in STATE_DEFAULT_LANGUAGES:
            return STATE_DEFAULT_LANGUAGES[state]
        return list(FALLBACK_LANGUAGES)
    except Exception:
        return list(FALLBACK_LANGUAGES)
    finally:
        db.close()


def clear_tenant_language_cache(tenant_id: int | None = None) -> None:
    if tenant_id is None:
        _tenant_language_cache.clear()
    else:
        _tenant_language_cache.pop(tenant_id, None)
