import extra_streamlit_components as stx
from datetime import datetime, timedelta
import streamlit as st
import importlib  # <--- CRITICAL FOR RELOAD
import requests
from streamlit_option_menu import option_menu
from datetime import datetime, timedelta
import os
import base64
import json
import time # <--- ADDED: Necessary for the wait delays
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# --- FORCE RELOAD MODULES ---
# This ensures Streamlit loads your latest fixes in sansadx.py immediately
import modules.sansadx 
importlib.reload(modules.sansadx)
from modules.sansadx import render_sansadx 
# ----------------------------

load_dotenv()

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
    # render_sansadx is already imported above
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

# --- 🔌 DATABASE CONNECTION (FIXED FOR POSTGRES) ---
@st.cache_resource
def get_db_engine():
    """Connects to Railway Postgres if available, else Local SQLite"""
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        # 🛠️ Fix for SQLAlchemy: Postgres requires 'postgresql://'
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        return create_engine(db_url)
    else:
        # 🟢 FIX: Point to your actual local backup file
        return create_engine("sqlite:///./sansadx.db")

def run_query(query_str, params=None):
    """Safe wrapper for database queries"""
    engine = get_db_engine()
    # Use 'with engine.connect()' for safe connection management
    with engine.connect() as conn:
        try:
            # text() is required for SQLAlchemy + Postgres
            result = conn.execute(text(query_str), params or {})
            
            # .mappings().all() returns a list of dictionaries (cleaner than tuples)
            if result.returns_rows:
                return result.mappings().all()
            return []
        except Exception as e:
            # Print error to logs so we can debug if it fails
            print(f"❌ DB Query Error: {e}")
            return []

# --- 🍪 COOKIE MANAGER SETUP (ADDED) ---
def get_manager():
    # ✅ Adding a key makes the component stable across refreshes
    return stx.CookieManager(key="needle_cookies")

cookie_manager = get_manager()

# --- BACKEND LOGIC ---
def attempt_login(username, password):
    """Authenticate directly against database"""
    # 1. Admin Override (Backdoor for demo)
    if username == "admin" and password == "password":
        return {"username": "admin", "role": "admin", "tenant_id": 1}, None

    # 2. Database Check
    # 🟢 FIX: Changed 'password' to 'password_hash' to match your DB schema
    query = "SELECT * FROM users WHERE username = :u AND password_hash = :p"
    users = run_query(query, {"u": username, "p": password})
    
    if users:
        user = users[0]
        return {
            "username": user['username'],
            "role": user.get('role', 'user'),
            "tenant_id": user.get('tenant_id', 1)
        }, None
    
    return None, "❌ Incorrect Username or Password"

# --- 🍪 COOKIE HELPER (ADDED) ---
def get_user_from_cookie(username):
    """Authenticate via Cookie (No Password Check)"""
    if username == "admin":
        return {"username": "admin", "role": "admin", "tenant_id": 1}
    
    query = "SELECT * FROM users WHERE username = :u"
    users = run_query(query, {"u": username})
    
    if users:
        user = users[0]
        return {
            "username": user['username'],
            "role": user.get('role', 'user'),
            "tenant_id": user.get('tenant_id', 1)
        }
    return None

def fetch_summary(tenant_id):
    """Calculate dashboard stats directly from DB for the Situation Room"""
    try:
        # We query the 'cases' table (Postgres)
        query = "SELECT category, case_metadata FROM cases WHERE tenant_id = :tid"
        rows = run_query(query, {"tid": tenant_id})
        
        category_breakdown = {}
        red_zones_raw = {}
        
        for row in rows:
            # Count Categories
            cat = row.get('category') or "Uncategorized"
            category_breakdown[cat] = category_breakdown.get(cat, 0) + 1
            
            # Count Red Zones
            ac = "Unknown"
            try:
                # Handle both String JSON and Dict JSON
                meta = row.get('case_metadata')
                if isinstance(meta, str):
                    meta = json.loads(meta)
                
                if isinstance(meta, dict):
                    ac = meta.get('assembly_constituency', 'Unknown')
            except:
                pass
            
            if ac and ac != "Unknown":
                red_zones_raw[ac] = red_zones_raw.get(ac, 0) + 1

        # Format Red Zones
        red_zones = [{"assembly_constituency": k, "count": v} for k, v in red_zones_raw.items() if v > 0]
        red_zones.sort(key=lambda x: x['count'], reverse=True)

        return {
            "category_breakdown": category_breakdown,
            "red_zones": red_zones
        }
    except Exception as e:
        print(f"❌ Fetch Summary Error: {e}")
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
                    # 1. Set Session State
                    st.session_state.authenticated = True
                    st.session_state.current_user = user_data["username"]
                    st.session_state.user_role = user_data["role"]
                    st.session_state.tenant_id = user_data["tenant_id"]
                    st.session_state.house_type = "LOK_SABHA" 
                    st.session_state.theme_color = "#009a4e"
                    
                    # 2. SAVE COOKIE
                    cookie_manager.set("needle_user", username, expires_at=datetime.now() + timedelta(days=30))
                    
                    # 3. CRITICAL WAIT: Give browser 1.5 seconds to actually save the cookie
                    st.success("Login successful! Redirecting...")
                    time.sleep(1.5)  # <--- INCREASED DELAY FOR SAFETY
                    
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

