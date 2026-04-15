import json
import os
import re

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

# --- KEYWORD MATCHING ---
def _keyword_matches(keyword: str, text_lower: str) -> bool:
    """
    Order-independent keyword matching with word-boundary protection.
    - Single word  → whole-word match (prevents "kv" matching "backup", "nali"
                     matching "channel"). Uses regex \b which is Unicode-aware
                     in Python 3, so Devanagari/Tamil/etc. words work correctly.
    - Multi-word   → every word in the keyword must appear as a whole word
                     somewhere in the text (any order). This handles
                     "डॉक्टर अस्पताल में नहीं" matching
                     "अस्पताल में डॉक्टर नहीं है".
    """
    parts = keyword.lower().split()
    if len(parts) == 1:
        return bool(re.search(r'\b' + re.escape(parts[0]) + r'\b', text_lower))
    return all(
        bool(re.search(r'\b' + re.escape(p) + r'\b', text_lower))
        for p in parts
    )


# --- CLASSIFICATION LOGIC ---
def get_classification(text: str):
    """
    Scans the text against the JSON taxonomy rules.
    Returns the best match or a default fallback.
    """
    text_lower = text.lower()

    for rule in TAXONOMY_DB:
        for keyword in rule["keywords"]:
            if _keyword_matches(keyword, text_lower):
                return {
                    "category": rule["category"],
                    "authority": rule["authority"],
                    "level": rule["level"],
                    "mp_role": rule["mp_role"],
                    "political_response": rule.get("political_response", "We will look into this."),
                    "match_type": "Deterministic",
                }

    return {
        "category": "General Grievance",
        "authority": "District Collector's Office",
        "level": "Admin",
        "mp_role": "Coordinate",
        "political_response": "Your issue has been noted and will be forwarded to the relevant department.",
        "match_type": "Fallback",
    }