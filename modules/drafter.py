import streamlit as st
from langchain_groq import ChatGroq
from modules.utils import track_action, show_download_button
from modules.persistence import save_draft

def render_drafter(username):
    st.header("Legislative Drafter")
    
    api_key = st.session_state.groq_api_key
    if not api_key:
        st.warning("Enter API Key in Sidebar.")
        return

    tab1, tab2, tab3 = st.tabs(["Letters", "Questions", "Zero Hour"])

    # --- LETTERS ---
    with tab1:
        recipient = st.text_input("Recipient", placeholder="District Collector")
        subject = st.text_input("Subject", placeholder="Road Repair")
        context = st.text_area("Details")
        
        if st.button("Draft Letter"):
            llm = ChatGroq(temperature=0.5, groq_api_key=api_key, model_name="llama-3.1-8b-instant")
            prompt = f"Write a formal letter to {recipient} about {subject}. Details: {context}"
            draft = llm.invoke(prompt).content
            st.text_area("Output", draft, height=300)
            
            c1, c2 = st.columns([1,4])
            with c1: 
                if st.button("💾 Save Letter"):
                    save_draft(username, f"Letter: {subject}", draft, "Letter")
                    track_action(f"Drafted Letter: {subject}")
            with c2: show_download_button(draft, "Letter")

    # --- QUESTIONS ---
    with tab2:
        ministry = st.text_input("Ministry", placeholder="Railways")
        topic = st.text_input("Topic", placeholder="Safety")
        
        if st.button("Generate PQ"):
            llm = ChatGroq(temperature=0.5, groq_api_key=api_key, model_name="llama-3.1-8b-instant")
            prompt = f"Generate 5 Parliamentary Questions for {ministry} on {topic}."
            draft = llm.invoke(prompt).content
            st.write(draft)
            
            c1, c2 = st.columns([1,4])
            with c1:
                if st.button("💾 Save PQs"):
                    save_draft(username, f"PQ: {topic}", draft, "Parliamentary Question")
                    track_action(f"Generated PQs: {topic}")
            with c2: show_download_button(draft, "PQ_Draft")