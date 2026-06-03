import sys
import types as py_types

from modules.voice_note_normalizer import normalize_voice_note_transcript


class _FakeResponse:
    text = (
        '{"normalized_text":"नाथ पाई सर्कलमध्ये खूप चोरी होत आहे.",'
        '"english_support_text":"There is a lot of theft happening at Nath Pai Circle.",'
        '"detected_language":"Marathi",'
        '"mentioned_location_original":"नाथ पाई सर्कल",'
        '"mentioned_location_roman":"Nath Pai Circle",'
        '"confidence":"high"}'
    )


class _FakeModels:
    def generate_content(self, **kwargs):
        self.last_kwargs = kwargs
        return _FakeResponse()


class _FakeClient:
    def __init__(self):
        self.models = _FakeModels()


def test_voice_note_normalizer_uses_candidate_shortlist_with_gemini(monkeypatch):
    fake_client = _FakeClient()

    fake_google = py_types.ModuleType("google")
    fake_genai = py_types.ModuleType("google.genai")
    fake_types = py_types.SimpleNamespace(
        GenerateContentConfig=lambda **kwargs: kwargs,
    )
    fake_genai.types = fake_types
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)

    import modules.voice_note_normalizer as normalizer
    import core.gemini_client as gemini_client

    monkeypatch.setattr(gemini_client, "get_gemini_client", lambda: fake_client)
    monkeypatch.setattr(
        normalizer,
        "resolve_location",
        lambda *_args, **_kwargs: {"location_resolved": False},
    )
    monkeypatch.setattr(
        normalizer,
        "suggest_location_candidates",
        lambda *_args, **_kwargs: [
            {
                "matched_value": "Nath Pai Circle",
                "assembly_constituency": "Belgaum South",
                "confidence_level": "fuzzy",
                "score": 140,
            }
        ],
    )

    result = normalize_voice_note_transcript(
        "नाथबाई सर्कलमध्ये खूप चोरी होत आहे.",
        tenant_id=10,
        detected_language="Marathi",
    )

    assert result.raw_transcript == "नाथबाई सर्कलमध्ये खूप चोरी होत आहे."
    assert result.normalized_text == "नाथ पाई सर्कलमध्ये खूप चोरी होत आहे."
    assert result.english_support_text == "There is a lot of theft happening at Nath Pai Circle."
    assert result.mentioned_location_roman == "Nath Pai Circle"
    assert result.extracted_language == "Marathi"
    assert result.provider == "sarvam+gemini"
    assert result.notes["candidate_locations"][0]["matched_value"] == "Nath Pai Circle"


def test_voice_note_normalizer_falls_back_to_raw_transcript(monkeypatch):
    import modules.voice_note_normalizer as normalizer
    import core.gemini_client as gemini_client

    monkeypatch.setattr(gemini_client, "get_gemini_client", lambda: None)
    monkeypatch.setattr(
        normalizer,
        "resolve_location",
        lambda *_args, **_kwargs: {"location_resolved": False},
    )
    monkeypatch.setattr(
        normalizer,
        "suggest_location_candidates",
        lambda *_args, **_kwargs: [
            {
                "matched_value": "Shahapur",
                "assembly_constituency": "Belgaum South",
                "confidence_level": "boundary",
                "score": 120,
            }
        ],
    )

    result = normalize_voice_note_transcript(
        "shapur madhe pani nahi",
        tenant_id=10,
        detected_language="Marathi",
    )

    assert result.normalized_text == "shapur madhe pani nahi"
    assert result.mentioned_location_roman == "Shahapur"
    assert result.provider == "sarvam"
    assert result.notes["normalizer"] == "fallback"
