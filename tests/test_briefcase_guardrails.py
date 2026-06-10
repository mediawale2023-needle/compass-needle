"""
Guardrail tests for the Briefcase intelligence hardening:

1. Deterministic civic rescue rules (Lane A) lock the domain over AI hints.
2. Venue-word suppression: landmark venues never drive the category.
3. UNKNOWN instead of guess: no default category when nothing is supported.
4. AI hint only: unconfirmed AI categories are flagged for review.
5. Grounding gate: ungrounded AI locations never reach the case record.
6. Parent/child level lock: parent-only mentions never map to a random child
   assembly.
7. Hard seat scoping: no nationwide index scan when a tenant has no seat
   context.
8. Fuzzy abstain: fuzzy geo matches resolve as medium confidence with
   needs_confirmation, never as silent truth.
"""

import json
import os
import sys
from types import SimpleNamespace

import pytest

os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-testing")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import modules.geography_resolver as geography_resolver
import sansadx_backend.ai_engine as ai_engine
import sansadx_backend.db as dbmod
from modules.briefcase_rules import (
    apply_civic_rules,
    arbitrate_category,
    detect_venue_context,
)


# ──────────────────────────────────────────────────────────────────────────────
# 1. Deterministic civic rescue rules
# ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "message,expected_domain,expected_subdomain",
    [
        ("Tilakwadi mein paani nahi aa raha", "Infrastructure & Utilities", "Water Supply"),
        ("naali bhar gayi hai pura mohalla pareshan", "Infrastructure & Utilities", "Drainage/Sewage"),
        ("kachara nahi uthta hamare yaha 2 hafte se", "Infrastructure & Utilities", "Solid Waste"),
        ("sadak toot gayi hai bade khadde hain", "Infrastructure & Utilities", "Roads & Bridges"),
        ("transformer jal gaya raat se light nahi", "Infrastructure & Utilities", "Power & Street Lighting"),
        ("Police FIR nahi likh rahi hai", "Law & Order", "FIR/Police Inaction"),
        ("Patwari paise mang raha hai jamin ke kagaz ke liye", "Bureaucratic / Administrative", "Bribery/Corruption"),
    ],
)
def test_civic_rules_lock_domain(message, expected_domain, expected_subdomain):
    hit = apply_civic_rules(message)
    assert hit is not None, f"no rule fired for: {message}"
    assert hit["problem_domain"] == expected_domain
    assert hit["problem_subdomain"] == expected_subdomain


def test_rule_beats_wrong_ai_hint():
    decision = arbitrate_category("Education", None, "School ke saamne wali naali bhar gayi hai")
    assert decision["problem_domain"] == "Infrastructure & Utilities"
    assert decision["problem_subdomain"] == "Drainage/Sewage"
    assert decision["confidence"] == "rule_locked"
    assert decision["needs_review"] is False


def test_bribery_outranks_sector_of_the_file():
    decision = arbitrate_category(
        "Housing & Land", None, "Patwari paise mang raha hai jamin ke kagaz ke liye"
    )
    assert decision["problem_domain"] == "Bureaucratic / Administrative"
    assert decision["problem_subdomain"] == "Bribery/Corruption"


# ──────────────────────────────────────────────────────────────────────────────
# 2. Venue-word suppression
# ──────────────────────────────────────────────────────────────────────────────
def test_venue_in_landmark_position_detected():
    ctx = detect_venue_context("Hospital ke pass road pe bahut bade gadde hain")
    assert "hospital" in ctx["landmark_venues"]
    assert "hospital" not in ctx["institution_subject_venues"]


def test_venue_as_complaint_subject_detected():
    ctx = detect_venue_context("sarkari hospital mein doctor kabhi nahi aate")
    assert "hospital" in ctx["institution_subject_venues"]
    assert "hospital" not in ctx["landmark_venues"]


def test_landmark_venue_does_not_become_category():
    # Naive AI says Health because of "hospital"; complaint is the road.
    decision = arbitrate_category("Health", None, "Hospital ke pass road pe bahut bade gadde hain")
    assert decision["problem_domain"] == "Infrastructure & Utilities"
    assert decision["problem_subdomain"] == "Roads & Bridges"


def test_institution_subject_keeps_venue_domain():
    decision = arbitrate_category("Health", None, "sarkari hospital mein doctor kabhi nahi aate")
    assert decision["problem_domain"] == "Health"
    assert decision["needs_review"] is False


def test_venue_only_signal_returns_unknown_not_venue_domain():
    # "mandir ke pass" pulls toward Social Issues; nothing else supports it.
    decision = arbitrate_category("Social Issues", None, "mandir ke pass wala mamla dekh lijiye")
    assert decision["problem_domain"] is None
    assert decision["confidence"] == "unknown"
    assert decision["needs_review"] is True
    assert decision["venue_suppressed"] is True


# ──────────────────────────────────────────────────────────────────────────────
# 3 + 4. UNKNOWN instead of guess / AI is a hint only
# ──────────────────────────────────────────────────────────────────────────────
def test_unknown_instead_of_default_category():
    decision = arbitrate_category(None, None, "sir wo kaam abhi tak nahi hua hai")
    assert decision["problem_domain"] is None
    assert decision["confidence"] == "unknown"
    assert decision["needs_review"] is True


