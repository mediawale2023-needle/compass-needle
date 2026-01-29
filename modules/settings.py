import streamlit as st
import os
import google.generativeai as genai
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load env variables
load_dotenv()

# --- 🔌 DATABASE CONNECTION ---
def get_db_engine():
    """Connects to Railway Postgres if available, else Local SQLite"""
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        return create_engine(db_url)
    return create_engine("sqlite:///./sansadx.db")

def update_profile(username, new_constituency, new_password=None):
    """Updates user profile details in the database"""
    engine = get_db_engine()
    
    # Base Query
    sql = "UPDATE users SET constituency = :c"
    params = {"c": new_constituency, "u": username}
    
    # If password is provided, add it to query
    if new_password:
        sql += ", password_hash = :p"
        params["p"] = new_password 
        
    sql += " WHERE username = :u"
    
    try:
        with engine.connect() as conn:
            conn.execute(text(sql), params)
            conn.commit()
            return True
    except Exception as e:
        st.error(f"Database Update Error: {e}")
        return False

# --- 🧠 AI MODEL LOGIC ---
def init_keys():
    """Ensures keys are loaded from Environment Variables."""
    # 1. Try to get key from Environment (Local .env or Railway Variables)
    env_key = os.getenv("GEMINI_API_KEY")
    
    if env_key:
        st.session_state["GLOBAL_GEMINI_KEY"] = env_key
        try:
            genai.configure(api_key=env_key)
        except Exception as e:
            print(f"Gemini Config Error: {e}")
    else:
        # If no key found, warn the user
        if "GLOBAL_GEMINI_KEY" not in st.session_state:
            st.session_state["GLOBAL_GEMINI_KEY"] = None

def get_valid_model():
    """
    Scans for the best available Gemini model using the secure key.
    """
    init_keys()
    api_key = st.session_state.get("GLOBAL_GEMINI_KEY")
    
    if not api_key: 
        return None
    
    try:
        genai.configure(api_key=api_key)
        
        # 1. Wishlist of models (Fastest -> Smartest)
        wishlist = [
            "gemini-1.5-flash",       # Best for speed/cost
            "gemini-1.5-pro",         # Best for complex reasoning
            "gemini-pro"              # Fallback
        ]
        
        # 2. Try to list models to verify connection
        try:
            list(genai.list_models()) # Just to test auth
        except:
            return None

        # 3. Return the generic generative model (It auto-selects best stable version)
        return genai.GenerativeModel("gemini-1.5-flash")
            
    except Exception as e:
        print(f"Model Discovery Error: {e}")
        return None

# --- 🖥️ SETTINGS PAGE RENDER ---
def render_settings():
    st.header("⚙️ Configuration & Profile")
    
    # Create Tabs
    tab_profile, tab_ai = st.tabs(["👤 Edit Profile", "🧠 AI Configuration"])

    # --- TAB 1: PROFILE MANAGEMENT ---
    with tab_profile:
        st.subheader("Manage Identity")
        current_user = st.session_state.get('current_user', 'Unknown')
        
        with st.form("profile_form"):
            # 1. Location
            current_loc = st.session_state.get('constituency', 'India')
            new_loc = st.text_input("Constituency (Required for Local Pulse)", value=current_loc)
            st.caption("This location determines your local news feed.")

            st.divider()

            # 2. Security
            st.subheader("🔐 Change Password")
            st.caption("Leave blank if you do not want to change password.")
            new_pass = st.text_input("New Password", type="password")
            confirm_pass = st.text_input("Confirm New Password", type="password")

            submit = st.form_submit_button("💾 Save Profile Changes", type="primary")
            
            if submit:
                # Validation
                if new_pass and new_pass != confirm_pass:
                    st.error("❌ Passwords do not match.")
                else:
                    success = update_profile(current_user, new_loc, new_pass if new_pass else None)
                    if success:
                        st.session_state.constituency = new_loc
                        st.success("✅ Profile updated successfully! The dashboard will now reflect your new location.")
                        time.sleep(1) # Allow user to read success message
                        st.rerun()

    # --- TAB 2: AI CONFIG ---
    with tab_ai:
        init_keys()
        current_key = st.session_state.get("GLOBAL_GEMINI_KEY", "")
        
        with st.container(border=True):
            st.subheader("🔑 Google Gemini API Key")
            
            if current_key:
                display_key = f"...{current_key[-6:]}"
                st.success(f"✅ Key Loaded Securely (Ends in {display_key})")
                
                if st.button("🧪 Test Connection"):
                    with st.spinner("Connecting to Google AI..."):
                        model = get_valid_model()
                        if model:
                            try:
                                resp = model.generate_content("Hello")
                                st.success(f"✅ Success! Connected to Gemini.")
                            except Exception as e:
                                st.error(f"Connection failed: {e}")
                        else:
                            st.error("❌ Invalid Key or API Error.")
            else:
                st.warning("⚠️ No API Key found.")
                st.info("Add `GEMINI_API_KEY` to your `.env` file (Local) or Railway Variables (Cloud).")

        st.divider()
        st.write("🟢 **System Status:** Online")