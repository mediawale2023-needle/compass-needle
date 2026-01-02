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
    except Exception as e:
        st.error(f"⚠️ Error reading database: {e}")
        return

    # 2. Filter by District
    if 'District' in df.columns:
        all_districts = sorted(df['District'].unique())
        default_ix = all_districts.index("Mumbai South") if "Mumbai South" in all_districts else 0
        target_dist = st.selectbox("Select Constituency / District", all_districts, index=default_ix)
        
        # 3. Split Data
        dist_data = df[df['District'] == target_dist]
        # Use safe string access for 'Type' column
        if 'Type' in df.columns:
            remote_df = dist_data[dist_data['Type'].str.contains("Remote", na=False)]
            local_df = dist_data[dist_data['Type'].str.contains("Local", na=False)]
        else:
            st.warning("Data missing 'Type' column. Showing all as potential targets.")
            remote_df = dist_data
            local_df = pd.DataFrame()
    else:
        st.error("Database format incorrect (Missing 'District' column). Regenerate data.")
        return

    # --- SECTION A: REMOTE SPENDERS ---
    st.subheader(f"🌍 Remote Spenders ({len(remote_df)})")
    st.info("💡 **Strategy:** These companies invest here voluntarily. Request an upscale.")
    
    if remote_df.empty:
        st.warning("No remote spenders found.")
    else:
        for idx, row in remote_df.iterrows():
            # SAFE ACCESS: Use .get() for everything to prevent KeyErrors
            company = row.get('Company', 'Unknown Company')
            total = row.get('Total_3Y', 'N/A')
            sector = row.get('Sector', 'General')
            
            with st.expander(f"💰 {company} | 3-Year Total: {total}"):
                c1, c2 = st.columns([1, 1])
                with c1:
                    st.write(f"**Focus Sector:** {sector}")
                    st.write("**Spending History:**")
                    # Handle History/Spend_History mismatch
                    history = row.get('Spend_History', row.get('History', {}))
                    st.json(history)
                
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
                                    Write a warm, strategic letter from an MP to the CSR Head of {company}.
                                    Context:
                                    - We acknowledge they spent {total} in {target_dist} recently ({sector}).
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
                                            save_draft(username, f"CSR Upscale: {company}", draft, "CSR Letter")
                                    with c2:
                                        show_download_button(draft, f"CSR_{company}")
                                    
                                    track_action(f"Drafted CSR Proposal for {company}")
                                except Exception as e:
                                    st.error(f"AI Error: {e}")

    # --- SECTION B: LOCAL SPENDERS ---
    st.divider()
    st.subheader(f"🏭 Local Operations ({len(local_df)})")
    
    # Check for Violators (Zero Spend) - Safe check
    if not local_df.empty and 'Status' in local_df.columns:
        violators = local_df[local_df['Status'].str.contains("ZERO SPEND", na=False)]
        
        if not violators.empty:
            st.error(f"🚨 ALERT: {len(violators)} Companies with Local Operations have ZERO CSR Spend!")
            for idx, row in violators.iterrows():
                company = row.get('Company', 'Unknown')
                with st.expander(f"❌ {company} (Violation)"):
                    st.write(f"**Issue:** {row.get('Gap_Analysis', 'Zero Spend detected')}")
                    history = row.get('Spend_History', row.get('History', {}))
                    st.json(history)
                    
                    if st.button(f"Draft Notice", key=f"vio_{idx}"):
                        api_key = st.session_state.get('groq_api_key')
                        if api_key:
                            llm = ChatGroq(temperature=0.6, groq_api_key=api_key, model_name="llama-3.1-8b-instant")
                            draft = llm.invoke(f"Write a stern D.O. letter to {company} about Zero CSR spend in {target_dist}.").content
                            st.text_area("Draft", draft)
                            show_download_button(draft, f"Notice_{company}")

        # Show Table of Compliant Locals
        compliant = local_df[~local_df['Status'].str.contains("ZERO SPEND", na=False)]
        if not compliant.empty:
            with st.expander("View Compliant Local Companies"):
                # Select only columns that exist
                cols_to_show = [c for c in ['Company', 'Sector', 'Total_3Y'] if c in compliant.columns]
                st.dataframe(compliant[cols_to_show], use_container_width=True)