import streamlit as st
from langchain_groq import ChatGroq
import json
import os
from modules.utils import track_action, show_download_button
from modules.persistence import save_draft

def render_matcher(user_tags=None):
    st.header("🎯 Fund Liquidity Radar (Schemes)")
    st.caption("Browse Government Schemes by Geography & Demographics. Budget 2025-26 enabled.")

    # --- 1. LOAD DATABASE ---
    schemes_db = []
    try:
        if os.path.exists("schemes.json"):
            with open("schemes.json", "r") as f:
                schemes_db = json.load(f)
        else:
            st.error("⚠️ 'schemes.json' missing. Run 'final_data_build.py' or 'master_reset.py'.")
            return
    except Exception as e:
        st.error(f"Error loading database: {e}")
        return

    # --- 2. EXTRACT DYNAMIC FILTERS ---
    all_geographies = ["Urban", "Rural", "Tribal", "Coastal", "Border Area", "Hilly Area"]
    all_demographics = ["Farmers", "Women", "Youth", "SC/ST", "MSME", "Minority"]

    # --- 3. FILTER UI (Simplified) ---
    with st.expander("📍 Configuration: Select Area and Beneficiary", expanded=True):
        c1, c2 = st.columns(2)
        with c1: selected_geo = st.multiselect("🌍 Geography", all_geographies)
        with c2: selected_demo = st.multiselect("👥 Beneficiary", all_demographics)

    # --- 4. SCANNING LOGIC ---
    found_schemes = []
    
    for item in schemes_db:
        # Default: Include all if no filters selected
        include_item = True
        
        # Apply filters if they exist
        if selected_geo or selected_demo:
            # Prepare search text (Description + Focus tags)
            item_text = (str(item.get('Description', '')) + " " + str(item.get('Focus', ''))).lower()
            
            # Check Geography Match
            geo_match = True
            if selected_geo:
                geo_match = any(g.lower() in item_text for g in selected_geo)
            
            # Check Demographic Match
            demo_match = True
            if selected_demo:
                demo_match = any(d.lower() in item_text for d in selected_demo)
            
            # Must match BOTH criteria types if selected
            if not (geo_match and demo_match):
                include_item = False
        
        if include_item:
            found_schemes.append(item)

    # --- 5. DISPLAY SCHEME CARDS ---
    st.divider()
    
    # Limit display to top 50 to ensure speed
    display_list = found_schemes[:50]
    
    if not display_list:
        st.warning("No schemes found for these specific filters.")
    else:
        st.success(f"Displaying {len(display_list)} schemes.")

        # Iterate with index to ensure unique keys
        for i, scheme in enumerate(display_list):
            with st.container():
                col_title, col_status = st.columns([3, 1])
                with col_title:
                    st.subheader(scheme.get('Scheme', 'Unknown Scheme'))
                    st.caption(f"Administered by: **{scheme.get('Ministry', 'Central Govt')}**")
                
                with col_status:
                    # Show Budget Allocation Badge
                    alloc = scheme.get('Budget_Alloc', 'Check Dept')
                    if alloc != "Check Dept":
                        st.success(f"💰 {alloc}")
                    else:
                        st.info("Budget: N/A")

                # Detailed View
                with st.expander("🔍 View Scheme Details & Guidelines", expanded=False):
                    t1, t2, t3 = st.tabs(["Overview", "Eligibility & Docs", "Action"])
                    
                    with t1:
                        st.write(f"**Description:** {scheme.get('Description')}")
                        st.write(f"**Grant Details:** {scheme.get('Grant')}")
                    
                    with t2:
                        st.write(f"**Eligibility:** {scheme.get('Eligibility')}")
                        st.write(f"**Required Documents:** {scheme.get('Documents')}")
                        st.write(f"**Application Process:** {scheme.get('Process')}")

                    with t3:
                        # Unique key using index 'i' to prevent DuplicateKeyError
                        if st.button("📝 Draft Sanction Letter", key=f"draft_{i}"):
                            api_key = st.session_state.get('groq_api_key')
                            if not api_key:
                                st.error("Please enter Groq API Key in sidebar first.")
                            else:
                                with st.spinner("Drafting..."):
                                    try:
                                        llm = ChatGroq(temperature=0.5, groq_api_key=api_key, model_name="llama-3.1-8b-instant")
                                        prompt = f"""
                                        Write a formal letter from an MP requesting implementation of {scheme.get('Scheme')} in his district. 
                                        Mention current 2025 budget allocation ({scheme.get('Budget_Alloc', 'N/A')}) if applicable.
                                        """
                                        draft = llm.invoke(prompt).content
                                        st.text_area("Final Draft", draft, height=250)
                                        show_download_button(draft, f"{scheme.get('Scheme')}_proposal")
                                        save_draft("milind_deora", scheme.get('Scheme'), draft, "Letter")
                                    except Exception as e:
                                        st.error(f"AI Error: {e}")
            st.divider()