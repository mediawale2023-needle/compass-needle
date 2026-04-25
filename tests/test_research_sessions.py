import os
from types import SimpleNamespace

os.environ.setdefault("JWT_SECRET", "x" * 32)

import api_router


def test_suggest_research_title_strips_pdf_suffix():
    assert api_router._suggest_research_title("Budget Brief 2026.pdf") == "Budget Brief 2026"


def test_build_session_document_context_includes_multiple_documents():
    docs = [
        SimpleNamespace(filename="Doc A.pdf", content_text="[Page 1]\nAlpha"),
        SimpleNamespace(filename="Doc B.pdf", content_text="[Page 1]\nBeta"),
    ]

    context = api_router._build_session_document_context(docs, max_chars=200)

    assert "[Document: Doc A.pdf]" in context
    assert "[Document: Doc B.pdf]" in context
    assert "Alpha" in context
    assert "Beta" in context


def test_serialize_retrieved_sources_preserves_citation_order():
    chunks = [
        {"citation": "PQ #1 — Water", "source_type": "pq_qa", "title": "Water question", "date_ref": "2026-01-01", "score": 0.98},
        {"citation": "Scheme: PMGSY", "source_type": "scheme", "title": "PMGSY", "date_ref": None, "score": 0.91},
    ]

    sources = api_router._serialize_retrieved_sources(chunks)

    assert sources[0]["index"] == 1
    assert sources[0]["citation"] == "PQ #1 — Water"
    assert sources[1]["index"] == 2
    assert sources[1]["source_type"] == "scheme"
