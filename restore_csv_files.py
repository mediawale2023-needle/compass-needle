import csv

# Data for 16 Ministries (Simplified for restoration)
data = {
    "SCHEMES.xlsx - AGRICULTURE.csv": [
        ["Scheme", "Ministry", "Objective", "Classification"],
        ["PM-KISAN", "Ministry of Agriculture", "Income support", "Financial Assistance"],
        ["PMFBY", "Ministry of Agriculture", "Crop Insurance", "Financial Assistance"],
        ["PMKSY", "Ministry of Agriculture", "Irrigation", "Agricultural Development"]
    ],
    "SCHEMES.xlsx - JAL SHAKTI.csv": [
        ["Scheme Name", "Ministry", "Objective"],
        ["Jal Jeevan Mission (JJM)", "Ministry of Jal Shakti", "Tap water for all"],
        ["Namami Gange", "Ministry of Jal Shakti", "Clean Ganga"],
        ["Swachh Bharat Mission (Gramin)", "Ministry of Jal Shakti", "Sanitation"]
    ],
    "SCHEMES.xlsx - HEAVY INDUSTRY.csv": [
        ["Scheme", "Ministry", "Objective"],
        ["FAME India", "Ministry of Heavy Industries", "EV Adoption"],
        ["PLI Auto", "Ministry of Heavy Industries", "Manufacturing Boost"]
    ],
    "SCHEMES.xlsx - EDUCATION.csv": [
        ["Scheme", "Ministry", "Objective"],
        ["Samagra Shiksha", "Ministry of Education", "School Education"],
        ["PM-SHRI", "Ministry of Education", "School Upgradation"],
        ["Mid-Day Meal", "Ministry of Education", "Nutrition"]
    ],
    "SCHEMES.xlsx - POWER.csv": [
        ["Scheme", "Ministry"],
        ["Deendayal Upadhyaya Gram Jyoti", "Ministry of Power"],
        ["IPDS", "Ministry of Power"]
    ],
    "SCHEMES.xlsx - RENEWABLE ENERGY.csv": [
        ["Scheme", "Ministry"],
        ["PM-KUSUM", "Ministry of New and Renewable Energy"],
        ["Grid Connected Rooftop Solar", "Ministry of New and Renewable Energy"]
    ],
    "SCHEMES.xlsx - HEALTH.csv": [
        ["Scheme", "Ministry"],
        ["Ayushman Bharat", "Ministry of Health and Family Welfare"],
        ["National Health Mission", "Ministry of Health and Family Welfare"]
    ],
    "SCHEMES.xlsx - URBAN.csv": [
        ["Scheme", "Ministry"],
        ["PMAY-Urban", "Ministry of Housing and Urban Affairs"],
        ["AMRUT", "Ministry of Housing and Urban Affairs"],
        ["Smart Cities", "Ministry of Housing and Urban Affairs"]
    ],
    "SCHEMES.xlsx - WOMEN AND CHILD.csv": [
        ["Scheme", "Ministry"],
        ["Saksham Anganwadi", "Ministry of Women and Child Development"],
        ["Mission Shakti", "Ministry of Women and Child Development"]
    ],
    "SCHEMES.xlsx - SOCIAL JUSTICE.csv": [
        ["Scheme", "Ministry"],
        ["PM-DAKSH", "Ministry of Social Justice and Empowerment"],
        ["SRESHTA", "Ministry of Social Justice and Empowerment"]
    ],
    "SCHEMES.xlsx - SPORTS.csv": [
        ["Scheme", "Ministry"],
        ["Khelo India", "Ministry of Youth Affairs and Sports"],
        ["Fit India", "Ministry of Youth Affairs and Sports"]
    ],
    "SCHEMES.xlsx - MSME.csv": [
        ["Scheme", "Ministry"],
        ["PMEGP", "Ministry of MSME"],
        ["SFURTI", "Ministry of MSME"]
    ],
    "SCHEMES.xlsx - TEXTILES.csv": [
        ["Scheme", "Ministry"],
        ["PM MITRA", "Ministry of Textiles"],
        ["Samarth", "Ministry of Textiles"]
    ],
    "SCHEMES.xlsx - FOOD PROCESSING.csv": [
        ["Scheme", "Ministry"],
        ["PM Kisan Sampada", "Ministry of Food Processing Industries"],
        ["PMFME", "Ministry of Food Processing Industries"]
    ],
    "SCHEMES.xlsx - PORTS.csv": [
        ["Scheme", "Ministry"],
        ["Sagarmala", "Ministry of Ports, Shipping and Waterways"]
    ],
    "SCHEMES.xlsx - CONSUMER AFFAIRS.csv": [
        ["Scheme", "Ministry"],
        ["Price Stabilization Fund", "Ministry of Consumer Affairs"]
    ]
}

for filename, rows in data.items():
    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    print(f"✅ Restored {filename}")

