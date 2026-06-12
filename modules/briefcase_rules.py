"""
Deterministic civic guardrail rules + venue-word suppression for Briefcase intake.

Design stance (see BRIEFCASE_INTELLIGENCE_ARCHITECTURE.md):
- AI output is a HINT layer, never final truth.
- These rules are the DECISION layer: predicate-anchored, high-precision
  patterns that lock the problem domain regardless of what the model said.
- A venue/landmark word (school, hospital, depot, ...) may determine the
  category ONLY when the complaint targets the institution itself — never
  when it merely anchors a location ("school ke saamne naali bhar gayi").
- If neither a rule, the AI hint, nor keyword inference is supported by the
  citizen's actual words, the answer is UNKNOWN (+ review), never a guess.

This module is import-light on purpose: no OpenAI, no DB. Pure functions over
the raw message text so they are trivially unit-testable and can never fail
the intake pipeline.
"""

from __future__ import annotations

import logging
import re

from sansadx_backend.unified_taxonomy import (
    CANONICAL_CATEGORIES,
    GENERIC_DOMAIN_INPUTS,
    PROBLEM_SUBDOMAINS_BY_DOMAIN,
    SUBDOMAIN_SIGNALS,
    SUBDOMAIN_TO_PROGRAM_TYPE,
    VALID_CATEGORIES,
    _CORRUPTION_EXPLICIT_MARKERS,
    _CORRUPTION_OFFICIAL_MARKERS,
    _DEMAND_MARKERS,
    _PAYMENT_MARKERS,
    _WORKFLOW_CONTEXT_MARKERS,
    _infer_subdomain_from_text,
    _looks_like_water_supply_outage,
    infer_emergency_taxonomy_override,
)

logger = logging.getLogger("needle.briefcase_rules")

RULES_VERSION = "briefcase_rules_v1"

# ──────────────────────────────────────────────────────────────────────────────
# Venue / landmark lexicon
# ──────────────────────────────────────────────────────────────────────────────
# venue token → domain that the venue word would naively pull the classifier to.
# Tokens are matched on normalized lowercase text with word boundaries.
VENUE_DOMAIN_PULL: dict[str, str] = {
    # Education venues
    "school": "Education",
    "shala": "Education",
    "vidyalaya": "Education",
    "college": "Education",
    "university": "Education",
    "anganwadi": "Education",
    "स्कूल": "Education",
    "शाळा": "Education",
    "विद्यालय": "Education",
    "कॉलेज": "Education",
    "आंगनवाड़ी": "Education",
    # Health venues
    "hospital": "Health",
    "dawakhana": "Health",
    "davakhana": "Health",
    "clinic": "Health",
    "dispensary": "Health",
    "phc": "Health",
    "chc": "Health",
    "अस्पताल": "Health",
    "दवाखाना": "Health",
    # Transport venues
    "depot": "Infrastructure & Utilities",
    "bus stand": "Infrastructure & Utilities",
    "bus stop": "Infrastructure & Utilities",
    "station": "Infrastructure & Utilities",
    "डिपो": "Infrastructure & Utilities",
    "स्टेशन": "Infrastructure & Utilities",
    "बस स्टैंड": "Infrastructure & Utilities",
    # Religious / community venues
    "mandir": "Social Issues",
    "temple": "Social Issues",
    "masjid": "Social Issues",
    "mosque": "Social Issues",
    "church": "Social Issues",
    "gurudwara": "Social Issues",
    "मंदिर": "Social Issues",
    "मस्जिद": "Social Issues",
    "गुरुद्वारा": "Social Issues",
    # Administrative venues
    "office": "Bureaucratic / Administrative",
    "daftar": "Bureaucratic / Administrative",
    "tehsil": "Bureaucratic / Administrative",
    "कार्यालय": "Bureaucratic / Administrative",
    "दफ्तर": "Bureaucratic / Administrative",
    "तहसील": "Bureaucratic / Administrative",
    # Police venues
    "thana": "Law & Order",
    "police station": "Law & Order",
    "थाना": "Law & Order",
    # Market venues
    "market": "Infrastructure & Utilities",
    "mandi": "Agriculture",
    "बाजार": "Infrastructure & Utilities",
    "मंडी": "Agriculture",
}

