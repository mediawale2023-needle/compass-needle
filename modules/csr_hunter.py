import streamlit as st
import json
import pandas as pd
from openai import OpenAI
import os
from modules.persistence import save_draft
from modules.utils import show_download_button, track_action

# --- TAD NECESSARY: Removed global client initialization to prevent Railway boot crash ---

def get_openai_client():
    """Helper to safely initialize OpenAI client after environment variables load."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)

def ask_openai(prompt):
    """Helper to maintain consistency with OpenAI across the project."""
    client = get_openai_client()
    if not client:
        return "⚠️ OpenAI API Key not configured. Please check Railway Variables."
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI Error: {e}"

def render_csr_hunter(username):
    st.header("💰 CSR Hunter (Maharashtra Edition)")
    st.caption("Track 3-year spending history & Identify 'Remote' vs 'Local' opportunities.")

    # 1. Load Data
    try:
        with open("csr_db.json", "r") as f:
            data = json.load(f)
        df = pd.DataFrame(data)
    except FileNotFoundError:
        st.error("⚠️ Database 'csr_db.json' not found. Please upload it.")
        return

    # 2. Filter by District
    if 'District' not in df.columns:
        st.error("⚠️ 'District' column not found in csr_db.json.")
        return

    all_districts = sorted(df['District'].unique())
    target_dist = st.selectbox("Select District", all_districts, index=all_districts.index("Mumbai South") if "Mumbai South" in all_districts else 0)
    
    # 3. Split Data
    dist_data = df[df['District'] == target_dist]

    if 'Type' in dist_data.columns:
        remote_df = dist_data[dist_data['Type'].str.contains("Remote", na=False)]
    else:
        remote_df = dist_data

    # Identify Violators (Local + Zero Spend)
    if 'Type' in dist_data.columns and 'Status' in dist_data.columns:
        violators_df = dist_data[
            (dist_data['Type'].str.contains("Local", na=False)) & 
            (dist_data['Status'].str.contains("ZERO SPEND", na=False))
        ]
        # Identify Compliant Locals
        compliant_local_df = dist_data[
            (dist_data['Type'].str.contains("Local", na=False)) & 
            (~dist_data['Status'].str.contains("ZERO SPEND", na=False))
        ]
    else:
        violators_df = pd.DataFrame()
        compliant_local_df = pd.DataFrame()

    # --- TABBED VIEW ---
    tab_remote, tab_watchdog, tab_local = st.tabs(["🌍 Remote Opportunities", "🚨 Compliance Watchdog", "🏭 Local Data"])

    # --- TAB A: REMOTE SPENDERS (The Upscale Opportunity) ---
    with tab_remote:
        st.info(f"**Strategy:** {len(remote_df)} companies spent here voluntarily (No local office). Request an upscale.")
        
        if remote_df.empty:
            st.warning("No remote spenders found in this district.")
        else:
            for idx, row in remote_df.iterrows():
                with st.expander(f"💰 {row['Company']} | 3-Year: {row['Total_3Y']}"):
                    c1, c2 = st.columns([1, 1])
                    with c1:
                        st.write(f"**Focus:** {row['Sector']}")
                        st.write("**Spending History:**")
                        st.json(row.get('Spend_History', row.get('History', {})))
                    
                    with c2:
                        st.write("#### ⚡ Action")
                        if st.button(f"Draft 'Upscale' Letter", key=f"rem_{idx}"):
                            with st.spinner("Drafting with OpenAI..."):
                                prompt = f"""
                                Write a strategic letter from an MP to the CSR Head of {row['Company']}.
                                Context:
                                - Acknowledge {row['Total_3Y']} spent in {row['District']} over 3 years.
                                - Since they have no office here, this support is valued.
                                - Propose a meeting to double this impact for the next FY.
                                Tone: Gratitude leading to a bigger ask.
                                """
                                draft = ask_openai(prompt)
                                
                                st.text_area("Draft Letter", draft, height=250)
                                save_draft(username, f"Upscale: {row['Company']}", draft, "CSR Letter")
                                show_download_button(draft, f"CSR_{row['Company']}")
                                track_action(f"Drafted CSR Proposal for {row['Company']}")

    # --- TAB B: COMPLIANCE WATCHDOG (The Enforcer) ---
    with tab_watchdog:
        if violators_df.empty:
            st.success(f"No CSR violations found in {target_dist}!")
        else:
            st.error(f"🚨 ALERT: {len(violators_df)} Local Companies with ZERO CSR Spend!")
            for idx, row in violators_df.iterrows():
                with st.expander(f"❌ {row['Company']} (Factory Present)"):
                    st.write("**3-Year History:**")
                    st.json(row.get('Spend_History', row.get('History', {})))
                    st.caption("Violation: Section 135 (Local Area Preference)")
                    
                    if st.button(f"Draft 'Show Cause' Notice", key=f"vio_{idx}"):
                        with st.spinner("Drafting Notice..."):
                            prompt = f"""
                            Write a stern D.O. Letter from MP to CEO of {row['Company']}.
                            Subject: Zero CSR Spend in {row['District']} despite local operations.
                            Context: MCA data shows ₹0 spend for 3 years. Demand immediate explanation and allocation.
                            Tone: Formal, Authoritative.
                            """
                            draft = ask_openai(prompt)
                            st.text_area("Notice Draft", draft, height=300)
                            save_draft(username, f"Notice: {row['Company']}", draft, "Legal Notice")
                            show_download_button(draft, f"Notice_{row['Company']}")

    # --- TAB C: LOCAL DATA (Reference) ---
    with tab_local:
        st.subheader(f"✅ Compliant Locals ({len(compliant_local_df)})")
        display_cols = [c for c in ['Company', 'Sector', 'Total_3Y'] if c in compliant_local_df.columns]
        if display_cols:
            st.dataframe(compliant_local_df[display_cols])
        else:
            st.dataframe(compliant_local_df)