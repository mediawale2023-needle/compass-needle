cat > sansadx_backend/ai_engine.py <<EOF
import os
import requests
import json
import glob
from .prompt import SYSTEM_PROMPT

# ==========================================
# 🌍 GEOGRAPHY RESOLVER (DYNAMIC FOLDER SCAN)
# ==========================================
def get_jurisdiction_context():
    """
    Scans 'data/geography/' for any JSON files generated from Polling Station PDFs.
    Combines all area names into a single context string for the AI.
    """
    geography_folder = "data/geography"
    
    # Handle different running environments (local vs cloud)
    if not os.path.exists(geography_folder):
        # Try one level up if running from backend folder
        geography_folder = "../data/geography"
        
    if not os.path.exists(geography_folder):
        print(f"⚠️ Geography Warning: Folder '{geography_folder}' not found.")
        return "Unknown Areas"

    known_areas = set()

    try:
        # Find all JSON files in the folder
        json_files = glob.glob(os.path.join(geography_folder, "*.json"))
        
        if not json_files:
            print("⚠️ Geography Warning: No JSON files found in data/geography/")
            return "Unknown Areas"

        print(f"🌍 Geography Loader: Found {len(json_files)} maps.")

        for file_path in json_files:
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)
                    
                    # Logic: Extract keys or specific 'name' fields depending on structure
                    # Assuming a flat list of names OR a dict where keys are Ward/Area names
                    if isinstance(data, dict):
                        known_areas.update(data.keys())
                    elif isinstance(data, list):
                        # If list of strings, add them. If list of dicts, look for 'name'
                        for item in data:
                            if isinstance(item, str):
                                known_areas.add(item)
                            elif isinstance(item, dict) and "name" in item:
                                known_areas.add(item["name"])
                                
            except Exception as e:
                print(f"⚠️ Error reading {file_path}: {e}")

        # Convert set to sorted list
        area_list = sorted(list(known_areas))
        print(f"🌍 Context Loaded: {len(area_list)} unique locations found.")
        
        # Return comma-separated string (limit to 300 items to fit AI context)
        return ", ".join(area_list[:300])

    except Exception as e:
        print(f"⚠️ Geography Fatal Error: {e}")
        return "Unknown Areas"

# Load this ONCE when server starts
REAL_JURISDICTION_CONTEXT = get_jurisdiction_context()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

def ask_groq_agent(user_message):
    if not GROQ_API_KEY:
        return {"status": "ERROR", "political_response": "⚠️ Server Error: AI Key Missing."}

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    # 💉 INJECT REAL GEOGRAPHY INTO PROMPT
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
                return {"status": "ERROR", "political_response": "Internal AI Error."}
        else:
            return {"status": "ERROR", "political_response": "Server busy."}

    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return {"status": "ERROR", "political_response": "Connection Error."}
EOF