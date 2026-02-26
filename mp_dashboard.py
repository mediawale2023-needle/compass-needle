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
import bcrypt
from itsdangerous import URLSafeSerializer
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# --- 1. PAGE CONFIG (MUST BE FIRST) ---
st.set_page_config(
    page_title="Needle | MP Dashboard",
    page_icon="",
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
    from modules.csr_insights import render_csr_insights
    from modules.csr_proposals import render_csr_proposals
    from modules.csr_pipeline import get_csr_candidates
    from modules.utils import track_action, show_download_button
    from modules.persistence import load_archives, delete_draft
    from modules.news_intel import fetch_news, analyze_sentiment, fetch_constituency_news, fetch_categorized_news
except ImportError as e:
    st.error(f" System Boot Error: Missing Module. Details: {e}")
    st.stop()

# --- SESSION STATE SETUP ---
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'current_user' not in st.session_state: st.session_state.current_user = ""
if 'display_name' not in st.session_state: st.session_state.display_name = ""
if 'user_role' not in st.session_state: st.session_state.user_role = ""
if 'tenant_id' not in st.session_state: st.session_state.tenant_id = None
if 'house_type' not in st.session_state: st.session_state.house_type = "Lok Sabha"
if 'theme_color' not in st.session_state: st.session_state.theme_color = "#006a4d"
if 'constituency' not in st.session_state: st.session_state.constituency = "India"
if 'logging_out' not in st.session_state: st.session_state.logging_out = False
if 'logout_confirmed' not in st.session_state: st.session_state.logout_confirmed = False

# Calendar Notes State
if 'calendar_notes' not in st.session_state:
    st.session_state.calendar_notes = {
        datetime.now().strftime("%Y-%m-%d"): "Meeting with Party President at 4 PM."
    }

# --- THEME ENGINE ---
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

# --- DATABASE CONNECTION ---
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
            print(f" DB Query Error: {e}")
            return []

# --- COOKIE MANAGER ---
def get_manager():
    return stx.CookieManager(key="needle_cookies_v2")

cookie_manager = get_manager()

# --- COOKIE SIGNING ---
_cookie_secret = os.getenv("COOKIE_SECRET")
if not _cookie_secret:
    import logging as _logging
    _logging.warning("COOKIE_SECRET env var not set — using a random per-process secret. Sessions will NOT survive server restarts.")
    _cookie_secret = os.urandom(32).hex()
_cookie_signer = URLSafeSerializer(_cookie_secret)

def sign_cookie(username: str) -> str:
    """Sign a username for secure cookie storage."""
    return _cookie_signer.dumps(username)

def unsign_cookie(signed_value: str):
    """Verify and extract username from signed cookie. Returns None if invalid."""
    try:
        return _cookie_signer.loads(signed_value)
    except Exception:
        return None

# --- LOGOUT HELPER ---
def perform_logout():
    """Robust logout: Clears session state and deletes cookie."""
    keys_to_clear = [
        'authenticated', 'current_user', 'display_name', 'user_role', 'tenant_id',
        'house_type', 'theme_color', 'constituency', 'calendar_notes'
    ]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    
    st.session_state.logging_out = True
    st.session_state.logout_confirmed = True
    
    try:
        cookie_manager.delete("needle_user")
    except Exception as e:
        print(f"Cookie delete warning: {e}")
    return True

# --- BACKEND LOGIC ---
# --- HOUSE → THEME MAPPING ---
HOUSE_THEMES = {
    "Lok Sabha": "#006a4d",
    "Rajya Sabha": "#8d153a",
}

def attempt_login(username, password):
    query = "SELECT * FROM users WHERE username = :u"
    users = run_query(query, {"u": username})
    
    if users:
        user = users[0]
        stored_hash = user.get('password_hash', '')
        password_valid = False
        
        # Try bcrypt first
        try:
            if stored_hash.startswith('$2b$') or stored_hash.startswith('$2a$'):
                password_valid = bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))
        except Exception:
            pass
        
        # Fallback: legacy plaintext match
        if not password_valid:
            password_valid = (stored_hash == password)
        
        if password_valid:
            # Auto-rehash legacy passwords to bcrypt
            if not (stored_hash.startswith('$2b$') or stored_hash.startswith('$2a$')):
                try:
                    new_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                    engine = get_db_engine()
                    with engine.begin() as conn:
                        conn.execute(text("UPDATE users SET password_hash = :h WHERE username = :u"), {"h": new_hash, "u": username})
                except Exception:
                    pass
            
            house = user.get('house') or "Lok Sabha"
            return {
                "username": user['username'],
                "display_name": user.get('display_name') or user['username'].title(),
                "role": user.get('role', 'user'),
                "tenant_id": user.get('tenant_id', 1),
                "constituency": user.get('constituency') or "India",
                "house": house,
                "theme_color": HOUSE_THEMES.get(house, "#006a4d"),
            }, None
    
    return None, " Incorrect Username or Password"

