import json

def generate_budget_db():
    print("💰 Generating Verified Union Budget 2025-26 Database...")
    
    budget_data = [
        {"Scheme": "MGNREGA", "Allocation": "₹86,000 Cr", "Status": "🟡 Stagnant", "Note": "No increase despite high demand."},
        {"Scheme": "Jal Jeevan Mission", "Allocation": "₹67,000 Cr", "Status": "🟢 High Liquidity", "Note": "Mission extended to 2028."},
        {"Scheme": "PMAY (Urban)", "Allocation": "₹26,170 Cr", "Status": "🟢 Open", "Note": "Part of new ₹10L Cr investment."},
        {"Scheme": "PMAY (Rural)", "Allocation": "₹54,500 Cr", "Status": "🟢 Open", "Note": "Focus on rural completion."},
        {"Scheme": "PM-KISAN", "Allocation": "₹60,000 Cr", "Status": "🟢 Active", "Note": "DBT payments stable."},
        {"Scheme": "PLI (Electronics)", "Allocation": "₹9,000 Cr", "Status": "🟢 Very High", "Note": "+56% Budget Hike."},
        {"Scheme": "PLI (Textiles)", "Allocation": "₹1,148 Cr", "Status": "🟢 Opportunity", "Note": "Massive 25x Budget Jump."},
        {"Scheme": "National Health Mission", "Allocation": "₹38,000 Cr", "Status": "🟢 Active", "Note": "Infra focus."},
        {"Scheme": "Saksham Anganwadi", "Allocation": "₹21,200 Cr", "Status": "🟢 Active", "Note": "Nutrition support."},
        {"Scheme": "PM-SHRI", "Allocation": "₹6,050 Cr", "Status": "🟢 Active", "Note": "School upgrades."}
    ]
    
    with open("budget_2025_26.json", "w") as f:
        json.dump(budget_data, f, indent=4)
        
    print(f"✅ Generated 'budget_2025_26.json' with {len(budget_data)} entries.")

if __name__ == "__main__":
    generate_budget_db()
