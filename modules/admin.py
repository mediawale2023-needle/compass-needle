import streamlit as st
import requests
import pandas as pd
import json

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

    # 2. MAIN LAYOUT
    tenants = fetch_tenants()
    if not tenants:
        st.warning("No Clients Found. Add one below.")
    
    col_left, col_right = st.columns([1, 2])

    # --- LEFT COLUMN: CLIENT SELECTOR ---
    with col_left:
        st.subheader("👥 Client List")
        if tenants:
            df = pd.DataFrame(tenants)
            # Radio button acts as the "Selector"
            selected_id = st.radio(
                "Select Client to Manage:", 
                df["id"].tolist(), 
                format_func=lambda x: df[df["id"]==x]["name"].values[0]
            )
            # Find the full object for the selected ID
            client = next((t for t in tenants if t["id"] == selected_id), None)
        else:
            client = None

    # --- RIGHT COLUMN: EDITOR ---
    with col_right:
        if client:
            st.subheader(f"⚙️ Managing: {client['name']}")
            
            # TABS: View vs Edit
            t1, t2 = st.tabs(["🔍 View Details", "✏️ JSON Config Editor"])
            
            # TAB 1: READ ONLY
            with t1:
                st.info(f"**Constituency:** {client['constituency']}")
                st.info(f"**Bot Number:** {client['whatsapp_number']}")
                st.write("**Current Config:**")
                st.json(client.get("config", {}))

            # TAB 2: EDIT MODE
            with t2:
                st.markdown("### Update Map & Logic")
                st.caption("Paste the contents of your `constituency_library` file here.")
                
                # Convert Dict -> String for editing
                current_json_str = json.dumps(client.get("config", {}), indent=2)
                
                # Text Area
                new_json_str = st.text_area(
                    "Configuration JSON", 
                    value=current_json_str, 
                    height=400
                )
                
                if st.button("💾 Save Config", type="primary"):
                    try:
                        # Validate syntax before sending
                        clean_config = json.loads(new_json_str)
                        
                        # Send to Backend
                        if update_client_config(client['id'], clean_config):
                            st.success("✅ Saved! The Client's dashboard is updated.")
                            st.rerun()
                        else:
                            st.error("Backend Error: Could not save.")
                            
                    except json.JSONDecodeError:
                        st.error("❌ Invalid JSON. Check for missing commas or brackets.")

    st.divider()
    
    # --- BOTTOM: ONBOARDING ---
    with st.expander("➕ Onboard New Client"):
        c1, c2, c3 = st.columns(3)
        new_name = c1.text_input("Name")
        new_const = c2.text_input("Constituency")
        new_phone = c3.text_input("Bot Number")
        
        if st.button("Create Client"):
            # Create with empty default config
            payload = {
                "name": new_name,
                "constituency": new_const,
                "whatsapp_number": new_phone,
                "config": {"type": "LOK_SABHA", "map_enabled": True, "jurisdiction": {}}
            }
            if create_client(payload):
                st.success("Client Created! Now select them above to add Map Data.")
                st.rerun()