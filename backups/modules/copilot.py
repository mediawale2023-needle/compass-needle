import streamlit as st
from pypdf import PdfReader
from modules.settings import get_valid_model, init_keys

def extract_text(uploaded_file):
    try:
        reader = PdfReader(uploaded_file)
        text = [page.extract_text() for page in reader.pages[:100]] 
        return "\n".join(text)
    except: return ""

def render_copilot(username):
    # --- PERSISTENCE ---
    if 'copilot_doc_text' not in st.session_state: st.session_state.copilot_doc_text = ""
    if 'copilot_filename' not in st.session_state: st.session_state.copilot_filename = ""
    if 'copilot_query' not in st.session_state: st.session_state.copilot_query = ""
    if 'cp_result' not in st.session_state: st.session_state.cp_result = ""

    # --- HEADER ---
    c_head1, c_head2 = st.columns([4, 1])
    with c_head1:
        st.title("🤖 Co-Pilot (Deep Research)")
        st.caption("Upload Bills or Acts.")
    with c_head2:
        if st.button("🔄 New Research"):
            st.session_state.copilot_doc_text = ""
            st.session_state.copilot_filename = ""
            st.session_state.copilot_query = ""
            st.session_state.cp_result = ""
            st.rerun()
    
    init_keys()

    # --- INPUT ---
    c1, c2 = st.columns([1, 1])
    with c1:
        if not st.session_state.copilot_doc_text:
            f = st.file_uploader("Upload Document (PDF)", type="pdf")
            if f:
                with st.spinner("Processing..."):
                    text = extract_text(f)
                    if text:
                        st.session_state.copilot_doc_text = text
                        st.session_state.copilot_filename = f.name
                        st.rerun()
        else:
            st.success(f"✅ Active: **{st.session_state.copilot_filename}**")
            with st.expander("Change File"):
                new_f = st.file_uploader("Upload New PDF", type="pdf")
                if new_f:
                    st.session_state.copilot_doc_text = extract_text(new_f)
                    st.session_state.copilot_filename = new_f.name
                    st.rerun()

    with c2:
        st.session_state.copilot_query = st.text_area("Research Query", value=st.session_state.copilot_query, height=100)
        output_lang = st.selectbox("Language", ["English", "Hindi", "Marathi", "Kannada"], index=0)

    st.divider()

    # --- ANALYSIS ---
    if st.button("🚀 Run Deep Analysis", type="primary"):
        txt = st.session_state.copilot_doc_text
        qry = st.session_state.copilot_query
        
        if txt and qry:
            with st.spinner(f"Analyzing in {output_lang}..."):
                # 👇 AUTO-DETECT MODEL
                model = get_valid_model()
                if model:
                    prompt = f"""
                    ROLE: Legislative Expert.
                    TASK: Formal Briefing Note.
                    QUERY: {qry}
                    DOC: {txt[:80000]}
                    LANGUAGE: {output_lang}
                    
                    RULES: No filler. Start with Header.
                    
                    OUTPUT STRUCTURE:
                    # Briefing Note: [Topic]
                    ### 1. Executive Summary
                    ### 2. Legal Risks
                    ### 3. Economic Impact
                    ### 4. Recommendation
                    """
                    try:
                        resp = model.generate_content(prompt)
                        st.session_state.cp_result = resp.text
                        st.rerun()
                    except Exception as e:
                        st.error(f"AI Error: {e}")
                else:
                    st.error("System Offline. Check Settings.")
        
        elif not txt: st.error("Upload PDF first.")
        elif not qry: st.error("Enter a query.")

    # --- RESULT ---
    if st.session_state.cp_result:
        st.subheader(f"📝 Briefing Note ({output_lang})")
        with st.container(border=True):
            st.markdown(st.session_state.cp_result)
        st.download_button("📥 Download", st.session_state.cp_result, "Brief.txt")