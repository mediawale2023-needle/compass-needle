import streamlit as st
from langchain_groq import ChatGroq
from pypdf import PdfReader
import requests
from bs4 import BeautifulSoup
import json
import pandas as pd
import os
# IMPORT THE NEW TRANSLATOR
from modules.utils import track_action, show_download_button, perform_translation

@st.cache_data
def load_data_from_json(file_path_or_buffer):
    try:
        if isinstance(file_path_or_buffer, str):
            with open(file_path_or_buffer, 'r') as f: data = json.load(f)
        else: data = json.load(file_path_or_buffer)
        return pd.DataFrame(data)
    except: return pd.DataFrame()

def render_copilot(username=None):
    st.header("Legislative Co-Pilot")
    
    # --- 1. READ GLOBAL STATE (No local dropdown) ---
    api_key = st.session_state.get('groq_api_key')
    # This reads what you selected in the MAIN sidebar
    current_lang = st.session_state.get("global_lang", "English") 

    if not api_key:
        st.warning("Please enter Groq API Key in the Main Sidebar.")
        return

    # --- INPUT SOURCE SELECTOR ---
    source_type = st.radio("Source:", ["📂 Upload PDF", "💾 Internal Archive", "🌐 Live Web"], horizontal=True)
    bill_text = ""
    bill_title = "Document"

    # (File Upload Logic - Kept Simple for brevity)
    if source_type == "📂 Upload PDF":
        uploaded_file = st.file_uploader("Upload Bill", type="pdf")
        if uploaded_file:
            reader = PdfReader(uploaded_file)
            for page in reader.pages: bill_text += page.extract_text()
            bill_title = uploaded_file.name
    
    elif source_type == "💾 Internal Archive":
        if os.path.exists("bills_db.json"):
            df = load_data_from_json("bills_db.json")
            search_query = st.selectbox("Search Index:", df['title'].unique())
            if search_query:
                row = df[df['title'] == search_query].iloc[0]
                bill_text = row['content']
                bill_title = row['title']

    elif source_type == "🌐 Live Web":
        url = st.text_input("Paste URL")
        if url and st.button("Fetch"):
            try:
                r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
                bill_text = BeautifulSoup(r.content, 'html.parser').get_text()
                st.success("Fetched.")
            except: st.error("Failed.")

    # --- AI BRAIN ---
    if bill_text:
        st.divider()
        st.subheader(f"Analysis ({current_lang})")
        query = st.chat_input("Ask a question...")
        
        if query:
            with st.spinner("Analyzing..."):
                try:
                    llm = ChatGroq(temperature=0, groq_api_key=api_key, model_name="llama-3.1-8b-instant")
                    prompt = f"Answer based on text:\n{bill_text[:15000]}\nQuestion: {query}"
                    
                    # 1. Generate English
                    eng_response = llm.invoke(prompt).content
                    
                    # 2. Translate using Utility (Visible Errors)
                    final_output = perform_translation(eng_response, current_lang)
                    
                    # 3. Display
                    st.markdown(final_output)
                    
                    # 4. Actions
                    c1, c2 = st.columns([1,4])
                    with c1: 
                        if st.button("💾 Save"): 
                            # Import save_draft dynamically to avoid circular imports if necessary
                            from modules.persistence import save_draft 
                            save_draft(username, f"Analysis: {bill_title}", final_output)
                            track_action("Saved Analysis")
                    with c2: show_download_button(final_output, "Analysis")
                        
                except Exception as e:
                    st.error(f"AI Error: {e}")