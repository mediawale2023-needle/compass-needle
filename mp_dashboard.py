import extra_streamlit_components as stx
from datetime import datetime, timedelta
import streamlit as st
import importlib
import requests
from streamlit_option_menu import option_menu
import os
import base64
import json
import time
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# --- 1. PAGE CONFIG (MUST BE FIRST) ---
st.set_page_config(
    page_title="Needle | MP Dashboard",
    page_icon="🇮🇳",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. FORCE RELOAD MODULES ---
import modules.sansadx 
importlib.reload(modules.sansadx)
from modules.sansadx import render_sansadx 

load_dotenv()

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
    from modules.utils import track_action, show_download_button
    from modules.persistence import load_archives, delete_draft
    from modules.news_intel import fetch_news, analyze_sentiment
except ImportError as e:
    st.error(f"⚠️ System Boot Error: Missing Module. Details: {e}")
    st.stop()

# --- SESSION STATE SETUP ---
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'current_user' not in st.session_state: st.session_state.current_user = ""
if 'user_role' not in st.session_state: st.session_state.user_role = ""
if 'tenant_id' not in st.session_state: st.session_state.tenant_id = None
if 'house_type' not in st.session_state: st.session_state.house_type = "LOK_SABHA"
if 'theme_color' not in st.session_state: st.session_state.theme_color = "#009a4e"
if 'constituency' not in st.session_state: st.session_state.constituency = "India"
if 'logging_out' not in st.session_state: st.session_state.logging_out = False

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

# --- 🔌 DATABASE CONNECTION ---
@st.cache_resource
def get_db_engine():
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        return create_engine(db_url)
    else:
        return create_engine("sqlite:///./sansadx.db")

def run_query(query_str, params=None):
    engine = get_db_engine()
    with engine.connect() as conn:
        try:
            result = conn.execute(text(query_str), params or {})
            if result.returns_rows:
                return result.mappings().all()
            return []
        except Exception as e:
            print(f"❌ DB Query Error: {e}")
            return []

# --- 🍪 COOKIE MANAGER ---
def get_manager():
    return stx.CookieManager(key="needle_cookies")

cookie_manager = get_manager()

# --- BACKEND LOGIC ---
def attempt_login(username, password):
    if username == "admin" and password == "password":
        return {"username": "admin", "role": "admin", "tenant_id": 1, "constituency": "New Delhi"}, None

    query = "SELECT * FROM users WHERE username = :u AND password_hash = :p"
    users = run_query(query, {"u": username, "p": password})
    
    if users:
        user = users[0]
        return {
            "username": user['username'],
            "role": user.get('role', 'user'),
            "tenant_id": user.get('tenant_id', 1),
            "constituency": user.get('constituency') or "India"
        }, None
    
    return None, "❌ Incorrect Username or Password"

def get_user_from_cookie(username):
    if username == "admin":
        return {"username": "admin", "role": "admin", "tenant_id": 1, "constituency": "New Delhi"}
    
    query = "SELECT * FROM users WHERE username = :u"
    users = run_query(query, {"u": username})
    
    if users:
        user = users[0]
        return {
            "username": user['username'],
            "role": user.get('role', 'user'),
            "tenant_id": user.get('tenant_id', 1),
            "constituency": user.get('constituency') or "India"
        }
    return None

def fetch_summary(tenant_id):
    try:
        query = "SELECT category, case_metadata FROM cases WHERE tenant_id = :tid"
        rows = run_query(query, {"tid": tenant_id})
        
        category_breakdown = {}
        red_zones_raw = {}
        
        for row in rows:
            cat = row.get('category') or "Uncategorized"
            category_breakdown[cat] = category_breakdown.get(cat, 0) + 1
            
            ac = "Unknown"
            try:
                meta = row.get('case_metadata')
                if isinstance(meta, str): meta = json.loads(meta)
                if isinstance(meta, dict): ac = meta.get('assembly_constituency', 'Unknown')
            except: pass
            
            if ac and ac != "Unknown":
                red_zones_raw[ac] = red_zones_raw.get(ac, 0) + 1

        red_zones = [{"assembly_constituency": k, "count": v} for k, v in red_zones_raw.items() if v > 0]
        red_zones.sort(key=lambda x: x['count'], reverse=True)

        return {"category_breakdown": category_breakdown, "red_zones": red_zones}
    except Exception as e:
        return {"category_breakdown": {}, "red_zones": []}

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
                user_data, error_msg = attempt_login(username, password)
                if user_data:
                    st.session_state.authenticated = True
                    st.session_state.current_user = user_data["username"]
                    st.session_state.user_role = user_data["role"]
                    st.session_state.tenant_id = user_data["tenant_id"]
                    st.session_state.constituency = user_data["constituency"]
                    st.session_state.house_type = "LOK_SABHA"
                    st.session_state.theme_color = "#009a4e"
                    
                    st.session_state.logging_out = False 

                    cookie_manager.set("needle_user", username, expires_at=datetime.now() + timedelta(days=30))
                    
                    st.success("Login successful! Redirecting...")
                    time.sleep(1.5)
                    st.rerun()
                else:
                    st.error(error_msg)

# --- HEADER ---
def render_header(username, color):
    loc = st.session_state.get('constituency', 'India')
    st.markdown(f"""
    <div class="needle-header">
        <div class="needle-logo">
            <span>🪡</span> Needle
        </div>
        <div style="display: flex; gap: 20px; align-items: center; font-size: 14px; font-weight: 500;">
            <span style="color: #666;">📍 {loc}</span>
            <span style="color: {color};">● Online</span>
            <span>{username.title()}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

# --- MAIN APP ---
if not st.session_state.authenticated and not st.session_state.logging_out:
    cookie_user = cookie_manager.get(cookie="needle_user")
    if cookie_user is None:
        time.sleep(0.5)
        cookie_user = cookie_manager.get(cookie="needle_user")
    if cookie_user:
        user_data = get_user_from_cookie(cookie_user)
        if user_data:
            st.session_state.authenticated = True
            st.session_state.current_user = user_data["username"]
            st.session_state.user_role = user_data["role"]
            st.session_state.tenant_id = user_data["tenant_id"]
            st.session_state.constituency = user_data["constituency"]
            st.session_state.theme_color = "#009a4e"
            st.rerun()

if not st.session_state.authenticated:
    login_screen()
else:
    # --- AUTHENTICATED ZONE ---
    # The Auto-Refresh logic has been removed here to stop the infinite loop.
    
    color = st.session_state.theme_color
    inject_custom_css(color)
    role = st.session_state.user_role
    username = st.session_state.current_user
    
    render_header(username, color)
    
    menu_options = ["Dashboard", "SansadX", "Co-Pilot", "Drafter", "PMB", "CSR Suite", "Schemes", "Archives", "Settings"]
    menu_icons = ["speedometer2", "whatsapp", "robot", "pen", "law", "buildings", "cash-coin", "archive", "gear"]
    
    if role not in ["admin", "mp"]:
        restricted_features = ["CSR Suite", "Schemes"]
        for feature in restricted_features:
            if feature in menu_options:
                index = menu_options.index(feature)
                menu_options.pop(index)
                menu_icons.pop(index)

    with st.sidebar:
        st.caption(f"NAVIGATION ({role.upper()})")
        selected = option_menu(
            menu_title=None,
            options=menu_options, 
            icons=menu_icons, 
            default_index=0,
            styles={"nav-link-selected": {"background-color": color}}
        )
        st.divider()
        if st.button("🔒 Log Out"):
            cookie_manager.delete("needle_user")
            st.session_state.authenticated = False
            st.session_state.logging_out = True
            time.sleep(1)
            st.rerun()
            
    if selected == "Dashboard":
        dashboard_data = fetch_summary(st.session_state.tenant_id)
        categories = dashboard_data.get("category_breakdown", {})
        red_zones = dashboard_data.get("red_zones", [])
        
        if categories:
            top_category = max(categories, key=categories.get)
            ticker_msg = f"📢 Highest Volume: {top_category} ({categories[top_category]} reports)"
            sub_msg = f"Total Grievances: {sum(categories.values())}"
        else:
            ticker_msg = "📢 No critical issues reported yet."
            sub_msg = "System is active and listening."

        if red_zones:
            top_3 = [rz['assembly_constituency'] for rz in red_zones[:3]]
            red_zone_text = f"📍 {len(red_zones)} Active Red Zones"
            red_zone_detail = ", ".join(top_3)
            if len(red_zones) > 3: red_zone_detail += "..."
        else:
            red_zone_text = "📍 No Red Zones"
            red_zone_detail = "All areas normal"

        st.markdown(f"<div class='widget-card'><div class='widget-title'>🔥 Situation Room (Constituency Intel)</div>", unsafe_allow_html=True)
        col_tick, col_map = st.columns([2, 1])
        with col_tick:
            st.caption("BURNING ISSUES TICKER")
            st.markdown(f"<div class='ticker-box'>{ticker_msg}</div><div style='font-size:14px; color:#666;'>• {sub_msg}</div>", unsafe_allow_html=True)
        with col_map:
            st.caption("RED ZONE ALERT")
            if red_zones:
                st.error(f"**{red_zone_text}**\n\n{red_zone_detail}")
            else:
                st.success(f"**{red_zone_text}**\n\n{red_zone_detail}")
        st.markdown("</div>", unsafe_allow_html=True)

        c_left, c_right = st.columns([2, 1])
        with c_left:
            st.markdown(f"<div class='widget-card'><div class='widget-title'>🏛️ Parliamentary Desk</div>", unsafe_allow_html=True)
            st.info("📜 **Parliament is currently in Session**")
            st.markdown("**Today's Business:**\n1. Question Hour\n2. Legislative Business: Energy Amendment Bill")
            st.markdown("</div>", unsafe_allow_html=True)

            st.markdown(f"<div class='widget-card'><div class='widget-title'>📰 Media Centre (Live)</div>", unsafe_allow_html=True)
            tab_nat, tab_loc = st.tabs(["🇮🇳 National", "📍 Local Pulse"])
            
            with tab_nat:
                nat_query = f"{username} politics"
                news_nat = fetch_news(query=nat_query, language="English", limit=5)
                if news_nat:
                    for news in news_nat:
                        sent = analyze_sentiment(news['title'])
                        d_str = news['published'].strftime("%d %b")
                        st.markdown(f"<div class='news-item'><span class='news-date'>{d_str} | {news['source']}</span><a href='{news['link']}' target='_blank' style='text-decoration:none; color:#333;'>{news['title']}</a><span style='float:right; font-size:10px;'>{sent}</span></div>", unsafe_allow_html=True)
                else:
                    st.caption("No national updates.")

            with tab_loc:
                c_lang, c_place = st.columns([1, 1])
                with c_lang:
                    local_lang = st.selectbox("Language", ["English", "Hindi", "Marathi", "Kannada", "Tamil"], label_visibility="collapsed")
                with c_place:
                    my_loc = st.session_state.get('constituency', 'India')
                    local_place = st.text_input("Place", value=my_loc, label_visibility="collapsed", key=f"loc_pulse_{username}")

                loc_query = f"{local_place} news"
                news_loc = fetch_news(query=loc_query, language=local_lang, limit=5)
                if news_loc:
                    for news in news_loc:
                        d_str = news['published'].strftime("%d %b")
                        st.markdown(f"<div class='news-item'><span class='news-date'>{d_str} | {news['source']}</span><a href='{news['link']}' target='_blank' style='text-decoration:none; color:#333;'>{news['title']}</a></div>", unsafe_allow_html=True)
                else:
                    st.caption(f"No updates for {local_place}.")
            st.markdown("</div>", unsafe_allow_html=True)

        with c_right:
            st.markdown(f"<div class='widget-card'><div class='widget-title'>🗓️ Calendar & Notes</div>", unsafe_allow_html=True)
            sel_date = st.date_input("Date", datetime.now(), label_visibility="collapsed")
            d_key = sel_date.strftime("%Y-%m-%d")
            if 'calendar_notes' not in st.session_state: st.session_state.calendar_notes = {}
            c_note = st.session_state.calendar_notes.get(d_key, "")
            st.caption(f"Notes for {sel_date.strftime('%d %b')}:")
            n_note = st.text_area("Note", c_note, height=150, label_visibility="collapsed")
            if st.button("💾 Save Note", use_container_width=True):
                st.session_state.calendar_notes[d_key] = n_note
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

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
        st.title("📂 Archives")
        archives = load_archives(username)
        for doc in archives:
            with st.expander(doc['title']):
                st.write(doc['content'])
                if st.button("Delete", key=f"d_{doc['id']}"):
                    delete_draft(username, doc['id'])
                    st.rerun()
    elif selected == "Settings": render_settings()