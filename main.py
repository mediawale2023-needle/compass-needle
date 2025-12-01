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
    from modules.utils import track_action
    from modules.persistence import load_archives, delete_draft # Needed for Archives display
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

# --- INITIALIZE PERSISTENT STORAGE ---
if 'uploaded_file_data' not in st.session_state:
    st.session_state.uploaded_file_data = None
if 'uploaded_file_name' not in st.session_state:
    st.session_state.uploaded_file_name = ""
if 'action_log' not in st.session_state: 
    st.session_state.action_log = []
if 'groq_api_key' not in st.session_state:
    st.session_state.groq_api_key = ""
if 'password_correct' not in st.session_state:
    st.session_state.password_correct = False


# --- CUSTOM CSS (Premium UI & Native App Feel) ---
st.markdown("""
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<style>
    /* Premium UI Overrides */
    .stApp { background-color: #f8f9fa; }
    h1, h2, h3 { font-family: 'Helvetica Neue', sans-serif; color: #0f172a; }
    /* Profile Card in Sidebar */
    .profile-card {
        background-color: white; border: 1px solid #e0e0e0;
        padding: 15px; border-radius: 10px; text-align: center; margin-bottom: 20px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .status-dot { color: #10b981; font-size: 0.8em; margin-top:5px;}
    /* Hide Default Streamlit Menu & Footer */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# --- AUTHENTICATION LOGIC (Development Bypass) ---
def check_password():
    # --- TEMPORARY BYPASS START ---
    if not st.session_state.password_correct:
        try:
            st.session_state["username"] = "milind_deora"
            st.session_state["user_profile"] = st.secrets["profiles"]["milind_deora"]
            st.session_state["current_user"] = "milind_deora"
            st.session_state["password_correct"] = True
            return True
        except:
            # Fallback for when secrets.toml isn't loaded correctly
            st.error("Login bypass failed: Ensure .streamlit/secrets.toml is correctly loaded with 'milind_deora' profile.")
            return False
    # --- TEMPORARY BYPASS END ---
    
    # NOTE: The full login gate is disabled here for rapid development. 
    # For production, uncomment the full check_password() function.
    return True 

# --- MAIN EXECUTION ---
if check_password():
    # --- GET PERSISTED USER DATA ---
    username = st.session_state.get("current_user", "milind_deora")
    user = st.session_state["user_profile"]

    # === GOD MODE (ADMIN ROUTING - Simplified for this context) ===
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
            
            # --- HISTORY LOG DISPLAY ---
            st.divider()
            st.subheader("🕒 Session History")
            if st.session_state.action_log:
                for item in reversed(st.session_state.action_log[-5:]):
                    st.markdown(f'<div style="font-size:0.85em;"><b>{item["time"]}</b>: {item["activity"]}</div>', unsafe_allow_html=True)
            else:
                st.caption("No activities recorded yet.")
            
            # --- SECURITY ACTIONS ---
            st.divider()
            if st.button("🔑 Change Password"):
                 st.session_state["show_change_form"] = True

            if st.button("🔒 Log Out"):
                st.session_state["password_correct"] = False
                st.session_state["show_change_form"] = False
                st.rerun()

        # Navigation
        selected = option_menu(
            menu_title=None,
            options=["Co-Pilot", "Drafter", "PMB Drafter", "Schemes", "Archives"],
            icons=["robot", "pen", "law", "cash-coin", "archive"],
            menu_icon="cast",
            default_index=0,
            orientation="horizontal",
            styles={
                "container": {"padding": "0!important", "background-color": "transparent"},
                "icon": {"color": "#002D62", "font-size": "18px"}, 
                "nav-link": {"font-size": "16px", "text-align": "center", "margin":"0px"},
                "nav-link-selected": {"background-color": "#002D62"},
            }
        )
        
        # --- ROUTING ---
        if selected == "Co-Pilot":
            render_copilot()
        elif selected == "Drafter":
            render_drafter(username)
        elif selected == "PMB Drafter":
            render_pmb_drafter(username)
        elif selected == "Schemes":
            render_matcher(user_tags=user.get('tags', []))
        elif selected == "Archives":
            # --- NEW: ARCHIVES VIEW ---
            st.title("📂 User Archives")
            archives = load_archives(username)
            if not archives:
                st.info("No drafts saved yet. Use the 'Save' button in the Drafter to create archives.")
            else:
                for draft in archives:
                    with st.expander(f"📝 {draft['title']} ({draft['date']})"):
                        st.text_area("Content Preview", draft['content'], height=200, disabled=True)
                        
                        col_d_p, col_d_d = st.columns([1,1])
                        
                        # --- DOWNLOAD BUTTON FOR ARCHIVE ITEM ---
                        col_d_p.button("⬇️ Download", key=f"dl_{draft['id']}", 
                                       on_click=show_download_button, 
                                       args=(draft['content'], draft['title'].replace(' ', '_')))
                                       
                        # --- DELETE BUTTON FOR ARCHIVE ITEM ---
                        col_d_d.button("🗑️ Delete", key=f"del_{draft['id']}", 
                                       on_click=delete_draft, 
                                       args=(username, draft['id']),
                                       type="secondary")

        # --- PASSWORD CHANGE FORM RENDER ---
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