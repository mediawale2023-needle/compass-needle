from sansadx_backend.prompts import (
    CONVERGENCE_PROGRAM_TYPES_TEXT,
    TAXONOMY_CATEGORIES,
)
from sansadx_backend.unified_taxonomy import (
    CANONICAL_CATEGORIES,
    CONVERGENCE_PROGRAM_TYPES,
    DEFAULT_PROBLEM_DOMAIN,
    PROBLEM_SUBDOMAINS_BY_DOMAIN,
    VALID_CATEGORIES,
    build_taxonomy_fields,
    canonicalize_category,
    canonicalize_convergence_program_type,
    canonicalize_problem_subdomain,
)


def test_prompt_problem_domains_match_canonical_order():
    assert TAXONOMY_CATEGORIES == " | ".join(CANONICAL_CATEGORIES)


def test_prompt_program_types_match_canonical_order():
    assert CONVERGENCE_PROGRAM_TYPES_TEXT == " | ".join(CONVERGENCE_PROGRAM_TYPES)


def test_valid_categories_set_matches_canonical_tuple():
    assert VALID_CATEGORIES == set(CANONICAL_CATEGORIES)


def test_every_domain_has_controlled_subdomains():
    assert set(PROBLEM_SUBDOMAINS_BY_DOMAIN) == set(CANONICAL_CATEGORIES)
    for subdomains in PROBLEM_SUBDOMAINS_BY_DOMAIN.values():
        assert subdomains


def test_general_and_legacy_labels_normalize_to_canonical_domains():
    assert canonicalize_category("General") == DEFAULT_PROBLEM_DOMAIN
    assert canonicalize_category("General Grievance") == DEFAULT_PROBLEM_DOMAIN
    assert canonicalize_category("Public Health") == "Health"
    assert canonicalize_category("Infrastructure (State)") == "Infrastructure & Utilities"
    assert canonicalize_category("Food Supply") == "Government Schemes & Welfare"


def test_subdomain_inference_is_domain_scoped():
    assert canonicalize_problem_subdomain(
        None,
        problem_domain="Law & Order",
        raw_text="Police FIR nahi likh rahi hai",
    ) == "FIR/Police Inaction"
    assert canonicalize_problem_subdomain(
        None,
        problem_domain="Bureaucratic / Administrative",
        raw_text="Aadhaar correction pending for months",
    ) == "Certificates/ID Documents"


def test_program_type_inference_uses_subdomain_mapping():
    assert canonicalize_convergence_program_type(
        None,
        problem_domain="Law & Order",
        problem_subdomain="Cybercrime/Fraud",
    ) == "Digitization/Data Systems"
    assert canonicalize_convergence_program_type(
        None,
        problem_domain="Housing & Land",
        problem_subdomain="PMAY/Housing Eligibility",
    ) == "Last-mile Access & Outreach"


def test_build_taxonomy_fields_returns_legacy_categories_mirror():
    fields = build_taxonomy_fields(
        problem_domain="Public Health",
        raw_text="PHC mein doctor nahi hai",
    )
    assert fields == {
        "problem_domain": "Health",
        "problem_subdomain": "Facility Access (PHC/CHC/Hospital)",
        "convergence_program_type": "Service Delivery Strengthening",
        "categories": ["Health"],
    }
