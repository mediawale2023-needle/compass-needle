"""
Unified taxonomy and crosswalk helpers for grievance -> convergence workflows.

This module is the single source of truth for:
1) Canonical grievance domains (9)
2) Ingestion aliases that should collapse into canonical domains
3) Legacy labels (old CSR pipeline labels) -> canonical domains
4) Canonical domain -> convergence sector mapping
"""

from __future__ import annotations

# Canonical grievance domains in canonical display order.
CANONICAL_CATEGORIES = (
    "Infrastructure & Utilities",
    "Housing & Land",
    "Health",
    "Education",
    "Government Schemes & Welfare",
    "Agriculture",
    "Social Issues",
    "Law & Order",
    "Bureaucratic / Administrative",
)

# Set form for fast membership checks.
VALID_CATEGORIES = set(CANONICAL_CATEGORIES)


# Ingestion aliases -> canonical domain
CATEGORY_ALIASES = {
    "infrastructure": "Infrastructure & Utilities",
    "infrastructure & utility": "Infrastructure & Utilities",
    "infrastructure (state)": "Infrastructure & Utilities",
    "infrastructure(state)": "Infrastructure & Utilities",
    "energy": "Infrastructure & Utilities",
    "water": "Infrastructure & Utilities",
    "sanitation": "Infrastructure & Utilities",
    "civic amenities": "Infrastructure & Utilities",
    "transport": "Infrastructure & Utilities",
    "telecom": "Infrastructure & Utilities",
    "railways": "Infrastructure & Utilities",
    "road": "Infrastructure & Utilities",
    "roads": "Infrastructure & Utilities",
    "electricity": "Infrastructure & Utilities",
    "revenue & land": "Housing & Land",
    "land": "Housing & Land",
    "housing": "Housing & Land",
    "land records": "Housing & Land",
    "public health": "Health",
    "health & sanitation": "Health",
    "medical": "Health",
    "healthcare": "Health",
    "education (central)": "Education",
    "education (state)": "Education",
    "school": "Education",
    "food supply": "Government Schemes & Welfare",
    "banking & finance": "Government Schemes & Welfare",
    "labor & employment": "Government Schemes & Welfare",
    "labour & employment": "Government Schemes & Welfare",
    "welfare": "Government Schemes & Welfare",
    "government schemes": "Government Schemes & Welfare",
    "schemes": "Government Schemes & Welfare",
    "pension": "Government Schemes & Welfare",
    "ration": "Government Schemes & Welfare",
    "farming": "Agriculture",
    "farmer": "Agriculture",
    "crop": "Agriculture",
    "law and order": "Law & Order",
    "police": "Law & Order",
    "crime": "Law & Order",
    "security": "Law & Order",
    "bureaucratic": "Bureaucratic / Administrative",
    "administrative": "Bureaucratic / Administrative",
    "bureaucratic/administrative": "Bureaucratic / Administrative",
    "bureaucratic/ administrative": "Bureaucratic / Administrative",
    "civic admin": "Bureaucratic / Administrative",
    "external affairs": "Bureaucratic / Administrative",
    "postal services": "Bureaucratic / Administrative",
    "corruption": "Bureaucratic / Administrative",
    "social issue": "Social Issues",
    "caste": "Social Issues",
    "women": "Social Issues",
    "general grievance": "Infrastructure & Utilities",
    "general": "Infrastructure & Utilities",
}


# Legacy labels that still appear in CSR pipeline or old records -> canonical domain
LEGACY_TO_CANONICAL = {
    "Water": "Infrastructure & Utilities",
    "Infrastructure": "Infrastructure & Utilities",
    "Infrastructure (State)": "Infrastructure & Utilities",
    "Energy": "Infrastructure & Utilities",
    "Education (Central)": "Education",
    "Public Health": "Health",
    "Sanitation": "Infrastructure & Utilities",
    "Civic Amenities": "Infrastructure & Utilities",
    "Transport": "Infrastructure & Utilities",
    "Food Supply": "Government Schemes & Welfare",
    "General Grievance": "Infrastructure & Utilities",
    "General": "Infrastructure & Utilities",
}


# Canonical domain -> convergence sector label used in outreach collateral
CATEGORY_TO_CONVERGENCE_SECTOR = {
    "Infrastructure & Utilities": "Public Infrastructure & Essential Services",
    "Housing & Land": "Housing Security & Land Rights Support",
    "Health": "Public Health Systems Strengthening",
    "Education": "School & Learning Outcomes",
    "Government Schemes & Welfare": "Welfare Access & Financial Inclusion",
    "Agriculture": "Farmer Resilience & Agri-Livelihoods",
    "Social Issues": "Social Protection & Inclusion",
    "Law & Order": "Community Safety & Prevention",
    "Bureaucratic / Administrative": "Citizen Service Delivery Reform",
}


def canonicalize_category(category: str | None) -> str:
    """
    Normalize any incoming category/legacy label to canonical grievance domain.
    """
    if not category:
        return "Infrastructure & Utilities"

    value = str(category).strip()
    if not value:
        return "Infrastructure & Utilities"

    if value in VALID_CATEGORIES:
        return value

    if value in LEGACY_TO_CANONICAL:
        return LEGACY_TO_CANONICAL[value]

    lowered = value.lower()
    if lowered in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[lowered]

    return "Infrastructure & Utilities"


def convergence_sector_for(category: str | None) -> str:
    """
    Return convergence sector label for any category input.
    """
    canonical = canonicalize_category(category)
    return CATEGORY_TO_CONVERGENCE_SECTOR.get(canonical, "General Convergence")
