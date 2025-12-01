import streamlit as st
from langchain_groq import ChatGroq
from pypdf import PdfReader
from modules.utils import track_action, show_download_button
from modules.persistence import save_draft
from deep_translator import GoogleTranslator

def render_copilot(username):
    st.header("Legislative Co-Pilot")
    
    # 1. Check API Key
    api_key = st.session_state.get('groq_api_key')
    if not api_key:
        st.error("⚠️ Groq API Key missing. Please enter it in the Sidebar.")
        return

    # 2. Get Language
    current_lang = st.session_state.get("global_lang", "English")
    lang_map = {"English": "en", "Hindi (हिंदी)": "hi", "Marathi (मराठी)": "mr", "Tamil (தமிழ்)": "ta"}
    target_lang_code = lang_map.get(current_lang, "en")

    # 3. File Uploader Logic (With Reset Button)
    uploaded_file = st.file_uploader("Upload Bill (PDF)", type="pdf", key="copilot_uploader")
    
    if uploaded_file:
        # Read the PDF
        try:
            reader = PdfReader(uploaded_file)
            text = ""
            for page in reader.pages:
                text += page.extract_text()
            
            st.success(f"✅ Loaded {len(reader.pages)} pages.")
            
            # Chat Interface
            query = st.chat_input("Ask a question about this bill...")
            
            if query:
                with st.spinner(f"Analyzing in {current_lang}..."):
                    try:
                        # A. Generate (English)
                        llm = ChatGroq(temperature=0, groq_api_key=api_key, model_name="llama-3.1-8b-instant")
                        prompt = f"Answer based on text:\n{text[:15000]}\nQuestion: {query}"
                        eng_response = llm.invoke(prompt).content
                        
                        # B. Translate
                        final_response = eng_response
                        if target_lang_code != "en":
                            final_response = GoogleTranslator(source='auto', target=target_lang_code).translate(eng_response)

                        # C. Display & Actions
                        st.markdown(f"### 🤖 Answer")
                        st.write(final_response)
                        
                        col1, col2 = st.columns([1, 4])
                        with col1:
                            if st.button("💾 Save"):
                                save_draft(username, f"Analysis: {uploaded_file.name}", final_response, "Co-Pilot")
                        with col2:
                            show_download_button(final_response, "Bill_Analysis")
                            
                    except Exception as e:
                        st.error(f"AI Error: {e}")
                        
        except Exception as e:
            st.error(f"Error reading PDF: {e}")