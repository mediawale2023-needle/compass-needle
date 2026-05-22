import sys
import types as py_types

from modules.whatsapp_media_intake import normalize_media_complaint


class _FakeResponse:
    text = (
        '{"complaint_text":"Tilakwadi madhe paani nahi",'
        '"detected_language":"Marathi",'
        '"mentioned_location_original":"Tilakwadi",'
        '"mentioned_location_roman":"Tilakwadi",'
        '"confidence":"high"}'
    )


class _FakeModels:
    def __init__(self):
        self.last_kwargs = None

    def generate_content(self, **kwargs):
        self.last_kwargs = kwargs
        return _FakeResponse()


class _FakeClient:
    def __init__(self):
        self.models = _FakeModels()


def test_normalize_media_complaint_returns_grievance_text(monkeypatch):
    fake_client = _FakeClient()

    fake_google = py_types.ModuleType("google")
    fake_genai = py_types.ModuleType("google.genai")
    fake_types = py_types.SimpleNamespace(
        Part=py_types.SimpleNamespace(from_bytes=lambda data, mime_type: {"data": data, "mime_type": mime_type}),
        GenerateContentConfig=lambda **kwargs: kwargs,
    )
    fake_genai.types = fake_types
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)

    import core.gemini_client as gemini_client

    monkeypatch.setattr(gemini_client, "get_gemini_client", lambda: fake_client)

    result = normalize_media_complaint(
        b"fake-image",
        "image/jpeg",
        tenant_id=2,
        media_type="image",
        caption="photo from Tilakwadi",
    )

    assert result.ok is True
    assert result.text == "Tilakwadi madhe paani nahi"
    assert result.extracted_language == "Marathi"
    assert result.mentioned_location_original == "Tilakwadi"
    assert result.mentioned_location_roman == "Tilakwadi"
    assert result.confidence == "high"
    assert fake_client.models.last_kwargs["model"] == "gemini-2.5-flash"


def test_normalize_media_complaint_fails_closed_on_empty_media():
    result = normalize_media_complaint(
        b"",
        "audio/ogg",
        tenant_id=2,
        media_type="audio",
    )

    assert result.ok is False
    assert result.error == "empty_media"
