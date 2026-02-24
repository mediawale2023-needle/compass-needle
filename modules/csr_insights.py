"""
CSR Insights Tab — Merged view of Discovery + Hunter + State Intel.
Answers: "Who has money and where is it going?"

Sub-tabs:
- Company Database: Browse CSR companies by district (from Discovery + Hunter)
- Compliance Watchdog: Track zero-spend violators (from Hunter)
- State Analytics: CSV-based spending analytics (from State Intel)
"""
import streamlit as st
import json
import pandas as pd
from modules.ai_helpers import ask_openai
from modules.persistence import save_draft
from modules.utils import show_download_button, track_action
from modules.state_intel import render_state_intel


def render_csr_insights(username):
    """Render the unified CSR Insights tab."""
    st.header("📊 CSR Insights")
    st.caption("Research CSR companies, track spending, and identify funding opportunities.")

    tab_companies, tab_watchdog, tab_analytics = st.tabs([
        "🏢 Company Database",
        "🚨 Compliance Watchdog",
        "🗺️ State Analytics",
    ])

    with tab_companies:
        _render_company_database(username)

    with tab_watchdog:
        _render_compliance_watchdog(username)

    with tab_analytics:
        render_state_intel(username)


def _load_csr_data():
    """Load CSR company data from all available sources."""
    all_data = []

    # Discovery database
    try:
        with open("csr_discovery.json", "r") as f:
            all_data += json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    # Hunter database
    try:
        with open("csr_db.json", "r") as f:
            all_data += json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    if not all_data:
        return pd.DataFrame()

    df = pd.DataFrame(all_data)
    # Deduplicate by company name
    if "Company" in df.columns:
        df = df.drop_duplicates(subset=["Company"], keep="first")
    return df


def _render_company_database(username):
    """Browse and filter CSR companies by district, sector, and type."""
    st.subheader("🏢 CSR Company Database")
    st.info("Browse companies spending in your district. Identify remote spenders for upscale requests.")

    df = _load_csr_data()
    if df.empty:
        st.error("⚠️ No CSR data found. Upload 'csr_db.json' or 'csr_discovery.json'.")
        return

    # Filters
    c1, c2 = st.columns(2)
    with c1:
        if "District" in df.columns:
            all_districts = sorted(df["District"].unique())
            default_ix = all_districts.index("Belgaum") if "Belgaum" in all_districts else 0
            target_dist = st.selectbox("📍 Select District", all_districts, index=default_ix, key="insights_dist")
            df = df[df["District"] == target_dist]
        else:
            target_dist = "Unknown"

    with c2:
        if "Sector" in df.columns:
            sectors = ["All"] + sorted(df["Sector"].dropna().unique().tolist())
            sel_sector = st.selectbox("🏥 Filter by Sector", sectors, key="insights_sector")
            if sel_sector != "All":
                df = df[df["Sector"] == sel_sector]

    # Split by type
    remote_df = df[df["Type"].str.contains("Remote", na=False)] if "Type" in df.columns else df
    local_df = df[df["Type"].str.contains("Local", na=False)] if "Type" in df.columns else pd.DataFrame()

    # Metrics
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Companies", len(df))
    m2.metric("Remote Spenders", len(remote_df))
    m3.metric("Local Operations", len(local_df))

    st.divider()

    # Remote Spenders — The upscale opportunity
    st.write(f"**🌍 Remote Spenders ({len(remote_df)})** — Companies spending here without a local office")

    if not remote_df.empty:
        for idx, row in remote_df.iterrows():
            company = row.get("Company", "Unknown")
            total = row.get("Total_3Y", "N/A")
            with st.expander(f"💰 {company} | 3-Year: {total}"):
                c1, c2 = st.columns([2, 1])
                with c1:
                    st.write(f"**Sector:** {row.get('Sector', 'General')}")
                    history = row.get("Spend_History", row.get("History", {}))
                    if isinstance(history, dict):
                        st.json(history)
                with c2:
                    if st.button("Draft Upscale Letter", key=f"ins_rem_{idx}_{company}"):
                        with st.spinner("Drafting..."):
                            prompt = f"""Write a strategic letter from an MP to the CSR Head of {company}.
                            Acknowledge their {total} spent in {target_dist} over 3 years.
                            Since they have no local office, this support is highly valued.
                            Propose a meeting to double this impact for the next FY.
                            Tone: Gratitude leading to a bigger ask. Professional."""
                            draft = ask_openai(prompt)
                            st.text_area("Draft Letter", draft, height=200, key=f"ins_draft_{idx}")
                            save_draft(username, f"Upscale: {company}", draft, "CSR Letter")
                            show_download_button(draft, f"CSR_{company}")
    else:
        st.caption("No remote spenders found in this district.")

    # Local Operations
    st.divider()
    if not local_df.empty:
        st.write(f"**🏭 Local Operations ({len(local_df)})**")
        display_cols = [c for c in ["Company", "Sector", "Total_3Y", "Status"] if c in local_df.columns]
        if display_cols:
            st.dataframe(local_df[display_cols], use_container_width=True)
        else:
            st.dataframe(local_df, use_container_width=True)


def _render_compliance_watchdog(username):
    """Track companies with zero CSR spend despite local operations."""
    st.subheader("🚨 Compliance Watchdog")
    st.info("Companies with local operations but ZERO CSR spend (Section 135 violation).")

    df = _load_csr_data()
    if df.empty:
        st.warning("No CSR data loaded.")
        return

    # Filter: Local companies with zero spend
    if "Type" not in df.columns or "Status" not in df.columns:
        st.info("Compliance data requires 'Type' and 'Status' columns in your CSR database.")
        return

    # District filter
    if "District" in df.columns:
        all_districts = sorted(df["District"].unique())
        default_ix = all_districts.index("Belgaum") if "Belgaum" in all_districts else 0
        target_dist = st.selectbox("📍 Select District", all_districts, index=default_ix, key="watchdog_dist")
        df = df[df["District"] == target_dist]
    else:
        target_dist = "Unknown"

    violators = df[
        (df["Type"].str.contains("Local", na=False))
        & (df["Status"].str.contains("ZERO SPEND", na=False))
    ]

    if violators.empty:
        st.success(f"✅ No CSR violations found in {target_dist}!")
        return

    st.error(f"🚨 ALERT: {len(violators)} companies with ZERO CSR spend in {target_dist}!")

    for idx, row in violators.iterrows():
        company = row.get("Company", "Unknown")
        with st.expander(f"❌ {company} (Factory Present)"):
            st.write("**3-Year History:**")
            history = row.get("Spend_History", row.get("History", {}))
            if isinstance(history, dict):
                st.json(history)
            st.caption("Violation: Section 135 (Local Area Preference)")

            if st.button("Draft Show Cause Notice", key=f"wdog_vio_{idx}_{company}"):
                with st.spinner("Drafting Notice..."):
                    prompt = f"""Write a stern D.O. Letter from an MP to the CEO of {company}.
                    Subject: Zero CSR Spend in {target_dist} despite local operations.
                    Context: MCA data shows ₹0 spend for 3 years. Demand immediate explanation.
                    Tone: Formal, Authoritative."""
                    draft = ask_openai(prompt)
                    st.text_area("Notice Draft", draft, height=300, key=f"wdog_draft_{idx}")
                    save_draft(username, f"Notice: {company}", draft, "Legal Notice")
                    show_download_button(draft, f"Notice_{company}")
