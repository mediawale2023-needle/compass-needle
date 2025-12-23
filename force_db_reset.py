import json
import os

def reset_database():
    print("🔧 FORCE RESETTING DATABASE...")

    # --- HARDCODED MASTER DATA (Source of Truth) ---
    # This list contains schemes from all your CSVs + Verified 2025-26 Budget Data
    DATA = [
        # --- AGRICULTURE ---
        {
            "Scheme": "Pradhan Mantri KISAN Samman Nidhi (PM-KISAN)",
            "Ministry": "Ministry of Agriculture & Farmers Welfare",
            "Description": "Income support of Rs 6,000/- per year to all landholding farmer families.",
            "Focus": ["Farmers", "Financial Assistance"],
            "Budget_Alloc": "₹60,000 Cr",
            "Budget_Status": "🟢 Active",
            "Budget_Note": "Stable allocation for DBT.",
            "Grant": "₹6,000 / year",
            "Eligibility": "Landholding farmer families",
            "Documents": "Aadhaar, Land Record, Bank Account",
            "Process": "pmkisan.gov.in"
        },
        {
            "Scheme": "Pradhan Mantri Fasal Bima Yojana (PMFBY)",
            "Ministry": "Ministry of Agriculture & Farmers Welfare",
            "Description": "Comprehensive crop insurance to cover yield losses.",
            "Focus": ["Farmers", "Insurance"],
            "Budget_Alloc": "₹12,242 Cr",
            "Budget_Status": "🟢 Active",
            "Budget_Note": "Crop Insurance Coverage.",
            "Grant": "Insurance Claim based on loss",
            "Eligibility": "Farmers with insured crops",
            "Documents": "Crop sowing certificate, Land docs",
            "Process": "Bank / CSC"
        },
        {
            "Scheme": "Pradhan Mantri Krishi Sinchai Yojana (PMKSY)",
            "Ministry": "Ministry of Agriculture & Farmers Welfare",
            "Description": "Focus on 'Per Drop More Crop' and irrigation coverage.",
            "Focus": ["Farmers", "Irrigation"],
            "Budget_Alloc": "₹11,391 Cr",
            "Budget_Status": "🟢 High Liquidity",
            "Budget_Note": "Includes micro-irrigation fund.",
            "Grant": "Subsidy on Drip/Sprinkler",
            "Eligibility": "Farmers with cultivable land",
            "Documents": "Land docs, Aadhaar",
            "Process": "State Agriculture Dept"
        },

        # --- JAL SHAKTI ---
        {
            "Scheme": "Jal Jeevan Mission (JJM)",
            "Ministry": "Ministry of Jal Shakti",
            "Description": "Functional Household Tap Connection (FHTC) to every rural household by 2024.",
            "Focus": ["Rural", "Water"],
            "Budget_Alloc": "₹67,000 Cr",
            "Budget_Status": "🟢 Very High Liquidity",
            "Budget_Note": "Mission extended. High priority.",
            "Grant": "Piped Water Connection",
            "Eligibility": "Rural Households",
            "Documents": "Aadhaar",
            "Process": "Gram Panchayat / VWSC"
        },
        {
            "Scheme": "Swachh Bharat Mission (Gramin)",
            "Ministry": "Ministry of Jal Shakti",
            "Description": "To accelerate the efforts to achieve universal sanitation coverage.",
            "Focus": ["Rural", "Sanitation"],
            "Budget_Alloc": "₹7,192 Cr",
            "Budget_Status": "🟢 Active",
            "Budget_Note": "Focus on ODF Plus.",
            "Grant": "₹12,000 for Toilet",
            "Eligibility": "Households without toilet",
            "Documents": "Aadhaar, Bank Account",
            "Process": "Gram Pradhan / Block Office"
        },

        # --- HOUSING & URBAN ---
        {
            "Scheme": "Pradhan Mantri Awas Yojana (Urban) 2.0",
            "Ministry": "Ministry of Housing and Urban Affairs",
            "Description": "Housing for All in urban areas. PMAY-U 2.0 covers middle class too.",
            "Focus": ["Urban", "Housing"],
            "Budget_Alloc": "₹26,170 Cr",
            "Budget_Status": "🟢 Very High Liquidity",
            "Budget_Note": "Includes new PMAY-U 2.0 allocation.",
            "Grant": "Interest Subsidy / Construction Aid",
            "Eligibility": "EWS/LIG/MIG families",
            "Documents": "Income Proof, Aadhaar",
            "Process": "pmaymis.gov.in"
        },
        {
            "Scheme": "Smart Cities Mission / AMRUT",
            "Ministry": "Ministry of Housing and Urban Affairs",
            "Description": "Providing basic services (water supply, sewerage, urban transport) to households.",
            "Focus": ["Urban", "Infrastructure"],
            "Budget_Alloc": "₹10,000 Cr",
            "Budget_Status": "🟢 Active",
            "Budget_Note": "Urban Rejuvenation projects.",
            "Grant": "Project based funding",
            "Eligibility": "Municipal Corporations",
            "Documents": "DPR",
            "Process": "State Urban Dept"
        },
        {
            "Scheme": "PM SVANidhi",
            "Ministry": "Ministry of Housing and Urban Affairs",
            "Description": "Micro-credit facility for street vendors.",
            "Focus": ["Urban", "Street Vendors"],
            "Budget_Alloc": "₹373 Cr",
            "Budget_Status": "🟢 Active",
            "Budget_Note": "Working capital loans.",
            "Grant": "Loan up to ₹50,000",
            "Eligibility": "Street Vendors",
            "Documents": "Vending Certificate",
            "Process": "pmsvanidhi.mohua.gov.in"
        },

        # --- RURAL DEVELOPMENT ---
        {
            "Scheme": "MGNREGA",
            "Ministry": "Ministry of Rural Development",
            "Description": "100 days of guaranteed wage employment.",
            "Focus": ["Rural", "Employment"],
            "Budget_Alloc": "₹86,000 Cr",
            "Budget_Status": "🟡 Stagnant",
            "Budget_Note": "Allocation unchanged.",
            "Grant": "Wage Employment",
            "Eligibility": "Rural Adults",
            "Documents": "Job Card",
            "Process": "Gram Panchayat"
        },
        {
            "Scheme": "Pradhan Mantri Awas Yojana (Gramin)",
            "Ministry": "Ministry of Rural Development",
            "Description": "Pucca houses with basic amenities for rural poor.",
            "Focus": ["Rural", "Housing"],
            "Budget_Alloc": "₹54,500 Cr",
            "Budget_Status": "🟢 High Liquidity",
            "Budget_Note": "Rural housing push.",
            "Grant": "₹1.2 Lakh + Labor",
            "Eligibility": "SECC List Beneficiaries",
            "Documents": "Aadhaar, Job Card",
            "Process": "AwaasSoft / Block Office"
        },

        # --- HEAVY INDUSTRIES / POWER ---
        {
            "Scheme": "PM E-DRIVE (FAME Replacement)",
            "Ministry": "Ministry of Heavy Industries",
            "Description": "Replaces FAME. Promotion of Electric Vehicles (2W, 3W, Ambulances).",
            "Focus": ["EV", "Transport"],
            "Budget_Alloc": "₹4,000 Cr",
            "Budget_Status": "🟢 New Scheme",
            "Budget_Note": "Replaces FAME India.",
            "Grant": "Subsidy on EV purchase",
            "Eligibility": "EV Buyers / Manufacturers",
            "Documents": "Purchase Proof",
            "Process": "Dealer / Portal"
        },
        {
            "Scheme": "PLI Scheme (Automobile & Components)",
            "Ministry": "Ministry of Heavy Industries",
            "Description": "Production Linked Incentive for Auto sector.",
            "Focus": ["Industry", "Manufacturing"],
            "Budget_Alloc": "₹2,819 Cr",
            "Budget_Status": "🟢 Active",
            "Budget_Note": "Manufacturing boost.",
            "Grant": "4-18% incentive on sales",
            "Eligibility": "Auto Manufacturers",
            "Documents": "Investment Proof",
            "Process": "Project Management Agency"
        },
        {
            "Scheme": "PM Surya Ghar: Muft Bijli Yojana",
            "Ministry": "Ministry of New and Renewable Energy",
            "Description": "Free electricity up to 300 units via Rooftop Solar.",
            "Focus": ["Energy", "Solar"],
            "Budget_Alloc": "₹20,000 Cr",
            "Budget_Status": "🟢 Massive Allocation",
            "Budget_Note": "Major budget focus.",
            "Grant": "Subsidy up to ₹78,000",
            "Eligibility": "Households",
            "Documents": "Electricity Bill, Roof Ownership",
            "Process": "pmsuryaghar.gov.in"
        },

        # --- EDUCATION ---
        {
            "Scheme": "Samagra Shiksha",
            "Ministry": "Ministry of Education",
            "Description": "Integrated Scheme for School Education.",
            "Focus": ["Education", "Students"],
            "Budget_Alloc": "₹41,250 Cr",
            "Budget_Status": "🟢 High Liquidity",
            "Budget_Note": "School Infra & Quality.",
            "Grant": "School Grants / Teacher Salary",
            "Eligibility": "Govt Schools",
            "Documents": "UDISE Data",
            "Process": "District Education Officer"
        },
        {
            "Scheme": "PM-SHRI Schools",
            "Ministry": "Ministry of Education",
            "Description": "Upgradation of 14,500 schools to model schools.",
            "Focus": ["Education", "Infrastructure"],
            "Budget_Alloc": "₹7,500 Cr",
            "Budget_Status": "🟢 Active",
            "Budget_Note": "Model School development.",
            "Grant": "Up to ₹2 Cr per school",
            "Eligibility": "Selected Govt Schools",
            "Documents": "School Development Plan",
            "Process": "Selection Portal"
        },

        # --- HEALTH ---
        {
            "Scheme": "Ayushman Bharat (PM-JAY)",
            "Ministry": "Ministry of Health and Family Welfare",
            "Description": "Health insurance cover of Rs. 5 lakhs per family.",
            "Focus": ["Health", "Insurance"],
            "Budget_Alloc": "₹9,406 Cr",
            "Budget_Status": "🟢 High",
            "Budget_Note": "Expanded coverage.",
            "Grant": "₹5 Lakh Cover",
            "Eligibility": "SECC 2011 Data / State List",
            "Documents": "Ration Card, Aadhaar",
            "Process": "Empanelled Hospital"
        },
        {
            "Scheme": "National Health Mission (NHM)",
            "Ministry": "Ministry of Health and Family Welfare",
            "Description": "Universal access to equitable, affordable & quality health care services.",
            "Focus": ["Health", "Rural"],
            "Budget_Alloc": "₹37,227 Cr",
            "Budget_Status": "🟢 Very High",
            "Budget_Note": "Core health funding.",
            "Grant": "Infra & Services",
            "Eligibility": "Public Health Facilities",
            "Documents": "State PIP",
            "Process": "State Health Society"
        },

        # --- WOMEN & CHILD ---
        {
            "Scheme": "Saksham Anganwadi & Poshan 2.0",
            "Ministry": "Ministry of Women and Child Development",
            "Description": "Integrated nutrition support programme.",
            "Focus": ["Women", "Children"],
            "Budget_Alloc": "₹21,960 Cr",
            "Budget_Status": "🟢 Very High",
            "Budget_Note": "Malnutrition focus.",
            "Grant": "Nutrition Support",
            "Eligibility": "Children 0-6, Mothers",
            "Documents": "Aadhaar (Mother/Child)",
            "Process": "Anganwadi Centre"
        },
        {
            "Scheme": "Mission Shakti (Sambal & Samarthya)",
            "Ministry": "Ministry of Women and Child Development",
            "Description": "Safety, security and empowerment of women.",
            "Focus": ["Women"],
            "Budget_Alloc": "₹3,150 Cr",
            "Budget_Status": "🟢 Active",
            "Budget_Note": "One Stop Centres etc.",
            "Grant": "Service based",
            "Eligibility": "Women in distress",
            "Documents": "ID Proof",
            "Process": "District Office"
        },

        # --- OTHERS ---
        {
            "Scheme": "Khelo India",
            "Ministry": "Ministry of Youth Affairs and Sports",
            "Description": "Development of sports infrastructure and talent.",
            "Focus": ["Sports", "Youth"],
            "Budget_Alloc": "₹1,000 Cr",
            "Budget_Status": "🟢 Active",
            "Budget_Note": "Sports Infra.",
            "Grant": "Scholarships / Infra",
            "Eligibility": "Athletes / States",
            "Documents": "Sports Certs",
            "Process": "Sports Authority of India"
        },
        {
            "Scheme": "PM Vishwakarma",
            "Ministry": "Ministry of MSME",
            "Description": "Support to traditional artisans and craftspeople.",
            "Focus": ["MSME", "Artisans"],
            "Budget_Alloc": "₹4,824 Cr",
            "Budget_Status": "🟢 Active",
            "Budget_Note": "Artisan support.",
            "Grant": "Loan + Toolkit Incentive",
            "Eligibility": "18 Trades (Carpenter, etc.)",
            "Documents": "Aadhaar, Skill Cert",
            "Process": "CSC / Online"
        }
    ]

    # --- WRITE TO FILE ---
    try:
        with open("schemes.json", "w", encoding='utf-8') as f:
            json.dump(DATA, f, indent=4, ensure_ascii=False)
        print(f"✅ SUCCESS: Database rebuilt with {len(DATA)} high-priority schemes.")
        print("   The 'Ministry' dropdown will now include Agriculture, Power, Jal Shakti, etc.")
    except Exception as e:
        print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    reset_database()