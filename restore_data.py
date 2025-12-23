cat << 'EOF' > restore_data.py
import csv
import os

# Data Dictionary: Filename -> List of Rows
data_map = {
    "SCHEMES.xlsx - AGRICULTURE.csv": [
        ["Scheme Name", "Ministry", "Objective", "Classification"],
        ["Pradhan Mantri KISAN Samman Nidhi (PM-KISAN)", "Ministry of Agriculture", "Income support for farmers", "Financial Assistance"],
        ["Pradhan Mantri Fasal Bima Yojana (PMFBY)", "Ministry of Agriculture", "Crop insurance", "Financial Assistance"],
        ["Pradhan Mantri Krishi Sinchai Yojana (PMKSY)", "Ministry of Agriculture", "Irrigation coverage", "Infrastructure"],
        ["National Bamboo Mission", "Ministry of Agriculture", "Bamboo sector growth", "Development"],
        ["Paramparagat Krishi Vikas Yojana", "Ministry of Agriculture", "Organic farming", "Sustainability"]
    ],
    "SCHEMES.xlsx - HEAVY INDUSTRY.csv": [
        ["Scheme", "Ministry", "Objective"],
        ["FAME-India Scheme", "Ministry of Heavy Industries", "Electric Vehicle adoption", "Subsidy"],
        ["PLI for Automobile", "Ministry of Heavy Industries", "Manufacturing boost", "Incentive"],
        ["PLI for ACC Battery", "Ministry of Heavy Industries", "Battery manufacturing", "Incentive"]
    ],
    "SCHEMES.xlsx - JAL SHAKTI.csv": [
        ["Scheme Name", "Ministry", "Objective"],
        ["Jal Jeevan Mission (JJM)", "Ministry of Jal Shakti", "Tap water for every rural home", "Infrastructure"],
        ["Namami Gange Programme", "Ministry of Jal Shakti", "Clean Ganga", "Sanitation"],
        ["Swachh Bharat Mission (Gramin)", "Ministry of Jal Shakti", "Rural sanitation", "Sanitation"]
    ],
    "SCHEMES.xlsx - EDUCATION.csv": [
        ["Scheme", "Ministry", "Objective"],
        ["Samagra Shiksha", "Ministry of Education", "Holistic school education", "Education"],
        ["PM-SHRI", "Ministry of Education", "School upgradation", "Infrastructure"],
        ["Mid-Day Meal Scheme", "Ministry of Education", "Nutritional support", "Health"]
    ],
    "SCHEMES.xlsx - WOMEN AND CHILD.csv": [
        ["Scheme", "Ministry", "Objective"],
        ["Saksham Anganwadi", "Ministry of Women and Child Development", "Early childhood care", "Welfare"],
        ["Mission Shakti", "Ministry of Women and Child Development", "Women empowerment", "Welfare"],
        ["Mission Vatsalya", "Ministry of Women and Child Development", "Child protection", "Welfare"]
    ],
    "SCHEMES.xlsx - RENEWABLE ENERGY.csv": [
        ["Scheme", "Ministry", "Objective"],
        ["PM-KUSUM", "Ministry of New and Renewable Energy", "Solar pumps for farmers", "Energy"],
        ["Rooftop Solar Programme", "Ministry of New and Renewable Energy", "Residential solar", "Energy"],
        ["National Green Hydrogen Mission", "Ministry of New and Renewable Energy", "Green fuel production", "Energy"]
    ],
    "SCHEMES.xlsx - HEALTH.csv": [
        ["Scheme", "Ministry", "Objective"],
        ["Ayushman Bharat (PMJAY)", "Ministry of Health", "Health insurance", "Health"],
        ["National Health Mission", "Ministry of Health", "Rural/Urban health infra", "Infrastructure"]
    ],
    "SCHEMES.xlsx - URBAN .csv": [
        ["Scheme", "Ministry", "Objective"],
        ["PMAY-Urban", "Ministry of Housing", "Housing for all", "Infrastructure"],
        ["AMRUT", "Ministry of Housing", "Urban rejuvenation", "Infrastructure"],
        ["Smart Cities Mission", "Ministry of Housing", "Urban development", "Infrastructure"],
        ["PM SVANidhi", "Ministry of Housing", "Street vendor loans", "Financial Assistance"]
    ],
    "SCHEMES.xlsx - POWER.csv": [
        ["Scheme", "Ministry", "Objective"],
        ["Deendayal Upadhyaya Gram Jyoti Yojana", "Ministry of Power", "Rural electrification", "Infrastructure"],
        ["Integrated Power Development Scheme", "Ministry of Power", "Urban power distribution", "Infrastructure"]
    ],
    "SCHEMES.xlsx - PORTS.csv": [
        ["Scheme", "Ministry", "Objective"],
        ["Sagarmala", "Ministry of Ports", "Port-led development", "Infrastructure"]
    ],
    "SCHEMES.xlsx - SOCIAL JUSTICE.csv": [
        ["Scheme", "Ministry", "Objective"],
        ["PM-DAKSH", "Ministry of Social Justice", "Skill development", "Skilling"],
        ["SRESHTA", "Ministry of Social Justice", "Education for SC students", "Education"]
    ],
    "SCHEMES.xlsx - SPORTS.csv": [
        ["Scheme", "Ministry", "Objective"],
        ["Khelo India", "Ministry of Sports", "Sports development", "Sports"]
    ],
    "SCHEMES.xlsx - MSME.csv": [
        ["Scheme", "Ministry", "Objective"],
        ["PMEGP", "Ministry of MSME", "Employment generation", "Employment"],
        ["SFURTI", "Ministry of MSME", "Traditional industries", "Development"]
    ],
    "SCHEMES.xlsx - FOOD PROCESSING.csv": [
        ["Scheme", "Ministry", "Objective"],
        ["PM Kisan Sampada Yojana", "Ministry of Food Processing", "Supply chain infra", "Infrastructure"],
        ["PMFME", "Ministry of Food Processing", "Micro food enterprises", "Financial Assistance"]
    ],
    "SCHEMES.xlsx - MINORITY AFFAIRS.csv": [
        ["Scheme", "Ministry", "Objective"],
        ["PM Jan Vikas Karyakram", "Ministry of Minority Affairs", "Minority area development", "Infrastructure"]
    ],
    "SCHEMES.xlsx - CONSUMER AFFAIRS.csv": [
        ["Scheme", "Ministry", "Objective"],
        ["Price Stabilization Fund", "Ministry of Consumer Affairs", "Buffer stock management", "Welfare"]
    ],
    "SCHEMES.xlsx - TEXTILES.csv": [
        ["Scheme", "Ministry", "Objective"],
        ["PM MITRA", "Ministry of Textiles", "Textile parks", "Infrastructure"],
        ["Samarth", "Ministry of Textiles", "Skill development", "Skilling"]
    ]
}

print("📂 Restoring CSV Files...")
for filename, rows in data_map.items():
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    print(f"   ✅ Created: {filename}")

print("\n🎉 Restoration Complete. Now run 'final_data_build.py'.")
EOF