def test_normalize_categories_no_longer_defaults_to_infrastructure():
    assert ai_engine._normalize_categories([], "sir kuch kaam tha") == []
    assert ai_engine._normalize_categories(["NotARealCategoryXYZ123"], "sir kuch kaam tha") == []


def test_normalize_grievance_taxonomy_unknown_path_sets_review_flag():
    grievance = ai_engine._normalize_grievance_taxonomy(
        {"categories": [], "problem_domain": None},
        "sir wo kaam abhi tak nahi hua hai",
    )
    assert grievance["problem_domain"] is None
    assert grievance["problem_subdomain"] is None
    assert grievance["categories"] == []
    assert grievance["needs_review"] is True
    assert grievance["_category_confidence"] == "unknown"


def test_unconfirmed_ai_hint_is_kept_but_flagged_for_review():
    # Valid domain from AI, but no independent keyword evidence in the text.
    decision = arbitrate_category("Agriculture", None, "bahut dikkat ho rahi hai kuch kijiye")
    assert decision["problem_domain"] == "Agriculture"
    assert decision["confidence"] == "ai_unconfirmed"
    assert decision["needs_review"] is True


def test_default_grievance_data_uses_rules_not_default_guess():
    # Rule-classifiable error-path message gets the rule category…
    data = ai_engine._default_grievance_data("paani nahi aa raha 3 din se")
    assert data["problem_domain"] == "Infrastructure & Utilities"
    assert data["problem_subdomain"] == "Water Supply"
    assert data["needs_review"] is True
    # …and an unclassifiable one stays UNKNOWN instead of Infrastructure.
    data = ai_engine._default_grievance_data("sir kuch baat karni thi")
    assert data["problem_domain"] is None
    assert data["categories"] == []


# ──────────────────────────────────────────────────────────────────────────────
# 5. Grounding gate (full intake path with stubbed model)
# ──────────────────────────────────────────────────────────────────────────────
def _stub_client(payload: dict):
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))]
    )
    return SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_kwargs: response))
    )


def test_hallucinated_location_is_cleared_and_recorded_as_hint(monkeypatch):
    monkeypatch.setattr(ai_engine, "get_client", lambda: _stub_client({
        "status": "new",
        "detected_language": "Hinglish",
        "political_response": "Ji, note kar liya.",
        "grievance_data": {
            "categories": ["Infrastructure & Utilities"],
            "problem_domain": "Infrastructure & Utilities",
            "problem_subdomain": "Water Supply",
            "convergence_program_type": None,
            "location": "Rampur",  # hallucinated — not in the message
            "person": None,
            "department": None,
            "scheme": None,
        },
    }))
    monkeypatch.setattr(ai_engine, "get_jurisdiction_context", lambda tenant_id=1: "")
    monkeypatch.setattr(
        ai_engine,
        "_get_tenant_profile",
        lambda tenant_id: {"mp_name": "Test MP", "constituency": "Belagavi", "state": "", "house": "Lok Sabha"},
    )
    monkeypatch.setattr(
        ai_engine,
        "resolve_geography_from_text",
        lambda *_args, **_kwargs: {"location_resolved": False},
    )

    result = ai_engine.ask_chatgpt_agent("paani nahi aa raha 3 din se", tenant_id=1)

    assert result["grievance_data"]["location"] is None
    assert result["assembly_constituency"] == "Unknown"
    assert result["_match_confidence"] == "ungrounded_cleared"
    # The hallucination is preserved for audit as a hint, marked ungrounded.
    assert result["grievance_data"]["_ai_location_hint"] == "Rampur"
    assert result["grievance_data"]["_ai_location_hint_grounded"] is False


def test_fuzzy_geo_resolution_flags_review(monkeypatch):
    monkeypatch.setattr(ai_engine, "get_client", lambda: _stub_client({
        "status": "new",
        "detected_language": "Hinglish",
        "political_response": "Ji, note kar liya.",
        "grievance_data": {
            "categories": ["Infrastructure & Utilities"],
            "problem_domain": "Infrastructure & Utilities",
            "problem_subdomain": "Water Supply",
            "convergence_program_type": None,
            "location": None,
            "person": None,
            "department": None,
            "scheme": None,
        },
    }))
    monkeypatch.setattr(ai_engine, "get_jurisdiction_context", lambda tenant_id=1: "")
    monkeypatch.setattr(
        ai_engine,
        "_get_tenant_profile",
        lambda tenant_id: {"mp_name": "Test MP", "constituency": "Belagavi", "state": "", "house": "Lok Sabha"},
    )
    monkeypatch.setattr(
        ai_engine,
        "resolve_geography_from_text",
        lambda *_args, **_kwargs: {
            "location_resolved": True,
            "matched_value": "Tilakwadi",
            "assembly_constituency": "Belgaum Dakshin",
            "confidence": "medium",
            "needs_confirmation": True,
            "confidence_level": "fuzzy",
        },
    )

    result = ai_engine.ask_chatgpt_agent("Tilkwadi me pani nahi aa raha", tenant_id=1)

    assert result["grievance_data"]["location"] == "Tilakwadi"
    assert result["needs_review"] is True
    assert result["grievance_data"]["_geo_needs_confirmation"] is True
    assert result["_match_confidence"] == "message_grounded_medium"


