from sansadx_backend.db import derive_case_taxonomy_state
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
    infer_emergency_taxonomy_override,
    infer_personal_request_category,
    infer_silent_log_category,
    looks_like_contextless_media_message,
)
from modules.emergency_keywords import detect_emergency_severity


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


def test_derive_case_taxonomy_state_backfills_legacy_general_rows():
    payload = derive_case_taxonomy_state(
        category="General Grievance",
        raw_message="Pension nahi mil rahi hai",
        status="completed",
        case_metadata={"summary": "Pension nahi mil rahi hai"},
    )
    assert payload["category"] == "Government Schemes & Welfare"
    assert payload["problem_domain"] == "Government Schemes & Welfare"
    assert payload["problem_subdomain"] == "Pension"
    assert payload["convergence_program_type"] == "Last-mile Access & Outreach"
    assert payload["case_metadata"]["categories"] == ["Government Schemes & Welfare"]


def test_derive_case_taxonomy_state_leaves_offensive_taxonomy_null():
    payload = derive_case_taxonomy_state(
        category="General",
        raw_message="abusive message",
        status="offensive",
        case_metadata={"summary": "abusive message"},
    )
    assert payload["category"] == "Uncategorised"
    assert payload["problem_domain"] is None
    assert payload["problem_subdomain"] is None
    assert payload["convergence_program_type"] is None
    assert payload["case_metadata"]["categories"] == []


def test_build_taxonomy_fields_rescues_riot_report_into_law_and_order():
    fields = build_taxonomy_fields(
        problem_domain="Infrastructure & Utilities",
        problem_subdomain="Roads & Bridges",
        raw_text="आंगोल में दंगा हुआ है, कुछ मस्जिद पर पत्थर मारे लोगों ने।",
    )
    assert fields["problem_domain"] == "Law & Order"
    assert fields["problem_subdomain"] == "Theft/Assault/Violent Crime"


def test_build_taxonomy_fields_rescues_domestic_violence_in_progress():
    fields = build_taxonomy_fields(
        problem_domain="General",
        raw_text="घरेलू हिंसा अभी चल रही है, महिला को तुरंत खतरा है।",
    )
    assert fields["problem_domain"] == "Social Issues"
    assert fields["problem_subdomain"] == "Gender-based Violence"


def test_infer_emergency_taxonomy_override_for_missing_child():
    domain, subdomain = infer_emergency_taxonomy_override("लापता बच्चा, तुरंत ढूंढने में मदद चाहिए")
    assert domain == "Law & Order"
    assert subdomain == "Kidnapping/Missing"


def test_detect_emergency_severity_matches_hindi_riot_text():
    assert detect_emergency_severity("आंगोल में दंगा हुआ है, कुछ मस्जिद पर पत्थर मारे लोगों ने।") is True


def test_infer_personal_request_category_for_private_land_help():
    assert (
        infer_personal_request_category("mera mere bhai ke saath zameen ko lekar jhagda hua. aap meri madad karo")
        == "Personal Request"
    )


def test_infer_personal_request_category_for_transfer_request():
    assert (
        infer_personal_request_category("mujhe transfer karwa dijiye please help")
        == "Personal Request"
    )


def test_infer_silent_log_category_for_political_support_message():
    assert infer_silent_log_category("thank you sir and happy birthday to you") == "Political / Support Message"


def test_infer_silent_log_category_for_media_outreach():
    assert infer_silent_log_category("press interview request from local media reporter") == "Media / Press Outreach"


def test_pure_greetings_route_to_silent_greetings_category():
    for greeting in ("Good morning", "Hello", "Hi", "Namaste", "Good evening sir ji", "शुभ प्रभात", "Jai Hind"):
        assert infer_silent_log_category(greeting.lower()) == "Greetings", greeting


def test_greeting_with_grievance_is_not_silenced():
    # A greeting attached to an actual issue must still route as a grievance.
    assert infer_silent_log_category("good morning, paani problem in my area") is None
    assert infer_silent_log_category("hello sir, road is broken near my house") is None
    # Substrings like "hi" inside ordinary words must not trigger greeting detection.
    assert infer_silent_log_category("this is a water issue") is None
    assert infer_silent_log_category("machine repair needed") is None


def test_contextless_media_message_detection_is_narrow():
    assert looks_like_contextless_media_message("photo") is True
    assert looks_like_contextless_media_message("please see attached pdf") is True
    assert looks_like_contextless_media_message("water problem in tilakwadi") is False
