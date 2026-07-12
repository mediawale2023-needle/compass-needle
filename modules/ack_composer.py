"""Composer for citizen-facing status updates.

Templates own the sentences, code owns the commitments: the caller supplies a
case *status* and the citizen's detected language, and the composer returns a
fixed, policy-compliant message. The only variable part is an optional issue
phrase ("water supply issue") looked up from a pre-translated dictionary —
never free-form model output — so the wording is byte-identical for the same
inputs regardless of which LLM the platform runs on.

No case reference numbers, no outcome promises, no deadlines, no emotional
language: see modules/ack_policy.py. Golden tests pin the exact strings.
"""
from modules.localized_replies import ensure_ji_prefix, normalize_language_name

POLICY_STATUSES = {"received", "in_progress", "resolved", "closed"}

_STATUS_ALIASES = {
    "new": "received",
    "pending": "received",
    "pending_review": "received",
    "awaiting_location": "received",
    "incomplete": "received",
    "escalated": "in_progress",
    "in_progress": "in_progress",
    "resolved": "resolved",
    "completed": "resolved",
    "closed": "closed",
}

# {issue} is replaced via str.replace (never .format) with a pre-translated
# noun phrase in matching language, or removed together with its brackets
# when no phrase is available.
_STATUS_TEMPLATES: dict[str, dict[str, str]] = {
    "received": {
        "Hindi": "Aapki shikayat{issue} hamare paas darj hai aur review mein hai 🙏 Jaise hi koi update hoga, hum aapko batayenge.",
        "Hinglish": "Aapki complaint{issue} hamare paas registered hai aur review mein hai 🙏 Jaise hi koi update hoga, hum aapko batayenge.",
        "Marathi": "तुमची तक्रार{issue} आमच्याकडे नोंदलेली आहे आणि पुनरावलोकनात आहे 🙏 काही अपडेट मिळताच आम्ही तुम्हाला कळवू.",
        "Kannada": "ನಿಮ್ಮ ದೂರು{issue} ನಮ್ಮ ಬಳಿ ದಾಖಲಾಗಿದೆ ಮತ್ತು ಪರಿಶೀಲನೆಯಲ್ಲಿದೆ 🙏 ಯಾವುದೇ ಮಾಹಿತಿ ಸಿಕ್ಕ ತಕ್ಷಣ ನಾವು ನಿಮಗೆ ತಿಳಿಸುತ್ತೇವೆ.",
        "English": "Your complaint{issue} is registered with us and under review 🙏 We will let you know as soon as there is an update.",
    },
    "in_progress": {
        "Hindi": "Aapki shikayat{issue} par kaam chal raha hai 🙏 Jaise hi koi update hoga, hum aapko batayenge.",
        "Hinglish": "Aapki complaint{issue} par kaam chal raha hai 🙏 Jaise hi koi update hoga, hum aapko batayenge.",
        "Marathi": "तुमच्या तक्रारीवर{issue} काम सुरू आहे 🙏 काही अपडेट मिळताच आम्ही तुम्हाला कळवू.",
        "Kannada": "ನಿಮ್ಮ ದೂರಿನ{issue} ಮೇಲೆ ಕೆಲಸ ನಡೆಯುತ್ತಿದೆ 🙏 ಯಾವುದೇ ಮಾಹಿತಿ ಸಿಕ್ಕ ತಕ್ಷಣ ನಾವು ನಿಮಗೆ ತಿಳಿಸುತ್ತೇವೆ.",
        "English": "Work is underway on your complaint{issue} 🙏 We will let you know as soon as there is an update.",
    },
    "resolved": {
        "Hindi": "Aapki shikayat{issue} par karyavahi puri ho gayi hai 🙏 Agar samasya abhi bhi bani hui hai, to kripya humein isi number par bataiye.",
        "Hinglish": "Aapki complaint{issue} par karyavahi puri ho gayi hai 🙏 Agar problem abhi bhi hai, to please humein isi number par bataiye.",
        "Marathi": "तुमच्या तक्रारीवरील{issue} कार्यवाही पूर्ण झाली आहे 🙏 समस्या अजूनही असल्यास, कृपया आम्हाला याच नंबरवर कळवा.",
        "Kannada": "ನಿಮ್ಮ ದೂರಿನ{issue} ಮೇಲಿನ ಕ್ರಮ ಪೂರ್ಣಗೊಂಡಿದೆ 🙏 ಸಮಸ್ಯೆ ಇನ್ನೂ ಇದ್ದರೆ, ದಯವಿಟ್ಟು ಇದೇ ಸಂಖ್ಯೆಗೆ ತಿಳಿಸಿ.",
        "English": "Action on your complaint{issue} has been completed 🙏 If the problem still remains, please tell us on this same number.",
    },
    "closed": {
        "Hindi": "Aapki shikayat{issue} ko band kar diya gaya hai 🙏 Kisi bhi nayi samasya ke liye aap humein isi number par likh sakte hain.",
        "Hinglish": "Aapki complaint{issue} close kar di gayi hai 🙏 Kisi bhi nayi problem ke liye aap humein isi number par message kar sakte hain.",
        "Marathi": "तुमची तक्रार{issue} बंद करण्यात आली आहे 🙏 कोणत्याही नवीन समस्येसाठी तुम्ही आम्हाला याच नंबरवर लिहू शकता.",
        "Kannada": "ನಿಮ್ಮ ದೂರನ್ನು{issue} ಮುಚ್ಚಲಾಗಿದೆ 🙏 ಯಾವುದೇ ಹೊಸ ಸಮಸ್ಯೆಗೆ ನೀವು ಇದೇ ಸಂಖ್ಯೆಗೆ ಬರೆಯಬಹುದು.",
        "English": "Your complaint{issue} has been closed 🙏 For any new issue, you can write to us on this same number.",
    },
}

