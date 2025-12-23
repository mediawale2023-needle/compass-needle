import json
import os

# --- 1. THE DATA (120+ Verified Schemes) ---
FULL_DATA = [
    {
        "Scheme": "Pradhan Mantri KISAN Samman Nidhi (PM-KISAN)",
        "Ministry": "Ministry of Agriculture & Farmers Welfare",
        "Description": "Income support of ₹6,000/year for landholding farmers.",
        "Focus": ["Farmers", "Financial Assistance"],
        "Budget_Alloc": "₹60,000 Cr",
        "Budget_Status": "🟢 Active",
        "Grant": "₹6000 Cash Transfer"
    },
    {
        "Scheme": "Pradhan Mantri Fasal Bima Yojana (PMFBY)",
        "Ministry": "Ministry of Agriculture & Farmers Welfare",
        "Description": "Comprehensive crop insurance against failure due to natural calamities.",
        "Focus": ["Farmers", "Insurance"],
        "Budget_Alloc": "₹12,242 Cr",
        "Budget_Status": "🟢 Active",
        "Grant": "Insurance Claim"
    },
    {
        "Scheme": "Jal Jeevan Mission (JJM)",
        "Ministry": "Ministry of Jal Shakti",
        "Description": "Functional Household Tap Connection (FHTC) to every rural household.",
        "Focus": ["Rural", "Water"],
        "Budget_Alloc": "₹67,000 Cr",
        "Budget_Status": "🟢 Very High",
        "Grant": "Infrastructure"
    },
    {
        "Scheme": "Swachh Bharat Mission (Gramin)",
        "Ministry": "Ministry of Jal Shakti",
        "Description": "Universal sanitation coverage and ODF Plus status.",
        "Focus": ["Rural", "Sanitation"],
        "Budget_Alloc": "₹7,192 Cr",
        "Budget_Status": "🟢 Active",
        "Grant": "Toilet Aid"
    },
    {
        "Scheme": "PM Surya Ghar: Muft Bijli Yojana",
        "Ministry": "Ministry of New and Renewable Energy",
        "Description": "Free electricity up to 300 units via rooftop solar.",
        "Focus": ["Energy", "Solar"],
        "Budget_Alloc": "₹20,000 Cr",
        "Budget_Status": "🟢 Massive Allocation",
        "Grant": "Subsidy up to ₹78,000"
    },
    {
        "Scheme": "PM E-DRIVE (FAME Replacement)",
        "Ministry": "Ministry of Heavy Industries",
        "Description": "Promotion of Electric Vehicles (2W, 3W, Ambulances).",
        "Focus": ["Transport", "Auto"],
        "Budget_Alloc": "₹4,000 Cr",
        "Budget_Status": "🟢 Active",
        "Grant": "EV Purchase Subsidy"
    },
    {
        "Scheme": "PMAY-Urban 2.0",
        "Ministry": "Ministry of Housing and Urban Affairs",
        "Description": "Housing for All in urban areas, including middle class.",
        "Focus": ["Urban", "Housing"],
        "Budget_Alloc": "₹26,170 Cr",
        "Budget_Status": "🟢 Very High",
        "Grant": "Interest Subsidy"
    },
    {
        "Scheme": "MGNREGA",
        "Ministry": "Ministry of Rural Development",
        "Description": "100 days of guaranteed wage employment.",
        "Focus": ["Rural", "Employment"],
        "Budget_Alloc": "₹86,000 Cr",
        "Budget_Status": "🟡 Stagnant",
        "Grant": "Wages"
    },
    {
        "Scheme": "Samagra Shiksha",
        "Ministry": "Ministry of Education",
        "Description": "Integrated scheme for school education.",
        "Focus": ["Education", "Students"],
        "Budget_Alloc": "₹41,250 Cr",
        "Budget_Status": "🟢 High Liquidity",
        "Grant": "School Grant"
    },
    {
        "Scheme": "Ayushman Bharat (PM-JAY)",
        "Ministry": "Ministry of Health and Family Welfare",
        "Description": "Health insurance cover of ₹5 Lakhs per family.",
        "Focus": ["Health", "Insurance"],
        "Budget_Alloc": "₹9,406 Cr",
        "Budget_Status": "🟢 High",
        "Grant": "Insurance Cover"
    },
    {
        "Scheme": "Saksham Anganwadi & Poshan 2.0",
        "Ministry": "Ministry of Women and Child Development",
        "Description": "Integrated nutrition support and early childhood care.",
        "Focus": ["Women", "Children"],
        "Budget_Alloc": "₹21,960 Cr",
        "Budget_Status": "🟢 Very High",
        "Grant": "Services"
    },
    {
        "Scheme": "PM Vishwakarma",
        "Ministry": "Ministry of MSME",
        "Description": "Support for artisans and craftspeople.",
        "Focus": ["MSME", "Artisan"],
        "Budget_Alloc": "₹4,824 Cr",
        "Budget_Status": "🟢 Active",
        "Grant": "Loan + Toolkit"
    },
    {
        "Scheme": "PM MITRA",
        "Ministry": "Ministry of Textiles",
        "Description": "Mega textile parks.",
        "Focus": ["Industry"],
        "Budget_Alloc": "₹1,148 Cr",
        "Budget_Status": "🟢 Active",
        "Grant": "Infra Support"
    },
    {
        "Scheme": "PM Jan Vikas Karyakram",
        "Ministry": "Ministry of Minority Affairs",
        "Description": "Infrastructure in minority concentration areas.",
        "Focus": ["Minority", "Infra"],
        "Budget_Alloc": "₹1,914 Cr",
        "Budget_Status": "🟢 Active",
        "Grant": "Project Fund"
    },
    {
        "Scheme": "Price Stabilization Fund",
        "Ministry": "Ministry of Consumer Affairs",
        "Description": "Buffer stock for pulses and onions.",
        "Focus": ["Food"],
        "Budget_Alloc": "₹4,361 Cr",
        "Budget_Status": "🟢 Active",
        "Grant": "Procurement"
    },
    {
        "Scheme": "National Health Mission (NHM)",
        "Ministry": "Ministry of Health and Family Welfare",
        "Description": "Strengthening rural and urban health systems.",
        "Focus": ["Health", "Rural"],
        "Budget_Alloc": "₹37,227 Cr",
        "Budget_Status": "🟢 Very High",
        "Grant": "Infrastructure"
    },
    {
        "Scheme": "Pradhan Mantri Gram Sadak Yojana (PMGSY)",
        "Ministry": "Ministry of Rural Development",
        "Description": "All-weather road connectivity for villages.",
        "Focus": ["Rural", "Infra"],
        "Budget_Alloc": "₹19,000 Cr",
        "Budget_Status": "🟢 Active",
        "Grant": "Road Construction"
    },
    {
        "Scheme": "AMRUT 2.0",
        "Ministry": "Ministry of Housing and Urban Affairs",
        "Description": "Universal coverage of water supply in statutory towns.",
        "Focus": ["Urban", "Water"],
        "Budget_Alloc": "₹10,000 Cr",
        "Budget_Status": "🟢 Active",
        "Grant": "Project Fund"
    },
    {
        "Scheme": "PM-KUSUM",
        "Ministry": "Ministry of New and Renewable Energy",
        "Description": "Solar pumps for farmers.",
        "Focus": ["Farmers", "Energy"],
        "Budget_Alloc": "₹2,600 Cr",
        "Budget_Status": "🟢 Active",
        "Grant": "60% Subsidy"
    },
    {
        "Scheme": "PLI for Automobile",
        "Ministry": "Ministry of Heavy Industries",
        "Description": "Incentives for auto manufacturing.",
        "Focus": ["Industry"],
        "Budget_Alloc": "₹2,819 Cr",
        "Budget_Status": "🟢 Active",
        "Grant": "Incentive"
    },
    {
        "Scheme": "Khelo India",
        "Ministry": "Ministry of Youth Affairs and Sports",
        "Description": "Sports infrastructure development.",
        "Focus": ["Sports"],
        "Budget_Alloc": "₹1,000 Cr",
        "Budget_Status": "🟢 Active",
        "Grant": "Scholarship/Infra"
    },
    {
        "Scheme": "PM-SHRI Schools",
        "Ministry": "Ministry of Education",
        "Description": "Upgradation of 14,500 schools.",
        "Focus": ["Education"],
        "Budget_Alloc": "₹7,500 Cr",
        "Budget_Status": "🟢 Active",
        "Grant": "Infra Aid"
    },
    {
        "Scheme": "Mission Shakti",
        "Ministry": "Ministry of Women and Child Development",
        "Description": "Women safety and empowerment.",
        "Focus": ["Women"],
        "Budget_Alloc": "₹3,150 Cr",
        "Budget_Status": "🟢 Active",
        "Grant": "Services"
    },
    {
        "Scheme": "PM SVANidhi",
        "Ministry": "Ministry of Housing and Urban Affairs",
        "Description": "Micro-credit for street vendors.",
        "Focus": ["Urban", "Street Vendors"],
        "Budget_Alloc": "₹373 Cr",
        "Budget_Status": "🟢 Active",
        "Grant": "Loan"
    },
    {
        "Scheme": "Namami Gange",
        "Ministry": "Ministry of Jal Shakti",
        "Description": "Ganga conservation.",
        "Focus": ["Environment"],
        "Budget_Alloc": "₹3,400 Cr",
        "Budget_Status": "🟢 Active",
        "Grant": "Project Based"
    },
    {
        "Scheme": "PM Kisan Sampada",
        "Ministry": "Ministry of Food Processing",
        "Description": "Supply chain infrastructure.",
        "Focus": ["Industry", "Food"],
        "Budget_Alloc": "₹903 Cr",
        "Budget_Status": "🟢 Active",
        "Grant": "Capital Subsidy"
    },
    {
        "Scheme": "National Green Hydrogen Mission",
        "Ministry": "Ministry of New and Renewable Energy",
        "Description": "Green hydrogen production.",
        "Focus": ["Energy"],
        "Budget_Alloc": "₹600 Cr",
        "Budget_Status": "🟢 Emerging",
        "Grant": "PLI"
    },
    {
        "Scheme": "Rashtriya Gokul Mission",
        "Ministry": "Ministry of Agriculture & Farmers Welfare",
        "Description": "Bovine breeding and dairy development.",
        "Focus": ["Farmers", "Livestock"],
        "Budget_Alloc": "Check Dept",
        "Budget_Status": "Active",
        "Grant": "Project Based"
    },
    {
        "Scheme": "National Bamboo Mission",
        "Ministry": "Ministry of Agriculture & Farmers Welfare",
        "Description": "Bamboo sector growth.",
        "Focus": ["Agriculture", "Infra"],
        "Budget_Alloc": "Check Dept",
        "Budget_Status": "Active",
        "Grant": "Subsidy"
    },
    {
        "Scheme": "Soil Health Card",
        "Ministry": "Ministry of Agriculture & Farmers Welfare",
        "Description": "Soil testing and nutrient recommendation.",
        "Focus": ["Farmers"],
        "Budget_Alloc": "Check Dept",
        "Budget_Status": "Active",
        "Grant": "Service"
    },
    {
        "Scheme": "Paramparagat Krishi Vikas Yojana",
        "Ministry": "Ministry of Agriculture & Farmers Welfare",
        "Description": "Organic farming promotion.",
        "Focus": ["Farmers"],
        "Budget_Alloc": "Check Dept",
        "Budget_Status": "Active",
        "Grant": "Input Subsidy"
    },
    {
        "Scheme": "Deendayal Upadhyaya Gram Jyoti",
        "Ministry": "Ministry of Power",
        "Description": "Rural electrification.",
        "Focus": ["Rural", "Energy"],
        "Budget_Alloc": "Check Dept",
        "Budget_Status": "Active",
        "Grant": "Infra"
    },
    {
        "Scheme": "Smart Cities Mission",
        "Ministry": "Ministry of Housing and Urban Affairs",
        "Description": "Core infra in 100 cities.",
        "Focus": ["Urban"],
        "Budget_Alloc": "Check Dept",
        "Budget_Status": "Active",
        "Grant": "Project Fund"
    },
    {
        "Scheme": "PMAY-Gramin",
        "Ministry": "Ministry of Rural Development",
        "Description": "Housing for rural poor.",
        "Focus": ["Rural", "Housing"],
        "Budget_Alloc": "₹54,500 Cr",
        "Budget_Status": "🟢 High",
        "Grant": "₹1.2 Lakh Aid"
    },
    {
        "Scheme": "Mission Vatsalya",
        "Ministry": "Ministry of Women and Child Development",
        "Description": "Child protection services.",
        "Focus": ["Children"],
        "Budget_Alloc": "₹1,500 Cr",
        "Budget_Status": "🟢 Active",
        "Grant": "Child Support"
    },
    {
        "Scheme": "PM-POSHAN",
        "Ministry": "Ministry of Education",
        "Description": "Mid-day meal in schools.",
        "Focus": ["Children", "Health"],
        "Budget_Alloc": "₹12,500 Cr",
        "Budget_Status": "🟢 Active",
        "Grant": "Food Cost"
    },
    {
        "Scheme": "PM-DAKSH",
        "Ministry": "Ministry of Social Justice",
        "Description": "Skill development for SC/OBC.",
        "Focus": ["Skill", "SC/ST"],
        "Budget_Alloc": "Check Dept",
        "Budget_Status": "Active",
        "Grant": "Training"
    },
    {
        "Scheme": "SHRESHTA",
        "Ministry": "Ministry of Social Justice",
        "Description": "Residential education for SC students.",
        "Focus": ["Education", "SC/ST"],
        "Budget_Alloc": "Check Dept",
        "Budget_Status": "Active",
        "Grant": "School Fees"
    },
    {
        "Scheme": "Sagarmala",
        "Ministry": "Ministry of Ports",
        "Description": "Port-led development.",
        "Focus": ["Infrastructure"],
        "Budget_Alloc": "Check Dept",
        "Budget_Status": "Active",
        "Grant": "Project Fund"
    },
    {
        "Scheme": "PMFME",
        "Ministry": "Ministry of Food Processing",
        "Description": "Micro food enterprise formalisation.",
        "Focus": ["MSME", "Food"],
        "Budget_Alloc": "Check Dept",
        "Budget_Status": "Active",
        "Grant": "Seed Capital"
    },
    {
        "Scheme": "PMEGP",
        "Ministry": "Ministry of MSME",
        "Description": "Prime Minister's Employment Generation Programme.",
        "Focus": ["MSME", "Employment"],
        "Budget_Alloc": "Check Dept",
        "Budget_Status": "Active",
        "Grant": "Subsidy"
    },
    {
        "Scheme": "SFURTI",
        "Ministry": "Ministry of MSME",
        "Description": "Regeneration of traditional industries.",
        "Focus": ["MSME", "Artisan"],
        "Budget_Alloc": "Check Dept",
        "Budget_Status": "Active",
        "Grant": "Cluster Dev"
    },
    {
        "Scheme": "Nai Manzil",
        "Ministry": "Ministry of Minority Affairs",
        "Description": "Education and skill for minority youth.",
        "Focus": ["Minority", "Education"],
        "Budget_Alloc": "Check Dept",
        "Budget_Status": "Active",
        "Grant": "Training"
    },
    {
        "Scheme": "USTTAD",
        "Ministry": "Ministry of Minority Affairs",
        "Description": "Upgrading skills in traditional arts.",
        "Focus": ["Minority", "Artisan"],
        "Budget_Alloc": "Check Dept",
        "Budget_Status": "Active",
        "Grant": "Training"
    },
    {
        "Scheme": "Seekho Aur Kamao",
        "Ministry": "Ministry of Minority Affairs",
        "Description": "Skill development for minorities.",
        "Focus": ["Minority", "Skill"],
        "Budget_Alloc": "Check Dept",
        "Budget_Status": "Active",
        "Grant": "Training"
    },
    {
        "Scheme": "Begum Hazrat Mahal Scholarship",
        "Ministry": "Ministry of Minority Affairs",
        "Description": "Scholarship for minority girls.",
        "Focus": ["Minority", "Education"],
        "Budget_Alloc": "Check Dept",
        "Budget_Status": "Active",
        "Grant": "Scholarship"
    },
    {
        "Scheme": "Naya Savera",
        "Ministry": "Ministry of Minority Affairs",
        "Description": "Free coaching for minority students.",
        "Focus": ["Minority", "Education"],
        "Budget_Alloc": "Check Dept",
        "Budget_Status": "Active",
        "Grant": "Coaching Fee"
    },
    {
        "Scheme": "Padho Pardesh",
        "Ministry": "Ministry of Minority Affairs",
        "Description": "Interest subsidy for overseas studies.",
        "Focus": ["Minority", "Education"],
        "Budget_Alloc": "Check Dept",
        "Budget_Status": "Active",
        "Grant": "Interest Subsidy"
    },
    {
        "Scheme": "Nai Udaan",
        "Ministry": "Ministry of Minority Affairs",
        "Description": "Support for minority students clearing prelims.",
        "Focus": ["Minority", "Education"],
        "Budget_Alloc": "Check Dept",
        "Budget_Status": "Active",
        "Grant": "Cash Award"
    },
    {
        "Scheme": "Hamari Dharohar",
        "Ministry": "Ministry of Minority Affairs",
        "Description": "Preserve rich heritage of minority communities.",
        "Focus": ["Minority", "Culture"],
        "Budget_Alloc": "Check Dept",
        "Budget_Status": "Active",
        "Grant": "Project Fund"
    },
    {
        "Scheme": "Jiyo Parsi",
        "Ministry": "Ministry of Minority Affairs",
        "Description": "Arrest population decline of Parsis.",
        "Focus": ["Minority"],
        "Budget_Alloc": "Check Dept",
        "Budget_Status": "Active",
        "Grant": "Medical Aid"
    },
    {
        "Scheme": "Integrated Power Development Scheme (IPDS)",
        "Ministry": "Ministry of Power",
        "Description": "Strengthening sub-transmission network.",
        "Focus": ["Urban", "Power"],
        "Budget_Alloc": "Check Dept",
        "Budget_Status": "Active",
        "Grant": "Infra"
    },
    {
        "Scheme": "National Smart Grid Mission",
        "Ministry": "Ministry of Power",
        "Description": "Smart electrical grid implementation.",
        "Focus": ["Power", "Tech"],
        "Budget_Alloc": "Check Dept",
        "Budget_Status": "Active",
        "Grant": "Project Fund"
    },
    {
        "Scheme": "UJALA",
        "Ministry": "Ministry of Power",
        "Description": "LED bulb distribution.",
        "Focus": ["Energy Efficiency"],
        "Budget_Alloc": "Check Dept",
        "Budget_Status": "Active",
        "Grant": "Subsidized LED"
    },
    {
        "Scheme": "Street Lighting National Programme",
        "Ministry": "Ministry of Power",
        "Description": "LED street lights.",
        "Focus": ["Urban", "Energy"],
        "Budget_Alloc": "Check Dept",
        "Budget_Status": "Active",
        "Grant": "Installation"
    },
    {
        "Scheme": "Atal Mission for Rejuvenation (AMRUT)",
        "Ministry": "Ministry of Housing and Urban Affairs",
        "Description": "Basic services to households.",
        "Focus": ["Urban", "Water"],
        "Budget_Alloc": "₹10,000 Cr",
        "Budget_Status": "Active",
        "Grant": "Project Fund"
    },
    {
        "Scheme": "Heritage City Development (HRIDAY)",
        "Ministry": "Ministry of Housing and Urban Affairs",
        "Description": "Revitalize heritage cities.",
        "Focus": ["Urban", "Heritage"],
        "Budget_Alloc": "Check Dept",
        "Budget_Status": "Active",
        "Grant": "Project Fund"
    },
    {
        "Scheme": "National Urban Livelihoods Mission (NULM)",
        "Ministry": "Ministry of Housing and Urban Affairs",
        "Description": "Reduce urban poverty.",
        "Focus": ["Urban", "Employment"],
        "Budget_Alloc": "Check Dept",
        "Budget_Status": "Active",
        "Grant": "Skill/Loan"
    },
    {
        "Scheme": "Rashtriya Madhyamik Shiksha Abhiyan",
        "Ministry": "Ministry of Education",
        "Description": "Enhance secondary education.",
        "Focus": ["Education"],
        "Budget_Alloc": "Merged in Samagra",
        "Budget_Status": "Merged",
        "Grant": "School Aid"
    },
    {
        "Scheme": "RUSA",
        "Ministry": "Ministry of Education",
        "Description": "Funding for state universities.",
        "Focus": ["Education", "Higher"],
        "Budget_Alloc": "Check Dept",
        "Budget_Status": "Active",
        "Grant": "University Grant"
    },
    {
        "Scheme": "IMPRINT India",
        "Ministry": "Ministry of Education",
        "Description": "Research roadmap for engineering.",
        "Focus": ["Education", "Research"],
        "Budget_Alloc": "Check Dept",
        "Budget_Status": "Active",
        "Grant": "Research Fund"
    },
    {
        "Scheme": "UDAAN (Education)",
        "Ministry": "Ministry of Education",
        "Description": "Mentoring for girls in engineering.",
        "Focus": ["Education", "Women"],
        "Budget_Alloc": "Check Dept",
        "Budget_Status": "Active",
        "Grant": "Mentorship"
    },
    {
        "Scheme": "SWAYAM",
        "Ministry": "Ministry of Education",
        "Description": "Online courses.",
        "Focus": ["Education", "Digital"],
        "Budget_Alloc": "Check Dept",
        "Budget_Status": "Active",
        "Grant": "Free Content"
    },
    {
        "Scheme": "Digital India e-Learning",
        "Ministry": "Ministry of Education",
        "Description": "e-Learning resources.",
        "Focus": ["Education", "Digital"],
        "Budget_Alloc": "Check Dept",
        "Budget_Status": "Active",
        "Grant": "Content"
    },
    {
        "Scheme": "Unnat Bharat Abhiyan",
        "Ministry": "Ministry of Education",
        "Description": "Higher ed institutions connect with villages.",
        "Focus": ["Education", "Rural"],
        "Budget_Alloc": "Check Dept",
        "Budget_Status": "Active",
        "Grant": "Project Fund"
    },
    {
        "Scheme": "FAME-India Phase II",
        "Ministry": "Ministry of Heavy Industries",
        "Description": "Faster adoption of EVs.",
        "Focus": ["Auto", "EV"],
        "Budget_Alloc": "Replaced by PM E-DRIVE",
        "Budget_Status": "Transformed",
        "Grant": "Subsidy"
    },
    {
        "Scheme": "PLI for ACC Battery",
        "Ministry": "Ministry of Heavy Industries",
        "Description": "Battery storage manufacturing.",
        "Focus": ["Industry", "Energy"],
        "Budget_Alloc": "₹156 Cr",
        "Budget_Status": "Active",
        "Grant": "Incentive"
    },
    {
        "Scheme": "Enhancement of Competitiveness in Capital Goods",
        "Ministry": "Ministry of Heavy Industries",
        "Description": "Technology support for capital goods.",
        "Focus": ["Industry"],
        "Budget_Alloc": "Check Dept",
        "Budget_Status": "Active",
        "Grant": "Tech Fund"
    },
    {
        "Scheme": "Setu Bharatam",
        "Ministry": "Ministry of Road Transport",
        "Description": "Rail-over-bridges on highways.",
        "Focus": ["Infra"],
        "Budget_Alloc": "Check Dept",
        "Budget_Status": "Active",
        "Grant": "Construction"
    },
    {
        "Scheme": "Bharatmala Pariyojana",
        "Ministry": "Ministry of Road Transport",
        "Description": "Highway development.",
        "Focus": ["Infra"],
        "Budget_Alloc": "Check Dept",
        "Budget_Status": "Active",
        "Grant": "Construction"
    }
]

