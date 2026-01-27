import streamlit as st
import os
import google.generativeai as genai
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load env variables (for Database)
load_dotenv()

# 🔒 YOUR INTEGRATED KEY
DEFAULT_API_KEY = "AIzaSyDTs8kUJDwVBhqw93JZDPhdn7aS9L3uc-I"

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
    """Ensures keys are loaded into Session State on app start."""
    if "GLOBAL_GEMINI_KEY" not in st.session_state:
        st.session_state["GLOBAL_GEMINI_KEY"] = DEFAULT_API_KEY
        os.environ["GEMINI_API_KEY"] = DEFAULT_API_KEY
        try:
            genai.configure(api_key=DEFAULT_API_KEY)
        except: pass

def get_valid_model():
    """
    Scans the user's account for a VALID model name.
    Prioritizes stable, high-quota models (2.0 Flash / Flash Latest).
    """
    init_keys()
    api_key = st.session_state.get("GLOBAL_GEMINI_KEY")
    if not api_key: return None
    
    try:
        genai.configure(api_key=api_key)
        
        # 1. Get List of ALL Models available to this key
        all_models = list(genai.list_models())
        valid_names = [m.name for m in all_models if 'generateContent' in m.supported_generation_methods]
        
        # 2. Define our "Wishlist" (Best & Most Stable first)
        wishlist = [
            "gemini-2.0-flash",       # New Standard (Fast & High Quota)
            "gemini-flash-latest",    # Stable Alias
            "gemini-1.5-flash",       # Workhorse
            "gemini-1.5-pro-latest",  # High Intelligence
            "gemini-pro"              # Old Reliable (Fallback)
        ]
        
        # 3. Find the best match
        selected_model_name = None
        for wish in wishlist:
            for valid in valid_names:
                if wish in valid:
                    selected_model_name = valid
                    break
            if selected_model_name: break
            
        # 4. Fallback: If nothing on wishlist matches, take the first valid one
        if not selected_model_name and valid_names:
            for m in valid_names:
                if "2.5" not in m:
                    selected_model_name = m
                    break
            if not selected_model_name:
                selected_model_name = valid_names[0]
            
        if selected_model_name:
            clean_name = selected_model_name.replace("models/", "")
            return genai.GenerativeModel(clean_name)
            
    except Exception as e:
        print(f"Model Discovery Error: {e}")
        return None
    return None

# --- 🖥️ SETTINGS PAGE RENDER ---
def render_settings():
    st.header("⚙️ Configuration & Profile")
    
    # Create Tabs to separate Tech Config from Profile Edit
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
                        # Update Session State immediately so UI reflects change
                        st.session_state.constituency = new_loc
                        st.success("✅ Profile updated successfully! The dashboard will now reflect your new location.")
                        st.rerun()

    # --- TAB 2: AI CONFIG (YOUR ORIGINAL CODE) ---
    with tab_ai:
        init_keys()
        current_key = st.session_state.get("GLOBAL_GEMINI_KEY", "")
        
        with st.container(border=True):
            st.subheader("🔑 Google Gemini API Key")
            display_key = f"...{current_key[-6:]}" if len(current_key) > 10 else "Not Set"
            st.text_input("Active Key", value=display_key, disabled=True)
            st.caption("✅ System is using the integrated key.")
            
            if st.button("🧪 Auto-Detect & Test Connection"):
                with st.spinner("Scanning for best available model..."):
                    model = get_valid_model()
                    if model:
                        try:
                            resp = model.generate_content("Hello")
                            st.success(f"✅ Success! Connected to: **{model.model_name}**")
                        except Exception as e:
                            st.error(f"Connected to {model.model_name} but generation failed: {e}")
                    else:
                        st.error("❌ Key accepted, but no models found.")

        st.divider()
        st.write("🟢 **System Status:** Online")