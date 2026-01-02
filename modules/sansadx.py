import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime

# --- CONFIG ---
API_URL = "http://127.0.0.1:8000"

def fetch_cases(tenant_id):
    """Fetch all cases for the tenant from the backend"""
    try:
        resp = requests.get(f"{API_URL}/cases", params={"tenant_id": tenant_id})
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        st.error(f"Connection Error: {e}")
    return []

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

        # Build the row for the table
        data.append({
            "ID": c["id"],
            "Received": datetime.strptime(c["created_at"], "%Y-%m-%dT%H:%M:%S.%f").strftime("%d %b %H:%M"),
            "Sender": c["user_phone"],
            "Category": c["category"] or "General",
            "Location": geo_tag,           # The fixed location string
            "Message": c["raw_message"],   # <--- The actual message content
            "Status": c["status"],
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