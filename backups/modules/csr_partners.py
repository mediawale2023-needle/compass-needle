import streamlit as st
import json
import pandas as pd
from modules.settings import get_valid_model, init_keys
from modules.persistence import save_draft
from modules.utils import show_download_button, track_action

def render_csr_partners(username):
    st.header("🤝 CSR Implementation Partners")
    st.caption("Vetted NGO Registry. Match Corporates with Trusted Locals.")

    init_keys()

    # 1. Load Data (With Fallback)
    try:
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
        except: pass # Use mock data if file missing

        # Load Corporates
        corp_list = ["Reliance Industries", "Tata Group", "HDFC Bank"]
        try:
            with open("csr_db.json", "r") as f:
                corps = json.load(f)
                corp_list = [c['Company'] for c in corps]
        except: pass
            
    except Exception as e:
        st.error(f"System Error: {e}")
        return

    df = pd.DataFrame(data)

    # 2. Statistics
    c1, c2, c3 = st.columns(3)
    c1.metric("Total NGOs", len(df))
    # Safe counting
    green_count = len(df[df['Risk_Level'] == 'Green'])
    red_count = len(df[df['Risk_Level'] == 'Red'])
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

        with st.expander(f"{icon} {row['NGO_Name']} ({row.get('Sector', 'General')})"):
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
                
                # Unique key for selectbox
                target_corp = st.selectbox(f"Select Funder for {row['NGO_Name']}", corp_list, key=f"sel_{idx}_{row['NGO_Name']}")
                
                if st.button(f"Draft Recommendation Letter", key=f"rec_{idx}_{row['NGO_Name']}"):
                    with st.spinner("Drafting Introduction (Gemini)..."):
                        # 👇 CHANGED: Switched from Groq to Gemini
                        model = get_valid_model()
                        
                        if model:
                            try:
                                prompt = f"""
                                Write a formal 'Letter of Recommendation' from an Indian MP to the CSR Head of {target_corp}.
                                
                                Subject: Recommending {row['NGO_Name']} for CSR Implementation in {row['Sector']}.
                                
                                Details:
                                - The MP confirms that {row['NGO_Name']} is a vetted local partner with Valid CSR-1 ({row['CSR_1_Number']}).
                                - They have a strong track record in {row['Sector']}.
                                - This creates a trusted bridge between {target_corp}'s funds and ground execution.
                                
                                Tone: Professional endorsement.
                                """
                                response = model.generate_content(prompt)
                                draft = response.text
                                
                                # Save & Download
                                st.subheader("Draft Preview")
                                with st.container(border=True):
                                    st.text_area("Content", draft, height=250)
                                    
                                save_draft(username, f"Recommend: {row['NGO_Name']} to {target_corp}", draft, "Recommendation")
                                show_download_button(draft, f"Rec_{row['NGO_Name']}")
                                track_action(f"Recommended {row['NGO_Name']}")
                                
                            except Exception as e:
                                st.error(f"AI Error: {e}")
                        else:
                            st.error("System Offline. Check Settings.")
            else:
                st.error("Cannot recommend this NGO due to compliance issues.")