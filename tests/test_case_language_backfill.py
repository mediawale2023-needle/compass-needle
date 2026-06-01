import json

from scripts.backfill_case_languages import _best_language_source, _should_backfill


def test_best_language_source_prefers_raw_transcript():
    row = {
        "raw_message": "Yellur madhe paani nahi aahe",
        "case_metadata": {
            "source_media_raw_transcript": "नाथ पाई सर्कलमध्ये खूप चोरी होत आहे.",
            "summary": "fallback",
        },
    }
    assert _best_language_source(row) == "नाथ पाई सर्कलमध्ये खूप चोरी होत आहे."


def test_should_backfill_when_language_missing():
    assert _should_backfill({}, "तलाठी पैसे मागत आहे") is True


def test_should_backfill_when_stored_english_but_text_is_not_english():
    meta = {"detected_language": "English"}
    assert _should_backfill(meta, "Yellur madhe paani nahi aahe") is True


def test_should_not_backfill_when_supported_language_already_present():
    meta = {"detected_language": "Marathi"}
    assert _should_backfill(meta, "Yellur madhe paani nahi aahe") is False


def test_best_language_source_handles_json_string_metadata():
    row = {
        "raw_message": "Budhawar peth madhe rasta kharab aahe",
        "case_metadata": json.dumps({
            "source_media_raw_transcript": "",
            "summary": "summary only",
        }),
    }
    assert _best_language_source(row) == "Budhawar peth madhe rasta kharab aahe"
