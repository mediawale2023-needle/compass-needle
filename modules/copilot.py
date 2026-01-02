import streamlit as st
import pymupdf  
from modules.settings import get_valid_model, init_keys

def extract_structured_pages(uploaded_file):
    """Extracts text while preserving page numbers for citations."""
    try:
        file_bytes = uploaded_file.read()
        doc = pymupdf.open(stream=file_bytes, filetype="pdf")
        pages_data = []
        for page_num, page in enumerate(doc):
            text = page.get_text("text")
            if text.strip():
                pages_data.append({
                    "page": page_num + 1,
                    "content": text
                })
        return pages_data
    except Exception as e:
        st.error(f"Extraction Error: {e}")
        return []

def render_copilot(username):
    # --- 1. PERSISTENCE ---
    if 'pages_data' not in st.session_state: st.session_state.pages_data = []
    if 'copilot_filename' not in st.session_state: st.session_state.copilot_filename = ""
    if 'cp_result' not in st.session_state: st.session_state.cp_result = ""

    init_keys()

    # --- 2. HEADER ---
    c_head1, c_head2 = st.columns([4, 1])
    with c_head1:
        st.title("🤖 Co-Pilot (Intelligent Research)")
        st.caption(f"Authenticated: {username} | Auto-Detecting Intent & Language")
    with c_head2:
        if st.button("🔄 New Research"):
            st.session_state.pages_data = []
            st.session_state.copilot_filename = ""
            st.session_state.cp_result = ""
            st.rerun()

    st.divider()

    # --- 3. INPUT ---
    c1, c2 = st.columns([1, 1])
    with c1:
        if not st.session_state.pages_data:
            f = st.file_uploader("Upload Document (PDF)", type="pdf")
            if f:
                with st.spinner("Processing..."):
                    st.session_state.pages_data = extract_structured_pages(f)
                    st.session_state.copilot_filename = f.name
                    st.rerun()
        else:
            st.success(f"✅ Active: **{st.session_state.copilot_filename}**")
            if st.button("Change File"):
                st.session_state.pages_data = []; st.rerun()

    with c2:
        query = st.text_area("Research Query", placeholder="e.g., Critique this bill from an opposition viewpoint.", height=100)
        output_lang = st.selectbox("Output Language", ["English", "Hindi", "Marathi", "Kannada"], index=0)

    # --- 4. ANALYSIS ---
    if st.button("🚀 Run Analysis", type="primary", use_container_width=True):
        if not st.session_state.pages_data:
            st.error("Upload a PDF first.")
        elif not query:
            st.error("Enter a query.")
        else:
            with st.spinner(f"Analyzing in {output_lang}..."):
                model = get_valid_model()
                if model:
                    # STEP 1: DETECT INTENT
                    classifier_prompt = f"Identify if this query is asking for a NEUTRAL summary, CRITICAL critique, or SUPPORTIVE view: '{query}'. Return only one word: NEUTRAL, CRITICAL, or SUPPORTIVE."
                    try:
                        detected_intent = model.generate_content(classifier_prompt).text.strip().upper()
                    except:
                        detected_intent = "NEUTRAL"

                    # STEP 2: DEFINE LENS
                    lenses = {
                        "CRITICAL": "LENS: Opposition Critic. Focus on loopholes, risks, and administrative failures.",
                        "SUPPORTIVE": "LENS: Government Proponent. Focus on national interest, efficiency, and solutions.",
                        "NEUTRAL": "LENS: Legislative Clerk. Focus on factual and balanced briefing."
                    }
                    active_lens = lenses.get(detected_intent, lenses["NEUTRAL"])

                    # STEP 3: EXECUTE WITH LANGUAGE ENFORCEMENT
                    full_context = "".join([f"\n--- PAGE {p['page']} ---\n{p['content']}" for p in st.session_state.pages_data])
                    
                    prompt = f"""
                    {active_lens}
                    TASK: Answer the query based ONLY on the doc.
                    DOC: {st.session_state.copilot_filename}
                    CONTEXT: {full_context[:100000]}
                    
                    STRICT RULES:
                    1. LANGUAGE: You MUST write the entire response in {output_lang}. 
                    2. CITATIONS: Include [Page X] for every fact.
                    3. QUERY: {query}
                    
                    STRUCTURE:
                    # Briefing Note ({detected_intent})
                    ### 1. Executive Summary
                    ### 2. Legal/Political Analysis
                    ### 3. Recommendations
                    """
                    
                    try:
                        resp = model.generate_content(prompt)
                        st.session_state.cp_result = f"**Perspective: {detected_intent}**\n\n" + resp.text
                        st.rerun()
                    except Exception as e:
                        st.error(f"AI Error: {e}")

    # --- 5. RESULT ---
    if st.session_state.cp_result:
        with st.container(border=True):
            st.markdown(st.session_state.cp_result)
        st.download_button("📥 Download", st.session_state.cp_result, f"Research_{output_lang}.md")