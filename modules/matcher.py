import streamlit as st
from langchain_groq import ChatGroq
import json
import os
from modules.utils import track_action, show_download_button
from modules.persistence import save_draft

def render_matcher(user_tags=None):
    st.header("🎯 Fund Liquidity Radar (Schemes)")
    st.caption("Match constituency needs with active Government Schemes & **2025-26 Budget Status**.")

    # --- 1. THE TRUTH SOURCE (Embedded Budget Data) ---
    BUDGET_OVERLAY = {
        "jal jeevan": {"alloc": "₹67,000 Cr", "status": "🟢 Very High Liquidity", "note": "Target: 100% rural tap coverage by 2028."},
        "mgnrega": {"alloc": "₹86,000 Cr", "status": "🟡 Stagnant", "note": "Same as FY24. Demand-driven."},
        "pm-kisan": {"alloc": "₹60,000 Cr", "status": "🟢 Active", "note": "Direct Benefit Transfer stable."},
        "kisann": {"alloc": "₹60,000 Cr", "status": "🟢 Active", "note": "Direct Benefit Transfer stable."},
        "fasal bima": {"alloc": "₹12,242 Cr", "status": "🟢 Active", "note": "Crop Insurance allocation."},
        "krishi sinchai": {"alloc": "₹11,391 Cr", "status": "🟢 High", "note": "Focus on micro-irrigation."},
        "fame": {"alloc": "₹4,000 Cr (PM E-DRIVE)", "status": "🟢 Transformed", "note": "FAME is now PM E-DRIVE."},
        "electric vehicle": {"alloc": "₹4,000 Cr (PM E-DRIVE)", "status": "🟢 Transformed", "note": "Replaces FAME II."},
        "surya": {"alloc": "₹20,000 Cr", "status": "🟢 Massive Allocation", "note": "PM Surya Ghar Muft Bijli Yojana."},
        "solar": {"alloc": "₹20,000 Cr", "status": "🟢 Massive Allocation", "note": "PM Surya Ghar Muft Bijli Yojana."},
        "hydrogen": {"alloc": "₹600 Cr", "status": "🟢 Emerging", "note": "National Green Hydrogen Mission."},
        "pmay": {"alloc": "₹23,294 Cr (Urban)", "status": "🟢 Very High", "note": "Part of ₹10L Cr investment plan."},
        "awas": {"alloc": "₹23,294 Cr (Urban)", "status": "🟢 Very High", "note": "Part of ₹10L Cr investment plan."},
        "amrut": {"alloc": "₹10,000 Cr", "status": "🟢 Active", "note": "Smart Cities & Urban Rejuvenation."},
        "smart cit": {"alloc": "₹10,000 Cr", "status": "🟢 Active", "note": "Smart Cities Mission."},
        "swachh": {"alloc": "₹12,192 Cr (Total)", "status": "🟢 Active", "note": "Urban + Rural Sanitation."},
        "samagra": {"alloc": "₹41,250 Cr", "status": "🟢 High Liquidity", "note": "Flagship School Education Scheme."},
        "mid-day": {"alloc": "₹12,500 Cr", "status": "🟢 Active", "note": "PM-POSHAN Scheme."},
        "poshan": {"alloc": "₹21,960 Cr", "status": "🟢 Very High", "note": "Saksham Anganwadi & Poshan 2.0."},
        "anganwadi": {"alloc": "₹21,960 Cr", "status": "🟢 Very High", "note": "Saksham Anganwadi."},
        "health mission": {"alloc": "₹37,227 Cr", "status": "🟢 Active", "note": "National Health Mission (NHM)."},
        "ayushman": {"alloc": "₹9,406 Cr", "status": "🟢 High", "note": "PMJAY Insurance Cover."},
        "pli": {"alloc": "₹19,000 Cr (Total)", "status": "🟢 High Opportunity", "note": "Electronics, Auto, Textiles PLI."},
        "textile": {"alloc": "₹1,148 Cr (PLI)", "status": "🟢 Opportunity", "note": "25x increase in PLI allocation."},
        "khelo": {"alloc": "₹1,000 Cr", "status": "🟢 Active", "note": "Sports Development."},
        "sampada": {"alloc": "₹903 Cr", "status": "🟢 Active", "note": "Food Processing Infrastructure."},
        "svanidhi": {"alloc": "₹373 Cr", "status": "🟢 Active", "note": "Street Vendor Loans."}
    }

    # --- 2. LOAD SCHEMES ---
    schemes_db = []
    try:
        if os.path.exists("schemes.json"):
            with open("schemes.json", "r") as f:
                schemes_db = json.load(f)
        else:
            st.error("⚠️ 'schemes.json' not found. Please run the data pipeline.")
            return
    except Exception as e:
        st.error(f"Error reading database: {e}")
        return

    # --- 3. FILTER LISTS ---
    # Extract unique ministries for dropdown
    all_ministries = sorted(list(set([str(s.get('Ministry', '')).strip() for s in schemes_db if s.get('Ministry')])))
    
    # Safe fallback if extraction fails
    if not all_ministries:
        all_ministries = ["Ministry of Agriculture", "Ministry of Jal Shakti", "Ministry of Power", "Ministry of Education", "Ministry of Health"]

    all_geographies = ["Urban", "Rural", "Tribal", "Coastal", "Border Area", "Aspirational District"]
    all_demographics = ["Farmers", "Women", "Youth", "SC/ST", "Minority", "MSME", "Students"]
    
    # Defaults
    default_geo = [t for t in (user_tags or []) if t in all_geographies]
    default_demo = [t for t in (user_tags or []) if t in all_demographics]

    # --- 4. FILTER UI ---
    with st.expander("📍 Configure Search Filters", expanded=True):
        selected_ministry = st.multiselect("🏛️ Filter by Ministry", all_ministries)
        c1, c2 = st.columns(2)
        with c1: selected_geo = st.multiselect("🌍 Geography", all_geographies, default=default_geo)
        with c2: selected_demo = st.multiselect("👥 Beneficiary", all_demographics, default=default_demo)

    # --- 5. SCANNER LOGIC ---
    if st.button("🔍 Scan for Funds"):
        if not (selected_geo or selected_demo or selected_ministry):
            st.warning("Please select at least one filter.")
        else:
            found_schemes = []
            user_criteria = set(selected_geo + selected_demo)
            
            for item in schemes_db:
                # A. Ministry Filter
                if selected_ministry and item.get('Ministry', '').strip() not in selected_ministry:
                    continue

                # B. Keyword/Tag Matching
                raw_tags = item.get('Focus', [])
                if isinstance(raw_tags, str): raw_tags = [raw_tags]
                scheme_tags = set([str(t).strip() for t in raw_tags])
                
                full_text = (str(item.get('Description', '')) + " " + str(item.get('Scheme', ''))).lower()
                
                kw_map = {
                    "Farmers": ["kisan", "agriculture", "crop"], "Women": ["mahila", "girl", "female", "widow"],
                    "Students": ["scholarship", "school", "education"], "Urban": ["city", "municipal", "smart city", "amrut"],
                    "Rural": ["gram", "village", "panchayat", "mgnrega"], "Health": ["ayushman", "health", "medical"],
                    "Tribal": ["tribal", "vanbasi", "forest"], "MSME": ["business", "loan", "pli", "industry"],
                    "Fishermen": ["fish", "matsya", "boat"], "Water": ["jal", "water", "irrigation"]
                }
                for tag, keywords in kw_map.items():
                    if tag in user_criteria and any(k in full_text for k in keywords):
                        scheme_tags.add(tag)

                matches = user_criteria.intersection(scheme_tags)
                
                if (selected_geo or selected_demo) and not matches and not selected_ministry:
                    continue

                item['Matched_Tags'] = list(matches)
                item['Match_Score'] = len(matches)
                
                # C. BUDGET OVERLAY
                s_name_lower = item['Scheme'].lower()
                budget_hit = False
                
                for key, data in BUDGET_OVERLAY.items():
                    if key in s_name_lower:
                        item['Budget_Alloc'] = data['alloc']
                        item['Budget_Status'] = data['status']
                        item['Budget_Note'] = data['note']
                        item['Boost'] = 100
                        budget_hit = True
                        break
                
                if not budget_hit:
                    item['Budget_Alloc'] = "Check Dept"
                    item['Budget_Status'] = "Unknown"
                    item['Budget_Note'] = ""
                    item['Boost'] = 0

                found_schemes.append(item)
            
            # Sort
            found_schemes.sort(key=lambda x: (x['Boost'], x['Match_Score']), reverse=True)
            st.session_state['matched_results'] = found_schemes
            st.rerun()

    # --- 6. DISPLAY RESULTS ---
    if st.session_state.get('matched_results'):
        results = st.session_state['matched_results']
        st.success(f"Found {len(results)} relevant schemes.")
        
        # ERROR FIX: Added 'enumerate' to generate unique keys for buttons
        for i, item in enumerate(results[:50]):
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
                        st.success(f"Budget 25-26: {b_status}")
                        if b_alloc != "Check Dept": st.caption(f"💰 {b_alloc}")
                    elif "Yellow" in b_status:
                        st.warning(f"Budget 25-26: {b_status}")
                    else:
                        st.info("Budget: Not Linked")

                with st.expander("View Details & Guidelines"):
                    if item.get('Budget_Alloc') != "Check Dept":
                        st.markdown(f"### 💰 2025-26 Allocation: **{item['Budget_Alloc']}**")
                        st.info(f"**Intel:** {item['Budget_Note']}")
                    
                    st.write(item.get('Description', ''))
                    
                    # Details Tabs
                    t1, t2, t3 = st.tabs(["Eligibility", "Documents", "Process"])
                    with t1: st.write(item.get('Eligibility', 'Check Portal'))
                    with t2: st.write(item.get('Documents', 'Check Portal'))
                    with t3: st.write(item.get('Process', 'Check Portal'))

                    # ERROR FIX: Unique Key generated using index 'i'
                    if st.button("Draft Proposal", key=f"btn_{i}_{item.get('Scheme')}"):
                        api_key = st.session_state.get('groq_api_key')
                        if not api_key:
                            st.error("Enter API Key in Sidebar")
                        else:
                            with st.spinner("Drafting..."):
                                try:
                                    llm = ChatGroq(temperature=0.5, groq_api_key=api_key, model_name="llama-3.1-8b-instant")
                                    # Prompt logic
                                    budget_ctx = ""
                                    if item.get('Budget_Alloc') != "Check Dept":
                                        budget_ctx = f"- Note: 2025-26 Budget Allocation is {item['Budget_Alloc']}."
                                    
                                    prompt = f"""
                                    Write a formal letter from an MP to the Minister of {item.get('Ministry', 'Govt of India')}.
                                    Subject: Implementation of {item['Scheme']} in my constituency.
                                    Context: 
                                    - Matches local needs ({', '.join(item.get('Matched_Tags', ['Development']))}).
                                    {budget_ctx}
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
        c1, c2 = st.columns([1, 4])
        with c1:
            if st.button("💾 Save"):
                save_draft(st.session_state.get("current_user", "User"), st.session_state['final_draft_title'], st.session_state['final_draft_text'], "Proposal")
        with c2:
            show_download_button(st.session_state['final_draft_text'], "Proposal")