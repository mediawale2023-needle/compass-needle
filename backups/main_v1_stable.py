import streamlit as st
import requests
from streamlit_option_menu import option_menu
from datetime import datetime, timedelta
import os
import base64
from dotenv import load_dotenv

# --- 1. BOOTSTRAP SYSTEM ---
load_dotenv()

# --- 2. PAGE CONFIG ---
st.set_page_config(
    page_title="Needle | MP Dashboard",
    page_icon="🇮🇳",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 3. SECURE IMPORTS ---
try:
    from modules.settings import render_settings
    from modules.copilot import render_copilot
    from modules.drafter import render_drafter
    from modules.matcher import render_matcher
    from modules.sansadx import render_sansadx
    from modules.news_intel import fetch_news, analyze_sentiment
    from modules.persistence import load_archives, delete_draft
    from modules.csr_projects import render_csr_projects
    from modules.state_intel import render_state_intel
    from modules.pmb_drafter import render_pmb_drafter
except ImportError as e:
    st.error(f"⚠️ System Boot Error: {e}")
    st.stop()

# --- 4. SESSION STATE ---
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'current_user' not in st.session_state: st.session_state.current_user = ""
if 'mp_name' not in st.session_state: st.session_state.mp_name = "Jagdish Shettar"
if 'constituency' not in st.session_state: st.session_state.constituency = "Belagavi"
if 'theme_color' not in st.session_state: st.session_state.theme_color = "#009a4e"
if 'calendar_notes' not in st.session_state: st.session_state.calendar_notes = {}

# --- 5. THEME ENGINE ---
def inject_custom_css(color_hex):
    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
        html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; color: #333; }}
        .needle-header {{ background: white; padding: 1rem 1.5rem; border-bottom: 1px solid #e0e0e0; margin-bottom: 2rem; display: flex; align-items: center; justify-content: space-between; }}
        .needle-logo {{ font-size: 26px; font-weight: 800; color: {color_hex}; display: flex; align-items: center; gap: 10px; }}
        .widget-card {{ background: white; padding: 20px; border-radius: 8px; border: 1px solid #eee; box-shadow: 0 2px 8px rgba(0,0,0,0.04); margin-bottom: 20px; }}
        .widget-title {{ font-size: 14px; font-weight: 700; color: #666; margin-bottom: 15px; text-transform: uppercase; border-bottom: 2px solid {color_hex}; padding-bottom: 5px; display: inline-block; }}
        .ticker-box {{ background-color: #fff3cd; color: #856404; padding: 12px; border-radius: 4px; border-left: 5px solid #ffc107; font-weight: 600; margin-bottom: 10px; }}
        .news-item {{ padding: 12px 0; border-bottom: 1px solid #f0f0f0; }}
        .news-date {{ font-size: 11px; color: #999; margin-bottom: 4px; display: block; }}
        .news-tag-pos {{ color: #28a745; font-size: 10px; font-weight: 700; background: #e6f4ea; padding: 2px 6px; border-radius: 4px; }}
        .news-tag-neg {{ color: #dc3545; font-size: 10px; font-weight: 700; background: #fde8e8; padding: 2px 6px; border-radius: 4px; }}
        .news-tag-neu {{ color: #666; font-size: 10px; font-weight: 700; background: #f0f0f0; padding: 2px 6px; border-radius: 4px; }}
        .stButton > button {{ background-color: {color_hex}; color: white; border: none; font-weight: 600; }}
    </style>
    """, unsafe_allow_html=True)

# --- 6. LOGIN LOGIC ---
if not st.session_state.authenticated:
    st.markdown("<div style='text-align: center; margin-top: 100px;'><h1>🪡 Needle</h1><p>MP Private Access Portal</p></div>", unsafe_allow_html=True)
    _, col, _ = st.columns([1, 1, 1])
    with col:
        with st.form("login"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.form_submit_button("Log In", use_container_width=True):
                if u == "admin" and p == "password":
                    st.session_state.authenticated = True
                    st.session_state.current_user = "admin"
                    st.rerun()
                else: st.error("Invalid Credentials")

else:
    color = st.session_state.theme_color
    inject_custom_css(color)
    username = st.session_state.mp_name 
    constituency = st.session_state.constituency

    # --- HEADER ---
    st.markdown(f"""
    <div class="needle-header">
        <div class="needle-logo"><span>🪡</span> Needle</div>
        <div style="font-size: 14px; font-weight: 500;">
            <span style="color: {color};">● System Online</span> | <span>{username} ({constituency})</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- SIDEBAR ---
    with st.sidebar:
        selected = option_menu(
            menu_title=None,
            options=["Dashboard", "SansadX", "Co-Pilot", "Drafter", "PMB", "CSR Suite", "Schemes", "Archives", "Settings"], 
            icons=["speedometer2", "whatsapp", "robot", "pen", "law", "buildings", "cash-coin", "archive", "gear"], 
            default_index=0,
            styles={"nav-link-selected": {"background-color": color}}
        )
        if st.button("🔒 Secure Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()

    # --- 7. DASHBOARD ROUTING ---
    if selected == "Dashboard":
        st.markdown(f"<div class='widget-card'><div class='widget-title'>🔥 Situation Room</div>", unsafe_allow_html=True)
        c1, c2 = st.columns([2, 1])
        with c1:
            st.caption("BURNING ISSUES TICKER")
            st.markdown(f"<div class='ticker-box'>📢 Crisis Alert in {constituency}: Water Shortage reported.</div>", unsafe_allow_html=True)
        with c2:
            st.caption("CRISIS MAP")
            st.error("📍 2 Red Zones Detected")
        st.markdown("</div>", unsafe_allow_html=True)

        l_col, r_col = st.columns([2, 1])
        with l_col:
            st.markdown("<div class='widget-card'><div class='widget-title'>🏛️ Parliamentary Desk</div>", unsafe_allow_html=True)
            st.info("📜 **Parliament is currently in Session**")
            st.markdown("</div>", unsafe_allow_html=True)

            # --- MEDIA CENTRE (Sorted by Date) ---
            st.markdown("<div class='widget-card'><div class='widget-title'>📰 Media Centre (Live)</div>", unsafe_allow_html=True)
            
            # Create Tabs
            tab_nat, tab_loc = st.tabs(["🇮🇳 National", "📍 Local Pulse"])

            # --- TAB 1: NATIONAL NEWS (English) ---
            with tab_nat:
                nat_query = f"{username} politics"
                news_nat = fetch_news(query=nat_query, language="English", limit=5)
                
                # SORTING LOGIC: Latest Date First
                if news_nat:
                    news_nat = sorted(news_nat, key=lambda x: x['published'], reverse=True)
                    
                    for news in news_nat:
                        sent = analyze_sentiment(news['title'])
                        d_str = news['published'].strftime("%d %b | %H:%M")
                        tag_class = f"news-tag-{sent}"
                        
                        st.markdown(f"""
                        <div class='news-item'>
                            <span class='news-date'>{d_str} | {news['source']}</span>
                            <a href='{news['link']}' target='_blank' style='text-decoration:none; color:#333;'>
                                {news['title']}
                            </a>
                            <span class='{tag_class}' style='font-size:0.7rem; float:right;'>{sent.upper()}</span>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.caption("No national updates found.")

            # --- TAB 2: LOCAL PULSE (With Manual Inputs) ---
            with tab_loc:
                c_lang, c_place = st.columns([1, 1])
                with c_lang:
                    local_lang = st.selectbox("Language", ["English", "Hindi", "Marathi", "Kannada", "Tamil"], label_visibility="collapsed")
                with c_place:
                    local_place = st.text_input("Place", value=constituency, label_visibility="collapsed")

                # Fetch Local News
                loc_query = f"{local_place}"
                news_loc = fetch_news(query=loc_query, language=local_lang, limit=5)
                
                # SORTING LOGIC: Latest Date First
                if news_loc:
                    news_loc = sorted(news_loc, key=lambda x: x['published'], reverse=True)

                    for news in news_loc:
                        d_str = news['published'].strftime("%d %b | %H:%M")
                        st.markdown(f"""
                        <div class='news-item'>
                            <span class='news-date'>{d_str} | {news['source']}</span>
                            <a href='{news['link']}' target='_blank' style='text-decoration:none; color:#333;'>
                                {news['title']}
                            </a>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.caption(f"No updates for {local_place} in {local_lang}.")
            st.markdown("</div>", unsafe_allow_html=True)

        with r_col:
            st.markdown("<div class='widget-card'><div class='widget-title'>🗓️ Calendar & Notes</div>", unsafe_allow_html=True)
            sel_date = st.date_input("Planner", datetime.now(), label_visibility="collapsed")
            date_key = sel_date.strftime("%Y-%m-%d")
            current_note = st.session_state.calendar_notes.get(date_key, "")
            st.caption(f"Schedule for {sel_date.strftime('%d %B')}:")
            new_note = st.text_area("Note", value=current_note, height=180, label_visibility="collapsed", key="dash_note")
            
            if st.button("💾 Save Schedule", use_container_width=True):
                st.session_state.calendar_notes[date_key] = new_note
                st.toast("Schedule Updated!")
            st.markdown("</div>", unsafe_allow_html=True)

    # --- 8. MODULE ROUTING ---
    elif selected == "SansadX": render_sansadx(username)
    elif selected == "Co-Pilot": render_copilot(username)
    elif selected == "Drafter": render_drafter(username)
    elif selected == "PMB": render_pmb_drafter(username)
    elif selected == "CSR Suite":
        t1, t2 = st.tabs(["🗺️ State Intel", "💼 CSR Projects"])
        with t1: render_state_intel(username)
        with t2: render_csr_projects(username)
    elif selected == "Schemes": render_matcher(username)
    elif selected == "Archives":
        st.title("📂 Archives")
        docs = load_archives(username)
        if docs:
            for d in docs:
                with st.expander(f"📄 {d['title']}"): st.write(d['content'])
        else: st.info("No saved drafts found.")
    elif selected == "Settings": render_settings()