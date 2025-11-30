import streamlit as st

def render_copilot():
    st.header("🤖 Legislative Co-Pilot (Brain Offline)")
    st.warning("⚠️ High-Performance RAG Module disabled in Mobile Mode.")
    
    uploaded_file = st.file_uploader("Upload Bill (PDF)", type="pdf")
    if uploaded_file:
        st.success("File Received. (Indexing disabled to save memory)")
    
    query = st.chat_input("Ask a question...")
    if query:
        st.info(f"You asked: {query}")
        st.markdown("### AI Analysis")
        st.write("To enable full analysis, please deploy on a standard server with >2GB RAM.")
