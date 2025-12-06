import streamlit as st
import pandas as pd
import os
from modules.persistence import save_draft
from modules.utils import show_download_button, track_action

# --- CACHED DATA LOADER (DEBUG MODE) ---
@st.cache_data
def load_csr_csv():
    # 1. Define the filename we want
    target_file = "CSR_Report_2025-12-06.csv"
    
    # 2. Check if it exists
    if os.path.exists(target_file):
        try:
            return pd.read_csv(target_file)
        except Exception as e:
            st.error(f"File found but unreadable: {e}")
            return pd.DataFrame()
            
    # 3. IF NOT FOUND: Run Diagnostics
    else:
        st.error(f"❌ CRITICAL ERROR: '{target_file}' not found.")
        
        # Show what IS there so you can fix the name
        current_files = os.listdir('.')
        st.warning(f"📂 Files actually available in Root Folder:")
        st.write(current_files)
        
        # Check if it's there but named differently (case sensitivity)
        for f in current_files:
            if f.lower() == target_file.lower():
                st.info(f"💡 Found similar file: '{f}'. Please rename it to '{target_file}' exactly.")
                
        return pd.DataFrame()

def render_state_intel(username):
    st.header("🗺️ State-Level Intelligence")
    
    # Load Data using the new Debug function
    df = load_csr_csv()
    
    if df.empty:
        st.stop() # Stop rendering if data is missing

    # ... (Rest of your original code below remains unchanged) ...
    # 2. State Selector
    states = sorted(df['CSR State'].dropna().unique())
    default_ix = list(states).index("Maharashtra") if "Maharashtra" in states else 0
    selected_state = st.selectbox("Select State Target", states, index=default_ix)

    # 3. Filter Data
    state_df = df[df['CSR State'] == selected_state]
    
    # 4. Aggregate
    summary_df = state_df.groupby(['Company Name', 'CSR Development Sector'])['Project Amount Spent (In INR Cr.)'].sum().reset_index()
    summary_df = summary_df.sort_values(by='Project Amount Spent (In INR Cr.)', ascending=False)
    
    # 5. Metrics
    total_spend = state_df['Project Amount Spent (In INR Cr.)'].sum()
    active_companies = state_df['Company Name'].nunique()
    
    c1, c2 = st.columns(2)
    c1.metric("Total CSR Spend", f"₹{total_spend:,.2f} Cr")
    c2.metric("Active Companies", active_companies)
    
    st.divider()
    
    # 6. Detailed List
    st.subheader(f"🏢 Top Spenders in {selected_state}")
    
    search = st.text_input("Search Company", placeholder="Reliance, Tata, HDFC...")
    if search:
        summary_df = summary_df[summary_df['Company Name'].str.contains(search, case=False)]
        
    for idx, row in summary_df.head(20).iterrows():
        comp = row['Company Name']
        sector = row['CSR Development Sector']
        amount = f"₹{row['Project Amount Spent (In INR Cr.)']:.2f} Cr"
        
        with st.expander(f"💰 {comp} - {amount}"):
            st.write(f"**Focus:** {sector}")
            if st.button(f"Draft Proposal", key=f"state_btn_{idx}"):
                # ... (Drafting logic) ...
                st.info("Drafting...")