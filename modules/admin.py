import streamlit as st
import json
import pandas as pd
import os
from datetime import datetime
# --- IMPORT UTILITIES ---
from modules.utils import track_action, show_download_button

def run_intelligence_cycle():
    """Reads PQ DB -> Updates Scheme Status"""
    try:
        # Load all necessary files
        with open("schemes.json", "r") as f: schemes = json.load(f)
        with open("questions_db.json", "r") as f: questions = json.load(f)
    except: return ["Error: Schemes or Questions Database missing."]

    logs = []
    
    # 1. Logic Loop
    for scheme in schemes:
        scheme_name = scheme.get('Scheme', '').split(" ")[0] # Match first word like "AMRUT"
        for q in questions:
            if scheme_name in q.get('text', '') or scheme_name in q.get('answer', ''):
                ans = q.get('answer', '').lower()
                
                # Check for RED FLAGS
                if any(x in ans for x in ["exhausted", "no further", "insufficient", "utilized 90%"]):
                    scheme['Status'] = "🔴 Funds Exhausted"
                    scheme['Confidence'] = 10
                    scheme['Evidence'] = f"Auto-detected from PQ #{q.get('question_id', 'N/A')}: Minister admitted funds exhausted."
                    logs.append(f"🔻 {scheme['Scheme']} -> RED")
                
                # Check for GREEN FLAGS
                elif any(x in ans for x in ["unspent", "released", "available", "fresh proposals"]):
                    scheme['Status'] = "🟢 High Liquidity"
                    scheme['Confidence'] = 90
                    scheme['Evidence'] = f"Auto-detected from PQ #{q.get('question_id', 'N/A')}: Minister mentioned unspent funds."
                    logs.append(f"🟢 {scheme['Scheme']} -> GREEN")
    
    # 2. Save the new "Truth"
    with open("schemes.json", "w") as f: json.dump(schemes, f, indent=4)
    
    # --- LOG ACTION ---
    track_action(f"Admin: Ran Intelligence Cycle ({len(logs)} updates)")
    
    return logs

def render_admin():
    st.title("🎛️ Master Control Panel (Admin)")
    st.info("System Status: Operational. Logged in as Admin.")
    
    tab1, tab2 = st.tabs(["🔄 Intelligence Engine", "💾 Database Manager"])

    # TAB 1: INTELLIGENCE
    with tab1:
        st.subheader("🤖 Auto-Intelligence Engine")
        st.info("Triggers NLP analysis on recent Parliamentary Questions (PQ) to update scheme status.")
        
        if st.button("🔄 Run Intelligence Cycle"):
            with st.spinner("Analyzing Minister's Answers..."):
                logs = run_intelligence_cycle()
                if logs:
                    st.success("Intelligence Updated!")
                    for log in logs: st.text(log)
                else: st.warning("No new matches found or data is stale.")
        
        st.divider()
        st.subheader("Current Scheme Status (Live View)")
        try:
            with open("schemes.json", "r") as f: 
                current_schemes = json.load(f)
            st.dataframe(pd.DataFrame(current_schemes), use_container_width=True)
            
            # --- NEW: DOWNLOAD CURRENT DATABASE ---
            st.caption("Download current database state:")
            show_download_button(json.dumps(current_schemes, indent=4), "Current_Schemes_DB")
            
        except:
            st.error("No schemes.json found.")
            
    # TAB 2: DATABASE MANAGER
    with tab2:
        st.subheader("Update Core Databases")
        
        # --- SCHEMES DB MANAGEMENT ---
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Schemes DB (schemes.json)**")
            # Download Backup
            if os.path.exists("schemes.json"):
                with open("schemes.json", "r") as f: 
                    show_download_button(f.read(), "Backup_Schemes")
            
            # Upload New
            up_sch = st.file_uploader("Upload New Schemes List", type="json", key="sch")
            if up_sch:
                with open("schemes.json", "wb") as f: f.write(up_sch.getbuffer())
                st.success("Schemes DB Updated.")
                track_action("Admin: Updated Schemes Database")

        # --- PQ DB MANAGEMENT ---
        with c2:
            st.markdown("**PQ DB (questions_db.json)**")
            # Download Backup
            if os.path.exists("questions_db.json"):
                with open("questions_db.json", "r") as f: 
                    show_download_button(f.read(), "Backup_PQ_DB")

            # Upload New
            up_pq = st.file_uploader("Upload New PQ Dump", type="json", key="pq")
            if up_pq:
                with open("questions_db.json", "wb") as f: f.write(up_pq.getbuffer())
                st.success("PQ DB Updated.")
                track_action("Admin: Updated PQ Database")
        
        st.divider()
        st.subheader("User Management (Simulated)")
        st.info(f"To add/remove users, edit the `.streamlit/secrets.toml` file manually.")