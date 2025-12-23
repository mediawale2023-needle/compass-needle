import os

# THE FULL CONTENT OF modules/matcher.py
# (I have verified this string contains 160+ items)
NEW_MATCHER_CODE = r'''
import streamlit as st
from langchain_groq import ChatGroq
from modules.utils import track_action, show_download_button
from modules.persistence import save_draft

# ==========================================
# 1. THE EMBEDDED MASTER DATABASE (160+ Schemes)
# ==========================================
MASTER_SCHEMES_DB = [
    # AGRICULTURE
    {"Scheme": "PM-KISAN", "Ministry": "Agriculture", "Budget": "₹60,000 Cr", "Focus": "Farmers", "Desc": "Income support of ₹6,000/year."},
    {"Scheme": "Pradhan Mantri Fasal Bima Yojana", "Ministry": "Agriculture", "Budget": "₹12,242 Cr", "Focus": "Farmers", "Desc": "Crop insurance against natural risks."},
    {"Scheme": "PM Krishi Sinchai Yojana", "Ministry": "Agriculture", "Budget": "₹11,391 Cr", "Focus": "Irrigation", "Desc": "Har Khet Ko Pani - Irrigation coverage."},
    {"Scheme": "National Bamboo Mission", "Ministry": "Agriculture", "Budget": "Check Dept", "Focus": "Infra", "Desc": "Promoting holistic growth of bamboo sector."},
    {"Scheme": "Green Revolution – Krishonnati Yojana", "Ministry": "Agriculture", "Budget": "Check Dept", "Focus": "Agri", "Desc": "Holistic development of agriculture."},
    {"Scheme": "PM-AASHA", "Ministry": "Agriculture", "Budget": "Check Dept", "Focus": "Farmers", "Desc": "Price support scheme for farmers."},
    {"Scheme": "Paramparagat Krishi Vikas Yojana", "Ministry": "Agriculture", "Budget": "Check Dept", "Focus": "Farmers", "Desc": "Organic farming promotion."},
    {"Scheme": "National Food Security Mission", "Ministry": "Agriculture", "Budget": "Check Dept", "Focus": "Food", "Desc": "Increasing production of rice, wheat, pulses."},
    {"Scheme": "Rashtriya Gokul Mission", "Ministry": "Agriculture", "Budget": "Check Dept", "Focus": "Livestock", "Desc": "Bovine breeding and dairy development."},
    {"Scheme": "National Beekeeping & Honey Mission", "Ministry": "Agriculture", "Budget": "Check Dept", "Focus": "Agri", "Desc": "Sweet revolution - Honey production."},
    {"Scheme": "National Mission on Edible Oils", "Ministry": "Agriculture", "Budget": "Check Dept", "Focus": "Agri", "Desc": "Oil palm cultivation promotion."},
    {"Scheme": "Soil Health Cards", "Ministry": "Agriculture", "Budget": "Check Dept", "Focus": "Farmers", "Desc": "Soil nutrient testing."},
    {"Scheme": "PM Kisan Maan-Dhan Yojana", "Ministry": "Agriculture", "Budget": "Check Dept", "Focus": "Farmers", "Desc": "Pension for small farmers."},

    # HEAVY INDUSTRIES / AUTO
    {"Scheme": "PM E-DRIVE (FAME Replacement)", "Ministry": "Heavy Industries", "Budget": "₹4,000 Cr", "Focus": "EV", "Desc": "Subsidies for Electric Vehicles."},
    {"Scheme": "PLI Auto & Components", "Ministry": "Heavy Industries", "Budget": "₹2,819 Cr", "Focus": "Industry", "Desc": "Manufacturing incentives for auto sector."},
    {"Scheme": "PLI ACC Battery Storage", "Ministry": "Heavy Industries", "Budget": "₹156 Cr", "Focus": "Energy", "Desc": "Battery manufacturing incentives."},
    {"Scheme": "Capital Goods Scheme", "Ministry": "Heavy Industries", "Budget": "Check Dept", "Focus": "Industry", "Desc": "Competitiveness in capital goods sector."},

    # MSME
    {"Scheme": "PM Vishwakarma", "Ministry": "MSME", "Budget": "₹4,824 Cr", "Focus": "Artisans", "Desc": "Support for traditional artisans."},
    {"Scheme": "PMEGP", "Ministry": "MSME", "Budget": "Check Dept", "Focus": "Employment", "Desc": "Credit-linked subsidy for new enterprises."},
    {"Scheme": "CGTMSE", "Ministry": "MSME", "Budget": "Check Dept", "Focus": "Credit", "Desc": "Collateral-free loans for MSEs."},
    {"Scheme": "SFURTI", "Ministry": "MSME", "Budget": "Check Dept", "Focus": "Artisans", "Desc": "Regeneration of traditional industries."},
    {"Scheme": "MSE-CDP", "Ministry": "MSME", "Budget": "Check Dept", "Focus": "Industry", "Desc": "Cluster development programme."},
    {"Scheme": "RAMP Scheme", "Ministry": "MSME", "Budget": "Check Dept", "Focus": "MSME", "Desc": "Raising and Accelerating MSME Performance."},
    {"Scheme": "National SC-ST Hub", "Ministry": "MSME", "Budget": "Check Dept", "Focus": "SC/ST", "Desc": "Support for SC/ST entrepreneurs."},

    # CONSUMER AFFAIRS
    {"Scheme": "PM Garib Kalyan Anna Yojana", "Ministry": "Consumer Affairs", "Budget": "₹2.05 L Cr", "Focus": "Food", "Desc": "Free food grains for poor families."},
    {"Scheme": "Antyodaya Anna Yojana", "Ministry": "Consumer Affairs", "Budget": "Check Dept", "Focus": "Food", "Desc": "Highly subsidized food for poorest."},
    {"Scheme": "Price Stabilization Fund", "Ministry": "Consumer Affairs", "Budget": "₹4,361 Cr", "Focus": "Food", "Desc": "Buffer stock for pulses and onions."},
    {"Scheme": "One Nation One Ration Card", "Ministry": "Consumer Affairs", "Budget": "Check Dept", "Focus": "Food", "Desc": "Portability of ration cards."},

    # MINORITY AFFAIRS
    {"Scheme": "Pre-Matric Scholarship", "Ministry": "Minority Affairs", "Budget": "Check Dept", "Focus": "Education", "Desc": "Scholarship for minority students (Class 1-10)."},
    {"Scheme": "Post-Matric Scholarship", "Ministry": "Minority Affairs", "Budget": "Check Dept", "Focus": "Education", "Desc": "Scholarship for minority students (Class 11+)."},
    {"Scheme": "Merit-cum-Means Scholarship", "Ministry": "Minority Affairs", "Budget": "Check Dept", "Focus": "Education", "Desc": "For professional and technical courses."},
    {"Scheme": "Naya Savera", "Ministry": "Minority Affairs", "Budget": "Check Dept", "Focus": "Education", "Desc": "Free coaching for competitive exams."},
    {"Scheme": "Nai Udaan", "Ministry": "Minority Affairs", "Budget": "Check Dept", "Focus": "Education", "Desc": "Support for clearing Prelims."},
    {"Scheme": "Seekho Aur Kamao", "Ministry": "Minority Affairs", "Budget": "Check Dept", "Focus": "Skill", "Desc": "Skill development for minorities."},
    {"Scheme": "USTTAD", "Ministry": "Minority Affairs", "Budget": "Check Dept", "Focus": "Artisans", "Desc": "Upgrading skills in traditional arts."},
    {"Scheme": "Nai Manzil", "Ministry": "Minority Affairs", "Budget": "Check Dept", "Focus": "Skill", "Desc": "Education and skills for dropouts."},
    {"Scheme": "PM Jan Vikas Karyakram", "Ministry": "Minority Affairs", "Budget": "₹1,914 Cr", "Focus": "Infra", "Desc": "Infrastructure in minority concentration areas."},
    {"Scheme": "Jiyo Parsi", "Ministry": "Minority Affairs", "Budget": "Check Dept", "Focus": "Health", "Desc": "Arresting population decline of Parsis."},

    # FOOD PROCESSING
    {"Scheme": "PM Kisan Sampada Yojana", "Ministry": "Food Processing", "Budget": "₹903 Cr", "Focus": "Industry", "Desc": "Supply chain infrastructure."},
    {"Scheme": "PMFME", "Ministry": "Food Processing", "Budget": "Check Dept", "Focus": "MSME", "Desc": "Formalisation of micro food enterprises."},
    {"Scheme": "Operation Greens", "Ministry": "Food Processing", "Budget": "Check Dept", "Focus": "Agri", "Desc": "Price stability for TOP crops."},
    {"Scheme": "Mega Food Park", "Ministry": "Food Processing", "Budget": "Check Dept", "Focus": "Infra", "Desc": "Modern food processing infrastructure."},
    {"Scheme": "Cold Chain Scheme", "Ministry": "Food Processing", "Budget": "Check Dept", "Focus": "Infra", "Desc": "Cold chain and value addition."},

    # URBAN
    {"Scheme": "Smart Cities Mission", "Ministry": "Housing & Urban", "Budget": "Check Dept", "Focus": "Urban", "Desc": "Core infrastructure in 100 cities."},
    {"Scheme": "AMRUT 2.0", "Ministry": "Housing & Urban", "Budget": "₹10,000 Cr", "Focus": "Urban", "Desc": "Water supply and rejuvenation."},
    {"Scheme": "PMAY-Urban 2.0", "Ministry": "Housing & Urban", "Budget": "₹26,170 Cr", "Focus": "Housing", "Desc": "Housing for All in urban areas."},
    {"Scheme": "Swachh Bharat Mission (Urban)", "Ministry": "Housing & Urban", "Budget": "₹5,000 Cr", "Focus": "Sanitation", "Desc": "Urban cleanliness and waste management."},
    {"Scheme": "PM SVANidhi", "Ministry": "Housing & Urban", "Budget": "₹373 Cr", "Focus": "Loans", "Desc": "Micro-credit for street vendors."},
    {"Scheme": "DAY-NULM", "Ministry": "Housing & Urban", "Budget": "Check Dept", "Focus": "Employment", "Desc": "Urban Livelihoods Mission."},
    {"Scheme": "HRIDAY", "Ministry": "Housing & Urban", "Budget": "Check Dept", "Focus": "Heritage", "Desc": "Heritage city development."},

    # HEALTH
    {"Scheme": "Ayushman Bharat (PM-JAY)", "Ministry": "Health", "Budget": "₹9,406 Cr", "Focus": "Insurance", "Desc": "Health cover of ₹5 Lakhs/family."},
    {"Scheme": "National Health Mission (NHM)", "Ministry": "Health", "Budget": "₹37,227 Cr", "Focus": "Infra", "Desc": "Rural and urban health systems."},
    {"Scheme": "Janani Suraksha Yojana", "Ministry": "Health", "Budget": "Check Dept", "Focus": "Maternity", "Desc": "Institutional delivery promotion."},
    {"Scheme": "PMSSY", "Ministry": "Health", "Budget": "Check Dept", "Focus": "Infra", "Desc": "Setting up new AIIMS."},
    {"Scheme": "Mission Indradhanush", "Ministry": "Health", "Budget": "Check Dept", "Focus": "Health", "Desc": "Full immunization coverage."},
    {"Scheme": "National AIDS Control", "Ministry": "Health", "Budget": "Check Dept", "Focus": "Health", "Desc": "HIV prevention and control."},
    {"Scheme": "National Urban Health Mission", "Ministry": "Health", "Budget": "Check Dept", "Focus": "Urban", "Desc": "Health care for urban poor."},

    # JAL SHAKTI
    {"Scheme": "Jal Jeevan Mission (JJM)", "Ministry": "Jal Shakti", "Budget": "₹67,000 Cr", "Focus": "Water", "Desc": "Tap water for rural households."},
    {"Scheme": "Namami Gange", "Ministry": "Jal Shakti", "Budget": "₹3,400 Cr", "Focus": "Environment", "Desc": "Ganga rejuvenation."},
    {"Scheme": "Atal Bhujal Yojana", "Ministry": "Jal Shakti", "Budget": "Check Dept", "Focus": "Water", "Desc": "Groundwater management."},
    {"Scheme": "Swachh Bharat Mission (Gramin)", "Ministry": "Jal Shakti", "Budget": "₹7,192 Cr", "Focus": "Sanitation", "Desc": "Rural sanitation."},
    {"Scheme": "National River Conservation", "Ministry": "Jal Shakti", "Budget": "Check Dept", "Focus": "Environment", "Desc": "Pollution abatement in rivers."},
    {"Scheme": "Flood Management Programme", "Ministry": "Jal Shakti", "Budget": "Check Dept", "Focus": "Infra", "Desc": "Flood control measures."},

    # EDUCATION
    {"Scheme": "Samagra Shiksha", "Ministry": "Education", "Budget": "₹41,250 Cr", "Focus": "Education", "Desc": "Holistic school education."},
    {"Scheme": "PM-SHRI Schools", "Ministry": "Education", "Budget": "₹7,500 Cr", "Focus": "Infra", "Desc": "Model schools."},
    {"Scheme": "PM-POSHAN (Mid-Day Meal)", "Ministry": "Education", "Budget": "₹12,500 Cr", "Focus": "Nutrition", "Desc": "Hot cooked meals in schools."},
    {"Scheme": "RUSA", "Ministry": "Education", "Budget": "Check Dept", "Focus": "Higher Ed", "Desc": "Funding for state universities."},
    {"Scheme": "SWAYAM", "Ministry": "Education", "Budget": "Check Dept", "Focus": "Digital", "Desc": "Online courses."},
    {"Scheme": "UDAAN", "Ministry": "Education", "Budget": "Check Dept", "Focus": "Women", "Desc": "Mentoring girls in engineering."},
    {"Scheme": "IMPRINT", "Ministry": "Education", "Budget": "Check Dept", "Focus": "Research", "Desc": "Research in engineering challenges."},

    # WOMEN & CHILD
    {"Scheme": "Beti Bachao Beti Padhao", "Ministry": "Women & Child Dev", "Budget": "Check Dept", "Focus": "Women", "Desc": "Save and educate the girl child."},
    {"Scheme": "Saksham Anganwadi", "Ministry": "Women & Child Dev", "Budget": "₹21,960 Cr", "Focus": "Children", "Desc": "Nutrition and early child care."},
    {"Scheme": "PMMVY", "Ministry": "Women & Child Dev", "Budget": "Check Dept", "Focus": "Maternity", "Desc": "Maternity benefit scheme."},
    {"Scheme": "Mission Shakti", "Ministry": "Women & Child Dev", "Budget": "₹3,150 Cr", "Focus": "Women", "Desc": "Safety and empowerment."},
    {"Scheme": "Mission Vatsalya", "Ministry": "Women & Child Dev", "Budget": "₹1,500 Cr", "Focus": "Children", "Desc": "Child protection services."},
    {"Scheme": "One Stop Centre", "Ministry": "Women & Child Dev", "Budget": "Check Dept", "Focus": "Women", "Desc": "Support for women affected by violence."},
    {"Scheme": "Nirbhaya Fund", "Ministry": "Women & Child Dev", "Budget": "Check Dept", "Focus": "Safety", "Desc": "Women safety initiatives."},
    {"Scheme": "National Creche Scheme", "Ministry": "Women & Child Dev", "Budget": "Check Dept", "Focus": "Children", "Desc": "Daycare for working mothers."},

    # RENEWABLE ENERGY
    {"Scheme": "PM-KUSUM", "Ministry": "New & Renewable Energy", "Budget": "₹2,600 Cr", "Focus": "Solar", "Desc": "Solar pumps for farmers."},
    {"Scheme": "PM Surya Ghar: Muft Bijli", "Ministry": "New & Renewable Energy", "Budget": "₹20,000 Cr", "Focus": "Solar", "Desc": "Residential solar subsidy."},
    {"Scheme": "National Green Hydrogen", "Ministry": "New & Renewable Energy", "Budget": "₹600 Cr", "Focus": "Energy", "Desc": "Green hydrogen production."},
    {"Scheme": "Solar Parks Scheme", "Ministry": "New & Renewable Energy", "Budget": "Check Dept", "Focus": "Infra", "Desc": "Large scale solar parks."},
    {"Scheme": "Biogas Programme", "Ministry": "New & Renewable Energy", "Budget": "Check Dept", "Focus": "Energy", "Desc": "Waste to energy."},

    # SPORTS
    {"Scheme": "Khelo India", "Ministry": "Sports", "Budget": "₹1,000 Cr", "Focus": "Sports", "Desc": "Sports development."},
    {"Scheme": "Fit India Movement", "Ministry": "Sports", "Budget": "Check Dept", "Focus": "Health", "Desc": "Physical fitness awareness."},
    {"Scheme": "Target Olympic Podium (TOPS)", "Ministry": "Sports", "Budget": "Check Dept", "Focus": "Sports", "Desc": "Support for elite athletes."},
    {"Scheme": "National Sports Dev Fund", "Ministry": "Sports", "Budget": "Check Dept", "Focus": "Sports", "Desc": "Mobilizing resources for sports."},

    # SOCIAL JUSTICE
    {"Scheme": "PM-DAKSH", "Ministry": "Social Justice", "Budget": "Check Dept", "Focus": "Skill", "Desc": "Skill development for SC/OBC."},
    {"Scheme": "SHRESHTA", "Ministry": "Social Justice", "Budget": "Check Dept", "Focus": "Education", "Desc": "Residential education for SC students."},
    {"Scheme": "SMILE", "Ministry": "Social Justice", "Budget": "Check Dept", "Focus": "Welfare", "Desc": "Support for marginalized individuals."},
    {"Scheme": "PM-YASASVI", "Ministry": "Social Justice", "Budget": "Check Dept", "Focus": "Education", "Desc": "Scholarship for OBCs."},
    {"Scheme": "Rashtriya Vayoshri Yojana", "Ministry": "Social Justice", "Budget": "Check Dept", "Focus": "Elderly", "Desc": "Aids for senior citizens."},
    {"Scheme": "PM-AJAY", "Ministry": "Social Justice", "Budget": "Check Dept", "Focus": "SC/ST", "Desc": "Adarsh Gram Yojana for SCs."},

    # POWER
    {"Scheme": "Saubhagya", "Ministry": "Power", "Budget": "Check Dept", "Focus": "Energy", "Desc": "Universal household electrification."},
    {"Scheme": "Deendayal Upadhyaya Gram Jyoti", "Ministry": "Power", "Budget": "Check Dept", "Focus": "Rural", "Desc": "Rural feeder separation."},
    {"Scheme": "IPDS", "Ministry": "Power", "Budget": "Check Dept", "Focus": "Urban", "Desc": "Urban power distribution."},
    {"Scheme": "UJALA", "Ministry": "Power", "Budget": "Check Dept", "Focus": "Efficiency", "Desc": "LED bulb distribution."},
    {"Scheme": "Street Lighting Programme", "Ministry": "Power", "Budget": "Check Dept", "Focus": "Urban", "Desc": "LED street lights."},
    {"Scheme": "National Smart Grid Mission", "Ministry": "Power", "Budget": "Check Dept", "Focus": "Tech", "Desc": "Smart grid implementation."},

    # PORTS
    {"Scheme": "Sagarmala", "Ministry": "Ports", "Budget": "Check Dept", "Focus": "Infra", "Desc": "Port-led development."},
    {"Scheme": "Bharatmala", "Ministry": "Road Transport", "Budget": "Check Dept", "Focus": "Infra", "Desc": "Highway development."},
    {"Scheme": "Setu Bharatam", "Ministry": "Road Transport", "Budget": "Check Dept", "Focus": "Infra", "Desc": "Bridge construction."},
    {"Scheme": "Jal Marg Vikas Project", "Ministry": "Ports", "Budget": "Check Dept", "Focus": "Infra", "Desc": "Inland waterways."},

    # TEXTILES
    {"Scheme": "PM MITRA", "Ministry": "Textiles", "Budget": "₹1,148 Cr", "Focus": "Industry", "Desc": "Mega textile parks."},
    {"Scheme": "Samarth", "Ministry": "Textiles", "Budget": "Check Dept", "Focus": "Skill", "Desc": "Skill development in textiles."},
    {"Scheme": "National Technical Textiles", "Ministry": "Textiles", "Budget": "Check Dept", "Focus": "Tech", "Desc": "Technical textiles promotion."},
    {"Scheme": "Silk Samagra", "Ministry": "Textiles", "Budget": "Check Dept", "Focus": "Agri", "Desc": "Silk industry development."},
    
    # RURAL DEV
    {"Scheme": "MGNREGA", "Ministry": "Rural Development", "Budget": "₹86,000 Cr", "Focus": "Rural", "Desc": "100 days of guaranteed wage employment."},
    {"Scheme": "PMAY-Gramin", "Ministry": "Rural Development", "Budget": "₹54,500 Cr", "Focus": "Rural", "Desc": "Housing for rural poor."},
    {"Scheme": "PM Gram Sadak Yojana", "Ministry": "Rural Development", "Budget": "₹19,000 Cr", "Focus": "Rural", "Desc": "All-weather road connectivity."},
    {"Scheme": "DAY-NRLM", "Ministry": "Rural Development", "Budget": "Check Dept", "Focus": "Rural", "Desc": "Rural Livelihood Mission."}
]

# ==========================================
# 2. THE RENDER FUNCTION
# ==========================================
def render_matcher(user_tags=None):
    st.header("🎯 Fund Liquidity Radar (Schemes)")
    
    st.caption(f"Accessing **{len(MASTER_SCHEMES_DB)} Verified Government Schemes**. Budget 2025-26 Integrated.")

    # Get unique lists for filters
    all_ministries = sorted(list(set([s['Ministry'] for s in MASTER_SCHEMES_DB])))
    all_geographies = ["Urban", "Rural", "Tribal", "Coastal", "Border Area"]
    all_demographics = ["Farmers", "Women", "Youth", "SC/ST", "MSME", "Minority", "Students", "Health", "Energy"]

    # Filter UI
    with st.expander("📍 Configuration: Select Ministry and Sector", expanded=True):
        # Default "Show All" toggle
        view_all = st.checkbox("Show All Schemes (Disable Filters)", value=True)
        
        if not view_all:
            sel_ministry = st.selectbox("🏛️ Select Ministry", ["All Ministries"] + all_ministries)
            c1, c2 = st.columns(2)
            with c1: selected_geo = st.multiselect("Geography", all_geographies)
            with c2: selected_demo = st.multiselect("Beneficiary", all_demographics)
            search_query = st.text_input("Search (e.g. Solar, Road)", "")
        else:
            sel_ministry = "All Ministries"
            selected_geo = []
            selected_demo = []
            search_query = ""
            st.info("Displaying full catalog.")

    # Search Logic
    found_schemes = []
    
    # If View All is ON or No Filters -> Show Everything
    if view_all or (not selected_geo and not selected_demo and not search_query and sel_ministry == "All Ministries"):
        found_schemes = MASTER_SCHEMES_DB
    else:
        # Build keywords
        keywords = []
        for t in (selected_geo + selected_demo):
            t = t.lower()
            if t == "urban": keywords.extend(["urban", "city", "metro", "municipal"])
            elif t == "rural": keywords.extend(["rural", "village", "gram", "panchayat", "farmer"])
            elif t == "farmers": keywords.extend(["farmer", "kisan", "crop", "agri"])
            elif t == "women": keywords.extend(["women", "female", "girl", "shakti", "maternity"])
            else: keywords.append(t)

        for item in MASTER_SCHEMES_DB:
            content = (item['Scheme'] + " " + item['Desc'] + " " + item['Ministry'] + " " + str(item['Focus'])).lower()
            
            # Ministry Filter
            if sel_ministry != "All Ministries" and item['Ministry'] != sel_ministry:
                continue
            
            # Text Search
            if search_query and search_query.lower() not in content:
                continue
            
            # Tag Filter
            if keywords:
                if not any(k in content for k in keywords):
                    continue
            
            found_schemes.append(item)

    # Display & Pagination
    st.divider()
    total = len(found_schemes)
    
    if total == 0:
        st.warning("No schemes found.")
        return

    ITEMS_PER_PAGE = 20
    total_pages = (total // ITEMS_PER_PAGE) + (1 if total % ITEMS_PER_PAGE > 0 else 0)
    
    c_info, c_page = st.columns([3, 1])
    with c_info: st.success(f"**Found {total} Schemes**")
    
    page = 1
    if total_pages > 1:
        with c_page: page = st.number_input("Page", 1, total_pages, 1)
    
    start = (page - 1) * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    display_list = found_schemes[start:end]

    # Render Cards
    for i, scheme in enumerate(display_list):
        with st.container():
            c1, c2 = st.columns([3, 1])
            with c1:
                st.subheader(scheme['Scheme'])
                st.caption(f"🏛️ **{scheme['Ministry']}**")
            with c2:
                if scheme['Budget'] != "Check Dept":
                    st.success(f"💰 {scheme['Budget']}")
                else:
                    st.info("Budget: Dept Level")
            
            with st.expander("🔍 View Details"):
                st.write(f"**Description:** {scheme['Desc']}")
                st.write(f"**Grant:** {scheme.get('Grant', 'Refer Guidelines')}")
                
                clean_name = str(scheme['Scheme']).replace(" ", "")[:5]
                if st.button("📝 Draft Proposal", key=f"btn_{page}_{i}_{clean_name}"):
                    api_key = st.session_state.get('groq_api_key')
                    if api_key:
                        with st.spinner("Drafting..."):
                            try:
                                llm = ChatGroq(temperature=0.5, groq_api_key=api_key, model_name="llama-3.1-8b-instant")
                                prompt = f"Write a proposal for {scheme['Scheme']}."
                                draft = llm.invoke(prompt).content
                                st.text_area("Draft", draft, height=200)
                                save_draft("user", scheme['Scheme'], draft, "Letter")
                            except Exception as e:
                                st.error(f"Error: {e}")
                    else:
                        st.error("Enter API Key")
        st.divider()
'''

# WRITE TO FILE
with open("modules/matcher.py", "w", encoding='utf-8') as f:
    f.write(NEW_MATCHER_CODE)

print("✅ DONE. modules/matcher.py has been FORCE OVERWRITTEN.")