from sansadx_backend.prompts import TAXONOMY_CATEGORIES
from sansadx_backend.unified_taxonomy import (
    CANONICAL_CATEGORIES,
    VALID_CATEGORIES,
    canonicalize_category,
    convergence_sector_for,
)


def test_prompt_categories_match_canonical_order():
    assert TAXONOMY_CATEGORIES == " | ".join(CANONICAL_CATEGORIES)


def test_valid_categories_set_matches_canonical_tuple():
    assert VALID_CATEGORIES == set(CANONICAL_CATEGORIES)


def test_legacy_labels_are_canonicalized():
    assert canonicalize_category("Public Health") == "Health"
    assert canonicalize_category("Infrastructure (State)") == "Infrastructure & Utilities"
    assert canonicalize_category("Food Supply") == "Government Schemes & Welfare"


def test_aliases_are_canonicalized():
    assert canonicalize_category("healthcare") == "Health"
    assert canonicalize_category("law and order") == "Law & Order"
    assert canonicalize_category("corruption") == "Bureaucratic / Administrative"


def test_convergence_sector_mapping_uses_canonicalized_input():
    assert convergence_sector_for("Public Health") == "Public Health Systems Strengthening"
    assert convergence_sector_for("corruption") == "Citizen Service Delivery Reform"
