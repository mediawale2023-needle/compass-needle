import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
from sqlalchemy import create_engine, text

# --- 1. DIRECT DATABASE CONNECTION SETUP ---
@st.cache_resource
def get_engine():
    """Smart connection: Uses Railway Postgres if available, else local SQLite (same as db.py)"""
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        # Fix for SQLAlchemy: Postgres requires 'postgresql://'
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        return create_engine(db_url)
    return create_engine("sqlite:///./sansadx.db")

def fetch_cases(tenant_id):
    """Fetch all cases for the tenant directly from the Database"""
    try:
        engine = get_engine()
        if not tenant_id: tenant_id = 1
        
        # Query all cases
        query = text("SELECT * FROM cases WHERE tenant_id = :tid ORDER BY created_at DESC")
        
        with engine.connect() as conn:
            result = conn.execute(query, {"tid": tenant_id})
            df = pd.DataFrame(result.fetchall(), columns=result.keys())
        
        if not df.empty:
            df['created_at'] = df['created_at'].astype(str)
            return df.to_dict('records')
        return []

    except Exception as e:
        print(f" SansadX DB Error: {e}")
        return []

# --- 2. HELPER: RENDER TABLE ---
def render_filtered_table(df, key_suffix):
    """Reusable function to render the table inside tabs"""
    if df.empty:
        st.info("No messages in this category.")
        return

    st.dataframe(
        df,
        column_config={
            "ID": st.column_config.NumberColumn("ID", width="small"),
            "Time": st.column_config.TextColumn("Received", width="small"),
            "Sender": st.column_config.TextColumn("Sender", width="medium"),
            "Category": st.column_config.TextColumn("Category", width="small"),
            "Location": st.column_config.TextColumn("Location", width="medium"),
            "Constituency": st.column_config.TextColumn("Constituency", width="medium"),
            "Status": st.column_config.SelectboxColumn("Status", options=["new", "closed", "progress", "OFFENSIVE", "completed", "incomplete"], width="small"),
            "Message": st.column_config.TextColumn("Message", width="large"),
            "Full_Meta": None, # Hidden
            "Intent": None # Hidden
        },
        use_container_width=True,
        hide_index=True,
        key=f"table_{key_suffix}"
    )

# --- 3. MAIN RENDER FUNCTION ---
def render_sansadx(username):
    st.title("SansadX: Grievance Dashboard")
    
    # A. Fetch Data
    tenant_id = st.session_state.get('tenant_id', 1) 
    cases = fetch_cases(tenant_id)
    
    if not cases:
        st.info(" Inbox is empty. Waiting for new messages...")
        if st.button(" Check for New Messages"): st.rerun()
        return

    # B. Process Data & Extract Intent
    data = []
    for c in cases:
        specific_loc = "Unknown"
        assembly = ""
        # TAD NECESSARY: Match status from main.py logic
        db_status = str(c.get("status", "new")).lower()
        intent = "complaint" # Default

        # Parse Metadata
        try:
            meta_raw = c.get("case_metadata")
            if isinstance(meta_raw, str): meta = json.loads(meta_raw)
            elif isinstance(meta_raw, dict): meta = meta_raw
            else: meta = {}

            # Extract Geography
            if meta.get("location_resolved"):
                specific_loc = meta.get("matched_value", "Unknown").title()
                assembly = meta.get("assembly_constituency", "")
            
            # Extract Intent (The Key Logic)
            intent = meta.get("user_intent", "complaint").lower()
            
            # TAD NECESSARY: If status is 'completed' or 'incomplete', it belongs in Complaints
            if db_status in ["completed", "incomplete"]:
                intent = "complaint"
            elif db_status == "offensive":
                intent = "offensive"
            elif db_status == "emergency":
                intent = "emergency"
            elif db_status == "irrelevant":
                intent = "greeting"

        except Exception:
            pass

        # FALLBACK: If case_metadata was empty, use location/ward columns
        if specific_loc == "Unknown" and c.get("location"):
            specific_loc = str(c.get("location", "")).title()
        if not assembly and c.get("ward"):
            assembly = str(c.get("ward", ""))

        # Formatting
        time_str = str(c.get("created_at", ""))
        try:
            if "." in time_str: parsed_time = datetime.strptime(time_str.split('.')[0], "%Y-%m-%d %H:%M:%S")
            else: parsed_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
            formatted_time = parsed_time.strftime("%d %b %H:%M")
        except: formatted_time = time_str

        data.append({
            "ID": c.get("id"),
            "Time": formatted_time,
            "Sender": c.get("user_phone", "Unknown"),
            "Category": c.get("category") or "General",
            "Location": specific_loc,
            "Constituency": assembly,
            "Status": db_status,
            "Message": c.get("raw_message", ""),
            "Intent": intent, # Used for filtering tabs
            "Full_Meta": c.get("case_metadata")
        })

    main_df = pd.DataFrame(data)

    # C. Global Filters (Apply to all tabs)
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    with c1: search = st.text_input(" Search", placeholder="Search content...", key="sx_search")
    with c2: filter_const = st.selectbox("Constituency", ["All"] + list(main_df["Constituency"].unique()), key="sx_const")
    with c4: 
        if st.button(" Refresh", use_container_width=True): st.rerun()

    # Apply Search/Constituency Filters first
    if search:
        mask = main_df["Message"].str.contains(search, case=False, na=False) | \
               main_df["Location"].str.contains(search, case=False, na=False)
        main_df = main_df[mask]
    if filter_const != "All":
        main_df = main_df[main_df["Constituency"] == filter_const]

    # D. SPLIT DATAFRAMES BY INTENT
    df_emergency = main_df[main_df['Intent'] == 'emergency']
    df_complaint = main_df[main_df['Intent'] == 'complaint']
    df_request = main_df[main_df['Intent'] == 'request']
    df_greeting = main_df[main_df['Intent'] == 'greeting']
    df_spam = main_df[main_df['Intent'] == 'offensive']

    # E. RENDER TABS (CLEAN & PROFESSIONAL)
    t1, t2, t3, t4, t5 = st.tabs([
        f"Complaints ({len(df_complaint)})",
        f"Emergency ({len(df_emergency)})",
        f"Requests ({len(df_request)})",
        f"Greetings ({len(df_greeting)})",
        f"Spam ({len(df_spam)})"
    ])

    with t1: render_filtered_table(df_complaint, "cmp")
    with t2: render_filtered_table(df_emergency, "emg")
    with t3: render_filtered_table(df_request, "req")
    with t4: render_filtered_table(df_greeting, "grt")
    with t5: render_filtered_table(df_spam, "spm")