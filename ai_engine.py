import os
import requests
import json
import glob
import difflib  # Logic for Fuzzy Matching (Typos)

# ==========================================
# 1. THE PERSONA
# ==========================================
SYSTEM_PROMPT = """
You are the **Member of Parliament (MP)**.
You are replying personally to citizens on WhatsApp.

────────────────────────
STEP 1: SAFETY & MODERATION (AI POWERED)
────────────────────────
**Do not look for specific keywords.** Analyze the **INTENT**.
If the user's message contains **Direct Abuse, Vulgarity, or Threats** in ANY language:
- Set "user_intent": "offensive"
- Set "status": "OFFENSIVE"
- **SELECT THE CORRECT WARNING FROM BELOW:**
  - **Hindi:** "मर्यादा रखें। अभद्र भाषा का प्रयोग करने पर आप पर कानूनी कार्यवाही हो सकती है।"
  - **Marathi:** "मर्यादा राखा. अभद्र भाषेचा वापर केल्यास कायदेशीर कारवाई होऊ शकते."
  - **Kannada:** "ಮರ್ಯಾದೆ ಕಾಪಾಡಿ. ಅಸಭ್ಯ ಭಾಷೆ ಬಳಸಿದರೆ ಕಾನೂನು ಕ್ರಮ ಕೈಗೊಳ್ಳಲಾಗುವುದು."
  - **English:** "Maintain decorum. Legal action can be taken for abusive language."
- Output JSON immediately.

────────────────────────
STEP 2: PERSONA & LANGUAGE
────────────────────────
- **Identity:** MP. Tone: Professional, Empathetic.
- **Language Rule:** **STRICTLY MATCH** the user's language and script.

────────────────────────
STEP 3: DATA EXTRACTION
────────────────────────
- Allowed Categories: [ "Roads", "Water", "Electricity", "Drainage", "Waste", "Health", "Education", "Other" ]
- **Location Logic:**
  1. Extract the specific Area, Village, or Ward name mentioned by the user.
  2. Put this extracted name in "location_english".
  3. **Leave "assembly_constituency" as "Unknown"** (Our system will map it automatically).

────────────────────────
STEP 4: CLASSIFICATION & RESPONSE (THE 5 TABS)
────────────────────────
Classify the message into **"user_intent"** and **"status"**.

**TAB 1: EMERGENCY**
- **Intent:** "emergency"
- **Status:** "EMERGENCY"
- **Response:** (Translate naturally) "I have flagged your message as High Priority. Please dial 100 for emergencies."

**TAB 2: COMPLAINTS (Default)**
- **Intent:** "complaint"
- **Status Options:**
  - "COMPLETED" (Grievance + Location found) -> "Ji, I have noted the [Category] complaint in [Location]. You will be updated soon."
  - "INCOMPLETE" (Location missing) -> "Ji, I see the [Category] issue. To help you, please tell me the exact Colony, Ward, or Area name?"
  - "FOLLOW_UP" (Status check) -> "Ji, let me check the status of your previous complaint and get back to you."
  - "SUGGESTION" (New Ideas) -> "That is a constructive suggestion. I have noted it for our planning committee."

**TAB 3: REQUESTS**
- **Intent:** "request"
- **Status:** "REQUEST" (Jobs, Transfers, Admissions)
- **Response:** (Translate naturally) "Namaste. For personal requests, please visit our Public Office with a written application."

**TAB 4: GREETINGS**
- **Intent:** "greeting"
- **Status:** "IRRELEVANT" or "APPRECIATION"
- **Response:** (Translate naturally) "Namaste! Please let me know if there are any civic issues."

**TAB 5: SPAM**
- **Intent:** "offensive"
- **Status:** "OFFENSIVE"
- **Response:** (See Step 1 Warning)

────────────────────────
STEP 5: FEW-SHOT EXAMPLES (CONTEXTUAL LEARNING)
────────────────────────
Input: "Hogo huch suli mangen" (Kannada - Abuse)
Output JSON:
{{
  "user_intent": "offensive",
  "status": "OFFENSIVE",
  "political_response": "__WARN_KANNADA__",
  "grievance_data": {{ "category": null, "location_english": null, "assembly_constituency": null }}
}}

Input: "My son needs a job" (Request)
Output JSON:
{{
  "user_intent": "request",
  "status": "REQUEST",
  "political_response": "Namaste. For personal requests, please visit our Public Office.",
  "grievance_data": {{ "category": "Other", "location_english": null, "assembly_constituency": null }}
}}

Input: "Khasa Bag mein kachra hai" (Complaint)
Output JSON:
{{
  "user_intent": "complaint",
  "status": "COMPLETED",
  "political_response": "Ji, Khasa Bag mein kachra uthane ki shikayat note kar li hai.",
  "grievance_data": {{
      "category": "Waste",
      "location_english": "Khasa Bag",
      "assembly_constituency": "Unknown"
  }}
}}

──────────────────────
STEP 6: YOUR TASK
────────────────────────
Analyze the USER MESSAGE below and output valid JSON.

USER MESSAGE: "{user_message}"
"""

