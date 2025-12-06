import json
import random

def generate_maharashtra_csr_db():
    print("🏭 Minting Full Maharashtra Database (36 Districts)...")

    districts = [
        "Ahmednagar", "Akola", "Amravati", "Aurangabad", "Beed", "Bhandara", "Buldhana",
        "Chandrapur", "Dhule", "Gadchiroli", "Gondia", "Hingoli", "Jalgaon", "Jalna",
        "Kolhapur", "Latur", "Mumbai City", "Mumbai Suburban", "Nagpur", "Nanded",
        "Nandurbar", "Nashik", "Osmanabad", "Palghar", "Parbhani", "Pune", "Raigad",
        "Ratnagiri", "Sangli", "Satara", "Sindhudurg", "Solapur", "Thane", "Wardha",
        "Washim", "Yavatmal"
    ]

    # 1. National Giants (These spend everywhere - Guarantees data for every district)
    national_giants = [
        ("Reliance Foundation", ["Education", "Health"], 1500),
        ("Tata Trusts", ["Rural Dev", "Health"], 1200),
        ("HDFC Bank Parivartan", ["Education", "Water"], 900),
        ("SBI Foundation", ["Health", "Skill Dev"], 600)
    ]

    # 2. Industrial Players (Specific Locations)
    local_players = [
        ("Mahindra & Mahindra", ["Mumbai City", "Mumbai Suburban", "Nashik", "Pune", "Nagpur"], 110),
        ("Bajaj Auto", ["Pune", "Aurangabad"], 140),
        ("JSW Steel", ["Mumbai City", "Thane", "Raigad"], 190),
        ("MahaGenco", ["Nagpur", "Chandrapur", "Nashik"], 150),
        ("Western Coalfields", ["Nagpur", "Chandrapur", "Yavatmal"], 200),
        ("Sun Pharma", ["Mumbai Suburban", "Ahmednagar"], 80)
    ]

    db = []

    for dist in districts:
        # A. GUARANTEE: Add National Giants to EVERY district (Remote Spenders)
        for name, focus, budget in national_giants:
            spend_base = random.randint(15, 80)
            db.append({
                "District": dist,
                "Company": name,
                "Type": "🌍 Remote (No Office)",
                "Sector": random.choice(focus),
                "Spend_History": {
                    "2022-23": f"₹{spend_base} L",
                    "2023-24": f"₹{int(spend_base * 1.1)} L",
                    "2024-25": f"₹{int(spend_base * 1.05)} L"
                },
                "Total_3Y": f"₹{int(spend_base * 3.15)} Lakhs",
                "Status": "✅ Active Spender",
                "Gap_Analysis": "Opportunity for Upscale"
            })

        # B. ADD LOCALS: Only if they match the district
        for name, locs, budget in local_players:
            if dist in locs:
                # 20% Chance of Zero Spend Violation
                is_violator = random.random() < 0.2
                if is_violator:
                     db.append({
                        "District": dist,
                        "Company": name,
                        "Type": "🏭 Local (Factory/Office)",
                        "Sector": "N/A",
                        "Spend_History": {"2022-23": "₹0", "2023-24": "₹0", "2024-25": "₹0"},
                        "Total_3Y": "₹0",
                        "Status": "🚨 ZERO SPEND (Violation)",
                        "Gap_Analysis": "CRITICAL: Operation exists but Funds missing."
                    })
                else:
                    spend = random.randint(50, 300)
                    db.append({
                        "District": dist,
                        "Company": name,
                        "Type": "🏭 Local (Factory/Office)",
                        "Sector": "Community Dev",
                        "Spend_History": {
                            "2022-23": f"₹{spend} L",
                            "2023-24": f"₹{spend} L",
                            "2024-25": f"₹{spend} L"
                        },
                        "Total_3Y": f"₹{spend * 3} Lakhs",
                        "Status": "✅ Compliant",
                        "Gap_Analysis": "Good Standing"
                    })

    with open("csr_db.json", "w") as f:
        json.dump(db, f, indent=4)
    
    print(f"✅ SUCCESS! Generated {len(db)} records covering ALL {len(districts)} districts.")

if __name__ == "__main__":
    generate_maharashtra_csr_db()
