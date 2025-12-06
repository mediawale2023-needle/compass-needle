import streamlit as st
from streamlit_option_menu import option_menu
from datetime import datetime
import os

# --- MODULE IMPORTS ---
try:
    from modules.copilot import render_copilot
    from modules.drafter import render_drafter
    from modules.matcher import render_matcher
    from modules.admin import render_admin
    from modules.pmb_drafter import render_pmb_drafter
    # CSR Suite
    from modules.csr_discovery import render_csr_discovery
    from modules.csr_projects import render_csr_projects
    from modules.csr_partners import render_csr_partners
    from modules.state_intel import render_state_intel
    # Utils
    from modules.utils import track_action, show_download_button
    from modules.persistence import load_archives, delete_draft 
except ImportError as e:
    st.error(f"⚠️ Module Missing: {e}")
    st.stop()

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Needle | Sovereign OS",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- INITIALIZE STATE ---
if 'uploaded_file_data' not in st.session_state: st.session_state.uploaded_file_data = None
if 'uploaded_file_name' not in st.session_state: st.session_state.uploaded_file_name = ""
if 'action_log' not in st.session_state: st.session_state.action_log = [] 
if 'groq_api_key' not in st.session_state: st.session_state.groq_api_key = ""
if 'password_correct' not in st.session_state: st.session_state.password_correct = False
if 'global_lang' not in st.session_state: st.session_state.global_lang = "English"

# --- CSS ---
st.markdown("""
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<style>
    .stApp { background-color: #f8f9fa; }
    h1, h2, h3 { font-family: 'Helvetica Neue', sans-serif; color: #0f172a; }
    .profile-card { background: white; border: 1px solid #e0e0e0; padding: 15px; border-radius: 10px; text-align: center; margin-bottom: 20px; }
    .status-dot { color: #10b981; font-size: 0.8em; margin-top:5px;}
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# --- AUTH ---
def check_password():
    if not st.session_state.password_correct:
        try:
            st.session_state["username"] = "milind_deora"
            st.session_state["user_profile"] = st.secrets["profiles"]["milind_deora"]
            st.session_state["current_user"] = "milind_deora"
            st.session_state["password_correct"] = True
            return True
        except:
            # Fallback
            st.session_state["username"] = "milind_deora"
            st.session_state["user_profile"] = {
                "name": "Hon. Milind Deora",
                "constituency": "Maharashtra", 
                "tags": ["Urban", "Coastal"],
                "avatar": "https://ui-avatars.com/api/?name=Milind+Deora&background=002D62&color=fff"
            }
            st.session_state["current_user"] = "milind_deora"
            st.session_state["password_correct"] = True
            return True
    return True 

# --- EXECUTION ---
if check_password():
    username = st.session_state.get("current_user", "milind_deora")
    user = st.session_state["user_profile"]

    if username == "admin":
        render_admin()
    else:
        # SIDEBAR
        with st.sidebar:
            st.markdown(f"""
            <div class="profile-card">
                <img src="{user.get('avatar')}" style="border-radius: 50%;">
                <div style="font-weight:bold; margin-top:10px;">{user.get('name')}</div>
                <div style="font-size:0.9em; color:#666;">{user.get('constituency')}</div>
                <div class="status-dot">● Secure Server Active</div>
            </div>
            """, unsafe_allow_html=True)
            
            st.divider()
            input_key = st.text_input("Groq API Key", type="password", value=st.session_state.get('groq_api_key', ''), key='global_key')
            if input_key: st.session_state.groq_api_key = input_key
            
            st.divider()
            selected_lang = st.selectbox("Output Language", ["English", "Hindi (हिंदी)", "Marathi (मराठी)", "Tamil (தமிழ்)"], key="global_lang_select")
            st.session_state.global_lang = selected_lang

            st.divider()
            if st.button("🔒 Log Out"):
                st.session_state["password_correct"] = False
                st.rerun()

        # MENU
        selected = option_menu(
            menu_title=None,
            options=["Co-Pilot", "Drafter", "PMB", "CSR Suite", "Schemes", "Archives"],
            icons=["robot", "pen", "law", "buildings", "cash-coin", "archive"],
            default_index=0,
            orientation="horizontal"
        )
        
        # ROUTING
        if selected == "Co-Pilot":
            render_copilot(username)
        elif selected == "Drafter":
            render_drafter(username)
        elif selected == "PMB":
            render_pmb_drafter(username)
        elif selected == "CSR Suite":
            st.title("💰 Corporate Social Responsibility (CSR)")
            
            # 4 Sub-Tabs: State Intel is first now
            tab_state, tab_disc, tab_proj, tab_part = st.tabs([
                "🗺️ State Intel",  
                "🔭 Discovery", 
                "📋 Project Catalog", 
                "🤝 Partners"
            ])
            
            with tab_state:
                render_state_intel(username) # Shows ALL companies
            with tab_disc:
                render_csr_discovery(username)
            with tab_proj:
                render_csr_projects(username)
            with tab_part:
                render_csr_partners(username)
            
        elif selected == "Schemes":
            render_matcher(user_tags=user.get('tags', []))
            
        elif selected == "Archives":
            st.title("📂 User Archives")
            archives = load_archives(username)
            if not archives: st.info("No saved drafts.")
            else:
                for doc in archives:
                    with st.expander(f"📄 {doc['title']} ({doc['date']})"):
                        st.text_area("Content", doc['content'], height=200, disabled=True)
                        c1, c2 = st.columns([1, 4])
                        with c1:
                            if st.button("🗑️ Delete", key=f"del_{doc['id']}"): delete_draft(username, doc['id'])
                        with c2:
                            show_download_button(doc['content'], doc['title'])