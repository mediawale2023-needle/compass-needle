"""
Geography Resolver (FINAL - INTELLIGENT MATCHING)
1. Checks Overrides (God Mode).
2. Exact Substring Match.
3. Spaceless Match (Fixes "Shahunagar" vs "Shahu Nagar").
4. Fuzzy Typos Match (Fixes "Tilkwadi" vs "Tilakwadi").
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import re
import string
from difflib import SequenceMatcher # <--- The Magic Library for Typos

# --- CONFIG & PATHS ---
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent

POSSIBLE_PATHS = [
    CURRENT_DIR / "data" / "geography",
    PROJECT_ROOT / "data" / "geography",
    Path("data/geography").resolve()
]

GEOGRAPHY_BASE_PATH = None
for p in POSSIBLE_PATHS:
    if p.exists():
        GEOGRAPHY_BASE_PATH = p
        break

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==========================================
# 🛑 MANUAL OVERRIDES
# ==========================================
MANUAL_OVERRIDES = {
    "tilakwadi": "Belgaum Dakshin",
    "club road": "Belgaum Uttar",
    "camp": "Belgaum Uttar",
    "vadgaon": "Belgaum Dakshin",
    "shahapur": "Belgaum Dakshin",
    "hindalga": "Belgaum Rural"
}

PRIORITY_ASSEMBLIES = ["Belgaum Dakshin", "Belgaum South", "Belgaum Uttar", "Belgaum North"]

_geography_index = {
    "assemblies": {},
    "loaded": False
}

# --- HELPERS ---
def normalize(text: str) -> str:
    """Standardizes text: lower, no punctuation, single spaces."""
    if not text: return ""
    text = text.translate(str.maketrans('', '', string.punctuation))
    return re.sub(r"\s+", " ", text.lower().strip())

def get_keywords(text: str) -> set:
    """Get significant words >= 3 chars."""
    words = normalize(text).split()
    stopwords = {
        "road", "street", "near", "opp", "opposite", "behind", "front", 
        "main", "cross", "lane", "area", "colony", "city", 
        "town", "village", "taluk", "district", "state", "ward", "zone",
        "problem", "issue", "water", "logging", "broken", "bad" # Add grievance words to ignore
    }
    return {w for w in words if len(w) >= 3 and w not in stopwords}

def similarity_score(a: str, b: str) -> float:
    """Returns a score between 0 and 100 indicating how similar two strings are."""
    return SequenceMatcher(None, a, b).ratio() * 100

# --- LOADER ---
def load_geography_index() -> bool:
    global _geography_index
    if not GEOGRAPHY_BASE_PATH: return False

    print(f"📍 INDEXING GEOGRAPHY FROM: {GEOGRAPHY_BASE_PATH}")
    _geography_index["assemblies"] = {}
    files_loaded = 0

    for parl_dir in GEOGRAPHY_BASE_PATH.iterdir():
        if not parl_dir.is_dir(): continue
        parl_name = parl_dir.name

        for json_file in parl_dir.glob("*.json"):
            assembly = json_file.stem
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    stations = json.load(f)
            except: continue

            if assembly not in _geography_index["assemblies"]:
                _geography_index["assemblies"][assembly] = {"parl": parl_name, "entries": []}

            for s in stations:
                raw_loc = s.get("locality", "")
                raw_bldg = s.get("building_name", "")
                station = str(s.get("station_number", "")).strip()
                
                # Pre-calculate normalized versions for speed
                norm_loc = normalize(raw_loc)
                norm_bldg = normalize(raw_bldg)
                
                keywords = get_keywords(raw_loc) | get_keywords(raw_bldg)
                
                if keywords or station:
                    _geography_index["assemblies"][assembly]["entries"].append({
                        "orig_name": raw_loc,
                        "norm_name": norm_loc,
                        "spaceless_name": norm_loc.replace(" ", ""), # For "Shahu Nagar" -> "shahunagar" match
                        "station": station,
                        "keywords": keywords
                    })
            files_loaded += 1
            print(f"   ✔ Indexed {assembly}: {len(stations)} locations")

    _geography_index["loaded"] = True
    return files_loaded > 0

# --- RESOLVER ---
def resolve_location(text: str, scope_parliamentary: Optional[str] = None) -> Dict[str, Any]:
    if not text: return {"location_resolved": False}
    if not _geography_index["loaded"]: load_geography_index()

    clean_text = normalize(text)
    spaceless_text = clean_text.replace(" ", "") # "shahunagarroad"
    user_keywords = get_keywords(text)
    
    print(f"🔎 RESOLVING: '{clean_text}'")

    # 1. OVERRIDES
    for k, v in MANUAL_OVERRIDES.items():
        if k in clean_text:
            print(f"   🚨 OVERRIDE: {k} -> {v}")
            return {"location_resolved": True, "assembly_constituency": v, "matched_value": k.title(), "confidence": "god_mode"}

    candidates = []

    for assembly, data in _geography_index["assemblies"].items():
        if scope_parliamentary and normalize(data["parl"]) != normalize(scope_parliamentary): continue

        for entry in data["entries"]:
            score = 0
            match_type = "none"

            # A. EXACT SUBSTRING (Highest Quality)
            # "Tilakwadi" in "Tilakwadi Road"
            if entry["norm_name"] and entry["norm_name"] in clean_text:
                score = 100 - len(entry["norm_name"]) + 50
                match_type = "exact"
            
            # B. SPACELESS MATCH (Fixes "Shahunagar")
            # "shahunagar" in "shahunagarbroken"
            elif entry["spaceless_name"] and len(entry["spaceless_name"]) > 4 and entry["spaceless_name"] in spaceless_text:
                score = 90
                match_type = "spaceless"

            # C. FUZZY KEYWORD MATCH (Fixes Typos)
            else:
                for uk in user_keywords:
                    for dk in entry["keywords"]:
                        # Check similarity (e.g. "Shahunagar" vs "Shahu")
                        sim = similarity_score(uk, dk)
                        if sim > 85: # 85% Match required (allows 1-2 letter mistakes)
                            score = sim
                            match_type = f"fuzzy ({uk}~{dk})"
                            break # Found a good keyword match, stop checking this entry
            
            if score > 60:
                candidates.append({
                    "assembly": assembly,
                    "parl": data["parl"],
                    "name": entry["orig_name"],
                    "score": score,
                    "type": match_type
                })

    if not candidates:
        return {"location_resolved": False}

    # D. TIE BREAKER (City Priority)
    for c in candidates:
        if c["assembly"] in PRIORITY_ASSEMBLIES:
            c["score"] += 15

    candidates.sort(key=lambda x: x["score"], reverse=True)
    winner = candidates[0]

    print(f"   🏆 WINNER: {winner['name']} ({winner['assembly']}) - Score: {winner['score']:.1f} [{winner['type']}]")
    
    return {
        "location_resolved": True,
        "assembly_constituency": winner["assembly"],
        "parliamentary_constituency": winner["parl"],
        "matched_value": winner["name"],
        "confidence": "high"
    }

# --- WRAPPERS ---
def enrich_grievance_with_location(grievance: Dict) -> Dict:
    text = grievance.get("raw_message") or ""
    res = resolve_location(text, scope_parliamentary=None)
    grievance["geography"] = res
    return grievance

def get_index_stats() -> Dict[str, int]:
    return {"loaded": _geography_index["loaded"], "assemblies": len(_geography_index["assemblies"])}

def reload_index():
    _geography_index["loaded"] = False
    return load_geography_index()