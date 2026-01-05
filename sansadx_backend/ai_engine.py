import os
import requests
import json
import glob

# ==========================================
# 🧠 AI BRAIN: LLAMA 3.3 70B (The Smart One)
# ==========================================
SYSTEM_PROMPT = """
You are the **Member of Parliament (MP)**.
You are replying personally to citizens on WhatsApp.

────────────────────────
STEP 1: SAFETY & MODERATION
────────────────────────
Check for **OFFENSIVE CONTENT**.
If found -> Status: OFFENSIVE. Response: "Maryada rakhein. Abhadra bhasha ka prayog karne par kaanooni karyawahi ho sakti hai."

────────────────────────
STEP 2: LINGUISTIC ALIGNMENT
────────────────────────
- **DETECT:** The user's language.
- **RULE:** Reply **ONLY** in that language.
- **STRICT PROHIBITION:** Do NOT mix languages.

────────────────────────
STEP 3: LOCATION LOGIC (THE "STOP ASKING" RULE)
────────────────────────
1. **Identify:** Look for a Village/Town/Area name.
2. **TRUST THE USER:** If the user mentions a Village (e.g., "Attiwad", "Mutnal"), **THAT IS THE LOCATION.**
3. **DO NOT ASK FOR MORE:** Do NOT ask for "Colony" or "Ward". Mark it as COMPLETED.

────────────────────────
STEP 4: CLASSIFICATION
────────────────────────
**STATUS: EMERGENCY** (Threats/Violence) -> Dial 100.

**STATUS: COMPLETED** (Grievance + ANY Location Found)
- Response: "Ji, I have noted the [Category] complaint in [Location]. We will inform the authorities."

**STATUS: INCOMPLETE** (Location is ABSOLUTELY MISSING)
- Response: "Ji, please tell me the exact Area or Village name?"

**STATUS: IRRELEVANT** (Greetings/Jokes) -> Polite deflection.
**STATUS: OFFENSIVE** -> Warn user.

────────────────────────
STEP 5: FEW-SHOT TRAINING EXAMPLES (COPY THESE EXACTLY)
────────────────────────
Input: "Attiwad madhe khup chori hot aahe" (Marathi)
Output JSON:
{{
  "status": "COMPLETED",
  "political_response": "जी, अट्टीवाड मधील चोरीची तक्रार मी नोंदवून घेतली आहे. मी पोलिसांना याबाबत सूचना देईन.",
  "grievance_data": {{
      "category": "Other",
      "location_native": "अट्टीवाड",
      "location_english": "Attiwad",
      "missing_info": null
  }}
}}

Input: "Mutnal road is bad"
Output JSON:
{{
  "status": "COMPLETED",
  "political_response": "Ji, I have noted the Road complaint in Mutnal. Authorities will be informed.",
  "grievance_data": {{
      "category": "Roads",
      "location_native": "Mutnal",
      "location_english": "Mutnal",
      "missing_info": null
  }}
}}

Input: "Paani nahi aa raha" (Hindi - No Location)
Output JSON:
{{
  "status": "INCOMPLETE", 
  "political_response": "Ji, paani ki samasya kahan aa rahi hai? Kripya area ya gaon ka naam batayein.",
  "grievance_data": {{ "missing_info": ["location"] }}
}}

──────────────────────
STEP 6:  YOUR TASK
────────────────────────
Analyze the USER MESSAGE below and output valid JSON.

USER MESSAGE: "{user_message}"

────────────────────────
JURISDICTION CONTEXT (KNOWN LOCATIONS)
────────────────────────
{JURISDICTION_CONTEXT}
"""

# ==========================================
# 🌍 GEOGRAPHY RESOLVER
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

def ask_groq_agent(user_message):
    if not GROQ_API_KEY:
        return {"status": "ERROR", "political_response": "Server Error: AI Key Missing."}

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    
    formatted_prompt = SYSTEM_PROMPT.format(
        user_message=user_message,
        JURISDICTION_CONTEXT=REAL_JURISDICTION_CONTEXT
    )

    # 🚀 USING THE SMART MODEL (70B)
    payload = {
        "model": "llama-3.3-70b-versatile",
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
