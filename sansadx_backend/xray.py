import os
import json
from pathlib import Path

# 1. Find the Data Folder
CURRENT_DIR = Path(__file__).parent
DATA_DIR_1 = CURRENT_DIR / "data" / "geography"
DATA_DIR_2 = CURRENT_DIR.parent / "data" / "geography"

TARGET_DIR = DATA_DIR_1 if DATA_DIR_1.exists() else DATA_DIR_2

print(f"🩻 X-RAY DIAGNOSTIC\nLooking for data in: {TARGET_DIR}")

if not TARGET_DIR.exists():
    print("❌ CRITICAL: Data folder not found anywhere!")
    exit()

# 2. Open Belgaum South (or any file found)
found_files = list(TARGET_DIR.rglob("*.json"))
if not found_files:
    print("❌ CRITICAL: No JSON files found inside the folder!")
    exit()

print(f"✅ Found {len(found_files)} files.")

# 3. Read the first file and print RAW keys
target_file = found_files[0]
print(f"\n📄 Inspecting: {target_file.name}")

try:
    with open(target_file, "r") as f:
        data = json.load(f)
        
    print(f"📊 Total Stations: {len(data)}")
    print("\n🔍 FIRST 10 RAW LOCALITY NAMES (Exactly as saved):")
    print("-" * 40)
    for i, item in enumerate(data[:10]):
        loc = item.get("locality", "MISSING")
        print(f"{i+1}. '{loc}'")
    print("-" * 40)
    
    # 4. Check for 'Tilakwadi' specifically
    print("\n🕵️‍♀️ SEARCHING FOR 'Tilakwadi' in this file...")
    found = False
    for item in data:
        loc = item.get("locality", "").lower()
        if "tilakwadi" in loc:
            print(f"   FOUND: '{item.get('locality')}'")
            found = True
    
    if not found:
        print("❌ 'Tilakwadi' is NOT in this file. Please check other files or re-upload PDF.")

except Exception as e:
    print(f"❌ Error reading file: {e}")