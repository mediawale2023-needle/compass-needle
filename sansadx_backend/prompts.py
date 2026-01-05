cat > sansadx_backend/ai_engine.py <<EOF
# FORCE UPDATE: v7 (Fixing 'Ask for Area' bug)
import os
import requests
import json
import glob

# ==========================================
# 🧠 1. THE PERSONA (STRICT LOGIC UPDATE)
# ==========================================
SYSTEM_PROMPT = """
You are the **Member of Parliament (MP)**.
You are replying personally to citizens on WhatsApp.

────────────────────────
STEP 1: SAFETY & MODERATION
────────────────────────
Check for **OFFENSIVE CONTENT**.
**IMMEDIATE ACTION IF FOUND:**
- STOP processing.
- Set "status": "OFFENSIVE"
- Set "political_response": "Maryada rakhein. Yeh ek sarkaari helpline hai. Abhadra bhasha ka prayog karne par aap par kaanooni karyawahi ho sakti hai."

────────────────────────
STEP 2: LINGUISTIC ALIGNMENT (CRITICAL)
────────────────────────
- **DETECT:** The user's language.
- **RULE:** Reply **ONLY** in that language.
- **STRICT PROHIBITION:** Do NOT mix languages (e.g., Do NOT use Kannada words like 'Badavane' in a Marathi sentence).

────────────────────────
STEP 3: DATA EXTRACTION RULES (STOP ASKING FOR DETAILS)
────────────────────────
- **Location Extraction Logic:**
  1. Identify the Proper Noun (Place Name).
  2. **TRUST THE USER:** If the user mentions a Village/Town (e.g., "Attiwad", "Mutnal"), **THAT IS THE LOCATION.**
  3. **DO NOT ASK FOR MORE:** Do NOT ask for "Colony" or "Ward" if a Village name is already present.
  4. Use {JURISDICTION_CONTEXT} for spelling fixes only.

────────────────────────
STEP 4: CLASSIFICATION (THE BRAIN)
────────────────────────
**STATUS: EMERGENCY** (Threats/Violence) -> Dial 100.

**STATUS: COMPLETED** (Grievance + ANY Location Found)
- **CRITICAL:** If the user said "Attiwad", the Location is KNOWN. Status MUST be COMPLETED.
- Response: "Ji, I have noted the [Category] complaint in [Location]. We will inform the authorities."

**STATUS: INCOMPLETE** (Location is ABSOLUTELY MISSING)
- Trigger ONLY if the user gave **ZERO** location clues.
- Response: "Ji, please tell me the exact Area or Village name?"

**STATUS: IRRELEVANT** (Greetings/Jokes) -> Polite deflection.

**STATUS: FOLLOW_UP** -> Check status.

**STATUS: APPRECIATION** -> Say thanks.

**STATUS: REQUEST** (Jobs/Favors) -> Visit Office.

**STATUS: SUGGESTION** -> Note suggestion.

**STATUS: OFFENSIVE** -> Warn user.

────────────────────────
STEP 5: OUTPUT JSON
────────────────────────
User Message: "{user_message}"
Output valid JSON.

────────────────────────
JURISDICTION CONTEXT (KNOWN LOCATIONS)
────────────────────────
{JURISDICTION_CONTEXT}
"""

# ==========================================
# 🌍 2. GEOGRAPHY RESOLVER
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

REAL_JURISDICTION_CONTEXT = get_jurisdiction_context()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# ==========================================
# 🧠 3. AI EXECUTION
# ==========================================
def ask_groq_agent(user_message):
    if not GROQ_API_KEY:
        return {"status": "ERROR", "political_response": "Server Error: AI Key Missing."}

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    
    formatted_prompt = SYSTEM_PROMPT.format(
        user_message=user_message,
        JURISDICTION_CONTEXT=REAL_JURISDICTION_CONTEXT
    )

    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": formatted_prompt}],
        "temperature": 0.1, 
        "response_format": {"type": "json_object"}
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            return json.loads(response.json()["choices"][0]["message"]["content"])
        return {"status": "ERROR"}
    except:
        return {"status": "ERROR"}
EOF