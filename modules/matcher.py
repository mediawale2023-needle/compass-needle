import streamlit as st
from langchain_groq import ChatGroq
import json
import os
from modules.utils import track_action, show_download_button
from modules.persistence import save_draft

def render_matcher(user_tags=None):
    st.header("🎯 Fund Liquidity Radar (Schemes)")
    st.caption("Match constituency needs with active Government Schemes.")

    # --- 1. LOAD DATABASE (Safe Load) ---
    schemes_db = []
    try:
        if os.path.exists("schemes.json"):
            with open("schemes.json", "r") as f:
                schemes_db = json.load(f)
        else:
            st.error("⚠️ 'schemes.json' not found. Please upload it in Admin panel.")
            return
    except Exception as e:
        st.error(f"Error reading database: {e}")
        return

    # --- 2. EXPANDED PROFILE LISTS ---
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
    
    # Defaults
    default_geo = []
    default_demo = []
    if user_tags:
        for tag in user_tags:
            if tag in all_geographies: default_geo.append(tag)
            if tag in all_demographics: default_demo.append(tag)

    # --- 3. FILTER INTERFACE (Always Visible) ---
    with st.expander("📍 Configure Search Filters", expanded=True):
        c1, c2 = st.columns(2)
        with c1: 
            selected_geo = st.multiselect("Geography", all_geographies, default=default_geo, key="geo_select")
        with c2: 
            selected_demo = st.multiselect("Beneficiary / Demographics", all_demographics, default=default_demo, key="demo_select")

    # --- 4. SCANNER LOGIC ---
    if st.button("🔍 Scan for Funds"):
        if not (selected_geo or selected_demo):
            st.warning("Please select at least one Geography or Demographic.")
        else:
            # Run the Search
            found_schemes = []
            user_criteria = set(selected_geo + selected_demo)
            
            for item in schemes_db:
                # A. Get Tags
                raw_tags = item.get('Focus', [])
                if isinstance(raw_tags, str): raw_tags = [raw_tags]
                scheme_tags = set([str(t).strip() for t in raw_tags])
                
                # B. Semantic Match
                full_text = (str(item.get('Description', '')) + " " + str(item.get('Scheme', ''))).lower()
                keyword_map = {
                    "Farmers": ["kisan", "agriculture", "crop"],
                    "Women": ["mahila", "girl", "female", "widow", "shakti"],
                    "Students": ["scholarship", "school", "education"],
                    "Urban": ["city", "municipal", "metro", "smart city"],
                    "Rural": ["gram", "village", "panchayat"],
                    "Health": ["ayushman", "health", "medical"],
                    "Tribal": ["tribal", "vanbasi"],
                    "Minority": ["minority", "madrassa", "waqf"],
                    "MSME": ["business", "entrepreneur", "loan"]
                }
                for tag, keywords in keyword_map.items():
                    if tag in user_criteria and any(k in full_text for k in keywords):
                        scheme_tags.add(tag)

                # C. Intersection
                matches = user_criteria.intersection(scheme_tags)
                
                if len(matches) > 0:
                    item['Match_Score'] = len(matches)
                    item['Matched_Tags'] = list(matches)
                    found_schemes.append(item)
            
            # Sort
            found_schemes.sort(key=lambda x: x['Match_Score'], reverse=True)
            
            # SAVE TO SESSION STATE (Persistence Fix)
            st.session_state['matched_results'] = found_schemes
            st.success(f"Found {len(found_schemes)} schemes. Results saved below.")

    # --- 5. DISPLAY RESULTS (Persistent) ---
    if 'matched_results' in st.session_state and st.session_state['matched_results']:
        results = st.session_state['matched_results']
        
        for item in results[:50]:
            with st.container():
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.subheader(item.get('Scheme', 'Unknown'))
                    st.caption(f"Ministry: {item.get('Ministry', 'N/A')}")
                    st.success(f"✅ Matched: {', '.join(item.get('Matched_Tags', []))}")
                
                with c2:
                    status = item.get('Status', 'Open')
                    if "Open" in status or "Active" in status: st.success(status)
                    else: st.error(status)
                    
                with st.expander("View Details & Draft"):
                    st.write(f"**Grant:** {item.get('Grant', 'See Guidelines')}")
                    st.write(item.get('Description', ''))
                    
                    # --- Rich Details Tabs ---
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
                                    Context: Matches needs: {', '.join(item.get('Matched_Tags', []))}. Request immediate sanction.
                                    Tone: Official, Urgent.
                                    """
                                    draft = llm.invoke(prompt).content
                                    
                                    # Save to Session State so it persists
                                    st.session_state['final_draft_text'] = draft
                                    st.session_state['final_draft_title'] = f"Proposal: {item['Scheme']}"
                                    track_action(f"Drafted Proposal for {item['Scheme']}")
                                    
                                except Exception as e:
                                    st.error(f"AI Error: {e}")

    # --- 6. SHOW DRAFT (Persistent) ---
    if 'final_draft_text' in st.session_state:
        st.markdown("---")
        st.subheader("📝 Final Draft")
        st.text_area("Output", st.session_state['final_draft_text'], height=300)
        
        c1, c2 = st.columns([1, 4])
        with c1:
            if st.button("💾 Save to Archive"):
                username = st.session_state.get("current_user", "User")
                save_draft(username, st.session_state['final_draft_title'], st.session_state['final_draft_text'], "Proposal")
        with c2:
            show_download_button(st.session_state['final_draft_text'], "Proposal")