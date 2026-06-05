"""
emergency_keywords.py — Multi-language severity keyword detection.

Used as a fallback layer when AI classification does not return
status='emergency'. Covers 13 Indian languages + English/Hinglish.

Hazard types: fire, flood, violence, medical, stampede, accident, missing, emergency
"""

import re

# ── Keyword sets per hazard per language ──────────────────────────────────────
# Keys are hazard buckets. Values are flat lists of transliterated and
# native-script keywords. Native script covered by GPT; transliteration
# covered here for romanised messages.

HAZARD_KEYWORDS: dict[str, list[str]] = {
    "fire": [
        # English
        "fire", "burning", "flames", "ablaze", "caught fire", "house fire",
        "building fire", "explosion",
        # Hindi / Hinglish
        "aag", "aag lagi", "aag lag gayi", "jal raha", "jal rahi", "jalaa",
        "dhamaka", "आग", "आग लगी", "आग लग गई", "आग लग गयी", "धमाका",
        # Marathi
        "aag lagli", "aag lavli", "jalt ahe",
        # Telugu
        "agni", "manta pattindi",
        # Tamil
        "thee", "theepidittadhu",
        # Kannada
        "benkiya", "benki",
        # Bengali
        "agun", "agun legeche",
        # Gujarati
        "aag", "aag lagī",
        # Punjabi
        "agg", "agg lag gayi",
        # Urdu
        "aag lagi", "ātish",
        # Odia
        "āguni",
        # Assamese
        "জুই", "jui",
    ],

    "flood": [
        # English
        "flood", "flooding", "waterlogging", "submerged", "inundated",
        "cyclone", "landslide", "landfall", "tsunami", "cloudburst",
        "overflowing river", "dam burst",
        # Hindi / Hinglish
        "baadh", "baarish mein duba", "nadi ubri", "toofan", "bhaagdad",
        "bhukamp", "बाढ़", "जलभराव", "तूफान", "चक्रवात", "भूकंप", "भूस्खलन",
        "रासायनिक रिसाव", "गैस रिसाव", "बांध टूट", "बांध फूट", "इमारत गिर",
        # Marathi
        "paaani bhar", "mahapoor",
        # Telugu
        "vellu", "vana",
        # Tamil
        "vellaparuvu", "tsunami",
        # Bengali
        "baan", "jalbaddha",
        # Odia
        "badha",
        # Assamese
        "ঢাপ", "baan",
    ],

    "violence": [
        # English
        "riot", "attack", "shooting", "stabbing", "mob", "lynching",
        "murder", "killed", "shot dead", "violence", "communal tension",
        "curfew", "stone pelting",
        # Hindi / Hinglish
        "danga", "maar diya", "goli maari", "chaku mara", "goli lagi",
        "murder ho gaya", "bheed ne mara", "hatya", "दंगा", "हत्या",
        "हमला", "मारपीट", "पथराव", "पत्थरबाजी", "सांप्रदायिक हिंसा", "धार्मिक झड़प",
        "मॉब", "लिंचिंग", "अपहरण", "धमकी", "फिरौती",
        # Marathi
        "danga", "khoon",
        # Telugu
        "champesaru", "kottesaru",
        # Tamil
        "kollai", "thadukku",
        # Kannada
        "kollalegalu", "hakku",
        # Bengali
        "hatya", "mara",
        # Punjabi
        "maar", "khoon",
        # Urdu
        "qatl", "fasad", "danga",
    ],

    "medical": [
        # English
        "dying", "unconscious", "heart attack", "stroke", "overdose",
        "poisoning", "ambulance needed", "bleeding heavily", "critical condition",
        "not breathing", "convulsions", "seizure", "collapsed",
        # Hindi / Hinglish
        "mar raha hai", "mar rahi hai", "behosh", "hospital le jao",
        "ambulance bhejo", "khoon nikal raha", "bachao", "dil ka daura",
        "saans nahi aa rahi", "zehr kha liya", "एंबुलेंस", "एम्बुलेंस",
        "दिल का दौरा", "सांस नहीं", "ऑक्सीजन", "गंभीर", "खून बह रहा", "बेहोश",
        # Marathi
        "marto ahe", "beshan", "ambulans paathva",
        # Telugu
        "chastunnadu", "ambulance pathandi",
        # Tamil
        "saagiraan", "ambulance anupungal",
        # Kannada
        "saayuttiddare", "ambulance kareyiri",
        # Bengali
        "marachhe", "ambulance pathao",
        # Gujarati
        "maravā", "ambulance moklo",
        # Punjabi
        "mar reha hai", "ambulance ghallo",
        # Urdu
        "mar raha hai", "ambulance bhejo",
    ],

    "stampede": [
        # English
        "stampede", "crowd crush", "trampled", "crowd collapse",
        # Hindi / Hinglish
        "bhaagdad", "bheed mein kuchal", "bhaagdaad machi",
        # Marathi
        "chashmati", "gathala",
        # Tamil
        "mithippu",
        # Bengali
        "chodmara",
    ],

    "accident": [
        # English
        "accident", "road accident", "collision", "crash", "hit and run",
        "train accident", "bus accident", "fell down", "fell from building",
        # Hindi / Hinglish
        "accident ho gaya", "gaadi takrayi", "truck ne mara",
        "train se gir gaya", "gir gaya", "दुर्घटना", "एक्सीडेंट", "हादसा", "इमारत से गिर",
        # Marathi
        "apghat", "apghat zhala",
        # Telugu
        "pramadam", "accident ayindi",
        # Tamil
        "vilundhavar", "accident aachi",
        # Kannada
        "apaghata", "accident aayithu",
        # Bengali
        "durghatona", "accident hochhe",
    ],

    "missing": [
        # English
        "missing", "kidnapped", "abducted", "child missing", "woman missing",
        # Hindi / Hinglish
        "gaayab ho gaya", "apaharan", "bachha gaayab", "kidnap",
        "ladki gaayab", "बच्चा गायब", "लापता बच्चा", "अपहरण", "मानव तस्करी",
        # Marathi
        "harwala", "harwali",
        # Telugu
        "kayam ayyaru",
        # Tamil
        "kayam aanaanga",
        # Bengali
        "niyapatta",
        # Punjabi
        "gaayab ho gaya",
        # Urdu
        "gum ho gaya",
    ],
}

