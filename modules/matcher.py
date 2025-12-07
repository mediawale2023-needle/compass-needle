import streamlit as st
from langchain_groq import ChatGroq
import json
import os
from modules.utils import track_action, show_download_button
from modules.persistence import save_draft

# --- 1. THE MASTER DATABASE (Hardcoded for Guaranteed Availability) ---
MASTER_SCHEMES_DB = [
    # (Keeping the same massive list from before - truncated here for brevity but ensure you keep the full list in your file)
    # --- AGRICULTURE ---
    {"Scheme": "Pradhan Mantri KISAN Samman Nidhi (PM-KISAN)", "Ministry": "Agriculture", "Budget_Alloc": "₹60,000 Cr", "Description": "Income support of ₹6,000/year for landholding farmers.", "Focus": "Farmers", "Grant": "₹6000 Cash Transfer"},
    {"Scheme": "Pradhan Mantri Fasal Bima Yojana", "Ministry": "Agriculture", "Budget_Alloc": "₹12,242 Cr", "Description": "Comprehensive crop insurance against failure due to natural calamities.", "Focus": "Farmers", "Grant": "Insurance Claim"},
    # ... (Include all 60+ items from the previous response here) ...
    # For brevity in this response, I'm assuming you have the full list.
    # If not, copy the MASTER_SCHEMES_DB block from the previous message.
]

# (If you need the full list again, just ask, and I will paste it. 
# But assuming you have it, let's focus on the Logic Update)

def render_matcher(user_tags=None):
    st.header("🎯 Fund Liquidity Radar (Schemes)")
    st.caption("Access 300+ Government Schemes. Budget 2025-26 Integrated.")

    # --- 1. FILTER UI ---
    all_geographies = ["Urban", "Rural", "Tribal", "Coastal", "Border Area"]
    all_demographics = ["Farmers", "Women", "Youth", "SC/ST", "MSME", "Minority", "Students", "Health", "Infrastructure", "Energy"]

    with st.expander("📍 Configuration: Select Area and Beneficiary", expanded=True):
        # NEW: "Show All" Toggle
        show_all = st.checkbox("Show All Schemes (Disable Filters)", value=False)
        
        if not show_all:
            c1, c2 = st.columns(2)
            with c1: selected_geo = st.multiselect("🌍 Geography / Sector", all_geographies)
            with c2: selected_demo = st.multiselect("👥 Beneficiary", all_demographics)
        else:
            selected_geo = []
            selected_demo = []
            st.info("Displaying full catalog of schemes.")

    # --- 2. SEARCH LOGIC ---
    found_schemes = []
    
    # If "Show All" is checked, we just copy the master list
    if show_all:
        found_schemes = MASTER_SCHEMES_DB
    else:
        # Define Keyword Mappings (The "Smart" Brain)
        KEYWORD_MAP = {
            "Urban": ["urban", "city", "municipal", "metro", "smart", "svanidhi", "housing"],
            "Rural": ["rural", "village", "gram", "panchayat", "mgnrega", "krishi", "kisan", "sadak"],
            "Tribal": ["tribal", "vanbasi"],
            "Coastal": ["coastal", "port", "fish", "sagarmala"],
            "Farmers": ["farmer", "kisan", "crop", "agriculture", "fasal", "sinchai", "soil"],
            "Women": ["women", "female", "girl", "shakti", "maternity", "anganwadi", "lakhpati"],
            "Youth": ["youth", "student", "skill", "khelo", "sport", "employment"],
            "MSME": ["msme", "business", "industry", "textile", "pli", "vishwakarma", "food processing"],
            "Students": ["school", "education", "vidya", "samagra", "mid-day", "shreshta"],
            "Health": ["health", "ayushman", "hospital", "medicine", "nutrition", "phc"],
            "Infrastructure": ["infra", "road", "water", "jal", "gange", "power", "energy", "housing"],
            "Energy": ["energy", "solar", "power", "hydrogen", "electric", "surya", "kusum"],
            "SC/ST": ["sc", "st", "dalit", "social justice", "daksh", "shreshta"],
            "Minority": ["minority", "jan vikas", "waqf"]
        }

        # Build Search Terms
        search_terms = []
        for tag in (selected_geo + selected_demo):
            search_terms.extend(KEYWORD_MAP.get(tag, [tag.lower()]))
        
        # Filter Loop
        for item in MASTER_SCHEMES_DB:
            # If no filters selected (and not Show All), showing nothing is standard, 
            # OR we can show everything by default. Let's show everything if empty.
            if not search_terms:
                found_schemes.append(item)
                continue

            # Combine scheme text
            content = (item['Scheme'] + " " + item['Description'] + " " + item['Focus']).lower()
            
            # Check if ANY search term exists in content (OR Logic)
            if any(term in content for term in search_terms):
                found_schemes.append(item)

    # --- 3. PAGINATION & DISPLAY ---
    st.divider()
    
    total = len(found_schemes)
    
    # Pagination Logic
    ITEMS_PER_PAGE = 20
    if total > 0:
        total_pages = (total // ITEMS_PER_PAGE) + (1 if total % ITEMS_PER_PAGE > 0 else 0)
        c_info, c_page = st.columns([3, 1])
        with c_info: st.success(f"**Found {total} Schemes**")
        
        # Only show page selector if more than 1 page
        if total_pages > 1:
            with c_page: page = st.number_input("Page", 1, total_pages, 1)
        else:
            page = 1
        
        start = (page - 1) * ITEMS_PER_PAGE
        end = start + ITEMS_PER_PAGE
        display_list = found_schemes[start:end]
    else:
        st.warning("No schemes found matching your criteria.")
        display_list = []

    # Display Cards
    for i, scheme in enumerate(display_list):
        with st.container():
            c1, c2 = st.columns([3, 1])
            with c1:
                st.subheader(scheme['Scheme'])
                st.caption(f"Ministry: **{scheme['Ministry']}**")
            with c2:
                alloc = scheme.get('Budget_Alloc', 'Check Dept')
                if alloc != "Check Dept": st.success(f"💰 {alloc}")
                else: st.info("Budget: N/A")
            
            with st.expander("🔍 View Details"):
                st.write(f"**Description:** {scheme['Description']}")
                st.write(f"**Grant:** {scheme['Grant']}")
                
                # Unique Key: Page + Index
                if st.button("📝 Draft Proposal", key=f"btn_{page}_{i}_{scheme['Scheme'][:5]}"):
                    api_key = st.session_state.get('groq_api_key')
                    if api_key:
                        with st.spinner("Drafting..."):
                            try:
                                llm = ChatGroq(temperature=0.5, groq_api_key=api_key, model_name="llama-3.1-8b-instant")
                                prompt = f"Write a formal proposal letter for {scheme['Scheme']}."
                                draft = llm.invoke(prompt).content
                                st.text_area("Draft", draft, height=200)
                                save_draft("user", scheme['Scheme'], draft, "Letter")
                            except: st.error("AI Error")
                    else:
                        st.error("Enter API Key")
        st.divider()