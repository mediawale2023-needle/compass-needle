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
        print("✅ SansadX: Found DATABASE_URL, connecting to Postgres...")
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        return create_engine(db_url)
    
    print("⚠️ SansadX: No DATABASE_URL, using local SQLite.")
    return create_engine("sqlite:///needle.db")

def fetch_cases(tenant_id):
    """Fetch all cases for the tenant directly from the Database"""
    try:
        engine = get_engine()
        
        # SAFETY CHECK: Force tenant_id to be an Integer
        if not tenant_id:
            tenant_id = 1
        else:
            try:
                tenant_id = int(tenant_id)
            except:
                tenant_id = 1
            
        # ✅ FIX: Wrap query in text() for SQLAlchemy 2.0
        query = text("SELECT * FROM cases WHERE tenant_id = :tid ORDER BY created_at DESC")
        
        # ✅ FIX: Use a context manager for the connection
        with engine.connect() as conn:
            # We explicitly execute first to debug connection
            result = conn.execute(query, {"tid": tenant_id})
            # Convert to DataFrame
            df = pd.DataFrame(result.fetchall(), columns=result.keys())
        
        if not df.empty:
            # Fix datetime serialization for Streamlit
            df['created_at'] = df['created_at'].astype(str)
            return df.to_dict('records')
            
        return []

    except Exception as e:
        print(f"❌ SansadX DB Error: {e}")
        return []

# --- 2. RENDER FUNCTION (UI Logic) ---
def render_sansadx(username):
    st.title("💬 SansadX: Grievance Dashboard")
    
    # 1. Fetch Data
    tenant_id = st.session_state.get('tenant_id', 1) 
    cases = fetch_cases(tenant_id)
    
    if not cases:
        st.info("📭 Inbox is empty. Waiting for new messages...")
        # Optional: Add a refresh button
        if st.button("🔄 Check for New Messages"):
            st.rerun()
        return

    # 2. Process Data for Display
    data = []
    for c in cases:
        specific_loc = "Unknown"
        assembly = "Unknown"
        
        # --- GEO LOGIC ---
        try:
            # Postgres JSONB is sometimes already a dict, sometimes a string
            meta_raw = c.get("case_metadata")
            if isinstance(meta_raw, str):
                meta = json.loads(meta_raw)
            elif isinstance(meta_raw, dict):
                meta = meta_raw
            else:
                meta = {}

            if meta.get("location_resolved"):
                specific_loc = meta.get("matched_value", "Unknown").title()
                assembly = meta.get("assembly_constituency", "Unknown")
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
            # Handle Postgres format (often has milliseconds)
            if "." in time_str:
                parsed_time = datetime.strptime(time_str.split('.')[0], "%Y-%m-%d %H:%M:%S")
            else:
                parsed_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
            formatted_time = parsed_time.strftime("%d %b %H:%M")
        except:
            formatted_time = time_str

        # Append to list with EXACT requested keys
        data.append({
            "ID": c_id,
            "Time": formatted_time,
            "Sender": sender,
            "Category": cat,
            "Location": specific_loc,
            "Constituency": assembly,
            "Status": status,
            "Message": raw_msg,
            "Full_Meta": c.get("case_metadata") # Hidden column for debug
        })

    df = pd.DataFrame(data)

    # 3. Filters
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    with c1:
        search = st.text_input("🔍 Search Messages", placeholder="Search content...", key="sx_search")
    with c2:
        unique_cats = list(df["Category"].unique()) if not df.empty else []
        filter_cat = st.selectbox("Category", ["All"] + unique_cats, key="sx_cat")
    with c3:
        unique_const = list(df["Constituency"].unique()) if not df.empty else []
        filter_const = st.selectbox("Constituency", ["All"] + unique_const, key="sx_const")
    with c4:
        if st.button("🔄 Refresh"):
            st.rerun()

    if not df.empty:
        if search:
            mask = df["Message"].str.contains(search, case=False, na=False) | \
                   df["Location"].str.contains(search, case=False, na=False)
            df = df[mask]
        if filter_cat != "All":
            df = df[df["Category"] == filter_cat]
        if filter_const != "All":
            df = df[df["Constituency"] == filter_const]

    # 4. Render Table
    st.dataframe(
        df,
        column_config={
            "ID": st.column_config.NumberColumn("ID", width="small"),
            "Time": st.column_config.TextColumn("Received", width="small"),
            "Sender": st.column_config.TextColumn("Sender", width="medium"),
            "Category": st.column_config.TextColumn("Category", width="small"),
            "Location": st.column_config.TextColumn("Location", width="medium"),
            "Constituency": st.column_config.TextColumn("Constituency", width="medium"),
            "Status": st.column_config.SelectboxColumn("Status", options=["new", "closed", "progress"], width="small"),
            "Message": st.column_config.TextColumn("Message", width="large"),
            "Full_Meta": None
        },
        use_container_width=True,
        hide_index=True
    )

    # 5. Inspector
    st.divider()
    if not df.empty:
        st.subheader("🔎 Complaint Inspector")
        case_options = df["ID"].tolist()
        selected_id = st.selectbox("Select Case ID to Inspect:", case_options, key="sx_inspect")
        
        row = df[df["ID"] == selected_id].iloc[0]
        c1, c2 = st.columns(2)
        with c1:
            st.info(f"**From:** {row['Sender']}")
            st.markdown(f"**Message:**\n> {row['Message']}")
            st.caption(f"Received: {row['Time']}")
        with c2:
            st.success(f"📍 **Location:** {row['Location']}")
            st.warning(f"🗳️ **Constituency:** {row['Constituency']}")
            st.json(row["Full_Meta"])