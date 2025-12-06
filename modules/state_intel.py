import streamlit as st
import pandas as pd
from langchain_groq import ChatGroq
from modules.persistence import save_draft
from modules.utils import show_download_button, track_action

# --- CACHED DATA LOADER ---
@st.cache_data
def load_csr_csv():
    try:
        files = ["CSR_Report_2025-12-06.csv", "csr_data.csv", "real_csr_data.csv"]
        for f in files:
            try:
                return pd.read_csv(f)
            except: continue
        return pd.DataFrame()
    except: return pd.DataFrame()

def render_state_intel(username):
    st.header("🗺️ State-Level Intelligence")
    st.caption("Analyze CSR spending by specific Company or Development Sector.")

    # 1. Load Data
    df = load_csr_csv()
    if df.empty:
        st.error("⚠️ CSR Data File missing. Please upload 'CSR_Report_2025-12-06.csv' to the root folder.")
        return

    # 2. State Selector
    if 'CSR State' in df.columns:
        states = sorted(df['CSR State'].dropna().unique())
        default_ix = list(states).index("Maharashtra") if "Maharashtra" in states else 0
        selected_state = st.selectbox("Select State Target", states, index=default_ix)

        # 3. Filter Data for State
        state_df = df[df['CSR State'] == selected_state]
        
        # Top Metrics for Context
        total_state_spend = state_df['Project Amount Spent (In INR Cr.)'].sum()
        total_active_comps = state_df['Company Name'].nunique()
        
        c1, c2 = st.columns(2)
        c1.metric(f"Total CSR in {selected_state}", f"₹{total_state_spend:,.2f} Cr")
        c2.metric("Active Corporates", total_active_comps)
        
        st.divider()

        # 4. THE DUAL-MODE SELECTOR
        filter_mode = st.radio("How do you want to search?", ["🏢 By Company", "🏥 By Focus Area (Sector)"], horizontal=True)
        
        # --- MODE A: SEARCH BY COMPANY (Sorted by Spend) ---
        if filter_mode == "🏢 By Company":
            # LOGIC UPDATE: Group by company sum to sort them
            comp_stats = state_df.groupby('Company Name')['Project Amount Spent (In INR Cr.)'].sum().sort_values(ascending=False)
            
            # Create the sorted list
            company_list = comp_stats.index.tolist()
            
            # Show dropdown
            selected_comp = st.selectbox("Select a Company (Sorted by Highest Spend)", company_list)
            
            # Filter for specific company
            comp_data = state_df[state_df['Company Name'] == selected_comp]
            
            # Calculate Stats
            comp_total = comp_data['Project Amount Spent (In INR Cr.)'].sum()
            sectors = comp_data['CSR Development Sector'].unique()
            
            st.subheader(f"📊 {selected_comp} Profile")
            st.info(f"Total Spent in {selected_state}: **₹{comp_total:,.2f} Cr**")
            
            st.write("**Key Focus Areas:**")
            # Show breakdown by sector
            sector_breakdown = comp_data.groupby('CSR Development Sector')['Project Amount Spent (In INR Cr.)'].sum().reset_index()
            # Sort sectors by spend too
            sector_breakdown = sector_breakdown.sort_values(by='Project Amount Spent (In INR Cr.)', ascending=False)
            st.dataframe(sector_breakdown, use_container_width=True)
            
            # Action Button
            if st.button(f"Draft Proposal for {selected_comp}", type="primary"):
                api_key = st.session_state.get('groq_api_key')
                if not api_key:
                    st.error("Enter Groq Key in Sidebar")
                else:
                    with st.spinner("Drafting..."):
                        try:
                            llm = ChatGroq(temperature=0.6, groq_api_key=api_key, model_name="llama-3.1-8b-instant")
                            prompt = f"""
                            Write a formal letter from an MP to the CSR Head of {selected_comp}.
                            Context:
                            - We analyzed your CSR data and see you spent ₹{comp_total:.2f} Cr in {selected_state}.
                            - Your focus on {', '.join(sectors[:3])} aligns with our constituency needs.
                            - Request a meeting to discuss a specific project in my district.
                            Tone: Professional, Data-driven.
                            """
                            draft = llm.invoke(prompt).content
                            st.text_area("Draft", draft, height=250)
                            save_draft(username, f"CSR: {selected_comp}", draft, "Letter")
                            show_download_button(draft, f"Letter_{selected_comp}")
                        except Exception as e:
                            st.error(f"AI Error: {e}")

        # --- MODE B: SEARCH BY SECTOR ---
        else:
            # Get list of sectors active in this state
            sector_list = sorted(state_df['CSR Development Sector'].dropna().unique())
            selected_sector = st.selectbox("Select Development Sector", sector_list)
            
            # Filter for specific sector
            sector_data = state_df[state_df['CSR Development Sector'] == selected_sector]
            
            # Group by company to see who spends most in this sector
            top_spenders = sector_data.groupby('Company Name')['Project Amount Spent (In INR Cr.)'].sum().reset_index()
            top_spenders = top_spenders.sort_values(by='Project Amount Spent (In INR Cr.)', ascending=False)
            
            st.subheader(f"🏆 Top Spenders in '{selected_sector}'")
            st.metric("Total Sector Budget", f"₹{top_spenders['Project Amount Spent (In INR Cr.)'].sum():,.2f} Cr")
            
            # Show list of companies (Top 20 to keep it clean)
            for idx, row in top_spenders.head(20).iterrows():
                comp = row['Company Name']
                amt = row['Project Amount Spent (In INR Cr.)']
                
                with st.expander(f"💰 {comp} - ₹{amt:.2f} Cr"):
                    if st.button(f"Pitch to {comp}", key=f"sec_btn_{idx}"):
                        api_key = st.session_state.get('groq_api_key')
                        if not api_key:
                            st.error("Enter Key")
                        else:
                            with st.spinner("Drafting..."):
                                llm = ChatGroq(temperature=0.6, groq_api_key=api_key, model_name="llama-3.1-8b-instant")
                                prompt = f"""
                                Write a funding proposal to {comp}.
                                Subject: CSR Partnership for {selected_sector} project in my district.
                                Context:
                                - We know you are a top spender in {selected_sector} in {selected_state} (₹{amt:.2f} Cr).
                                - We have a ready-to-deploy project in this same sector.
                                Tone: Persuasive.
                                """
                                draft = llm.invoke(prompt).content
                                st.text_area("Draft", draft, height=200)
                                save_draft(username, f"Pitch: {comp} ({selected_sector})", draft, "Proposal")
                                show_download_button(draft, f"Pitch_{comp}")

    else:
        st.error("Invalid CSV format: 'CSR State' column missing.")