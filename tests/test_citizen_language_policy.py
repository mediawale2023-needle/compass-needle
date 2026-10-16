from modules.citizen_language import (
    LanguageDecision,
    detect_script,
    resolve_language_decision,
    validate_and_prepare_reply,
)


def _history(language: str, script: str, raw_message: str = "") -> list[dict]:
    return [{
        "raw_message": raw_message,
        "case_metadata": {
            "language_decision": {
                "language": language,
                "script": script,
                "confidence": "high",
                "source": "current_message_ai",
            }
        },
    }]


def test_script_detection_is_independent_across_indian_writing_systems():
    assert detect_script("पाणी नाही") == "Devanagari"
    assert detect_script("ನೀರು ಇಲ್ಲ") == "Kannada"
    assert detect_script("தண்ணீர் இல்லை") == "Tamil"
    assert detect_script("నీరు లేదు") == "Telugu"
    assert detect_script("জল নেই") == "Bengali"
    assert detect_script("પાણી નથી") == "Gujarati"
    assert detect_script("ਪਾਣੀ ਨਹੀਂ") == "Gurmukhi"
    assert detect_script("پانی نہیں") == "Arabic"
    assert detect_script("paani nahi") == "Latin"
    assert detect_script("water ಇಲ್ಲ") == "Mixed"


def test_short_roman_message_keeps_conversation_language_over_ambiguous_rule():
    decision = resolve_language_decision(
        message="Mahatma Phule Road var paani nahi",
        rule_language="Hinglish",
        rule_confident=True,
        ai_language="Hinglish",
        history_rows=_history("Marathi", "Latin", "Shahapur madhe paani nahi"),
        tenant_languages=["Kannada", "English", "Hindi"],
    )

    assert decision.language == "Marathi"
    assert decision.script == "Latin"
    assert decision.used_conversation_history is True
    assert decision.code_mixed is True
    assert "Marathi" not in decision.tenant_language_context


def test_clear_native_script_change_overrides_conversation_context():
    decision = resolve_language_decision(
        message="ನಮ್ಮ ಊರಿನಲ್ಲಿ ನೀರು ಇಲ್ಲ",
        rule_language="Hindi",
        rule_confident=False,
        ai_language="Kannada",
        history_rows=_history("Marathi", "Latin"),
    )

    assert decision.language == "Kannada"
    assert decision.script == "Kannada"
    assert decision.used_conversation_history is False


def test_clear_roman_language_change_overrides_conversation_context():
    decision = resolve_language_decision(
        message="nimma samasya alli ide",
        rule_language="Kannada",
        rule_confident=True,
        ai_language="Kannada",
        history_rows=_history("Marathi", "Latin"),
    )

    assert decision.language == "Kannada"
    assert decision.script == "Latin"
    assert decision.used_conversation_history is False


def test_code_mixed_script_is_recorded_without_forcing_tenant_default():
    decision = resolve_language_decision(
        message="water supply ಇಲ್ಲ please check",
        ai_language="Kannada",
        tenant_languages=["Hindi", "English"],
    )

    assert decision.language == "Kannada"
    assert decision.script == "Mixed"
    assert decision.code_mixed is True


def test_uncertain_language_does_not_default_to_hindi_or_english():
    decision = resolve_language_decision(
        message="MG Road 4",
        rule_language="English",
        rule_confident=False,
        tenant_languages=["Hindi", "English"],
    )

    assert decision.language == ""
    assert decision.script == "Latin"
    assert decision.is_resolved is False


def test_reply_validation_repairs_escaped_newlines_and_rejects_wrong_script():
    latin_decision = LanguageDecision(language="Marathi", script="Latin", confidence="high")
    repaired, validation = validate_and_prepare_reply("Tumcha sandesh\\n\\nDhanyavaad", latin_decision)
    assert repaired == "Tumcha sandesh\n\nDhanyavaad"
    assert validation["valid"] is True

    rejected, validation = validate_and_prepare_reply("आपका संदेश मिल गया", latin_decision)
    assert rejected == "🙏"
    assert validation["fallback_used"] is True
    assert validation["reason"] == "reply_script_mismatch"
