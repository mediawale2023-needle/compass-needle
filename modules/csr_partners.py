import streamlit as st
import json
import pandas as pd
from openai import OpenAI
import os
from modules.settings import init_keys
from modules.persistence import save_draft
from modules.utils import show_download_button, track_action
from modules.ai_helpers import get_openai_client, ask_openai

# --- TAD NECESSARY: Removed global client initialization to prevent Railway boot crash ---

def render_csr_partners(username):
    from modules.ui_theme import inject_theme
    inject_theme()
    st.header("CSR Implementation Partners")
    st.caption("Vetted NGO Registry. Match Corporates with Trusted Locals.")

    init_keys()

    # Default Mock Data to prevent crash
    data = [
        {"NGO_Name": "Seva Foundation", "Sector": "Health", "CSR_1_Number": "CSR00123", "Darpan_ID": "MH/2020/01", "Risk_Level": "Green", "Compliance_Status": "Clean", "Capabilities": "Mobile Clinics", "Last_Audit": "2024-03"},
        {"NGO_Name": "Green Earth", "Sector": "Environment", "CSR_1_Number": "CSR00999", "Darpan_ID": "DL/2019/55", "Risk_Level": "Yellow", "Compliance_Status": "FCRA Pending", "Capabilities": "Tree Plantation", "Last_Audit": "2023-12"},
        {"NGO_Name": "EduCare Trust", "Sector": "Education", "CSR_1_Number": "CSR00456", "Darpan_ID": "KA/2021/88", "Risk_Level": "Green", "Compliance_Status": "Clean", "Capabilities": "Smart Classes", "Last_Audit": "2024-01"}
    ]
    
    # Try Loading Real File
    try:
        with open("ngo_db.json", "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        pass  # Use fallback mock data
    except Exception as e:
        st.warning(f"⚠️ Could not parse ngo_db.json: {e}. Using default data.")

    # Load Corporates
    corp_list = ["Reliance Industries", "Tata Group", "HDFC Bank"]
    try:
        with open("csr_db.json", "r") as f:
            corps = json.load(f)
            corp_list = [c.get('Company') for c in corps if c.get('Company')]
            if not corp_list:
                corp_list = ["Reliance Industries", "Tata Group", "HDFC Bank"]
    except FileNotFoundError:
        pass  # Use fallback list
    except Exception as e:
        st.warning(f"⚠️ Could not parse csr_db.json: {e}. Using default company list.")

    df = pd.DataFrame(data)

    # 2. Statistics
    c1, c2, c3 = st.columns(3)
    c1.metric("Total NGOs", len(df))
    # Safe counting
    green_count = len(df[df['Risk_Level'] == 'Green']) if 'Risk_Level' in df.columns else 0
    red_count = len(df[df['Risk_Level'] == 'Red']) if 'Risk_Level' in df.columns else 0
    c2.metric("Verified (Green)", green_count)
    c3.metric("Blacklisted (Red)", red_count)

    st.divider()

    # 3. Filter
    sector_options = ["All"]
    if 'Sector' in df.columns:
        sector_options += list(df['Sector'].unique())
        
    sector_filter = st.selectbox("Filter by Sector", sector_options)
    
    if sector_filter != "All":
        df = df[df['Sector'] == sector_filter]

    # 4. The Registry
    for idx, row in df.iterrows():
        ngo_name = row.get('NGO_Name', 'Unknown NGO')
        # Color Code the Card
        risk = row.get('Risk_Level', 'Yellow')
        if risk == 'Green':
            icon = "✅"
            color = "green"
        elif risk == 'Yellow':
            icon = "⚠️"
            color = "orange"
        else:
            icon = "🚫"
            color = "red"

        with st.expander(f"{icon} {ngo_name} ({row.get('Sector', 'General')})"):
            c1, c2 = st.columns([2, 1])
            with c1:
                st.write(f"**CSR-1 Number:** `{row.get('CSR_1_Number', 'N/A')}`")
                st.write(f"**Darpan ID:** `{row.get('Darpan_ID', 'N/A')}`")
                st.write(f"**Capacity:** {row.get('Capabilities', 'N/A')}")
            with c2:
                status = row.get('Compliance_Status', 'Unknown')
                st.markdown(f"**Compliance:** :{color}[{status}]")
                st.caption(f"Audit: {row.get('Last_Audit', 'N/A')}")

            # 5. The "Matchmaker"
            if risk == 'Green':
                st.markdown("---")
                st.write("**🔗 Connect to Corporate**")
                
                target_corp = st.selectbox(f"Select Funder for {ngo_name}", corp_list, key=f"sel_{idx}_{ngo_name}")
                
                if st.button(f"Draft Recommendation Letter", key=f"rec_{idx}_{ngo_name}"):
                    with st.spinner("Drafting Recommendation via OpenAI..."):
                        prompt = f"""
                        Write a formal 'Letter of Recommendation' from an Indian Member of Parliament to the CSR Head of {target_corp}.
                        
                        Subject: Recommending {ngo_name} for CSR Implementation in {row.get('Sector', 'General')}.
                        
                        Details:
                        - The MP confirms that {ngo_name} is a vetted local partner with Valid CSR-1 ({row.get('CSR_1_Number', 'N/A')}).
                        - They have a strong track record in {row.get('Sector', 'General')}.
                        - This creates a trusted bridge between {target_corp}'s funds and ground execution.
                        
                        Tone: Professional endorsement, authoritative.
                        """
                        draft = ask_openai(prompt)
                        
                        # Save & Download
                        st.subheader("Draft Preview")
                        with st.container(border=True):
                            st.text_area("Content", draft, height=250)
                            
                        save_draft(username, f"Recommend: {ngo_name} to {target_corp}", draft, "Recommendation")
                        show_download_button(draft, f"Rec_{ngo_name}")
                        track_action(f"Recommended {ngo_name}")
            else:
                st.error("Cannot recommend this NGO due to compliance issues.")