"""Conversation-aware language and script policy for citizen WhatsApp replies.

This module deliberately separates script detection (deterministic Unicode
ranges) from language detection (rules/AI/context).  It does not own language
keyword dictionaries and it never treats tenant language configuration as an
allow-list.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
import unicodedata
from typing import Any, Iterable

from modules.localized_replies import normalize_language_name


_SCRIPT_RANGES: tuple[tuple[str, int, int], ...] = (
    ("Arabic", 0x0600, 0x06FF),
    ("Arabic", 0x0750, 0x077F),
    ("Arabic", 0x08A0, 0x08FF),
    ("Devanagari", 0x0900, 0x097F),
    ("Bengali", 0x0980, 0x09FF),
    ("Gurmukhi", 0x0A00, 0x0A7F),
    ("Gujarati", 0x0A80, 0x0AFF),
    ("Odia", 0x0B00, 0x0B7F),
    ("Tamil", 0x0B80, 0x0BFF),
    ("Telugu", 0x0C00, 0x0C7F),
    ("Kannada", 0x0C80, 0x0CFF),
    ("Malayalam", 0x0D00, 0x0D7F),
    ("Sinhala", 0x0D80, 0x0DFF),
    ("Ol Chiki", 0x1C50, 0x1C7F),
    ("Meetei Mayek", 0xABC0, 0xABFF),
)

_LANGUAGE_SCRIPTS: dict[str, set[str]] = {
    "Hindi": {"Devanagari", "Latin"},
    "Hinglish": {"Latin", "Devanagari", "Mixed"},
    "Marathi": {"Devanagari", "Latin"},
    "Kannada": {"Kannada", "Latin"},
    "Tamil": {"Tamil", "Latin"},
    "Telugu": {"Telugu", "Latin"},
    "Bengali": {"Bengali", "Latin"},
    "Gujarati": {"Gujarati", "Latin"},
    "Punjabi": {"Gurmukhi", "Latin"},
    "Odia": {"Odia", "Latin"},
    "Malayalam": {"Malayalam", "Latin"},
    "Assamese": {"Bengali", "Latin"},
    "Urdu": {"Arabic", "Latin"},
    "English": {"Latin"},
}

_NEUTRAL_REPLY = "🙏"


@dataclass(frozen=True)
class LanguageDecision:
    language: str = ""
    script: str = "Unknown"
    confidence: str = "unknown"
    source: str = "unresolved"
    code_mixed: bool = False
    used_conversation_history: bool = False
    tenant_language_context: tuple[str, ...] = ()

    @property
    def is_resolved(self) -> bool:
        return bool(self.language and self.script != "Unknown")

    def to_metadata(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["tenant_language_context"] = list(self.tenant_language_context)
        payload["resolved"] = self.is_resolved
        return payload


def detect_script(text: str) -> str:
    """Return the dominant writing system without guessing a language."""
    counts: dict[str, int] = {}
    for char in str(text or ""):
        codepoint = ord(char)
        script = ""
        if ("A" <= char <= "Z") or ("a" <= char <= "z"):
            script = "Latin"
        else:
            for name, start, end in _SCRIPT_RANGES:
                if start <= codepoint <= end:
                    script = name
                    break
        if script:
            counts[script] = counts.get(script, 0) + 1

    if not counts:
        return "Unknown"
    meaningful = [name for name, count in counts.items() if count >= 2]
    if len(meaningful) > 1:
        return "Mixed"
    return max(counts, key=counts.get)


def _parse_meta(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def previous_language_decision(history_rows: Iterable[dict[str, Any]]) -> LanguageDecision | None:
    """Read the newest usable decision, including legacy case metadata."""
    for row in history_rows or ():
        meta = _parse_meta(row.get("case_metadata"))
        stored = meta.get("language_decision")
        if isinstance(stored, dict):
            language = normalize_language_name(str(stored.get("language") or ""), "")
            script = str(stored.get("script") or "Unknown")
            if language:
                return LanguageDecision(
                    language=language,
                    script=script if script != "Unknown" else detect_script(row.get("raw_message") or ""),
                    confidence=str(stored.get("confidence") or "medium"),
                    source=str(stored.get("source") or "case_metadata"),
                    code_mixed=bool(stored.get("code_mixed")),
                )

        language = normalize_language_name(
            str(meta.get("detected_language") or meta.get("language") or ""),
            "",
        )
        if language:
            return LanguageDecision(
                language=language,
                script=detect_script(row.get("raw_message") or ""),
                confidence="medium",
                source="legacy_case_metadata",
                code_mixed=language == "Hinglish",
            )
    return None


def resolve_language_decision(
    *,
    message: str,
    rule_language: str = "",
    rule_confident: bool = False,
    ai_language: str = "",
    language_hint: str = "",
    history_rows: Iterable[dict[str, Any]] = (),
    tenant_languages: Iterable[str] = (),
) -> LanguageDecision:
    """Reconcile current evidence with stable conversation language.

    Short same-script messages are intentionally interpreted in conversation
    context. A clear script change wins immediately. For Roman text, a language
    switch requires stronger current evidence than one short-message heuristic:
    agreement between AI and rules on a sufficiently informative message.
    """
    script = detect_script(message)
    previous = previous_language_decision(history_rows)
    rule = normalize_language_name(rule_language, "")
    ai = normalize_language_name(ai_language, "")
    hint = normalize_language_name(language_hint, "")
    tenant_context = tuple(
        language
        for language in (normalize_language_name(str(item), "") for item in tenant_languages)
        if language
    )
    words = re.findall(r"[^\W\d_]+", str(message or ""), flags=re.UNICODE)

    if hint:
        return LanguageDecision(
            language=hint,
            script=script if script != "Unknown" else (previous.script if previous else "Unknown"),
            confidence="high",
            source="current_message_hint",
            code_mixed=script == "Mixed" or hint == "Hinglish",
            used_conversation_history=bool(previous and script == "Unknown"),
            tenant_language_context=tenant_context,
        )

    same_script_context = bool(
        previous
        and previous.language
        and (
            script == "Unknown"
            or previous.script == "Unknown"
            or script == previous.script
            or script == "Mixed"
            or previous.script == "Mixed"
        )
    )
    current_detectors_agree = bool(
        rule_confident
        and rule
        and ai
        and rule == ai
        and previous
        and rule != previous.language
    )
    clear_roman_switch = bool(
        script == "Latin"
        and current_detectors_agree
        and (
            len(words) >= 12
            or (len(words) >= 3 and rule not in {"Hinglish"})
        )
    )

    if same_script_context and not clear_roman_switch:
        return LanguageDecision(
            language=previous.language,
            script=script if script != "Unknown" else previous.script,
            confidence="high" if len(words) <= 12 else "medium",
            source="conversation_history",
            code_mixed=(
                script == "Mixed"
                or previous.code_mixed
                or (bool(ai) and ai != previous.language)
                or (bool(rule) and rule != previous.language)
            ),
            used_conversation_history=True,
            tenant_language_context=tenant_context,
        )

    chosen = rule if rule_confident and rule else ai
    source = "current_message_rule" if rule_confident and rule else "current_message_ai"
    confidence = "high" if rule_confident and rule else "medium"
    if not chosen:
        return LanguageDecision(
            script=script,
            tenant_language_context=tenant_context,
        )

    return LanguageDecision(
        language=chosen,
        script=script,
        confidence=confidence,
        source=source,
        code_mixed=script == "Mixed" or chosen == "Hinglish" or bool(ai and rule and ai != rule),
        tenant_language_context=tenant_context,
    )


def language_context_prompt(decision: LanguageDecision) -> str:
    """Compact internal context consumed by the existing classification call."""
    if decision.language:
        return (
            "AUTHORITATIVE LANGUAGE CONTEXT (system generated): "
            f"language={decision.language}; script={decision.script}; "
            f"source={decision.source}. Use this language and script for analysis and reply."
        )
    tenant_hint = ", ".join(decision.tenant_language_context)
    return (
        "AUTHORITATIVE LANGUAGE CONTEXT (system generated): language=Unknown; "
        f"script={decision.script}; tenant_context={tenant_hint or 'none'}. "
        "Detect from the citizen message; tenant_context is a prior, not a restriction."
    )


def _script_counts(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for char in str(text or ""):
        name = detect_script(char)
        if name != "Unknown":
            counts[name] = counts.get(name, 0) + 1
    return counts


def validate_and_prepare_reply(reply: str, decision: LanguageDecision) -> tuple[str, dict[str, Any]]:
    """Normalize formatting and cheaply enforce the authoritative script.

    Templates and the classifier share the language decision, so deterministic
    script validation is sufficient here and avoids another model call.
    """
    text = unicodedata.normalize("NFC", str(reply or "")).replace("\\n", "\n").strip()
    result = {
        "valid": True,
        "fallback_used": False,
        "reason": "",
        "language": decision.language,
        "script": decision.script,
        "check": "deterministic_template_and_unicode_script",
    }
    if not text:
        return text, result
    if not decision.language or decision.script == "Unknown":
        result.update(valid=False, fallback_used=True, reason="language_or_script_unresolved")
        return _NEUTRAL_REPLY, result

    counts = _script_counts(text)
    expected = decision.script
    if expected == "Mixed":
        allowed = _LANGUAGE_SCRIPTS.get(decision.language, {"Latin"}) | {"Latin"}
        incompatible = sum(count for name, count in counts.items() if name not in allowed)
    elif expected == "Latin":
        incompatible = sum(count for name, count in counts.items() if name != "Latin")
    else:
        incompatible = sum(count for name, count in counts.items() if name not in {expected, "Latin"})
        if counts and counts.get(expected, 0) == 0:
            incompatible += 1

    if incompatible:
        result.update(valid=False, fallback_used=True, reason="reply_script_mismatch")
        return _NEUTRAL_REPLY, result
    return text, result
