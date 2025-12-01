import streamlit as st
import base64
from datetime import datetime

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
        filename = f"{filename_prefix}_{timestamp}.txt"
        
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