"""
Profile Loader — Single source of truth for tenant profile data.

All modules (news_intel, drafter, ui_theme, mp_dashboard) should use
load_tenant_profile(tenant_id) instead of reading tenant_profile.json directly.
"""
import json
import os
import streamlit as st


def _load_from_db(tenant_id):
    """Query tenant_profiles table for the given tenant_id."""
    try:
        from db import SessionLocal, TenantProfile
        db = SessionLocal()
        try:
            row = db.query(TenantProfile).filter(
                TenantProfile.tenant_id == tenant_id
            ).first()
            if row:
                extra = row.profile_data or {}
                return {
                    "mp_name": row.mp_name or "",
                    "constituency": row.constituency or "",
                    "state": row.state or "",
                    "house": row.house or "Lok Sabha",
                    "party": row.party or "Independent",
                    "key_facts": extra.get("key_facts", []),
                    "languages": extra.get("languages", ["English", "Hindi"]),
                    "vocabulary_guide": extra.get("vocabulary_guide", {}),
                    "sovereignty_rules": extra.get("sovereignty_rules", ""),
                    "alt_names": extra.get("alt_names", []),
                }
        finally:
            db.close()
    except Exception:
        pass
    return None


def _load_from_json():
    """Fallback: read the legacy tenant_profile.json file."""
    try:
        with open("tenant_profile.json", "r", encoding="utf-8") as f:
            profile = json.load(f)
        # Normalise to expected shape
        return {
            "mp_name": profile.get("mp_name", ""),
            "constituency": profile.get("constituency", ""),
            "state": profile.get("state", ""),
            "house": profile.get("house", "Lok Sabha"),
            "party": profile.get("party", "Independent"),
            "key_facts": profile.get("key_facts", []),
            "languages": profile.get("languages", ["English", "Hindi"]),
            "vocabulary_guide": profile.get("vocabulary_guide", {}),
            "sovereignty_rules": profile.get("sovereignty_rules", ""),
            "alt_names": [],
        }
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return None


_EMPTY_PROFILE = {
    "mp_name": "Member of Parliament",
    "constituency": "India",
    "state": "",
    "house": "Lok Sabha",
    "party": "Independent",
    "key_facts": [],
    "languages": ["English", "Hindi"],
    "vocabulary_guide": {},
    "sovereignty_rules": "",
    "alt_names": [],
}


def load_tenant_profile(tenant_id=None):
    """
    Load the tenant profile for the given tenant_id.

    Resolution order:
      1. Database (tenant_profiles table)
      2. Legacy tenant_profile.json
      3. Empty defaults

    If tenant_id is None, tries st.session_state.tenant_id.
    """
    if tenant_id is None:
        tenant_id = st.session_state.get("tenant_id")

    # 1. Try database
    if tenant_id is not None:
        profile = _load_from_db(tenant_id)
        if profile:
            return profile

    # 2. Fall back to JSON file
    profile = _load_from_json()
    if profile:
        return profile

    # 3. Empty defaults
    return dict(_EMPTY_PROFILE)