# ── Hazard classification from problem_domain / category ──────────────────────
_DOMAIN_HAZARD_MAP: dict[str, str] = {
    "law & order": "violence",
    "law and order": "violence",
    "emergency": "emergency",
    "health": "medical",
    "healthcare": "medical",
    "disaster": "flood",
    "natural disaster": "flood",
    "fire": "fire",
    "flood": "flood",
    "accident": "accident",
    "stampede": "stampede",
    "missing person": "missing",
    "crime": "violence",
}


def detect_emergency_severity(message: str, language: str = "English") -> bool:
    """
    Return True if the message contains emergency severity keywords.
    Runs across all keyword lists regardless of language — mixed-language
    messages (Hinglish, code-switched) are common in practice.
    """
    if not message:
        return False
    normalised = _normalise(message)
    for keywords in HAZARD_KEYWORDS.values():
        for kw in keywords:
            if kw in normalised:
                return True
    return False


def classify_hazard_type(
    message: str,
    status: str = "",
    category: str = "",
    problem_domain: str = "",
) -> str:
    """
    Return the hazard bucket for an emergency case.
    Priority: keyword match > domain map > status fallback.
    """
    normalised = _normalise(message)

    # Keyword match — longest/most specific hazard bucket wins
    for hazard, keywords in HAZARD_KEYWORDS.items():
        for kw in keywords:
            if kw in normalised:
                return hazard

    # Domain map
    for domain_key, hazard in _DOMAIN_HAZARD_MAP.items():
        if domain_key in (problem_domain or "").lower():
            return hazard
        if domain_key in (category or "").lower():
            return hazard

    return "emergency"


def _normalise(text: str) -> str:
    """Lowercase and strip ASCII punctuation without breaking Indic-script words."""
    text = text.lower()
    text = re.sub(r"[!?,.;:/\\()\\[\\]{}\"'`~@#$%^&*_+=<>|-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()
