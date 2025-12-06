import streamlit as st
from langchain_groq import ChatGroq
import json
import os
from modules.utils import track_action, show_download_button
from modules.persistence import save_draft

def render_matcher(user_tags=None):
    st.header("🎯 Fund Liquidity Radar (Schemes)")
    
    # ... (Keep your existing Profile Setup & Filter Lists code here) ...
    # [Copy the lists 'all_geographies' and 'all_demographics' from previous version]
    # [Copy the 'with st.expander' filter block from previous version]
    
    # For brevity, I am pasting the updated SCANNER logic below:

    # --- 3. LOAD DATABASE ---
    schemes_db = []
    try:
        if os.path.exists("schemes.json"):
            with open("schemes.json", "r") as f: schemes_db = json.load(f)
    except: pass

    # --- 4. SMART SCANNER ---
    if st.button("🔍 Scan for Funds"):
        # ... (Keep existing matching logic) ...
        
        # [Assuming 'matched_schemes' list is generated as before]
        # matched_schemes = ... (your existing matching code)

        if matched_schemes:
            st.write(f"Found **{len(matched_schemes)}** relevant schemes.")
            
            for item in matched_schemes[:50]:
                with st.container():
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.subheader(item.get('Scheme', 'Unknown'))
                        st.caption(f"Ministry: {item.get('Ministry', 'N/A')}")
                    with c2:
                        st.success(item.get('Status', 'Open'))

                    # --- NEW: RICH DETAILS DISPLAY ---
                    with st.expander("📄 View Guidelines & Eligibility"):
                        
                        # Use Tabs to organize the heavy text
                        t_desc, t_elig, t_doc, t_proc = st.tabs(["About", "Eligibility", "Documents", "Process"])
                        
                        with t_desc:
                            st.write(item.get('Description', ''))
                            st.info(f"**Benefit:** {item.get('Grant', '')}")
                            
                        with t_elig:
                            st.write("### Who can apply?")
                            st.write(item.get('Eligibility', 'N/A'))
                            
                        with t_doc:
                            st.write("### Required Documents")
                            st.write(item.get('Documents', 'N/A'))
                            
                        with t_proc:
                            st.write("### Application Process")
                            st.write(item.get('Process', 'N/A'))
                        
                        st.divider()
                        
                        # Draft Button
                        if st.button(f"Draft Proposal", key=f"sc_{item.get('Scheme')}"):
                            api_key = st.session_state.get('groq_api_key')
                            if api_key:
                                with st.spinner("Drafting..."):
                                    llm = ChatGroq(temperature=0.5, groq_api_key=api_key, model_name="llama-3.1-8b-instant")
                                    prompt = f"""
                                    Write a formal fund request letter for {item['Scheme']}.
                                    Context:
                                    - Eligibility Confirmed: {item.get('Eligibility')[:200]}...
                                    - Requesting Benefit: {item.get('Grant')}
                                    Tone: Official.
                                    """
                                    draft = llm.invoke(prompt).content
                                    st.text_area("Draft", draft, height=300)
                                    show_download_button(draft, "Proposal")
                    st.divider()