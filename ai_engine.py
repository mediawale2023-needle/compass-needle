import os
import requests
import json
import glob

# ==========================================
# 1. THE PERSONA (WITH HARDCODED TEMPLATES + INTENT CLASSIFICATION)
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
- **Location & Constituency Logic:**
  1. **TRUST THE USER:** If they name a place, USE IT.
  2. **MANDATORY LOOKUP:** Check the {JURISDICTION_CONTEXT} list below.
     - If location found (e.g., "Attiwad" -> "Belgaum Rural"), extract "Belgaum Rural".
     - **Output this name in the JSON exactly.**

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
  "political_response": "ಮರ್ಯಾದೆ ಕಾಪಾಡಿ. ಅಸಭ್ಯ ಭಾಷೆ ಬಳಸಿದರೆ ಕಾನೂನು ಕ್ರಮ ಕೈಗೊಳ್ಳಲಾಗುವುದು.",
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
      "assembly_constituency": "Belgaum North"
  }}
}}

──────────────────────
STEP 6: YOUR TASK
────────────────────────
Analyze the USER MESSAGE below and output valid JSON.

USER MESSAGE: "{user_message}"

────────────────────────
JURISDICTION CONTEXT (LOOKUP TABLE)
────────────────────────
{JURISDICTION_CONTEXT}
"""

# ==========================================
# 2. SMART GEOGRAPHY RESOLVER (DEEP SCAN)
# ==========================================
def get_jurisdiction_context():
    mapping = []
    cwd = os.getcwd()
    print(f"DEBUG: Scanning geography from: {cwd}")
    
    for root, dirs, files in os.walk(cwd):
        for filename in files:
            if filename.endswith(".json"):
                if "node_modules" in root or "venv" in root: continue
                
                file_path = os.path.join(root, filename)
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        data = json.load(f)
                        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                            if "locality" in data[0] or "station_number" in data[0]:
                                constituency_name = filename.replace(".json", "").replace("_", " ").title()
                                areas = []
                                for item in data:
                                    if isinstance(item, dict):
                                        loc = item.get("locality") or item.get("building_name")
                                        if loc and len(loc) > 2: areas.append(loc.strip())

                                areas = list(set(areas))
                                if areas:
                                    mapping.append(f"📍 {constituency_name} includes: {', '.join(areas[:250])}")
                                    print(f"DEBUG: Loaded {constituency_name} ({len(areas)} areas)")
                except Exception: continue

    if not mapping: return "No Jurisdiction Data Available."
    return "\n".join(mapping)

REAL_JURISDICTION_CONTEXT = get_jurisdiction_context()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# ==========================================
# 3. AI EXECUTION (WITH CLEANUP BRIDGE)
# ==========================================
def ask_groq_agent(user_message):
    if not GROQ_API_KEY: return {"status": "ERROR", "political_response": "Server Error."}

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}

    formatted_prompt = SYSTEM_PROMPT.format(
        user_message=user_message,
        JURISDICTION_CONTEXT=REAL_JURISDICTION_CONTEXT
    )

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": formatted_prompt}],
        "temperature": 0.1, 
        "response_format": {"type": "json_object"}
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            content = response.json()["choices"][0]["message"]["content"]
            try:
                data = json.loads(content)
                
                # 🛠️ CLEANUP: Wipe constituency for Non-Complaints
                intent = data.get("user_intent", "complaint")
                
                if intent in ["offensive", "greeting", "request"]:
                    # Force wipe geography logic so it doesn't show on map
                    data["assembly_constituency"] = None
                    data["constituency"] = None
                    if "grievance_data" in data:
                        data["grievance_data"]["assembly_constituency"] = None
                        data["grievance_data"]["location_english"] = None
                
                else:
                    # 🛠️ DATA BRIDGE: Copy constituency for Complaints/Emergencies
                    if "grievance_data" in data:
                        const = data["grievance_data"].get("assembly_constituency")
                        if const and const != "Unknown":
                            data["assembly_constituency"] = const
                            data["constituency"] = const # Double Safety
                
                return data
            except: return {"status": "ERROR", "political_response": "AI Error."}
        else: return {"status": "ERROR", "political_response": "Server busy."}
    except Exception: return {"status": "ERROR", "political_response": "Connection Error."}