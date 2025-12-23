import streamlit as st
import base64
from datetime import datetime
from deep_translator import GoogleTranslator

def track_action(activity_description):
    """Adds a timestamped entry to the session history log."""
    if 'action_log' not in st.session_state:
        st.session_state.action_log = []
    
    st.session_state.action_log.append({
        "time": datetime.now().strftime("%H:%M"),
        "activity": activity_description
    })

def show_download_button(text_content, filename_prefix="needle_draft"):
    """Generates a download link for text content."""
    try:
        b64 = base64.b64encode(text_content.encode('utf-8')).decode()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"{filename_prefix.replace(' ', '_')}_{timestamp}.txt"
        
        href = f'<a href="data:file/txt;base64,{b64}" download="{filename}">'
        button_html = f'''
        <div style="margin-top:10px;">
            {href}<button style="
                background-color: #f0f2f6; 
                border: 1px solid #d1d5db; 
                border-radius: 5px; 
                padding: 5px 15px; 
                cursor: pointer; 
                color: #31333F; 
                font-size: 14px;">
                ⬇️ Download .txt
            </button></a>
        </div>
        '''
        st.markdown(button_html, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Download Error: {e}")

def perform_translation(text, target_language_name):
    """
    Centralized Translation Logic.
    Reads the language name (e.g. 'Marathi (मराठी)') and translates.
    """
    # 1. Map the long name to the ISO code
    lang_map = {
        "English": "en", 
        "Hindi (हिंदी)": "hi", 
        "Marathi (मराठी)": "mr", 
        "Tamil (தமிழ்)": "ta"
    }
    
    target_code = lang_map.get(target_language_name, "en")
    
    # 2. If English, return as is
    if target_code == "en":
        return text

    # 3. Perform Translation with Error Reporting
    try:
        translator = GoogleTranslator(source='auto', target=target_code)
        translated_text = translator.translate(text)
        return translated_text
    except Exception as e:
        # If it fails, show the error so we know WHY it failed
        st.warning(f"⚠️ Translation Failed: {e}")
        return text # Fallback to English