import os
import requests
import json
import glob
import logging
import time
import difflib  # Logic for Fuzzy Matching (Typos)
from openai import OpenAI
from openai import RateLimitError, APIError, APIConnectionError
from .prompts import SYSTEM_PROMPT, TAXONOMY_CATEGORIES

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
_VALID_CATEGORIES = {
    "Infrastructure & Utilities",
    "Housing & Land",
    "Health",
    "Education",
    "Government Schemes & Welfare",
    "Agriculture",
    "Social Issues",
    "Law & Order",
    "Bureaucratic / Administrative",
}

# Known hallucinations / old names / partial names → canonical category
_CATEGORY_ALIASES = {
    "infrastructure": "Infrastructure & Utilities",
    "infrastructure & utility": "Infrastructure & Utilities",
    "infrastructure (state)": "Infrastructure & Utilities",
    "infrastructure(state)": "Infrastructure & Utilities",
    "energy": "Infrastructure & Utilities",
    "water": "Infrastructure & Utilities",
    "sanitation": "Infrastructure & Utilities",
    "civic amenities": "Infrastructure & Utilities",
    "transport": "Infrastructure & Utilities",
    "telecom": "Infrastructure & Utilities",
    "railways": "Infrastructure & Utilities",
    "road": "Infrastructure & Utilities",
    "roads": "Infrastructure & Utilities",
    "electricity": "Infrastructure & Utilities",
    "revenue & land": "Housing & Land",
    "land": "Housing & Land",
    "housing": "Housing & Land",
    "land records": "Housing & Land",
    "public health": "Health",
    "health & sanitation": "Health",
    "medical": "Health",
    "healthcare": "Health",
    "education (central)": "Education",
    "education (state)": "Education",
    "school": "Education",
    "food supply": "Government Schemes & Welfare",
    "banking & finance": "Government Schemes & Welfare",
    "labor & employment": "Government Schemes & Welfare",
    "labour & employment": "Government Schemes & Welfare",
    "welfare": "Government Schemes & Welfare",
    "government schemes": "Government Schemes & Welfare",
    "schemes": "Government Schemes & Welfare",
    "pension": "Government Schemes & Welfare",
    "ration": "Government Schemes & Welfare",
    "farming": "Agriculture",
    "farmer": "Agriculture",
    "crop": "Agriculture",
    "law and order": "Law & Order",
    "police": "Law & Order",
    "crime": "Law & Order",
    "security": "Law & Order",
    "bureaucratic": "Bureaucratic / Administrative",
    "administrative": "Bureaucratic / Administrative",
    "bureaucratic/administrative": "Bureaucratic / Administrative",
    "bureaucratic/ administrative": "Bureaucratic / Administrative",
    "civic admin": "Bureaucratic / Administrative",
    "external affairs": "Bureaucratic / Administrative",
    "postal services": "Bureaucratic / Administrative",
    "corruption": "Bureaucratic / Administrative",
    "social issue": "Social Issues",
    "caste": "Social Issues",
    "women": "Social Issues",
    "general grievance": "Infrastructure & Utilities",
    "general": "Infrastructure & Utilities",
}


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

    # 5. Keyword fallback — scan taxonomy if nothing survived
    if not result and raw_message:
        msg_lower = raw_message.lower()
        try:
            from sansadx_backend.jurisdiction import TAXONOMY_DB
            for rule in TAXONOMY_DB:
                for kw in rule.get("keywords", []):
                    if kw.lower() in msg_lower:
                        raw_cat = rule.get("category", "")
                        mapped = (
                            raw_cat if raw_cat in _VALID_CATEGORIES
                            else _CATEGORY_ALIASES.get(raw_cat.lower())
                        )
                        if mapped:
                            result.append(mapped)
                            logger.info("Category recovered via taxonomy kw '%s' → '%s'", kw, mapped)
                            break
                if result:
                    break
        except Exception:
            pass

    # 6. Final default — never return empty
    if not result:
        logger.warning("Category recovery failed for message; defaulting to Infrastructure & Utilities")
        result = ["Infrastructure & Utilities"]

    # Deduplicate preserving order
    seen: set = set()
    return [c for c in result if not (c in seen or seen.add(c))]  # type: ignore[func-returns-value]


