import streamlit as st
from streamlit_option_menu import option_menu
from datetime import datetime

# --- MODULE IMPORTS ---
try:
    from modules.copilot import render_copilot
    from modules.drafter import render_drafter
    from modules.matcher import render_matcher
    from modules.admin import render_admin
    from modules.pmb_drafter import render_pmb_drafter
    from modules.utils import track_action, show_download_button
    from modules.persistence import load_archives, delete_draft 
except ImportError as e:
    st.error(f"Module Import Error: {e}. Please ensure all files are correctly placed in the 'modules/' folder.")
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

# --- CUSTOM CSS ---
st.markdown("""
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<style>
    .stApp { background-color: #f8f9fa; }
    h1, h2, h3 { font-family: 'Helvetica Neue', sans-serif; color: #0f172a; }
    .profile-card {
        background-color: white; border: 1px solid #e0e0e0;
        padding: 15px; border-radius: 10px; text-align: center; margin-bottom: 20px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .status-dot { color: #10b981; font-size: 0.8em; margin-top:5px;}
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# --- AUTH BYPASS FOR DEV ---
def check_password():
    if not st.session_state.password_correct:
        try:
            st.session_state["username"] = "milind_deora"
            st.session_state["user_profile"] = st.secrets["profiles"]["milind_deora"]
            st.session_state["current_user"] = "milind_deora"
            st.session_state["password_correct"] = True
            return True
        except:
            st.error("Login bypass failed: Check secrets.toml.")
            return False
    return True 

# --- MAIN EXECUTION ---
if check_password():
    username = st.session_state.get("current_user", "milind_deora")
    user = st.session_state["user_profile"]

    if username == "admin":
        render_admin()
    else:
        # === SIDEBAR (GLOBAL CONTROLS) ===
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
            st.header("🔐 Access")
            
            # API Key Input
            input_key = st.text_input(
                "API Key", type="password", 
                value=st.session_state.get('groq_api_key', ''), 
                key='global_groq_key_input', placeholder="gsk_..."
            )
            if input_key: st.session_state.groq_api_key = input_key
            
            st.divider()
            st.header("🗣️ Language")
            
            # --- GLOBAL LANGUAGE SELECTOR (THE FIX) ---
            # This saves the language to session_state so ALL modules can see it
            selected_lang = st.selectbox(
                "Output Language", 
                ["English", "Hindi (हिंदी)", "Marathi (मराठी)", "Tamil (தமிழ்)"],
                key="global_lang_select",
                index=["English", "Hindi (हिंदी)", "Marathi (मराठी)", "Tamil (தமிழ்)"].index(st.session_state.get("global_lang", "English"))
            )
            st.session_state.global_lang = selected_lang

            st.divider()
            
            # History Log
            st.subheader("🕒 History")
            if st.session_state.action_log:
                for item in reversed(st.session_state.action_log[-5:]):
                    st.caption(f"{item['time']} - {item['activity']}")
            else:
                st.caption("No activity yet.")
                
            if st.button("🔒 Log Out"):
                st.session_state["password_correct"] = False
                st.rerun()

        # Navigation
        selected = option_menu(
            menu_title=None,
            options=["Co-Pilot", "Drafter", "PMB Drafter", "Schemes", "Archives"],
            icons=["robot", "pen", "law", "cash-coin", "archive"],
            menu_icon="cast",
            default_index=0,
            orientation="horizontal"
        )
        
        # --- PASSING GLOBAL SETTINGS TO MODULES ---
        # We now pass the 'global_lang' to modules or they read it from session_state
        if selected == "Co-Pilot":
            render_copilot(api_key=st.session_state.groq_api_key)
        elif selected == "Drafter":
            render_drafter(username)
        elif selected == "PMB Drafter":
            render_pmb_drafter(username)
        elif selected == "Schemes":
            render_matcher(user_tags=user.get('tags', []))
        elif selected == "Archives":
            st.title("📂 User Archives")
            archives = load_archives(username)
            if not archives:
                st.info("No drafts saved yet.")
            else:
                for doc in archives:
                    with st.expander(f"📄 {doc['title']} ({doc['date']})"):
                        st.text_area("Content", doc['content'], height=200, disabled=True)
                        c1, c2 = st.columns([1, 4])
                        with c1:
                            if st.button("🗑️ Delete", key=f"del_{doc['id']}"): delete_draft(username, doc['id'])
                        with c2:
                            show_download_button(doc['content'], doc['title'])