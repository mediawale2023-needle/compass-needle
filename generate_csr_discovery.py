import json
import random

def generate_full_maharashtra_db():
    print("🏭 Generating Correct CSR Database...")

    districts = [
        "Ahmednagar", "Akola", "Amravati", "Aurangabad", "Beed", "Bhandara", "Buldhana",
        "Chandrapur", "Dhule", "Gadchiroli", "Gondia", "Hingoli", "Jalgaon", "Jalna",
        "Kolhapur", "Latur", "Mumbai City", "Mumbai Suburban", "Nagpur", "Nanded",
        "Nandurbar", "Nashik", "Osmanabad", "Palghar", "Parbhani", "Pune", "Raigad",
        "Ratnagiri", "Sangli", "Satara", "Sindhudurg", "Solapur", "Thane", "Wardha",
        "Washim", "Yavatmal"
    ]

    national_giants = [
        ("Reliance Foundation", ["Education", "Health"], 1500),
        ("Tata Trusts", ["Cancer Care", "Education"], 1200),
        ("HDFC Parivartan", ["Rural Dev", "Education"], 900),
        ("SBI Foundation", ["Health", "Skill Dev"], 600)
    ]
    
    local_ops_map = {
        "Mahindra & Mahindra": ["Mumbai City", "Mumbai Suburban", "Nashik", "Pune", "Nagpur"],
        "Bajaj Auto": ["Pune", "Aurangabad"],
        "Siemens Ltd": ["Thane", "Mumbai South"],
        "MahaGenco": ["Nagpur", "Chandrapur", "Nashik"],
        "Western Coalfields": ["Nagpur", "Chandrapur"],
        "JSW Steel": ["Mumbai City", "Raigad"]
    }

    db = []

    for dist in districts:
        # A. Remote Spenders
        for name, focus, budget in national_giants:
            if random.random() < 0.7:
                base = random.randint(10, 50)
                db.append({
                    "District": dist,
                    "Company": name,
                    "Type": "🌍 Remote (No Office)",
                    "Sector": random.choice(focus),
                    "Spend_History": {
                        "2022-23": f"₹{base} L",
                        "2023-24": f"₹{int(base*1.1)} L",
                        "2024-25": f"₹{int(base*1.2)} L"
                    },
                    "Total_3Y": f"₹{int(base*3.3)} Lakhs",
                    "Status": "✅ Active Spender",
                    "Gap_Analysis": "Opportunity to Upscale"
                })

        # B. Local Spenders
        for name, locs in local_ops_map.items():
            if dist in locs:
                is_violator = random.random() < 0.3
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
                    base = random.randint(50, 200)
                    db.append({
                        "District": dist,
                        "Company": name,
                        "Type": "🏭 Local (Factory/Office)",
                        "Sector": "Community Dev",
                        "Spend_History": {
                            "2022-23": f"₹{base} L",
                            "2023-24": f"₹{base} L",
                            "2024-25": f"₹{base} L"
                        },
                        "Total_3Y": f"₹{base * 3} Lakhs",
                        "Status": "✅ Compliant",
                        "Gap_Analysis": "Good Standing"
                    })

    with open("csr_discovery.json", "w") as f:
        json.dump(db, f, indent=4)
    
    print(f"✅ SUCCESS! Generated correct database with 'Total_3Y' keys.")

if __name__ == "__main__":
    generate_full_maharashtra_db()