# Pre-translated issue phrases keyed by taxonomy subdomain (lowercased).
# This dictionary — not an LLM — is the only source of the {issue} slot, so
# swapping the underlying model can never change citizen-visible wording.
# Extend it as taxonomy coverage grows; a missing entry simply omits the slot.
_ISSUE_PHRASES: dict[str, dict[str, str]] = {
    "water supply": {
        "Hindi": "paani ki samasya",
        "Hinglish": "paani ki problem",
        "Marathi": "पाण्याची समस्या",
        "Kannada": "ನೀರಿನ ಸಮಸ್ಯೆ",
        "English": "the water supply issue",
    },
    "power & street lighting": {
        "Hindi": "bijli/street light ki samasya",
        "Hinglish": "bijli/street light ki problem",
        "Marathi": "वीज/पथदिव्यांची समस्या",
        "Kannada": "ವಿದ್ಯುತ್/ಬೀದಿ ದೀಪದ ಸಮಸ್ಯೆ",
        "English": "the electricity/street light issue",
    },
    "roads & bridges": {
        "Hindi": "sadak ki samasya",
        "Hinglish": "road ki problem",
        "Marathi": "रस्त्याची समस्या",
        "Kannada": "ರಸ್ತೆ ಸಮಸ್ಯೆ",
        "English": "the road issue",
    },
    "sanitation & waste": {
        "Hindi": "safai/kachre ki samasya",
        "Hinglish": "safai/garbage ki problem",
        "Marathi": "स्वच्छता/कचऱ्याची समस्या",
        "Kannada": "ಸ್ವಚ್ಛತೆ/ಕಸದ ಸಮಸ್ಯೆ",
        "English": "the sanitation/garbage issue",
    },
    "drainage & sewerage": {
        "Hindi": "naali/sewage ki samasya",
        "Hinglish": "drainage ki problem",
        "Marathi": "गटार/ड्रेनेजची समस्या",
        "Kannada": "ಚರಂಡಿ ಸಮಸ್ಯೆ",
        "English": "the drainage issue",
    },
}


def resolve_issue_phrase(problem_subdomain: str | None, detected_language: str = "") -> str | None:
    key = str(problem_subdomain or "").strip().lower()
    if not key:
        return None
    phrases = _ISSUE_PHRASES.get(key)
    if not phrases:
        return None
    language = normalize_language_name(detected_language, "Hindi")
    return phrases.get(language) or phrases.get("Hindi")


def compose_status_update(
    status: str,
    detected_language: str = "",
    *,
    problem_subdomain: str | None = None,
) -> str:
    """Return the fixed, policy-compliant citizen message for a case status.

    Unknown statuses map to "received" (a truthful receipt confirmation is
    always safe); unknown languages fall back to Hindi like every other
    citizen template in modules/localized_replies.py.
    """
    canonical = _STATUS_ALIASES.get(str(status or "").strip().lower(), "received")
    templates = _STATUS_TEMPLATES[canonical]
    language = normalize_language_name(detected_language, "Hindi")
    template = templates.get(language) or templates["Hindi"]

    phrase = resolve_issue_phrase(problem_subdomain, detected_language)
    if phrase:
        message = template.replace("{issue}", f" ({phrase})")
    else:
        message = template.replace("{issue}", "")
    return ensure_ji_prefix(message)
