import json
import os

# --- PATH SETUP ---
# This ensures we find the file even if running from a different folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TAXONOMY_FILE = os.path.join(BASE_DIR, "taxonomy.json")

# --- LOAD DATABASE ---
def load_taxonomy():
    """
    Loads the categorization rules from the JSON file.
    """
    if not os.path.exists(TAXONOMY_FILE):
        print(f"⚠️ WARNING: Taxonomy file not found at {TAXONOMY_FILE}")
        return []
        
    try:
        with open(TAXONOMY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            print(f"✅ Loaded {len(data)} taxonomy rules.")
            return data
    except Exception as e:
        print(f"❌ Error loading taxonomy: {e}")
        return []

# Load once on startup
TAXONOMY_DB = load_taxonomy()

# --- CLASSIFICATION LOGIC ---
def get_classification(text: str):
    """
    Scans the text against the JSON taxonomy rules.
    Returns the best match or a default 'Unknown'.
    """
    text_lower = text.lower()
    
    # 1. Exact Keyword Match
    # We iterate through the JSON list
    for rule in TAXONOMY_DB:
        for keyword in rule["keywords"]:
            if keyword in text_lower:
                # Found a match! Return the full rule object
                return {
                    "category": rule["category"],
                    "authority": rule["authority"],
                    "level": rule["level"],
                    "mp_role": rule["mp_role"],
                    "political_response": rule.get("political_response", "We will look into this."),
                    "match_type": "Deterministic"
                }
    
    # 2. Default Fallback (If no keywords match)
    return {
        "category": "General Grievance",
        "authority": "District Collector's Office",
        "level": "Admin",
        "mp_role": "Coordinate",
        "political_response": "Your issue has been noted and will be forwarded to the relevant department.",
        "match_type": "Fallback"
    }