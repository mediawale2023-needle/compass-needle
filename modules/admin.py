import streamlit as st
import json
import random
from datetime import datetime
import pandas as pd

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
        scheme_name = scheme['Scheme'].split(" ")[0] # Match first word like "AMRUT"
        for q in questions:
            if scheme_name in q['text'] or scheme_name in q['answer']:
                ans = q['answer'].lower()
                
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
        st.subheader("Current Scheme Status (Editable)")
        try:
            with open("schemes.json", "r") as f: 
                current_schemes = json.load(f)
            st.dataframe(pd.DataFrame(current_schemes), use_container_width=True)
        except:
            st.error("No schemes.json found.")
            
    # TAB 2: DATABASE MANAGER
    with tab2:
        st.subheader("Update Core Databases")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Schemes DB (schemes.json)**")
            up_sch = st.file_uploader("Upload New Schemes List", type="json", key="sch")
            if up_sch:
                with open("schemes.json", "wb") as f: f.write(up_sch.getbuffer())
                st.success("Schemes DB Updated.")
        with c2:
            st.markdown("**PQ DB (questions_db.json)**")
            up_pq = st.file_uploader("Upload New PQ Dump", type="json", key="pq")
            if up_pq:
                with open("questions_db.json", "wb") as f: f.write(up_pq.getbuffer())
                st.success("PQ DB Updated.")
        
        st.divider()
        st.subheader("User Management (Simulated)")
        st.info(f"To add/remove users, edit the `.streamlit/secrets.toml` file manually.")