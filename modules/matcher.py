import streamlit as st
import pandas as pd

def render_matcher(mp_name):
    # --- 1. HEADER & METRICS ---
    st.markdown(f"### 🎯 Scheme Matcher for {mp_name}")
    st.caption("AI-powered recommendation engine to match constituents with government benefits.")

    # --- 2. INTELLIGENCE DATABASE (Central + Karnataka Specific) ---
    # This mock DB represents what would normally be a SQL query
    schemes_db = [
        # --- KARNATAKA FLAGSHIP SCHEMES (The 5 Guarantees) ---
        {"title": "Gruha Lakshmi Yojana", "theme": "Social Welfare", "type": "State (Karnataka)", "demography": "Women", "benefit": "₹2,000 monthly assistance to woman head of family."},
        {"title": "Shakti Scheme", "theme": "Transport", "type": "State (Karnataka)", "demography": "Women", "benefit": "Free bus travel for women across Karnataka."},
        {"title": "Gruha Jyothi", "theme": "Energy", "type": "State (Karnataka)", "demography": "All Households", "benefit": "Free electricity up to 200 units for households."},
        {"title": "Yuva Nidhi", "theme": "Employment", "type": "State (Karnataka)", "demography": "Youth", "benefit": "Unemployment allowance for graduates (₹3,000) and diploma holders (₹1,500)."},
        {"title": "Anna Bhagya", "theme": "Food Security", "type": "State (Karnataka)", "demography": "BPL Families", "benefit": "Free rice distribution for BPL card holders."},
        
        # --- CENTRAL INFRASTRUCTURE & HOUSING ---
        {"title": "PM Awas Yojana (Urban)", "theme": "Housing", "type": "Central", "demography": "Urban Poor", "benefit": "Subsidized housing for urban poor."},
        {"title": "PM Awas Yojana (Gramin)", "theme": "Housing", "type": "Central", "demography": "Rural Poor", "benefit": "Financial aid for building pucca houses in rural areas."},
        {"title": "Jal Jeevan Mission", "theme": "Water", "type": "Central", "demography": "Rural", "benefit": "Functional Household Tap Connection (FHTC) to every rural home."},
        {"title": "Amrit Bharat Station Scheme", "theme": "Infrastructure", "type": "Central", "demography": "Urban", "benefit": "Modernization of railway stations (Relevant for Belagavi)."},
        
        # --- FARMERS & AGRICULTURE ---
        {"title": "PM Kisan Samman Nidhi", "theme": "Agriculture", "type": "Central", "demography": "Farmers", "benefit": "₹6,000 per year income support to farmers."},
        {"title": "Raitha Vidya Nidhi", "theme": "Education", "type": "State (Karnataka)", "demography": "Students (Farmers' Children)", "benefit": "Scholarship for children of farmers."},
        {"title": "PM Fasal Bima Yojana", "theme": "Agriculture", "type": "Central", "demography": "Farmers", "benefit": "Crop insurance against natural calamities."},
        
        # --- HEALTH & SANITATION ---
        {"title": "Ayushman Bharat (PMJAY)", "theme": "Health", "type": "Central", "demography": "BPL Families", "benefit": "Health cover of ₹5 Lakh per family per year."},
        {"title": "Arogya Karnataka", "theme": "Health", "type": "State (Karnataka)", "demography": "All Residents", "benefit": "Co-branded health assurance scheme with Ayushman Bharat."},
        {"title": "Swachh Bharat Mission 2.0", "theme": "Sanitation", "type": "Central", "demography": "Urban/Rural", "benefit": "Toilet construction and waste management funding."},
        
        # --- ECONOMY & SKILLS ---
        {"title": "PM Vishwakarma", "theme": "Skill Dev", "type": "Central", "demography": "Artisans/OBC", "benefit": "Collateral-free loans and skill training for artisans."},
        {"title": "Mudra Yojana (PMMY)", "theme": "Finance", "type": "Central", "demography": "Entrepreneurs", "benefit": "Loans up to ₹10 Lakh for small businesses."},
        {"title": "Stand-Up India", "theme": "Finance", "type": "Central", "demography": "SC/ST/Women", "benefit": "Bank loans between ₹10 Lakh and ₹1 Crore."},
        {"title": "PM SVANidhi", "theme": "Economy", "type": "Central", "demography": "Street Vendors", "benefit": "Micro-credit facility for street vendors."},
        
        # --- WOMEN & CHILD ---
        {"title": "Poshan Abhiyaan", "theme": "Health", "type": "Central", "demography": "Women/Children", "benefit": "Nutritional support for pregnant women and children."},
        {"title": "Beti Bachao Beti Padhao", "theme": "Social Welfare", "type": "Central", "demography": "Girl Child", "benefit": "Education and welfare grants for the girl child."},
        {"title": "Udyogini Scheme", "theme": "Employment", "type": "State (Karnataka)", "demography": "Women", "benefit": "Subsidized loans for women entrepreneurs."}
    ]

    # --- 3. FILTER DASHBOARD ---
    # We use a container to make the filters look like a control panel
    with st.container():
        c1, c2, c3 = st.columns([1, 1, 1])
        
        with c1:
            # Theme Filter
            all_themes = sorted(list(set([s['theme'] for s in schemes_db])))
            sel_theme = st.multiselect("📌 Filter by Theme", ["All"] + all_themes, default="All")
            
        with c2:
            # Demography Filter
            all_demos = sorted(list(set([s['demography'] for s in schemes_db])))
            sel_demo = st.multiselect("👥 Target Group", ["All"] + all_demos, default="All")
            
        with c3:
            # Type Filter (State vs Central)
            all_types = sorted(list(set([s['type'] for s in schemes_db])))
            sel_type = st.multiselect("🏛️ Gov Level", ["All"] + all_types, default="All")

    # --- 4. MATCHING LOGIC ---
    results = schemes_db

    # Apply Theme Filter
    if "All" not in sel_theme and len(sel_theme) > 0:
        results = [s for s in results if s['theme'] in sel_theme]

    # Apply Demography Filter
    if "All" not in sel_demo and len(sel_demo) > 0:
        results = [s for s in results if s['demography'] in sel_demo]

    # Apply Type Filter
    if "All" not in sel_type and len(sel_type) > 0:
        results = [s for s in results if s['type'] in sel_type]

    # --- 5. RESULTS DISPLAY (UNLIMITED) ---
    st.divider()
    
    # Dynamic Header based on count
    if len(results) > 0:
        st.success(f"✅ Found **{len(results)}** schemes matching your criteria.")
        
        # Display Loop
        for scheme in results:
            with st.expander(f"📄 **{scheme['title']}** |  {scheme['type']}"):
                c_left, c_right = st.columns([3, 1])
                with c_left:
                    st.markdown(f"**Benefit:** {scheme['benefit']}")
                    st.caption(f"**Sector:** {scheme['theme']}  |  **Target:** {scheme['demography']}")
                with c_right:
                    # Action Buttons
                    if st.button("Draft Letter", key=f"draft_{scheme['title']}"):
                        st.toast(f"Drafting recommendation for {scheme['title']}...")
                    if st.button("View Guidelines", key=f"guide_{scheme['title']}"):
                        st.info("Opening official guidelines PDF...")
    else:
        st.warning("⚠️ No schemes found. Try selecting 'All' to reset filters.")
        if st.button("Reset All Filters"):
            st.rerun()