# Positional words that mark a venue as a LANDMARK (location anchor), not the
# subject of the complaint. Multi-language + transliteration.
_NEARNESS_WORDS = (
    "ke pass", "ke paas", "paas", "pass",
    "ke saamne", "ke samne", "saamne", "samne", "samor", "samore",
    "ke peeche", "peeche", "piche", "ke pichhe",
    "ke aage", "aage",
    "ke bagal", "bagal", "baju", "bajula", "shejari",
    "javal", "jawal", "javalcha",
    "hattira", "pakkadalli", "hatra",
    "near", "next to", "beside", "behind", "in front of", "opposite", "outside",
    "ke pass wali", "ke samne wali", "wali",
    "के पास", "के सामने", "सामने", "के पीछे", "पीछे", "के आगे", "बगल",
    "जवळ", "समोर", "शेजारी", "च्या जवळ",
    "ಹತ್ತಿರ", "ಪಕ್ಕದಲ್ಲಿ",
    "road par", "road pe", "road par hi", "रोड पर", "रोड पे",
)

# Locative/subject markers: venue followed by these → complaint is ABOUT the
# institution ("school mein teacher nahi", "hospital madhe doctor nahi").
_INSTITUTION_SUBJECT_WORDS = (
    "mein", "me", "mai", "madhe", "madhye", "alli", "ali", "andar",
    "में", "मध्ये", "ಅಲ್ಲಿ", "ನಲ್ಲಿ",
)

# Institution-failure verbs: venue + these → complaint about the institution
# even without a locative marker ("anganwadi nahi khulti", "depot band hai").
_INSTITUTION_FAILURE_WORDS = (
    "band", "bandh", "बंद", "nahi khulta", "nahi khulti", "nahi khul",
    "nahi chalta", "nahi chalti", "nahi chal",
    "admit nahi", "ilaj nahi", "treatment nahi", "dawai nahi",
    "kabhi nahi", "nahi aata", "nahi aate", "nahi milta", "nahi milte",
    "staff nahi", "doctor nahi", "teacher nahi", "nurse nahi",
)


