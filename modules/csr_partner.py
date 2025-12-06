import streamlit as st
import json
import pandas as pd
from langchain_groq import ChatGroq
from modules.persistence import save_draft
from modules.utils import show_download_button

def render_csr_partners(username):
    st.header("🤝 CSR Implementation Partners")
    st.caption("Vetted NGO Registry.")

    try:
        with open("ngo_db.json", "r") as f: data = json.load(f)
        with open("csr_db.json", "r") as f: corps = json.load(f)
        corp_list = [c['Company'] for c in corps]
    except:
        st.error("Database missing.")
        return

    df = pd.DataFrame(data)
    
    for idx, row in df.iterrows():
        icon = "✅" if row['Risk_Level'] == 'Green' else "🚫"
        with st.expander(f"{icon} {row['NGO_Name']} ({row['Sector']})"):
            st.write(f"**CSR-1:** `{row['CSR_1_Number']}`")
            st.write(f"**Status:** {row['Compliance_Status']}")
            
            if row['Risk_Level'] == 'Green':
                target_corp = st.selectbox(f"Connect to:", corp_list, key=f"sel_{idx}")
                if st.button(f"Draft Recommendation", key=f"rec_{idx}"):
                    api_key = st.session_state.get('groq_api_key')
                    if api_key:
                        llm = ChatGroq(temperature=0.6, groq_api_key=api_key, model_name="llama-3.1-8b-instant")
                        draft = llm.invoke(f"Write a recommendation letter for {row['NGO_Name']} to {target_corp}.").content
                        st.text_area("Draft", draft, height=200)
                        save_draft(username, f"Recommend: {row['NGO_Name']}", draft, "Letter")
                        show_download_button(draft, "Recommendation")