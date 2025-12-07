import pandas as pd
import json
import os
import glob

def build_intelligence_database():
    print("🏗️  INITIATING MASTER BUILD SEQUENCE...")
    
    # --- SECTION A: BUDGET INTELLIGENCE LAYER (2025-26) ---
    # Hardcoded values from Union Budget 2025-26 Speech & Demands for Grants
    BUDGET_MAP = {
        # Agriculture
        "PM-KISAN": {"alloc": "₹60,000 Cr", "status": "🟢 Active"},
        "Pradhan Mantri Fasal Bima Yojana (PMFBY)": {"alloc": "₹12,242 Cr", "status": "🟢 Active"},
        "Pradhan Mantri Krishi Sinchai Yojana": {"alloc": "₹11,391 Cr", "status": "🟢 High Liquidity"},
        "Krishonnati Yojana": {"alloc": "₹7,553 Cr", "status": "🟢 Active"},
        
        # Education
        "Samagra Shiksha": {"alloc": "₹41,250 Cr", "status": "🟢 High Liquidity"},
        "Mid-Day Meal": {"alloc": "₹12,500 Cr (PM-POSHAN)", "status": "🟢 Active"},
        "PM-SHRI": {"alloc": "₹7,500 Cr", "status": "🟢 Active"},
        
        # Water & Health
        "Jal Jeevan Mission": {"alloc": "₹67,000 Cr", "status": "🟢 Very High Liquidity"},
        "National Health Mission": {"alloc": "₹37,227 Cr", "status": "🟢 Active"},
        "Ayushman Bharat": {"alloc": "₹9,406 Cr (PMJAY)", "status": "🟢 Active"},
        
        # Infrastructure & Urban
        "Pradhan Mantri Awas Yojana (Urban)": {"alloc": "₹23,294 Cr", "status": "🟢 Very High"},
        "Smart Cities": {"alloc": "₹10,000 Cr (AMRUT)", "status": "🟢 Active"},
        "Swachh Bharat Mission": {"alloc": "₹12,192 Cr (Total)", "status": "🟢 Active"},
        
        # Industry & Energy
        "FAME-India": {"alloc": "₹4,000 Cr (PM E-DRIVE)", "status": "🟢 Transformed"},
        "PLI": {"alloc": "₹19,000 Cr (Total PLI)", "status": "🟢 High Opportunity"},
        "PM Surya Ghar": {"alloc": "₹20,000 Cr", "status": "🟢 Massive Allocation"},
        "Green Hydrogen": {"alloc": "₹600 Cr", "status": "🟢 Emerging"},
        
        # Social
        "Saksham Anganwadi": {"alloc": "₹21,960 Cr", "status": "🟢 Very High"},
        "Mission Shakti": {"alloc": "₹3,150 Cr", "status": "🟢 Active"},
        "PM-JANMAN": {"alloc": "₹341 Cr", "status": "🟢 Tribal Focus"}
    }

    # --- SECTION B: INGESTION ENGINE ---
    # Locates all Excel-converted CSVs
    csv_files = glob.glob("SCHEMES.xlsx - *.csv")
    
    if not csv_files:
        print("❌ CRITICAL ERROR: Source CSV files not found.")
        print("   Ensure files like 'SCHEMES.xlsx - AGRICULTURE.csv' are in the root directory.")
        return

    master_db = []
    
    print(f"   📂 Found {len(csv_files)} source files. Processing...")

    for filepath in csv_files:
        try:
            # Read CSV
            df = pd.read_csv(filepath)
            # Normalize Headers (lowercase, strip whitespace)
            df.columns = [c.strip().lower() for c in df.columns]
            
            # Identify Key Columns (Smart Mapping)
            col_map = {
                'name': next((c for c in df.columns if 'scheme' in c and 'name' in c), 'scheme'),
                'ministry': next((c for c in df.columns if 'ministry' in c), 'ministry'),
                'desc': next((c for c in df.columns if 'objective' in c), 'objective'),
                'focus': next((c for c in df.columns if 'class' in c or 'type' in c), 'classification')
            }

            for _, row in df.iterrows():
                # Extract Data
                s_name = str(row.get(col_map['name'], 'Unknown')).strip()
                if s_name.lower() in ['nan', 'scheme', 'unknown']: continue

                s_ministry = str(row.get(col_map['ministry'], 'Government of India')).strip()
                s_desc = str(row.get(col_map['desc'], 'See details in official guidelines.'))
                s_focus = str(row.get(col_map['focus'], 'General Development'))
                
                # --- INTELLIGENCE INJECTION ---
                # Check against Budget Map
                b_alloc = "Check Dept"
                b_status = "Unknown"
                b_note = ""
                
                for key, data in BUDGET_MAP.items():
                    if key.lower() in s_name.lower():
                        b_alloc = data['alloc']
                        b_status = data['status']
                        b_note = "Sourced from Union Budget 2025-26"
                        break
                
                # Build Record
                entry = {
                    "Scheme": s_name,
                    "Ministry": s_ministry,
                    "Description": s_desc,
                    "Focus": [x.strip() for x in s_focus.split(',')],
                    "Grant": "Refer to Guidelines",
                    "Eligibility": "Check Official Portal",
                    "Documents": "Standard KYC",
                    "Process": "Online/District Office",
                    
                    # Budget Fields
                    "Budget_Alloc": b_alloc,
                    "Budget_Status": b_status,
                    "Budget_Note": b_note,
                    
                    "Confidence": 95 if b_alloc != "Check Dept" else 80
                }
                master_db.append(entry)
                
        except Exception as e:
            print(f"   ⚠️ Warning: Issue with file {filepath}: {e}")

    # --- SECTION C: DEDUPLICATION & SAVE ---
    # Convert to dict to remove duplicates by Name
    unique_db = {item['Scheme']: item for item in master_db}
    final_list = list(unique_db.values())
    
    with open("schemes.json", "w", encoding='utf-8') as f:
        json.dump(final_list, f, indent=4, ensure_ascii=False)

    print(f"✅ BUILD COMPLETE.")
    print(f"   - Total Unique Schemes: {len(final_list)}")
    print(f"   - Database: 'schemes.json' updated.")

if __name__ == "__main__":
    build_intelligence_database()