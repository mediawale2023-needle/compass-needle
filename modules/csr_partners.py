import streamlit as st
import json
import pandas as pd
from langchain_groq import ChatGroq
from modules.persistence import save_draft
from modules.utils import show_download_button, track_action

def render_csr_partners(username):
    st.header("🤝 CSR Implementation Partners")
    st.caption("Vetted NGO Registry. Match Corporates with Trusted Locals.")

    # 1. Load Data
    try:
        with open("ngo_db.json", "r") as f:
            data = json.load(f)
        
        # Load Corporates for the "Match" dropdown
        with open("csr_db.json", "r") as f:
            corps = json.load(f)
            corp_list = [c['Company'] for c in corps]
            
    except FileNotFoundError:
        st.error("Database missing. Please run 'generate_ngo_db.py' locally and upload 'ngo_db.json'.")
        return

    df = pd.DataFrame(data)

    # 2. Statistics
    c1, c2, c3 = st.columns(3)
    c1.metric("Total NGOs", len(df))
    c2.metric("Verified (Green)", len(df[df['Risk_Level'] == 'Green']))
    c3.metric("Blacklisted (Red)", len(df[df['Risk_Level'] == 'Red']))

    st.divider()

    # 3. Filter
    sector_filter = st.selectbox("Filter by Sector", ["All"] + list(df['Sector'].unique()))
    if sector_filter != "All":
        df = df[df['Sector'] == sector_filter]

    # 4. The Registry
    for idx, row in df.iterrows():
        # Color Code the Card
        if row['Risk_Level'] == 'Green':
            icon = "✅"
            color = "green"
        elif row['Risk_Level'] == 'Yellow':
            icon = "⚠️"
            color = "orange"
        else:
            icon = "🚫"
            color = "red"

        with st.expander(f"{icon} {row['NGO_Name']} ({row['Sector']})"):
            c1, c2 = st.columns([2, 1])
            with c1:
                st.write(f"**CSR-1 Number:** `{row['CSR_1_Number']}`")
                st.write(f"**Darpan ID:** `{row['Darpan_ID']}`")
                st.write(f"**Capacity:** {row['Capabilities']}")
            with c2:
                st.markdown(f"**Compliance:** :{color}[{row['Compliance_Status']}]")
                st.caption(f"Audit: {row['Last_Audit']}")

            # 5. The "Matchmaker"
            if row['Risk_Level'] == 'Green':
                st.markdown("---")
                st.write("**🔗 Connect to Corporate**")
                
                target_corp = st.selectbox(f"Select Funder for {row['NGO_Name']}", corp_list, key=f"sel_{idx}")
                
                if st.button(f"Draft Recommendation Letter", key=f"rec_{idx}"):
                    api_key = st.session_state.get('groq_api_key')
                    if not api_key:
                        st.error("Enter Groq API Key in Sidebar")
                    else:
                        with st.spinner("Drafting Introduction..."):
                            try:
                                llm = ChatGroq(temperature=0.6, groq_api_key=api_key, model_name="llama-3.1-8b-instant")
                                prompt = f"""
                                Write a formal 'Letter of Recommendation' from an Indian MP to the CSR Head of {target_corp}.
                                
                                Subject: Recommending {row['NGO_Name']} for CSR Implementation in {row['Sector']}.
                                
                                Details:
                                - The MP confirms that {row['NGO_Name']} is a vetted local partner with Valid CSR-1 ({row['CSR_1_Number']}).
                                - They have a strong track record in {row['Sector']}.
                                - This creates a trusted bridge between {target_corp}'s funds and ground execution.
                                
                                Tone: Professional endorsement.
                                """
                                draft = llm.invoke(prompt).content
                                
                                # Save & Download
                                st.text_area("Draft", draft, height=250)
                                save_draft(username, f"Recommend: {row['NGO_Name']} to {target_corp}", draft, "Recommendation")
                                show_download_button(draft, f"Rec_{row['NGO_Name']}")
                                track_action(f"Recommended {row['NGO_Name']}")
                                
                            except Exception as e:
                                st.error(f"Error: {e}")
            else:
                st.error("Cannot recommend this NGO due to compliance issues.")