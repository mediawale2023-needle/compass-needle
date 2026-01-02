import pandas as pd
import json
import os
import glob

def integrate_manual_schemes():
    print("🚀 Integrating Manual Scheme Data from CSVs...")
    
    # 1. Load Existing Schemes DB (if it exists)
    existing_schemes = []
    if os.path.exists("schemes.json"):
        try:
            with open("schemes.json", "r", encoding='utf-8') as f:
                existing_schemes = json.load(f)
            print(f"   ℹ️  Loaded {len(existing_schemes)} existing schemes.")
        except:
            print("   ⚠️  Could not read existing schemes.json. Starting fresh.")
    
    # 2. List of Uploaded CSVs (Matches your upload list)
    # Using glob to find them dynamically is safer
    csv_files = glob.glob("SCHEMES.xlsx - *.csv")
    
    if not csv_files:
        print("   ❌ No matching CSV files found. Make sure files like 'SCHEMES.xlsx - AGRICULTURE.csv' are in the folder.")
        return

    new_schemes = []
    
    for file in csv_files:
        print(f"   -> Processing {file}...")
        try:
            df = pd.read_csv(file)
            
            # Normalize Columns: Strip spaces, convert to lowercase for easy matching
            df.columns = [c.strip().lower() for c in df.columns]
            
            for _, row in df.iterrows():
                # Flexible Column Mapping
                # Tries different common names found in your files
                scheme_name = str(row.get('scheme name', row.get('scheme', 'Unknown Scheme')))
                if scheme_name == 'nan': continue # Skip empty rows

                ministry = str(row.get('ministry', 'Unknown Ministry'))
                objective = str(row.get('objective', row.get('objectives', 'No details available.')))
                
                # 'Classification' or 'Type' columns -> Focus Tags
                focus_raw = str(row.get('classification', row.get('type', 'General')))
                focus_tags = [t.strip() for t in focus_raw.split(',')]

                # Create Standardized Entry
                entry = {
                    "Scheme": scheme_name.strip(),
                    "Ministry": ministry.strip(),
                    "Description": objective.strip(),
                    "Focus": focus_tags,
                    
                    # Defaults for missing fields (can be enriched later)
                    "Grant": "Check Official Guidelines", 
                    "Eligibility": "Check Official Guidelines",
                    "Documents": "Standard KYC (Aadhaar, PAN, Bank Details)",
                    "Process": "Visit Ministry Website or District Office",
                    
                    # Metadata
                    "Status": "🟢 Active",
                    "Confidence": 90,
                    "Evidence": "Manually Curated Data",
                    "Budget_Alloc": "Unknown", # Will be updated by budget matcher if found
                    "Budget_Status": "Unknown"
                }
                new_schemes.append(entry)
                
        except Exception as e:
            print(f"   ❌ Error processing {file}: {e}")

    # 3. Merge & Deduplicate
    # We use a dictionary keyed by Scheme Name to prevent duplicates
    # New manual data will OVERWRITE old data (assuming manual is better quality)
    
    master_db = {item['Scheme']: item for item in existing_schemes}
    
    count_new = 0
    count_update = 0
    
    for item in new_schemes:
        if item['Scheme'] in master_db:
            # Update existing entry with better description/focus if needed
            # For now, we trust the manual data's description more
            master_db[item['Scheme']]['Description'] = item['Description']
            master_db[item['Scheme']]['Focus'] = item['Focus']
            master_db[item['Scheme']]['Ministry'] = item['Ministry']
            count_update += 1
        else:
            master_db[item['Scheme']] = item
            count_new += 1

    final_list = list(master_db.values())
    
    # 4. Save
    with open("schemes.json", "w", encoding='utf-8') as f:
        json.dump(final_list, f, indent=4, ensure_ascii=False)
        
    print(f"\n✅ INTEGRATION COMPLETE!")
    print(f"   - New Schemes Added: {count_new}")
    print(f"   - Existing Updated:  {count_update}")
    print(f"   - Total Database Size: {len(final_list)}")

if __name__ == "__main__":
    integrate_manual_schemes()