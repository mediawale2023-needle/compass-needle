import streamlit as st
from langchain_groq import ChatGroq
from deep_translator import GoogleTranslator
from modules.utils import track_action, show_download_button
from modules.persistence import save_draft

def translate_text(text, target_lang_name):
    """Translates text if the target language is not English."""
    lang_map = {"English": "en", "Hindi (हिंदी)": "hi", "Marathi (मराठी)": "mr", "Tamil (தமிழ்)": "ta"}
    target_code = lang_map.get(target_lang_name, "en")
    
    if target_code != "en":
        try:
            return GoogleTranslator(source='auto', target=target_code).translate(text)
        except Exception:
            return text
    return text

def render_drafter(username):
    st.header("Legislative Drafter")
    
    # --- RETRIEVE GLOBAL CONTEXT ---
    api_key = st.session_state.get('groq_api_key')
    current_lang = st.session_state.get("global_lang", "English")

    if not api_key:
        st.warning("⚠️ Please enter the Groq API key in the Sidebar first.")
        return

    tab1, tab2, tab3, tab4 = st.tabs(["📄 Letters", "❓ Questions", "🎤 Zero Hour", "📱 Media"])

    # --- TAB 1: LETTERS ---
    with tab1:
        st.subheader(f"Official Correspondence ({current_lang})")
        c1, c2 = st.columns(2)
        with c1: letter_type = st.selectbox("Type", ["D.O. Letter", "Representation", "Sanction Request"], key="l_type")
        with c2: recip = st.text_input("Recipient", placeholder="e.g. District Collector", key="l_recip")
        
        subj = st.text_input("Subject", placeholder="Urgent Repair of NH-48", key="l_subj")
        ctx = st.text_area("Details (25+ words)", height=100, key="l_ctx")
        
        if st.button("Draft Letter", type="primary"):
            if len(ctx) < 5: st.error("More details needed.")
            else:
                with st.spinner(f"Drafting & Translating..."):
                    try:
                        llm = ChatGroq(temperature=0.5, groq_api_key=api_key, model_name="llama-3.1-8b-instant")
                        eng_draft = llm.invoke(f"Write a formal {letter_type} to {recip}. Subject: {subj}. Context: {ctx}. Tone: Official Indian Govt protocol.").content
                        
                        final_draft = translate_text(eng_draft, current_lang)
                        st.session_state['draft_letter'] = final_draft
                        track_action(f"Drafted Letter: {subj[:20]}")
                    except Exception as e: st.error(f"Error: {e}")

        if 'draft_letter' in st.session_state:
            st.text_area("Final Draft", st.session_state['draft_letter'], height=350)
            c1, c2 = st.columns([1, 4])
            with c1:
                if st.button("💾 Save", key="save_let"): save_draft(username, f"Letter: {subj}", st.session_state['draft_letter'], "Letter")
            with c2: show_download_button(st.session_state['draft_letter'], "Official_Letter")

    # --- TAB 2: QUESTIONS ---
    with tab2:
        st.subheader("Parliamentary Questions")
        minis = st.text_input("Ministry", placeholder="Railways", key="pq_min")
        topic = st.text_input("Topic", placeholder="Safety", key="pq_top")
        
        if st.button("Generate PQs"):
            with st.spinner("Generating..."):
                llm = ChatGroq(temperature=0.4, groq_api_key=api_key, model_name="llama-3.1-8b-instant")
                # PQs are usually English/Hindi standard, so we keep them in English for accuracy
                prompt = f"Generate 3 Starred Questions for {minis} regarding {topic}. Format: (a)-(d)."
                st.session_state['draft_pq'] = llm.invoke(prompt).content
                track_action(f"Generated PQ: {topic}")
        
        if 'draft_pq' in st.session_state:
            st.code(st.session_state['draft_pq'], language="text")
            c1, c2 = st.columns([1, 4])
            with c1:
                if st.button("💾 Save", key="save_pq"): save_draft(username, f"PQ: {topic}", st.session_state['draft_pq'], "Question")
            with c2: show_download_button(st.session_state['draft_pq'], "Parl_Question")

    # --- TAB 3: ZERO HOUR ---
    with tab3:
        st.subheader(f"Zero Hour Speech ({current_lang})")
        issue = st.text_input("Urgent Issue", placeholder="Water Crisis", key="zh_issue")
        
        if st.button("Draft Speech"):
            with st.spinner("Writing..."):
                llm = ChatGroq(temperature=0.7, groq_api_key=api_key, model_name="llama-3.1-8b-instant")
                eng_speech = llm.invoke(f"Write a 250-word Zero Hour speech about {issue}. Start 'Hon'ble Speaker Sir,'").content
                
                final_speech = translate_text(eng_speech, current_lang)
                st.session_state['draft_speech'] = final_speech
                track_action(f"Drafted Speech: {issue}")
        
        if 'draft_speech' in st.session_state:
            st.text_area("Script", st.session_state['draft_speech'], height=300)
            c1, c2 = st.columns([1, 4])
            with c1:
                if st.button("💾 Save", key="save_zh"): save_draft(username, f"Speech: {issue}", st.session_state['draft_speech'], "Zero Hour")
            with c2: show_download_button(st.session_state['draft_speech'], "Zero_Hour")

    # --- TAB 4: MEDIA ---
    with tab4:
        st.subheader("Media Spin")
        raw_text = st.text_area("Paste Content:", height=100, key="media_in")
        platform = st.radio("Target:", ["X Thread", "WhatsApp", "Press Note"], horizontal=True)
        
        if st.button("Generate"):
            with st.spinner("Converting..."):
                llm = ChatGroq(temperature=0.8, groq_api_key=api_key, model_name="llama-3.1-8b-instant")
                res = llm.invoke(f"Convert this to a {platform} for an Indian MP: {raw_text}").content
                st.session_state['draft_media'] = res
                track_action("Generated Media Content")
        
        if 'draft_media' in st.session_state:
            st.markdown(st.session_state['draft_media'])
            c1, c2 = st.columns([1, 4])
            with c1:
                if st.button("💾 Save", key="save_med"): save_draft(username, f"Media: {platform}", st.session_state['draft_media'], "Media")
            with c2: show_download_button(st.session_state['draft_media'], "Media_Post")