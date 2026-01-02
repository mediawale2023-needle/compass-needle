import streamlit as st
import requests
import pandas as pd
import folium
from streamlit_folium import st_folium
from folium.plugins import HeatMap

# --- CONFIGURATION ---
API_URL = "http://127.0.0.1:8000"

def fetch_data():
    """Fetches both CASES and the Tenant's CONFIG"""
    try:
        cases = requests.get(f"{API_URL}/cases").json()
        config = requests.get(f"{API_URL}/tenant/config").json()
        return pd.DataFrame(cases), config
    except:
        return pd.DataFrame(), {}

def render_sansadx(username):
    # 1. FETCH DATA
    df, config = fetch_data()
    
    # 2. READ CONFIG (The Brain)
    # Defaults to LOK_SABHA if not specified
    client_type = config.get("type", "LOK_SABHA") 
    map_enabled = config.get("map_enabled", True)
    jurisdiction = config.get("jurisdiction", {}) # Wards or Districts

    st.title(f"📊 Grievance Dashboard")
    st.caption(f"Mode: {client_type.replace('_', ' ')}")
    
    if df.empty:
        st.warning("⚠️ No Data Available")
        return

    # 3. DATA CLEANING
    if "ward" in df.columns:
        df["area"] = df["ward"]
    else:
        df["area"] = "Unknown"

    # --- CONDITIONAL RENDERING ---

    # 🗺️ MODE A: LOK SABHA (Show Map)
    if client_type == "LOK_SABHA" and map_enabled:
        
        # Draw Map
        if jurisdiction:
            # Center on first ward in list
            try:
                first_ward = list(jurisdiction.values())[0]
                m = folium.Map(location=[first_ward["lat"], first_ward["lon"]], zoom_start=10)
                
                # Add Heat Points
                heat_data = []
                area_counts = df["area"].value_counts().to_dict()
                
                for area, count in area_counts.items():
                    if area in jurisdiction:
                        lat = jurisdiction[area]["lat"]
                        lon = jurisdiction[area]["lon"]
                        heat_data.append([lat, lon, count])
                        
                        # Marker
                        folium.Marker(
                            [lat, lon],
                            popup=f"{area}: {count} Issues",
                            tooltip=area,
                            icon=folium.Icon(color="red" if count > 5 else "blue")
                        ).add_to(m)
                
                if heat_data:
                    HeatMap(heat_data, radius=25).add_to(m)
                
                st_folium(m, width=800, height=400)
            except Exception as e:
                st.error(f"Map Error: Check JSON Config. {e}")
        else:
            st.info("Map enabled but no coordinates found in Config.")

    # 📉 MODE B: RAJYA SABHA (No Map, Just Charts)
    elif client_type == "RAJYA_SABHA":
        st.subheader("State-Wide Analysis")
        
        # Simple Bar Chart instead of Map
        if not df.empty:
            st.bar_chart(df["area"].value_counts())
        
        st.info("ℹ️ Viewing data by District/Sector (No Map).")

    # --- COMMON DATA TABLE ---
    st.divider()
    st.subheader("📋 Case Files")
    
    # Filter Logic
    all_areas = ["All"] + list(df["area"].unique())
    selected_area = st.selectbox("Filter by Area:", all_areas)
    
    if selected_area != "All":
        filtered_df = df[df["area"] == selected_area]
    else:
        filtered_df = df
        
    st.dataframe(filtered_df[["created_at", "area", "category", "status", "notes_for_staff"]], use_container_width=True)