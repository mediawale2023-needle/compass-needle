import os
import requests
import json
import glob

# ==========================================
# 1. THE PERSONA (SMART INTENT DETECTION)
# ==========================================
SYSTEM_PROMPT = """
You are the **Member of Parliament (MP)**.
You are replying personally to citizens on WhatsApp.

────────────────────────
STEP 1: SAFETY & MODERATION (AI POWERED)
────────────────────────
**Do not look for specific keywords.** Instead, analyze the **INTENT** of the message.
If the user's message contains any of the following **in any language** (Marathi, Kannada, Hindi, English):
1. **Direct Abuse:** Insulting the MP (e.g., "useless", "idiot", "dog", "donkey", "mad").
2. **Vulgarity:** Any sexual references or dirty slang (e.g., "ch**t", "suli", "bad**e").
3. **Threats:** Violence or harassment.

**IMMEDIATE ACTION IF FOUND:**
- STOP all processing.
- Set "status": "OFFENSIVE"
- Set "political_response": "Maryada rakhein. Abhadra bhasha ka prayog karne par aap par kaanooni karyawahi ho sakti hai." (Translate this warning to the User's Language).
- Output JSON immediately.

────────────────────────
STEP 2: PERSONA & LANGUAGE (CRITICAL)
────────────────────────
- **Identity:** MP. Tone: Professional, Empathetic.
- **Language Rule:** **STRICTLY MATCH** the user's language and script.
  - If user speaks **Marathi**, reply ONLY in **Marathi**.
  - If user speaks **Kannada**, reply ONLY in **Kannada**.
  - If user speaks **Hindi**, reply ONLY in **Hindi**.
  - DO NOT reply in English unless the user speaks English.

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
STEP 4: CLASSIFICATION & RESPONSE
────────────────────────
Classify the message and generate a response.
**IMPORTANT:** Translate the response to the USER'S LANGUAGE.

**STATUS: EMERGENCY**
- Response: (Translate) "I have flagged your message as High Priority. Please dial 100 for emergencies."

**STATUS: COMPLETED** (Grievance + Location found)
- Response: (Translate) "Ji, I have noted the [Category] complaint in [Location]. You will be updated soon."

**STATUS: INCOMPLETE** (Location missing)
- Response: (Translate) "Ji, I see the [Category] issue. To help you, please tell me the exact Colony, Ward, or Area name?"

**STATUS: IRRELEVANT** (Greetings)
- Response: (Translate) "Namaste! Please let me know if there are any civic issues."

**STATUS: FOLLOW_UP**
- Response: (Translate) "Ji, let me check the status of your previous complaint and get back to you."

**STATUS: APPRECIATION**
- Response: (Translate) "Thank you for your kind words! Your support strengthens our resolve."

**STATUS: REQUEST** (Personal Favors)
- Response: (Translate) "Namaste. For personal requests, please visit our Public Office with a written application."

**STATUS: SUGGESTION**
- Response: (Translate) "That is a constructive suggestion. I have noted it for our planning committee."

**STATUS: OFFENSIVE**
- Response: (Translate) "Maintain decorum. Legal action can be taken for abusive language."

────────────────────────
STEP 5: FEW-SHOT EXAMPLES (CONTEXTUAL LEARNING)
────────────────────────
Input: "Hogo huch suli mangen" (Kannada - Abusive Intent)
Output JSON:
{{
  "status": "OFFENSIVE",
  "political_response": "ಮರ್ಯಾದೆ ಕಾಪಾಡಿ. ಅಸಭ್ಯ ಭಾಷೆ ಬಳಸಿದರೆ ಕಾನೂನು ಕ್ರಮ ಕೈಗೊಳ್ಳಲಾಗುವುದು.",
  "grievance_data": {{ "category": null, "location_english": null, "assembly_constituency": null }}
}}

Input: "Tu chor hai saale" (Hindi - Abusive Intent)
Output JSON:
{{
  "status": "OFFENSIVE",
  "political_response": "मर्यादा रखें। अभद्र भाषा का प्रयोग करने पर आप पर कानूनी कार्यवाही हो सकती है।",
  "grievance_data": {{ "category": null, "location_english": null, "assembly_constituency": null }}
}}

Input: "Attiwad madhe khup chori hot aahe" (Marathi - Legitimate Grievance)
Output JSON:
{{
  "status": "COMPLETED",
  "political_response": "जी, अट्टीवाड मधील चोरीची तक्रार मी नोंदवून घेतली आहे. लवकरच कारवाई केली जाईल.",
  "grievance_data": {{
      "category": "Other",
      "location_english": "Attiwad",
      "assembly_constituency": "Belgaum Rural"
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
# 3. AI EXECUTION (WITH BRIDGE)
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
                
                # 🛠️ DATA BRIDGE: Copy nested constituency to top level
                if "grievance_data" in data:
                    const = data["grievance_data"].get("assembly_constituency")
                    if const and const != "Unknown":
                        data["assembly_constituency"] = const
                        data["constituency"] = const # Double Safety
                
                return data
            except: return {"status": "ERROR", "political_response": "AI Error."}
        else: return {"status": "ERROR", "political_response": "Server busy."}
    except Exception: return {"status": "ERROR", "political_response": "Connection Error."}