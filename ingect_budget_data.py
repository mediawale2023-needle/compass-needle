import json
import os

def inject_budget():
    print("💰 Injecting Verified 2025-26 Budget Data into Schemes DB...")
    
    if not os.path.exists("schemes.json"):
        print("❌ 'schemes.json' not found. Please run the ingestion script first.")
        return
        
    with open("schemes.json", "r", encoding='utf-8') as f:
        schemes = json.load(f)
    
    # MASTER BUDGET MAP (Scheme Name -> 2025-26 Allocation & Status)
    # This maps the names in your CSVs to the Budget Speech numbers
    budget_map = {
        # --- AGRICULTURE ---
        "Pradhan Mantri KISAN Samman Nidhi (PM-KISAN)": {"alloc": "₹60,000 Cr", "status": "🟢 Active (Stable)"},
        "Pradhan Mantri Fasal Bima Yojana (PMFBY)": {"alloc": "₹12,242 Cr", "status": "🟢 Active"},
        "Pradhan Mantri Krishi Sinchai Yojana (PMKSY)": {"alloc": "₹11,391 Cr", "status": "🟢 High Liquidity"},
        "Green Revolution – Krishonnati Yojana": {"alloc": "₹7,553 Cr", "status": "🟢 Active"},
        "National Food Security Mission (NFSM)": {"alloc": "Under Krishonnati", "status": "🟢 Active"},
        
        # --- HEAVY INDUSTRIES / AUTO ---
        "Faster Adoption and Manufacturing of (Hybrid and) Electric Vehicles in India (FAME-India) Scheme": {"alloc": "₹4,000 Cr (PM E-DRIVE)", "status": "🟢 Transformed"},
        "Production Linked Incentive (PLI) Scheme for Automobile and Auto Components": {"alloc": "₹2,819 Cr", "status": "🟢 Active"},
        "Production Linked Incentive (PLI) Scheme for Advanced Chemistry Cell (ACC) Battery Storage": {"alloc": "₹156 Cr", "status": "🟢 Emerging"},
        
        # --- JAL SHAKTI ---
        "Jal Jeevan Mission (JJM)": {"alloc": "₹67,000 Cr", "status": "🟢 Very High Liquidity"},
        "Swachh Bharat Mission (Gramin) - Phase II": {"alloc": "₹7,192 Cr", "status": "🟢 Active"},
        "Namami Gange Programme": {"alloc": "₹3,400 Cr", "status": "🟢 Active"},
        
        # --- EDUCATION ---
        "Samagra Shiksha": {"alloc": "₹41,250 Cr", "status": "🟢 High Liquidity"},
        "Mid-Day Meal Scheme (MDMS)": {"alloc": "₹12,500 Cr (PM-POSHAN)", "status": "🟢 Active"},
        "PM-SHRI": {"alloc": "₹7,500 Cr", "status": "🟢 Active"},
        
        # --- HOUSING & URBAN ---
        "Pradhan Mantri Awas Yojana (Urban) (PMAY-U)": {"alloc": "₹23,294 Cr", "status": "🟢 Very High Liquidity"},
        "Smart Cities Mission": {"alloc": "₹10,000 Cr (AMRUT/Smart)", "status": "🟢 Active"},
        "Swachh Bharat Mission (Urban)": {"alloc": "₹5,000 Cr", "status": "🟢 Active"},
        "PM SVANidhi": {"alloc": "₹373 Cr", "status": "🟢 Active (Street Vendors)"},
        
        # --- FOOD PROCESSING ---
        "Pradhan Mantri Kisan SAMPADA Yojana (PMKSY)": {"alloc": "₹903 Cr", "status": "🟢 Active"},
        "Production Linked Incentive Scheme for Food Processing Industry (PLISFPI)": {"alloc": "₹1,200 Cr", "status": "🟢 Opportunity"},
        
        # --- SPORTS ---
        "Khelo India Programme": {"alloc": "₹1,000 Cr", "status": "🟢 Active"},
        
        # --- WOMEN & CHILD ---
        "Integrated Child Development Services (ICDS)": {"alloc": "₹21,960 Cr (Saksham Anganwadi)", "status": "🟢 Very High"},
        "Pradhan Mantri Matru Vandana Yojana (PMMVY)": {"alloc": "₹3,150 Cr (Mission Shakti)", "status": "🟢 Active"},
        "Mission Vatsalya": {"alloc": "₹1,500 Cr", "status": "🟢 Active"},
        
        # --- HEALTH ---
        "Ayushman Bharat": {"alloc": "₹9,406 Cr (PMJAY)", "status": "🟢 High Liquidity"},
        "National Health Mission (NHM)": {"alloc": "₹37,227 Cr", "status": "🟢 Very High"},
        
        # --- RENEWABLE ENERGY ---
        "PM-KUSUM": {"alloc": "₹2,600 Cr", "status": "🟢 Active"},
        "National Green Hydrogen Mission": {"alloc": "₹600 Cr", "status": "🟢 Emerging"},
        "Grid Connected Rooftop Solar": {"alloc": "₹20,000 Cr (PM Surya Ghar)", "status": "🟢 Massive Allocation"},
        
        # --- MINORITY AFFAIRS ---
        "Pradhan Mantri Jan Vikas Karyakram (PMJVK)": {"alloc": "₹1,914 Cr", "status": "🟢 Active"},
        
        # --- CONSUMER AFFAIRS ---
        "Price Stabilization Fund (PSF)": {"alloc": "₹4,361 Cr", "status": "🟢 Buffer Stock"}
    }

    count = 0
    for item in schemes:
        name = item.get('Scheme', '').strip()
        
        # Smart Matching Logic
        match = None
        
        # 1. Exact Match
        if name in budget_map:
            match = budget_map[name]
        
        # 2. Fuzzy/Partial Match (e.g., "FAME" inside long name)
        if not match:
            for k, v in budget_map.items():
                # Check if key is part of name OR name is part of key
                if k.lower() in name.lower() or name.lower() in k.lower():
                    match = v
                    break
        
        if match:
            item['Budget_Alloc'] = match['alloc']
            item['Budget_Status'] = match['status']
            item['Budget_Note'] = "Updated from Union Budget 2025-26"
            count += 1
        else:
            # Set defaults for unmatched schemes
            if 'Budget_Alloc' not in item or item['Budget_Alloc'] == "Unknown":
                item['Budget_Alloc'] = "Check Dept"
                item['Budget_Status'] = "Unknown"

    # Save
    with open("schemes.json", "w", encoding='utf-8') as f:
        json.dump(schemes, f, indent=4, ensure_ascii=False)
        
    print(f"✅ Success! Enriched {count} schemes with 2025-26 Budget Data.")

if __name__ == "__main__":
    inject_budget()