def get_user_from_cookie(username):
    query = "SELECT * FROM users WHERE username = :u"
    users = run_query(query, {"u": username})
    
    if users:
        user = users[0]
        house = user.get('house') or "Lok Sabha"
        return {
            "username": user['username'],
            "display_name": user.get('display_name') or user['username'].title(),
            "role": user.get('role', 'user'),
            "tenant_id": user.get('tenant_id', 1),
            "constituency": user.get('constituency') or "India",
            "house": house,
            "theme_color": HOUSE_THEMES.get(house, "#006a4d"),
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
                if isinstance(meta, str): 
                    meta = json.loads(meta)
                if isinstance(meta, dict): 
                    ac = meta.get('assembly_constituency', 'Unknown')
            except: 
                pass
            
            if ac and ac != "Unknown":
                red_zones_raw[ac] = red_zones_raw.get(ac, 0) + 1

        red_zones = [{"assembly_constituency": k, "count": v} for k, v in red_zones_raw.items() if v > 0]
        red_zones.sort(key=lambda x: x['count'], reverse=True)

        return {"category_breakdown": category_breakdown, "red_zones": red_zones}
    except Exception as e:
        print(f" Summary Fetch Error: {e}")
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
                    st.session_state.logging_out = False
                    st.session_state.logout_confirmed = False
                    st.session_state.authenticated = True
                    st.session_state.current_user = user_data["username"]
                    st.session_state.display_name = user_data["display_name"]
                    st.session_state.user_role = user_data["role"]
                    st.session_state.tenant_id = user_data["tenant_id"]
                    st.session_state.constituency = user_data["constituency"]
                    st.session_state.house_type = user_data["house"]
                    st.session_state.theme_color = user_data["theme_color"]

                    cookie_manager.set("needle_user", sign_cookie(username), expires_at=datetime.now() + timedelta(days=30))
                    
                    st.success("Login successful! Redirecting...")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(error_msg)

# --- HEADER ---
def render_header(username, color):
    loc = st.session_state.get('constituency', 'India')
    name = st.session_state.get('display_name') or username.title()
    house = st.session_state.get('house_type', 'Lok Sabha')
    st.markdown(f"""
    <div class="needle-header">
        <div class="needle-logo">
            <span></span> Needle
        </div>
        <div style="display: flex; gap: 20px; align-items: center; font-size: 14px; font-weight: 500;">
            <span style="color: #666;">{house} · {loc}</span>
            <span style="color: {color};">● Online</span>
            <span>{name}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

# --- MAIN APP ---
if st.session_state.get('logout_confirmed', False):
    # Force-clear the cookie from browser via JS (belt-and-suspenders)
    st.markdown(
        "<script>document.cookie='needle_user=; Max-Age=0; path=/;';</script>",
        unsafe_allow_html=True,
    )
    try:
        cookie_manager.delete("needle_user")
    except:
        pass
    st.session_state.logout_confirmed = False
    st.session_state.logging_out = True   # Keep True to block cookie auto-login on next rerun
    st.session_state.authenticated = False
    login_screen()
    st.stop()

if not st.session_state.get('authenticated', False):
    # Skip cookie auto-login if we just logged out
    if st.session_state.get('logging_out', False):
        st.session_state.logging_out = False
        login_screen()
        st.stop()

    cookie_token = cookie_manager.get(cookie="needle_user")
    if cookie_token is None:
        time.sleep(0.5)
        cookie_token = cookie_manager.get(cookie="needle_user")
    if cookie_token:
        cookie_user = unsign_cookie(cookie_token)
        if cookie_user:
            user_data = get_user_from_cookie(cookie_user)
            if user_data:
                st.session_state.authenticated = True
                st.session_state.current_user = user_data["username"]
                st.session_state.display_name = user_data["display_name"]
                st.session_state.user_role = user_data["role"]
                st.session_state.tenant_id = user_data["tenant_id"]
                st.session_state.constituency = user_data["constituency"]
                st.session_state.house_type = user_data["house"]
                st.session_state.theme_color = user_data["theme_color"]
                st.rerun()

if not st.session_state.authenticated:
    login_screen()
else:
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
            menu_title=None, options=menu_options, icons=menu_icons, 
            default_index=0, styles={"nav-link-selected": {"background-color": color}}
        )
        st.divider()
        if st.button("Log Out", use_container_width=True):
            perform_logout()
            st.rerun()
            
    if selected == "Dashboard":
        dashboard_data = fetch_summary(st.session_state.tenant_id)
        categories = dashboard_data.get("category_breakdown", {})
        red_zones = dashboard_data.get("red_zones", [])
        
        if categories:
            top_category = max(categories, key=categories.get)
            ticker_msg = f"Highest Volume: {top_category} ({categories[top_category]} reports)"
            sub_msg = f"Total Grievances: {sum(categories.values())}"
        else:
            ticker_msg = "No critical issues reported yet."
            sub_msg = "System is active and listening."

        st.markdown(f"<div class='widget-card'><div class='widget-title'>Situation Room (Constituency Intel)</div>", unsafe_allow_html=True)
        col_tick, col_map = st.columns([2, 1])
        with col_tick:
            st.caption("BURNING ISSUES TICKER")
            st.markdown(f"<div class='ticker-box'>{ticker_msg}</div><div style='font-size:14px; color:#666;'>• {sub_msg}</div>", unsafe_allow_html=True)
        with col_map:
            st.caption("RED ZONE ALERT")
            if red_zones:
                st.error(f"{len(red_zones)} Active Red Zones")
            else:
                st.success(f"All areas normal")
        st.markdown("</div>", unsafe_allow_html=True)

        # --- CSR Funding Indicator ---
        try:
            csr_candidates = get_csr_candidates(st.session_state.tenant_id)
            if csr_candidates:
                st.markdown(f"<div class='widget-card'><div class='widget-title'>CSR Funding Pipeline</div>", unsafe_allow_html=True)
                st.warning(f"**{len(csr_candidates)} issue(s)** have crossed the 200-complaint threshold and qualify for CSR-funded intervention.")
                st.caption("Go to **CSR Suite → Proposals** to generate data-backed pitches.")
                st.markdown("</div>", unsafe_allow_html=True)
        except Exception:
            pass # Pipeline not yet populated

        c_left, c_right = st.columns([2, 1])
        with c_left:
            st.markdown(f"<div class='widget-card'><div class='widget-title'>Parliamentary Desk</div>", unsafe_allow_html=True)
            st.info(" **Parliament is currently in Session**")
            st.markdown("</div>", unsafe_allow_html=True)

            st.markdown(f"<div class='widget-card'><div class='widget-title'>Media Centre</div>", unsafe_allow_html=True)
            tab_nat, tab_loc = st.tabs(["National", "Local Pulse"])

            # Load MP profile for name-based queries
            try:
                import json as _json
                with open("tenant_profile.json", "r") as _f:
                    _prof = _json.load(_f)
                mp_display_name = _prof.get("mp_name", username)
                mp_constituency = _prof.get("constituency", "")
            except Exception:
                mp_display_name = username
                mp_constituency = ""

            with tab_nat:
                st.caption(f"**{mp_display_name}** in national media")
                news_nat = fetch_news(query=f'"{mp_display_name}"', limit=8)
                if news_nat:
                    for news in news_nat:
                        sent = analyze_sentiment(news['title'])
                        badge = '' if sent == 'pos' else '' if sent == 'neg' else ''
                        st.markdown(f"<div class='news-item'>{badge} <a href='{news['link']}'>{news['title']}</a></div>", unsafe_allow_html=True)
                else:
                    st.caption("No national coverage found today.")

            with tab_loc:
                st.caption(f" Local newspapers & regional media about **{mp_display_name}** and **{mp_constituency}**")
                local_news = fetch_constituency_news(limit=8)
                if local_news:
                    for news in local_news:
                        sent = news.get('sentiment', 'neu')
                        badge = '' if sent == 'pos' else '' if sent == 'neg' else ''
                        pub = news.get('published')
                        date_str = pub.strftime('%d %b') if hasattr(pub, 'strftime') else ''
                        source = news.get('source', '')
                        meta = f" <span style='font-size:11px;color:#888;'>{date_str} · {source}</span>" if date_str else ""
                        st.markdown(f"<div class='news-item'>{badge} <a href='{news['link']}'>{news['title']}</a>{meta}</div>", unsafe_allow_html=True)
                else:
                    st.caption("No local coverage found today.")

            st.markdown("</div>", unsafe_allow_html=True)

        with c_right:
            st.markdown(f"<div class='widget-card'><div class='widget-title'>Calendar & Notes</div>", unsafe_allow_html=True)
            sel_date = st.date_input("Date", datetime.now(), label_visibility="collapsed")
            if st.button(" Save Note", use_container_width=True):
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    elif selected == "SansadX": render_sansadx(username)
    elif selected == "Co-Pilot": render_copilot(username)
    elif selected == "Drafter": render_drafter(username)
    elif selected == "PMB": render_pmb_drafter(username)
    elif selected == "CSR Suite":
        t1, t2, t3, t4 = st.tabs(["Insights", "Proposals", "Projects", "Partners"])
        with t1: render_csr_insights(username)
        with t2: render_csr_proposals(username)
        with t3: render_csr_projects(username)
        with t4: render_csr_partners(username)
    elif selected == "Schemes": render_matcher(username)
    elif selected == "Archives":
        archives = load_archives(username)
        for doc in archives:
            with st.expander(doc['title']):
                st.write(doc['content'])
                if st.button("Delete", key=f"d_{doc['id']}"):
                    delete_draft(username, doc['id'])
                    st.rerun()
    elif selected == "Settings": render_settings()