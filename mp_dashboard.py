import streamlit as st
import requests
from streamlit_option_menu import option_menu
from datetime import datetime, timedelta
import os
import base64

# --- API CONFIG ---
API_URL = "http://127.0.0.1:8000"

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Needle | MP Dashboard",
    page_icon="🇮🇳",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- MODULE IMPORTS ---
try:
    from modules.settings import render_settings
    from modules.copilot import render_copilot
    from modules.drafter import render_drafter
    from modules.matcher import render_matcher
    from modules.pmb_drafter import render_pmb_drafter
    from modules.csr_projects import render_csr_projects
    from modules.csr_partners import render_csr_partners
    from modules.state_intel import render_state_intel
    from modules.sansadx import render_sansadx
    from modules.utils import track_action, show_download_button
    from modules.persistence import load_archives, delete_draft
    from modules.news_intel import fetch_news, analyze_sentiment
except ImportError as e:
    st.error(f"⚠️ System Boot Error: Missing Module. Details: {e}")
    st.stop()

# --- SESSION STATE SETUP (SECURE LOGIN RESTORED) ---
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'current_user' not in st.session_state: st.session_state.current_user = ""
if 'user_role' not in st.session_state: st.session_state.user_role = ""
if 'tenant_id' not in st.session_state: st.session_state.tenant_id = None
if 'house_type' not in st.session_state: st.session_state.house_type = "LOK_SABHA"
if 'theme_color' not in st.session_state: st.session_state.theme_color = "#009a4e"

# Calendar Notes State
if 'calendar_notes' not in st.session_state:
    st.session_state.calendar_notes = {
        datetime.now().strftime("%Y-%m-%d"): "Meeting with Party President at 4 PM."
    }

