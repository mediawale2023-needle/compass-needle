import os
import json
from pathlib import Path

# 1. Define Path (Using the path successfully found by your last run)
TARGET_DIR = Path("/Users/sanketjadhav/Desktop/compass-needle/data/geography")

print(f"🩻 DEEP X-RAY DIAGNOSTIC\nScanning: {TARGET_DIR}")

if not TARGET_DIR.exists():
    print("❌ CRITICAL: Data folder disappeared!")
    exit()

found_files = list(TARGET_DIR.rglob("*.json"))
print(f"✅ Found {len(found_files)} files. Scanning all of them...\n")

total_matches = 0

# 2. Loop through EVERY file
for file_path in found_files:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        print(f"📂 Checking {file_path.parent.name} / {file_path.name}...")
        
        # Search inside this file
        file_matches = 0
        for item in data:
            loc = str(item.get("locality", "")).lower()
            if "tilakwadi" in loc:
                print(f"   🎯 FOUND MATCH: '{item.get('locality')}'")
                print(f"      (Saved as: {json.dumps(item)})")
                file_matches += 1
        
        if file_matches == 0:
            print("   (No match)")
        else:
            total_matches += file_matches
            
    except Exception as e:
        print(f"   ❌ Error reading file: {e}")

print("-" * 40)
if total_matches == 0:
    print("❌ CONCLUSION: 'Tilakwadi' does not exist in ANY file.")
    print("👉 FIX: Go to Admin Dashboard -> Geography Upload -> Re-upload the PDF for Belgaum South.")
else:
    print(f"✅ CONCLUSION: Found {total_matches} matches.")
    print("👉 FIX: If you see the match above, the Backend just needs a Restart.")