STATIC_RESPONSES = {
    "__WARN_HINDI__": "मर्यादा रखें। अभद्र भाषा का प्रयोग करने पर आप पर कानूनी कार्यवाही हो सकती है।",
    "__WARN_MARATHI__": "मर्यादा राखा. अभद्र भाषेचा वापर केल्यास कायदेशीर कारवाई होऊ शकते.",
    "__WARN_KANNADA__": "ಮರ್ಯಾದೆ ಕಾಪಾಡಿ. ಅಸಭ್ಯ ಭಾಷೆ ಬಳಸಿದರೆ ಕಾನೂನು ಕ್ರಮ ಕೈಗೊಳ್ಳಲಾಗುವುದು.",
    "__WARN_ENGLISH__": "Maintain decorum. Legal action can be taken for abusive language."
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

    # 1. Load from geography JSON files — ONLY this tenant's constituency folder
    base_paths = ["data/geography", "../data/geography", "/app/data/geography"]
    for folder in base_paths:
        if not os.path.exists(folder):
            continue

        if tenant_constituency:
            # Try exact match first, then case-insensitive match
            constituency_folder = os.path.join(folder, tenant_constituency)
            if not os.path.exists(constituency_folder):
                # Case-insensitive fallback
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
                            if isinstance(data, dict): known_areas.update(data.keys())
                            elif isinstance(data, list):
                                for item in data:
                                    if isinstance(item, str): known_areas.add(item)
                                    elif isinstance(item, dict):
                                        if "locality" in item: known_areas.add(item["locality"])
                                        elif "name" in item: known_areas.add(item["name"])
                    except Exception:
                        pass  # nosec B110
            # If no constituency folder found, don't load ANY geography (avoid cross-contamination)
        else:
            # No tenant constituency known — skip file-based geography to avoid loading wrong data
            logger.warning(f"No constituency found for tenant {tenant_id}, skipping file geography")

    # 2. Load from tenant_overrides DB (tenant-specific locations)
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
}

_KANNADA_MARKERS = {
    "ide", "illa", "alli", "maadi", "beku", "aithu",
    "helri", "hogidhe", "bandilla", "kelsa",
}

