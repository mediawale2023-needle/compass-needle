import streamlit as st
from streamlit_option_menu import option_menu
from datetime import datetime
import os

# --- MODULE IMPORTS (Safe Loading) ---
try:
    from modules.copilot import render_copilot
    from modules.drafter import render_drafter
    from modules.matcher import render_matcher  # Schemes
    from modules.admin import render_admin
    from modules.pmb_drafter import render_pmb_drafter
    # CSR Suite
    from modules.csr_discovery import render_csr_discovery
    from modules.csr_projects import render_csr_projects
    from modules.csr_partners import render_csr_partners
    from modules.state_intel import render_state_intel  
    # Utilities
    from modules.utils import track_action, show_download_button
    from modules.persistence import load_archives, delete_draft 
except ImportError as e:
    st.error(f"⚠️ Module Missing: {e}. Please ensure all files are in the 'modules/' folder.")
    st.stop()

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Needle | Sovereign OS",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- INITIALIZE SESSION STATE ---
if 'uploaded_file_data' not in st.session_state: st.session_state.uploaded_file_data = None
if 'uploaded_file_name' not in st.session_state: st.session_state.uploaded_file_name = ""
if 'action_log' not in st.session_state: st.session_state.action_log = [] 
if 'groq_api_key' not in st.session_state: st.session_state.groq_api_key = ""
if 'password_correct' not in st.session_state: st.session_state.password_correct = False
if 'global_lang' not in st.session_state: st.session_state.global_lang = "English"


# --- CUSTOM CSS (Native App Feel) ---
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
    /* Tabs Styling */
    .stTabs [data-baseweb="tab-list"] { gap: 20px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: #fff; border-radius: 5px; padding: 10px 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    .stTabs [aria-selected="true"] { background-color: #e6f0ff; color: #002D62; border-bottom: 2px solid #002D62; }
</style>
""", unsafe_allow_html=True)

# --- AUTHENTICATION (DEV BYPASS ACTIVE) ---
def check_password():
    if not st.session_state.password_correct:
        try:
            # Force Login as Default User for Demo
            st.session_state["username"] = "milind_deora"
            st.session_state["user_profile"] = st.secrets["profiles"]["milind_deora"]
            st.session_state["current_user"] = "milind_deora"
            st.session_state["password_correct"] = True
            return True
        except:
            # Fallback if secrets.toml is missing
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

# --- MAIN APP EXECUTION ---
if check_password():
    username = st.session_state.get("current_user", "milind_deora")
    user = st.session_state["user_profile"]

    # === GOD MODE (ADMIN) ===
    if username == "admin":
        render_admin()
        
    else:
        # === STANDARD MP INTERFACE ===
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
            
            # --- GLOBAL API KEY INPUT ---
            input_key = st.text_input(
                "Groq API Key", type="password", 
                value=st.session_state.get('groq_api_key', ''), 
                key='global_key_input', placeholder="gsk_..."
            )
            if input_key: st.session_state.groq_api_key = input_key
            
            st.divider()
            
            # --- GLOBAL LANGUAGE ---
            selected_lang = st.selectbox(
                "Output Language", 
                ["English", "Hindi (हिंदी)", "Marathi (मराठी)", "Tamil (தமிழ்)"],
                key="global_lang_select",
                index=["English", "Hindi (हिंदी)", "Marathi (मराठी)", "Tamil (தமிழ்)"].index(st.session_state.get("global_lang", "English"))
            )
            st.session_state.global_lang = selected_lang

            st.divider()
            
            # --- HISTORY LOG ---
            st.subheader("🕒 History")
            if st.session_state.action_log:
                for item in reversed(st.session_state.action_log[-5:]):
                    st.markdown(f'<div style="font-size:0.8em; border-bottom:1px solid #eee; margin-bottom:4px;"><b>{item["time"]}</b>: {item["activity"]}</div>', unsafe_allow_html=True)
            else:
                st.caption("No activity yet.")
            
            st.divider()

            # --- PASSWORD CHANGE ---
            if st.button("🔑 Change Password"):
                 st.session_state["show_change_form"] = True

            if st.button("🔒 Log Out"):
                st.session_state["password_correct"] = False
                st.session_state["show_change_form"] = False
                st.rerun()

        # === NAVIGATION MENU ===
        selected = option_menu(
            menu_title=None,
            options=[
                "Dashboard", 
                "Co-Pilot", 
                "Drafter", 
                "PMB", 
                "State Intel", 
                "CSR Suite", 
                "Schemes", 
                "Archives"
            ],
            icons=[
                "speedometer2", 
                "robot", 
                "pen", 
                "law", 
                "map-fill",
                "buildings",  # CSR Suite
                "cash-coin", 
                "archive"
            ],
            menu_icon="cast",
            default_index=0,
            orientation="horizontal",
            styles={
                "container": {"padding": "0!important", "background-color": "transparent"},
                "icon": {"color": "#002D62", "font-size": "14px"}, 
                "nav-link": {"font-size": "14px", "text-align": "center", "margin":"2px", "padding":"10px"},
                "nav-link-selected": {"background-color": "#002D62", "color": "white"},
            }
        )
        
        # === PASSWORD CHANGE FORM RENDER ===
        if st.session_state.get('show_change_form', False):
            st.title("🔑 Password Change Request")
            st.warning("All changes require final approval from System Administrator (Manual Update in secrets.toml).")
            with st.form("change_password_form"):
                st.text_input("New Password", type="password", key="new_pass")
                st.text_input("Confirm New Password", type="password", key="confirm_pass")
                
                if st.form_submit_button("Submit Request"):
                    if st.session_state.new_pass != st.session_state.confirm_pass:
                        st.error("Passwords do not match.")
                    else:
                        st.success(f"Request submitted for {user.get('name')}. Contact Admin.")
                        st.session_state.show_change_form = False
                        st.rerun()

        # === ROUTING LOGIC ===
        
        elif selected == "Dashboard":
            # Simple Dashboard View
            st.title("🏛️ Command Center")
            c1, c2, c3 = st.columns(3)
            c1.metric("State CSR Funds", "₹35,835 Cr", "Maharashtra")
            c2.metric("Pending Drafts", "3", "Urgent")
            c3.metric("District Alert", "Nagpur (Water)", "Critical")
            st.info("System Status: All Intelligence Nodes Online.")

        elif selected == "Co-Pilot":
            render_copilot(username)
            
        elif selected == "Drafter":
            render_drafter(username)
            
        elif selected == "PMB":
            render_pmb_drafter(username)
            
        elif selected == "State Intel":
            render_state_intel(username)

        elif selected == "CSR Suite":
            # --- CSR SUB-NAVIGATION ---
            st.title("💰 Corporate Social Responsibility (CSR)")
            
            # Create Sub-Tabs
            tab_disc, tab_proj, tab_part = st.tabs([
                "🔭 Discovery (Funding)", 
                "📋 Project Catalog", 
                "🤝 Partners (NGOs)"
            ])
            
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
            if not archives:
                st.info("No saved drafts found.")
            else:
                for doc in archives:
                    with st.expander(f"📄 {doc['title']} ({doc['date']})"):
                        st.caption(f"Category: {doc['category']}")
                        st.text_area("Content", doc['content'], height=200, disabled=True)
                        c1, c2 = st.columns([1, 4])
                        with c1:
                            if st.button("🗑️ Delete", key=f"del_{doc['id']}"): delete_draft(username, doc['id'])
                        with c2:
                            show_download_button(doc['content'], doc['title'])