import os
import json
import glob

# CONFIGURATION
# ---------------------------------------------------------
# Where are your geography JSON files located?
DATA_FOLDER = "data"   # Change this if they are in the root folder (use ".")
TENANT_ID = "1"        # The ID to assign these rules to
# ---------------------------------------------------------

def generate_rulebook():
    print(f"🔍 Scanning folder: {DATA_FOLDER}...")
    
    # 1. Initialize the Rulebook
    rulebook = {}
    
    # 2. Find all JSON files
    # This looks for files like "belgaum_rural.json", "ramdurg.json"
    search_path = os.path.join(DATA_FOLDER, "*.json")
    files = glob.glob(search_path)
    
    if not files:
        # Fallback: Try looking in the current directory if 'data' is empty
        print(f"⚠️ No files found in '{DATA_FOLDER}'. Checking root directory...")
        files = glob.glob("*.json")
        # Exclude system files
        files = [f for f in files if f not in ["package.json", "tsconfig.json", "tenant_overrides.json"]]

    print(f"✅ Found {len(files)} constituency files.")

    # 3. Process each file
    for file_path in files:
        try:
            # Extract Constituency Name from Filename
            # e.g., "data/belgaum_rural.json" -> "Belgaum Rural"
            filename = os.path.basename(file_path)
            constituency_name = filename.replace(".json", "").replace("_", " ").title()
            
            print(f"   Processing: {constituency_name}...")
            
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
                # Check if it's the right format (List of objects)
                if isinstance(data, list):
                    for entry in data:
                        # We look for "locality" or "building_name"
                        # We normalize it: lowercase + trimmed
                        
                        loc = entry.get("locality", "").strip()
                        if loc:
                            rulebook[loc.lower()] = constituency_name
                            
                        # Optional: extracting from building name can be noisy, 
                        # but helpful if locality is empty.
                        # building = entry.get("building_name", "").split("\n")[0].strip()
                        # if building:
                        #    rulebook[building.lower()] = constituency_name

        except Exception as e:
            print(f"❌ Error reading {file_path}: {e}")

    # 4. Save to tenant_overrides.json
    final_output = {
        TENANT_ID: rulebook
    }
    
    with open("tenant_overrides.json", "w", encoding="utf-8") as f:
        json.dump(final_output, f, indent=2, ensure_ascii=False)
        
    print("---------------------------------------------------------")
    print(f"✅ SUCCESS! Generated {len(rulebook)} location rules.")
    print(f"📁 Saved to: tenant_overrides.json")

if __name__ == "__main__":
    generate_rulebook()