def detect_input_language(message: str) -> str:
    """Detect language from transliterated text using word markers.
    Returns: 'Marathi', 'Kannada', 'English', 'Hindi', or 'Hinglish'.
    """
    words = set(message.lower().split())
    text_lower = message.lower()

    # Check Marathi markers (most specific first)
    marathi_hits = sum(1 for m in _MARATHI_MARKERS if m in text_lower)
    if marathi_hits >= 2:
        return "Marathi"
    
    # Check Kannada markers
    kannada_hits = sum(1 for m in _KANNADA_MARKERS if m in text_lower)
    if kannada_hits >= 2:
        return "Kannada"

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

    # --- Deterministic language detection ---
    detected_lang = detect_input_language(user_message)

    # --- Inject MP Persona & Professional Constraints ---
    mp_identity = ""
    if mp_name and mp_constituency:
        mp_identity = f"""
    MP IDENTITY:
    You are the grievance system for the MP from **{mp_constituency}**{f', {mp_state}' if mp_state else ''}.

    RULES:
    1. If a citizen reports a civic issue (water, road, electricity, etc.) with or without a location,
       ALWAYS acknowledge it. Say the complaint is "noted and recorded" and they will be updated soon.
       Extract the location name as-is from the message (do not modify or validate it).
    2. If no location is mentioned → Ask for the village/area name. Mark as INCOMPLETE.
    3. NEVER mark a civic complaint as IRRELEVANT. IRRELEVANT is ONLY for greetings, jokes, or spam.
    4. ALWAYS reply in the SAME LANGUAGE as the citizen. Never switch to English.
        """

    persona_instructions = f"""
    STRICT RULES:
    1. You are a Member of Parliament (MP) communicating with a citizen.
    2. NEVER mention 'departments', 'forwarding', or 'officials'.
    3. Maintain professional authority. DO NOT say 'it feels good' or 'I understand'.
    4. NO PROMISES: Do not promise a specific action. State the grievance is 'noted and recorded'.
    5. LANGUAGE: The citizen's message is in **{detected_lang}**. You MUST write your political_response in **{detected_lang}** only. Do NOT switch to Hindi or any other language. Set detected_language to "{detected_lang}".
    6. Only If info is missing (location/area), ask for it directly in {detected_lang}.
    7. Be concise (max 2 sentences).
    {mp_identity}
    """

    # Format the v3.0 system instructions from prompts.py
    system_instructions = f"{persona_instructions}\n\n{SYSTEM_PROMPT.format(user_message='{{MESSAGE_BELOW}}', jurisdiction_context=real_jurisdiction_context, taxonomy_categories=TAXONOMY_CATEGORIES)}"

    # Prefix user message with detected language so GPT cannot miss it
    tagged_message = f"[LANGUAGE: {detected_lang}]\n<user_input>\n{user_message}\n</user_input>"

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
                    "political_response": (
                        "Thank you for contacting us. Your message has been received "
                        "and will be reviewed by our team. 🙏"
                    ),
                    "grievance_data": {},
                    "is_critical": False,
                    "_ai_retry_exhausted": True,
                }
        except Exception as _unexpected_exc:
            logger.error("Unexpected OpenAI error (no retry): %s", _unexpected_exc)
            return {
                "status": "pending",
                "detected_language": detected_lang,
                "political_response": (
                    "Thank you for contacting us. Your message has been received "
                    "and will be reviewed by our team. 🙏"
                ),
                "grievance_data": {},
                "is_critical": False,
                "_ai_retry_exhausted": True,
            }

    try:
        response = _response_obj
        
        try:
            # Parse OpenAI response
            content = response.choices[0].message.content
            data = json.loads(content)
            
            # 🛡️ NORMALIZATION: Ensure status is lowercase to match main.py logic
            if "status" in data:
                data["status"] = data["status"].lower()

            # [START OF MULTI-TENANT FIX (WITH AUTO-CORRECT)] ----------------
            try:
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
                    # Resolve this tenant's constituency folder
                    _tenant_const = mp_constituency if mp_name else None
                    if not _tenant_const:
                        try:
                            from sansadx_backend.db import SessionLocal as _SL, Tenant as _T
                            _db = _SL()
                            try:
                                _ten = _db.query(_T).filter(_T.id == tenant_id).first()
                                if _ten:
                                    _tenant_const = _ten.constituency
                            finally:
                                _db.close()
                        except Exception:
                            pass
                    
                    if _tenant_const:
                        for base in ["data/geography", "/app/data/geography"]:
                            const_dir = os.path.join(base, _tenant_const)
                            if not os.path.isdir(const_dir):
                                # Case-insensitive fallback
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
                            break  # found the folder, stop searching
                except Exception as e:
                    logger.warning(f"Geography file scan failed: {e}")
                
                # 3. Merge: DB overrides take priority, then geography files
                combined_rules = {}
                combined_rules.update(geo_file_rules)
                combined_rules.update(tenant_rules)  # DB overrides win
                
                # 4. Get AI's extracted location
                ai_loc = data.get("grievance_data", {}).get("location", "")
                if ai_loc:
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

            # 🛠️ MULTI-LABEL SYNC + CATEGORY VALIDATION
            if "grievance_data" in data:
                cats = data["grievance_data"].get("categories", [])
                if isinstance(cats, str):
                    cats = [cats]
                validated = _normalize_categories(cats, user_message)
                data["grievance_data"]["categories"] = validated

            return data
            
        except Exception as e:
            logger.error("JSON Parse Error: %s", e)
            return {
                "status": "pending",
                "detected_language": detected_lang,
                "political_response": (
                    "Thank you for contacting us. Your message has been received "
                    "and will be reviewed by our team. 🙏"
                ),
                "grievance_data": {},
                "is_critical": False,
            }

    except Exception as e:
        logger.error("Unexpected outer error in ask_chatgpt_agent: %s", e)
        return {
            "status": "pending",
            "detected_language": "",
            "political_response": (
                "Thank you for contacting us. Your message has been received "
                "and will be reviewed by our team. 🙏"
            ),
            "grievance_data": {},
            "is_critical": False,
        }