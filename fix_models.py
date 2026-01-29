import os

# We switch to 2.5 because 1.5 is missing and 2.0 has zero quota
NEW_MODEL = "gemini-2.5-flash"

# 🚨 ADDED settings.py to this list
files_to_fix = [
    "modules/settings.py", 
    "modules/sansadx.py",
    "modules/copilot.py",
    "modules/drafter.py"
]

old_names = [
    "gemini-1.5-flash",
    "gemini-2.0-flash",
    "gemini-flash-latest",
    "gemini-pro"
]

print(f"🔧 Starting repairs... Switching everything to {NEW_MODEL}")

for file_path in files_to_fix:
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        new_content = content
        changes_made = False
        
        # Replace every known old model name
        for old in old_names:
            if old in new_content:
                new_content = new_content.replace(old, NEW_MODEL)
                changes_made = True
                print(f"   Found '{old}' in {file_path} -> Replaced.")
        
        if changes_made:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"✅ Fixed: {file_path}")
        else:
            print(f"⚠️ No old models found in: {file_path}")
    else:
        print(f"❌ File not found: {file_path}")

print("\n🎉 Repairs complete. Please restart your app.")