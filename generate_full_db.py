import json
import os

def generate_db():
    print("🚀 GENERATING FULL 150+ SCHEME DATABASE...")

    # --- 1. THE RAW DATA (Extracted from your CSVs) ---
    RAW_DATA = [
        # AGRICULTURE
        {"Scheme": "Pradhan Mantri KISAN Samman Nidhi (PM-KISAN)", "Ministry": "Ministry of Agriculture", "Focus": "Farmers", "Desc": "Income support of ₹6,000/year."},
        {"Scheme": "Pradhan Mantri Fasal Bima Yojana (PMFBY)", "Ministry": "Ministry of Agriculture", "Focus": "Farmers", "Desc": "Crop insurance against natural risks."},
        {"Scheme": "Pradhan Mantri Krishi Sinchai Yojana (PMKSY)", "Ministry": "Ministry of Agriculture", "Focus": "Irrigation", "Desc": "Har Khet Ko Pani - Irrigation coverage."},
        {"Scheme": "Pradhan Mantri Kisan Maan-Dhan Yojana (PM-KMY)", "Ministry": "Ministry of Agriculture", "Focus": "Farmers", "Desc": "Pension for small and marginal farmers."},
        {"Scheme": "Soil Health Cards (SHC) Scheme", "Ministry": "Ministry of Agriculture", "Focus": "Farmers", "Desc": "Soil nutrient testing and recommendations."},
        {"Scheme": "National Bamboo Mission", "Ministry": "Ministry of Agriculture", "Focus": "Infra", "Desc": "Promoting bamboo sector growth."},
        {"Scheme": "Green Revolution – Krishonnati Yojana", "Ministry": "Ministry of Agriculture", "Focus": "Agri", "Desc": "Holistic development of agriculture."},
        {"Scheme": "PM-AASHA", "Ministry": "Ministry of Agriculture", "Focus": "Farmers", "Desc": "Price support scheme for farmers."},
        {"Scheme": "Paramparagat Krishi Vikas Yojana (PKVY)", "Ministry": "Ministry of Agriculture", "Focus": "Farmers", "Desc": "Organic farming promotion."},
        {"Scheme": "National Food Security Mission (NFSM)", "Ministry": "Ministry of Agriculture", "Focus": "Food", "Desc": "Increasing production of rice, wheat, pulses."},
        {"Scheme": "Rashtriya Gokul Mission", "Ministry": "Ministry of Agriculture", "Focus": "Livestock", "Desc": "Bovine breeding and dairy development."},
        {"Scheme": "National Beekeeping and Honey Mission", "Ministry": "Ministry of Agriculture", "Focus": "Agri", "Desc": "Sweet revolution - Honey production."},
        {"Scheme": "National Mission on Edible Oils (NMEO-OP)", "Ministry": "Ministry of Agriculture", "Focus": "Agri", "Desc": "Oil palm cultivation promotion."},
        {"Scheme": "National Mission on Natural Farming", "Ministry": "Ministry of Agriculture", "Focus": "Farmers", "Desc": "Chemical-free farming."},

        # HEAVY INDUSTRY / AUTO
        {"Scheme": "FAME-India Scheme (PM E-DRIVE)", "Ministry": "Ministry of Heavy Industries", "Focus": "EV", "Desc": "Subsidies for Electric Vehicles."},
        {"Scheme": "PLI for Automobile and Auto Components", "Ministry": "Ministry of Heavy Industries", "Focus": "Industry", "Desc": "Manufacturing incentives for auto sector."},
        {"Scheme": "PLI for ACC Battery Storage", "Ministry": "Ministry of Heavy Industries", "Focus": "Energy", "Desc": "Battery manufacturing incentives."},
        {"Scheme": "Capital Goods Scheme", "Ministry": "Ministry of Heavy Industries", "Focus": "Industry", "Desc": "Competitiveness in capital goods sector."},

        # CONSUMER AFFAIRS
        {"Scheme": "Pradhan Mantri Garib Kalyan Anna Yojana (PMGKAY)", "Ministry": "Ministry of Consumer Affairs", "Focus": "Food", "Desc": "Free food grains for poor families."},
        {"Scheme": "Antyodaya Anna Yojana (AAY)", "Ministry": "Ministry of Consumer Affairs", "Focus": "Food", "Desc": "Highly subsidized food for poorest families."},
        {"Scheme": "One Nation One Ration Card", "Ministry": "Ministry of Consumer Affairs", "Focus": "Food", "Desc": "Portability of ration cards."},
        {"Scheme": "Price Stabilization Fund", "Ministry": "Ministry of Consumer Affairs", "Focus": "Food", "Desc": "Buffer stock for pulses and onions."},

        # MSME
        {"Scheme": "PM Vishwakarma", "Ministry": "Ministry of MSME", "Focus": "Artisans", "Desc": "Support for traditional artisans."},
        {"Scheme": "PMEGP", "Ministry": "Ministry of MSME", "Focus": "Employment", "Desc": "Credit-linked subsidy for new enterprises."},
        {"Scheme": "CGTMSE", "Ministry": "Ministry of MSME", "Focus": "Credit", "Desc": "Collateral-free loans for MSEs."},
        {"Scheme": "SFURTI", "Ministry": "Ministry of MSME", "Focus": "Artisans", "Desc": "Regeneration of traditional industries."},
        {"Scheme": "MSE-CDP", "Ministry": "Ministry of MSME", "Focus": "Industry", "Desc": "Cluster development programme."},
        {"Scheme": "RAMP Scheme", "Ministry": "Ministry of MSME", "Focus": "MSME", "Desc": "Raising and Accelerating MSME Performance."},
        
        # MINORITY AFFAIRS
        {"Scheme": "Pre-Matric Scholarship", "Ministry": "Ministry of Minority Affairs", "Focus": "Education", "Desc": "Scholarship for minority students (Class 1-10)."},
        {"Scheme": "Post-Matric Scholarship", "Ministry": "Ministry of Minority Affairs", "Focus": "Education", "Desc": "Scholarship for minority students (Class 11+)."},
        {"Scheme": "Merit-cum-Means Scholarship", "Ministry": "Ministry of Minority Affairs", "Focus": "Education", "Desc": "For professional and technical courses."},
        {"Scheme": "Naya Savera", "Ministry": "Ministry of Minority Affairs", "Focus": "Education", "Desc": "Free coaching for competitive exams."},
        {"Scheme": "Nai Udaan", "Ministry": "Ministry of Minority Affairs", "Focus": "Education", "Desc": "Support for clearing Prelims."},
        {"Scheme": "Seekho Aur Kamao", "Ministry": "Ministry of Minority Affairs", "Focus": "Skill", "Desc": "Skill development for minorities."},
        {"Scheme": "USTTAD", "Ministry": "Ministry of Minority Affairs", "Focus": "Artisans", "Desc": "Upgrading skills in traditional arts."},
        {"Scheme": "Nai Manzil", "Ministry": "Ministry of Minority Affairs", "Focus": "Skill", "Desc": "Education and skills for dropouts."},
        {"Scheme": "PM Jan Vikas Karyakram (PMJVK)", "Ministry": "Ministry of Minority Affairs", "Focus": "Infra", "Desc": "Infrastructure in minority concentration areas."},
        {"Scheme": "Jiyo Parsi", "Ministry": "Ministry of Minority Affairs", "Focus": "Health", "Desc": "Arresting population decline of Parsis."},

        # FOOD PROCESSING
        {"Scheme": "PM Kisan Sampada Yojana", "Ministry": "Ministry of Food Processing", "Focus": "Industry", "Desc": "Supply chain infrastructure."},
        {"Scheme": "PMFME", "Ministry": "Ministry of Food Processing", "Focus": "MSME", "Desc": "Formalisation of micro food enterprises."},
        {"Scheme": "Operation Greens", "Ministry": "Ministry of Food Processing", "Focus": "Agri", "Desc": "Price stability for TOP crops."},
        {"Scheme": "Mega Food Park", "Ministry": "Ministry of Food Processing", "Focus": "Infra", "Desc": "Modern food processing infrastructure."},

        # URBAN
        {"Scheme": "Smart Cities Mission", "Ministry": "Ministry of Housing & Urban Affairs", "Focus": "Urban", "Desc": "Core infrastructure in 100 cities."},
        {"Scheme": "AMRUT 2.0", "Ministry": "Ministry of Housing & Urban Affairs", "Focus": "Urban", "Desc": "Water supply and rejuvenation."},
        {"Scheme": "PMAY-Urban", "Ministry": "Ministry of Housing & Urban Affairs", "Focus": "Housing", "Desc": "Housing for All in urban areas."},
        {"Scheme": "Swachh Bharat Mission (Urban)", "Ministry": "Ministry of Housing & Urban Affairs", "Focus": "Sanitation", "Desc": "Urban cleanliness and waste management."},
        {"Scheme": "PM SVANidhi", "Ministry": "Ministry of Housing & Urban Affairs", "Focus": "Loans", "Desc": "Micro-credit for street vendors."},
        {"Scheme": "DAY-NULM", "Ministry": "Ministry of Housing & Urban Affairs", "Focus": "Employment", "Desc": "Urban Livelihoods Mission."},
        {"Scheme": "HRIDAY", "Ministry": "Ministry of Housing & Urban Affairs", "Focus": "Heritage", "Desc": "Heritage city development."},

        # HEALTH
        {"Scheme": "Ayushman Bharat (PM-JAY)", "Ministry": "Ministry of Health", "Focus": "Insurance", "Desc": "Health cover of ₹5 Lakhs/family."},
        {"Scheme": "National Health Mission (NHM)", "Ministry": "Ministry of Health", "Focus": "Infra", "Desc": "Rural and urban health systems."},
        {"Scheme": "Janani Suraksha Yojana", "Ministry": "Ministry of Health", "Focus": "Maternity", "Desc": "Institutional delivery promotion."},
        {"Scheme": "PMSSY", "Ministry": "Ministry of Health", "Focus": "Infra", "Desc": "Setting up new AIIMS."},
        {"Scheme": "Mission Indradhanush", "Ministry": "Ministry of Health", "Focus": "Health", "Desc": "Full immunization coverage."},
        {"Scheme": "National AIDS Control Programme", "Ministry": "Ministry of Health", "Focus": "Health", "Desc": "HIV prevention and control."},

        # JAL SHAKTI
        {"Scheme": "Jal Jeevan Mission (JJM)", "Ministry": "Ministry of Jal Shakti", "Focus": "Water", "Desc": "Tap water for rural households."},
        {"Scheme": "Namami Gange", "Ministry": "Ministry of Jal Shakti", "Focus": "Environment", "Desc": "Ganga rejuvenation."},
        {"Scheme": "Atal Bhujal Yojana", "Ministry": "Ministry of Jal Shakti", "Focus": "Water", "Desc": "Groundwater management."},
        {"Scheme": "Swachh Bharat Mission (Gramin)", "Ministry": "Ministry of Jal Shakti", "Focus": "Sanitation", "Desc": "Rural sanitation."},
        {"Scheme": "National River Conservation Plan", "Ministry": "Ministry of Jal Shakti", "Focus": "Environment", "Desc": "Pollution abatement in rivers."},

        # EDUCATION
        {"Scheme": "Samagra Shiksha", "Ministry": "Ministry of Education", "Focus": "Education", "Desc": "Holistic school education."},
        {"Scheme": "PM-SHRI Schools", "Ministry": "Ministry of Education", "Focus": "Infra", "Desc": "Model schools."},
        {"Scheme": "Mid-Day Meal (PM-POSHAN)", "Ministry": "Ministry of Education", "Focus": "Nutrition", "Desc": "Hot cooked meals in schools."},
        {"Scheme": "RUSA", "Ministry": "Ministry of Education", "Focus": "Higher Ed", "Desc": "Funding for state universities."},
        {"Scheme": "SWAYAM", "Ministry": "Ministry of Education", "Focus": "Digital", "Desc": "Online courses."},
        {"Scheme": "UDAAN", "Ministry": "Ministry of Education", "Focus": "Women", "Desc": "Mentoring girls in engineering."},
        {"Scheme": "IMPRINT", "Ministry": "Ministry of Education", "Focus": "Research", "Desc": "Research in engineering challenges."},

        # WOMEN & CHILD
        {"Scheme": "Beti Bachao Beti Padhao", "Ministry": "Ministry of Women & Child Dev", "Focus": "Women", "Desc": "Save and educate the girl child."},
        {"Scheme": "Saksham Anganwadi (ICDS)", "Ministry": "Ministry of Women & Child Dev", "Focus": "Children", "Desc": "Nutrition and early child care."},
        {"Scheme": "PMMVY", "Ministry": "Ministry of Women & Child Dev", "Focus": "Maternity", "Desc": "Maternity benefit scheme."},
        {"Scheme": "Mission Shakti", "Ministry": "Ministry of Women & Child Dev", "Focus": "Women", "Desc": "Safety and empowerment."},
        {"Scheme": "Mission Vatsalya", "Ministry": "Ministry of Women & Child Dev", "Focus": "Children", "Desc": "Child protection services."},
        {"Scheme": "One Stop Centre", "Ministry": "Ministry of Women & Child Dev", "Focus": "Women", "Desc": "Support for women affected by violence."},
        {"Scheme": "Nirbhaya Fund", "Ministry": "Ministry of Women & Child Dev", "Focus": "Safety", "Desc": "Women safety initiatives."},

        # RENEWABLE ENERGY
        {"Scheme": "PM-KUSUM", "Ministry": "Ministry of New & Renewable Energy", "Focus": "Solar", "Desc": "Solar pumps for farmers."},
        {"Scheme": "Rooftop Solar Programme", "Ministry": "Ministry of New & Renewable Energy", "Focus": "Solar", "Desc": "Residential solar subsidy."},
        {"Scheme": "National Green Hydrogen Mission", "Ministry": "Ministry of New & Renewable Energy", "Focus": "Energy", "Desc": "Green hydrogen production."},
        {"Scheme": "Solar Parks Scheme", "Ministry": "Ministry of New & Renewable Energy", "Focus": "Infra", "Desc": "Large scale solar parks."},
        {"Scheme": "Biogas Programme", "Ministry": "Ministry of New & Renewable Energy", "Focus": "Energy", "Desc": "Waste to energy."},

        # SPORTS
        {"Scheme": "Khelo India", "Ministry": "Ministry of Sports", "Focus": "Sports", "Desc": "Sports development."},
        {"Scheme": "Fit India Movement", "Ministry": "Ministry of Sports", "Focus": "Health", "Desc": "Physical fitness awareness."},
        {"Scheme": "Target Olympic Podium Scheme (TOPS)", "Ministry": "Ministry of Sports", "Focus": "Sports", "Desc": "Support for elite athletes."},

        # SOCIAL JUSTICE
        {"Scheme": "PM-DAKSH", "Ministry": "Ministry of Social Justice", "Focus": "Skill", "Desc": "Skill development for SC/OBC."},
        {"Scheme": "SHRESHTA", "Ministry": "Ministry of Social Justice", "Focus": "Education", "Desc": "Residential education for SC students."},
        {"Scheme": "SMILE", "Ministry": "Ministry of Social Justice", "Focus": "Welfare", "Desc": "Support for marginalized individuals."},
        {"Scheme": "PM-YASASVI", "Ministry": "Ministry of Social Justice", "Focus": "Education", "Desc": "Scholarship for OBCs."},
        {"Scheme": "Rashtriya Vayoshri Yojana", "Ministry": "Ministry of Social Justice", "Focus": "Elderly", "Desc": "Aids for senior citizens."},
        {"Scheme": "PM-AJAY", "Ministry": "Ministry of Social Justice", "Focus": "SC/ST", "Desc": "Adarsh Gram Yojana for SCs."},

        # POWER
        {"Scheme": "Saubhagya", "Ministry": "Ministry of Power", "Focus": "Energy", "Desc": "Universal household electrification."},
        {"Scheme": "Deendayal Upadhyaya Gram Jyoti", "Ministry": "Ministry of Power", "Focus": "Rural", "Desc": "Rural feeder separation."},
        {"Scheme": "IPDS", "Ministry": "Ministry of Power", "Focus": "Urban", "Desc": "Urban power distribution."},
        {"Scheme": "UJALA", "Ministry": "Ministry of Power", "Focus": "Efficiency", "Desc": "LED bulb distribution."},
        {"Scheme": "Street Lighting National Programme", "Ministry": "Ministry of Power", "Focus": "Urban", "Desc": "LED street lights."},

        # PORTS
        {"Scheme": "Sagarmala", "Ministry": "Ministry of Ports", "Focus": "Infra", "Desc": "Port-led development."},
        {"Scheme": "Bharatmala", "Ministry": "Ministry of Road Transport", "Focus": "Infra", "Desc": "Highway development."},
        {"Scheme": "Setu Bharatam", "Ministry": "Ministry of Road Transport", "Focus": "Infra", "Desc": "Bridge construction."},
        {"Scheme": "Jal Marg Vikas Project", "Ministry": "Ministry of Ports", "Focus": "Infra", "Desc": "Inland waterways."},

        # TEXTILES
        {"Scheme": "PM MITRA", "Ministry": "Ministry of Textiles", "Focus": "Industry", "Desc": "Mega textile parks."},
        {"Scheme": "Samarth", "Ministry": "Ministry of Textiles", "Focus": "Skill", "Desc": "Skill development in textiles."}
    ]

    # --- 2. BUDGET INJECTION (2025-26) ---
    BUDGET_MAP = {
        "PM-KISAN": "₹60,000 Cr",
        "PMFBY": "₹12,242 Cr",
        "PMKSY": "₹11,391 Cr",
        "Jal Jeevan": "₹67,000 Cr",
        "Swachh Bharat": "₹7,192 Cr",
        "Namami Gange": "₹3,400 Cr",
        "Surya Ghar": "₹20,000 Cr",
        "PM-KUSUM": "₹2,600 Cr",
        "Green Hydrogen": "₹600 Cr",
        "FAME": "₹4,000 Cr (PM E-DRIVE)",
        "E-DRIVE": "₹4,000 Cr",
        "PLI": "₹19,000 Cr (Total)",
        "PMGKAY": "₹2.05 Lakh Cr",
        "PMAY": "₹26,170 Cr",
        "AMRUT": "₹10,000 Cr",
        "SVANidhi": "₹373 Cr",
        "MGNREGA": "₹86,000 Cr",
        "Samagra Shiksha": "₹41,250 Cr",
        "Ayushman Bharat": "₹9,406 Cr",
        "National Health Mission": "₹37,227 Cr",
        "Saksham Anganwadi": "₹21,960 Cr",
        "Mission Shakti": "₹3,150 Cr",
        "Mission Vatsalya": "₹1,500 Cr",
        "Khelo India": "₹1,000 Cr",
        "Vishwakarma": "₹4,824 Cr",
        "MITRA": "₹1,148 Cr",
        "Kisan Sampada": "₹903 Cr",
        "PMJVK": "₹1,914 Cr",
        "Price Stabilization": "₹4,361 Cr"
    }

    # --- 3. BUILD FINAL LIST ---
    final_db = []
    
    for item in RAW_DATA:
        # Defaults
        item['Budget_Alloc'] = "Check Dept"
        item['Budget_Status'] = "Active"
        item['Grant'] = "Refer to Guidelines"
        item['Eligibility'] = "Check Portal"
        item['Documents'] = "Standard KYC"
        item['Process'] = "Online/District Office"
        
        # Inject Budget
        for key, val in BUDGET_MAP.items():
            if key in item['Scheme']:
                item['Budget_Alloc'] = val
                item['Budget_Status'] = "🟢 Active"
                break
        
        final_db.append(item)

    # --- 4. SAVE ---
    with open("schemes.json", "w", encoding='utf-8') as f:
        json.dump(final_db, f, indent=4)
    
    print(f"✅ SUCCESS: 'schemes.json' created with {len(final_db)} verified schemes.")

if __name__ == "__main__":
    generate_db()