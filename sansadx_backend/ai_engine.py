import os
import requests
import json
import glob
import difflib  # Logic for Fuzzy Matching (Typos)
from openai import OpenAI # Switch to OpenAI
from .prompts import SYSTEM_PROMPT, TAXONOMY_CATEGORIES

# ==========================================
# 1. CONFIGURATION
# ==========================================
# Initialize OpenAI Client
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

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
    if not os.environ.get("OPENAI_API_KEY"): 
        print("❌ ERROR: OPENAI_API_KEY is missing.")
        return {"status": "ERROR", "political_response": "Server Error."}

    # Fetch dynamic jurisdiction context
    real_jurisdiction_context = get_jurisdiction_context()

    # Format the v3.0 prompt from prompts.py
    formatted_prompt = SYSTEM_PROMPT.format(
        user_message=user_message,
        jurisdiction_context=real_jurisdiction_context,
        taxonomy_categories=TAXONOMY_CATEGORIES
    )

    try:
        # OpenAI Chat Completion Call with Strict JSON Mode
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": formatted_prompt}],
            response_format={"type": "json_object"}
        )
        
        try:
            # Parse OpenAI response
            content = response.choices[0].message.content
            data = json.loads(content)
            
            # [START OF MULTI-TENANT FIX (WITH AUTO-CORRECT)] ----------------
            try:
                # 1. Load the Rulebook
                with open("tenant_overrides.json", "r") as f:
                    all_overrides = json.load(f)
                
                # 2. Get Rules for THIS Tenant
                tenant_rules = all_overrides.get(str(tenant_id), {})
                
                # 3. Get AI's extracted location (v3 key is 'location')
                ai_loc = data.get("grievance_data", {}).get("location", "")
                if ai_loc:
                    ai_loc_clean = ai_loc.lower().strip()
                    
                    # 4. SMART MATCHING (Exact or Fuzzy)
                    match_found = False
                    final_loc_name = ai_loc_clean
                    
                    if ai_loc_clean in tenant_rules:
                        match_found = True
                    else:
                        matches = difflib.get_close_matches(ai_loc_clean, tenant_rules.keys(), n=1, cutoff=0.8)
                        if matches:
                            print(f"✨ Auto-Corrected: '{ai_loc_clean}' -> '{matches[0]}'")
                            final_loc_name = matches[0]
                            match_found = True
                    
                    # 5. Apply the Fix
                    if match_found:
                        correct_constituency = tenant_rules[final_loc_name]
                        data["assembly_constituency"] = correct_constituency
                        data["constituency"] = correct_constituency
                        if "grievance_data" in data:
                            data["grievance_data"]["assembly_constituency"] = correct_constituency
                            data["grievance_data"]["location"] = final_loc_name.title()
                            
                        print(f"✅ Location Mapped: {final_loc_name} -> {correct_constituency}")
                    else:
                        data["assembly_constituency"] = "Unknown"
                        
            except Exception as e:
                print(f"⚠️ Override Logic Warning: {e}") 
            # [END OF FIX] -------------------------------------------------

            # -----------------------------------------------
            # 🛡️ LANGUAGE SWAP LOGIC
            # -----------------------------------------------
            raw_resp = data.get("political_response", "")
            if raw_resp in STATIC_RESPONSES:
                data["political_response"] = STATIC_RESPONSES[raw_resp]

            # -----------------------------------------------
            # 🛠️ MULTI-LABEL SYNC
            # -----------------------------------------------
            # Ensure categories is always a list for the database
            if "grievance_data" in data:
                cats = data["grievance_data"].get("categories", [])
                if isinstance(cats, str):
                    data["grievance_data"]["categories"] = [cats]
            
            return data
            
        except Exception as e:
            print(f"❌ JSON Parse Error: {e}")
            return {"status": "ERROR", "political_response": "AI Error."}
            
    except Exception as e:
        print(f"❌ OpenAI Connection Error: {e}")
        return {"status": "ERROR", "political_response": "Connection Error."}