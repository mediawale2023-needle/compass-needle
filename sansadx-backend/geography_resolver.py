"""
Geography Resolver Module

Deterministic location resolver for grievances.
NO AI, NO fuzzy matching - exact matches only.

Resolution order:
1. Exact match on locality
2. Exact match on village/area name
3. Exact match on polling station number
4. Exact match on building name
5. Admin-defined alias map
"""

import json
import os
import logging
from pathlib import Path
from typing import Optional, Dict, List, Any
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configuration ---
GEOGRAPHY_BASE_PATH = Path(__file__).parent.parent / "data" / "geography"
ALIAS_MAP_PATH = Path(__file__).parent.parent / "data" / "location_aliases.json"

# --- Global Index (loaded at startup) ---
_geography_index = {
    "localities": {},      # locality -> {assembly, parliamentary, station}
    "station_numbers": {}, # station_num -> {assembly, parliamentary, locality}
    "building_names": {},  # building -> {assembly, parliamentary, locality}
    "aliases": {},         # alias -> canonical location
    "loaded": False
}


def load_geography_index() -> bool:
    """
    Load all geography JSON files and build lookup indices.
    Called once at startup.
    
    Returns True if any data was loaded.
    """
    global _geography_index
    
    logger.info("Loading geography index...")
    
    _geography_index = {
        "localities": {},
        "station_numbers": {},
        "building_names": {},
        "aliases": {},
        "loaded": False
    }
    
    # Ensure directory exists
    if not GEOGRAPHY_BASE_PATH.exists():
        logger.warning(f"Geography directory not found: {GEOGRAPHY_BASE_PATH}")
        GEOGRAPHY_BASE_PATH.mkdir(parents=True, exist_ok=True)
        return False
    
    files_loaded = 0
    
    # Iterate through parliamentary constituencies
    for parl_dir in GEOGRAPHY_BASE_PATH.iterdir():
        if not parl_dir.is_dir():
            continue
        
        parliamentary = parl_dir.name
        
        # Iterate through assembly constituency JSON files
        for json_file in parl_dir.glob("*.json"):
            assembly = json_file.stem
            
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    stations = json.load(f)
                
                for station in stations:
                    # Index by locality
                    locality = normalize_text(station.get("locality", ""))
                    if locality:
                        _geography_index["localities"][locality] = {
                            "assembly_constituency": assembly,
                            "parliamentary_constituency": parliamentary,
                            "polling_station": station.get("station_number", ""),
                            "building_name": station.get("building_name", "")
                        }
                    
                    # Index by station number
                    station_num = station.get("station_number", "")
                    if station_num:
                        _geography_index["station_numbers"][station_num] = {
                            "assembly_constituency": assembly,
                            "parliamentary_constituency": parliamentary,
                            "locality": station.get("locality", "")
                        }
                    
                    # Index by building name
                    building = normalize_text(station.get("building_name", ""))
                    if building:
                        _geography_index["building_names"][building] = {
                            "assembly_constituency": assembly,
                            "parliamentary_constituency": parliamentary,
                            "locality": station.get("locality", "")
                        }
                
                files_loaded += 1
                logger.info(f"Loaded: {parliamentary}/{assembly} ({len(stations)} stations)")
                
            except Exception as e:
                logger.error(f"Error loading {json_file}: {e}")
    
    # Load alias map if exists
    if ALIAS_MAP_PATH.exists():
        try:
            with open(ALIAS_MAP_PATH, 'r', encoding='utf-8') as f:
                _geography_index["aliases"] = json.load(f)
            logger.info(f"Loaded {len(_geography_index['aliases'])} location aliases")
        except Exception as e:
            logger.error(f"Error loading alias map: {e}")
    
    _geography_index["loaded"] = True
    logger.info(f"Geography index loaded: {files_loaded} files, "
                f"{len(_geography_index['localities'])} localities, "
                f"{len(_geography_index['station_numbers'])} stations")
    
    return files_loaded > 0


def normalize_text(text: str) -> str:
    """
    Normalize text for matching.
    - Lowercase
    - Remove extra whitespace
    - Strip punctuation (but keep core content)
    """
    if not text:
        return ""
    
    # Lowercase and strip
    text = text.lower().strip()
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    
    return text


