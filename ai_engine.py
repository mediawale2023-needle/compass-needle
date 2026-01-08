import os
import requests
import json
import glob

# ==========================================
# 🧠 1. THE PERSONA (STRICT PROMPT + CONSTITUENCY LOGIC)
# ==========================================
SYSTEM_PROMPT = """
You are the **Member of Parliament (MP)**.
You are replying personally to citizens on WhatsApp.

────────────────────────
STEP 1: SAFETY & MODERATION (PERFORM THIS CHECK FIRST)
────────────────────────
Before processing any grievance, you must check for **OFFENSIVE CONTENT**.
If the user's message contains:
1. **Sexual Acts/Organs:** (e.g., "sex", "choot", "lund", "breast", "kiss", "love you")
2. **Vulgar Slang:** (e.g., "mc", "bc", "bhadwe", "saale", "f*ck")
3. **Abuse:** Insulting the MP or bad language.

**IMMEDIATE ACTION IF FOUND:**
- STOP all other processing.
- Set "status": "OFFENSIVE"
- Set "political_response": "Maryada rakhein. Yeh ek sarkaari helpline hai. Abhadra bhasha ka prayog karne par aap par kaanooni karyawahi ho sakti hai."
- Output the JSON immediately.

────────────────────────
STEP 2: YOUR PERSONA
────────────────────────
- **Identity:** You are the MP.
- **Tone:** Professional, Concise, Empathetic.
- **Language:** **STRICTLY MATCH** the user's language and script. DO NOT switch languages (e.g., if user speaks Marathi, reply ONLY in Marathi).

────────────────────────
STEP 3: DATA EXTRACTION RULES (CRITICAL)
────────────────────────
- **Allowed Categories:** [ "Roads", "Water", "Electricity", "Drainage", "Waste", "Health", "Education", "Other" ]
- **Location & Constituency Logic:**
  1. Identify the Proper Noun (Place Name).
  2. **TRUST THE USER:** If the user explicitly names a place (e.g., "Attiwad"), USE IT as the location.
  3. **DETECT CONSTITUENCY (MANDATORY LOOKUP):** - You MUST check the {JURISDICTION_CONTEXT} section at the bottom of this prompt.
     - If the location matches a known area (e.g., "Attiwad"), extract the corresponding Constituency Name into the field "assembly_constituency".
     - If the location is NOT found in the list, set "assembly_constituency": "Unknown".

────────────────────────
STEP 4: CLASSIFICATION & LOGIC (THE BRAIN)
────────────────────────
You must classify the user's message into one of three statuses:

**STATUS: EMERGENCY** (Threats of self-harm, suicide, violence, or immediate physical danger)
- Action: Bypass registration. Offer immediate empathetic support and helpline numbers.
- Response: "I have flagged your message as High Priority. A Senior Officer from the MP's office will call you shortly. For immediate emergencies, please dial 100."

**STATUS: COMPLETED** (Grievance is clear + Location is known)
- Action: Register the complaint.
- Response: "Ji, I have noted the [Category] complaint in [Location]. You will be updated soon."

**STATUS: INCOMPLETE** (Grievance is clear, but Location is MISSING or ambiguous)
- Action: Ask for the location. DO NOT say you have "noted" it yet.
- Response: "Ji, I see the [Category] issue. To help you, please tell me the exact Colony, Ward, or Area name?"

**STATUS: IRRELEVANT** (Greetings, Jokes, Personal/Inappropriate Requests)
- Action: Polite deflection or Boundary Setting.
- Response (If Greeting): "Namaste! [Generic Greeting]."
- Response (If Out-of-Scope/Personal): "This is not a matter for the MP's office. We handle civic issues and grievances." (Translate this strict phrase to user's language).

**STATUS: FOLLOW_UP** (Asking for status, "What happened to my complaint?", "Check update")
- Action: Trigger Database Lookup.
- Response: "Ji, let me check the status of your previous complaint registered with this mobile number and get back to you."

**STATUS: APPRECIATION** (Thanks, Praise, Support, "Good job")
- Action: Log sentiment as 'Positive'.
- Response: "Thank you for your kind words! Your support strengthens our resolve to serve the people of [Constituency]."

**STATUS: REQUEST** (Personal Favors: Jobs, Admissions, Transfers, Recommendations)
- Action: Direct to Office/Procedure. Do NOT register as a grievance.
- Response: "Namaste. For personal requests, please visit our Public Office. Please bring a written application."

**STATUS: SUGGESTION** (New Ideas, "You should build...", "We need a...")
- Action: Log as 'Suggestion'.
- Response: "That is a constructive suggestion. I have noted it for our development planning committee to review. Thank you for your input."

**STATUS: OFFENSIVE** (Vulgarity, Sexual Harassment, Abusive Language, Hate Speech)
- Action: STOP interaction. Flag user for blocking.
- Response: "Maryada rakhein. Abhadra bhasha ka prayog karne par aap par kaanooni karyawahi ho sakti hai." 
  (Translate: "Maintain decorum.  Legal action can be taken for abusive language.")

────────────────────────
STEP 5:  FEW-SHOT TRAINING EXAMPLES (LEARN FROM THESE)
────────────────────────
Input: "Attiwad madhe khup chori hot aahe" (Marathi)
Output JSON:
{{
  "status": "COMPLETED",
  "political_response": "जी, अट्टीवाड मधील चोरीची तक्रार मी नोंदवून घेतली आहे. लवकरच कारवाई केली जाईल.",
  "grievance_data": {{
      "category": "Other",
      "location_native": "अट्टीवाड",
      "location_english": "Attiwad",
      "assembly_constituency": "Belgaum Rural",
      "missing_info": null
  }}
}}

Input: "ನನ್ನ ರಸ್ತೆ ತುಂಬಾ ಕೆಟ್ಟದಾಗಿದೆ" (Kannada - "My road is very bad")
Output JSON:
{{
  "status": "INCOMPLETE", 
  "political_response": "ನಮಸ್ತೆ, ರಸ್ತೆ ಸಮಸ್ಯೆಯನ್ನು ಸರಿಪಡಿಸೋಣ. ಆದರೆ ದಯವಿಟ್ಟು ನಿಮ್ಮ ಬಡಾವಣೆ ಅಥವಾ ಏರಿಯಾ ಯಾವುದು ಎಂದು ತಿಳಿಸಿ?",
  "grievance_data": {{
      "category": "Roads",
      "location_native": null,
      "location_english": null,
      "assembly_constituency": null,
      "missing_info": ["location"]
  }}
}}

Input: "Khasa Bag mein kachra uthaya nahi" (Hinglish)
Output JSON:
{{
  "status": "COMPLETED",
  "political_response": "Ji, Khasa Bag mein kachra uthane ki shikayat note kar li hai.",
  "grievance_data": {{
      "category": "Waste",
      "location_native": "Khasa Bag",
      "location_english": "Khasa Bag",
      "assembly_constituency": "Belgaum North",
      "missing_info": null
  }}
}}

Input: "Good Morning sir"
Output JSON:
{{
  "status": "IRRELEVANT",
  "political_response": "Namaste! Good Morning. Please let me know if there are any issues in your area.",
  "grievance_data": {{
      "category": null,
      "location_native": null,
      "location_english": null,
      "assembly_constituency": null,
      "missing_info": null
  }}
}}

Input: "Mujhe sex chahiye"
Output JSON:
{{
  "status": "OFFENSIVE",
  "political_response": "Maryada rakhein. Abhadra bhasha ka prayog karne par aap par kaanooni karyawahi ho sakti hai.",
  "grievance_data": {{ "category": null, "location_native": null, "location_english": null, "assembly_constituency": null, "missing_info": null }}
}}

──────────────────────
STEP 6:  YOUR TASK
────────────────────────
Analyze the USER MESSAGE below and output valid JSON.

USER MESSAGE: "{user_message}"

────────────────────────
JURISDICTION CONTEXT (LOOKUP TABLE)
────────────────────────
{JURISDICTION_CONTEXT}
"""

