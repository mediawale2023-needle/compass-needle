import os
import json
import glob

# CONFIGURATION
# ---------------------------------------------------------
# We look inside this folder AND all its sub-folders
SEARCH_ROOT = "data/geography"  
TENANT_ID = "1"
# ---------------------------------------------------------

def generate_rulebook():
    print(f"🔍 Scanning recursively starting from: {SEARCH_ROOT}...")
    
    rulebook = {}
    
    # 1. Find ALL .json files recursively (using ** pattern)
    # This finds data/geography/belagavi/north.json, data/geography/pune/south.json, etc.
    search_pattern = os.path.join(SEARCH_ROOT, "**", "*.json")
    files = glob.glob(search_pattern, recursive=True)
    
    # Safety: Exclude non-geography files if any exist
    ignored_files = ["package.json", "tsconfig.json", "tenant_overrides.json"]
    geo_files = [f for f in files if os.path.basename(f) not in ignored_files]
    
    print(f"✅ Found {len(geo_files)} geography files.")

    # 2. Process each file
    total_locations = 0
    
    for file_path in geo_files:
        try:
            # Extract Constituency Name from Filename
            # e.g., "belgaum_rural.json" -> "Belgaum Rural"
            filename = os.path.basename(file_path)
            constituency_name = filename.replace(".json", "").replace("_", " ").title()
            
            print(f"   📂 Processing: {constituency_name}...")
            count = 0
            
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
                # Verify standard format (List of objects)
                if isinstance(data, list):
                    for entry in data:
                        # Extract Locality (and normalize text)
                        loc = str(entry.get("locality", "")).strip().lower()
                        
                        # Rule: Add to book if name is valid (longer than 2 chars)
                        if loc and len(loc) > 2:
                            rulebook[loc] = constituency_name
                            count += 1
                            
            total_locations += count
            print(f"      -> Added {count} locations.")

        except Exception as e:
            print(f"❌ Error reading {file_path}: {e}")

    # 3. Save to tenant_overrides.json in the MAIN folder
    final_output = {
        TENANT_ID: rulebook
    }
    
    with open("tenant_overrides.json", "w", encoding="utf-8") as f:
        json.dump(final_output, f, indent=2, ensure_ascii=False)
        
    print("---------------------------------------------------------")
    print(f"✅ SUCCESS! Generated {total_locations} Master Rules.")
    print(f"📁 Saved to: tenant_overrides.json")

if __name__ == "__main__":
    generate_rulebook()