# ==========================================
# 2. CONFIGURATION & STATIC DATA
# ==========================================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

STATIC_RESPONSES = {
    "__WARN_HINDI__": "मर्यादा रखें। अभद्र भाषा का प्रयोग करने पर आप पर कानूनी कार्यवाही हो सकती है।",
    "__WARN_MARATHI__": "मर्यादा राखा. अभद्र भाषेचा वापर केल्यास कायदेशीर कारवाई होऊ शकते.",
    "__WARN_KANNADA__": "ಮರ್ಯಾದೆ ಕಾಪಾಡಿ. ಅಸಭ್ಯ ಭಾಷೆ ಬಳಸಿದರೆ ಕಾನೂನು ಕ್ರಮ ಕೈಗೊಳ್ಳಲಾಗುವುದು.",
    "__WARN_ENGLISH__": "Maintain decorum. Legal action can be taken for abusive language."
}

# ==========================================
# 3. AI EXECUTION (LIGHTWEIGHT + PYTHON OVERRIDE)
# ==========================================
def ask_groq_agent(user_message, tenant_id=1):
    if not GROQ_API_KEY: 
        print("❌ ERROR: GROQ_API_KEY is missing.")
        return {"status": "ERROR", "political_response": "Server Error."}

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}

    # We removed JURISDICTION_CONTEXT from here to fix 'Server Busy' errors.
    formatted_prompt = SYSTEM_PROMPT.format(user_message=user_message)

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": formatted_prompt}],
        "temperature": 0.1, 
        "response_format": {"type": "json_object"}
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        
        # Check for API Errors (like 400 Bad Request)
        if response.status_code != 200:
            print(f"⚠️ GROQ API ERROR: {response.status_code} - {response.text}")
            return {"status": "ERROR", "political_response": "Server busy."}

        content = response.json()["choices"][0]["message"]["content"]
        
        try:
            data = json.loads(content)
            
            # [START OF MULTI-TENANT FIX (WITH AUTO-CORRECT)] ----------------
            try:
                # 1. Load the Rulebook
                with open("tenant_overrides.json", "r") as f:
                    all_overrides = json.load(f)
                
                # 2. Get Rules for THIS Tenant
                tenant_rules = all_overrides.get(str(tenant_id), {})
                
                # 3. Get AI's guess
                ai_loc = data.get("grievance_data", {}).get("location_english", "").lower().strip()
                
                # 4. SMART MATCHING (Exact or Fuzzy)
                match_found = False
                final_loc_name = ai_loc
                
                if ai_loc in tenant_rules:
                    # Case A: Perfect Exact Match
                    match_found = True
                elif ai_loc:
                    # Case B: Fuzzy Logic (Typos)
                    # cutoff=0.8 means 80% similarity required. n=1 gets the single best match.
                    matches = difflib.get_close_matches(ai_loc, tenant_rules.keys(), n=1, cutoff=0.8)
                    if matches:
                        print(f"✨ Auto-Corrected: '{ai_loc}' -> '{matches[0]}'")
                        final_loc_name = matches[0]
                        match_found = True
                
                # 5. Apply the Fix
                if match_found:
                    correct_constituency = tenant_rules[final_loc_name]
                    
                    data["assembly_constituency"] = correct_constituency
                    data["constituency"] = correct_constituency
                    if "grievance_data" in data:
                        data["grievance_data"]["assembly_constituency"] = correct_constituency
                        # Save the corrected spelling back to data so the database is clean
                        data["grievance_data"]["location_english"] = final_loc_name.title()
                        
                    print(f"✅ Location Mapped: {final_loc_name} -> {correct_constituency}")
                        
            except Exception as e:
                print(f"⚠️ Override Logic Warning: {e}") 
            # [END OF FIX] -------------------------------------------------

            # -----------------------------------------------
            # 🛡️ LANGUAGE SWAP LOGIC
            # -----------------------------------------------
            raw_resp = data.get("political_response", "")
            if raw_resp in STATIC_RESPONSES:
                data["political_response"] = STATIC_RESPONSES[raw_resp]

            # 🛠️ CLEANUP LOGIC
            intent = data.get("user_intent", "complaint")
            
            if intent in ["offensive", "greeting", "request"]:
                data["assembly_constituency"] = None
                data["constituency"] = None
                if "grievance_data" in data:
                    data["grievance_data"]["assembly_constituency"] = None
                    data["grievance_data"]["location_english"] = None
            else:
                if "grievance_data" in data:
                    const = data["grievance_data"].get("assembly_constituency")
                    if const and const != "Unknown":
                        data["assembly_constituency"] = const
                        data["constituency"] = const
            
            return data
            
        except Exception as e:
            print(f"❌ JSON Parse Error: {e}")
            return {"status": "ERROR", "political_response": "AI Error."}
            
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return {"status": "ERROR", "political_response": "Connection Error."}