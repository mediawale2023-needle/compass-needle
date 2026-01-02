import json
import os
from difflib import get_close_matches

def merge_datasets():
    print("🚀 Starting Budget Injection...")
    
    # 1. Load the Scheme DB (Target)
    if not os.path.exists("schemes_db.json"):
        print("❌ 'schemes_db.json' not found. Run 'build_schemes_db.py' first.")
        return
    
    with open("schemes_db.json", "r", encoding="utf-8") as f:
        schemes = json.load(f)
        
    # 2. Load the Budget DB (Source)
    # We try looking for 'budget_2025_26.json' or 'budget.json'
    budget_file = "budget_2025_26.json"
    if not os.path.exists(budget_file):
        budget_file = "budget.json"
        
    if not os.path.exists(budget_file):
        print(f"⚠️ Budget file not found. Creating a mock budget for demo purposes.")
        budget_data = [] # We will handle empty later
    else:
        print(f"📂 Loading financial data from: {budget_file}")
        with open(budget_file, "r", encoding="utf-8") as f:
            raw_budget = json.load(f)
            # Handle if it's a dict like {"schemes": [...]} or just a list
            if isinstance(raw_budget, dict):
                budget_data = raw_budget.get("schemes", [])
            else:
                budget_data = raw_budget

    # 3. Create a Lookup Dictionary for Budget
    # We map "Scheme Name" -> "Budget Amount"
    budget_map = {}
    for item in budget_data:
        # Find the name key
        name = item.get("name", item.get("Scheme", item.get("scheme_name", "")))
        # Find the money key
        money = item.get("budget_allocation", item.get("budget", item.get("amount", "N/A")))
        
        if name:
            budget_map[name.lower().strip()] = money

    print(f"💰 Found funding data for {len(budget_map)} schemes.")

    # 4. Merge Logic (Fuzzy Match)
    matches_found = 0
    budget_keys = list(budget_map.keys())
    
    for s in schemes:
        s_name = s['name'].lower().strip()
        
        # A. Exact Match
        if s_name in budget_map:
            s['budget_allocation'] = budget_map[s_name]
            matches_found += 1
            continue
            
        # B. Fuzzy Match (if exact fails)
        # Finds the closest match if it's > 60% similar
        close = get_close_matches(s_name, budget_keys, n=1, cutoff=0.6)
        if close:
            matched_name = close[0]
            s['budget_allocation'] = budget_map[matched_name]
            s['budget_source_name'] = matched_name # Traceability
            matches_found += 1
        else:
            s['budget_allocation'] = "Check Dept" # Default if no funds found

    # 5. Save Updated DB
    with open("schemes_db.json", "w", encoding="utf-8") as f:
        json.dump(schemes, f, indent=4)
        
    print(f"✅ MERGE COMPLETE!")
    print(f"   - Total Schemes: {len(schemes)}")
    print(f"   - Funds Linked: {matches_found}")
    print(f"   - Database updated: schemes_db.json")

if __name__ == "__main__":
    merge_datasets()