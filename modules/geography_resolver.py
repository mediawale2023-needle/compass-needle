"""
Geography Resolver (MULTI-TENANT)
1. Checks Overrides from tenant_overrides.json (per tenant_id).
2. Exact Substring Match against geography index.
3. Spaceless Match (Fixes "Shahunagar" vs "Shahu Nagar").
4. Fuzzy Typos Match (Fixes "Tilkwadi" vs "Tilakwadi").
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import re
import string
from difflib import SequenceMatcher

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
# TENANT-AWARE OVERRIDES (loaded from tenant_overrides.json)
# ==========================================

def _load_tenant_overrides(tenant_id):
    """Load geo_overrides for a specific tenant from tenant_overrides.json."""
    override_paths = [
        PROJECT_ROOT / "tenant_overrides.json",
        Path("tenant_overrides.json").resolve(),
        Path("/app/tenant_overrides.json"),
    ]
    for op in override_paths:
        if op.exists():
            try:
                with open(op, "r", encoding="utf-8") as f:
                    data = json.load(f)
                geo_overrides = data.get("geo_overrides", {}).get(str(tenant_id), {})
                return geo_overrides
            except Exception:
                pass
    return {}


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
    """Get significant words >= 4 chars, excluding generic location/complaint terms."""
    words = normalize(text).split()
    stopwords = {
        # English generic
        "road", "street", "near", "opp", "opposite", "behind", "front", 
        "main", "cross", "lane", "area", "colony", "city", 
        "town", "village", "taluk", "district", "state", "ward", "zone",
        "problem", "issue", "water", "logging", "broken", "bad",
        "east", "west", "north", "south", "station", "nagar", "chowk",
        "market", "park", "garden", "society", "sector", "block", "camp",
        "gate", "bridge", "school", "college", "hospital", "temple",
        "masjid", "church", "railway", "bus", "stop", "circle", "square",
        # Indian location generic
        "bazar", "bazaar", "peth", "pet", "galli", "gali", "wadi", "wada",
        "gaon", "goan", "pada", "pura", "pur", "abad", "ghat", "khurd",
        "budruk", "tarf", "road", "marg", "path", "math", "devi",
        "maharaj", "govt", "government", "primary", "high", "english",
        "medium", "kannada", "marathi", "urdu", "hindi",
        "building", "room", "hall", "office", "depot", "vaccine",
        "number", "polling", "booth", "average", "voters",
        "total", "part", "page", "list",
        # Complaint language (Hindi/Marathi/Kannada/English)
        "classroom", "toilet", "rasta", "kharab", "nahi", "aahe",
        "milto", "madhe", "teacher", "tutla", "tutli", "band",
        "paani", "supply", "drain", "khade", "footpath", "light",
        "phone", "call", "please", "help", "urgent", "request",
        "complaint", "regarding", "about", "from", "this", "that",
        "very", "much", "also", "here", "there", "where", "when",
    }
    return {w for w in words if len(w) >= 4 and w not in stopwords}

def similarity_score(a: str, b: str) -> float:
    """Returns a score between 0 and 100 indicating how similar two strings are."""
    return SequenceMatcher(None, a, b).ratio() * 100

# --- LOADER ---
def load_geography_index() -> bool:
    global _geography_index
    if not GEOGRAPHY_BASE_PATH: return False

    print(f"INDEXING GEOGRAPHY FROM: {GEOGRAPHY_BASE_PATH}")
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
                raw_loc = s.get("locality", "").replace("\n", " ").strip()
                raw_bldg = s.get("building_name", "").replace("\n", " ").strip()
                station = str(s.get("station_number", "")).strip()
                
                # Pre-calculate normalized versions for speed
                norm_loc = normalize(raw_loc)
                norm_bldg = normalize(raw_bldg)
                
                keywords = get_keywords(raw_loc) | get_keywords(raw_bldg)
                
                if keywords or station:
                    _geography_index["assemblies"][assembly]["entries"].append({
                        "orig_name": raw_loc,
                        "norm_name": norm_loc,
                        "spaceless_name": norm_loc.replace(" ", ""),
                        "station": station,
                        "keywords": keywords
                    })
            files_loaded += 1
            print(f"   Indexed {assembly}: {len(stations)} locations")

    _geography_index["loaded"] = True
    return files_loaded > 0

# --- RESOLVER ---
def resolve_location(text: str, scope_parliamentary: Optional[str] = None, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    if not text: return {"location_resolved": False}
    if not _geography_index["loaded"]: load_geography_index()

    clean_text = normalize(text)
    spaceless_text = clean_text.replace(" ", "")
    user_keywords = get_keywords(text)
    
    print(f"RESOLVING: '{clean_text}' (tenant={tenant_id})")

    # 1. TENANT-SPECIFIC OVERRIDES (from tenant_overrides.json)
    if tenant_id is not None:
        tenant_overrides = _load_tenant_overrides(tenant_id)
        for k, v in tenant_overrides.items():
            if k.lower() in clean_text:
                print(f"   OVERRIDE (tenant {tenant_id}): {k} -> {v}")
                return {"location_resolved": True, "assembly_constituency": v, "matched_value": k.title(), "confidence": "god_mode"}

    candidates = []

    for assembly, data in _geography_index["assemblies"].items():
        if scope_parliamentary and normalize(data["parl"]) != normalize(scope_parliamentary): continue

        for entry in data["entries"]:
            score = 0
            match_type = "none"

            # A. EXACT SUBSTRING (Highest Quality)
            if entry["norm_name"] and entry["norm_name"] in clean_text:
                score = 100 - len(entry["norm_name"]) + 50
                match_type = "exact"
            
            # B. SPACELESS MATCH (Fixes "Shahunagar")
            elif entry["spaceless_name"] and len(entry["spaceless_name"]) > 4 and entry["spaceless_name"] in spaceless_text:
                score = 90
                match_type = "spaceless"

            # C. FUZZY KEYWORD MATCH (Fixes Typos — strict threshold, long words only)
            else:
                for uk in user_keywords:
                    if len(uk) < 5: continue  # Skip short words for fuzzy
                    for dk in entry["keywords"]:
                        if len(dk) < 5: continue
                        sim = similarity_score(uk, dk)
                        if sim > 92:
                            score = sim
                            match_type = f"fuzzy ({uk}~{dk})"
                            break

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

    # D. TIE BREAKER — no hardcoded priority, just use score
    candidates.sort(key=lambda x: x["score"], reverse=True)
    winner = candidates[0]

    print(f"   WINNER: {winner['name']} ({winner['assembly']}) - Score: {winner['score']:.1f} [{winner['type']}]")
    
    return {
        "location_resolved": True,
        "assembly_constituency": winner["assembly"],
        "parliamentary_constituency": winner["parl"],
        "matched_value": winner["name"],
        "confidence": "high"
    }

# --- WRAPPERS ---
def _get_tenant_constituency(tenant_id):
    """Look up the parliamentary constituency for a given tenant_id."""
    if not tenant_id:
        return None
    try:
        # Try tenant_overrides.json first
        override_paths = [
            PROJECT_ROOT / "tenant_overrides.json",
            Path("tenant_overrides.json").resolve(),
        ]
        for op in override_paths:
            if op.exists():
                with open(op, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Check if constituency is stored in overrides
                tenant_data = data.get("tenants", {}).get(str(tenant_id), {})
                if tenant_data.get("constituency"):
                    return tenant_data["constituency"]
    except Exception:
        pass
    
    # Fallback: look up from DB
    try:
        from db import SessionLocal, Tenant
        db = SessionLocal()
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if tenant and tenant.constituency:
            db.close()
            return tenant.constituency
        db.close()
    except Exception:
        pass
    
    return None

def enrich_grievance_with_location(grievance: Dict, tenant_id: Optional[int] = None) -> Dict:
    text = grievance.get("raw_message") or ""
    # Auto-scope by tenant's parliamentary constituency
    scope = _get_tenant_constituency(tenant_id) if tenant_id else None
    logger.info(f"Enriching grievance for tenant={tenant_id}, scope={scope}")
    res = resolve_location(text, scope_parliamentary=scope, tenant_id=tenant_id)
    grievance["geography"] = res
    return grievance

def get_index_stats() -> Dict[str, int]:
    return {"loaded": _geography_index["loaded"], "assemblies": len(_geography_index["assemblies"])}

def reload_index():
    _geography_index["loaded"] = False
    return load_geography_index()

# ==========================================
# AUTO-GENERATE OVERRIDES FROM GEOGRAPHY DATA
# ==========================================
def auto_generate_overrides():
    """
    Scans all geography JSON files, extracts unique locality→assembly mappings,
    and writes them to tenant_overrides.json keyed by tenant_id.
    
    - Looks up tenant_id by matching constituency name to geography folder name
    - Preserves manually-added overrides (manual entries take priority)
    - Cleans newlines and deduplicates
    """
    if not GEOGRAPHY_BASE_PATH or not GEOGRAPHY_BASE_PATH.exists():
        logger.warning("Geography base path not found, cannot auto-generate overrides")
        return {"error": "Geography path not found"}
    
    # Load existing overrides to preserve manual entries
    overrides_path = PROJECT_ROOT / "tenant_overrides.json"
    existing_data = {}
    if overrides_path.exists():
        try:
            with open(overrides_path, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        except Exception:
            existing_data = {}
    
    # Preserve non-geo_overrides keys (like WhatsApp mappings)
    preserved_keys = {k: v for k, v in existing_data.items() if k != "geo_overrides"}
    existing_geo = existing_data.get("geo_overrides", {})
    
    # Look up tenant_ids by constituency name from DB
    constituency_to_tenant = {}
    try:
        from db import SessionLocal, Tenant
        db = SessionLocal()
        tenants = db.query(Tenant).all()
        for t in tenants:
            if t.constituency and t.constituency != "System":
                constituency_to_tenant[t.constituency] = t.id
        db.close()
    except Exception as e:
        logger.warning(f"Could not load tenants from DB: {e}")
    
    # Scan geography folders
    new_geo_overrides = {}
    stats = {}
    
    for parl_dir in sorted(GEOGRAPHY_BASE_PATH.iterdir()):
        if not parl_dir.is_dir():
            continue
        
        parl_name = parl_dir.name  # e.g., "Belagavi", "Kalyan Dombivli"
        tenant_id = constituency_to_tenant.get(parl_name)
        
        if not tenant_id:
            logger.info(f"No tenant found for constituency '{parl_name}', skipping override generation")
            continue
        
        tid_str = str(tenant_id)
        overrides_map = {}
        
        for json_file in sorted(parl_dir.glob("*.json")):
            assembly_name = json_file.stem  # e.g., "Belgaum Uttar"
            
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    stations = json.load(f)
            except Exception:
                continue
            
            if not isinstance(stations, list):
                continue
            
            for station in stations:
                # Extract locality (primary) and building parts
                locality = station.get("locality", "").replace("\n", " ").strip()
                
                if not locality or len(locality) < 3:
                    continue
                
                # Normalize the key (lowercase, clean)
                key = locality.lower().strip()
                key = re.sub(r'\s+', ' ', key)
                
                # Skip if too generic (single common word)
                if key in {"east", "west", "north", "south", "ward", "room", "hall"}:
                    continue
                
                # Only add if not already mapped (first occurrence wins)
                if key not in overrides_map:
                    overrides_map[key] = assembly_name
        
        # Merge: existing manual overrides take priority over auto-generated
        existing_tenant_overrides = existing_geo.get(tid_str, {})
        merged = {**overrides_map, **existing_tenant_overrides}  # manual wins
        
        new_geo_overrides[tid_str] = merged
        stats[parl_name] = {
            "tenant_id": tenant_id,
            "auto_generated": len(overrides_map),
            "manual_preserved": len(existing_tenant_overrides),
            "total": len(merged),
        }
    
    # Write the final overrides file
    final_data = {**preserved_keys, "geo_overrides": new_geo_overrides}
    
    try:
        with open(overrides_path, "w", encoding="utf-8") as f:
            json.dump(final_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Auto-generated overrides written to {overrides_path}")
    except Exception as e:
        logger.error(f"Failed to write overrides: {e}")
        return {"error": str(e)}
    
    return {"success": True, "stats": stats}