import os
import requests
import json
import glob
import logging
import difflib  # Logic for Fuzzy Matching (Typos)
from openai import OpenAI # Switch to OpenAI
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

    IMPORTANT — ALWAYS ACCEPT COMPLAINTS:
    - If a citizen mentions ANY location and a civic issue (water, road, electricity, etc.),
      ALWAYS acknowledge the complaint, mark it as COMPLETED (or INCOMPLETE if location is missing),
      and say it has been noted and recorded.
    - NEVER mark a real civic complaint as IRRELEVANT. IRRELEVANT is ONLY for greetings, jokes,
      or messages with zero civic content.
    - If the location is unknown to you, still accept the complaint. Small villages, mohallas,
      and bazaars may not be in your known list but are still valid.
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

    try:
        # OpenAI Chat Completion Call with Strict JSON Mode
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_instructions},
                {"role": "user", "content": tagged_message}
            ],
            response_format={"type": "json_object"}
        )
        
        try:
            # Parse OpenAI response
            content = response.choices[0].message.content
            data = json.loads(content)
            
            # 🛡️ NORMALIZATION: Ensure status is lowercase to match main.py logic
            if "status" in data:
                data["status"] = data["status"].lower()

            # [START OF MULTI-TENANT FIX (WITH AUTO-CORRECT)] ----------------
            try:
                # 1. Load the Rulebook from DB
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
                
                # 3. Get AI's extracted location
                ai_loc = data.get("grievance_data", {}).get("location", "")
                if ai_loc:
                    ai_loc_clean = ai_loc.lower().strip()
                    
                    # 4. SMART MATCHING (Exact or Fuzzy)
                    match_found = False
                    final_loc_name = ai_loc_clean
                    
                    # Match against lower-case keys in tenant_rules
                    tenant_keys_lower = {k.lower(): k for k in tenant_rules.keys()}
                    
                    if ai_loc_clean in tenant_keys_lower:
                        final_loc_name = tenant_keys_lower[ai_loc_clean]
                        match_found = True
                    else:
                        matches = difflib.get_close_matches(ai_loc_clean, tenant_keys_lower.keys(), n=1, cutoff=0.75)
                        if matches:
                            final_loc_name = tenant_keys_lower[matches[0]]
                            logger.info(f"Auto-Corrected: '{ai_loc_clean}' -> '{final_loc_name}'")
                            match_found = True
                    
                    # 5. Apply the Fix
                    if match_found:
                        correct_constituency = tenant_rules[final_loc_name]
                        data["assembly_constituency"] = correct_constituency
                        data["constituency"] = correct_constituency
                        
                        # --- FIXED: Keep status as "new" so staff must manually triage ---
                        original_status = data.get("status", "").lower()
                        if original_status not in ("emergency", "offensive"):
                            data["status"] = "new"
                        
                        # Set is_critical for emergency cases
                        if original_status == "emergency":
                            data["is_critical"] = True
                        
                        if "grievance_data" in data:
                            data["grievance_data"]["assembly_constituency"] = correct_constituency
                            data["grievance_data"]["location"] = final_loc_name # Set to official spelling
                            
                        logger.info(f"Location Mapped: {final_loc_name} -> {correct_constituency}")
                    else:
                        data["assembly_constituency"] = "Unknown"
                        
            except Exception as e:
                logger.warning(f"Override Logic Warning: {e}") 
            # [END OF FIX] -------------------------------------------------

            # 🛡️ LANGUAGE SWAP LOGIC
            raw_resp = data.get("political_response", "")
            if raw_resp in STATIC_RESPONSES:
                data["political_response"] = STATIC_RESPONSES[raw_resp]

            # 🛠️ MULTI-LABEL SYNC
            if "grievance_data" in data:
                cats = data["grievance_data"].get("categories", [])
                if isinstance(cats, str):
                    data["grievance_data"]["categories"] = [cats]
            
            return data
            
        except Exception as e:
            logger.error(f"JSON Parse Error: {e}")
            return {"status": "error", "political_response": "AI Error."}
            
    except Exception as e:
        logger.error(f"OpenAI Connection Error: {e}")
        return {"status": "error", "political_response": "Connection Error."}