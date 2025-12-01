import streamlit as st
from langchain_groq import ChatGroq
from deep_translator import GoogleTranslator
from modules.utils import track_action, show_download_button
from modules.persistence import save_draft

# --- HELPER FUNCTIONS ---
def get_api_key():
    return st.session_state.get('groq_api_key')

def translate_text(text, target_lang_code):
    if target_lang_code != "en":
        try:
            return GoogleTranslator(source='auto', target=target_lang_code).translate(text)
        except Exception:
            return text
    return text

def render_drafter(username):
    st.header("✍️ Legislative Drafter")
    
    # 1. GET CREDENTIALS & LANGUAGE
    api_key = get_api_key()
    lang_option = st.session_state.get("global_lang", "English")
    lang_map = {"English": "en", "Hindi (हिंदी)": "hi", "Marathi (मराठी)": "mr", "Tamil (தமிழ்)": "ta"}
    target_code = lang_map.get(lang_option, "en")

    if not api_key:
        st.warning("Please enter Groq API Key in the Sidebar.")
        return

    # 2. TABS
    tab1, tab2, tab3, tab4 = st.tabs(["📄 Letters", "❓ Questions", "🎤 Zero Hour", "📱 Media"])

    # ==========================================
    # TAB 1: OFFICIAL CORRESPONDENCE
    # ==========================================
    with tab1:
        st.subheader(f"Official Communication ({lang_option})")
        
        c1, c2 = st.columns(2)
        with c1: letter_type = st.selectbox("Type", ["D.O. Letter", "Representation", "Sanction Request"], key="l_type")
        with c2: recip = st.text_input("Recipient", placeholder="e.g. District Collector", key="l_recip")
        
        subj = st.text_input("Subject", placeholder="Urgent Repair of NH-48", key="l_subj")
        ctx = st.text_area("Details (25+ words)", height=100, key="l_ctx")
        
        if st.button("Draft Letter", type="primary"):
            if len(ctx) < 5:
                st.error("Please provide more details.")
            else:
                with st.spinner(f"Drafting & Translating..."):
                    try:
                        llm = ChatGroq(temperature=0.5, groq_api_key=api_key, model_name="llama-3.1-8b-instant")
                        prompt = f"Write a formal {letter_type} from an Indian MP to {recip}. Subject: {subj}. Context: {ctx}. Tone: Official Indian Govt protocol."
                        
                        eng_draft = llm.invoke(prompt).content
                        final_draft = translate_text(eng_draft, target_code)
                        
                        st.session_state['draft_letter'] = final_draft
                        track_action(f"Drafted Letter: {subj[:20]}")
                    except Exception as e:
                        st.error(f"Error: {e}")

        if 'draft_letter' in st.session_state:
            st.text_area("Final Draft", st.session_state['draft_letter'], height=400)
            
            c1, c2 = st.columns([1, 4])
            with c1:
                if st.button("💾 Save", key="save_let"):
                    save_draft(username, f"Letter: {subj}", st.session_state['draft_letter'], "Letter")
            with c2:
                show_download_button(st.session_state['draft_letter'], "Official_Letter")

    # ==========================================
    # TAB 2: PARLIAMENTARY QUESTIONS (STRICT MODE)
    # ==========================================
    with tab2:
        st.subheader("Generate Bulk Parliamentary Questions")
        st.caption("Generates 5 distinct questions with 4+ sub-questions each.")
        
        minis = st.text_input("Ministry", placeholder="Ministry of Railways", key="pq_min")
        topic = st.text_input("Topic", placeholder="Safety Standards / Kavach System", key="pq_top")
        
        if st.button("Generate 5 PQs"):
            if not minis or not topic:
                st.error("Please enter Ministry and Topic.")
            else:
                with st.spinner("Generating 5 High-Impact Questions..."):
                    try:
                        llm = ChatGroq(temperature=0.6, groq_api_key=api_key, model_name="llama-3.1-8b-instant")
                        
                        full_output = []
                        
                        # LOOP TO GENERATE 5 SEPARATE QUESTIONS
                        for i in range(1, 6):
                            prompt = f"""
                            TASK: Act as a Legislative Research Analyst for the Indian Parliament.
                            GENERATE Starred Parliamentary Question #{i} for the {minis} regarding '{topic}'.
                            
                            STRICT FORMAT RULES:
                            1. Start strictly with: "Will the Minister of {minis} be pleased to state:"
                            2. You MUST generate distinct sub-questions labeled (a), (b), (c), and (d).
                            3. Optionally add (e) if relevant.
                            4. Content Requirements:
                               (a) Ask about the current status/awareness of the issue.
                               (b) Ask for specific state-wise data or statistics.
                               (c) Ask about funds allocated vs utilized in the last 3 years.
                               (d) Ask about the time-bound steps taken by the Government to resolve it.
                            
                            Do not add conversational filler. Just the question text.
                            """
                            response = llm.invoke(prompt).content
                            full_output.append(f"### QUESTION {i}\n{response}")

                        # Join all 5 questions into one block
                        combined_text = "\n\n---\n\n".join(full_output)
                        st.session_state['draft_pq'] = combined_text
                        track_action(f"Generated 5 PQs: {topic}")
                        
                    except Exception as e:
                        st.error(f"Generation Error: {e}")
        
        if 'draft_pq' in st.session_state:
            st.text_area("Generated Questions", st.session_state['draft_pq'], height=500)
            
            c1, c2 = st.columns([1, 4])
            with c1:
                if st.button("💾 Save", key="save_pq"):
                    save_draft(username, f"5 PQs: {topic}", st.session_state['draft_pq'], "Question")
            with c2:
                show_download_button(st.session_state['draft_pq'], "Parl_Questions")

    # ==========================================
    # TAB 3: ZERO HOUR SPEECH
    # ==========================================
    with tab3:
        st.subheader(f"Zero Hour Speech ({lang_option})")
        issue = st.text_input("Urgent Issue", placeholder="Bridge Collapse / Water Crisis", key="zh_issue")
        
        if st.button("Draft Speech"):
            with st.spinner("Writing Speech..."):
                try:
                    llm = ChatGroq(temperature=0.7, groq_api_key=api_key, model_name="llama-3.1-8b-instant")
                    eng_speech = llm.invoke(f"Write a passionate 250-word Zero Hour speech for an Indian MP about: {issue}. Start with 'Hon'ble Speaker Sir,' and end with a specific demand for action.").content
                    
                    final_speech = translate_text(eng_speech, target_code)
                    st.session_state['draft_speech'] = final_speech
                    track_action(f"Drafted Speech: {issue}")
                except Exception as e:
                    st.error(f"Error: {e}")
        
        if 'draft_speech' in st.session_state:
            st.text_area("Script", st.session_state['draft_speech'], height=300)
            c1, c2 = st.columns([1, 4])
            with c1:
                if st.button("💾 Save", key="save_zh"):
                    save_draft(username, f"Speech: {issue}", st.session_state['draft_speech'], "Zero Hour")
            with c2:
                show_download_button(st.session_state['draft_speech'], "Zero_Hour")

    # ==========================================
    # TAB 4: MEDIA SPIN
    # ==========================================
    with tab4:
        st.subheader("Amplification Engine")
        content_source = st.text_area("Paste Text to Spin:", height=100, key="media_in")
        platform = st.radio("Target:", ["X Thread", "WhatsApp Forward", "Press Note"], horizontal=True)
        
        if st.button("Generate Post"):
            if not content_source:
                st.error("Please paste content.")
            else:
                with st.spinner("Converting..."):
                    try:
                        llm = ChatGroq(temperature=0.8, groq_api_key=api_key, model_name="llama-3.1-8b-instant")
                        res = llm.invoke(f"Convert this text into a viral {platform} for an Indian Politician. Text: {content_source}").content
                        st.session_state['draft_media'] = res
                        track_action("Generated Media Content")
                    except Exception as e:
                        st.error(f"Error: {e}")
        
        if 'draft_media' in st.session_state:
            st.markdown(st.session_state['draft_media'])
            c1, c2 = st.columns([1, 4])
            with c1:
                if st.button("💾 Save", key="save_med"):
                    save_draft(username, f"Media: {platform}", st.session_state['draft_media'], "Media")
            with c2:
                show_download_button(st.session_state['draft_media'], "Media_Post")