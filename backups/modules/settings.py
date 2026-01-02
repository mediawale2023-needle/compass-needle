import streamlit as st
import os
import google.generativeai as genai

# 🔒 YOUR INTEGRATED KEY
DEFAULT_API_KEY = "AIzaSyDTs8kUJDwVBhqw93JZDPhdn7aS9L3uc-I"

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
    Prioritizes stable, high-quota models (2.0 Flash / Flash Latest) to avoid errors.
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
        # We prioritize '2.0-flash' and 'flash-latest' as they are the new standards.
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
            # Try to avoid '2.5' preview models if possible (low quota)
            for m in valid_names:
                if "2.5" not in m:
                    selected_model_name = m
                    break
            # If only 2.5 exists, take it
            if not selected_model_name:
                selected_model_name = valid_names[0]
            
        if selected_model_name:
            # Clean up the name (remove 'models/' prefix)
            clean_name = selected_model_name.replace("models/", "")
            return genai.GenerativeModel(clean_name)
            
    except Exception as e:
        print(f"Model Discovery Error: {e}")
        return None
    return None

def render_settings():
    st.header("⚙️ Global Configuration")
    
    init_keys()
    current_key = st.session_state.get("GLOBAL_GEMINI_KEY", "")
    
    with st.container(border=True):
        st.subheader("🔑 Google Gemini API Key")
        # Show masked key
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