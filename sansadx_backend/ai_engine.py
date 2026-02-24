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
def get_jurisdiction_context():
    paths = ["data/geography", "../data/geography", "/app/data/geography"]
    known_areas = set()
    for folder in paths:
        if os.path.exists(folder):
            for file_path in glob.glob(os.path.join(folder, "*.json")):
                try:
                    with open(file_path, "r") as f:
                        data = json.load(f)
                        if isinstance(data, dict): known_areas.update(data.keys())
                        elif isinstance(data, list):
                            for item in data:
                                if isinstance(item, str): known_areas.add(item)
                                elif isinstance(item, dict) and "name" in item: known_areas.add(item["name"])
                except: pass
    
    if not known_areas: return "Attiwad, Mutnal, Tilakwadi, Belgaum" 
    return ", ".join(sorted(list(known_areas))[:300])

# ==========================================
# 3. AI EXECUTION (v3.0 ENGINE)
# ==========================================
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

    # Fetch dynamic jurisdiction context
    real_jurisdiction_context = get_jurisdiction_context()

    # --- TAD NECESSARY: Inject MP Persona & Professional Constraints ---
    persona_instructions = """
    STRICT RULES:
    1. You are a Member of Parliament (MP) communicating with a citizen.
    2. NEVER mention 'departments', 'forwarding', or 'officials'.
    3. Maintain professional authority. DO NOT say 'it feels good' or 'I understand'.
    4. NO PROMISES: Do not promise a specific action. State the grievance is 'noted and recorded'.
    5. LANGUAGE MIRROR: First detect the EXACT language of the user's message — Hindi, Marathi, Kannada, English, or Hinglish. Then respond in that SAME language. Do NOT default to Hindi. Key distinction: Marathi uses words like "aahe", "nahi", "hotoy", "madhe", "kela", "zala". Hindi uses "hai", "nahi", "ho raha", "mein", "kiya", "hua". If the user writes in Marathi, you MUST reply in Marathi.
    6. Only If info is missing (location/area), ask for it directly: "Please provide the name of your area/village."
    7. Be concise (max 2 sentences).
    """

    # Format the v3.0 system instructions from prompts.py
    system_instructions = f"{persona_instructions}\n\n{SYSTEM_PROMPT.format(user_message='{{MESSAGE_BELOW}}', jurisdiction_context=real_jurisdiction_context, taxonomy_categories=TAXONOMY_CATEGORIES)}"

    try:
        # OpenAI Chat Completion Call with Strict JSON Mode
        # System role: classification instructions (higher authority)
        # User role: citizen's raw message (keeps it separate)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_instructions},
                {"role": "user", "content": user_message}
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
                # 1. Load the Rulebook
                override_path = "tenant_overrides.json"
                if not os.path.exists(override_path):
                    override_path = "/app/tenant_overrides.json"

                with open(override_path, "r") as f:
                    all_overrides = json.load(f)
                
                # --- TAD NECESSARY: Fix path to 'geo_overrides' key ---
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
                        
                        # --- TAD NECESSARY: Force status to completed if location is matched ---
                        data["status"] = "completed"
                        
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