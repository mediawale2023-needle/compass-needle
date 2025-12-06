import streamlit as st
from langchain_groq import ChatGroq
import json
import os
from modules.utils import track_action, show_download_button
from modules.persistence import save_draft

def render_matcher(user_tags=None):
    st.header("🎯 Fund Liquidity Radar (Schemes)")
    st.caption("Match constituency needs with active Government Schemes.")

    # --- 1. COMPREHENSIVE LISTS (Hardcoded for maximum coverage) ---
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
    
    # Set Defaults based on User Profile (so they don't start empty)
    default_geo = []
    default_demo = []
    
    if user_tags:
        for tag in user_tags:
            if tag in all_geographies: default_geo.append(tag)
            if tag in all_demographics: default_demo.append(tag)

    # --- 2. FILTER INTERFACE ---
    with st.expander("📍 Configure Search Filters", expanded=True):
        c1, c2 = st.columns(2)
        with c1: 
            selected_geo = st.multiselect("Geography", all_geographies, default=default_geo)
        with c2: 
            selected_demo = st.multiselect("Beneficiary / Demographics", all_demographics, default=default_demo)

    # --- 3. LOAD DATABASE ---
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

    # --- 4. SMART SCANNER ---
    if st.button("🔍 Scan for Funds"):
        if not (selected_geo or selected_demo):
            st.warning("Please select at least one Geography or Demographic to filter.")
        else:
            st.success(f"Scanning {len(schemes_db)} Schemes against your criteria...")
            
            matched_schemes = []
            user_criteria = set(selected_geo + selected_demo)
            
            for item in schemes_db:
                # A. Get Item Tags (Handle various formats)
                raw_tags = item.get('Focus', [])
                if isinstance(raw_tags, str): raw_tags = [raw_tags] # Handle string case
                
                scheme_tags = set([str(t).strip() for t in raw_tags])
                
                # B. SEMANTIC MATCHING (The "Smart" Part)
                # If tags are missing, check title/description for keywords
                full_text = (str(item.get('Description', '')) + " " + str(item.get('Scheme', ''))).lower()
                
                # Map keywords to your dropdown options
                keyword_map = {
                    "Farmers": ["kisan", "agriculture", "crop", "farm"],
                    "Women": ["mahila", "girl", "female", "widow", "shakti"],
                    "Students": ["scholarship", "school", "education", "vidya"],
                    "Urban": ["city", "municipal", "metro", "smart city"],
                    "Rural": ["gram", "village", "panchayat", "rural"],
                    "Health": ["ayushman", "health", "medical", "disease"],
                    "Tribal": ["tribal", "vanbasi", "forest"],
                    "Minority": ["minority", "madrassa", "waqf"],
                    "MSME": ["business", "entrepreneur", "startup", "loan"]
                }
                
                # Add inferred tags based on text analysis
                for tag, keywords in keyword_map.items():
                    if any(k in full_text for k in keywords):
                        scheme_tags.add(tag)

                # C. Find Intersection
                matches = user_criteria.intersection(scheme_tags)
                
                if len(matches) > 0:
                    item['Match_Score'] = len(matches)
                    item['Matched_Tags'] = list(matches)
                    matched_schemes.append(item)
            
            # Sort by Match Score (Most relevant first)
            matched_schemes.sort(key=lambda x: x['Match_Score'], reverse=True)
            
            if matched_schemes:
                st.write(f"Found **{len(matched_schemes)}** relevant schemes.")
                
                for item in matched_schemes[:50]: # Limit to top 50
                    with st.container():
                        c1, c2 = st.columns([3, 1])
                        with c1:
                            st.subheader(item.get('Scheme', 'Unknown'))
                            st.caption(f"Ministry: {item.get('Ministry', 'N/A')}")
                            st.success(f"✅ Matched: {', '.join(item['Matched_Tags'])}")
                        
                        with c2:
                            status = item.get('Status', 'Open')
                            if "Open" in status or "Active" in status: st.success(status)
                            else: st.error(status)
                            
                        with st.expander("View Details & Draft"):
                            st.write(f"**Grant:** {item.get('Grant', 'See Guidelines')}")
                            st.write(item.get('Description', ''))
                            
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
                                            Context: Matches needs: {', '.join(item['Matched_Tags'])}. Request immediate sanction.
                                            Tone: Official, Urgent.
                                            """
                                            
                                            draft = llm.invoke(prompt).content
                                            st.text_area("Draft Output", draft, height=300)
                                            
                                            # Save/Download
                                            username = st.session_state.get("current_user", "User")
                                            save_draft(username, f"Scheme: {item['Scheme']}", draft, "Proposal")
                                            show_download_button(draft, "Proposal")
                                            
                                            track_action(f"Drafted Proposal for {item['Scheme']}")
                                            
                                        except Exception as e:
                                            st.error(f"AI Error: {e}")
                        st.divider()
            else:
                st.warning("No schemes found for these specific filters. Try selecting broader categories.")