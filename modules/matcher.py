import streamlit as st
from langchain_groq import ChatGroq
import json
import os
from modules.utils import track_action, show_download_button
from modules.persistence import save_draft

def render_matcher(user_tags=None):
    st.header("🎯 Fund Liquidity Radar (Schemes)")
    st.caption("Match constituency needs with active Government Schemes & 2025-26 Budget Status.")

    # --- 1. LOAD DATABASES ---
    schemes_db = []
    budget_db = []
    
    try:
        if os.path.exists("schemes.json"):
            with open("schemes.json", "r") as f:
                schemes_db = json.load(f)
        
        if os.path.exists("budget_2025_26.json"):
            with open("budget_2025_26.json", "r") as f:
                budget_db = json.load(f)
    except Exception as e:
        st.error(f"Error reading database: {e}")
        return

    # Budget Lookup Helper
    def get_budget_info(scheme_name):
        if not budget_db: return None
        for b in budget_db:
            # Fuzzy match: check if budget scheme name matches database scheme name
            s_name = scheme_name.lower()
            b_name = b['Scheme'].lower()
            
            # Match partial names (e.g. "Jal Jeevan" in "Jal Jeevan Mission")
            if b_name in s_name or s_name in b_name:
                return b
            
            # Special aliases for common schemes
            if "mgnrega" in b_name and "employment" in s_name: return b
            if "pmay" in b_name and "awas" in s_name: return b
            if "pli" in b_name and "production" in s_name: return b
            
        return None

    # --- 2. EXPANDED PROFILE LISTS (HARDCODED FOR VISIBILITY) ---
    # These lists will ALWAYS show up in the dropdown
    all_geographies = [
        "Urban", "Rural", "Semi-Urban", "Tribal (Scheduled Area)", "Coastal", 
        "Hilly Area", "Border Area", "Aspirational District", "Industrial Zone", 
        "North East Region", "Drought Prone", "Flood Prone", "LWE Affected", "Island"
    ]
    
    all_demographics = [
        "Farmers", "Fishermen", "Youth (18-35)", "Women", "Children", 
        "Senior Citizens", "SC (Scheduled Caste)", "ST (Scheduled Tribe)", 
        "OBC", "Minority Communities", "Disabled (Divyangjan)", 
        "Artisans", "Weavers", "Street Vendors", "MSME Owners", 
        "Students", "Transgender", "BPL (Below Poverty Line)", "Ex-Servicemen"
    ]
    
    # Set defaults based on user profile, but allow changing
    default_geo = []
    default_demo = []
    if user_tags:
        for tag in user_tags:
            if tag in all_geographies: default_geo.append(tag)
            if tag in all_demographics: default_demo.append(tag)

    with st.expander("📍 Configure Search Filters", expanded=True):
        c1, c2 = st.columns(2)
        with c1: 
            selected_geo = st.multiselect("Geography", all_geographies, default=default_geo, key="geo_select")
        with c2: 
            selected_demo = st.multiselect("Beneficiary / Demographics", all_demographics, default=default_demo, key="demo_select")

    # --- 3. SCANNER LOGIC ---
    if st.button("🔍 Scan for Funds"):
        # Allow searching even if no filter is selected (shows all)
        if not (selected_geo or selected_demo):
            st.info("Scanning all schemes (No filters selected)...")
            user_criteria = set()
        else:
            st.success(f"Scanning against: {', '.join(selected_geo + selected_demo)}")
            user_criteria = set(selected_geo + selected_demo)
            
        found_schemes = []
        
        for item in schemes_db:
            # A. Tag Matching
            raw_tags = item.get('Focus', [])
            if isinstance(raw_tags, str): raw_tags = [raw_tags]
            scheme_tags = set([str(t).strip() for t in raw_tags])
            
            # B. Semantic Match (Keyword Mapping)
            full_text = (str(item.get('Description', '')) + " " + str(item.get('Scheme', ''))).lower()
            keyword_map = {
                "Farmers": ["kisan", "agriculture", "crop", "farm"],
                "Women": ["mahila", "girl", "female", "widow", "shakti", "lakhpati"],
                "Students": ["scholarship", "school", "education", "vidya"],
                "Urban": ["city", "municipal", "metro", "smart city", "amrut"],
                "Rural": ["gram", "village", "panchayat", "mgnrega", "rural"],
                "Health": ["ayushman", "health", "medical", "hospital"],
                "Tribal": ["tribal", "vanbasi", "forest"],
                "Minority": ["minority", "madrassa", "waqf"],
                "MSME": ["business", "entrepreneur", "loan", "pli", "industry"],
                "Fishermen": ["fish", "matsya", "blue revolution", "boat"],
                "Water": ["jal", "water", "irrigation", "clean"]
            }
            
            # Add implied tags based on text
            for tag, keywords in keyword_map.items():
                if any(k in full_text for k in keywords):
                    scheme_tags.add(tag)

            # C. Intersection
            if user_criteria:
                matches = user_criteria.intersection(scheme_tags)
                match_score = len(matches)
            else:
                matches = set()
                match_score = 1 # Show everything if no filter
            
            if match_score > 0:
                item['Match_Score'] = match_score
                item['Matched_Tags'] = list(matches)
                
                # D. MERGE BUDGET INTEL
                budget_info = get_budget_info(item['Scheme'])
                if budget_info:
                    item['Budget_Alloc'] = budget_info['Allocation_2025_26']
                    item['Budget_Status'] = budget_info['Status']
                    item['Budget_Note'] = budget_info['Notes']
                    item['Boost'] = 100 # Push budgeted schemes to top
                else:
                    item['Budget_Alloc'] = "Unknown"
                    item['Budget_Status'] = "Check Dept"
                    item['Budget_Note'] = ""
                    item['Boost'] = 0

                found_schemes.append(item)
        
        # Sort by Budget Boost first, then Match Score
        found_schemes.sort(key=lambda x: (x['Boost'], x['Match_Score']), reverse=True)
        
        # Save to Session State
        st.session_state['matched_results'] = found_schemes

    # --- 4. DISPLAY RESULTS ---
    if 'matched_results' in st.session_state:
        results = st.session_state['matched_results']
        
        if not results:
            st.warning("No matching schemes found.")
        else:
            for item in results[:50]:
                with st.container():
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.subheader(item.get('Scheme', 'Unknown'))
                        st.caption(f"Ministry: {item.get('Ministry', 'N/A')}")
                        if item.get('Matched_Tags'):
                            st.success(f"✅ Matched: {', '.join(item['Matched_Tags'])}")
                    
                    with c2:
                        # Show Budget Status
                        b_status = item.get('Budget_Status', 'Unknown')
                        b_alloc = item.get('Budget_Alloc', 'N/A')
                        
                        if "Green" in b_status or "High" in b_status or "Open" in b_status:
                            st.success(f"Budget 25-26: {b_status}")
                            if b_alloc != "Unknown": st.caption(f"💰 {b_alloc}")
                        elif "Yellow" in b_status:
                            st.warning(f"Budget 25-26: {b_status}")
                        else:
                            st.info("Budget: Not Linked")
                        
                    with st.expander("View Details & Draft"):
                        if item.get('Budget_Alloc') != "Unknown":
                            st.info(f"**Budget Intel:** {item.get('Budget_Note')}")
                        
                        st.write(f"**Grant:** {item.get('Grant', 'See Guidelines')}")
                        st.write(item.get('Description', ''))
                        
                        # Rich Details Tabs
                        t1, t2, t3 = st.tabs(["Eligibility", "Documents", "Process"])
                        with t1: st.write(item.get('Eligibility', 'Check Portal'))
                        with t2: st.write(item.get('Documents', 'Check Portal'))
                        with t3: st.write(item.get('Process', 'Check Portal'))

                        if st.button(f"Draft Proposal", key=f"sc_{item.get('Scheme')}"):
                            api_key = st.session_state.get('groq_api_key')
                            if not api_key:
                                st.error("Enter API Key in Sidebar")
                            else:
                                with st.spinner("Drafting..."):
                                    try:
                                        llm = ChatGroq(temperature=0.5, groq_api_key=api_key, model_name="llama-3.1-8b-instant")
                                        prompt = f"""
                                        Write a formal fund request letter from an MP to the Minister of {item.get('Ministry', 'Govt of India')}.
                                        Subject: Implementation of {item['Scheme']} in my constituency.
                                        Context: 
                                        - Matches local needs: {', '.join(item.get('Matched_Tags', ['Constituency Development']))}. 
                                        - Budget Allocation 2025-26: {item.get('Budget_Alloc', 'N/A')}.
                                        - Request immediate sanction.
                                        Tone: Official, Urgent.
                                        """
                                        draft = llm.invoke(prompt).content
                                        st.session_state['final_draft_text'] = draft
                                        st.session_state['final_draft_title'] = f"Proposal: {item['Scheme']}"
                                        track_action(f"Drafted Proposal for {item['Scheme']}")
                                    except Exception as e:
                                        st.error(f"AI Error: {e}")
                st.divider()

    # --- 5. SHOW DRAFT ---
    if st.session_state.get('final_draft_text'):
        st.markdown("---")
        st.subheader("📝 Final Draft")
        st.text_area("Output", st.session_state['final_draft_text'], height=400)
        
        c1, c2 = st.columns([1, 4])
        with c1:
            if st.button("💾 Save to Archive"):
                username = st.session_state.get("current_user", "User")
                save_draft(username, st.session_state['final_draft_title'], st.session_state['final_draft_text'], "Proposal")
        with c2:
            show_download_button(st.session_state['final_draft_text'], "Proposal")