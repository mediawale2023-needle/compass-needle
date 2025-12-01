import streamlit as st
import base64
from datetime import datetime
import time

def track_action(activity_description):
    """Adds a timestamped entry to the persistent session history log."""
    # Ensure the log list exists
    if 'action_log' not in st.session_state:
        st.session_state.action_log = []
        
    st.session_state.action_log.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "activity": activity_description
    })

def show_download_button(text_content, filename_prefix="needle_draft"):
    """
    Generates an anchor tag (button) to download the text content via base64 encoding.
    (This uses a hack because st.download_button is not used.)
    """
    try:
        # Encode content to base64
        b64 = base64.b64encode(text_content.encode('utf-8')).decode()
    except Exception:
        # Fallback if encoding fails (e.g., complex unicode data)
        st.error("Download encoding failed.")
        return

    # Generate a unique, professional filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{filename_prefix.replace(' ', '_')}_{timestamp}.txt"
    
    # Create the downloadable link using HTML markdown
    href = f'<a href="data:file/txt;base64,{b64}" download="{filename}">'
    button_html = f'<button style="background-color:#002D62; color:white; padding: 10px 20px; border-radius: 5px; border: none; cursor: pointer;">⬇️ Download to PC</button></a>'
    
    # Inject the button HTML into Streamlit
    st.markdown(href + button_html, unsafe_allow_html=True)