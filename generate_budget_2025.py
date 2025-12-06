import json

def generate_budget_db():
    print("💰 Generating Union Budget 2025-26 Database...")
    
    # Data sourced from Union Budget 2025-26 Documents & PIB Highlights
    budget_data = [
        {
            "Scheme": "Mahatma Gandhi National Rural Employment Guarantee Scheme (MGNREGS)",
            "Ministry": "Ministry of Rural Development",
            "Allocation_2025_26": "₹86,000 Cr",
            "Change_from_Prev": "0% (Same as 2024-25)",
            "Status": "🟡 Funds Stagnant",
            "Notes": "Allocation unchanged despite deficit reports. Demand-driven scheme."
        },
        {
            "Scheme": "Jal Jeevan Mission (JJM)",
            "Ministry": "Ministry of Jal Shakti",
            "Allocation_2025_26": "₹67,000 Cr",
            "Change_from_Prev": "Significant Increase",
            "Status": "🟢 High Liquidity",
            "Notes": "Mission extended to 2028. Focus on functional tap connections."
        },
        {
            "Scheme": "Pradhan Mantri Awas Yojana (Urban)",
            "Ministry": "Ministry of Housing & Urban Affairs",
            "Allocation_2025_26": "₹26,170 Cr", 
            "Change_from_Prev": "Increased",
            "Status": "🟢 Open",
            "Notes": "Part of ₹10 lakh crore investment under PMAY 2.0."
        },
        {
            "Scheme": "Pradhan Mantri Awas Yojana (Rural)",
            "Ministry": "Ministry of Rural Development",
            "Allocation_2025_26": "₹54,500 Cr",
            "Change_from_Prev": "Stable",
            "Status": "🟢 Open",
            "Notes": "Continued focus on rural housing completion."
        },
        {
            "Scheme": "PM-KISAN",
            "Ministry": "Ministry of Agriculture",
            "Allocation_2025_26": "₹60,000 Cr",
            "Change_from_Prev": "Stable",
            "Status": "🟢 Active",
            "Notes": "Direct benefit transfer to farmers continues."
        },
        {
            "Scheme": "Production Linked Incentive (PLI) Scheme (Electronics)",
            "Ministry": "Ministry of Electronics & IT",
            "Allocation_2025_26": "₹9,000 Cr",
            "Change_from_Prev": "+56% Increase",
            "Status": "🟢 Very High Liquidity",
            "Notes": "Major boost for electronics manufacturing."
        },
        {
            "Scheme": "Production Linked Incentive (PLI) Scheme (Textiles)",
            "Ministry": "Ministry of Textiles",
            "Allocation_2025_26": "₹1,148 Cr",
            "Change_from_Prev": "Massive Increase (from ₹45 Cr)",
            "Status": "🟢 High Opportunity",
            "Notes": "Huge jump in allocation. Good time to apply."
        },
         {
            "Scheme": "Saksham Anganwadi and Poshan 2.0",
            "Ministry": "Ministry of Women and Child Development",
            "Allocation_2025_26": "₹21,200 Cr",
            "Change_from_Prev": "Stable",
            "Status": "🟢 Active",
            "Notes": "Integrated nutrition support programme."
        },
        {
             "Scheme": "National Health Mission",
             "Ministry": "Ministry of Health and Family Welfare",
             "Allocation_2025_26": "₹38,000 Cr",
             "Change_from_Prev": "Increased",
             "Status": "🟢 Active",
             "Notes": "Core health infrastructure funding."
        },
        {
            "Scheme": "Prime Minister's Schools for Rising India (PM-SHRI)",
            "Ministry": "Ministry of Education",
            "Allocation_2025_26": "₹6,050 Cr",
             "Change_from_Prev": "Increased",
            "Status": "🟢 Active",
            "Notes": "Upgradation of schools."
        }
    ]
    
    with open("budget_2025_26.json", "w") as f:
        json.dump(budget_data, f, indent=4)
        
    print(f"✅ Success! Generated 'budget_2025_26.json' with {len(budget_data)} schemes.")

if __name__ == "__main__":
    generate_budget_db()
