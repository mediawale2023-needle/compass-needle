import streamlit as st
from langchain_groq import ChatGroq
from pypdf import PdfReader
from deep_translator import GoogleTranslator
from modules.utils import track_action, show_download_button
from modules.persistence import save_draft

def render_copilot(username):
    st.header("Legislative Co-Pilot")
    
    api_key = st.session_state.groq_api_key
    if not api_key:
        st.warning("Please enter Groq API Key in Sidebar.")
        return

    uploaded_file = st.file_uploader("Upload Bill (PDF)", type="pdf")
    
    if uploaded_file:
        reader = PdfReader(uploaded_file)
        text = ""
        for page in reader.pages: text += page.extract_text()
        st.success(f"Loaded {len(reader.pages)} pages.")
        
        query = st.chat_input("Ask a question...")
        if query:
            with st.spinner("Analyzing..."):
                try:
                    llm = ChatGroq(temperature=0, groq_api_key=api_key, model_name="llama-3.1-8b-instant")
                    prompt = f"Answer based on text:\n{text[:15000]}\nQuestion: {query}"
                    response = llm.invoke(prompt).content
                    
                    st.markdown("### Analysis")
                    st.write(response)
                    
                    # --- SAVE & DOWNLOAD ---
                    c1, c2 = st.columns([1,4])
                    with c1:
                        if st.button("💾 Save"):
                            save_draft(username, f"Analysis: {uploaded_file.name}", response, "Co-Pilot")
                            track_action("Saved Bill Analysis")
                    with c2:
                        show_download_button(response, "Bill_Analysis")
                        
                except Exception as e:
                    st.error(f"Error: {e}")