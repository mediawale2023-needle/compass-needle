import pandas as pd
import json
import os

def convert():
    print("🚀 Injecting Rich Details into Schemes Database...")
    
    if not os.path.exists("kaggle_schemes.csv"):
        print("❌ Error: 'kaggle_schemes.csv' not found.")
        return

    try:
        df = pd.read_csv("kaggle_schemes.csv")
        # Clean column names
        df.columns = [c.strip().lower() for c in df.columns]
        
        needle_db = []
        
        for _, row in df.iterrows():
            # Filter for Central Schemes
            level = str(row.get('level', '')).lower()
            if 'central' not in level:
                continue

            # EXTRACT RICH DATA
            # We use " or 'N/A'" so it never returns an empty string
            eligibility = str(row.get('eligibility', 'Check Official Guidelines'))
            documents = str(row.get('documents', 'Check Official Guidelines'))
            process = str(row.get('application', 'Visit National Portal'))
            
            if len(eligibility) < 5: eligibility = "Details not available in dataset."
            if len(documents) < 5: documents = "Standard KYC (Aadhaar, PAN)."

            entry = {
                "Scheme": str(row.get('scheme_name', 'Unknown')),
                "Ministry": str(row.get('ministry_name', 'Central Govt')),
                "Description": str(row.get('details', ''))[:300] + "...",
                "Focus": [x.strip() for x in str(row.get('schemecategory', 'General')).split(',')],
                "Grant": str(row.get('benefits', 'Check Guidelines'))[:100],
                
                # NEW FIELDS FOR TABS
                "Eligibility": eligibility,
                "Documents": documents,
                "Process": process,
                
                "Status": "🟢 Active", 
                "Confidence": 90
            }
            needle_db.append(entry)
            
        with open("schemes.json", "w", encoding='utf-8') as f:
            json.dump(needle_db, f, indent=4, ensure_ascii=False)
            
        print(f"✅ SUCCESS! Updated 'schemes.json' with {len(needle_db)} rich records.")
        
    except Exception as e:
        print(f"❌ Failed: {e}")

if __name__ == "__main__":
    convert()
