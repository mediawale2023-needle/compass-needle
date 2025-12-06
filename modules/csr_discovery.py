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
    # Default to a district if available, else first one
    default_ix = all_districts.index("Mumbai South") if "Mumbai South" in all_districts else 0
    target_dist = st.selectbox("Select Constituency / District", all_districts, index=default_ix)
    
    # 3. Split Data
    dist_data = df[df['District'] == target_dist]
    remote_df = dist_data[dist_data['Type'].str.contains("Remote")]
    local_df = dist_data[dist_data['Type'].str.contains("Local")]

    # --- SECTION A: REMOTE SPENDERS ---
    st.subheader(f"🌍 Remote Spenders ({len(remote_df)})")
    st.info("💡 **Strategy:** These companies invest here voluntarily. Request an upscale.")
    
    if remote_df.empty:
        st.warning("No remote spenders found.")
    else:
        for idx, row in remote_df.iterrows():
            with st.expander(f"💰 {row['Company']} | 3-Year Total: {row['Total_3Y']}"):
                c1, c2 = st.columns([1, 1])
                with c1:
                    st.write(f"**Focus Sector:** {row['Sector']}")
                    st.write("**Spending History:**")
                    # FIX: Use .get() to handle either key name safely
                    history_data = row.get('Spend_History', row.get('History', {}))
                    st.json(history_data)
                
                with c2:
                    st.caption("Action Plan:")
                    if st.button(f"Draft 'Upscale' Request", key=f"rem_{idx}"):
                        api_key = st.session_state.get('groq_api_key')
                        if not api_key:
                            st.error("Enter Groq Key in Sidebar.")
                        else:
                            with st.spinner("Drafting..."):
                                try:
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
                                    
                                    # Save & Download
                                    col1, col2 = st.columns([1,1])
                                    with col1:
                                        if st.button("💾 Save", key=f"sv_rem_{idx}"):
                                            save_draft(username, f"CSR Upscale: {row['Company']}", draft, "CSR Letter")
                                    with c2:
                                        show_download_button(draft, f"CSR_{row['Company']}")
                                    
                                    track_action(f"Drafted CSR Proposal for {row['Company']}")
                                except Exception as e:
                                    st.error(f"AI Error: {e}")

    # --- SECTION B: LOCAL SPENDERS ---
    st.divider()
    st.subheader(f"🏭 Local Operations ({len(local_df)})")
    
    # Check for Violators (Zero Spend)
    violators = local_df[local_df['Status'].str.contains("ZERO SPEND")]
    
    if not violators.empty:
        st.error(f"🚨 ALERT: {len(violators)} Companies with Local Operations have ZERO CSR Spend!")
        for idx, row in violators.iterrows():
            with st.expander(f"❌ {row['Company']} (Violation)"):
                st.write(f"**Issue:** {row.get('Gap_Analysis', 'Zero Spend detected')}")
                history_data = row.get('Spend_History', row.get('History', {}))
                st.json(history_data)
                
                if st.button(f"Draft Notice", key=f"vio_{idx}"):
                    api_key = st.session_state.get('groq_api_key')
                    if api_key:
                        llm = ChatGroq(temperature=0.6, groq_api_key=api_key, model_name="llama-3.1-8b-instant")
                        draft = llm.invoke(f"Write a stern D.O. letter to {row['Company']} about Zero CSR spend in {row['District']}.").content
                        st.text_area("Draft", draft)
                        show_download_button(draft, f"Notice_{row['Company']}")

    # Show Table of Compliant Locals
    compliant = local_df[~local_df['Status'].str.contains("ZERO SPEND")]
    if not compliant.empty:
        with st.expander("View Compliant Local Companies"):
            st.dataframe(compliant[['Company', 'Sector', 'Total_3Y']], use_container_width=True)