def resolve_location(text: str, context: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Resolve location from grievance text.
    
    Returns:
        If resolved:
        {
            "location_resolved": true,
            "assembly_constituency": "...",
            "parliamentary_constituency": "...",
            "polling_station": "...",
            "confidence": "exact",
            "match_type": "locality|station_number|building|alias"
        }
        
        If NOT resolved:
        {
            "location_resolved": false
        }
    """
    global _geography_index
    
    # Ensure index is loaded
    if not _geography_index["loaded"]:
        load_geography_index()
    
    if not text:
        return {"location_resolved": False}
    
    normalized_text = normalize_text(text)
    words = normalized_text.split()
    
    # --- RESOLUTION ORDER (Strict, Exact Match Only) ---
    
    # 1. Exact match on locality
    for locality, data in _geography_index["localities"].items():
        if locality and locality in normalized_text:
            return {
                "location_resolved": True,
                "assembly_constituency": data["assembly_constituency"],
                "parliamentary_constituency": data["parliamentary_constituency"],
                "polling_station": data["polling_station"],
                "confidence": "exact",
                "match_type": "locality",
                "matched_value": locality
            }
    
    # 2. Check for station number mentions (e.g., "booth 123", "station 45")
    station_patterns = [
        r'booth\s*(\d+)',
        r'station\s*(\d+)',
        r'polling\s*station\s*(\d+)',
        r'ps\s*(\d+)',
        r'#(\d+)'
    ]
    
    for pattern in station_patterns:
        match = re.search(pattern, normalized_text)
        if match:
            station_num = match.group(1)
            if station_num in _geography_index["station_numbers"]:
                data = _geography_index["station_numbers"][station_num]
                return {
                    "location_resolved": True,
                    "assembly_constituency": data["assembly_constituency"],
                    "parliamentary_constituency": data["parliamentary_constituency"],
                    "polling_station": station_num,
                    "confidence": "exact",
                    "match_type": "station_number",
                    "matched_value": station_num
                }
    
    # 3. Exact match on building name
    for building, data in _geography_index["building_names"].items():
        if building and building in normalized_text:
            return {
                "location_resolved": True,
                "assembly_constituency": data["assembly_constituency"],
                "parliamentary_constituency": data["parliamentary_constituency"],
                "polling_station": "",
                "confidence": "exact",
                "match_type": "building_name",
                "matched_value": building
            }
    
    # 4. Check alias map
    for alias, canonical in _geography_index["aliases"].items():
        if normalize_text(alias) in normalized_text:
            # Re-resolve using canonical name
            result = resolve_location(canonical)
            if result.get("location_resolved"):
                result["match_type"] = "alias"
                result["matched_value"] = alias
                return result
    
    # 5. No match found
    return {"location_resolved": False}


def enrich_grievance_with_location(grievance_data: Dict) -> Dict:
    """
    Enrich grievance data with resolved location.
    
    Args:
        grievance_data: Dict containing at minimum:
            - raw_message or message text
            - location (optional, from AI classification)
    
    Returns:
        grievance_data with added geography fields
    """
    # Get text to analyze
    text = grievance_data.get("raw_message", "") or grievance_data.get("message", "")
    ai_location = grievance_data.get("location", "")
    
    # Try to resolve from AI-extracted location first
    if ai_location:
        result = resolve_location(ai_location)
        if result.get("location_resolved"):
            grievance_data["geography"] = result
            return grievance_data
    
    # Fall back to full message text
    if text:
        result = resolve_location(text)
        if result.get("location_resolved"):
            grievance_data["geography"] = result
            return grievance_data
    
    # No resolution
    grievance_data["geography"] = {"location_resolved": False}
    return grievance_data


def get_index_stats() -> Dict:
    """
    Get statistics about the loaded geography index.
    """
    global _geography_index
    
    return {
        "loaded": _geography_index["loaded"],
        "localities_count": len(_geography_index["localities"]),
        "stations_count": len(_geography_index["station_numbers"]),
        "buildings_count": len(_geography_index["building_names"]),
        "aliases_count": len(_geography_index["aliases"])
    }


def reload_index():
    """
    Force reload of geography index.
    Useful after admin uploads new geography data.
    """
    global _geography_index
    _geography_index["loaded"] = False
    return load_geography_index()


# --- Auto-load on import ---
if __name__ == "__main__":
    # Test the resolver
    load_geography_index()
    
    print("\n=== Geography Resolver Test ===")
    print(f"Stats: {get_index_stats()}")
    
    # Test queries
    test_queries = [
        "Water problem in Muglihal village",
        "Issue at booth 123",
        "Road damage near Government Primary School"
    ]
    
    for query in test_queries:
        result = resolve_location(query)
        print(f"\nQuery: {query}")
        print(f"Result: {json.dumps(result, indent=2)}")
