import streamlit as st
import pandas as pd
import os
import glob

# --- CONFIGURATION ---
ALL_INDIA_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", 
    "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", 
    "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", 
    "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura", 
    "Uttar Pradesh", "Uttarakhand", "West Bengal",
    "Andaman & Nicobar", "Chandigarh", "Delhi", "Jammu & Kashmir", "Ladakh",
    "Lakshadweep", "Puducherry"
]

def get_all_csv_files():
    """Finds all CSVs in root and modules folder."""
    files = glob.glob("*.csv") + glob.glob("modules/*.csv") + glob.glob("../*.csv")
    return sorted(list(set(files)))

def load_data(selected_file):
    """Loads file and cleans numbers safely (handles Scientific Notation)."""
    if not selected_file or not os.path.exists(selected_file):
        return pd.DataFrame(), None

    try:
        df = pd.read_csv(selected_file)
        
        # 1. Identify Columns
        amt_col = next((c for c in df.columns if "Amount" in c or "Spent" in c or "Cost" in c), None)
        comp_col = next((c for c in df.columns if "Company" in c or "Name" in c), None)

        # 2. CLEANING: Remove "Total" Rows
        if comp_col:
            df = df[~df[comp_col].astype(str).str.contains("Total", case=False, na=False)]
            df = df[~df[comp_col].astype(str).str.contains("Grand", case=False, na=False)]

        # 3. Remove Duplicates
        df = df.drop_duplicates()

        # 4. CLEANING: Scientific Notation Safe
        if amt_col:
            # CRITICAL FIX: We simply remove commas, but we allow 'e', '.', and '-'
            # This allows Python to understand '5.0e-7' correctly as a small number
            df[amt_col] = pd.to_numeric(
                df[amt_col].astype(str).str.replace(',', ''), 
                errors='coerce'
            ).fillna(0)
            
        return df, amt_col
        
    except Exception as e:
        st.error(f"Error reading {selected_file}: {e}")
        return pd.DataFrame(), None

def render_state_intel(username):
    st.subheader("🗺️ CSR Intelligence Hub")

    # --- SETTINGS SECTION ---
    with st.expander("🛠️ Data Settings", expanded=True):
        c1, c2 = st.columns([3, 1])
        
        # File Selector
        all_files = get_all_csv_files()
        if not all_files:
            st.error("❌ No CSV files found! Please check your folder.")
            return

        with c1:
            # Auto-select the 2025 report if available
            default_idx = next((i for i, f in enumerate(all_files) if "2025" in f), 0)
            selected_file = st.selectbox("📂 Select Data Source:", all_files, index=default_idx)
            
        # Cache Clear
        with c2:
            st.write("") 
            if st.button("🧹 Clear Cache"):
                st.cache_data.clear()
                st.rerun()

    # --- LOAD DATA ---
    df, amt_col = load_data(selected_file)
    
    if df.empty or not amt_col:
        st.warning("File is empty or unreadable.")
        return 

    # --- DEFINE COLUMNS ---
    state_col = next((c for c in df.columns if "State" in c), "State")
    dist_col = next((c for c in df.columns if "District" in c or "City" in c), "District")
    sect_col = next((c for c in df.columns if "Sector" in c or "Focus" in c), "Sector")
    comp_col = next((c for c in df.columns if "Company" in c or "Name" in c), "Company Name")

    # --- FILTERS ---
    with st.container():
        c1, c2 = st.columns(2)
        with c1:
            selected_state = st.selectbox("📍 Select State", ["All India"] + sorted(ALL_INDIA_STATES))
        
        if selected_state != "All India":
            df = df[df[state_col] == selected_state]
            
        with c2:
            sectors = sorted(df[sect_col].dropna().unique().tolist()) if not df.empty else []
            selected_sector = st.multiselect("🏥 Select Sector", sectors)
            
        if selected_sector:
            df = df[df[sect_col].isin(selected_sector)]

    st.divider()

    # --- METRICS ---
    total_spend = df[amt_col].sum()
    active_companies = df[comp_col].nunique()
    
    # Calculate Top Spender
    if not df.empty:
        top_company = df.groupby(comp_col)[amt_col].sum().idxmax()
    else:
        top_company = "N/A"

    m1, m2, m3 = st.columns(3)
    m1.metric("💰 Total Available Funds", f"₹{total_spend:,.2f} Cr")
    m2.metric("🏢 Active Companies", active_companies)
    
    with m3:
        st.markdown(f"""
        <div style="border:1px solid #e0e0e0; padding:10px; border-radius:5px; background-color:white;">
            <div style="font-size:0.8rem; color:#666;">🏆 Leading Donor</div>
            <div style="font-size:1.0rem; font-weight:600; color:#0f172a; line-height:1.2; margin-top:5px; word-wrap: break-word;">
                {top_company}
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # --- LEADERBOARD ---
    st.subheader(f"🏢 Who is spending in {selected_state}?")
    
    if not df.empty:
        leaderboard = (
            df.groupby(comp_col)[[amt_col]]
            .sum()
            .sort_values(by=amt_col, ascending=False)
            .reset_index()
        )
        leaderboard.index += 1
        leaderboard.rename(columns={comp_col: "Company Name", amt_col: "Total Spent (Cr)"}, inplace=True)
        
        st.dataframe(
            leaderboard, 
            use_container_width=True,
            column_config={"Total Spent (Cr)": st.column_config.NumberColumn(format="₹ %.2f Cr")}
        )

    # --- PROJECT DETAILS ---
    with st.expander("📄 View Detailed Project breakdown", expanded=False):
        cols = [comp_col, sect_col, dist_col, amt_col]
        desc = next((c for c in df.columns if "Project" in c or "Description" in c), None)
        if desc: cols.insert(1, desc)
            
        st.dataframe(df[cols].sort_values(by=amt_col, ascending=False), use_container_width=True)