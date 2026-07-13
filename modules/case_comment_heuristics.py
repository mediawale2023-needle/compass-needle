"""Tenant-scoped heuristic detector for messages ABOUT an existing case
rather than reports of a NEW civic problem.

"Thank you.", "Any update?", "Please look into it urgently.", "The issue is
still pending." are all commentary on a citizen's existing thread — not new
grievances. Left undetected, each one becomes a phantom sibling case, an
unwarranted "registered as a separate issue" ack, and (if the model can't
find a location in feedback text) a location-clarification demand.

This is Layer 1: fast, deterministic, no AI call. Only the tenant's own
configured communication languages are checked (modules/tenant_languages.py)
— an office in Karnataka should not pay the false-positive risk of Bengali
phrase matches. Anything this layer does not catch falls through to the AI
classifier's CASE_COMMENT status (Phase B) as the fully multilingual
fallback.

Detection is deliberately conservative: a match requires a short message
(<= MAX_WORDS) so a real, longer grievance that happens to contain "please
look into it" as one clause is never miscategorized.
"""
import re

MAX_WORDS = 12

# tone -> {language: [phrase, ...]}. Phrases are matched as whole-word/
# whole-phrase patterns against normalized text (lowercase, punctuation
# stripped, collapsed whitespace). Keep phrases short and distinctive;
# false negatives here just mean the AI fallback (Phase B) handles it.
_PHRASES: dict[str, dict[str, list[str]]] = {
    "grateful": {
        "English": ["thank you", "thanks", "thank you so much", "much appreciated", "appreciate it"],
        "Hindi": ["dhanyavad", "shukriya", "bahut dhanyavad", "aapka dhanyavad"],
        "Hinglish": ["thank you", "thanks", "dhanyavad", "shukriya"],
        "Marathi": ["dhanyavad", "aabhari aahe", "khup dhanyavad"],
        "Kannada": ["dhanyavadagalu", "thanks", "vandanegalu"],
    },
    "urging": {
        "English": [
            "please look into it urgently", "please take action", "need action",
            "we need action", "please act fast", "please resolve this soon",
            "dont just register", "not just register", "please expedite",
            "please prioritize this",
        ],
        "Hindi": [
            "jaldi karvai kijiye", "turant karvai kijiye", "sirf darj mat kijiye",
            "kripya jald karvai", "kaam turant kijiye",
        ],
        "Hinglish": [
            "please jaldi karo", "koi action lo", "sirf register mat karo",
            "jaldi karvai karo", "turant action lijiye",
        ],
        "Marathi": ["lavkar karvai kara", "फक्त नोंद करू नका", "त्वरित कारवाई करा"],
        "Kannada": ["dayavittu shighra kramavahisi", "tvarita kriya kaigolli"],
    },
    "status_inquiry": {
        "English": [
            "any update", "any updates", "what is the status", "still pending",
            "still no action", "nothing happened yet", "no response yet",
            "is still pending",
        ],
        "Hindi": ["koi update", "status kya hai", "abhi tak kuch nahi hua", "abhi bhi pending hai"],
        "Hinglish": ["koi update hai kya", "status kya hai", "abhi tak kuch nahi hua"],
        "Marathi": ["kahi update ahe ka", "status kay ahe", "ajun kahi zala nahi"],
        "Kannada": ["yenadru update ide?", "status enu"],
    },
    "other": {
        "English": ["i have attached the photo", "attached the photo", "sent the photo"],
        "Hindi": ["photo bhej diya hai", "photo attach kar diya"],
        "Hinglish": ["photo bhej diya hai", "photo attach kiya hai"],
        "Marathi": ["photo pathavla ahe"],
        "Kannada": ["photo kalisiddene"],
    },
}


def _normalize(text: str) -> str:
    lowered = (text or "").lower()
    stripped = re.sub(r"[^\w\s]", "", lowered)
    return re.sub(r"\s+", " ", stripped).strip()


def detect_case_comment(text: str, languages: list[str]) -> tuple[bool, str | None]:
    """Return (matched, tone) for a message given the tenant's configured
    languages. tone is one of grateful|urging|status_inquiry|other, or None
    if no match — callers should fall through to the AI classifier.
    """
    normalized = _normalize(text)
    if not normalized:
        return (False, None)
    if len(normalized.split()) > MAX_WORDS:
        return (False, None)

    language_set = set(languages or [])
    for tone, by_language in _PHRASES.items():
        for language, phrases in by_language.items():
            if language not in language_set:
                continue
            for phrase in phrases:
                phrase_normalized = _normalize(phrase)
                if not phrase_normalized:
                    continue
                pattern = r"\b" + re.escape(phrase_normalized) + r"\b"
                if re.search(pattern, normalized):
                    return (True, tone)
    return (False, None)
