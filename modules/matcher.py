import streamlit as st
from langchain_groq import ChatGroq
import json
import os
from modules.utils import track_action, show_download_button
from modules.persistence import save_draft

def render_matcher(user_tags=None):
    st.header("🎯 Fund Liquidity Radar (Schemes)")
    st.caption("Match constituency needs with active Government Schemes & **2025-26 Budget Status**.")

    # --- 1. LOAD DATABASES ---
    schemes_db = []
    budget_db = []
    
    try:
        # Load Schemes (The big database)
        if os.path.exists("schemes.json"):
            with open("schemes.json", "r", encoding='utf-8') as f:
                schemes_db = json.load(f)
        else:
            st.warning("⚠️ 'schemes.json' not found. Please run the ingestion script.")
            
        # Load Budget (The financial data)
        if os.path.exists("budget_2025_26.json"):
            with open("budget_2025_26.json", "r", encoding='utf-8') as f:
                budget_db = json.load(f)
    except Exception as e:
        st.error(f"Error reading database: {e}")
        return

    # --- 2. EXTRACT MINISTRIES DYNAMICALLY ---
    # Scans your database to find all available Ministries for the dropdown
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
    
    # Defaults from User Profile
    default_geo = [t for t in (user_tags or []) if t in all_geographies]
    default_demo = [t for t in (user_tags or []) if t in all_demographics]

    # --- 4. FILTER INTERFACE ---
    with st.expander("📍 Configure Search Filters", expanded=True):
        # Ministry Filter (The Fix)
        selected_ministry = st.multiselect("🏛️ Filter by Ministry", all_ministries, placeholder="Select Ministry (e.g. Agriculture, Jal Shakti)")
        
        c1, c2 = st.columns(2)
        with c1: 
            selected_geo = st.multiselect("🌍 Geography", all_geographies, default=default_geo)
        with c2: 
            selected_demo = st.multiselect("👥 Beneficiary", all_demographics, default=default_demo)

    # --- 5. SCANNER LOGIC ---
    if st.button("🔍 Scan for Funds"):
        # We allow search if ANY filter is set (Ministry OR Geo OR Demo)
        if not (selected_geo or selected_demo or selected_ministry):
            st.warning("Please select at least one filter.")
        else:
            found_schemes = []
            user_criteria = set(selected_geo + selected_demo)
            
            for item in schemes_db:
                # A. MINISTRY FILTER (Hard Check)
                # If user selected a Ministry, we ONLY show schemes from that Ministry
                if selected_ministry:
                    if item.get('Ministry', '').strip() not in selected_ministry:
                        continue

                # B. TAG MATCHING (Soft Check)
                raw_tags = item.get('Focus', [])
                if isinstance(raw_tags, str): raw_tags = [raw_tags]
                scheme_tags = set([str(t).strip() for t in raw_tags])
                
                # C. KEYWORD MATCHING
                full_text = (str(item.get('Description', '')) + " " + str(item.get('Scheme', ''))).lower()
                keyword_map = {
                    "Farmers": ["kisan", "agriculture", "crop", "farm"],
                    "Women": ["mahila", "girl", "female", "widow", "shakti"],
                    "Students": ["scholarship", "school", "education", "vidya"],
                    "Urban": ["city", "municipal", "metro", "smart city", "amrut"],
                    "Rural": ["gram", "village", "panchayat", "mgnrega"],
                    "Health": ["ayushman", "health", "medical", "hospital"],
                    "Tribal": ["tribal", "vanbasi", "forest"],
                    "MSME": ["business", "loan", "pli", "industry", "credit"]
                }
                for tag, keywords in keyword_map.items():
                    if tag in user_criteria and any(k in full_text for k in keywords):
                        scheme_tags.add(tag)

                matches = user_criteria.intersection(scheme_tags)
                
                # Logic: If Geo/Demo filters ARE set, we need at least one match.
                # If ONLY Ministry is set, we show everything for that Ministry.
                if (selected_geo or selected_demo) and not matches and not selected_ministry:
                    continue

                item['Match_Score'] = len(matches)
                item['Matched_Tags'] = list(matches)
                
                # Boost Score for Budget
                boost = 0
                if "High" in item.get('Budget_Status', '') or "Green" in item.get('Budget_Status', ''):
                    boost = 100
                elif "Active" in item.get('Budget_Status', ''):
                    boost = 50

                item['Boost'] = boost
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
                    # Budget Badge
                    b_status = item.get('Budget_Status', 'Unknown')
                    b_alloc = item.get('Budget_Alloc', 'Check Dept')
                    
                    if "Green" in b_status or "High" in b_status or "Active" in b_status:
                        st.success(f"Budget: {b_status}")
                        if b_alloc != "Check Dept": st.caption(f"💰 {b_alloc}")
                    elif "Yellow" in b_status:
                        st.warning(f"Budget: {b_status}")
                    else:
                        st.info("Budget: Not Linked")

                # Details Expander with Tabs
                with st.expander("View Details & Guidelines"):
                    t1, t2, t3 = st.tabs(["Overview", "Eligibility & Docs", "Process"])
                    
                    with t1:
                        if item.get('Budget_Alloc') != "Check Dept":
                            st.info(f"**Budget Insight:** {item.get('Budget_Note', 'Allocated in 2025-26 Budget.')}")
                        st.write(f"**Description:** {item.get('Description', '')}")
                        st.write(f"**Grant:** {item.get('Grant', 'See Guidelines')}")

                    with t2:
                        st.write("### Eligibility")
                        st.write(item.get('Eligibility', 'Check Portal'))
                        st.write("### Documents Required")
                        st.write(item.get('Documents', 'Check Portal'))

                    with t3:
                        st.write("### Application Process")
                        st.write(item.get('Process', 'Check Portal'))

                    if st.button("Draft Proposal", key=f"btn_{item.get('Scheme')}"):
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
                                    - Scheme fits local needs ({', '.join(item.get('Matched_Tags', ['Development']))}).
                                    - 2025-26 Budget Allocation: {item.get('Budget_Alloc', 'N/A')}.
                                    - Requesting immediate sanction.
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
        c1, c2 = st.columns([1, 4])
        with c1:
            if st.button("💾 Save"):
                save_draft(st.session_state.get("current_user", "User"), st.session_state['final_draft_title'], st.session_state['final_draft_text'], "Proposal")
        with c2:
            show_download_button(st.session_state['final_draft_text'], "Proposal")