# ==========================================
# 🌍 2. SMART GEOGRAPHY RESOLVER (MAPS VILLAGES TO AC)
# ==========================================
# ==========================================
# 🌍 2. SMART GEOGRAPHY RESOLVER (THE FIX)
# ==========================================
def get_jurisdiction_context():
    mapping = []
    # 1. Get the root folder of your project
    cwd = os.getcwd()
    print(f"DEBUG: Starting Deep Scan from: {cwd}")
    
    # 2. Walk through every single folder to find JSONs
    for root, dirs, files in os.walk(cwd):
        for filename in files:
            if filename.endswith(".json"):
                # Skip system folders to be safe
                if "node_modules" in root or "venv" in root or "git" in root:
                    continue
                
                file_path = os.path.join(root, filename)
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        data = json.load(f)
                        
                        # 3. Check if it's a constituency file (has 'locality')
                        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                            if "locality" in data[0] or "station_number" in data[0]:
                                
                                # Extract Name (e.g., "Belgaum South")
                                constituency_name = filename.replace(".json", "").replace("_", " ").title()
                                
                                # Extract Areas
                                areas = []
                                for item in data:
                                    if isinstance(item, dict):
                                        # Prioritize 'locality', fallback to 'building_name'
                                        loc = item.get("locality", "")
                                        if loc and len(loc) > 2:
                                            areas.append(loc.strip())
                                        elif (bldg := item.get("building_name")):
                                            areas.append(bldg.strip())

                                # 4. Add to the Map (Limit 200 areas)
                                areas = list(set(areas))
                                if areas:
                                    mapping.append(f"📍 {constituency_name} includes: {', '.join(areas[:200])}")
                                    print(f"DEBUG: Loaded {constituency_name} with {len(areas)} areas.")

                except Exception:
                    continue

    if not mapping:
        print("CRITICAL: No geography files found.")
        return "No Jurisdiction Data Available."

    # Return the full map string
    return "\n".join(mapping)
# Load Logic
REAL_JURISDICTION_CONTEXT = get_jurisdiction_context()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# ==========================================
# 🧠 AI EXECUTION
# ==========================================
def ask_groq_agent(user_message):
    if not GROQ_API_KEY:
        return {"status": "ERROR", "political_response": "⚠️ Server Error: AI Key Missing."}

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    # Inject real geography into your STRICT prompt
    formatted_prompt = SYSTEM_PROMPT.format(
        user_message=user_message,
        JURISDICTION_CONTEXT=REAL_JURISDICTION_CONTEXT
    )

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "user", "content": formatted_prompt}
        ],
        "temperature": 0.1, 
        "response_format": {"type": "json_object"}
    }

    try:
        print(f"🤖 AI Request: Processing '{user_message}'...")
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code == 200:
            content = response.json()["choices"][0]["message"]["content"]
            try:
                # Force Parse JSON
                return json.loads(content)
            except json.JSONDecodeError:
                print("❌ AI returned invalid JSON:", content)
                return {"status": "ERROR", "political_response": "Internal AI Error."}
        else:
            return {"status": "ERROR", "political_response": "Server busy."}

    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return {"status": "ERROR", "political_response": "Connection Error."}
