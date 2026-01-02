import streamlit as st
import requests
import pandas as pd
import json
import time

API_URL = "http://127.0.0.1:8000"

# --- API HELPERS ---
def fetch_stats():
    try:
        return requests.get(f"{API_URL}/admin/stats").json()
    except:
        return {}

def fetch_tenants():
    try:
        return requests.get(f"{API_URL}/admin/tenants").json()
    except:
        return []

def create_client(payload):
    try:
        res = requests.post(f"{API_URL}/admin/tenants", json=payload)
        return res.status_code == 200
    except:
        return False

def update_client_config(tenant_id, new_config_dict):
    """Sends the edited JSON to the backend"""
    payload = {"config": new_config_dict}
    try:
        res = requests.patch(f"{API_URL}/admin/tenants/{tenant_id}", json=payload)
        return res.status_code == 200
    except:
        return False

# --- MAIN RENDERER ---
def render_master_admin():
    st.title("⚡ Needle Master Admin")
    st.caption("SaaS Super-Controller | Multi-Tenant Management")
    
    # 1. METRICS
    stats = fetch_stats()
    c1, c2, c3 = st.columns(3)
    c1.metric("Active Clients", stats.get("clients", 0))
    c2.metric("Total Grievances", stats.get("total_grievances", 0))
    c3.metric("System Health", "Online")

    st.divider()

    # 2. CLIENT TABLE (The Trigger)
    st.subheader("👥 Active Clients")
    
    tenants = fetch_tenants()
    if not tenants:
        st.warning("No Clients Found. Add one below.")
        client = None
    else:
        df = pd.DataFrame(tenants)
        
        # 🧠 INTERACTIVE TABLE
        # "on_select='rerun'" makes the app reload instantly when you click a row
        selection = st.dataframe(
            df[["id", "name", "constituency", "whatsapp_number", "subscription_plan"]],
            use_container_width=True,
            hide_index=True,
            on_select="rerun",           # <--- THE MAGIC
            selection_mode="single-row"  # Only one client at a time
        )
        
        # 3. HANDLE SELECTION
        # Check if a row was clicked
        if selection.selection.rows:
            selected_index = selection.selection.rows[0]
            client = tenants[selected_index] # Get the full object using the index
        else:
            client = None

    # 4. INSPECTOR PANE (Conditional Render)
    if client:
        st.markdown("---") # Visual separator
        st.info(f"🔍 Inspecting: **{client['name']}**")
        
        c_left, c_right = st.columns([1, 2])
        
        # --- VIEW DETAILS ---
        with c_left:
            st.markdown("### 📋 Profile")
            st.text_input("Name", value=client['name'], disabled=True)
            st.text_input("Constituency", value=client['constituency'], disabled=True)
            st.text_input("Bot Number", value=client['whatsapp_number'], disabled=True)
            st.text_input("Plan", value=client['subscription_plan'], disabled=True)

        # --- EDITOR ---
        with c_right:
            st.markdown("### ⚙️ Configuration (JSON)")
            
            # TABS: View vs Edit
            t_view, t_edit = st.tabs(["👁️ View Config", "✏️ Edit Config"])
            
            with t_view:
                st.json(client.get("config", {}), expanded=False)
            
            with t_edit:
                current_json_str = json.dumps(client.get("config", {}), indent=2)
                
                new_json_str = st.text_area(
                    "Paste new configuration here:", 
                    value=current_json_str, 
                    height=300
                )
                
                if st.button("💾 Save Changes", type="primary"):
                    try:
                        clean_config = json.loads(new_json_str)
                        if update_client_config(client['id'], clean_config):
                            st.toast("✅ Config Updated!", icon="💾")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("Backend Error.")
                    except json.JSONDecodeError:
                        st.error("❌ Invalid JSON.")

    else:
        # Helper text when nothing is selected
        if tenants:
            st.caption("👆 Click on a row above to view details and edit configuration.")

    # 5. ONBOARDING (Always at bottom)
    st.divider()
    with st.expander("➕ Onboard New Client"):
        c1, c2, c3 = st.columns(3)
        new_name = c1.text_input("Name")
        new_const = c2.text_input("Constituency")
        new_phone = c3.text_input("Bot Number")
        
        if st.button("Create Client"):
            payload = {
                "name": new_name,
                "constituency": new_const,
                "whatsapp_number": new_phone,
                "config": {"type": "LOK_SABHA", "map_enabled": True, "jurisdiction": {}}
            }
            if create_client(payload):
                st.success("Client Created! Click their name in the table to configure.")
                st.rerun()