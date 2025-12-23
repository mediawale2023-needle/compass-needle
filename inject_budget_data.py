import json
import os
from difflib import get_close_matches

# --- REAL BUDGET 2025-26 DATA (Estimates in Crores) ---
# Source: Budget at a Glance & Ministry Demands
REAL_BUDGET_DATA = {
    # --- AGRICULTURE & FARMERS ---
    "Pradhan Mantri Kisan Samman Nidhi (PM-KISAN)": "₹60,000 Cr",
    "Pradhan Mantri Fasal Bima Yojana (PMFBY)": "₹14,600 Cr",
    "Modified Interest Subvention Scheme (MISS)": "₹22,600 Cr",
    "Rashtriya Krishi Vikas Yojana (RKVY)": "₹8,500 Cr",
    "Krishionnati Yojana": "₹8,000 Cr",
    "National Mission on Natural Farming": "₹459 Cr",
    
    # --- EDUCATION ---
    "Samagra Shiksha": "₹41,250 Cr",
    "PM POSHAN (Mid Day Meal)": "₹12,500 Cr",
    "PM-SHRI Schools": "₹7,500 Cr",
    "Pradhan Mantri Uchchatar Shiksha Abhiyan (PM-USHA)": "₹1,815 Cr",
    
    # --- HEALTH ---
    "National Health Mission (NHM)": "₹38,000 Cr",
    "Ayushman Bharat - PMJAY": "₹9,406 Cr",
    "Pradhan Mantri Ayushman Bharat Health Infrastructure Mission (PMABHIM)": "₹4,200 Cr",
    "National AYUSH Mission": "₹1,275 Cr",
    "Establishment of New Medical Colleges": "₹5,000 Cr",
    
    # --- URBAN & HOUSING ---
    "Pradhan Mantri Awas Yojana (Urban)": "₹19,794 Cr",
    "PMAY-Urban 2.0 (New)": "₹3,500 Cr",
    "AMRUT (Urban Rejuvenation)": "₹10,000 Cr",
    "Smart Cities Mission": "₹2,400 Cr",
    "Swachh Bharat Mission (Urban)": "₹5,000 Cr",
    "PM SVANidhi (Street Vendors)": "₹326 Cr",
    
    # --- RURAL DEVELOPMENT ---
    "Mahatma Gandhi National Rural Employment Guarantee Program (MGNREGA)": "₹86,000 Cr",
    "Pradhan Mantri Awas Yojana (Gramin)": "₹54,500 Cr",
    "Pradhan Mantri Gram Sadak Yojana (PMGSY)": "₹12,000 Cr",
    "National Livelihood Mission (Ajeevika)": "₹14,129 Cr",
    
    # --- JAL SHAKTI (WATER) ---
    "Jal Jeevan Mission (JJM)": "₹69,926 Cr",
    "Swachh Bharat Mission (Gramin)": "₹7,192 Cr",
    "Namami Gange": "₹3,500 Cr",
    
    # --- SOCIAL JUSTICE & OTHERS ---
    "PM-YASASVI (Scholarships for OBC/EBC)": "₹3,400 Cr",
    "Pradhan Mantri Anusuchit Jaati Abhyuday Yojana (PM-AJAY)": "₹2,500 Cr",
    "Post Matric Scholarship for SCs": "₹6,350 Cr",
    "Saksham Anganwadi and POSHAN 2.0": "₹21,200 Cr",
    "Mission Shakti (Women Empowerment)": "₹3,146 Cr",
    "Mission Vatsalya (Child Protection)": "₹1,472 Cr",
    
    # --- INDUSTRY & INFRA ---
    "Production Linked Incentive (PLI) Schemes (Auto/Electronics/Pharma)": "₹6,200 Cr",
    "FAME India (EV Subsidy)": "₹2,671 Cr",
    "PM Vishwakarma": "₹4,824 Cr",
    "Guarantee Emergency Credit Line (GECL) for MSME": "₹9,812 Cr",
    "Solar Power (Grid)": "₹8,500 Cr",
    "Green Energy Corridors": "₹600 Cr",
    "National Green Hydrogen Mission": "₹600 Cr",
    
    # --- FISHERIES & FOOD PROCESSING ---
    "Pradhan Mantri Matsya Sampada Yojana": "₹2,465 Cr",
    "PM Formalisation of Micro Food Processing Enterprises (PMFME)": "₹2,000 Cr"
}

def inject_budget():
    print("🚀 Starting Budget 2025-26 Injection...")
    
    # 1. Load your existing Scheme Database
    if not os.path.exists("schemes_db.json"):
        print("❌ 'schemes_db.json' not found. Run 'build_schemes_db.py' first!")
        return
        
    with open("schemes_db.json", "r", encoding="utf-8") as f:
        schemes = json.load(f)
        
    print(f"📂 Loaded {len(schemes)} schemes from database.")
    
    # 2. Matching Logic
    matches = 0
    budget_keys = list(REAL_BUDGET_DATA.keys())
    
    for s in schemes:
        name = s['name'].strip()
        
        # Exact Match?
        if name in REAL_BUDGET_DATA:
            s['budget_allocation'] = REAL_BUDGET_DATA[name]
            matches += 1
            continue
            
        # Fuzzy Match? (e.g. 'PMAY Urban' matching 'Pradhan Mantri Awas Yojana (Urban)')
        # We look for the best match with at least 50% similarity
        close = get_close_matches(name, budget_keys, n=1, cutoff=0.5)
        
        if close:
            best_match = close[0]
            s['budget_allocation'] = REAL_BUDGET_DATA[best_match]
            matches += 1
        else:
            s['budget_allocation'] = "Check Dept"

    # 3. Save the enriched database
    with open("schemes_db.json", "w", encoding="utf-8") as f:
        json.dump(schemes, f, indent=4)
        
    print(f"✅ SUCCESS! Injected funds into {matches} schemes.")
    print("   Example: 'Samagra Shiksha' now has '₹41,250 Cr'")

if __name__ == "__main__":
    inject_budget()