import json
import random

def generate_ngo_db():
    print("🤝 Building Trusted NGO Partner Network...")

    ngos = [
        ("Seva Sadan Foundation", "Education", "Green", "Valid"),
        ("Gram Vikas Samiti", "Rural Dev", "Green", "Valid"),
        ("Urban Uplift Trust", "Skill Dev", "Red", "CSR-1 Expired"),
        ("Jal Shakti Abhiyan Group", "Water", "Green", "Valid"),
        ("Mahila Udyog Manch", "Women Empowerment", "Green", "Valid"),
        ("Bright Future Society", "Education", "Yellow", "FCRA Pending"),
        ("Green Earth Initiative", "Environment", "Green", "Valid"),
        ("Jan Kalyan Trust", "Health", "Red", "Blacklisted by NITI Aayog"),
        ("Tech for Rural India", "Technology", "Green", "Valid"),
        ("Animal Care Unit", "Animal Welfare", "Yellow", "Audit Pending")
    ]

    db = []
    for name, sector, risk, status in ngos:
        entry = {
            "NGO_Name": name,
            "Darpan_ID": f"MH/2023/{random.randint(10000,99999)}",
            "CSR_1_Number": f"CSR{random.randint(1000000,9999999)}",
            "Sector": sector,
            "Key_Contact": "Director",
            "Phone": f"+91-98{random.randint(10000000, 99999999)}",
            "Risk_Level": risk,
            "Compliance_Status": status,
            "Last_Audit": f"{random.randint(2021, 2024)}-03-31",
            "Capabilities": f"Can handle projects up to ₹{random.randint(10, 50)} Lakhs."
        }
        db.append(entry)

    with open("ngo_db.json", "w") as f:
        json.dump(db, f, indent=4)
    
    print(f"✅ Vetted {len(db)} Local NGOs.")

if __name__ == "__main__":
    generate_ngo_db()
