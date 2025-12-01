import streamlit as st
from langchain_groq import ChatGroq
# IMPORT NEW UTILS
from modules.utils import track_action, show_download_button, perform_translation
from modules.persistence import save_draft

def render_drafter(username):
    st.header("Legislative Drafter")
    
    # --- READ GLOBAL STATE (No local dropdown) ---
    api_key = st.session_state.get('groq_api_key')
    current_lang = st.session_state.get("global_lang", "English")

    if not api_key:
        st.warning("Enter API Key in Main Sidebar.")
        return

    tab1, tab2, tab3 = st.tabs(["Letters", "Questions", "Zero Hour"])

    # --- LETTERS ---
    with tab1:
        st.subheader(f"Official Correspondence ({current_lang})")
        recipient = st.text_input("Recipient", placeholder="District Collector")
        subject = st.text_input("Subject", placeholder="Road Repair")
        context = st.text_area("Details")
        
        if st.button("Draft Letter"):
            with st.spinner("Drafting..."):
                llm = ChatGroq(temperature=0.5, groq_api_key=api_key, model_name="llama-3.1-8b-instant")
                prompt = f"Write a formal letter to {recipient} about {subject}. Details: {context}"
                
                # 1. Generate
                eng_draft = llm.invoke(prompt).content
                # 2. Translate
                final_draft = perform_translation(eng_draft, current_lang)
                
                st.text_area("Output", final_draft, height=300)
                
                c1, c2 = st.columns([1,4])
                with c1: 
                    if st.button("💾 Save Letter"): 
                        save_draft(username, f"Letter: {subject}", final_draft, "Letter")
                with c2: show_download_button(final_draft, "Letter")

    # --- ZERO HOUR ---
    with tab3:
        st.subheader(f"Zero Hour Speech ({current_lang})")
        issue = st.text_input("Issue", placeholder="Water Crisis")
        if st.button("Draft Speech"):
            with st.spinner("Writing..."):
                llm = ChatGroq(temperature=0.7, groq_api_key=api_key, model_name="llama-3.1-8b-instant")
                eng_speech = llm.invoke(f"Write a 200-word speech about {issue}.").content
                
                # Translate
                final_speech = perform_translation(eng_speech, current_lang)
                
                st.text_area("Script", final_speech, height=200)
                c1, c2 = st.columns([1,4])
                with c1: 
                    if st.button("💾 Save"): 
                        save_draft(username, f"Speech: {issue}", final_speech, "Zero Hour")
                with c2: show_download_button(final_speech, "Speech")
    
    # (Keep the Questions tab logic similar if needed, usually PQs are English/Hindi only)
    with tab2:
        st.info("Parliamentary Questions are generated in English/Hindi format standard.")