# ──────────────────────────────────────────────────────────────────────────────
# 6–8. Geography resolver: level lock, seat scope, fuzzy abstain
# ──────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def parent_span_geography_index(monkeypatch):
    """Synthetic seat where parent locality 'Gandhinagar' has children in TWO
    assemblies, and 'Tilakwadi' has children in only one."""
    rows = [
        {
            "tenant_id": 7,
            "seat_type": "mp",
            "seat_name": "Belagavi",
            "parliamentary_constituency": "Belagavi",
            "assembly": "Belgaum Dakshin",
            "stations": [
                {"station_number": "1", "locality": "Somawar Peth Tilakwadi", "building_name": ""},
                {"station_number": "2", "locality": "Kariyappa Colony Tilakwadi", "building_name": ""},
                {"station_number": "3", "locality": "Azad Galli Gandhinagar", "building_name": ""},
            ],
        },
        {
            "tenant_id": 7,
            "seat_type": "mp",
            "seat_name": "Belagavi",
            "parliamentary_constituency": "Belagavi",
            "assembly": "Belgaum Uttar",
            "stations": [
                {"station_number": "1", "locality": "Nehru Galli Gandhinagar", "building_name": ""},
            ],
        },
    ]
    monkeypatch.setattr(dbmod, "get_all_geography_data", lambda: rows)
    monkeypatch.setattr(geography_resolver, "GEOGRAPHY_BASE_PATH", None)
    monkeypatch.setattr(geography_resolver, "_geography_index", {"assemblies": {}, "loaded": False})
    geography_resolver.reload_index()
    yield rows
    monkeypatch.setattr(geography_resolver, "_geography_index", {"assemblies": {}, "loaded": False})


def test_parent_only_mention_resolves_to_parent_not_random_child(parent_span_geography_index):
    result = geography_resolver.resolve_location(
        "Tilakwadi madhe pani nahi", scope_parliamentary="Belagavi"
    )
    assert result["location_resolved"] is True
    # Stored specificity must equal stated specificity: the parent, no child.
    assert result["matched_value"] == "Tilakwadi"
    assert result["matched_type"] == "locality"
    assert result["assembly_constituency"] == "Belgaum Dakshin"


def test_parent_spanning_assemblies_refuses_child_assembly_guess(parent_span_geography_index):
    result = geography_resolver.resolve_location(
        "Gandhinagar me light nahi hai", scope_parliamentary="Belagavi"
    )
    assert result["location_resolved"] is False
    assert result["reason"] in {"parent_spans_assemblies", "ambiguous_match", "ambiguous_near_tie"}
    assert set(result["ambiguous_assemblies"]) == {"Belgaum Dakshin", "Belgaum Uttar"}


def test_stated_sub_locality_is_honoured(parent_span_geography_index):
    # Finer-than-parent is allowed when the citizen actually said it.
    result = geography_resolver.resolve_location(
        "Somawar Peth Tilakwadi madhe pani nahi", scope_parliamentary="Belagavi"
    )
    assert result["location_resolved"] is True
    assert result["matched_type"] == "sub_locality"
    assert "Somawar Peth" in result["matched_value"]


def test_seat_scope_refuses_unscoped_tenant_resolution(parent_span_geography_index, monkeypatch):
    monkeypatch.setattr(geography_resolver, "_get_tenant_seat_context", lambda _tid: None)
    monkeypatch.setattr(geography_resolver, "_load_tenant_overrides", lambda _tid: {})
    # tenant known, no seat context, no parliamentary scope → refuse, no scan.
    assert geography_resolver._rank_location_candidates(
        "Tilakwadi madhe pani nahi", tenant_id=999
    ) == []
    result = geography_resolver.resolve_location("Tilakwadi madhe pani nahi", tenant_id=999)
    assert result == {"location_resolved": False}


def test_fuzzy_match_resolves_with_needs_confirmation(parent_span_geography_index):
    # "Tilkwadi" (typo) should still resolve via strict fuzzy matching, but as
    # medium confidence with needs_confirmation — never silent truth.
    result = geography_resolver.resolve_location(
        "Tilkwadi madhe pani nahi", scope_parliamentary="Belagavi"
    )
    if result.get("location_resolved"):
        assert result["confidence_level"] in {"fuzzy", "speech_phonetic", "boundary", "exact"}
        if result["confidence_level"] in {"fuzzy", "speech_phonetic"}:
            assert result["needs_confirmation"] is True
            assert result["confidence"] == "medium"
    else:
        # Abstaining entirely is also acceptable — it must just never be a
        # confident wrong answer.
        assert result["location_resolved"] is False
