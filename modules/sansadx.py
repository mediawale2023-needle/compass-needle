import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
from sqlalchemy import create_engine, text

# --- 1. DIRECT DATABASE CONNECTION SETUP ---
# This replaces API_URL. It connects to Railway Postgres (if online) or SQLite (if local).

@st.cache_resource
def get_engine():
    """Smart connection: Uses Railway Postgres if available, else local SQLite"""
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        # Fix for SQLAlchemy requiring 'postgresql' instead of 'postgres'
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        return create_engine(db_url)
    return create_engine("sqlite:///needle.db")

def fetch_cases(tenant_id):
    """Fetch all cases for the tenant directly from the Database"""
    try:
        engine = get_engine()
        
        # We use a SQL query instead of an API call
        # Note: If your table is named 'grievances', change 'cases' to 'grievances' below.
        query = "SELECT * FROM cases WHERE tenant_id = :tid ORDER BY created_at DESC"
        
        # specific param mapping for safety
        df = pd.read_sql(query, engine, params={"tid": tenant_id})
        
        # Convert DataFrame to a list of dictionaries (to match the old API format)
        if not df.empty:
            # Ensure created_at is a string for the datetime parsing later
            df['created_at'] = df['created_at'].astype(str)
            return df.to_dict('records')
            
        return []

    except Exception as e:
        st.error(f"Database Error: {e}")
        return []

# --- 2. RENDER FUNCTION (UI Logic) ---
def render_sansadx(username):
    st.title("💬 SansadX: Grievance Inbox")
    
    # 1. Fetch Data
    # Ensure we have a valid tenant ID
    tenant_id = st.session_state.get('tenant_id', 1) 
    cases = fetch_cases(tenant_id)
    
    if not cases:
        st.info("📭 Inbox is empty. Waiting for new messages...")
        return

    # 2. Process Data for Display
    data = []
    for c in cases:
        # --- GEO LOGIC START ---
        # We try to extract the precise location from the metadata JSON
        geo_tag = "Unknown"
        assembly = ""
        
        try:
            if c.get("case_metadata"):
                # The metadata is stored as a JSON string, so we parse it
                meta = json.loads(c.get("case_metadata"))
                
                # Check if the resolver actually found something
                if meta.get("location_resolved"):
                    # Prioritize the specific match (e.g., "Muglihal")
                    specific_loc = meta.get("matched_value", "").title()
                    # Get the Assembly Context (e.g., "Belgaum North")
                    assembly = meta.get("assembly_constituency", "")
                    
                    if specific_loc:
                        geo_tag = f"{specific_loc} ({assembly})"
                    elif assembly:
                        geo_tag = assembly
        except Exception as e:
            # If JSON parsing fails, we keep it as Unknown
            pass
        # --- GEO LOGIC END ---

        # Safe extraction of fields (handles missing keys gracefully)
        raw_msg = c.get("raw_message", "")
        cat = c.get("category") or "General"
        status = c.get("status", "new")
        sender = c.get("user_phone", "Unknown")
        c_id = c.get("id")
        
        # Date Parsing (Handle different formats if needed)
        try:
            time_str = c.get("created_at", "")
            # Try parsing with microseconds
            parsed_time = datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%S.%f")
            formatted_time = parsed_time.strftime("%d %b %H:%M")
        except ValueError:
            try:
                # Fallback: Try parsing without microseconds
                parsed_time = datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%S")
                formatted_time = parsed_time.strftime("%d %b %H:%M")
            except:
                formatted_time = time_str # Just show raw string if fail

        # Build the row for the table
        data.append({
            "ID": c_id,
            "Received": formatted_time,
            "Sender": sender,
            "Category": cat,
            "Location": geo_tag,           # The fixed location string
            "Message": raw_msg,   # <--- The actual message content
            "Status": status,
            "Full_Meta": c.get("case_metadata") # Hidden column for inspector
        })

    df = pd.DataFrame(data)

    # 3. Filters
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        search = st.text_input("🔍 Search Messages", placeholder="Search text or location...")
    with c2:
        # Dynamic filter for Categories based on what exists
        unique_cats = list(df["Category"].unique()) if not df.empty else []
        filter_cat = st.selectbox("Filter Category", ["All"] + unique_cats)
    with c3:
        # Dynamic filter for Status
        filter_stat = st.selectbox("Status", ["All", "new", "progress", "closed"])

    # Apply Filters
    if not df.empty:
        if search:
            # Search across Message and Location columns
            mask = df["Message"].str.contains(search, case=False, na=False) | \
                   df["Location"].str.contains(search, case=False, na=False)
            df = df[mask]
        if filter_cat != "All":
            df = df[df["Category"] == filter_cat]
        if filter_stat != "All":
            df = df[df["Status"] == filter_stat]

    # 4. Render Beautiful Table
    st.dataframe(
        df,
        column_config={
            "ID": st.column_config.NumberColumn("ID", width="small"),
            "Received": st.column_config.TextColumn("Time", width="small"),
            "Sender": st.column_config.TextColumn("Citizen", width="medium"),
            "Category": st.column_config.TextColumn("Type", width="small"),
            "Location": st.column_config.TextColumn("📍 Location", width="medium"),
            "Message": st.column_config.TextColumn("📝 Content", width="large"), # Shows full text
            "Status": st.column_config.SelectboxColumn("Status", options=["new", "closed", "progress"], width="small"),
            "Full_Meta": None # Hide this column from the view
        },
        use_container_width=True,
        hide_index=True
    )

    # 5. Quick View (Inspector)
    st.divider()
    st.subheader("🔎 Case Inspector")
    
    # Dropdown to select a case from the visible table
    if not df.empty:
        case_options = df["ID"].tolist()
        selected_id = st.selectbox("Select Case ID to Inspect:", case_options)
        
        # Get the full row data for the selected ID
        row = df[df["ID"] == selected_id].iloc[0]
        
        c1, c2 = st.columns(2)
        with c1:
            st.info(f"**From:** {row['Sender']}")
            st.markdown(f"**Message:**\n> {row['Message']}")
            st.caption(f"Received: {row['Received']}")
        
        with c2:
            st.warning("📍 Geography Data (Debug Info)")
            # Try to show the raw metadata so you can see why geography failed/succeeded
            try:
                if row["Full_Meta"]:
                    meta_json = json.loads(row["Full_Meta"])
                    st.json(meta_json)
                else:
                    st.write("No geography metadata found.")
            except:
                st.write("Error parsing metadata.")