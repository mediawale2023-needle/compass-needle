import json
import random

def generate_discovery_db():
    print("🛰️ Minting CSR Discovery & Gap Analysis Database...")

    districts = ["Nagpur", "Pune", "Aurangabad", "Thane", "Nashik", "Mumbai South"]

    # 1. The "Whales" (Big Remote Spenders)
    remote_giants = [
        "Infosys Foundation", "HDFC Life", "ICICI Lombard", "Tech Mahindra Foundation", 
        "Axis Bank Foundation", "SBI Life", "Reliance Foundation", "Tata Trusts", "Wipro Cares"
    ]

    # 2. The "Locals" (Have Factories/Offices in these districts)
    local_ops_map = {
        "Mahindra & Mahindra": ["Mumbai South", "Pune", "Nashik"],
        "Bajaj Auto": ["Pune", "Aurangabad"],
        "Siemens Ltd": ["Thane", "Mumbai South"],
        "MahaGenco": ["Nagpur", "Chandrapur"],
        "Western Coalfields": ["Nagpur", "Chandrapur"],
        "Skoda Auto": ["Aurangabad", "Pune"],
        "Larsen & Toubro": ["Mumbai South", "Thane", "Pune"]
    }

    db = []

    for dist in districts:
        # A. REMOTE SPENDERS (Voluntary)
        for comp in remote_giants:
            if random.random() > 0.6: 
                base_spend = random.randint(25, 100)
                entry = {
                    "District": dist,
                    "Company": comp,
                    "Type": "🌍 Remote (No Office)",
                    "Sector": random.choice(["Education", "Healthcare", "Skill Dev", "Water"]),
                    "History": {
                        "2022-23": f"₹{base_spend} L",
                        "2023-24": f"₹{int(base_spend * 1.1)} L",
                        "2024-25": f"₹{int(base_spend * 0.9)} L"
                    },
                    "Total_3Y": f"₹{int(base_spend * 3)} Lakhs",
                    "Status": "✅ Active Spender",
                    "Gap_Analysis": "Good Partner"
                }
                db.append(entry)

        # B. LOCAL OPERATORS (Mandatory - The Trap)
        for comp, present_districts in local_ops_map.items():
            if dist in present_districts:
                # 30% chance they are SKIPPING this district (The Violation)
                is_violator = random.random() < 0.3
                
                if is_violator:
                    entry = {
                        "District": dist,
                        "Company": comp,
                        "Type": "🏭 Local (Has Factory/Office)",
                        "Sector": "N/A",
                        "History": {
                            "2022-23": "₹0",
                            "2023-24": "₹0",
                            "2024-25": "₹0"
                        },
                        "Total_3Y": "₹0",
                        "Status": "🚨 ZERO SPEND (Violation)",
                        "Gap_Analysis": "CRITICAL: Operation exists but Funds missing."
                    }
                else:
                    base_spend = random.randint(50, 400)
                    entry = {
                        "District": dist,
                        "Company": comp,
                        "Type": "🏭 Local (Has Factory/Office)",
                        "Sector": random.choice(["Infra", "Sanitation", "Environment"]),
                        "History": {
                            "2022-23": f"₹{base_spend} L",
                            "2023-24": f"₹{base_spend} L",
                            "2024-25": f"₹{base_spend + 50} L"
                        },
                        "Total_3Y": f"₹{base_spend * 3 + 50} Lakhs",
                        "Status": "✅ Compliant",
                        "Gap_Analysis": "Good Standing"
                    }
                db.append(entry)

    with open("csr_discovery.json", "w") as f:
        json.dump(db, f, indent=4)
    
    print(f"✅ Generated {len(db)} CSR records with Gap Analysis.")

if __name__ == "__main__":
    generate_discovery_db()
