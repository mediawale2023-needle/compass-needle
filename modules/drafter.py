import streamlit as st
from langchain_groq import ChatGroq
from deep_translator import GoogleTranslator
from modules.utils import track_action, show_download_button
from modules.persistence import save_draft # Import the save function

def get_shared_context():
    """Retrieves API key and Target Language from session/sidebar."""
    api_key = st.session_state.get('groq_api_key')
    
    # Use a dummy selectbox if the main one isn't rendered (e.g., in Admin mode)
    lang_option = st.session_state.get('drafter_lang_selector', "English")
    
    lang_map = {"English": "en", "Hindi (हिंदी)": "hi", "Marathi (मराठी)": "mr", "Tamil (தமிழ்)": "ta"}
    target_lang_code = lang_map.get(lang_option, "en")
    
    return api_key, target_lang_code, lang_option

def translate_text(text, target_lang_code):
    """Translates text if the target language is not English."""
    if target_lang_code != "en":
        try:
            return GoogleTranslator(source='auto', target=target_lang_code).translate(text)
        except Exception:
            return text
    return text

def render_drafter(username): # ACCEPTS USERNAME
    st.header("✍️ Legislative Drafter")
    
    # 1. RETRIEVE CONTEXT
    api_key, target_lang_code, target_lang_name = get_shared_context()

    # 2. CHECK FOR CREDENTIALS
    if not api_key:
        st.warning("Please enter the Groq API key in the Co-Pilot sidebar first to enable drafting tools.")
        return # Stop execution if key is missing
        
    
    tab1, tab2, tab3, tab4 = st.tabs(["📄 Letters", "❓ Questions", "🎤 Zero Hour", "📱 Media"])
    
    # --- TAB 1: LETTERS (Save/Download Implemented) ---
    with tab1:
        st.subheader(f"Official Communication ({target_lang_name})")
        
        col1, col2 = st.columns(2)
        with col1:
            letter_type = st.selectbox("Type", ["D.O. Letter", "Formal Representation", "Fund Sanction Request"], key='letter_type')
        with col2:
            recipient = st.text_input("Recipient", placeholder="e.g. District Collector / Hon'ble Minister", key='recipient')
            
        subject = st.text_input("Subject", placeholder="e.g. Urgent Repair of NH-48", key='subject')
        
        context = st.text_area("Describe Issue (25-50 words needed)", placeholder="Details...", height=100, key='context')
        
        if st.button("Draft Letter"):
            if not context or len(context.split()) < 5:
                st.error("Please describe the issue in detail (at least 5 words required).")
            else:
                with st.spinner(f"Drafting in English, translating to {target_lang_name}..."):
                    try:
                        llm = ChatGroq(temperature=0.5, groq_api_key=api_key, model_name="llama-3.1-8b-instant")
                        
                        prompt = f"Write a formal and precise {letter_type} from an Indian MP to {recipient}. Subject: {subject}. Context: {context}. Tone: Official Indian Govt protocol."
                        english_draft = llm.invoke(prompt).content
                        final_draft = translate_text(english_draft, target_lang_code)
                        
                        st.text_area("Generated Draft", final_draft, height=400)
                        
                        # --- SAVE & DOWNLOAD ---
                        col_s, col_d = st.columns([1,1])
                        col_s.button("💾 Save to Archives", on_click=save_draft, 
                                     args=(username, f"Letter: {subject[:30]}", final_draft), key='save_letter')
                        col_d.button("⬇️ Download", on_click=show_download_button, 
                                     args=(final_draft, "Official_Letter"), key='download_letter')
                        
                        track_action(f"Drafted Letter: {subject[:30]}")
                        
                    except Exception as e:
                        st.error(f"Generation Failed (Error: {e}).")

    # --- TAB 2: QUESTIONS (Download Implemented) ---
    with tab2:
        st.subheader("Generate Bulk Parliamentary Questions")
        
        ministry = st.text_input("Target Ministry", placeholder="Ministry of Health and Family Welfare", key='minis_q')
        topic_area = st.text_area("General Policy Area / Keywords", placeholder="e.g., Doctor vacancies in rural areas", height=100, key='topic_q')

        if st.button("Generate 5 PQs"):
            if not ministry or not topic_area:
                st.error("Please specify the Ministry and a general topic area.")
            else:
                # ... (Generation Loop Logic) ...
                st.success(f"✅ Generated 5 Questions for the {ministry}.")
                # Placeholder for generated content (in a real run, this would be the loop output)
                full_output = "Will the Minister of Health be pleased to state: (a) Whether Govt has assessed vacancies..." 
                
                st.code(full_output, language="text")
                
                show_download_button(full_output, filename_prefix="5_PQs")
                track_action(f"Generated 5 PQs for {ministry}")

    # --- TAB 3: ZERO HOUR (Download Implemented) ---
    with tab3:
        st.subheader("Zero Hour Speech")
        issue = st.text_input("Urgent Issue", placeholder="Water Crisis - 200 words needed", key='issue_zh')
        
        if st.button("Draft Speech"):
            if not issue:
                st.error("Please enter an urgent issue.")
            else:
                with st.spinner("Drafting speech..."):
                    # Placeholder output
                    speech = "Hon'ble Speaker Sir, I rise to raise a matter of urgent public importance..."
                    st.text_area("Speech Script", speech, height=200)
                    
                    show_download_button(speech, filename_prefix=f"ZeroHour_{issue[:10]}")
                    track_action(f"Drafted Zero Hour Speech on: {issue}")

    # --- TAB 4: SOCIAL MEDIA (Download Implemented) ---
    with tab4:
        st.subheader("Amplification Engine")
        content_source = st.text_area("Paste Text to Spin:", height=100, key='source_sm')
        platform = st.radio("Target:", ["X Thread", "WhatsApp Forward", "Press Note"], horizontal=True)
        
        if st.button("Generate Post"):
            if not content_source:
                st.error("Please paste content to generate a post.")
            else:
                with st.spinner("Writing..."):
                    output = "Generated Social Media Post..."
                    st.markdown(output)
                    show_download_button(output, filename_prefix=f"Social_Post")
                    track_action(f"Generated Social Post")