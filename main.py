import streamlit as st
from modules.copilot import render_copilot
from modules.drafter import render_drafter

# Page Configuration
st.set_page_config(
    page_title="Needle - Legislative Intelligence",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Sovereign Blue branding
st.markdown("""
<style>
    .main-header {
        color: #002D62;
        font-size: 2.5rem;
        font-weight: bold;
        text-align: center;
        padding: 1rem 0;
    }
    .sub-header {
        color: #002D62;
        font-size: 1.2rem;
        text-align: center;
        margin-bottom: 2rem;
    }
    .footer {
        position: fixed;
        bottom: 0;
        left: 0;
        width: 100%;
        background-color: #002D62;
        color: white;
        text-align: center;
        padding: 0.5rem;
        font-size: 0.9rem;
        z-index: 999;
    }
    .stRadio > label {
        color: #002D62;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Main Header
st.markdown('<div class="main-header">🔍 Needle</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">The Compass for Indian Legislation</div>', unsafe_allow_html=True)

# Sidebar Navigation
st.sidebar.title("Navigation")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Select Module:",
    [
        "🤖 Legislative Co-Pilot",
        "📝 Parliamentary Question Generator",
        "⏰ Zero Hour Drafter"
    ],
    label_visibility="collapsed"
)

st.sidebar.markdown("---")
st.sidebar.info("**Office of the MP (Milind Deora)**\n\nLegislative Intelligence Unit")

# Route to appropriate module
if "Legislative Co-Pilot" in page:
    render_copilot()
elif "Parliamentary Question Generator" in page or "Zero Hour Drafter" in page:
    # Pass the selected page type to drafter
    if "Parliamentary Question Generator" in page:
        render_drafter("question")
    else:
        render_drafter("zero_hour")

# Footer
st.markdown('<div class="footer">🔒 Secure Mode: Local Embeddings Active | Powered by Needle v1.0</div>', unsafe_allow_html=True)