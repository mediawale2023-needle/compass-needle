import streamlit as st
from langchain_groq import ChatGroq
import json

def render_matcher(user_tags=None):
    st.header("🎯 Fund Liquidity Radar")
    st.caption("Real-time analysis of Ministry cash flows & Sanction Probability.")

    # 1. Profile Setup (Defaults from User Tags)
    default_geo = []
    default_demo = []
    if user_tags:
        # Note: This logic assumes specific tags exist in the user profile list
        if "Coastal" in user_tags: default_geo.append("Coastal")
        if "Urban" in user_tags: default_geo.append("Urban")
        if "Rural" in user_tags: default_geo.append("Rural")
        if "Fishermen" in user_tags: default_demo.append("Fishermen")

    with st.expander("📍 Target Profile", expanded=False):
        c1, c2 = st.columns(2)
        with c1: st.multiselect("Geography", ["Urban", "Rural", "Coastal", "Tribal"], default=default_geo)
        with c2: st.multiselect("Demographics", ["Fishermen", "Youth", "Women", "SC/ST"], default=default_demo)

    # 2. LOAD DATABASE
    try:
        with open("schemes.json", "r") as f:
            schemes_db = json.load(f)
    except FileNotFoundError:
        st.error("⚠️ schemes.json missing. Ask Admin to upload.")
        schemes_db = []

    # 3. SCANNER
    if st.button("🔍 Scan for Funds"):
        if schemes_db:
            st.success(f"Scanning {len(schemes_db)} Schemes against Live PQ Data...")
            
            for item in schemes_db:
                # Layout
                with st.container():
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.subheader(f"{item.get('Scheme', 'Unknown')}")
                        st.caption(f"Authority: {item.get('Ministry', 'Unknown')}")
                    with c2:
                        # Status Badge Logic (Based on confidence score in JSON)
                        status = item.get('Status', 'Unknown')
                        if item.get('Confidence', 0) > 80:
                            st.success(status)
                        elif item.get('Confidence', 0) > 50:
                            st.warning(status)
                        else:
                            st.error(status)

                    # Intelligence Box
                    with st.expander("💰 Liquidity Analysis", expanded=True):
                        b1, b2, b3 = st.columns(3)
                        b1.metric("Grant Size", item.get('Grant', 'N/A'))
                        b2.metric("Funds Left", item.get('Funds_Remaining', 'Unknown'))
                        b3.metric("Win Prob", f"{item.get('Confidence', 50)}%")
                        
                        st.info(f"🕵️ **Needle Verified:** {item.get('Evidence', 'Pending Analysis')}")

                    # Drafting Action
                    if item.get('Confidence', 0) > 50:
                        if st.button(f"Draft Application", key=item['Scheme']):
                            st.session_state['selected_scheme'] = item
                            st.rerun()
                    else:
                        st.button("Funds Exhausted", disabled=True, key=f"btn_{item.get('Scheme', 'x')}")
                    
                    st.divider()
        else:
            st.warning("Database is empty or failed to load.")

    # 4. DRAFTER LOGIC (Hidden until clicked)
    if 'selected_scheme' in st.session_state:
        item = st.session_state['selected_scheme']
        st.markdown("---")
        st.subheader(f"📝 Draft Proposal: {item['Scheme']}")
        
        if "api_key" not in st.session_state:
             st.session_state.api_key = st.text_input("Enter API Key", type="password")
        
        if st.button("Generate Official Letter") and st.session_state.api_key:
            llm = ChatGroq(temperature=0.5, groq_api_key=st.session_state.api_key, model_name="llama-3.1-8b-instant")
            
            prompt = f"Write a formal fund request letter. Scheme: {item['Scheme']}. Grant: {item['Grant']}. Ministry: {item['Ministry']}. Tone: Bureaucratic."
            with st.spinner("Drafting..."):
                st.text_area("Draft Output", llm.invoke(prompt).content, height=400)