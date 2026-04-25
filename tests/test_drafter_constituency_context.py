import os

os.environ.setdefault("JWT_SECRET", "x" * 32)

import api_router


def test_constituency_identity_context_is_minimal(monkeypatch):
    monkeypatch.setattr(
        api_router,
        "_q_one",
        lambda *_args, **_kwargs: {
            "mp_name": "Jane Doe",
            "constituency": "Belagavi",
            "state": "Karnataka",
            "house": "Lok Sabha",
            "party": "Independent",
        },
    )

    context = api_router._build_constituency_identity_context(42)

    assert "SENDER IDENTITY CONTEXT" in context
    assert "MP: Jane Doe" in context
    assert "Constituency: Belagavi" in context
    assert "KEY LOCAL CHALLENGES" not in context
    assert "DEVELOPMENT PRIORITIES" not in context
    assert "NOTABLE FACTS" not in context


def test_constituency_identity_context_returns_empty_without_profile(monkeypatch):
    monkeypatch.setattr(api_router, "_q_one", lambda *_args, **_kwargs: None)
    assert api_router._build_constituency_identity_context(42) == ""
