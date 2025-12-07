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
        else:
            st.warning("⚠️ 'schemes.json' not found. Please upload it via Admin.")
            
        if os.path.exists("budget_2025_26.json"):
            with open("budget_2025_26.json", "r") as f:
                budget_db = json.load(f)
    except Exception as e:
        st.error(f"Error reading database: {e}")
        return

    # --- 2. EXTRACT MINISTRIES DYNAMICALLY ---
    # This ensures the dropdown always matches your actual data
    unique_ministries = set()
    for s in schemes_db:
        if s.get('Ministry'):
            unique_ministries.add(str(s['Ministry']).strip())
    all_ministries = sorted(list(unique_ministries))

    # --- 3. FILTER LISTS ---
    all_geographies = [
        "Urban", "Rural", "Semi-Urban", "Tribal (Scheduled Area)", "Coastal", 
        "Hilly Area", "Border Area", "Aspirational District", "Industrial Zone", 
        "North East Region", "Drought Prone", "Flood Prone", "LWE Affected"
    ]
    all_demographics = [
        "Farmers", "Fishermen", "Youth (18-35)", "Women", "Children", 
        "Senior Citizens", "SC (Scheduled Caste)", "ST (Scheduled Tribe)", 
        "OBC", "Minority Communities", "Disabled (Divyangjan)", "MSME Owners",
        "Artisans", "Weavers", "Street Vendors", "Students", "BPL"
    ]
    
    # Defaults
    default_geo = [t for t in (user_tags or []) if t in all_geographies]
    default_demo = [t for t in (user_tags or []) if t in all_demographics]

    # --- 4. FILTER UI ---
    with st.expander("📍 Configure Search Filters", expanded=True):
        # Row 1: Ministry (Full Width)
        selected_ministry = st.multiselect("🏛️ Filter by Ministry (Optional)", all_ministries, placeholder="Select Ministries (e.g. Agriculture, Jal Shakti)")
        
        # Row 2: Geo & Demo
        c1, c2 = st.columns(2)
        with c1: selected_geo = st.multiselect("🌍 Geography", all_geographies, default=default_geo)
        with c2: selected_demo = st.multiselect("👥 Beneficiary", all_demographics, default=default_demo)

    # Helper for Budget
    def get_budget_info(scheme_name):
        if not budget_db: return None
        for b in budget_db:
            if b['Scheme'].lower() in scheme_name.lower() or scheme_name.lower() in b['Scheme'].lower(): return b
            if "mgnrega" in b['Scheme'].lower() and "employment" in scheme_name.lower(): return b
            if "pmay" in b['Scheme'].lower() and "awas" in scheme_name.lower(): return b
        return None

    # --- 5. SCANNER LOGIC ---
    if st.button("🔍 Scan for Funds"):
        # We allow search if ANY filter is set
        if not (selected_geo or selected_demo or selected_ministry):
            st.warning("Please select at least one filter.")
        else:
            found_schemes = []
            user_criteria = set(selected_geo + selected_demo)
            
            for item in schemes_db:
                # A. MINISTRY FILTER (Hard Filter)
                # If user selected specific ministries, skip schemes that don't match
                if selected_ministry:
                    if item.get('Ministry', '').strip() not in selected_ministry:
                        continue

                # B. TAG MATCHING (Soft Score)
                raw_tags = item.get('Focus', [])
                if isinstance(raw_tags, str): raw_tags = [raw_tags]
                scheme_tags = set([str(t).strip() for t in raw_tags])
                
                # C. KEYWORD MATCHING
                full_text = (str(item.get('Description', '')) + " " + str(item.get('Scheme', ''))).lower()
                keyword_map = {
                    "Farmers": ["kisan", "agriculture", "crop"], "Women": ["mahila", "girl", "female", "widow"],
                    "Students": ["scholarship", "school", "education"], "Urban": ["city", "municipal", "smart city", "amrut"],
                    "Rural": ["gram", "village", "panchayat", "mgnrega"], "Health": ["ayushman", "health", "medical"],
                    "Tribal": ["tribal", "vanbasi"], "MSME": ["business", "loan", "pli", "industry"]
                }
                for tag, keywords in keyword_map.items():
                    if tag in user_criteria and any(k in full_text for k in keywords):
                        scheme_tags.add(tag)

                # D. SCORING
                # If Geo/Demo filters are set, we score. If only Ministry is set, we show all for that Ministry.
                matches = user_criteria.intersection(scheme_tags)
                
                # Logic: If Geo/Demo selected, must match at least one OR be in selected Ministry
                if (selected_geo or selected_demo) and not matches and not selected_ministry:
                    continue 

                item['Match_Score'] = len(matches)
                item['Matched_Tags'] = list(matches)
                
                # E. BUDGET INTEL
                budget_info = get_budget_info(item['Scheme'])
                if budget_info:
                    item['Budget_Alloc'] = budget_info['Allocation_2025_26']
                    item['Budget_Status'] = budget_info['Status']
                    item['Budget_Note'] = budget_info['Notes']
                    item['Boost'] = 100
                else:
                    item['Budget_Alloc'] = "Unknown"
                    item['Budget_Status'] = "Check Dept"
                    item['Budget_Note'] = ""
                    item['Boost'] = 0

                found_schemes.append(item)
            
            # Sort: Budget Priority -> Relevance -> Alphabetical
            found_schemes.sort(key=lambda x: (x['Boost'], x['Match_Score']), reverse=True)
            st.session_state['matched_results'] = found_schemes
            st.rerun()

    # --- 6. DISPLAY RESULTS ---
    if st.session_state.get('matched_results'):
        results = st.session_state['matched_results']
        st.success(f"Found {len(results)} relevant schemes.")
        
        for item in results[:50]:
            with st.container():
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.subheader(item.get('Scheme', 'Unknown'))
                    st.caption(f"Ministry: {item.get('Ministry', 'N/A')}")
                    if item.get('Matched_Tags'):
                        st.success(f"✅ Matched: {', '.join(item['Matched_Tags'])}")
                
                with c2:
                    b_status = item.get('Budget_Status', 'Unknown')
                    if "Green" in b_status or "High" in b_status:
                        st.success(f"Budget 25-26: {b_status}")
                    elif "Yellow" in b_status:
                        st.warning(f"Budget 25-26: {b_status}")
                    else:
                        st.info("Budget: Not Linked")

                with st.expander("View Details & Draft"):
                    # Tabs for Details
                    tab_ov, tab_elig, tab_doc, tab_proc = st.tabs(["Overview", "Eligibility", "Documents", "Process"])
                    
                    with tab_ov:
                        if item.get('Budget_Alloc') != "Unknown":
                            st.info(f"💰 **2025 Allocation:** {item['Budget_Alloc']} | **Note:** {item['Budget_Note']}")
                        st.write(f"**Description:** {item.get('Description', '')}")
                        st.write(f"**Grant:** {item.get('Grant', 'Check Guidelines')}")

                    with tab_elig: st.write(item.get('Eligibility', 'Check Portal'))
                    with tab_doc: st.write(item.get('Documents', 'Check Portal'))
                    with tab_proc: st.write(item.get('Process', 'Check Portal'))

                    # Draft Button
                    if st.button("Draft Proposal", key=f"sc_{item.get('Scheme')}"):
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
                                    - Scheme matches local needs: {', '.join(item.get('Matched_Tags', ['Development']))}.
                                    - Budget 2025 Allocation: {item.get('Budget_Alloc', 'N/A')}.
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

    # --- 7. SAVE DRAFT ---
    if st.session_state.get('final_draft_text'):
        st.markdown("---")
        st.subheader("📝 Final Draft")
        st.text_area("Output", st.session_state['final_draft_text'], height=400)
        c1, c2 = st.columns([1,4])
        with c1:
            if st.button("💾 Save"):
                save_draft(st.session_state.get("current_user", "User"), st.session_state['final_draft_title'], st.session_state['final_draft_text'], "Proposal")
        with c2:
            show_download_button(st.session_state['final_draft_text'], "Proposal")