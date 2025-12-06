import streamlit as st
import pandas as pd
from langchain_groq import ChatGroq
from modules.persistence import save_draft
from modules.utils import show_download_button

# --- CACHED DATA LOADER ---
@st.cache_data
def load_csr_csv():
    try:
        # Look for the uploaded CSV
        files = ["CSR_Report_2025-12-06.csv", "csr_data.csv", "real_csr_data.csv"]
        for f in files:
            try:
                return pd.read_csv(f)
            except: continue
        return pd.DataFrame()
    except: return pd.DataFrame()

def render_state_intel(username):
    st.header("🗺️ State-Level Intelligence")
    st.caption("Full list of EVERY company spending CSR funds in this State.")

    # 1. Load Data
    df = load_csr_csv()
    if df.empty:
        st.error("⚠️ CSR Data File missing. Please upload 'CSR_Report_2025-12-06.csv'.")
        return

    # 2. State Selector
    if 'CSR State' in df.columns:
        states = sorted(df['CSR State'].dropna().unique())
        default_ix = list(states).index("Maharashtra") if "Maharashtra" in states else 0
        selected_state = st.selectbox("Select State Target", states, index=default_ix)

        # 3. Filter & Group
        state_df = df[df['CSR State'] == selected_state]
        
        # Group by Company to get total spend
        # We aggregate sectors into a list string
        summary_df = state_df.groupby('Company Name').agg({
            'Project Amount Spent (In INR Cr.)': 'sum',
            'CSR Development Sector': lambda x: ', '.join(list(set(x))[:3]) # Keep top 3 sectors for display
        }).reset_index()
        
        summary_df = summary_df.sort_values(by='Project Amount Spent (In INR Cr.)', ascending=False)

        # 4. Metrics
        total_spend = state_df['Project Amount Spent (In INR Cr.)'].sum()
        active_companies = len(summary_df)
        
        c1, c2 = st.columns(2)
        c1.metric("Total Available Funds", f"₹{total_spend:,.2f} Cr")
        c2.metric("Companies Active", active_companies)
        
        st.divider()

        # 5. THE FULL LIST (ALL COMPANIES)
        st.subheader(f"🏢 All Companies in {selected_state} ({active_companies})")
        
        # Search is crucial when showing ALL data
        search = st.text_input("🔍 Search Company Name", placeholder="Type to find specific company...")
        if search:
            summary_df = summary_df[summary_df['Company Name'].str.contains(search, case=False)]
        
        # Pagination logic to prevent browser crash if >1000 companies
        # We show them in batches of 50, but allow paging through ALL.
        page_size = 50
        total_pages = (len(summary_df) // page_size) + 1
        page = st.number_input("Page", min_value=1, max_value=total_pages, value=1)
        
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        
        batch_df = summary_df.iloc[start_idx:end_idx]

        for idx, row in batch_df.iterrows():
            comp = row['Company Name']
            amount = f"₹{row['Project Amount Spent (In INR Cr.)']:.2f} Cr"
            sectors = row['CSR Development Sector']
            
            with st.expander(f"💰 {comp} - {amount}"):
                st.write(f"**Sectors:** {sectors}...")
                
                if st.button(f"Draft Proposal", key=f"all_btn_{idx}"):
                    api_key = st.session_state.get('groq_api_key')
                    if not api_key:
                        st.error("Enter Groq Key in Sidebar")
                    else:
                        with st.spinner("Drafting..."):
                            llm = ChatGroq(temperature=0.6, groq_api_key=api_key, model_name="llama-3.1-8b-instant")
                            prompt = f"""
                            Write a formal letter from an MP to {comp}.
                            Context:
                            - We see they spent {amount} in {selected_state}.
                            - Request them to allocate a portion of this to my constituency.
                            Tone: Professional and Appreciative.
                            """
                            draft = llm.invoke(prompt).content
                            st.text_area("Draft", draft, height=200)
                            save_draft(username, f"State Lead: {comp}", draft, "CSR Letter")
                            show_download_button(draft, f"Letter_{comp}")
    else:
        st.error("Invalid CSV format: 'CSR State' column missing.")