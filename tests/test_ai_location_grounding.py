import json
import os
import sys
from types import SimpleNamespace


os.environ["OPENAI_API_KEY"] = "sk-test-fake-key-for-testing"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sansadx_backend.ai_engine as ai_engine
from sansadx_backend.unified_taxonomy import build_taxonomy_fields


def _stub_client(payload: dict):
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))]
    )
    return SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=lambda **_kwargs: response
            )
        )
    )


def test_location_grounding_rejects_absent_location():
    assert ai_engine._location_is_grounded_in_message(
        "shivaji nagar",
        "Talati paise magat aahe. Majhi madad kara",
    ) is False


def test_location_grounding_accepts_spaceless_location_variant():
    assert ai_engine._location_is_grounded_in_message(
        "Shahu Nagar",
        "Shahunagar drainage issue",
    ) is True


def test_location_grounding_rejects_full_message_blob():
    assert ai_engine._location_is_grounded_in_message(
        "talathi paise magat aahe majha kam hot nahi aahe",
        "Talathi paise magat aahe, majha kam hot nahi aahe",
    ) is False


def test_ask_chatgpt_agent_discards_ungrounded_ai_location(monkeypatch):
    monkeypatch.setattr(ai_engine, "get_client", lambda: _stub_client({
        "status": "new",
        "detected_language": "Marathi",
        "political_response": "Tumcha prashna nondi kela aahe.",
        "grievance_data": {
            "categories": ["Bureaucratic / Administrative"],
            "problem_domain": "Bureaucratic / Administrative",
            "problem_subdomain": None,
            "convergence_program_type": None,
            "location": "shivaji nagar",
            "person": "Talati",
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

    result = ai_engine.ask_chatgpt_agent(
        "Talati paise magat aahe. Majhi madad kara",
        tenant_id=1,
    )

    assert result["status"] == "new"
    assert result["assembly_constituency"] == "Unknown"
    assert result["grievance_data"]["location"] is None
    assert result["_match_confidence"] == "ungrounded_cleared"
    assert "ward number" not in result["political_response"].lower()


def test_ask_chatgpt_agent_prefers_message_grounded_resolution(monkeypatch):
    monkeypatch.setattr(ai_engine, "get_client", lambda: _stub_client({
        "status": "new",
        "detected_language": "English",
        "political_response": "Your grievance has been noted.",
        "grievance_data": {
            "categories": ["Infrastructure & Utilities"],
            "problem_domain": "Infrastructure & Utilities",
            "problem_subdomain": None,
            "convergence_program_type": None,
            "location": "Random Nagar",
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
            "matched_value": "Shahu Nagar",
            "assembly_constituency": "Belgaum Uttar",
            "confidence": "high",
        },
    )

    result = ai_engine.ask_chatgpt_agent("Shahunagar drainage issue", tenant_id=1)

    assert result["status"] == "new"
    assert result["assembly_constituency"] == "Belgaum Uttar"
    assert result["grievance_data"]["location"] == "Shahu Nagar"
    assert result["grievance_data"]["assembly_constituency"] == "Belgaum Uttar"
    assert result["_match_confidence"] == "message_grounded_high"


def test_ask_chatgpt_agent_uses_shared_resolver_for_grounded_ai_hint(monkeypatch):
    monkeypatch.setattr(ai_engine, "get_client", lambda: _stub_client({
        "status": "new",
        "detected_language": "Kannada",
        "political_response": "ನಿಮ್ಮ ಅಹವಾಲು ದಾಖಲಿಸಲಾಗಿದೆ.",
        "grievance_data": {
            "categories": ["Infrastructure & Utilities"],
            "problem_domain": "Infrastructure & Utilities",
            "problem_subdomain": "Water Supply",
            "convergence_program_type": None,
            "location": "Teacher Colony",
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

    def _resolver(text, *_args, **_kwargs):
        if text == "Teacher Colony nalli 3 din neer illa":
            return {"location_resolved": False}
        if text == "Teacher Colony":
            return {
                "location_resolved": True,
                "matched_value": "Teachers Colony",
                "assembly_constituency": "Belgaum Dakshin",
                "confidence_level": "exact",
            }
        return {"location_resolved": False}

    monkeypatch.setattr(ai_engine, "resolve_geography_from_text", _resolver)

    result = ai_engine.ask_chatgpt_agent("Teacher Colony nalli 3 din neer illa", tenant_id=1)

    assert result["status"] == "new"
    assert result["assembly_constituency"] == "Belgaum Dakshin"
    assert result["grievance_data"]["location"] == "Teachers Colony"
    assert result["grievance_data"]["assembly_constituency"] == "Belgaum Dakshin"
    assert result["_match_confidence"] == "ai_hint_exact"


def test_unmatched_location_defaults_to_seat_assembly_for_single_assembly_seat(monkeypatch):
    """Seat-generic: an MLA (single-assembly) seat keeps the assembly certain even
    when the ward cannot be matched. No constituency names are hardcoded — the
    default comes purely from ``get_default_seat_assembly``."""
    monkeypatch.setattr(ai_engine, "get_client", lambda: _stub_client({
        "status": "new",
        "detected_language": "Kannada",
        "political_response": "ನಿಮ್ಮ ಅಹವಾಲು ದಾಖಲಿಸಲಾಗಿದೆ.",
        "grievance_data": {
            "categories": ["Infrastructure & Utilities"],
            "problem_domain": "Infrastructure & Utilities",
            "problem_subdomain": "Water Supply",
            "convergence_program_type": None,
            "location": "Teacher Colony",
            "person": None,
            "department": None,
            "scheme": None,
        },
    }))
    monkeypatch.setattr(ai_engine, "get_jurisdiction_context", lambda tenant_id=1: "")
    monkeypatch.setattr(
        ai_engine,
        "_get_tenant_profile",
        lambda tenant_id: {"mp_name": "Test MLA", "constituency": "Belgaum South", "state": "", "house": "Vidhan Sabha"},
    )
    # Neither the whole message nor the AI hint resolves to a specific ward.
    monkeypatch.setattr(
        ai_engine,
        "resolve_geography_from_text",
        lambda *_args, **_kwargs: {"location_resolved": False},
    )
    # The seat structurally maps to exactly one assembly.
    monkeypatch.setattr(ai_engine, "get_default_seat_assembly", lambda **_kwargs: "Belgaum South")

    result = ai_engine.ask_chatgpt_agent("Teacher Colony nalli 3 din neer illa", tenant_id=10)

    assert result["status"] == "new"
    assert result["assembly_constituency"] == "Belgaum South"
    assert result["grievance_data"]["location"] is None
    assert result["grievance_data"]["assembly_constituency"] == "Belgaum South"
    assert result["_match_confidence"] == "seat_default"


def test_unmatched_location_stays_unknown_for_multi_assembly_seat(monkeypatch):
    """An MP (multi-assembly) seat cannot infer the assembly without a locality
    signal, so it must remain Unknown."""
    monkeypatch.setattr(ai_engine, "get_client", lambda: _stub_client({
        "status": "new",
        "detected_language": "Kannada",
        "political_response": "ನಿಮ್ಮ ಅಹವಾಲು ದಾಖಲಿಸಲಾಗಿದೆ.",
        "grievance_data": {
            "categories": ["Infrastructure & Utilities"],
            "problem_domain": "Infrastructure & Utilities",
            "problem_subdomain": "Water Supply",
            "convergence_program_type": None,
            "location": "Teacher Colony",
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
    # Multi-assembly seat -> no single default.
    monkeypatch.setattr(ai_engine, "get_default_seat_assembly", lambda **_kwargs: None)

    result = ai_engine.ask_chatgpt_agent("Teacher Colony nalli 3 din neer illa", tenant_id=1)

    assert result["assembly_constituency"] == "Unknown"
    assert result["grievance_data"]["location"] is None
    assert result["_match_confidence"] == "unmatched_cleared"


def test_get_default_seat_assembly_is_seat_generic(monkeypatch):
    """The default-assembly helper derives from seat structure, not place names."""
    import modules.geography_resolver as geo

    # MLA seat -> the seat itself is the single assembly.
    monkeypatch.setattr(
        geo,
        "_get_tenant_seat_context",
        lambda tid: {"seat_type": "mla", "seat_name": "Belgaum South", "scope_parliamentary": "Belgaum", "constituency": "Belgaum South"},
    )
    assert geo.get_default_seat_assembly(tenant_id=10) == "Belgaum South"

    # MP seat spanning multiple assemblies -> cannot infer a single assembly.
    monkeypatch.setattr(
        geo,
        "_get_tenant_seat_context",
        lambda tid: {"seat_type": "mp", "seat_name": "Belagavi", "scope_parliamentary": "Belagavi", "constituency": "Belagavi"},
    )
    assert geo.get_default_seat_assembly(tenant_id=2, scope_parliamentary="Belagavi") is None


def test_ask_chatgpt_agent_clears_sentence_like_ai_location(monkeypatch):
    monkeypatch.setattr(ai_engine, "get_client", lambda: _stub_client({
        "status": "new",
        "detected_language": "Marathi",
        "political_response": "Tumcha prashna nondi kela aahe.",
        "grievance_data": {
            "categories": ["Bureaucratic / Administrative"],
            "problem_domain": "Bureaucratic / Administrative",
            "problem_subdomain": None,
            "convergence_program_type": None,
            "location": "तलाठी पैसे मागत आहे माझं काम होत नाही आहे",
            "person": "Talati",
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

    result = ai_engine.ask_chatgpt_agent(
        "तलाठी पैसे मागत आहे, माझं काम होत नाही आहे.",
        tenant_id=1,
    )

    assert result["status"] == "new"
    assert result["assembly_constituency"] == "Unknown"
    assert result["grievance_data"]["location"] is None
    assert result["_match_confidence"] in {"ungrounded_cleared", "unmatched_cleared"}


def test_bureaucratic_case_can_stay_new_without_location(monkeypatch):
    monkeypatch.setattr(ai_engine, "get_client", lambda: _stub_client({
        "status": "new",
        "detected_language": "Marathi",
        "political_response": "Tumcha prashna nondi kela aahe.",
        "grievance_data": {
            "categories": ["Bureaucratic / Administrative"],
            "problem_domain": "Bureaucratic / Administrative",
            "problem_subdomain": "Bribery/Corruption",
            "convergence_program_type": None,
            "location": "talathi paise magat aahe majha kam hot nahi aahe",
            "person": "Talati",
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

    result = ai_engine.ask_chatgpt_agent(
        "तलाठी पैसे मागत आहे, माझं काम होत नाही आहे.",
        tenant_id=1,
    )

    assert result["status"] == "new"
    assert result["assembly_constituency"] == "Unknown"
    assert result["grievance_data"]["location"] is None
    assert "ward number" not in result["political_response"].lower()


def test_build_taxonomy_fields_overrides_wrong_road_guess_for_talathi_bribe():
    fields = build_taxonomy_fields(
        problem_domain="Infrastructure & Utilities",
        problem_subdomain="Roads & Bridges",
        raw_text="तलाठी पैसे मागत आहे, माझं काम करून द्या.",
    )

    assert fields["problem_domain"] == "Bureaucratic / Administrative"
    assert fields["problem_subdomain"] == "Bribery/Corruption"
    assert fields["convergence_program_type"] == "Monitoring & Transparency"
    assert fields["categories"] == ["Bureaucratic / Administrative"]


def test_normalize_grievance_taxonomy_overrides_wrong_road_guess_for_talathi_bribe():
    grievance = {
        "categories": ["Infrastructure & Utilities"],
        "problem_domain": "Infrastructure & Utilities",
        "problem_subdomain": "Roads & Bridges",
        "convergence_program_type": "Public Asset Upgrade",
        "location": None,
        "person": "तलाठी",
        "department": None,
        "scheme": None,
    }

    normalized = ai_engine._normalize_grievance_taxonomy(
        grievance,
        "तलाठी पैसे मागत आहे, माझं काम करून द्या.",
    )

    assert normalized["problem_domain"] == "Bureaucratic / Administrative"
    assert normalized["problem_subdomain"] == "Bribery/Corruption"
    assert normalized["convergence_program_type"] == "Monitoring & Transparency"
    assert normalized["categories"] == ["Bureaucratic / Administrative"]


def test_build_taxonomy_fields_overrides_wrong_road_guess_for_patwari_money_demand():
    fields = build_taxonomy_fields(
        problem_domain="Infrastructure & Utilities",
        problem_subdomain="Roads & Bridges",
        raw_text="Patwari is asking for money to move my file.",
    )

    assert fields["problem_domain"] == "Bureaucratic / Administrative"
    assert fields["problem_subdomain"] == "Bribery/Corruption"
    assert fields["convergence_program_type"] == "Monitoring & Transparency"
    assert fields["categories"] == ["Bureaucratic / Administrative"]


def test_build_taxonomy_fields_overrides_teacher_colony_water_outage():
    fields = build_taxonomy_fields(
        problem_domain="Education",
        problem_subdomain="Teacher Availability",
        raw_text="Teacher Colony nalli 3 din neer illa",
    )

    assert fields["problem_domain"] == "Infrastructure & Utilities"
    assert fields["problem_subdomain"] == "Water Supply"
    assert fields["convergence_program_type"] == "Public Asset Upgrade"
    assert fields["categories"] == ["Infrastructure & Utilities"]


def test_normalize_grievance_taxonomy_overrides_teacher_colony_water_outage():
    grievance = {
        "categories": ["Education"],
        "problem_domain": "Education",
        "problem_subdomain": "Teacher Availability",
        "convergence_program_type": "Service Delivery Strengthening",
        "location": "Teacher Colony",
        "person": None,
        "department": None,
        "scheme": None,
    }

    normalized = ai_engine._normalize_grievance_taxonomy(
        grievance,
        "Teacher Colony nalli 3 din neer illa",
    )

    assert normalized["problem_domain"] == "Infrastructure & Utilities"
    assert normalized["problem_subdomain"] == "Water Supply"
    assert normalized["convergence_program_type"] == "Public Asset Upgrade"
    assert normalized["categories"] == ["Infrastructure & Utilities"]
