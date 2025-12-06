import streamlit as st
import pandas as pd
from langchain_groq import ChatGroq
from modules.persistence import save_draft
from modules.utils import show_download_button

# --- CACHED DATA LOADER ---
@st.cache_data
def load_csr_csv():
    try:
        # We look for the exact file you uploaded
        # You can rename your file to 'csr_data.csv' to make it easier, 
        # but this code checks for your specific filename too.
        files = ["CSR_Report_2025-12-06.csv", "csr_data.csv", "real_csr_data.csv"]
        
        selected_file = None
        for f in files:
            try:
                pd.read_csv(f)
                selected_file = f
                break
            except:
                continue
                
        if selected_file:
            df = pd.read_csv(selected_file)
            return df
        else:
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"Error loading CSV: {e}")
        return pd.DataFrame()

def render_state_intel(username):
    st.header("🗺️ State-Level Intelligence")
    st.caption("Analyze official MCA data to find top spenders in your State.")

    # 1. Load Data
    df = load_csr_csv()
    if df.empty:
        st.warning("⚠️ CSR Data File missing. Please upload 'CSR_Report_2025-12-06.csv' to the root folder.")
        return

    # 2. State Selector
    # Clean up state names and get unique list
    if 'CSR State' in df.columns:
        states = sorted(df['CSR State'].dropna().unique())
        # Default to Maharashtra
        default_ix = list(states).index("Maharashtra") if "Maharashtra" in states else 0
        selected_state = st.selectbox("Select State Target", states, index=default_ix)

        # 3. Filter Data
        state_df = df[df['CSR State'] == selected_state]
        
        # 4. Aggregation (The "Big Board")
        # Group by Company and Sector to see who spent what
        summary_df = state_df.groupby(['Company Name', 'CSR Development Sector'])['Project Amount Spent (In INR Cr.)'].sum().reset_index()
        summary_df = summary_df.sort_values(by='Project Amount Spent (In INR Cr.)', ascending=False)
        
        # 5. Top Level Metrics
        total_spend = state_df['Project Amount Spent (In INR Cr.)'].sum()
        active_companies = state_df['Company Name'].nunique()
        
        c1, c2 = st.columns(2)
        c1.metric("Total CSR Spend", f"₹{total_spend:,.2f} Cr")
        c2.metric("Active Companies", active_companies)
        
        st.divider()
        
        # 6. Detailed Company List
        st.subheader(f"🏢 Top Spenders in {selected_state}")
        
        # Search Filter
        search = st.text_input("Search Company", placeholder="Reliance, Tata, HDFC...")
        if search:
            summary_df = summary_df[summary_df['Company Name'].str.contains(search, case=False)]
            
        # Display Results
        for idx, row in summary_df.head(20).iterrows(): # Show top 20 to keep it fast
            comp = row['Company Name']
            sector = row['CSR Development Sector']
            amount = f"₹{row['Project Amount Spent (In INR Cr.)']:.2f} Cr"
            
            with st.expander(f"💰 {comp} - {amount}"):
                st.write(f"**Focus:** {sector}")
                
                if st.button(f"Draft Proposal", key=f"state_btn_{idx}"):
                    api_key = st.session_state.get('groq_api_key')
                    if not api_key:
                        st.error("Enter Groq Key in Sidebar")
                    else:
                        with st.spinner("Drafting..."):
                            llm = ChatGroq(temperature=0.6, groq_api_key=api_key, model_name="llama-3.1-8b-instant")
                            prompt = f"""
                            Write a formal letter from an MP to {comp}.
                            Context:
                            - We noticed they spent {amount} in {selected_state} on {sector}.
                            - Request them to extend this support to my specific constituency.
                            Tone: Professional and Appreciative.
                            """
                            draft = llm.invoke(prompt).content
                            st.text_area("Draft", draft, height=200)
                            
                            # Save
                            save_draft(username, f"State Lead: {comp}", draft, "CSR Letter")
                            show_download_button(draft, f"Letter_{comp}")
    else:
        st.error("Column 'CSR State' not found in CSV.")