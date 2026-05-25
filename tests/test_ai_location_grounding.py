import json
import os
import sys
from types import SimpleNamespace


os.environ["OPENAI_API_KEY"] = "sk-test-fake-key-for-testing"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sansadx_backend.ai_engine as ai_engine


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
