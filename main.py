import streamlit as st
from streamlit_option_menu import option_menu

# --- MODULE IMPORTS ---
try:
    from modules.copilot import render_copilot
    from modules.drafter import render_drafter
    from modules.matcher import render_matcher
    from modules.admin import render_admin
    from modules.pmb_drafter import render_pmb_drafter
    from modules.utils import show_download_button
    from modules.persistence import load_archives, delete_draft
except ImportError:
    st.error("Modules missing. Please check file structure.")

st.set_page_config(page_title="Needle | Sovereign OS", page_icon="🧭", layout="wide")

# --- SESSION STATE SETUP ---
if 'action_log' not in st.session_state: st.session_state.action_log = []
if 'groq_api_key' not in st.session_state: st.session_state.groq_api_key = ""

# --- UI STYLING ---
st.markdown("""
<style>
    .stApp { background-color: #f8f9fa; }
    .profile-card { background:white; padding:15px; border-radius:10px; border:1px solid #ddd; text-align:center; }
    #MainMenu, footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("""
    <div class="profile-card">
        <img src="https://ui-avatars.com/api/?name=Milind+Deora&background=002D62&color=fff&size=64" style="border-radius:50%;">
        <div style="font-weight:bold; margin-top:5px;">Hon. Milind Deora</div>
        <div style="font-size:0.8em; color:green;">● Secure Server</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.divider()
    
    # PERSISTENT KEY INPUT
    input_key = st.text_input("Groq API Key", type="password", value=st.session_state.groq_api_key)
    if input_key: st.session_state.groq_api_key = input_key
    
    st.divider()
    
    # HISTORY LOG
    st.subheader("🕒 History")
    if st.session_state.action_log:
        for item in reversed(st.session_state.action_log[-5:]):
            st.caption(f"{item['time']} - {item['activity']}")
    else:
        st.caption("No activity yet.")

# --- NAVIGATION ---
selected = option_menu(
    menu_title=None,
    options=["Co-Pilot", "Drafter", "PMB Drafter", "Schemes", "Archives"],
    icons=["robot", "pen", "law", "cash-coin", "archive"],
    orientation="horizontal",
    default_index=0
)

# --- ROUTING ---
username = "milind_deora" # Hardcoded for MVP

if selected == "Co-Pilot":
    render_copilot(username)
elif selected == "Drafter":
    render_drafter(username)
elif selected == "PMB Drafter":
    render_pmb_drafter(username) # Ensure you update pmb_drafter to accept username if needed
elif selected == "Schemes":
    render_matcher(user_tags=["Coastal", "Urban"])
elif selected == "Archives":
    st.title("📂 User Archives")
    archives = load_archives()
    if not archives:
        st.info("No saved drafts found.")
    else:
        for doc in archives:
            with st.expander(f"📄 {doc['title']} ({doc['date']})"):
                st.caption(f"Category: {doc['category']}")
                st.text_area("Content", doc['content'], height=200)
                c1, c2 = st.columns([1, 4])
                with c1:
                    if st.button("🗑️ Delete", key=doc['id']):
                        delete_draft(doc['id'])
                with c2:
                    show_download_button(doc['content'], doc['title'])