# --- 🎨 THEME ENGINE ---
def inject_custom_css(color_hex):
    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
        
        html, body, [class*="css"] {{
            font-family: 'Inter', sans-serif;
            color: #333;
        }}
        .needle-header {{
            background: white;
            padding: 1rem 1.5rem;
            border-bottom: 1px solid #e0e0e0;
            margin-bottom: 2rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        .needle-logo {{
            font-size: 26px;
            font-weight: 800;
            color: {color_hex};
            display: flex;
            align-items: center;
            gap: 10px;
            letter-spacing: -0.5px;
        }}
        .widget-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            border: 1px solid #eee;
            box-shadow: 0 2px 8px rgba(0,0,0,0.04);
            margin-bottom: 20px;
            height: 100%;
        }}
        .widget-title {{
            font-size: 14px;
            font-weight: 700;
            color: #666;
            margin-bottom: 15px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 2px solid {color_hex};
            padding-bottom: 5px;
            display: inline-block;
        }}
        .ticker-box {{
            background-color: #fff3cd; 
            color: #856404; 
            padding: 10px; 
            border-radius: 4px; 
            border-left: 5px solid #ffc107;
            font-weight: 500;
            margin-bottom: 10px;
        }}
        .news-item {{
            padding: 10px 0;
            border-bottom: 1px solid #f0f0f0;
            font-size: 14px;
        }}
        .news-date {{ font-size: 11px; color: #999; margin-bottom: 2px; display: block; }}
        .news-tag-pos {{ color: #28a745; font-size: 10px; font-weight: 700; background: #e6f4ea; padding: 2px 6px; border-radius: 4px; }}
        .news-tag-neg {{ color: #dc3545; font-size: 10px; font-weight: 700; background: #fde8e8; padding: 2px 6px; border-radius: 4px; }}
        .news-tag-neu {{ color: #666; font-size: 10px; font-weight: 700; background: #f0f0f0; padding: 2px 6px; border-radius: 4px; }}
        section[data-testid="stSidebar"] {{ background-color: #f8f9fa; border-right: 1px solid #e0e0e0; }}
        .stButton > button {{ background-color: {color_hex}; color: white; border: none; font-weight: 600; }}
        .stButton > button:hover {{ background-color: #333; color: white; }}
    </style>
    """, unsafe_allow_html=True)

# --- BACKEND CONNECTORS ---
def get_tenant_config():
    try:
        response = requests.get(f"{API_URL}/tenant/config")
        if response.status_code == 200: return response.json()
        return {}
    except: return {}

def attempt_login(username, password):
    try:
        payload = {"username": username, "password": password}
        response = requests.post(f"{API_URL}/auth/login", json=payload)
        if response.status_code == 200: return response.json(), None
        elif response.status_code == 401: return None, "❌ Incorrect Username or Password"
        else: return None, f"⚠️ Server Error ({response.status_code})"
    except: return None, "🚫 Cannot connect to Backend."

# ✅ Function to fetch dashboard stats
def fetch_summary(tenant_id):
    try:
        resp = requests.get(f"{API_URL}/dashboard/summary", params={"tenant_id": tenant_id})
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"Fetch Error: {e}")
    return {}

# --- LOGIN SCREEN ---
def login_screen():
    st.markdown("""
    <div style='text-align: center; margin-top: 50px;'>
        <h1 style='font-family:Inter; font-weight:800; letter-spacing:-1px;'>Needle</h1>
        <p style='color: #666;'>Secure Access Portal for Members of Parliament</p>
    </div>
    """, unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1, 1])
    with c2:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Log In", type="primary", use_container_width=True)
            if submit:
                # Bypass login for admin (optional, keep if needed for testing)
                if username == "admin" and password == "password":
                    st.session_state.authenticated = True
                    st.session_state.current_user = "admin"
                    st.session_state.user_role = "admin"
                    st.session_state.theme_color = "#009a4e"
                    st.rerun()
               
                user_data, error_msg = attempt_login(username, password)
                if user_data:
                    st.session_state.authenticated = True
                    st.session_state.current_user = user_data["username"]
                    st.session_state.user_role = user_data["role"]
                    st.session_state.tenant_id = user_data["tenant_id"]
                    config = get_tenant_config()
                    h_type = config.get("type", "LOK_SABHA")
                    st.session_state.house_type = h_type
                    st.session_state.theme_color = "#800000" if h_type == "RAJYA_SABHA" else "#009a4e"
                    st.rerun()
                else:
                    st.error(error_msg)

# --- HEADER ---
def render_header(username, color):
    st.markdown(f"""
    <div class="needle-header">
        <div class="needle-logo">
            <span>🪡</span> Needle
        </div>
        <div style="display: flex; gap: 20px; align-items: center; font-size: 14px; font-weight: 500;">
            <span style="color: {color};">● Online</span>
            <span>{username.title()}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

# --- MAIN APP ---
if not st.session_state.authenticated:
    login_screen()
else:
    color = st.session_state.theme_color
    inject_custom_css(color)
    role = st.session_state.user_role
    username = st.session_state.current_user
    
    render_header(username, color)
    
    with st.sidebar:
        st.caption("NAVIGATION")
        selected = option_menu(
            menu_title=None,
            options=["Dashboard", "SansadX", "Co-Pilot", "Drafter", "PMB", "CSR Suite", "Schemes", "Archives", "Settings"], 
            icons=["speedometer2", "whatsapp", "robot", "pen", "law", "buildings", "cash-coin", "archive", "gear"], 
            default_index=0,
            styles={"nav-link-selected": {"background-color": color}}
        )
        st.divider()
        if st.button("🔒 Log Out"):
            st.session_state.authenticated = False
            st.rerun()

    # --- 📊 DASHBOARD: COMMAND CENTER ---
    if selected == "Dashboard":
        
        # ✅ FETCH REAL DATA
        dashboard_data = fetch_summary(st.session_state.tenant_id)
        
        # Parse Breakdown
        categories = dashboard_data.get("category_breakdown", {})
        red_zones = dashboard_data.get("red_zones", [])
        
        # Logic for Ticker
        if categories:
            top_category = max(categories, key=categories.get)
            ticker_msg = f"📢 Highest Volume: {top_category} ({categories[top_category]} reports)"
            sub_msg = f"Total Grievances (24h): {sum(categories.values())}"
        else:
            ticker_msg = "📢 No critical issues reported yet."
            sub_msg = "System is active and listening."

        # Parse Red Zones Text
        if red_zones:
            red_zone_text = f"📍 {len(red_zones)} Red Zones Detected"
            red_zone_detail = ", ".join([rz['assembly_constituency'] for rz in red_zones])
            red_zone_class = "st.error"
        else:
            red_zone_text = "📍 No Red Zones"
            red_zone_detail = "All areas normal"
            red_zone_class = "st.success"

        # ZONE 1: THE SITUATION ROOM
        st.markdown(f"<div class='widget-card'><div class='widget-title'>🔥 Situation Room (Constituency Intel)</div>", unsafe_allow_html=True)
        
        col_tick, col_map = st.columns([2, 1])
        with col_tick:
            st.caption("BURNING ISSUES TICKER")
            st.markdown(f"""
            <div class='ticker-box'>{ticker_msg}</div>
            <div style='font-size:14px; color:#666;'>• {sub_msg}</div>
            """, unsafe_allow_html=True)
        with col_map:
            st.caption("CRISIS MAP")
            if red_zones:
                st.error(f"{red_zone_text}\n\n({red_zone_detail})")
            else:
                st.success(red_zone_text)
                
        st.markdown("</div>", unsafe_allow_html=True)

        # ZONE 2 & 4 (Left Column) | ZONE 3 (Right Column)
        c_left, c_right = st.columns([2, 1])

        with c_left:
            # ZONE 2: PARLIAMENTARY DESK
            st.markdown(f"<div class='widget-card'><div class='widget-title'>🏛️ Parliamentary Desk</div>", unsafe_allow_html=True)
            
            session_active = True 
            if session_active:
                st.info("📜 **Parliament is currently in Session**")
                st.markdown("""
                **Today's Business:**
                1. **Question Hour:** Ministries of Commerce, Agriculture, and Textiles.
                2. **Legislative Business:** Discussion on Energy Amendment Bill, 2025.
                """)
            else:
                st.warning("🏛️ **Parliament is currently NOT in Session**")
            
            st.markdown("</div>", unsafe_allow_html=True)

            # --- ZONE 4: MEDIA CENTRE (LIVE) ---
            st.markdown(f"<div class='widget-card'><div class='widget-title'>📰 Media Centre (Live)</div>", unsafe_allow_html=True)
            
            # Create Tabs for National vs Local
            tab_nat, tab_loc = st.tabs(["🇮🇳 National", "📍 Local Pulse"])
            
            # --- TAB 1: NATIONAL NEWS (English) ---
            with tab_nat:
                nat_query = f"{username} politics"
                news_nat = fetch_news(query=nat_query, language="English", limit=5)
                
                if news_nat:
                    for news in news_nat:
                        sent = analyze_sentiment(news['title'])
                        d_str = news['published'].strftime("%d %b")
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

            # --- TAB 2: LOCAL PULSE (Vernacular) ---
            with tab_loc:
                c_lang, c_place = st.columns([1, 1])
                with c_lang:
                    local_lang = st.selectbox("Language", ["English", "Hindi", "Marathi", "Kannada", "Tamil"], label_visibility="collapsed")
                with c_place:
                    local_place = st.text_input("Place", value="Belagavi", label_visibility="collapsed")

                # Fetch Local News
                loc_query = f"{local_place}"
                news_loc = fetch_news(query=loc_query, language=local_lang, limit=5)
                
                if news_loc:
                    for news in news_loc:
                        d_str = news['published'].strftime("%d %b")
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

        with c_right:
            # ZONE 3: REMINDERS / CALENDAR
            st.markdown(f"<div class='widget-card'><div class='widget-title'>🗓️ Calendar & Notes</div>", unsafe_allow_html=True)
            
            selected_date = st.date_input("Select Date", datetime.now(), label_visibility="collapsed")
            date_key = selected_date.strftime("%Y-%m-%d")
            
            # Retrieve or Init notes
            if 'calendar_notes' not in st.session_state: st.session_state.calendar_notes = {}
            current_note = st.session_state.calendar_notes.get(date_key, "")
            
            st.caption(f"Notes for {selected_date.strftime('%d %B %Y')}:")
            new_note = st.text_area("Notes", value=current_note, height=150, label_visibility="collapsed", key="note_area")
            
            if st.button("💾 Save Note", use_container_width=True):
                st.session_state.calendar_notes[date_key] = new_note
                st.toast("Note saved!")
                st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)

    # --- 🛠️ MODULE LOADING ---
    elif selected == "SansadX": render_sansadx(username)
    elif selected == "Co-Pilot": render_copilot(username)
    elif selected == "Drafter": render_drafter(username)
    elif selected == "PMB": render_pmb_drafter(username)
    elif selected == "CSR Suite":
        st.title("💰 Corporate Social Responsibility (CSR)")
        t1, t2, t3 = st.tabs(["🗺️ State Intel", "📋 Project Catalog", "🤝 Partners"])
        with t1: render_state_intel(username)
        with t2: render_csr_projects(username)
        with t3: render_csr_partners(username)
    
    elif selected == "Schemes": render_matcher(username)
    
    elif selected == "Archives":
        st.title("📂 User Archives")
        archives = load_archives(username)
        if not archives: st.info("No saved drafts.")
        else:
            for doc in archives:
                with st.expander(f"📄 {doc['title']}"):
                    st.text_area("Content", doc['content'], height=200)
                    if st.button("Delete", key=f"del_{doc['id']}"): 
                        delete_draft(username, doc['id'])
                        st.rerun()

    # --- ⚙️ SETTINGS ---
    elif selected == "Settings":
        render_settings()