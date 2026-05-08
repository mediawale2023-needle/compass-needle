import os
import requests
import json
import glob
import logging
import time
import difflib  # Logic for Fuzzy Matching (Typos)
import unicodedata  # FIX P1: Used for emoji/symbol detection in detect_input_language()
import re
from openai import OpenAI
from openai import RateLimitError, APIError, APIConnectionError
from modules.geography_resolver import resolve_location as resolve_geography_from_text
from .prompts import (
    CONVERGENCE_PROGRAM_TYPES_TEXT,
    SYSTEM_PROMPT,
    TAXONOMY_CATEGORIES,
    TAXONOMY_SUBDOMAINS,
)
from .unified_taxonomy import (
    CATEGORY_ALIASES as _CATEGORY_ALIASES,
    LEGACY_TO_CANONICAL as _LEGACY_TO_CANONICAL,
    VALID_CATEGORIES as _VALID_CATEGORIES,
    build_taxonomy_fields,
)
from modules.localized_replies import get_generic_ack_reply, get_missing_location_reply

# ==========================================
# 1. CONFIGURATION
# ==========================================
logger = logging.getLogger("needle.ai_engine")

# --- TAD NECESSARY: Removed global client initialization to prevent Railway boot crash ---
def get_client():
    """Helper to safely initialize OpenAI client after environment variables load."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)

# ── Category validation ───────────────────────────────────────────────────────


def _normalize_categories(cats: list, raw_message: str) -> list:
    """
    Validate and correct AI-returned categories against the 9 valid ones.
    Steps: exact → alias → fuzzy → taxonomy keyword fallback → default.
    Always returns a non-empty list.
    """
    if not isinstance(cats, list):
        cats = [cats] if cats else []

    valid_lower = {c.lower(): c for c in _VALID_CATEGORIES}
    result = []

    for cat in cats:
        if not isinstance(cat, str) or not cat.strip():
            continue
        cat_lower = cat.strip().lower()

        # 1. Exact match (case-insensitive)
        if cat_lower in valid_lower:
            result.append(valid_lower[cat_lower])
            continue

        # 2. Alias lookup
        if cat_lower in _CATEGORY_ALIASES:
            result.append(_CATEGORY_ALIASES[cat_lower])
            continue

        # 2b. Legacy exact-label lookup
        if cat.strip() in _LEGACY_TO_CANONICAL:
            result.append(_LEGACY_TO_CANONICAL[cat.strip()])
            continue

        # 3. Fuzzy match against valid category names
        fm = difflib.get_close_matches(cat_lower, valid_lower.keys(), n=1, cutoff=0.70)
        if fm:
            result.append(valid_lower[fm[0]])
            logger.info("Category fuzzy-corrected: '%s' → '%s'", cat.strip(), valid_lower[fm[0]])
            continue

        # 4. Fuzzy match against alias keys
        fm2 = difflib.get_close_matches(cat_lower, _CATEGORY_ALIASES.keys(), n=1, cutoff=0.70)
        if fm2:
            result.append(_CATEGORY_ALIASES[fm2[0]])
            logger.info("Category alias-fuzzy: '%s' → '%s'", cat.strip(), _CATEGORY_ALIASES[fm2[0]])
            continue

        logger.warning("Unrecognised category dropped: '%s'", cat.strip())

    # 5. Keyword fallback — scan ALL taxonomy rules so multi-category messages
    #    recover every matching category (not just the first hit).
    if not result and raw_message:
        msg_lower = raw_message.lower()
        _seen_fallback: set = set()
        try:
            from sansadx_backend.jurisdiction import TAXONOMY_DB, _keyword_matches
            for rule in TAXONOMY_DB:
                for kw in rule.get("keywords", []):
                    if _keyword_matches(kw, msg_lower):
                        raw_cat = rule.get("category", "")
                        mapped = (
                            raw_cat if raw_cat in _VALID_CATEGORIES
                            else _CATEGORY_ALIASES.get(raw_cat.lower())
                        )
                        if mapped and mapped not in _seen_fallback:
                            result.append(mapped)
                            _seen_fallback.add(mapped)
                            logger.info("Category recovered via taxonomy kw '%s' → '%s'", kw, mapped)
                        break  # one keyword match per rule is enough; move to next rule
        except Exception:
            pass

    # 6. Final default — never return empty
    if not result:
        logger.warning("Category recovery failed for message; defaulting to Infrastructure & Utilities")
        result = ["Infrastructure & Utilities"]

    # Deduplicate preserving order
    seen: set = set()
    return [c for c in result if not (c in seen or seen.add(c))]  # type: ignore[func-returns-value]


def _default_grievance_data(raw_message: str = "") -> dict:
    """
    Returns a minimal but valid grievance_data dict for error-path returns.
    Runs keyword fallback so cases are never saved with zero categories.
    """
    fields = build_taxonomy_fields(raw_text=raw_message)
    return {
        **fields,
        "location": None,
        "person": None,
        "department": None,
        "scheme": None,
        "summary": raw_message[:200] if raw_message else "",
        "_ai_fallback": True,
    }


def _normalize_grievance_taxonomy(grievance: dict, raw_message: str) -> dict:
    """
    Canonicalize the 3-layer taxonomy while keeping legacy `categories`
    available for unchanged storage and API code paths.
    """
    grievance = dict(grievance or {})
    cats = grievance.get("categories", [])
    if isinstance(cats, str):
        cats = [cats]

    candidate_domain = grievance.get("problem_domain")
    if not candidate_domain and isinstance(cats, list) and cats:
        candidate_domain = cats[0]

    normalized_categories = _normalize_categories(cats, raw_message)
    if not candidate_domain and normalized_categories:
        candidate_domain = normalized_categories[0]

    fields = build_taxonomy_fields(
        problem_domain=candidate_domain,
        problem_subdomain=grievance.get("problem_subdomain"),
        convergence_program_type=grievance.get("convergence_program_type"),
        raw_text=raw_message,
        scheme=grievance.get("scheme"),
        department=grievance.get("department"),
    )
    grievance.update(fields)
    return grievance


STATIC_RESPONSES = {
    "__WARN_HINDI__": "मर्यादा रखें। अभद्र भाषा का प्रयोग करने पर आप पर कानूनी कार्यवाही हो सकती है।",
    "__WARN_MARATHI__": "मर्यादा राखा. अभद्र भाषेचा वापर केल्यास कायदेशीर कारवाई होऊ शकते.",
    "__WARN_KANNADA__": "ಮರ್ಯಾದೆ ಕಾಪಾಡಿ. ಅಸಭ್ಯ ಭಾಷೆ ಬಳಸಿದರೆ ಕಾನೂನು ಕ್ರಮ ಕೈಗೊಳ್ಳಲಾಗುವುದು.",
    "__WARN_ENGLISH__": "Maintain decorum. Legal action can be taken for abusive language."
}


def _build_grounding_forms(text: str) -> set[str]:
    """Build comparable text forms for grounding extracted locations in raw input."""
    if not text:
        return set()

    try:
        from modules.geography_resolver import _build_match_forms

        forms = _build_match_forms(text)
        if forms:
            return {form for form in forms if form}
    except Exception:
        pass

    lowered = re.sub(r"[^\w\s]", " ", str(text).lower())
    normalized = re.sub(r"\s+", " ", lowered).strip()
    if not normalized:
        return set()
    return {normalized, normalized.replace(" ", "")}


def _location_is_grounded_in_message(candidate_location: str, raw_message: str) -> bool:
    """
    Return True only when the candidate location is actually supported by the
    citizen's raw message text (including spaceless/transliterated forms).
    """
    location_forms = _build_grounding_forms(candidate_location)
    message_forms = _build_grounding_forms(raw_message)
    if not location_forms or not message_forms:
        return False

    message_spaceless = {form.replace(" ", "") for form in message_forms if form}

    for loc_form in location_forms:
        if len(loc_form) < 3:
            continue
        if loc_form in message_forms:
            return True

        boundary_pattern = r"\b" + re.escape(loc_form) + r"\b"
        if any(re.search(boundary_pattern, message_form) for message_form in message_forms):
            return True

        loc_spaceless = loc_form.replace(" ", "")
        if len(loc_spaceless) >= 5 and any(loc_spaceless in message_form for message_form in message_spaceless):
            return True

    return False

_OFFENSIVE_WARNING_NATIVE = {
    "Hindi": STATIC_RESPONSES["__WARN_HINDI__"],
    "Marathi": STATIC_RESPONSES["__WARN_MARATHI__"],
    "Kannada": STATIC_RESPONSES["__WARN_KANNADA__"],
    "English": STATIC_RESPONSES["__WARN_ENGLISH__"],
}

_OFFENSIVE_WARNING_LATIN = {
    "Hindi": "Maryada rakhein. Abhadra bhasha ka prayog karne par kanooni karvayi ho sakti hai.",
    "Hinglish": "Please maintain decorum. Abusive language can lead to legal action.",
    "Marathi": "Maryada rakha. Abhadra bhasha vaparlyas kanooni karvayi hou shakte.",
    "Kannada": "Maryade kapadi. Asabhya bhashe balasidare kanoonu kram tegedukollabahudu.",
    "English": STATIC_RESPONSES["__WARN_ENGLISH__"],
}

# ==========================================
# 2. GEOGRAPHY RESOLVER (MASTER CONTEXT)
# ==========================================
def get_jurisdiction_context(tenant_id=1):
    """Build a list of known areas from geography data and tenant overrides, scoped to this tenant."""
    known_areas = set()

    # Resolve this tenant's constituency name for folder matching
    tenant_constituency = None
    try:
        from sansadx_backend.db import SessionLocal, TenantProfile, Tenant
        db = SessionLocal()
        try:
            profile = db.query(TenantProfile).filter(TenantProfile.tenant_id == tenant_id).first()
            if profile and profile.constituency:
                tenant_constituency = profile.constituency
            else:
                tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
                if tenant and tenant.constituency:
                    tenant_constituency = tenant.constituency
        finally:
            db.close()
    except Exception:
        pass

    # 1. Load from DB geography_data first
    try:
        from sansadx_backend.db import get_geography_data
        for stations in get_geography_data(
            tenant_id=tenant_id,
            parliamentary_constituency=tenant_constituency,
        ).values():
            for item in stations:
                if isinstance(item, str):
                    known_areas.add(item)
                elif isinstance(item, dict):
                    if "locality" in item:
                        known_areas.add(item["locality"])
                    elif "name" in item:
                        known_areas.add(item["name"])
    except Exception:
        pass

    # 2. File fallback for local/dev bootstraps without DB geography rows
    if not known_areas:
        base_paths = ["data/geography", "../data/geography", "/app/data/geography"]
        for folder in base_paths:
            if not os.path.exists(folder):
                continue

            if tenant_constituency:
                constituency_folder = os.path.join(folder, tenant_constituency)
                if not os.path.exists(constituency_folder):
                    for d in os.listdir(folder):
                        if d.lower() == tenant_constituency.lower() and os.path.isdir(os.path.join(folder, d)):
                            constituency_folder = os.path.join(folder, d)
                            break
                    else:
                        constituency_folder = None

                if constituency_folder and os.path.exists(constituency_folder):
                    for file_path in glob.glob(os.path.join(constituency_folder, "*.json")):
                        try:
                            with open(file_path, "r") as f:
                                data = json.load(f)
                                if isinstance(data, dict):
                                    known_areas.update(data.keys())
                                elif isinstance(data, list):
                                    for item in data:
                                        if isinstance(item, str):
                                            known_areas.add(item)
                                        elif isinstance(item, dict):
                                            if "locality" in item:
                                                known_areas.add(item["locality"])
                                            elif "name" in item:
                                                known_areas.add(item["name"])
                        except Exception:
                            pass  # nosec B110
            else:
                logger.warning(f"No constituency found for tenant {tenant_id}, skipping file geography")

    # 3. Load from tenant_overrides DB (tenant-specific locations)
    try:
        from sansadx_backend.db import get_geo_overrides
        tenant_geo = get_geo_overrides(tenant_id)
        known_areas.update(tenant_geo.keys())
    except Exception:
        # Fallback to JSON file if DB not available
        override_paths = ["tenant_overrides.json", "/app/tenant_overrides.json"]
        for op in override_paths:
            if os.path.exists(op):
                try:
                    with open(op, "r") as f:
                        overrides = json.load(f)
                    tenant_geo = overrides.get("geo_overrides", {}).get(str(tenant_id), {})
                    known_areas.update(tenant_geo.keys())
                except Exception:
                    pass  # nosec B110
                break

    if not known_areas: return ""
    import itertools
    return ", ".join(itertools.islice(sorted(known_areas), 300))

# ==========================================
# 3. LANGUAGE DETECTION (rule-based, pre-GPT)
# ==========================================
# Marathi words that do NOT appear in Hindi transliteration
_MARATHI_MARKERS = {
    "aahe", "ahe", "hotoy", "hota", "hoti", "hotey",
    "madhe", "madhye", "mdhye",
    "kela", "keli", "kele", "kelya",
    "zala", "zali", "zale", "zalya",
    "traas", "tras",
    "yeina", "yena", "yet nahi",
    "nahi aahe", "nahi ahe",
    "aahet", "ahet",
    "kadhla", "kadhi", "karun",
    "sangayche", "sangitla", "sangto",
    "khup", "mhanje", "mhanun",
    "aaplyala", "tumhala", "amhala",
    "pudhe", "shivar", "gaav",
    # Additional transliteration variants (fix: language swap bug)
    "amahala", "amhala",          # आम्हाला — "us" (Marathi 1st-person plural)
    "yojane", "yojana che",       # योजनेचे — "of the scheme"
    "bethle", "bethla", "bethli", # बेटले/मिळाले — "received/got" (dialectal)
    "milena", "milale", "milali", # मिळाले — "received"
    "sangto", "sangta", "sangti", # सांगतो — "I/she/he says"
    "karto", "karte", "kartoy",   # करतो — "does/doing"
    "nighto", "nighale",          # निघतो — "leaves/left"
    "dya", "dyayla",              # द्या — "give (imperative)"
    "aaplyakade", "aamchya",      # आपल्याकडे / आमच्या
    # Common citizen transliteration patterns (agri/weather complaints)
    "majhi", "majha", "mala", "kahi", "zhali", "mule", "pavsa", "sheti", "kara",
}

_KANNADA_MARKERS = {
    "ide", "illa", "alli", "maadi", "beku", "aithu",
    "helri", "hogidhe", "bandilla", "kelsa",
}

# FIX P2: Tamil, Telugu, Bengali transliteration markers
_TAMIL_MARKERS = {
    "illa", "irukku", "pannunga", "sollunga", "varudu",
    "illai", "varala", "seyya", "enna", "theriyala",
    "kodunga", "mudiyala", "paarunga", "sollungo",
}

_TELUGU_MARKERS = {
    "ledu", "undi", "cheyyi", "cheppandi", "ivaali",
    "chala", "naaku", "meeru", "vastundi", "leru",
    "ippudu", "kaadu", "chesthunnaru", "ivvadam",
}

_BENGALI_MARKERS = {
    "hoyeche", "nei", "ache", "korchi", "dite",
    "paachi na", "hobe", "kothay", "jacche", "jachhe", "bolun",
    "hoye", "jacche", "achhe", "debe", "niye",
}

_LANGUAGE_SAFE_FALLBACKS = {
    "Hindi": "Ji, maine aapki samasya note kar li hai. Kripya gaon ya kshetra ka naam bhi batayen.",
    "Hinglish": "Ji, maine aapka issue note kar liya hai. Please village/area ka naam bhi share karein.",
    "Marathi": "Tumchi samasya nodavli aahe. Krupaya gaav kiwa ward che naav pan sanga.",
    "Kannada": "Nimma samasya namoodiside. Dayavittu grama athava ward hesaru koodi tilisi.",
    "Tamil": "Ungal pirachanai pathivu seyyappattadhu. Dayavu seidhu gramam alladhu ward peyaraiyum sollunga.",
    "Telugu": "Mee samasya namodayyindi. Dayachesi gramam leka ward peru kooda cheppandi.",
    "Bengali": "Apnar shomoshya nôthibhukto hoyeche. Doya kore gram ba ward er naam-o janan.",
    "English": "Your issue has been noted. Please also share your village or ward name.",
}


def _split_context_and_message(raw_input: str) -> tuple[str, str]:
    """
    If main.py passes a combined blob like:
      "<context>\\n\\nUSER MESSAGE: <citizen text>"
    split it so language detection/classification uses only the citizen text.
    """
    text = (raw_input or "").strip()
    if not text:
        return "", ""
    parts = re.split(r"\bUSER MESSAGE\s*:\s*", text, maxsplit=1, flags=re.IGNORECASE)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return "", text


def _mostly_ascii(text: str) -> bool:
    stripped = [c for c in (text or "") if not c.isspace()]
    if not stripped:
        return True
    ascii_count = sum(1 for c in stripped if ord(c) < 128)
    return (ascii_count / len(stripped)) >= 0.90


def _safe_language_fallback(lang: str) -> str:
    return _LANGUAGE_SAFE_FALLBACKS.get(lang, _LANGUAGE_SAFE_FALLBACKS["English"])


def get_offensive_warning_reply(detected_language: str = "", original_text: str = "") -> str:
    normalized = (detected_language or "").strip() or "English"
    if original_text and _mostly_ascii(original_text):
        return _OFFENSIVE_WARNING_LATIN.get(normalized, _OFFENSIVE_WARNING_LATIN["English"])
    return _OFFENSIVE_WARNING_NATIVE.get(normalized, _OFFENSIVE_WARNING_NATIVE["English"])


def detect_input_language(message: str) -> str:
    """Detect language from transliterated text using word markers.
    Returns: 'Marathi', 'Kannada', 'Tamil', 'Telugu', 'Bengali',
             'English', 'Hindi', or 'Hinglish'.
    """
    words = set(message.lower().split())
    text_lower = message.lower()

    # FIX P1: Detect pure-emoji or symbol-only input → English
    # Emoji are non-ASCII but are NOT Hindi/Devanagari.
    # Unicode general categories: So=Symbol-Other, Cs=Surrogate, Cn=Unassigned
    stripped_non_ws = message.replace(" ", "").replace("\t", "").replace("\n", "")
    if stripped_non_ws and all(
        ord(c) > 127 and unicodedata.category(c) in ("So", "Cs", "Cn", "Sk", "Sm")
        for c in stripped_non_ws
    ):
        return "English"

    # Check Marathi markers (most specific first)
    marathi_hits = sum(1 for m in _MARATHI_MARKERS if m in text_lower)
    if marathi_hits >= 2:
        return "Marathi"

    # Check Kannada markers
    kannada_hits = sum(1 for m in _KANNADA_MARKERS if m in text_lower)
    if kannada_hits >= 2:
        return "Kannada"

    # FIX P2: Check Tamil markers
    tamil_hits = sum(1 for m in _TAMIL_MARKERS if m in text_lower)
    if tamil_hits >= 2:
        return "Tamil"

    # FIX P2: Check Telugu markers
    telugu_hits = sum(1 for m in _TELUGU_MARKERS if m in text_lower)
    if telugu_hits >= 2:
        return "Telugu"

    # FIX P2: Check Bengali markers
    bengali_hits = sum(1 for m in _BENGALI_MARKERS if m in text_lower)
    if bengali_hits >= 2:
        return "Bengali"

    # If mostly ASCII with no Indic markers, likely English
    if all(ord(c) < 128 or c in ' \t\n' for c in message):
        # Check for common Hindi/Hinglish words
        hindi_markers = {"hai", "hain", "kya", "mein", "nahi", "bahut", "karo", "kijiye", "sahab"}
        if words & hindi_markers:
            return "Hinglish"
        # Single Marathi marker might be enough if no Hindi markers
        if marathi_hits >= 1:
            return "Marathi"
        return "English"

    # Devanagari / non-ASCII → let GPT handle
    return "Hindi"


# ==========================================
# 4. AI EXECUTION (v3.0 ENGINE)
# ==========================================
def _get_tenant_profile(tenant_id: int) -> dict:
    """Load MP profile from DB for the given tenant. Returns dict with mp_name, constituency, state."""
    try:
        from sansadx_backend.db import SessionLocal, TenantProfile, Tenant
        db = SessionLocal()
        try:
            profile = db.query(TenantProfile).filter(TenantProfile.tenant_id == tenant_id).first()
            if profile:
                return {
                    "mp_name": profile.mp_name or "",
                    "constituency": profile.constituency or "",
                    "state": profile.state or "",
                    "house": profile.house or "Lok Sabha",
                }
            # Fallback to tenant table if no profile exists
            tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
            if tenant:
                return {
                    "mp_name": tenant.name or "",
                    "constituency": tenant.constituency or "",
                    "state": "",
                    "house": "Lok Sabha",
                }
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Failed to load tenant profile for tenant {tenant_id}: {e}")
    return {"mp_name": "", "constituency": "", "state": "", "house": "Lok Sabha"}


def ask_chatgpt_agent(user_message, tenant_id=1):
    """
    Refactored Engine v3.0: 
    - Uses GPT-4o-mini
    - Supports Multi-Label Categories
    - Integrated Fuzzy Geography Matching
    """
    client = get_client()
    if not client: 
        logger.error("OPENAI_API_KEY is missing.")
        return {"status": "ERROR", "political_response": "Server Error: API Key Missing."}

    # Fetch dynamic jurisdiction context (scoped to this tenant)
    real_jurisdiction_context = get_jurisdiction_context(tenant_id=tenant_id)

    # Load MP identity for this tenant
    mp_profile = _get_tenant_profile(tenant_id)
    mp_name = mp_profile["mp_name"]
    mp_constituency = mp_profile["constituency"]
    mp_state = mp_profile["state"]

    # --- Deterministic language detection (on citizen message only) ---
    extra_context, primary_message = _split_context_and_message(user_message)
    effective_user_message = primary_message or (user_message or "")
    detected_lang = detect_input_language(effective_user_message)

    # --- Inject MP Persona & Professional Constraints ---
    mp_identity = ""
    if mp_name and mp_constituency:
        mp_identity = f"""
    MP IDENTITY:
    You are the grievance system for the MP from **{mp_constituency}**{f', {mp_state}' if mp_state else ''}.

    RULES:
    1. If a citizen reports a civic issue (water, road, electricity, etc.) with or without a location,
       ALWAYS acknowledge it. Say the issue is "noted and recorded" and they will be updated soon.
       Extract the location name as-is from the message (do not modify or validate it).
    2. If no location is mentioned → Ask for the village/area name. Mark as INCOMPLETE.
    3. NEVER mark a civic issue as IRRELEVANT. IRRELEVANT is ONLY for greetings, jokes, or spam.
    4. ALWAYS reply in the SAME LANGUAGE as the citizen. Never switch to English.
        """

    persona_instructions = f"""
    STRICT RULES:
    1. You are a Member of Parliament (MP) communicating with a citizen.
    2. NEVER mention 'departments', 'forwarding', or 'officials'.
    3. Maintain professional authority. DO NOT say 'it feels good' or 'I understand'.
    4. NO PROMISES: Do not promise a specific action. State the issue is 'noted and recorded'.
    5. LANGUAGE: The citizen's message is in **{detected_lang}**. You MUST write your political_response in **{detected_lang}** only. Do NOT switch to Hindi or any other language. Set detected_language to "{detected_lang}".
    6. Only If info is missing (location/area), ask for it directly in {detected_lang}.
    7. Be concise (max 2 sentences).
    8. Use neutral wording: prefer "issue/problem/samasya". Use "complaint" only if the citizen explicitly makes a complaint.
    {mp_identity}
    """

    # Format the v3.0 system instructions from prompts.py
    system_instructions = f"{persona_instructions}\n\n{SYSTEM_PROMPT.format(user_message='{{MESSAGE_BELOW}}', jurisdiction_context=real_jurisdiction_context, taxonomy_categories=TAXONOMY_CATEGORIES, taxonomy_subdomains=TAXONOMY_SUBDOMAINS, convergence_program_types=CONVERGENCE_PROGRAM_TYPES_TEXT)}"

    # Prefix user message with detected language so GPT cannot miss it
    if extra_context:
        tagged_message = (
            f"[LANGUAGE: {detected_lang}]\n"
            f"<user_input>\n{effective_user_message}\n</user_input>\n"
            f"<context>\n{extra_context}\n</context>"
        )
    else:
        tagged_message = f"[LANGUAGE: {detected_lang}]\n<user_input>\n{effective_user_message}\n</user_input>"

    # ── Retry with exponential backoff (3 attempts: 1s → 2s → 4s) ──────────
    _MAX_RETRIES = 3
    _response_obj = None
    for _attempt in range(_MAX_RETRIES):
        try:
            _response_obj = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_instructions},
                    {"role": "user", "content": tagged_message}
                ],
                response_format={"type": "json_object"}
            )
            break  # success — exit retry loop
        except (RateLimitError, APIError, APIConnectionError) as _retry_exc:
            if _attempt < _MAX_RETRIES - 1:
                _wait = 2 ** _attempt  # 1s, 2s, 4s
                logger.warning(
                    "OpenAI call failed (attempt %d/%d): %s. Retrying in %ds…",
                    _attempt + 1, _MAX_RETRIES, _retry_exc, _wait
                )
                time.sleep(_wait)
            else:
                logger.error(
                    "OpenAI call failed after %d attempts: %s. Saving case as pending.",
                    _MAX_RETRIES, _retry_exc
                )
                return {
                    "status": "pending",
                    "detected_language": detected_lang,
                    "political_response": get_generic_ack_reply(detected_lang, effective_user_message),
                    "grievance_data": _default_grievance_data(effective_user_message),
                    "is_critical": False,
                    "_ai_retry_exhausted": True,
                }
        except Exception as _unexpected_exc:
            logger.error("Unexpected OpenAI error (no retry): %s", _unexpected_exc)
            return {
                "status": "pending",
                "detected_language": detected_lang,
                "political_response": get_generic_ack_reply(detected_lang, effective_user_message),
                "grievance_data": _default_grievance_data(effective_user_message),
                "is_critical": False,
                "_ai_retry_exhausted": True,
            }

    try:
        response = _response_obj
        
        try:
            # Parse OpenAI response
            content = response.choices[0].message.content
            data = json.loads(content)
            
            # 🛡️ NORMALIZATION: Ensure status is a known canonical value
            _VALID_STATUSES = {
                "new", "pending", "completed", "incomplete",
                "emergency", "offensive", "irrelevant", "awaiting_location",
            }
            if "status" in data:
                _raw_status = str(data["status"]).lower().strip()
                data["status"] = _raw_status if _raw_status in _VALID_STATUSES else "pending"
            data["detected_language"] = detected_lang

            # [START OF MULTI-TENANT FIX (WITH AUTO-CORRECT)] ----------------
            try:
                _tenant_const = mp_constituency if mp_name else None
                if not _tenant_const:
                    try:
                        from sansadx_backend.db import get_tenant_constituency
                        _tenant_const = get_tenant_constituency(tenant_id)
                    except Exception:
                        _tenant_const = None

                message_geo = {"location_resolved": False}
                try:
                    message_geo = resolve_geography_from_text(
                        effective_user_message,
                        scope_parliamentary=_tenant_const,
                        tenant_id=tenant_id,
                    )
                except Exception as e:
                    logger.warning("Message-grounded geography resolution failed: %s", e)

                # 1. Load the Rulebook from DB (geo_overrides)
                try:
                    from sansadx_backend.db import get_geo_overrides
                    tenant_rules = get_geo_overrides(tenant_id)
                except Exception:
                    # Fallback to JSON file
                    override_path = "tenant_overrides.json"
                    if not os.path.exists(override_path):
                        override_path = "/app/tenant_overrides.json"
                    with open(override_path, "r") as f:
                        all_overrides = json.load(f)
                    tenant_rules = all_overrides.get("geo_overrides", {}).get(str(tenant_id), {})
                
                # 2. Also build location→assembly mapping from geography JSON files
                geo_file_rules = {}
                try:
                    try:
                        from sansadx_backend.db import get_geography_data
                        geo_db_rules = get_geography_data(
                            tenant_id=tenant_id,
                            parliamentary_constituency=_tenant_const,
                        )
                        for assembly_name, stations in geo_db_rules.items():
                            for station in stations:
                                if isinstance(station, dict):
                                    loc = station.get("locality", "").strip()
                                    if loc and loc not in geo_file_rules:
                                        geo_file_rules[loc] = assembly_name
                    except Exception:
                        pass

                    if not geo_file_rules and _tenant_const:
                        for base in ["data/geography", "/app/data/geography"]:
                            const_dir = os.path.join(base, _tenant_const)
                            if not os.path.isdir(const_dir):
                                if os.path.isdir(base):
                                    for d in os.listdir(base):
                                        if d.lower() == _tenant_const.lower() and os.path.isdir(os.path.join(base, d)):
                                            const_dir = os.path.join(base, d)
                                            break
                                    else:
                                        continue
                                else:
                                    continue

                            for fpath in glob.glob(os.path.join(const_dir, "*.json")):
                                assembly_name = os.path.splitext(os.path.basename(fpath))[0]
                                try:
                                    with open(fpath, "r") as gf:
                                        stations = json.load(gf)
                                    if isinstance(stations, list):
                                        for station in stations:
                                            if isinstance(station, dict):
                                                loc = station.get("locality", "").strip()
                                                if loc and loc not in geo_file_rules:
                                                    geo_file_rules[loc] = assembly_name
                                except Exception:
                                    pass
                            break
                except Exception as e:
                    logger.warning(f"Geography file scan failed: {e}")
                
                # 3. Merge: DB overrides take priority, then geography files
                combined_rules = {}
                combined_rules.update(geo_file_rules)
                combined_rules.update(tenant_rules)  # DB overrides win
                
                # 4. Get AI's extracted location
                ai_loc = data.get("grievance_data", {}).get("location", "")
                ai_loc_grounded = _location_is_grounded_in_message(ai_loc, effective_user_message) if ai_loc else False

                if message_geo.get("location_resolved"):
                    grounded_loc = message_geo.get("matched_value") or ai_loc
                    grounded_constituency = message_geo.get("assembly_constituency") or "Unknown"
                    data["assembly_constituency"] = grounded_constituency
                    data["constituency"] = grounded_constituency
                    data["_match_confidence"] = f"message_grounded_{message_geo.get('confidence', 'high')}"

                    original_status = data.get("status", "").lower()
                    if original_status not in ("emergency", "offensive"):
                        data["status"] = "new"

                    if original_status == "emergency":
                        data["is_critical"] = True

                    if "grievance_data" in data:
                        data["grievance_data"]["assembly_constituency"] = grounded_constituency
                        data["grievance_data"]["location"] = grounded_loc
                        data["grievance_data"]["_match_confidence"] = data["_match_confidence"]

                    logger.info(
                        "Location Mapped [message_grounded]: %s -> %s",
                        grounded_loc,
                        grounded_constituency,
                    )
                elif ai_loc and not ai_loc_grounded:
                    logger.warning(
                        "Discarding ungrounded AI location '%s' for message '%s'",
                        ai_loc,
                        effective_user_message[:160],
                    )
                    data["assembly_constituency"] = "Unknown"
                    data["constituency"] = "Unknown"
                    data["_match_confidence"] = "ungrounded_cleared"

                    original_status = data.get("status", "").lower()
                    if original_status not in ("emergency", "offensive", "irrelevant"):
                        data["status"] = "awaiting_location"
                        data["political_response"] = get_missing_location_reply(
                            detected_lang,
                            effective_user_message,
                        )

                    if "grievance_data" in data:
                        data["grievance_data"]["location"] = None
                        data["grievance_data"]["assembly_constituency"] = "Unknown"
                        data["grievance_data"]["_match_confidence"] = "ungrounded_cleared"
                elif ai_loc:
                    ai_loc_clean = ai_loc.lower().strip()
                    
                    # 5. SMART MATCHING — STRICT PRIORITY ORDER
                    # Priority 1: Exact match (highest confidence)
                    # Priority 2: Exact word boundary match (e.g., "hosur" matches "hosur" but not "gilihosur")
                    # Priority 3: Substring match only if input CONTAINS the key (not reverse)
                    # Priority 4: High-confidence fuzzy (85%+ cutoff, minimum 5 chars)
                    # Priority 5: Mark as "Unknown" for manual review
                    
                    match_found = False
                    final_loc_name = ai_loc_clean
                    match_confidence = "none"
                    
                    # Build lookup dict with lower-case keys
                    rules_keys_lower = {k.lower(): k for k in combined_rules.keys()}
                    
                    # PRIORITY 1: Exact match
                    if ai_loc_clean in rules_keys_lower:
                        final_loc_name = rules_keys_lower[ai_loc_clean]
                        match_found = True
                        match_confidence = "exact"
                    
                    # PRIORITY 2: Word boundary match (prevents "hosur" matching "gilihosur")
                    if not match_found:
                        import re
                        for rk_lower, rk_original in rules_keys_lower.items():
                            # Check if input is a complete word within the key or vice versa
                            # "hosur belagavi" should match "hosur" but "gilihosur" should NOT match "hosur"
                            pattern_key_in_input = r'\b' + re.escape(rk_lower) + r'\b'
                            
                            if re.search(pattern_key_in_input, ai_loc_clean):
                                # The key appears as a complete word in user input
                                # e.g., user said "hosur village" and key is "hosur"
                                final_loc_name = rk_original
                                match_found = True
                                match_confidence = "word_boundary"
                                logger.info(f"Word boundary match: '{rk_lower}' found in '{ai_loc_clean}'")
                                break
                    
                    # PRIORITY 3: Substring match ONLY if user input contains the entire key
                    # (NOT the reverse — prevents "hosur" matching "chandanhosur")
                    if not match_found:
                        best_substring_match = None
                        best_substring_len = 0
                        for rk_lower, rk_original in rules_keys_lower.items():
                            # Only match if the KEY is fully contained in user input
                            # AND the key is at least 5 chars (avoid matching "k" or "pg")
                            if len(rk_lower) >= 5 and rk_lower in ai_loc_clean:
                                # Prefer longer matches (more specific)
                                if len(rk_lower) > best_substring_len:
                                    best_substring_match = rk_original
                                    best_substring_len = len(rk_lower)
                        
                        if best_substring_match:
                            final_loc_name = best_substring_match
                            match_found = True
                            match_confidence = "substring"
                            logger.info(f"Substring match: '{best_substring_match}' ({best_substring_len} chars) in '{ai_loc_clean}'")
                    
                    # PRIORITY 4: High-confidence fuzzy match (STRICT: 85% cutoff, min 5 chars)
                    if not match_found and len(ai_loc_clean) >= 5:
                        # Only consider keys of similar length (±30%) to prevent wild mismatches
                        candidate_keys = [
                            k for k in rules_keys_lower.keys() 
                            if len(k) >= 5 and 0.7 <= len(k)/len(ai_loc_clean) <= 1.3
                        ]
                        if candidate_keys:
                            matches = difflib.get_close_matches(
                                ai_loc_clean, 
                                candidate_keys, 
                                n=1, 
                                cutoff=0.85  # Increased from 0.6 to 0.85 for safety
                            )
                            if matches:
                                final_loc_name = rules_keys_lower[matches[0]]
                                match_found = True
                                match_confidence = "fuzzy_85"
                                logger.info(f"Fuzzy match (85%): '{ai_loc_clean}' -> '{final_loc_name}'")
                    
                    # 6. Apply the mapping OR mark for manual review
                    if match_found:
                        correct_constituency = combined_rules[final_loc_name]
                        data["assembly_constituency"] = correct_constituency
                        data["constituency"] = correct_constituency
                        data["_match_confidence"] = match_confidence  # For debugging/audit
                        
                        # --- Keep status as "new" so staff must manually triage ---
                        original_status = data.get("status", "").lower()
                        if original_status not in ("emergency", "offensive"):
                            data["status"] = "new"
                        
                        # Set is_critical for emergency cases
                        if original_status == "emergency":
                            data["is_critical"] = True
                        
                        if "grievance_data" in data:
                            data["grievance_data"]["assembly_constituency"] = correct_constituency
                            data["grievance_data"]["location"] = final_loc_name  # Set to official spelling
                            data["grievance_data"]["_match_confidence"] = match_confidence
                            
                        logger.info(f"Location Mapped [{match_confidence}]: {final_loc_name} -> {correct_constituency}")
                    else:
                        # No confident match — mark for manual review
                        data["assembly_constituency"] = "Unknown"
                        data["_match_confidence"] = "unmatched"
                        logger.info(f"Location UNMATCHED (needs manual review): '{ai_loc_clean}'")
                        
            except Exception as e:
                logger.warning(f"Override Logic Warning: {e}") 
            # [END OF FIX] -------------------------------------------------

            # 🛡️ LANGUAGE SWAP LOGIC
            raw_resp = data.get("political_response", "")
            if raw_resp in STATIC_RESPONSES:
                data["political_response"] = STATIC_RESPONSES[raw_resp]

            if str(data.get("status", "")).lower() == "offensive":
                data["political_response"] = get_offensive_warning_reply(
                    detected_lang,
                    effective_user_message,
                )

            # 🛠️ MULTI-LABEL SYNC + CATEGORY VALIDATION
            if "grievance_data" in data:
                # FIX P0: OFFENSIVE and IRRELEVANT statuses intentionally have no categories per schema.
                # Do NOT apply the default fallback — it would pollute analytics dashboards.
                _current_status = str(data.get("status", "")).lower()
                if _current_status in ("offensive", "irrelevant"):
                    data["grievance_data"]["categories"] = []
                    data["grievance_data"]["problem_domain"] = None
                    data["grievance_data"]["problem_subdomain"] = None
                    data["grievance_data"]["convergence_program_type"] = None
                else:
                    data["grievance_data"] = _normalize_grievance_taxonomy(
                        data["grievance_data"],
                        effective_user_message,
                    )

            # Language guardrail: if citizen input was transliterated (mostly ASCII),
            # reject non-ASCII AI replies to avoid Hindi-script swaps for Marathi/Hinglish.
            _reply = str(data.get("political_response", "") or "").strip()
            if _mostly_ascii(effective_user_message) and _reply and not _mostly_ascii(_reply):
                logger.warning(
                    "Language guardrail triggered: forcing safe fallback. lang=%s input='%s' reply='%s'",
                    detected_lang, effective_user_message[:120], _reply[:120]
                )
                data["political_response"] = _safe_language_fallback(detected_lang)

            return data
            
        except Exception as e:
            logger.error("JSON Parse Error: %s", e)
            return {
                "status": "pending",
                "detected_language": detected_lang,
                "political_response": get_generic_ack_reply(detected_lang, effective_user_message),
                "grievance_data": _default_grievance_data(effective_user_message),
                "is_critical": False,
            }

    except Exception as e:
        logger.error("Unexpected outer error in ask_chatgpt_agent: %s", e)
        return {
            "status": "pending",
            "detected_language": detected_lang,
            "political_response": get_generic_ack_reply(detected_lang, effective_user_message),
            "grievance_data": _default_grievance_data(effective_user_message),
            "is_critical": False,
        }
