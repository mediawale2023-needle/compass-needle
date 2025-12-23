import json
import random

def generate_csr_data():
    print("🕵️ Generating 3-Year CSR Forensic Data...")

    # The Target Districts (Customize for your demo)
    districts = ["Nagpur", "Pune", "Aurangabad", "Thane", "Nashik", "Mumbai South"]

    # 1. The "Whales" (Big Remote Spenders)
    # Companies that might spend in these districts but are HQ'd elsewhere
    remote_giants = [
        "Infosys Foundation", "HDFC Life", "ICICI Lombard", "Tech Mahindra Foundation", 
        "Axis Bank Foundation", "SBI Life", "Reliance Foundation", "Tata Trusts", "Wipro Cares"
    ]

    # 2. The "Locals" (Have factories/offices)
    local_ops = ["Mahindra & Mahindra", "Bajaj Auto", "Siemens Ltd", "MahaGenco", "Western Coalfields"]

    db = []

    for dist in districts:
        # A. Create Remote Spenders (The Opportunity)
        for comp in remote_giants:
            if random.random() > 0.6: # 40% chance they are active here
                base_spend = random.randint(25, 100)
                entry = {
                    "District": dist,
                    "Company": comp,
                    "Type": "🌍 Remote (No Office)",
                    "Sector": random.choice(["Education", "Healthcare", "Skill Dev", "Water"]),
                    "Spend_History": {
                        "2022_23": f"₹{base_spend} L",
                        "2023_24": f"₹{int(base_spend * 1.1)} L",
                        "2024_25": f"₹{int(base_spend * 0.9)} L"
                    },
                    "Total_3Y": f"₹{int(base_spend * 3)} Lakhs",
                    "Status": "Active"
                }
                db.append(entry)

        # B. Create Local Spenders (The Obligation)
        for comp in local_ops:
            if random.random() > 0.3:
                base_spend = random.randint(50, 400)
                entry = {
                    "District": dist,
                    "Company": comp,
                    "Type": "🏭 Local (Factory/Office)",
                    "Sector": random.choice(["Infra", "Sanitation", "Environment"]),
                    "Spend_History": {
                        "2022_23": f"₹{base_spend} L",
                        "2023_24": f"₹{base_spend} L",
                        "2024_25": f"₹{base_spend + 50} L"
                    },
                    "Total_3Y": f"₹{base_spend * 3 + 50} Lakhs",
                    "Status": "Mandatory"
                }
                db.append(entry)

    with open("csr_db.json", "w") as f:
        json.dump(db, f, indent=4)
    
    print(f"✅ Generated forensic data for {len(db)} projects across {len(districts)} districts.")

if __name__ == "__main__":
    generate_csr_data()