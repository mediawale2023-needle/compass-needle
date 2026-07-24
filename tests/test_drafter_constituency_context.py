import os
import sys
import types

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


def test_letter_background_memory_includes_pq_as_quiet_context(monkeypatch):
    captured = {}

    fake_retriever = types.ModuleType("modules.brain_retriever")

    def _fake_retrieve(**kwargs):
        captured.update(kwargs)
        return [{"text": "The Ministry has discussed Karnataka railway connectivity in prior answers."}]

    def _fake_format_for_prompt(chunks, label):
        captured["label"] = label
        return f"{label}\n{chunks[0]['text']}"

    fake_retriever.retrieve = _fake_retrieve
    fake_retriever.format_for_prompt = _fake_format_for_prompt
    monkeypatch.setitem(sys.modules, "modules.brain_retriever", fake_retriever)

    context = api_router._retrieve_letter_background_memory(
        tenant_id=42,
        query="Special train between Belagavi and Mumbai",
        ministry="Ministry of Railways",
        k=7,
    )

    assert captured["tenant_id"] == 42
    assert captured["query_text"] == "Special train between Belagavi and Mumbai"
    assert captured["ministry"] == "Ministry of Railways"
    assert captured["k"] == 7
    assert captured["include_global"] is True
    assert captured["include_cross_mp"] is False
    assert "pq_qa" in captured["source_types"]
    assert "global_pq_qa" in captured["source_types"]
    assert "Do not cite source labels, PQ numbers, question IDs" in captured["label"]
    assert "BACKGROUND MEMORY" in context


def test_letter_drafter_prompt_uses_pq_memory_without_prior_pq_record(monkeypatch):
    captured = {}

    class _FakeModels:
        def generate_content(self, model, contents, config=None):
            captured["prompt"] = contents
            return type("Response", (), {"text": "Draft letter"})()

    class _FakeClient:
        models = _FakeModels()

    def _fake_q_one(query, params=None):
        if "FROM tenants" in query and "LEFT JOIN tenant_profiles" in query:
            return {
                "mp_name": "Jane Doe",
                "constituency": "Belagavi",
                "state": "Karnataka",
                "house": "Lok Sabha",
                "party": "Independent",
            }
        if "SELECT * FROM tenants" in query:
            return {"constituency": "Belagavi"}
        return None

    monkeypatch.setattr(api_router, "get_gemini_client", lambda: _FakeClient())
    monkeypatch.setattr(api_router, "get_tenant_or_fail", lambda _user: 42)
    monkeypatch.setattr(api_router, "_q_one", _fake_q_one)
    monkeypatch.setattr(
        api_router,
        "build_parliament_context",
        lambda *_args, **_kwargs: "MP'S PRIOR PARLIAMENTARY RECORD\nQ25113bf6e4",
    )

    def _fake_letter_memory(*_args, **kwargs):
        captured["letter_memory_args"] = kwargs
        return (
            "BACKGROUND MEMORY — use only for factual grounding. "
            "Do not cite source labels, PQ numbers, question IDs, or bracket references in the letter.\n"
            "The Ministry has recognized railway connectivity needs in Karnataka. Source: PQ #Q25113bf6e4"
        )

    monkeypatch.setattr(api_router, "_retrieve_letter_background_memory", _fake_letter_memory)

    # Call the undecorated endpoint: the slowapi wrapper eagerly evaluates
    # args[idx] for direct positional calls and IndexErrors outside a real
    # HTTP request. TestClient paths exercise the decorated route.
    _generate_draft = getattr(api_router.generate_draft, "__wrapped__", api_router.generate_draft)
    response = _generate_draft(
        api_router.DraftRequest(
            mode="letter",
            subject="Special train between Belagavi and Mumbai",
            recipient_name="Minister of Railways",
            ministry="Ministry of Railways",
            key_points="Request a special train service.",
            tone="Formal (Neutral)",
        ),
        request=None,
        user={"username": "jane", "display_name": "Jane Doe", "house": "Lok Sabha"},
    )

    assert response == {"content": "Draft letter"}
    assert captured["letter_memory_args"]["tenant_id"] == 42
    assert captured["letter_memory_args"]["ministry"] == "Ministry of Railways"
    assert "MP'S PRIOR PARLIAMENTARY RECORD" not in captured["prompt"]
    assert "BACKGROUND MEMORY" in captured["prompt"]
    assert "Q25113bf6e4" in captured["prompt"]
    assert "Do NOT mention, cite, summarize, or refer to prior Parliamentary Questions" in captured["prompt"]
    assert "You may silently use directly relevant PQ/global PQ background" in captured["prompt"]


def test_strip_visible_pq_references_removes_citation_scaffolding():
    cleaned = api_router._strip_visible_pq_references(
        "Connectivity has been discussed [see PQ #Q25113bf6e4]. "
        "Please also consider earlier inputs PQ #Qc08be79ac4 and Question #Qabcdef123. "
        "Source: PQ #Q99887766. "
        "The request remains important."
    )

    assert "PQ" not in cleaned
    assert "Source:" not in cleaned
    assert "Q25113bf6e4" not in cleaned
    assert "Qc08be79ac4" not in cleaned
    assert "Qabcdef123" not in cleaned
    assert "Connectivity has been discussed" in cleaned
    assert "The request remains important." in cleaned


def test_letter_drafter_strips_visible_pq_references(monkeypatch):
    class _FakeModels:
        def generate_content(self, model, contents, config=None):
            return type("Response", (), {
                "text": (
                    "Such a service would improve connectivity [see PQ #Q25113bf6e4]. "
                    "The Ministry may consider the proposal. PQ #Qc08be79ac4"
                )
            })()

    class _FakeClient:
        models = _FakeModels()

    monkeypatch.setattr(api_router, "get_gemini_client", lambda: _FakeClient())
    monkeypatch.setattr(api_router, "get_tenant_or_fail", lambda _user: 42)
    monkeypatch.setattr(api_router, "_q_one", lambda *_args, **_kwargs: {"constituency": "Belagavi"})
    monkeypatch.setattr(api_router, "_build_constituency_identity_context", lambda _tenant_id: "")
    monkeypatch.setattr(api_router, "_retrieve_letter_background_memory", lambda **_kwargs: "")

    # Call the undecorated endpoint: the slowapi wrapper eagerly evaluates
    # args[idx] for direct positional calls and IndexErrors outside a real
    # HTTP request. TestClient paths exercise the decorated route.
    _generate_draft = getattr(api_router.generate_draft, "__wrapped__", api_router.generate_draft)
    response = _generate_draft(
        api_router.DraftRequest(
            mode="letter",
            subject="Special train between Belagavi and Mumbai",
            recipient_name="Minister of Railways",
            ministry="Ministry of Railways",
            key_points="Request a special train service.",
            tone="Formal (Neutral)",
        ),
        request=None,
        user={"username": "jane", "display_name": "Jane Doe", "house": "Lok Sabha"},
    )

    assert "PQ" not in response["content"]
    assert "Q25113bf6e4" not in response["content"]
    assert "Qc08be79ac4" not in response["content"]
    assert "Such a service would improve connectivity" in response["content"]
