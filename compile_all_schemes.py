import pandas as pd
import json
import glob
import os

def compile_full_database():
    print("🚀 STARTING FULL DATA COMPILATION...")
    
    # 1. Budget Overlay (The Intelligence Layer)
    BUDGET_MAP = {
        "pm-kisan": {"alloc": "₹60,000 Cr", "status": "🟢 Active"},
        "fasal bima": {"alloc": "₹12,242 Cr", "status": "🟢 Active"},
        "jal jeevan": {"alloc": "₹67,000 Cr", "status": "🟢 Very High"},
        "mgnrega": {"alloc": "₹86,000 Cr", "status": "🟡 Stagnant"},
        "pmay": {"alloc": "₹23,294 Cr", "status": "🟢 Very High"},
        "awas": {"alloc": "₹23,294 Cr", "status": "🟢 Very High"},
        "samagra": {"alloc": "₹41,250 Cr", "status": "🟢 High Liquidity"},
        "poshan": {"alloc": "₹21,960 Cr", "status": "🟢 Very High"},
        "health mission": {"alloc": "₹37,227 Cr", "status": "🟢 Active"},
        "ayushman": {"alloc": "₹9,406 Cr", "status": "🟢 High"},
        "fame": {"alloc": "₹4,000 Cr (PM E-DRIVE)", "status": "🟢 Transformed"},
        "electric": {"alloc": "₹4,000 Cr (PM E-DRIVE)", "status": "🟢 Transformed"},
        "solar": {"alloc": "₹20,000 Cr (PM Surya Ghar)", "status": "🟢 Massive Allocation"},
        "pli": {"alloc": "₹19,000 Cr (Total)", "status": "🟢 High Opportunity"},
        "khelo": {"alloc": "₹1,000 Cr", "status": "🟢 Active"},
        "swachh": {"alloc": "₹12,192 Cr", "status": "🟢 Active"},
        "vishwakarma": {"alloc": "₹4,824 Cr", "status": "🟢 Active"}
    }

    # 2. File-to-Ministry Mapping (To fix missing Ministry names)
    FILE_MINISTRY_MAP = {
        "AGRICULTURE": "Ministry of Agriculture & Farmers Welfare",
        "PORTS": "Ministry of Ports, Shipping and Waterways",
        "POWER": "Ministry of Power",
        "SOCIAL JUSTICE": "Ministry of Social Justice and Empowerment",
        "SPORTS": "Ministry of Youth Affairs and Sports",
        "RENEWABLE": "Ministry of New and Renewable Energy",
        "WOMEN": "Ministry of Women and Child Development",
        "EDUCATION": "Ministry of Education",
        "JAL SHAKTI": "Ministry of Jal Shakti",
        "HEALTH": "Ministry of Health and Family Welfare",
        "URBAN": "Ministry of Housing and Urban Affairs",
        "FOOD PROCESSING": "Ministry of Food Processing Industries",
        "MINORITY": "Ministry of Minority Affairs",
        "MSME": "Ministry of Micro, Small and Medium Enterprises",
        "CONSUMER": "Ministry of Consumer Affairs",
        "HEAVY": "Ministry of Heavy Industries",
        "TEXTILES": "Ministry of Textiles"
    }

    # 3. Locate Files
    csv_files = glob.glob("SCHEMES.xlsx - *.csv")
    if not csv_files:
        print("❌ No CSV files found! Please run 'restore_data.py' first if files are missing.")
        return

    print(f"📂 Found {len(csv_files)} CSV files. Processing...")
    
    master_db = []
    seen_schemes = set()

    for filepath in csv_files:
        # Determine Ministry from filename
        this_ministry = "Central Government"
        for key, val in FILE_MINISTRY_MAP.items():
            if key in filepath:
                this_ministry = val
                break
        
        try:
            df = pd.read_csv(filepath)
            # Normalize columns
            df.columns = [c.strip().lower() for c in df.columns]
            
            # Find the best column for 'Scheme Name'
            name_col = next((c for c in df.columns if 'scheme' in c), None)
            desc_col = next((c for c in df.columns if 'obj' in c or 'desc' in c), None)
            focus_col = next((c for c in df.columns if 'class' in c or 'type' in c), None)

            if name_col:
                for _, row in df.iterrows():
                    s_name = str(row[name_col]).strip()
                    
                    # Clean up invalid names
                    if len(s_name) < 3 or s_name.lower() in ['nan', 'scheme', 'name', 'scheme name']: 
                        continue
                    
                    # Avoid duplicates
                    if s_name in seen_schemes:
                        continue
                    seen_schemes.add(s_name)

                    # Extract details
                    s_desc = str(row.get(desc_col, 'Refer to official guidelines for details.')) if desc_col else "Details pending update."
                    s_focus = str(row.get(focus_col, 'General')) if focus_col else "General"
                    
                    # Clean up focus tags
                    s_focus_list = [x.strip() for x in s_focus.replace(" and ", ",").split(',')]

                    # Check Budget
                    b_alloc = "Check Dept"
                    b_status = "Active"
                    b_note = ""
                    
                    for k, v in BUDGET_MAP.items():
                        if k in s_name.lower():
                            b_alloc = v['alloc']
                            b_status = v['status']
                            b_note = "2025-26 Budget Allocation"
                            break
                    
                    entry = {
                        "Scheme": s_name,
                        "Ministry": this_ministry,
                        "Description": s_desc,
                        "Focus": s_focus_list,  # List of tags
                        "Budget_Alloc": b_alloc,
                        "Budget_Status": b_status,
                        "Budget_Note": b_note,
                        "Grant": "Refer to Guidelines",
                        "Eligibility": "Check Official Portal",
                        "Documents": "Standard KYC",
                        "Process": "Online/District Office"
                    }
                    master_db.append(entry)
                    
            print(f"   ✅ Processed {filepath} ({len(df)} rows)")
            
        except Exception as e:
            print(f"   ⚠️ Error processing {filepath}: {e}")

    # 4. Save Final Database
    print(f"\n💾 Saving {len(master_db)} total schemes to 'schemes.json'...")
    with open("schemes.json", "w", encoding='utf-8') as f:
        json.dump(master_db, f, indent=4, ensure_ascii=False)
    
    print("🎉 SUCCESS! Full database compiled.")

if __name__ == "__main__":
    compile_full_database()