# ... (Keep all imports and setup code exactly the same) ...

# --- MAIN APP ---

# 🍪 AUTO-LOGIN VIA COOKIE (ROBUST VERSION)
# We check this every time the script runs. 
# If the browser has a cookie, we log them in automatically.
if not st.session_state.authenticated:
    # 1. Get cookie (use the specific key 'needle_user')
    cookie_user = cookie_manager.get(cookie="needle_user")
    
    # 2. CRITICAL FIX: Retry logic for race conditions
    # If cookie is None, the browser component might not be ready. Wait and try again.
    if cookie_user is None:
        time.sleep(0.5)
        cookie_user = cookie_manager.get(cookie="needle_user")

    # 3. If cookie exists (after retry), validate and login
    if cookie_user:
        user_data = get_user_from_cookie(cookie_user)
        if user_data:
            st.session_state.authenticated = True
            st.session_state.current_user = user_data["username"]
            st.session_state.user_role = user_data["role"]
            st.session_state.tenant_id = user_data["tenant_id"]
            st.session_state.house_type = "LOK_SABHA" 
            st.session_state.theme_color = "#009a4e"
            st.rerun()

if not st.session_state.authenticated:
    login_screen()
else:
    color = st.session_state.theme_color
    inject_custom_css(color)
    role = st.session_state.user_role
    username = st.session_state.current_user
    
    render_header(username, color)
    
    # --- 🛡️ ROLE-BASED MENU LOGIC ---
    # 1. Start with the FULL menu (What the MP sees)
    menu_options = ["Dashboard", "SansadX", "Co-Pilot", "Drafter", "PMB", "CSR Suite", "Schemes", "Archives", "Settings"]
    menu_icons = ["speedometer2", "whatsapp", "robot", "pen", "law", "buildings", "cash-coin", "archive", "gear"]
    
    # 2. FILTER: If user is NOT the MP or Admin, remove sensitive features
    # ✅ FIX: Added "mp" to this list so they see the full menu
    if role not in ["admin", "mp"]:
        # List of features to HIDE from Staff/PAs
        restricted_features = ["CSR Suite", "Schemes"]
        
        # Remove them from the menu
        for feature in restricted_features:
            if feature in menu_options:
                index = menu_options.index(feature)
                menu_options.pop(index)
                menu_icons.pop(index)

    with st.sidebar:
        st.caption(f"NAVIGATION ({role.upper()})") # Useful to see your role
        selected = option_menu(
            menu_title=None,
            options=menu_options, 
            icons=menu_icons, 
            default_index=0,
            styles={"nav-link-selected": {"background-color": color}}
        )
        st.divider()
        if st.button("🔒 Log Out"):
            # 🍪 DELETE COOKIE ON LOGOUT (ADDED)
            cookie_manager.delete("needle_user")
            st.session_state.authenticated = False
            st.rerun()
            
# ... (Rest of the routing logic remains the same) ...
    
    # --- 📊 DASHBOARD: COMMAND CENTER ---
    if selected == "Dashboard":
        
        # ✅ FETCH SUMMARY (Highlights Only)
        dashboard_data = fetch_summary(st.session_state.tenant_id)
        categories = dashboard_data.get("category_breakdown", {})
        red_zones = dashboard_data.get("red_zones", [])
        
        # Logic for Ticker
        if categories:
            top_category = max(categories, key=categories.get)
            ticker_msg = f"📢 Highest Volume: {top_category} ({categories[top_category]} reports)"
            sub_msg = f"Total Grievances: {sum(categories.values())}"
        else:
            ticker_msg = "📢 No critical issues reported yet."
            sub_msg = "System is active and listening."

        # Parse Red Zones Text
        if red_zones:
            top_3 = [rz['assembly_constituency'] for rz in red_zones[:3]]
            red_zone_text = f"📍 {len(red_zones)} Active Red Zones"
            red_zone_detail = ", ".join(top_3)
            if len(red_zones) > 3: red_zone_detail += "..."
        else:
            red_zone_text = "📍 No Red Zones"
            red_zone_detail = "All areas normal"

        # ZONE 1: THE SITUATION ROOM (Highlights)
        st.markdown(f"<div class='widget-card'><div class='widget-title'>🔥 Situation Room (Constituency Intel)</div>", unsafe_allow_html=True)
        
        col_tick, col_map = st.columns([2, 1])
        with col_tick:
            st.caption("BURNING ISSUES TICKER")
            st.markdown(f"""
            <div class='ticker-box'>{ticker_msg}</div>
            <div style='font-size:14px; color:#666;'>• {sub_msg}</div>
            """, unsafe_allow_html=True)
        with col_map:
            st.caption("RED ZONE ALERT")
            if red_zones:
                st.error(f"**{red_zone_text}**\n\n{red_zone_detail}")
            else:
                st.success(f"**{red_zone_text}**\n\n{red_zone_detail}")
                
        st.markdown("</div>", unsafe_allow_html=True)

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

            # --- ZONE 3: MEDIA CENTRE (LIVE) ---
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
            # ZONE 4: REMINDERS / CALENDAR
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