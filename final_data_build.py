import pandas as pd
import json
import os
import glob

def rebuild_database():
    print("🏗️  REBUILDING DATABASE WITH CORRECT MINISTRIES...")

    # 1. FILE -> MINISTRY MAPPING (The Source of Truth)
    # This forces the correct Ministry name for each file, ignoring CSV errors.
    file_map = {
        "SCHEMES.xlsx - AGRICULTURE.csv": "Ministry of Agriculture & Farmers Welfare",
        "SCHEMES.xlsx - PORTS.csv": "Ministry of Ports, Shipping and Waterways",
        "SCHEMES.xlsx - POWER.csv": "Ministry of Power",
        "SCHEMES.xlsx - SOCIAL JUSTICE.csv": "Ministry of Social Justice and Empowerment",
        "SCHEMES.xlsx - SPORTS.csv": "Ministry of Youth Affairs and Sports",
        "SCHEMES.xlsx - RENEWABLE ENERGY.csv": "Ministry of New and Renewable Energy",
        "SCHEMES.xlsx - WOMEN AND CHILD.csv": "Ministry of Women and Child Development",
        "SCHEMES.xlsx - EDUCATION.csv": "Ministry of Education",
        "SCHEMES.xlsx - JAL SHAKTI.csv": "Ministry of Jal Shakti",
        "SCHEMES.xlsx - HEALTH.csv": "Ministry of Health and Family Welfare",
        "SCHEMES.xlsx - URBAN .csv": "Ministry of Housing and Urban Affairs",
        "SCHEMES.xlsx - Ministry of Food Processing.csv": "Ministry of Food Processing Industries",
        "SCHEMES.xlsx - Minority Affairs.csv": "Ministry of Minority Affairs",
        "SCHEMES.xlsx - MSME.csv": "Ministry of Micro, Small and Medium Enterprises",
        "SCHEMES.xlsx - Ministry of Consumer Affairs.csv": "Ministry of Consumer Affairs",
        "SCHEMES.xlsx - Ministry of Heavy Industry.csv": "Ministry of Heavy Industries",
        "SCHEMES.xlsx - TEXTILES.csv": "Ministry of Textiles"
    }

    # 2. BUDGET DATA OVERLAY (2025-26)
    budget_map = {
        "pm-kisan": "₹60,000 Cr",
        "fasal bima": "₹12,242 Cr",
        "jal jeevan": "₹67,000 Cr",
        "mgnrega": "₹86,000 Cr",
        "pmay": "₹23,294 Cr",
        "awas": "₹23,294 Cr",
        "samagra": "₹41,250 Cr",
        "poshan": "₹21,960 Cr",
        "health mission": "₹37,227 Cr",
        "ayushman": "₹9,406 Cr",
        "fame": "₹4,000 Cr (PM E-DRIVE)",
        "electric": "₹4,000 Cr (PM E-DRIVE)",
        "solar": "₹20,000 Cr (PM Surya Ghar)",
        "pli": "₹19,000 Cr (Total)"
    }

    master_db = []

    # 3. PROCESS EACH FILE
    for filename, ministry_name in file_map.items():
        if os.path.exists(filename):
            try:
                df = pd.read_csv(filename)
                # Normalize columns
                df.columns = [c.strip().lower() for c in df.columns]
                
                # Find scheme name column (it varies by file)
                name_col = next((c for c in df.columns if 'scheme' in c and 'name' in c), None)
                if not name_col:
                    name_col = next((c for c in df.columns if 'scheme' in c), None)
                
                desc_col = next((c for c in df.columns if 'obj' in c), None) # Objectives
                focus_col = next((c for c in df.columns if 'class' in c or 'type' in c), None) # Classification

                if name_col:
                    for _, row in df.iterrows():
                        s_name = str(row[name_col]).strip()
                        if s_name.lower() in ['nan', 'scheme', 'name']: continue
                        
                        # Use the HARDCODED Ministry Name
                        s_ministry = ministry_name
                        s_desc = str(row.get(desc_col, '')) if desc_col else "See guidelines."
                        s_focus = str(row.get(focus_col, 'General')) if focus_col else "General"

                        # Check Budget
                        b_alloc = "Check Dept"
                        b_status = "Unknown"
                        for k, v in budget_map.items():
                            if k in s_name.lower():
                                b_alloc = v
                                b_status = "🟢 Active"
                                break
                        
                        entry = {
                            "Scheme": s_name,
                            "Ministry": s_ministry, # <--- This fixes the dropdown
                            "Description": s_desc,
                            "Focus": [s_focus],
                            "Budget_Alloc": b_alloc,
                            "Budget_Status": b_status,
                            "Grant": "Refer to Guidelines",
                            "Eligibility": "Check Official Portal",
                            "Documents": "Standard KYC",
                            "Process": "Online/District Office"
                        }
                        master_db.append(entry)
                        
                print(f"✅ Processed {filename} -> {ministry_name}")
            except Exception as e:
                print(f"❌ Error reading {filename}: {e}")
        else:
            print(f"⚠️ File not found: {filename}")

    # 4. SAVE
    with open("schemes.json", "w", encoding='utf-8') as f:
        json.dump(master_db, f, indent=4, ensure_ascii=False)
        
    print(f"\n🎉 DATABASE REBUILT. Total Schemes: {len(master_db)}")
    print("   The 'Ministry' dropdown will now show all departments.")

if __name__ == "__main__":
    rebuild_database()