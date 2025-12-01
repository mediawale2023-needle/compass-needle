import streamlit as st
from langchain_groq import ChatGroq
from pypdf import PdfReader
from deep_translator import GoogleTranslator
import requests
from bs4 import BeautifulSoup
import json
import pandas as pd
import os

# --- CACHED DATA LOADER (Prevents re-parsing JSON on every interaction) ---
@st.cache_data
def load_data_from_json(file_path_or_buffer):
    """Loads JSON data from file path or buffer and converts to DataFrame."""
    try:
        if isinstance(file_path_or_buffer, str):
            with open(file_path_or_buffer, 'r') as f:
                data = json.load(f)
        else:
            data = json.load(file_path_or_buffer)
            
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error loading JSON database: {e}")
        return pd.DataFrame()

# --- FILE UPLOADER PERSISTENCE HANDLER (BUG FIX) ---
def handle_file_upload_persistence():
    """Returns the uploaded file buffer, ensuring it persists across tabs via session state."""
    
    # If file is already in memory, use it
    if st.session_state.get('uploaded_file_data'):
        st.success(f"File persistent: {st.session_state.uploaded_file_name}")
        uploaded_file = st.session_state.uploaded_file_data
        
    else:
        # Show the uploader widget
        uploaded_file = st.file_uploader("Upload Document (PDF)", type="pdf", key="file_upload_widget")
        
        # If a new file is uploaded, save it to session state for persistence
        if uploaded_file is not None:
            st.session_state.uploaded_file_data = uploaded_file
            st.session_state.uploaded_file_name = uploaded_file.name
            st.rerun() # Rerun to remove the uploader widget and show the success message
            
    return st.session_state.get('uploaded_file_data')


def render_copilot():
    st.header("Legislative Co-Pilot (Classified)")
    
    # --- SIDEBAR CONFIGURATION (Key Entry Point) ---
    with st.sidebar:
        st.divider()
        st.header("🔐 Secure Access")
        
        # Centralized key input: reads and writes to session state immediately
        input_key = st.text_input(
            "Decryption Key (API)", 
            type="password", 
            value=st.session_state.get('groq_api_key', ''), # Pre-fill if key exists
            placeholder="gsk_..."
        )
        # If user types a key, save it to the shared state instantly
        if input_key and input_key != st.session_state.get('groq_api_key'):
             st.session_state.groq_api_key = input_key
             st.rerun()
             
        # Retrieve the shared key for this module's use
        api_key = st.session_state.get('groq_api_key')
        st.session_state.api_key = api_key # Store for internal module use
        
        st.caption("Get key from console.groq.com")
        
        st.divider()
        st.header("🗣️ Language")
        lang_option = st.selectbox(
            "Select Language", 
            ["English", "Hindi (हिंदी)", "Marathi (मराठी)", "Tamil (தமிழ்)"]
        )
    
    # Map selection to ISO language codes
    lang_map = {"English": "en", "Hindi (हिंदी)": "hi", "Marathi (मराठी)": "mr", "Tamil (தமிழ்)": "ta"}
    target_lang = lang_map[lang_option]
    
    # --- INPUT SOURCE SELECTOR ---
    source_type = st.radio(
        "Select Data Source:", 
        ["📂 Secure Upload", "💾 Internal Archive (Offline)", "🌐 Live Web Extraction"], 
        horizontal=True
    )
    
    bill_text = ""
    bill_title = "Classified Document"

    # --- MODE 1: PDF UPLOAD ---
    if source_type == "📂 Secure Upload":
        uploaded_file = handle_file_upload_persistence()
        
        if uploaded_file:
            pdf_buffer = uploaded_file
            if pdf_buffer:
                # Reset buffer position to start before reading
                pdf_buffer.seek(0)
                reader = PdfReader(pdf_buffer)
                
                for page in reader.pages:
                    bill_text += page.extract_text()
                    
                bill_title = st.session_state.uploaded_file_name
                st.caption(f"Loaded {len(reader.pages)} pages.")

    # --- MODE 2: INTERNAL ARCHIVE (Local JSON Database) ---
    elif source_type == "💾 Internal Archive (Offline)":
        df = None
        
        # Try to find the local file (bills_db.json) first
        file_path = "bills_db.json"
        if os.path.exists(file_path):
            df = load_data_from_json(file_path)
            st.toast("Secure connection to Local Node established.", icon="🔒")
        
        else:
            # Fallback: Ask user to upload
            st.warning("⚠️ Local Node Offline. Upload your database dump.")
            uploaded_json = st.file_uploader("Upload your 'bills_db.json' dump", type="json")
            if uploaded_json:
                df = load_data_from_json(uploaded_json)

        if df is not None and not df.empty:
            st.success(f"📚 Index Online: {len(df)} Records Available")
            
            # Search Interface
            search_query = st.selectbox("🔍 Search Intelligence Index:", df['title'].unique())
            
            if search_query:
                selected_row = df[df['title'] == search_query].iloc[0]
                bill_title = selected_row['title']
                bill_text = selected_row['content']
                
                with st.expander("📄 View Raw Intelligence", expanded=False):
                    st.caption(f"Verification ID: NDL-{abs(hash(bill_title)) % 100000}")
                    st.text(bill_text[:2000] + "...")

    # --- MODE 3: WEB EXTRACTOR ---
    elif source_type == "🌐 Live Web Extraction":
        url = st.text_input("Enter Target URL (e.g. PRS Link)")
        if url and st.button("Extract Data"):
            with st.spinner("Bypassing scraping protections..."):
                try:
                    headers = {'User-Agent': 'Mozilla/5.0'}
                    r = requests.get(url, headers=headers)
                    soup = BeautifulSoup(r.content, 'html.parser')
                    bill_title = soup.find('h1').text.strip() if soup.find('h1') else "Extracted Data"
                    
                    for p in soup.find_all('p'):
                        bill_text += p.get_text() + "\n"
                        
                    st.success(f"✅ Extraction Complete: {bill_title}")
                except Exception as e:
                    st.error(f"Extraction Failed: {e}")


    # --- AI ANALYSIS (The Brain) ---
    if bill_text and api_key:
        st.divider()
        st.subheader(f"🤖 Analyzing: {bill_title}")
        
        user_query = st.chat_input(f"Query the Intelligence Engine...")
        
        if user_query:
            with st.spinner("Processing & Translating..."):
                try:
                    # 1. Initialize Llama-3 (The Brain)
                    llm = ChatGroq(
                        temperature=0, 
                        groq_api_key=api_key, 
                        model_name="llama-3.1-8b-instant"
                    )
                    
                    # 2. Construct the Prompt (Context Stuffing: Limit text to 15k chars for free tier)
                    prompt = f"""
                    Act as a Senior Legislative Strategist. Answer the question based ONLY on the Bill Text provided below.
                    Keep the answer professional, concise, and structured with bullet points.
                    
                    Question: {user_query}
                    
                    Bill Text Context:
                    {bill_text[:15000]}
                    """
                    
                    # 3. Generate Answer (English Core)
                    english_response = llm.invoke(prompt).content
                    
                    # 4. Translate if needed
                    final_output = english_response
                    if target_lang != "en":
                        # Using Deep Translator (Stable for regional languages)
                        final_output = GoogleTranslator(source='auto', target=target_lang).translate(english_response)
                    
                    # 5. Display Result
                    st.markdown(f"### 💡 Strategic Insight ({lang_option})")
                    st.write(final_output)
                    
                except Exception as e:
                    st.error(f"AI Error: {e}. (Check your API Key or input size)")
    
    elif not api_key:
        st.info("👈 Enter Decryption Key (API) to proceed.")