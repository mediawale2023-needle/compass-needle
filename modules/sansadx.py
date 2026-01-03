import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
from sqlalchemy import create_engine, text

# --- 1. DIRECT DATABASE CONNECTION SETUP ---
@st.cache_resource
def get_engine():
    """Smart connection: Uses Railway Postgres if available, else local SQLite"""
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        return create_engine(db_url)
    return create_engine("sqlite:///needle.db")

def fetch_cases(tenant_id):
    """Fetch all cases for the tenant directly from the Database"""
    try:
        engine = get_engine()
        
        # SAFETY CHECK: If tenant_id is missing, default to 1
        if not tenant_id:
            tenant_id = 1
            
        # ✅ CORRECTED QUERY
        query = "SELECT * FROM cases WHERE tenant_id = :tid ORDER BY created_at DESC"
        
        # Run query with safe parameters
        df = pd.read_sql(query, engine, params={"tid": tenant_id})
        
        if not df.empty:
            df['created_at'] = df['created_at'].astype(str)
            return df.to_dict('records')
            
        return []

    except Exception as e:
        print(f"Database Error: {e}")
        return []

# --- 2. RENDER FUNCTION (UI Logic) ---
def render_sansadx(username):
    st.title("💬 SansadX: Grievance Inbox")
    
    # 1. Fetch Data
    tenant_id = st.session_state.get('tenant_id', 1) 
    cases = fetch_cases(tenant_id)
    
    if not cases:
        st.info("📭 Inbox is empty. Waiting for new messages...")
        return

    # 2. Process Data for Display
    data = []
    for c in cases:
        geo_tag = "Unknown"
        assembly = ""
        
        # --- GEO LOGIC ---
        try:
            if c.get("case_metadata"):
                meta = json.loads(c.get("case_metadata"))
                if meta.get("location_resolved"):
                    specific_loc = meta.get("matched_value", "").title()
                    assembly = meta.get("assembly_constituency", "")
                    if specific_loc:
                        geo_tag = f"{specific_loc} ({assembly})"
                    elif assembly:
                        geo_tag = assembly
        except Exception:
            pass

        # Safe extraction
        raw_msg = c.get("raw_message", "")
        cat = c.get("category") or "General"
        status = c.get("status", "new")
        sender = c.get("user_phone", "Unknown")
        c_id = c.get("id")
        
        # Date Parsing
        time_str = str(c.get("created_at", ""))
        try:
            # Try formatting cleanly, otherwise just show string
            parsed_time = datetime.strptime(time_str.split('.')[0], "%Y-%m-%dT%H:%M:%S")
            formatted_time = parsed_time.strftime("%d %b %H:%M")
        except:
            formatted_time = time_str

        data.append({
            "ID": c_id,
            "Received": formatted_time,
            "Sender": sender,
            "Category": cat,
            "Location": geo_tag,
            "Message": raw_msg,
            "Status": status,
            "Full_Meta": c.get("case_metadata")
        })

    df = pd.DataFrame(data)

    # 3. Filters
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        search = st.text_input("🔍 Search Messages", placeholder="Search text or location...")
    with c2:
        unique_cats = list(df["Category"].unique()) if not df.empty else []
        filter_cat = st.selectbox("Filter Category", ["All"] + unique_cats)
    with c3:
        filter_stat = st.selectbox("Status", ["All", "new", "progress", "closed"])

    if not df.empty:
        if search:
            mask = df["Message"].str.contains(search, case=False, na=False) | \
                   df["Location"].str.contains(search, case=False, na=False)
            df = df[mask]
        if filter_cat != "All":
            df = df[df["Category"] == filter_cat]
        if filter_stat != "All":
            df = df[df["Status"] == filter_stat]

    # 4. Render Table
    st.dataframe(
        df,
        column_config={
            "ID": st.column_config.NumberColumn("ID", width="small"),
            "Received": st.column_config.TextColumn("Time", width="small"),
            "Sender": st.column_config.TextColumn("Citizen", width="medium"),
            "Category": st.column_config.TextColumn("Type", width="small"),
            "Location": st.column_config.TextColumn("📍 Location", width="medium"),
            "Message": st.column_config.TextColumn("📝 Content", width="large"),
            "Status": st.column_config.SelectboxColumn("Status", options=["new", "closed", "progress"], width="small"),
            "Full_Meta": None
        },
        use_container_width=True,
        hide_index=True
    )

    # 5. Inspector
    st.divider()
    if not df.empty:
        st.subheader("🔎 Case Inspector")
        case_options = df["ID"].tolist()
        selected_id = st.selectbox("Select Case ID to Inspect:", case_options)
        
        row = df[df["ID"] == selected_id].iloc[0]
        c1, c2 = st.columns(2)
        with c1:
            st.info(f"**From:** {row['Sender']}")
            st.markdown(f"**Message:**\n> {row['Message']}")
            st.caption(f"Received: {row['Received']}")
        with c2:
            st.warning("📍 Geography Data (Debug Info)")
            try:
                if row["Full_Meta"]:
                    st.json(json.loads(row["Full_Meta"]))
                else:
                    st.write("No geography metadata found.")
            except:
                st.write("Error parsing metadata.")