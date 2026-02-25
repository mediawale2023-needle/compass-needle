import streamlit as st
import json
import pandas as pd
from sqlalchemy import text
from openai import OpenAI
import os
from modules.persistence import save_draft
from modules.utils import show_download_button, track_action
from modules.ai_helpers import get_openai_client, ask_openai

# --- TAD NECESSARY: Database Engine Import ---
try:
    from main import engine
except ImportError:
    engine = None

# --- TAD NECESSARY: Removed global client initialization to prevent Railway boot crash ---

def render_csr_discovery(username):
    from modules.ui_theme import inject_theme
    inject_theme()
    st.header("CSR Funding Discovery")
    st.caption("Identify companies spending in your district *without* a local office (Remote Spenders).")

    tenant_id = st.session_state.get('tenant_id', 1)

    # 1. Load Data
    try:
        with open("csr_discovery.json", "r") as f:
            data = json.load(f)
        df = pd.DataFrame(data)
    except FileNotFoundError:
        st.error(" Database 'csr_discovery.json' not found.")
        return

    # 2. Strategic Matching Section (THE SIGNATURE FEATURE)
    st.divider()
    st.subheader("Live Strategic Matches")
    st.info("Matching high-volume grievances with CSR-eligible companies.")
    
    gaps = get_live_gaps(tenant_id)
    if gaps:
        for gap in gaps:
            gap_category = gap[0]
            gap_volume = gap[1]
            gap_area = gap[2]
            # --- TAD NECESSARY: Crisis Alert Badge Logic ---
            if gap_volume >= 500:
                badge = " **CRITICAL CRISIS (500+)**"
            elif gap_volume >= 200:
                badge = " **MAJOR ISSUE (200+)**"
            else:
                badge = " **HIGH DEMAND (100+)**"

            # Match company sector with grievance category
            matches = df[df['Sector'].str.contains(gap_category, case=False, na=False)]
            if not matches.empty:
                with st.expander(f"{badge} | {gap_category} in {gap_area}"):
                    st.write(f" **Data Source:** {gap_volume} unique citizen reports verified.")
                    for _, corp in matches.head(3).iterrows():
                        col_a, col_b = st.columns([3, 1])
                        col_a.write(f" **{corp['Company']}** (Sector: {corp['Sector']})")
                        if col_b.button("Pitch Generator", key=f"gen_{corp['Company']}_{gap_area}"):
                            with st.spinner("Generating One-Click Pitch via OpenAI..."):
                                prompt = f"""
                                Act as a Senior Advisor to an Indian Member of Parliament. 
                                Write a formal CSR Partnership Proposal for {corp['Company']} for a project in {gap_area}.
                                
                                Context:
                                - Issue: {gap_category} (CRITICAL: Verified by {gap_volume} unique citizen reports).
                                - Urgency: This is a high-volume community gap requiring immediate CSR intervention.
                                
                                Include: Concept Note, Impact KPIs (highlighting the 100+ verified complainants), SDG Mapping, and an MP Signature line.
                                Tone: Professional, authoritative, and data-driven.
                                """
                                pitch = ask_openai(prompt)
                                st.markdown("### Generated Proposal")
                                st.container(border=True).markdown(pitch)
                                show_download_button(pitch, f"Pitch_{corp['Company']}")
            
    st.divider()

    # 3. Original District Filter Logic
    remote_df = pd.DataFrame()
    local_df = pd.DataFrame()
    target_dist = "Unknown"

    if 'District' in df.columns:
        all_districts = sorted(df['District'].unique())
        default_ix = all_districts.index("Mumbai South") if "Mumbai South" in all_districts else 0
        target_dist = st.selectbox("Select Constituency / District", all_districts, index=default_ix)
        
        dist_data = df[df['District'] == target_dist]
        if 'Type' in df.columns:
            remote_df = dist_data[dist_data['Type'].str.contains("Remote", na=False)]
            local_df = dist_data[dist_data['Type'].str.contains("Local", na=False)]
        else:
            remote_df = dist_data
            local_df = pd.DataFrame()

    # --- SECTION A: REMOTE SPENDERS ---
    st.subheader(f"Remote Spenders ({len(remote_df)})")
    if not remote_df.empty:
        for idx, row in remote_df.iterrows():
            company = row.get('Company', 'Unknown Company')
            total = row.get('Total_3Y', 'N/A')
            with st.expander(f" {company} | 3-Year Total: {total}"):
                c1, c2 = st.columns([1, 1])
                with c1:
                    st.write(f"**Focus Sector:** {row.get('Sector', 'General')}")
                    st.json(row.get('Spend_History', row.get('History', {})))
                with c2:
                    if st.button(f"Draft 'Upscale' Request", key=f"rem_{idx}"):
                        with st.spinner("Drafting..."):
                            prompt = f"Write an MP letter to {company} requesting CSR upscale for {target_dist} based on their focus on {row.get('Sector')}."
                            draft = ask_openai(prompt)
                            st.text_area("Draft Letter", draft, height=200)
                            show_download_button(draft, f"CSR_{company}")

    # --- SECTION B: LOCAL SPENDERS ---
    st.divider()
    st.subheader(f"Local Operations ({len(local_df)})")
    if not local_df.empty and 'Status' in local_df.columns:
        violators = local_df[local_df['Status'].str.contains("ZERO SPEND", na=False)]
        if not violators.empty:
            st.error(f" ALERT: {len(violators)} Companies with ZERO CSR Spend!")
            for idx, row in violators.iterrows():
                with st.expander(f" {row.get('Company', 'Unknown')}"):
                    if st.button(f"Draft Notice", key=f"vio_{idx}"):
                        with st.spinner("Drafting Notice..."):
                            draft = ask_openai(f"Draft a stern MP notice to {row['Company']} for zero CSR spend in their local area of operation.")
                            st.text_area("Notice Draft", draft)
                            show_download_button(draft, f"Notice_{row['Company']}")