def _norm_text(text: str) -> str:
    lowered = str(text or "").lower()
    lowered = re.sub(r"[^\w\sऀ-ൿ]", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _word_pattern(token: str) -> str:
    # \b is unreliable around Devanagari; fall back to whitespace boundaries.
    if re.search(r"[ऀ-ൿ]", token):
        return r"(?:^|\s)" + re.escape(token)
    return r"\b" + re.escape(token) + r"\b"


def _contains_word(blob: str, token: str) -> bool:
    return re.search(_word_pattern(token), blob) is not None


def _has_any(blob: str, markers) -> bool:
    return any(marker in blob for marker in markers)


# ──────────────────────────────────────────────────────────────────────────────
# Venue context detection
# ──────────────────────────────────────────────────────────────────────────────
def detect_venue_context(raw_message: str) -> dict:
    """
    Separate "complaint about an institution" from "landmark used as location".

    Returns:
        {
          "venues": [token, ...],                 # venue words present
          "landmark_venues": [token, ...],        # venue in landmark position
          "institution_subject_venues": [token],  # complaint targets the venue
        }
    """
    blob = _norm_text(raw_message)
    venues: list[str] = []
    landmark: list[str] = []
    subject: list[str] = []

    if not blob:
        return {"venues": [], "landmark_venues": [], "institution_subject_venues": []}

    for token in VENUE_DOMAIN_PULL:
        if not _contains_word(blob, token):
            continue
        venues.append(token)

        is_subject = False
        is_landmark = False

        # venue + locative/subject marker right after → about the institution
        for marker in _INSTITUTION_SUBJECT_WORDS:
            if re.search(
                _word_pattern(token) + r"\s+" + re.escape(marker) + r"(?:\s|$)",
                blob,
            ):
                is_subject = True
                break
        if not is_subject:
            for marker in _INSTITUTION_FAILURE_WORDS:
                if re.search(_word_pattern(token) + r"[\s\w]{0,12}?" + re.escape(marker), blob):
                    is_subject = True
                    break

        # venue + nearness word → landmark position
        if not is_subject:
            for near in _NEARNESS_WORDS:
                if re.search(
                    _word_pattern(token) + r"\s*(?:ke|ki|ka|chya|च्या|के|की|का)?\s*" + re.escape(near) + r"(?:\s|$)",
                    blob,
                ) or re.search(re.escape(near) + r"\s*" + _word_pattern(token), blob):
                    is_landmark = True
                    break

        if is_subject:
            subject.append(token)
        elif is_landmark:
            landmark.append(token)

    return {
        "venues": venues,
        "landmark_venues": landmark,
        "institution_subject_venues": subject,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Predicate-anchored civic rules (Lane A)
# ──────────────────────────────────────────────────────────────────────────────
# Each rule: nouns AND predicates must co-occur, OR a self-sufficient phrase
# matches. High precision over recall — these LOCK the domain.

_GENERIC_FAILURE = (
    "nahi", "nahin", "nhi", "नहीं", "नाही", "illa", "illai", "band", "बंद",
    "kharab", "खराब", "toot", "tut", "टूट", "तुट", "broken", "not working",
    "problem", "samasya", "समस्या", "pareshani", "परेशानी", "shikayat", "शिकायत",
)

_CIVIC_RULES: tuple[dict, ...] = (
    {
        "id": "R_DRAINAGE",
        "domain": "Infrastructure & Utilities",
        "subdomain": "Drainage/Sewage",
        "nouns": (
            "naali", "nali", "nalli ", "नाली", "gutter", "gatar", "गटर",
            "drain", "drainage", "sewage", "sewer", "nala", "manhole",
        ),
        "predicates": (
            "bhar", "भर", "choke", "chok", "चोक", "jam", "block", "overflow",
            "band", "बंद", "saaf nahi", "साफ नहीं", "tumbli", "bharli", "toot", "टूट",
            "ganda", "गंदा", "gandagi", "गंदगी",
        ),
        "phrases": (
            "water logging", "waterlogging", "jal jamav", "जलजमाव", "जल जमाव",
            "paani bhar jata", "pani bhar jata", "पानी भर जाता", "baarish mein paani bhar",
            "stagnant water", "sewage overflow", "drainage issue", "drainage problem",
            "sewer issue", "sewer problem", "gutter issue", "gutter problem",
        ),
    },
    {
        "id": "R_GARBAGE",
        "domain": "Infrastructure & Utilities",
        "subdomain": "Solid Waste",
        "nouns": (
            "kachra", "kachara", "kacra", "khachra", "kachre", "कचरा", "कचरे",
            "garbage", "waste", "trash", "rubbish", "dustbin", "डस्टबिन", "kasa",
        ),
        "predicates": (
            "nahi utht", "nahi uthay", "uthta nahi", "uthat nahi", "नहीं उठ",
            "saaf nahi", "safai nahi", "सफाई नहीं", "jal raha", "jala", "जल रहा",
            "dher", "ढेर", "pada", "padla", "पड़ा", "bhar", "भर", "dump",
            "collect nahi", "not collected", "not picked", "eturilla", "etturilla",
            "uchalat nahi",
        ),
        "phrases": (
            "safai nahi hoti", "kachre ka dhair", "kachre ka dher", "sweeper nahi",
            "safai karmchari nahi", "kasa eturilla", "कचरा नहीं उठता",
        ),
    },
    {
        "id": "R_ROAD",
        "domain": "Infrastructure & Utilities",
        "subdomain": "Roads & Bridges",
        "nouns": (
            "road", "sadak", "rasta", "raste", "rastya", "सड़क", "रास्ता", "रस्ता",
            "bridge", "pul", "पुल", "culvert", "flyover",
        ),
        "predicates": (
            "toot", "tut", "टूट", "तुट", "tutla", "tutli", "kharab", "खराब",
            "gadd", "khadd", "गड्ढ", "खड्ड", "pothole", "kacchi", "कच्ची",
            "band", "बंद", "doob", "डूब", "keechar", "कीचड़", "broken", "damaged",
        ),
        "phrases": (
            "pothole", "potholes", "gadde hain", "khadde hain", "गड्ढे",
        ),
    },
    {
        "id": "R_POWER",
        "domain": "Infrastructure & Utilities",
        "subdomain": "Power & Street Lighting",
        "nouns": (
            "bijli", "बिजली", "light", "लाइट", "current", "करंट", "electricity",
            "transformer", "ट्रांसफार्मर", "streetlight", "street light",
            "batti", "बत्ती", "vij", "वीज", "khamba", "खंभा", "pole", "voltage",
        ),
        "predicates": (
            "nahi", "nahin", "नहीं", "नाही", "gayi", "गई", "gul", "band", "बंद",
            "cut", "kat", "jal gaya", "जल गया", "kharab", "खराब", "toot", "टूट",
            "latki", "लटकी", "illa", "baruttilla", "jalat nahi", "jalti nahi",
        ),
        "phrases": (
            "power cut", "load shedding", "लोड शेडिंग", "current nahi",
            "light chali gayi", "बिजली नहीं",
        ),
    },
    {
        "id": "R_FIR_POLICE",
        "domain": "Law & Order",
        "subdomain": "FIR/Police Inaction",
        "nouns": (),
        "predicates": (),
        "phrases": (
            "fir nahi", "fir darj nahi", "fir likh nahi", "fir nahi likh",
            "f i r nahi", "report darj nahi", "रिपोर्ट दर्ज नहीं",
            "police sun nahi", "police nahi sun", "police kuch nahi",
            "police complaint nahi", "complaint nahi le", "complaint nahi likh",
            "thana complaint nahi", "thane wale fir", "police inaction",
            "एफआईआर नहीं", "एफ आई आर नहीं", "पुलिस नहीं सुन", "पुलिस सुन नहीं",
            "पुलिस कुछ नहीं",
        ),
    },
)


def apply_civic_rules(raw_message: str) -> dict | None:
    """
    Run predicate-anchored deterministic rules over the raw message.

    Returns {"rule_id", "problem_domain", "problem_subdomain"} on a hit,
    else None. Order encodes priority: emergency > corruption > FIR > civic.
    """
    blob = _norm_text(raw_message)
    if not blob:
        return None

    # 1. Emergency lexicon (delegates to the existing authoritative detector)
    emergency_domain, emergency_subdomain = infer_emergency_taxonomy_override(blob)
    if emergency_domain and emergency_subdomain:
        return {
            "rule_id": "R_EMERGENCY",
            "problem_domain": emergency_domain,
            "problem_subdomain": emergency_subdomain,
        }

    # 2. Bribery/corruption — outranks the sector the file concerns.
    has_explicit_corruption = _has_any(blob, _CORRUPTION_EXPLICIT_MARKERS)
    has_payment_demand = _has_any(blob, _PAYMENT_MARKERS) and _has_any(blob, _DEMAND_MARKERS)
    has_official_context = _has_any(blob, _CORRUPTION_OFFICIAL_MARKERS) or _has_any(blob, _WORKFLOW_CONTEXT_MARKERS)
    if (has_explicit_corruption or has_payment_demand) and has_official_context:
        return {
            "rule_id": "R_BRIBERY",
            "problem_domain": "Bureaucratic / Administrative",
            "problem_subdomain": "Bribery/Corruption",
        }

    # 3. Water outage (existing high-precision detector)
    if _looks_like_water_supply_outage(blob):
        return {
            "rule_id": "R_WATER",
            "problem_domain": "Infrastructure & Utilities",
            "problem_subdomain": "Water Supply",
        }

    # 4. Civic noun + predicate rules
    for rule in _CIVIC_RULES:
        if any(phrase in blob for phrase in rule["phrases"]):
            return {
                "rule_id": rule["id"],
                "problem_domain": rule["domain"],
                "problem_subdomain": rule["subdomain"],
            }
        if rule["nouns"] and rule["predicates"]:
            if _has_any(blob, rule["nouns"]) and _has_any(blob, rule["predicates"]):
                return {
                    "rule_id": rule["id"],
                    "problem_domain": rule["domain"],
                    "problem_subdomain": rule["subdomain"],
                }

    return None


# ──────────────────────────────────────────────────────────────────────────────
# Keyword confirmation of an AI hint
# ──────────────────────────────────────────────────────────────────────────────
def _ai_domain_keyword_confirmed(blob: str, domain: str, landmark_venues: list[str]) -> bool:
    """
    True when the message contains an independent keyword signal for the AI's
    chosen domain — excluding venue words sitting in landmark position.
    """
    if domain not in PROBLEM_SUBDOMAINS_BY_DOMAIN:
        return False
    landmark_set = set(landmark_venues)
    for subdomain in PROBLEM_SUBDOMAINS_BY_DOMAIN[domain]:
        for signal in SUBDOMAIN_SIGNALS.get(subdomain, ()):
            if signal in landmark_set:
                continue  # a landmark venue word is not category evidence
            if signal in blob:
                # Signal must not itself be a landmark-positioned venue word
                if signal in VENUE_DOMAIN_PULL and signal in landmark_set:
                    continue
                return True
    return False


def _strip_venue_words(blob: str, venues: list[str]) -> str:
    cleaned = blob
    for token in venues:
        cleaned = re.sub(_word_pattern(token), " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


# ──────────────────────────────────────────────────────────────────────────────
# Arbitration: rules > confirmed AI hint > keyword inference > UNKNOWN
# ──────────────────────────────────────────────────────────────────────────────
def arbitrate_category(
    ai_domain: str | None,
    ai_subdomain: str | None,
    raw_message: str,
) -> dict:
    """
    Decide the final category from all signal lanes. The AI label is a hint:
    it survives only if confirmed by deterministic evidence; otherwise it is
    flagged for review or replaced by UNKNOWN. Never guesses.

    Returns:
        {
          "problem_domain": str | None,      # None == UNKNOWN
          "problem_subdomain": str | None,
          "confidence": "rule_locked" | "ai_keyword_confirmed"
                        | "venue_suppressed_inferred" | "keyword_inferred"
                        | "ai_unconfirmed" | "unknown",
          "decided_by": str,
          "needs_review": bool,
          "venue_suppressed": bool,
          "rule_id": str | None,
        }
    """
    blob = _norm_text(raw_message)
    venue_ctx = detect_venue_context(raw_message)
    landmark_venues = venue_ctx["landmark_venues"]

    ai_domain_clean = str(ai_domain or "").strip()
    ai_domain_valid = ai_domain_clean in VALID_CATEGORIES and ai_domain_clean.lower() not in GENERIC_DOMAIN_INPUTS

    # Lane A — deterministic rules always win.
    rule_hit = apply_civic_rules(raw_message)
    if rule_hit:
        if ai_domain_valid and ai_domain_clean != rule_hit["problem_domain"]:
            logger.info(
                "CATEGORY_ARBITER model_disagreement rule=%s rule_domain=%r ai_domain=%r msg=%r",
                rule_hit["rule_id"], rule_hit["problem_domain"], ai_domain_clean, raw_message[:160],
            )
        return {
            "problem_domain": rule_hit["problem_domain"],
            "problem_subdomain": rule_hit["problem_subdomain"],
            "confidence": "rule_locked",
            "decided_by": f"rule:{rule_hit['rule_id']}",
            "needs_review": False,
            "venue_suppressed": bool(landmark_venues),
            "rule_id": rule_hit["rule_id"],
        }

    # Lane B — AI hint, validated.
    if ai_domain_valid:
        # Venue-word suppression: AI picked the domain a landmark venue pulls
        # toward, and there is no independent evidence for that domain.
        venue_pulled = any(
            VENUE_DOMAIN_PULL.get(v) == ai_domain_clean for v in landmark_venues
        )
        confirmed = _ai_domain_keyword_confirmed(blob, ai_domain_clean, landmark_venues)

        if venue_pulled and not confirmed:
            stripped = _strip_venue_words(blob, venue_ctx["venues"])
            inferred_domain, inferred_subdomain = _infer_subdomain_from_text(stripped)
            if inferred_domain:
                logger.info(
                    "CATEGORY_ARBITER venue_suppressed ai_domain=%r -> %r via landmark venues %s msg=%r",
                    ai_domain_clean, inferred_domain, landmark_venues, raw_message[:160],
                )
                return {
                    "problem_domain": inferred_domain,
                    "problem_subdomain": inferred_subdomain,
                    "confidence": "venue_suppressed_inferred",
                    "decided_by": "venue_suppression",
                    "needs_review": True,
                    "venue_suppressed": True,
                    "rule_id": None,
                }
            # Venue word was the only signal → UNKNOWN, review.
            return {
                "problem_domain": None,
                "problem_subdomain": None,
                "confidence": "unknown",
                "decided_by": "venue_suppression",
                "needs_review": True,
                "venue_suppressed": True,
                "rule_id": None,
            }

        if confirmed:
            return {
                "problem_domain": ai_domain_clean,
                "problem_subdomain": ai_subdomain,
                "confidence": "ai_keyword_confirmed",
                "decided_by": "ai+keyword",
                "needs_review": False,
                "venue_suppressed": False,
                "rule_id": None,
            }

        # Unconfirmed AI hint: keep it (it is still the best signal available)
        # but it is a hint — flag for operator review, never silent truth.
        return {
            "problem_domain": ai_domain_clean,
            "problem_subdomain": ai_subdomain,
            "confidence": "ai_unconfirmed",
            "decided_by": "ai_hint_unconfirmed",
            "needs_review": True,
            "venue_suppressed": False,
            "rule_id": None,
        }

    # Lane C — no usable AI hint: deterministic keyword inference only.
    inferred_domain, inferred_subdomain = _infer_subdomain_from_text(
        _strip_venue_words(blob, landmark_venues)
    )
    if inferred_domain:
        return {
            "problem_domain": inferred_domain,
            "problem_subdomain": inferred_subdomain,
            "confidence": "keyword_inferred",
            "decided_by": "keyword_fallback",
            "needs_review": True,
            "venue_suppressed": bool(landmark_venues),
            "rule_id": None,
        }

    # Nothing is supported by the citizen's words → UNKNOWN, never a guess.
    return {
        "problem_domain": None,
        "problem_subdomain": None,
        "confidence": "unknown",
        "decided_by": "none",
        "needs_review": True,
        "venue_suppressed": bool(landmark_venues),
        "rule_id": None,
    }


def taxonomy_fields_for_decision(decision: dict) -> dict:
    """
    Build storage-ready taxonomy fields from an arbitration decision without
    re-running inference (which could re-introduce a default guess).
    """
    domain = decision.get("problem_domain")
    if not domain or domain not in VALID_CATEGORIES:
        return {
            "problem_domain": None,
            "problem_subdomain": None,
            "convergence_program_type": None,
            "categories": [],
        }
    subdomain = decision.get("problem_subdomain")
    valid_subdomains = PROBLEM_SUBDOMAINS_BY_DOMAIN.get(domain, ())
    if subdomain not in valid_subdomains:
        subdomain = None
    return {
        "problem_domain": domain,
        "problem_subdomain": subdomain,
        "convergence_program_type": (
            SUBDOMAIN_TO_PROGRAM_TYPE.get(subdomain, "Service Delivery Strengthening")
            if subdomain
            else "Service Delivery Strengthening"
        ),
        "categories": [domain],
    }
