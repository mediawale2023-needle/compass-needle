import streamlit as st
import json
import pandas as pd
from langchain_groq import ChatGroq
from modules.persistence import save_draft
from modules.utils import show_download_button, track_action

def render_csr_discovery(username):
    st.header("🔭 CSR Funding Discovery")
    st.caption("Identify companies spending in your district *without* a local office (Remote Spenders).")

    # 1. Load Data
    try:
        with open("csr_discovery.json", "r") as f:
            data = json.load(f)
        df = pd.DataFrame(data)
    except FileNotFoundError:
        st.error("⚠️ Database 'csr_discovery.json' not found. Please upload it.")
        return

    # 2. Filter by District
    all_districts = sorted(df['District'].unique())
    target_dist = st.selectbox("Select Constituency / District", all_districts)
    
    # 3. Split Data
    dist_data = df[df['District'] == target_dist]
    remote_df = dist_data[dist_data['Type'].str.contains("Remote")]
    local_df = dist_data[dist_data['Type'].str.contains("Local")]

    # 4. REMOTE SPENDERS
    st.subheader(f"🌍 Remote Spenders ({len(remote_df)})")
    st.info("💡 **Strategy:** These companies invest here voluntarily. Request an upscale.")
    
    for idx, row in remote_df.iterrows():
        with st.expander(f"💰 {row['Company']} | 3-Year Total: {row['Total_3Y']}"):
            c1, c2 = st.columns([1, 1])
            with c1:
                st.write(f"**Focus Sector:** {row['Sector']}")
                st.write("**Spending History:**")
                st.json(row['History'])
            
            with c2:
                st.caption("Action Plan:")
                if st.button(f"Draft 'Upscale' Request", key=f"rem_{idx}"):
                    api_key = st.session_state.get('groq_api_key')
                    if not api_key:
                        st.error("Enter Groq Key in Sidebar.")
                    else:
                        with st.spinner("Drafting..."):
                            llm = ChatGroq(temperature=0.6, groq_api_key=api_key, model_name="llama-3.1-8b-instant")
                            prompt = f"""
                            Write a warm, strategic letter from an MP to the CSR Head of {row['Company']}.
                            
                            Context:
                            - We acknowledge they spent {row['Total_3Y']} in {row['District']} recently ({row['Sector']}).
                            - Since they have no local office, this voluntary support is highly appreciated.
                            - Request a meeting to discuss doubling this impact.
                            
                            Tone: Gratitude leading to a bigger ask.
                            """
                            draft = llm.invoke(prompt).content
                            
                            st.text_area("Draft Letter", draft, height=250)
                            
                            # --- SAVE & DOWNLOAD ---
                            c_s, c_d = st.columns([1,1])
                            with c_s:
                                if st.button("💾 Save", key=f"save_rem_{idx}"):
                                    save_draft(username, f"CSR Upscale: {row['Company']}", draft, "CSR Letter")
                            with c_d:
                                show_download_button(draft, f"CSR_{row['Company']}")
                            
                            track_action(f"Drafted CSR Proposal for {row['Company']}")

    # 5. LOCAL SPENDERS
    st.divider()
    st.subheader(f"🏭 Local Operations ({len(local_df)})")
    st.caption("Companies with factories/offices here. They are *mandated* to spend.")
    
    with st.expander("View Local Compliance Data"):
        st.dataframe(
            local_df[['Company', 'Sector', 'Total_3Y']], 
            use_container_width=True
        )