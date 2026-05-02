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


def test_irrelevant_status_is_preserved(monkeypatch):
    monkeypatch.setattr(ai_engine, "get_client", lambda: _stub_client({
        "status": "IRRELEVANT",
        "detected_language": "English",
        "political_response": "Thank you for reaching out.",
        "grievance_data": {
            "categories": [],
            "problem_domain": None,
            "problem_subdomain": None,
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
        lambda tenant_id: {"mp_name": "Test MP", "constituency": "Test Seat", "state": "", "house": "Lok Sabha"},
    )

    result = ai_engine.ask_chatgpt_agent("hello there", tenant_id=1)

    assert result["status"] == "irrelevant"
    assert result["grievance_data"]["categories"] == []
    assert result["grievance_data"]["problem_domain"] is None


def test_offensive_status_forces_warning_reply(monkeypatch):
    monkeypatch.setattr(ai_engine, "get_client", lambda: _stub_client({
        "status": "OFFENSIVE",
        "detected_language": "English",
        "political_response": "Thank you for reaching out. How can I help you?",
        "grievance_data": {
            "categories": [],
            "problem_domain": None,
            "problem_subdomain": None,
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
        lambda tenant_id: {"mp_name": "Test MP", "constituency": "Test Seat", "state": "", "house": "Lok Sabha"},
    )

    result = ai_engine.ask_chatgpt_agent("fuck you", tenant_id=1)

    assert result["status"] == "offensive"
    assert result["political_response"] == "Maintain decorum. Legal action can be taken for abusive language."
    assert result["grievance_data"]["categories"] == []