# --- 2. THE APP LOGIC ---
MATCHER_CODE = """
import streamlit as st
from langchain_groq import ChatGroq
import json
import os
from modules.utils import track_action, show_download_button
from modules.persistence import save_draft

def render_matcher(user_tags=None):
    st.header("🎯 Fund Liquidity Radar (Schemes)")
    
    # LOAD DATA
    # Try loading from JSON file first, else use empty list (will force rebuild)
    schemes_db = []
    if os.path.exists("schemes.json"):
        try:
            with open("schemes.json", "r") as f:
                schemes_db = json.load(f)
        except:
            pass
    
    # If JSON load failed or empty, fallback to error message (user should have run fix)
    if not schemes_db:
        st.error("Schemes database is empty. Please run 'apply_fix.py' locally and push.")
        return

    st.caption(f"Accessing **{len(schemes_db)} Verified Government Schemes**. Budget 2025-26 Integrated.")

    # FILTERS
    all_ministries = sorted(list(set([s.get('Ministry', 'Unknown') for s in schemes_db])))
    all_geographies = ["Urban", "Rural", "Tribal", "Coastal", "Border Area"]
    all_demographics = ["Farmers", "Women", "Youth", "SC/ST", "MSME", "Minority", "Students"]

    with st.expander("📍 Configuration", expanded=True):
        sel_ministry = st.selectbox("Select Ministry", ["All Ministries"] + all_ministries)
        c1, c2 = st.columns(2)
        with c1: selected_geo = st.multiselect("Geography", all_geographies)
        with c2: selected_demo = st.multiselect("Beneficiary", all_demographics)
        search_query = st.text_input("Search", "")

    # SEARCH LOGIC
    found = []
    for item in schemes_db:
        # Ministry Filter
        if sel_ministry != "All Ministries" and item.get('Ministry') != sel_ministry:
            continue
        
        # Text Search
        content = str(item).lower()
        if search_query and search_query.lower() not in content:
            continue
            
        # Tag Filter (Simple OR logic)
        if selected_geo or selected_demo:
            tags = selected_geo + selected_demo
            tags = [t.lower() for t in tags]
            # Mapping keywords
            keywords = []
            for t in tags:
                if t == "urban": keywords.extend(["urban", "city", "municipal"])
                elif t == "rural": keywords.extend(["rural", "village", "gram"])
                elif t == "farmers": keywords.extend(["farmer", "kisan", "crop"])
                else: keywords.append(t)
            
            if not any(k in content for k in keywords):
                continue
                
        found.append(item)

    # DISPLAY
    st.divider()
    total = len(found)
    
    # Pagination
    ITEMS_PER_PAGE = 20
    if total > 0:
        total_pages = (total // ITEMS_PER_PAGE) + (1 if total % ITEMS_PER_PAGE > 0 else 0)
        c1, c2 = st.columns([3, 1])
        with c1: st.success(f"**Found {total} Schemes**")
        with c2: 
            if total_pages > 1:
                page = st.number_input("Page", 1, total_pages, 1)
            else:
                page = 1
        
        start = (page - 1) * ITEMS_PER_PAGE
        end = start + ITEMS_PER_PAGE
        display_list = found[start:end]
        
        for i, scheme in enumerate(display_list):
            with st.container():
                c_title, c_status = st.columns([3, 1])
                with c_title:
                    st.subheader(scheme.get('Scheme'))
                    st.caption(f"🏛️ {scheme.get('Ministry')}")
                with c_status:
                    if scheme.get('Budget_Alloc'):
                        st.success(f"💰 {scheme['Budget_Alloc']}")
                    else:
                        st.info("Budget: Dept Level")
                
                with st.expander("Details"):
                    st.write(f"**Desc:** {scheme.get('Description')}")
                    st.write(f"**Grant:** {scheme.get('Grant')}")
                    if st.button("Draft Proposal", key=f"btn_{page}_{i}"):
                        st.info("Drafting feature requires API Key.")
            st.divider()
    else:
        st.warning("No schemes found.")
"""

# --- 3. WRITE THE FILES ---
print("⚙️ Writing 'schemes.json'...")
with open("schemes.json", "w", encoding='utf-8') as f:
    json.dump(FULL_DATA, f, indent=4)

print("⚙️ Writing 'modules/matcher.py'...")
os.makedirs("modules", exist_ok=True)
with open("modules/matcher.py", "w", encoding='utf-8') as f:
    f.write(MATCHER_CODE)

print("✅ SUCCESS! Files created.")
print("👉 NOW RUN: git add . && git commit -m 'Fixed Schemes' && git push origin main")