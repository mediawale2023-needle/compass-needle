"""
csr_discovery.py — CSR pipeline logic (pure Python, no Streamlit).
UI is handled by the Next.js frontend via /api/csr/* endpoints.
"""
import json
import logging
import os
import pandas as pd

logger = logging.getLogger("needle.csr_discovery")


def get_live_gaps(tenant_id: int):
    """
    Returns top grievance clusters (category, volume, area) for a tenant.
    Imported by api_router.py for /api/csr/strategic-matches.
    Falls back gracefully if DB is unavailable.
    """
    try:
        from api_router import get_live_gaps as _get_live_gaps
        return _get_live_gaps(tenant_id)
    except Exception as e:
        logger.warning(f"get_live_gaps fallback: {e}")
        return []


def load_csr_data(filepath: str = "csr_discovery.json"):
    """Load CSR company data from JSON file."""
    try:
        with open(filepath, "r") as f:
            data = json.load(f)
        return pd.DataFrame(data)
    except FileNotFoundError:
        logger.error(f"CSR data file not found: {filepath}")
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"Error loading CSR data: {e}")
        return pd.DataFrame()


def get_strategic_matches(tenant_id: int, csr_filepath: str = "csr_discovery.json"):
    """
    Cross-reference high-volume grievance clusters with CSR-eligible companies.
    Returns list of match dicts for API consumption.
    """
    df = load_csr_data(csr_filepath)
    gaps = get_live_gaps(tenant_id)

    if df.empty or not gaps:
        return []

    category_to_sector = {
        "water": ["Water", "Rural Dev"],
        "road": ["Infrastructure", "Community Dev"],
        "electricity": ["Infrastructure", "Community Dev"],
        "health": ["Health"],
        "education": ["Education"],
        "sanitation": ["Health", "Water"],
        "housing": ["Rural Dev", "Community Dev"],
        "employment": ["Skill Dev", "Education"],
    }

    results = []
    for (gap_category, gap_volume, gap_area) in gaps:
        cat_lower = (gap_category or "").lower()
        matched_sectors = next(
            (sectors for key, sectors in category_to_sector.items() if key in cat_lower),
            ["Community Dev"]
        )

        badge = "CRITICAL CRISIS (500+)" if gap_volume >= 500 else \
                "MAJOR ISSUE (200+)" if gap_volume >= 200 else \
                "HIGH DEMAND (100+)"

        if 'Sector' in df.columns:
            mask = df['Sector'].str.contains('|'.join(matched_sectors), case=False, na=False)
            matching_companies = df[mask].head(3).to_dict('records')
        else:
            matching_companies = []

        results.append({
            "category": gap_category,
            "volume": gap_volume,
            "area": gap_area,
            "badge": badge,
            "matched_companies": matching_companies,
        })

    return results


def generate_csr_pitch_prompt(company: str, area: str, category: str, volume: int, mp_name: str, constituency: str) -> str:
    """Build a prompt for AI pitch generation."""
    return f"""
Act as a Senior Advisor to an Indian Member of Parliament.
Write a formal CSR Partnership Proposal for {company} for a project in {area}.
MP: {mp_name}, Member of Parliament for {constituency}
Context:
- Issue: {category} (CRITICAL: Verified by {volume} unique citizen reports).
- Urgency: High-volume community gap requiring immediate CSR intervention.
Include: Concept Note, Impact KPIs, SDG Mapping, and an MP Signature line.
Tone: Professional, authoritative, and data-driven.
"""
