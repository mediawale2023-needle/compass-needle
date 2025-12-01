import pandas as pd
import json
import os

def convert():
    print("🚀 Starting Central Scheme Extraction...")
    
    if not os.path.exists("kaggle_schemes.csv"):
        print("❌ Error: 'kaggle_schemes.csv' not found.")
        return

    try:
        df = pd.read_csv("kaggle_schemes.csv")
        
        # --- FILTER LOGIC ---
        # We check if the 'level' column says 'Central'
        # If the column names are different in your specific CSV version, 
        # we print them out to help debug.
        
        # Normalize column names just in case (lowercase)
        df.columns = [c.strip().lower() for c in df.columns]
        
        # Check if 'level' column exists (Common in this dataset)
        if 'level' in df.columns:
            central_df = df[df['level'].str.contains('Central', case=False, na=False)]
        else:
            # Fallback: Filter by Ministry Name (Central ministries usually contain 'Ministry of')
            # State depts often say "Department of..." or have state names.
            print("⚠️ 'level' column not found. Filtering by Ministry name...")
            central_df = df[df['ministry_name'].str.contains('Ministry of', case=False, na=False)]

        needle_db = []
        print(f"   -> Found {len(central_df)} Central Schemes (out of {len(df)} total).")
        
        for _, row in central_df.iterrows():
            # Extract Data
            scheme_name = str(row.get('scheme_name', 'Unknown'))
            ministry = str(row.get('ministry_name', 'Central Govt'))
            desc = str(row.get('details', ''))[:400] + "..."
            
            # Clean Tags
            cat = str(row.get('schemecategory', 'General'))
            tags = [x.strip() for x in cat.split(',')]
            
            entry = {
                "Scheme": scheme_name,
                "Ministry": ministry,
                "Description": desc,
                "Focus": tags,
                "Grant": "View Guidelines",
                "Status": "🟢 Open", 
                "Confidence": 90,
                "Evidence": "Sourced from National Portal"
            }
            needle_db.append(entry)
            
        # Save filtered list
        with open("schemes.json", "w", encoding='utf-8') as f:
            json.dump(needle_db, f, indent=4, ensure_ascii=False)
            
        print(f"✅ SUCCESS! Saved {len(needle_db)} Central Schemes to 'schemes.json'.")
        
    except Exception as e:
        print(f"❌ Failed: {e}")

if __name__ == "__main__":
    convert()
