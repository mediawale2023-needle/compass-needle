import streamlit as st
import pandas as pd
from langchain_groq import ChatGroq
from modules.persistence import save_draft
from modules.utils import show_download_button, track_action

# --- CACHED DATA LOADER ---
@st.cache_data
def load_csr_csv():
    try:
        # Load the CSV you uploaded
        df = pd.read_csv("CSR_Report_2025-12-06.csv")
        return df
    except FileNotFoundError:
        st.error("CSV File Missing. Please upload 'CSR_Report_2025-12-06.csv' to the root folder.")
        return pd.DataFrame()

def render_state_intel(username):
    st.header("🗺️ State-Level Intelligence")
    st.caption("Deep dive into CSR spending by State. Identify active corporates.")

    # 1. Load Data
    df = load_csr_csv()
    if df.empty: return

    # 2. State Selector
    # Get unique states, sorted alphabetically
    states = sorted(df['CSR State'].dropna().unique())
    
    # Default to Maharashtra if available, else first one
    default_ix = states.index("Maharashtra") if "Maharashtra" in states else 0
    selected_state = st.selectbox("Select State Target", states, index=default_ix)

    # 3. Filter Data for State
    state_df = df[df['CSR State'] == selected_state]
    
    # 4. Aggregate Data (Group by Company & Sector)
    # We sum the spend for each company-sector pair
    summary_df = state_df.groupby(['Company Name', 'CSR Development Sector'])['Project Amount Spent (In INR Cr.)'].sum().reset_index()
    summary_df = summary_df.sort_values(by='Project Amount Spent (In INR Cr.)', ascending=False)
    
    # 5. High-Level Metrics
    total_spend = state_df['Project Amount Spent (In INR Cr.)'].sum()
    total_companies = state_df['Company Name'].nunique()
    top_sector = summary_df.iloc[0]['CSR Development Sector'] if not summary_df.empty else "N/A"

    c1, c2, c3 = st.columns(3)
    c1.metric("Total CSR Spend", f"₹{total_spend:,.2f} Cr")
    c2.metric("Active Companies", total_companies)
    c3.metric("Top Sector", top_sector.split(',')[0]) # Show first part of sector string

    st.divider()

    # 6. Detailed Breakdown (The "Big Board")
    st.subheader(f"🏢 Active Corporates in {selected_state}")
    
    # Search within the state results
    search_term = st.text_input("Search Company in this State", placeholder="e.g. Reliance, Tata")
    if search_term:
        summary_df = summary_df[summary_df['Company Name'].str.contains(search_term, case=False)]

    # Display Cards for Top 50 (to avoid UI lag, add pagination in real app)
    for idx, row in summary_df.head(50).iterrows():
        comp_name = row['Company Name']
        sector = row['CSR Development Sector']
        amount = f"₹{row['Project Amount Spent (In INR Cr.)']:.2f} Cr"
        
        with st.expander(f"💰 {comp_name} - {amount}"):
            c1, c2 = st.columns([3, 1])
            with c1:
                st.write(f"**Focus:** {sector}")
                st.caption(f"This company has actively spent {amount} in {selected_state}.")
            
            with c2:
                if st.button(f"Draft Proposal", key=f"state_{idx}"):
                    api_key = st.session_state.get('groq_api_key')
                    if not api_key:
                        st.error("Enter Groq Key in Sidebar")
                    else:
                        with st.spinner("Drafting..."):
                            llm = ChatGroq(temperature=0.6, groq_api_key=api_key, model_name="llama-3.1-8b-instant")
                            prompt = f"""
                            Write a formal letter from an MP to {comp_name}.
                            Context:
                            - We appreciate their contribution of {amount} to {selected_state} in the {sector} sector.
                            - Request a meeting to discuss expanding this impact to my specific constituency.
                            Tone: Appreciation and Partnership.
                            """
                            draft = llm.invoke(prompt).content
                            st.text_area("Draft", draft, height=200)
                            
                            # Save
                            save_draft(username, f"State Lead: {comp_name}", draft, "CSR Letter")
                            show_download_button(draft, f"Letter_{comp_name}")