import pandas as pd
import json
import os

def convert():
    print("🚀 Starting Aggressive Central Scheme Extraction...")
    
    if not os.path.exists("kaggle_schemes.csv"):
        print("❌ Error: 'kaggle_schemes.csv' not found.")
        return

    try:
        df = pd.read_csv("kaggle_schemes.csv")
        
        # 1. Normalize Columns
        df.columns = [c.strip().lower() for c in df.columns]
        
        # 2. Define State Blacklist (To filter out state ministries)
        state_blacklist = [
            "andhra", "arunachal", "assam", "bihar", "chhattisgarh", "goa", "gujarat", 
            "haryana", "himachal", "jharkhand", "karnataka", "kerala", "madhya", 
            "maharashtra", "manipur", "meghalaya", "mizoram", "nagaland", "odisha", 
            "punjab", "rajasthan", "sikkim", "tamil", "telangana", "tripura", 
            "uttar", "uttarakhand", "west bengal", "delhi", "jammu", "kashmir",
            "ladakh", "puducherry", "chandigarh", "dadra", "lakshadweep", "andaman"
        ]

        needle_db = []
        count_central = 0
        count_state = 0
        
        print(f"   -> Scanning {len(df)} total rows...")

        for _, row in df.iterrows():
            # Get raw values
            level = str(row.get('level', '')).lower()
            ministry = str(row.get('ministry_name', ''))
            scheme_name = str(row.get('scheme_name', ''))

            # --- THE STRICT FILTER ---
            is_central = False
            
            # Check 1: Explicit 'Central' tag
            if 'central' in level:
                is_central = True
            
            # Check 2: Exclude if Ministry/Scheme contains a State Name
            for state in state_blacklist:
                if state in ministry.lower() or state in scheme_name.lower():
                    is_central = False
                    break
            
            if is_central:
                count_central += 1
                
                # Prepare Entry
                desc = str(row.get('details', ''))[:400] + "..."
                cat = str(row.get('schemecategory', 'General'))
                tags = [x.strip() for x in cat.split(',')]
                
                entry = {
                    "Scheme": row.get('scheme_name', 'Unknown'),
                    "Ministry": row.get('ministry_name', 'Central Govt'),
                    "Description": desc,
                    "Focus": tags,
                    "Grant": "View Guidelines",
                    "Status": "🟢 Open", 
                    "Confidence": 90,
                    "Evidence": "Sourced from National Portal"
                }
                needle_db.append(entry)
            else:
                count_state += 1
            
        # Save filtered list
        with open("schemes.json", "w", encoding='utf-8') as f:
            json.dump(needle_db, f, indent=4, ensure_ascii=False)
            
        print(f"✅ SUCCESS! Saved {len(needle_db)} Central Schemes.")
        print(f"🗑️ Filtered out {count_state} State Schemes.")
        
    except Exception as e:
        print(f"❌ Failed: {e}")

if __name__ == "__main__":
    convert()
