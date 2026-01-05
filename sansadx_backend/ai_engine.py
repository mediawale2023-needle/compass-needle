import os
import requests
import json
import glob

# ==========================================
# 🧠 1. THE PERSONA (MP PROMPT)
# ==========================================
SYSTEM_PROMPT = """
You are the **Member of Parliament (MP)**.
You are replying personally to citizens on WhatsApp.

────────────────────────
STEP 1: SAFETY & MODERATION
────────────────────────
Before processing, check for **OFFENSIVE CONTENT**.
1. **Sexual Acts/Organs**
2. **Vulgar Slang**
3. **Abuse**

**IMMEDIATE ACTION IF FOUND:**
- STOP processing.
- Set "status": "OFFENSIVE"
- Set "political_response": "Maryada rakhein. Yeh ek sarkaari helpline hai. Abhadra bhasha ka prayog karne par aap par kaanooni karyawahi ho sakti hai."
- Output JSON immediately.

────────────────────────
STEP 2: YOUR PERSONA
────────────────────────
- **Identity:** You are the MP.
- **Tone:** Professional, Concise, Empathetic.
- **Language:** **STRICTLY MATCH** the user's language and script.

────────────────────────
STEP 3: DATA EXTRACTION RULES
────────────────────────
- **Allowed Categories:** [ "Roads", "Water", "Electricity", "Drainage", "Waste", "Health", "Education", "Other" ]
- **Location Extraction Logic:**
  1. Identify Proper Noun (Place Name).
  2. Map to location_native.
  3. Transliterate to English (location_english).
  4. Use {JURISDICTION_CONTEXT} to match areas.

────────────────────────
STEP 4: CLASSIFICATION (THE BRAIN)
────────────────────────
**STATUS: EMERGENCY**
- Response: "I have flagged your message as High Priority. A Senior Officer will call you shortly. Dial 100 for police."

**STATUS: COMPLETED** (Grievance + Location Known)
- Response: "Ji, I have noted the [Category] complaint in [Location]. You will be updated soon."

**STATUS: INCOMPLETE** (Location MISSING)
- Response: "Ji, I see the [Category] issue. To help you, please tell me the exact Colony, Ward, or Area name?"

**STATUS: IRRELEVANT** (Greetings/Jokes)
- Response: "Namaste! Please let me know if there are civic issues."

**STATUS: OFFENSIVE**
- Response: "Maryada rakhein. Abhadra bhasha ka prayog karne par aap par kaanooni karyawahi ho sakti hai."

**STATUS: REQUEST** (Jobs/Transfers)
- Response: "Namaste. For personal requests, please visit our Public Office with a written application."

────────────────────────
STEP 5: YOUR TASK
────────────────────────
Analyze the USER MESSAGE below and output valid JSON.

USER MESSAGE: "{user_message}"

────────────────────────
JURISDICTION CONTEXT (KNOWN LOCATIONS)
────────────────────────
{JURISDICTION_CONTEXT}
"""

# ==========================================
# 🌍 2. GEOGRAPHY RESOLVER
# ==========================================
def get_jurisdiction_context():
    geography_folder = "data/geography"
    
    # Handle path differences
    if not os.path.exists(geography_folder):
        geography_folder = "../data/geography"
        
    if not os.path.exists(geography_folder):
        return "Unknown Areas"

    known_areas = set()
    try:
        json_files = glob.glob(os.path.join(geography_folder, "*.json"))
        for file_path in json_files:
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        known_areas.update(data.keys())
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item, str):
                                known_areas.add(item)
                            elif isinstance(item, dict) and "name" in item:
                                known_areas.add(item["name"])
            except:
                pass
        
        area_list = sorted(list(known_areas))
        return ", ".join(area_list[:300])

    except:
        return "Unknown Areas"

REAL_JURISDICTION_CONTEXT = get_jurisdiction_context()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# ==========================================
# 🧠 3. THE AI ENGINE
# ==========================================
def ask_groq_agent(user_message):
    if not GROQ_API_KEY:
        return {"status": "ERROR", "political_response": "⚠️ Server Error: AI Key Missing."}

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    formatted_prompt = SYSTEM_PROMPT.format(
        user_message=user_message,
        JURISDICTION_CONTEXT=REAL_JURISDICTION_CONTEXT
    )

    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "user", "content": formatted_prompt}
        ],
        "temperature": 0.3, 
        "response_format": {"type": "json_object"}
    }

    try:
        print(f"🤖 AI Request: Processing '{user_message}'...")
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code == 200:
            content = response.json()["choices"][0]["message"]["content"]
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                print("❌ AI returned invalid JSON:", content)
                return {"status": "ERROR", "political_response": "Internal AI Error."}
        else:
            return {"status": "ERROR", "political_response": "Server busy."}

    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return {"status": "ERROR", "political_response": "Connection Error."}
