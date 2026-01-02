import os
import json
from geography_resolver import load_geography_index, resolve_location, _geography_index

# 1. Force Load
print("\n🔄 Loading Geography Index...")
load_geography_index()

# 2. Inspect the "Brain"
print("\n🧠 --- INDEX INSPECTION ---")
if not _geography_index["assemblies"]:
    print("❌ ERROR: The Index is EMPTY. No files were found in 'data/geography/'.")
else:
    for assembly, data in _geography_index["assemblies"].items():
        print(f"✅ Assembly: '{assembly}'")
        print(f"   - Localities Indexed: {len(data['localities'])}")
        
        # Print first 5 localities to check formatting
        sample = list(data['localities'].keys())[:5]
        print(f"   - Sample Keys: {sample}")
        
        # Check specifically for Tilakwadi
        if "tilakwadi" in data['localities']:
            print("   🎯 FOUND 'tilakwadi' in this assembly!")
        else:
            # Check partial matches
            matches = [k for k in data['localities'].keys() if "tilakwadi" in k]
            if matches:
                print(f"   ⚠️  Found partial matches for 'tilakwadi': {matches}")
            else:
                print("   ❌ 'tilakwadi' is NOT in this assembly.")

# 3. Test Resolution
print("\n🕵️‍♀️ --- RESOLUTION TEST ---")
test_inputs = [
    "Water logging in Tilakwadi",
    "Tilakwadi road blocked",
    "Issue at station 5",
    "Tilakwadi"
]

for text in test_inputs:
    result = resolve_location(text)
    status = "✅ MATCH" if result.get("location_resolved") else "❌ FAIL"
    print(f"Input: '{text}' -> {status}")
    if result.get("location_resolved"):
        print(f"   📍 Mapped to: {result.get('matched_value')} ({result.get('assembly_constituency')})")