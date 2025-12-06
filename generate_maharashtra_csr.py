import json
import random

def generate_maharashtra_csr_db():
    print("🏭 Minting Maharashtra CSR Intelligence Database...")

    # Full list of 36 Maharashtra Districts
    districts = [
        "Ahmednagar", "Akola", "Amravati", "Aurangabad", "Beed", "Bhandara", "Buldhana",
        "Chandrapur", "Dhule", "Gadchiroli", "Gondia", "Hingoli", "Jalgaon", "Jalna",
        "Kolhapur", "Latur", "Mumbai City", "Mumbai Suburban", "Nagpur", "Nanded",
        "Nandurbar", "Nashik", "Osmanabad", "Palghar", "Parbhani", "Pune", "Raigad",
        "Ratnagiri", "Sangli", "Satara", "Sindhudurg", "Solapur", "Thane", "Wardha",
        "Washim", "Yavatmal"
    ]

    # Major Companies with likely HQ/Factory locations in MH
    # (Company Name, [List of Local Districts], Base Budget Cr)
    companies = [
        ("Reliance Industries", ["Mumbai City", "Mumbai Suburban", "Raigad", "Nagpur"], 1185),
        ("Tata Consultancy Services", ["Mumbai City", "Mumbai Suburban", "Pune", "Thane"], 800),
        ("Mahindra & Mahindra", ["Mumbai City", "Mumbai Suburban", "Nashik", "Pune", "Nagpur"], 110),
        ("Bajaj Auto", ["Pune", "Aurangabad"], 140),
        ("HDFC Bank", ["Mumbai City", "Mumbai Suburban"], 795),
        ("Larsen & Toubro", ["Mumbai City", "Mumbai Suburban", "Pune", "Ahmednagar"], 400),
        ("JSW Steel", ["Mumbai City", "Thane", "Raigad"], 190),
        ("Hindustan Unilever", ["Mumbai City", "Mumbai Suburban"], 160),
        ("Infosys Foundation", ["Pune", "Nagpur"], 520), # Large operations in Pune
        ("Wipro Cares", ["Pune"], 230),
        ("Siemens Ltd", ["Mumbai City", "Thane", "Aurangabad"], 90),
        ("MahaGenco", ["Nagpur", "Chandrapur", "Nashik"], 150), # State PSU
        ("Western Coalfields", ["Nagpur", "Chandrapur", "Yavatmal"], 200), # PSU
        ("Sun Pharma", ["Mumbai Suburban", "Ahmednagar"], 80),
        ("Adani Foundation", ["Mumbai City", "Gondia", "Tiroda"], 450)
    ]
    
    # Generic "Remote Giants" (Banks, IT, Insurance) likely to spend anywhere
    remote_only_giants = [
        "ICICI Lombard", "HDFC Life", "SBI Life", "Axis Bank Foundation", 
        "Tech Mahindra Foundation", "Kotak Mahindra Bank", "Bill & Melinda Gates Foundation"
    ]

    db = []

    for dist in districts:
        # 1. Process Major Industrial Players
        for comp_name, local_hubs, budget in companies:
            # Determine if Local or Remote for THIS district
            if dist in local_hubs:
                is_local = True
                type_label = "🏭 Local (Factory/Office)"
                # Higher chance of spend if local
                active_chance = 0.9 
            else:
                is_local = False
                type_label = "🌍 Remote (No Office)"
                # Lower chance of spend if remote
                active_chance = 0.3

            if random.random() < active_chance:
                # Calculate spend
                spend_base = random.randint(10, 200) if is_local else random.randint(5, 50)
                
                # Check for "Zero Spend" Violation (Local only)
                status = "Active"
                if is_local and random.random() < 0.2: # 20% chance of violation
                    spend_base = 0
                    status = "🚨 ZERO SPEND (Violation)"
                
                entry = {
                    "District": dist,
                    "Company": comp_name,
                    "Type": type_label,
                    "Sector": random.choice(["Education", "Health", "Rural Dev", "Skill Dev", "Water"]),
                    "Spend_History": {
                        "2022_23": f"₹{spend_base} L",
                        "2023_24": f"₹{int(spend_base * 1.1)} L",
                        "2024_25": f"₹{int(spend_base * 0.9)} L"
                    },
                    "Total_3Y": f"₹{int(spend_base * 3)} Lakhs",
                    "Status": status
                }
                db.append(entry)

        # 2. Process Remote-Only Giants (The "Bonus" Money)
        for comp_name in remote_only_giants:
            if random.random() < 0.15: # 15% chance they picked this district
                spend_base = random.randint(10, 80)
                entry = {
                    "District": dist,
                    "Company": comp_name,
                    "Type": "🌍 Remote (No Office)",
                    "Sector": random.choice(["Digital Literacy", "Healthcare", "Financial Inclusion"]),
                    "Spend_History": {
                        "2022_23": f"₹{spend_base} L",
                        "2023_24": f"₹{int(spend_base * 1.1)} L",
                        "2024_25": f"₹{int(spend_base * 1.0)} L"
                    },
                    "Total_3Y": f"₹{int(spend_base * 3.1)} Lakhs",
                    "Status": "✅ Voluntary Spender"
                }
                db.append(entry)

    with open("csr_db.json", "w") as f:
        json.dump(db, f, indent=4)
    
    print(f"✅ Generated CSR Intelligence for {len(db)} projects across {len(districts)} Maharashtra districts.")

if __name__ == "__main__":
    generate_maharashtra_csr_db()
