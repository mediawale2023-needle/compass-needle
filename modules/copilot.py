import streamlit as st
import os
import json
import google.generativeai as genai
import pymupdf # Requires: pip install pymupdf
from io import BytesIO
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from modules.ui_theme import inject_theme, page_header, section_label, status_badge

# ============================================================
# RAJBHASHA INSTRUCTIONS
# ============================================================

RAJBHASHA_INSTRUCTIONS = """
LANGUAGE DIRECTIVE - HINDI OUTPUT:
You MUST use formal Rajbhasha Hindi throughout:
- "Assessment" = "आकलन", "Analysis" = "विश्लेषण", "Impact" = "प्रभाव"
- "Stakeholder" = "हितधारक", "Beneficiary" = "लाभार्थी", "Provision" = "प्रावधान"
- "Amendment" = "संशोधन", "Recommendation" = "अनुशंसा", "Evidence" = "साक्ष्य"
Use formal sentence structures. Avoid colloquial Hindi.
"""

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_gemini_model():
    """Configure and return Gemini model."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        api_key = st.session_state.get("GLOBAL_GEMINI_KEY")
    if not api_key:
        return None
    try:
        genai.configure(api_key=api_key)
        return genai.GenerativeModel('gemini-2.5-flash')
    except Exception as e:
        print(f"Gemini Error: {e}")
        return None


def extract_structured_pages(uploaded_file):
    """Extract text from PDF with page number preservation."""
    try:
        file_bytes = uploaded_file.read()
        doc = pymupdf.open(stream=file_bytes, filetype="pdf")
        pages_data = []
        for page_num, page in enumerate(doc):
            text = page.get_text("text")
            if text.strip():
                pages_data.append({"page": page_num + 1, "content": text})
        doc.close()
        return pages_data
    except Exception as e:
        st.error(f"PDF Extraction Error: {e}")
        return []


def get_document_context(pages_data, max_chars=100000):
    """Format pages into context string with page markers."""
    context_parts = []
    total_chars = 0
    for p in pages_data:
        page_text = f"\n\n--- PAGE {p['page']} ---\n{p['content']}"
        if total_chars + len(page_text) > max_chars:
            context_parts.append(f"\n\n[TRUNCATED: {len(pages_data) - len(context_parts)} more pages]")
            break
        context_parts.append(page_text)
        total_chars += len(page_text)
    return "".join(context_parts)


def save_analysis_to_disk(content, analysis_type, filename):
    """Save analysis with audit trail."""
    folder = "copilot_analyses"
    if not os.path.exists(folder):
        os.makedirs(folder)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c for c in filename if c.isalnum() or c in (' ', '_', '-')).strip()[:30]
    filepath = f"{folder}/{analysis_type}_{timestamp}_{safe_name}.md"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return filepath


# ============================================================
# BACKEND FUNCTION (For WhatsApp/API Integration)
# ============================================================

def ask_agent(prompt, tenant_id=1):
    """Standalone function for Backend (FastAPI/WhatsApp)."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "Error: GEMINI_API_KEY not found."
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        full_prompt = f"System: You are a helpful political aide named 'Needle'. Keep answers concise (under 200 words) for WhatsApp.\nUser: {prompt}"
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        print(f"Gemini Backend Error: {e}")
        return "I am currently overloaded. Please try again later."

ask_groq_agent = ask_agent


# ============================================================
# MAIN RENDER FUNCTION
# ============================================================

def render_copilot(username):
    """Document Co-Pilot — two tabs: Analyse + Ask."""

    inject_theme()

    # --- Session State ---
    if 'pages_data' not in st.session_state:
        st.session_state.pages_data = []
    if 'copilot_filename' not in st.session_state:
        st.session_state.copilot_filename = ""
    if 'analysis_result' not in st.session_state:
        st.session_state.analysis_result = ""
    if 'analysis_type' not in st.session_state:
        st.session_state.analysis_type = ""
    if 'copilot_chat_history' not in st.session_state:
        st.session_state.copilot_chat_history = []

    # --- Header ---
    page_header("Document Co-Pilot", "Strategic Intelligence for Parliamentary Use")

    col_spacer, col_btn = st.columns([5, 1])
    with col_btn:
        if st.button("New Analysis", use_container_width=True):
            st.session_state.pages_data = []
            st.session_state.copilot_filename = ""
            st.session_state.analysis_result = ""
            st.session_state.analysis_type = ""
            st.session_state.copilot_chat_history = []
            st.rerun()

    # --- Document Upload ---
    if not st.session_state.pages_data:
        st.markdown('<p class="section-label">Upload Document</p>', unsafe_allow_html=True)

        upload_col1, upload_col2 = st.columns([2, 1])
        with upload_col1:
            uploaded_file = st.file_uploader(
                "Upload Legislative Document (PDF)",
                type=["pdf"],
                help="Bills, Acts, Ordinances, Committee Reports, Policy Documents",
                label_visibility="collapsed"
            )
            if uploaded_file:
                with st.spinner("Extracting document structure..."):
                    st.session_state.pages_data = extract_structured_pages(uploaded_file)
                    st.session_state.copilot_filename = uploaded_file.name
                    if st.session_state.pages_data:
                        st.rerun()
                    else:
                        st.error("Failed to extract text from PDF.")
        with upload_col2:
            st.markdown("**Supported Formats**")
            st.caption("Bills & Acts \u00b7 Ordinances \u00b7 Committee Reports \u00b7 Policy Documents \u00b7 Budget Documents")
        return

    # --- Document Loaded ---
    status_badge(f"<strong>Active Document:</strong> {st.session_state.copilot_filename} &middot; {len(st.session_state.pages_data)} pages")

    col_spacer2, col_change = st.columns([5, 1])
    with col_change:
        if st.button("Change Document", use_container_width=True):
            st.session_state.pages_data = []
            st.session_state.copilot_filename = ""
            st.session_state.analysis_result = ""
            st.session_state.copilot_chat_history = []
            st.rerun()

    # --- Two Tabs ---
    tab_analyse, tab_ask = st.tabs(["Analyse", "Ask"])

    model = get_gemini_model()
    if not model:
        st.error("AI Model not connected. Add GEMINI_API_KEY to environment variables.")
        return

    # ==========================================================
    # TAB 1: ANALYSE
    # ==========================================================
    with tab_analyse:
        st.markdown('<p class="section-label">Comprehensive Document Analysis</p>', unsafe_allow_html=True)
        st.caption("One-click analysis covering legal risks, stakeholder impact, and parliamentary talking points.")

        col1, col2 = st.columns(2)
        with col1:
            analyse_language = st.selectbox("Language", ["English", "Hindi", "Bilingual"], key="analyse_lang")
        with col2:
            analyse_depth = st.radio("Depth", ["Quick Scan", "Comprehensive"], index=0, horizontal=True, key="analyse_depth")

        if st.button("Run Analysis", type="primary", use_container_width=True, key="btn_analyse"):
            with st.spinner("Analysing document..."):
                context = get_document_context(st.session_state.pages_data)
                lang_instruction = RAJBHASHA_INSTRUCTIONS if "Hindi" in analyse_language else ""
                depth_note = "Focus on top 5 most significant findings." if analyse_depth == "Quick Scan" else "Be comprehensive."

                prompt = f"""
ROLE: Senior Parliamentary Research Officer.
TASK: Intelligence briefing on this document for a Member of Parliament.

DOCUMENT: {st.session_state.copilot_filename}

{context}

PRODUCE THESE SECTIONS:

## Executive Summary
3-4 line summary: what this document is and why it matters.

## Key Risks and Red Flags
| Clause/Section | Risk Level (High/Medium/Low) | Issue | Implication | Citation |
|---|---|---|---|---|

## Stakeholder Impact
- Beneficiaries: who gains and how
- Adversely Affected: who loses and how
- Constituency Impact: effect on the MP's voters

## Talking Points for Parliament
3-5 ready-to-use arguments — both FOR and AGAINST positions.

## Recommended Action
Support, oppose, or seek amendments — with specific suggestions.

RULES:
1. {depth_note}
2. Every claim must cite [Page X].
3. If inferring, mark [INFERENCE].
4. Language: {analyse_language}
{lang_instruction}
"""
                try:
                    response = model.generate_content(prompt)
                    result_text = response.text
                    st.session_state.analysis_result = result_text
                    st.session_state.analysis_type = "Document_Analysis"
                    st.session_state.copilot_chat_history.append({"role": "user", "parts": ["Analyse this document."]})
                    st.session_state.copilot_chat_history.append({"role": "model", "parts": [result_text]})
                    st.rerun()
                except Exception as e:
                    st.error(f"Analysis Error: {e}")

    # ==========================================================
    # TAB 2: ASK
    # ==========================================================
    with tab_ask:
        st.markdown('<p class="section-label">Ask Anything About This Document</p>', unsafe_allow_html=True)
        st.caption("The AI retains context from your analysis and previous questions.")

        chat_history = st.session_state.copilot_chat_history
        if chat_history:
            with st.container(height=350):
                for msg in chat_history:
                    role = msg["role"]
                    text = msg["parts"][0] if msg["parts"] else ""
                    if role == "user":
                        st.markdown(f'<div class="chat-user">{text}</div>', unsafe_allow_html=True)
                    else:
                        with st.expander("Response", expanded=False):
                            st.markdown(text)
            st.caption(f"{len([m for m in chat_history if m['role'] == 'user'])} questions in this session")
        else:
            st.info("Run an analysis first, then ask follow-up questions here.")

        custom_query = st.text_input(
            "Your question",
            placeholder="e.g., What is the budget implication of clause 3?",
            key="custom_query",
            label_visibility="collapsed"
        )

        btn_col1, btn_col2 = st.columns([4, 1])
        with btn_col1:
            send_pressed = st.button("Submit", type="primary", use_container_width=True, key="btn_ask")
        with btn_col2:
            if st.button("Clear", use_container_width=True, key="btn_clear_chat"):
                st.session_state.copilot_chat_history = []
                st.session_state.analysis_result = ""
                st.rerun()

        if send_pressed:
            if not custom_query:
                st.warning("Please enter a question.")
            else:
                with st.spinner("Searching document..."):
                    context = get_document_context(st.session_state.pages_data)
                    system_prompt = f"""
You are a Senior Legislative Research Officer. Answer based ONLY on this document.

DOCUMENT: {st.session_state.copilot_filename}
{context}

RULES:
1. Every claim must cite [Page X].
2. If not in the document: "This information is not found in the document."
3. If inferring: mark [INFERENCE].
4. Be concise and actionable.
Use the full conversation history for contextual follow-ups.
"""
                    try:
                        chat = model.start_chat(history=chat_history)
                        response = chat.send_message(f"{system_prompt}\n\nQUERY: {custom_query}")
                        result_text = response.text
                        st.session_state.copilot_chat_history.append({"role": "user", "parts": [custom_query]})
                        st.session_state.copilot_chat_history.append({"role": "model", "parts": [result_text]})
                        st.session_state.analysis_result = result_text
                        st.session_state.analysis_type = "Custom_Query"
                        st.rerun()
                    except Exception as e:
                        st.error(f"Query Error: {e}")

    # ==========================================================
    # RESULTS
    # ==========================================================
    if st.session_state.analysis_result:
        st.divider()

        result_header_col1, result_header_col2 = st.columns([4, 1])
        with result_header_col1:
            label = "Analysis Results" if st.session_state.analysis_type == "Document_Analysis" else "Response"
            st.markdown(f"### {label}")
        with result_header_col2:
            if st.button("Clear", key="clear_results"):
                st.session_state.analysis_result = ""
                st.session_state.analysis_type = ""
                st.rerun()

        result_text = st.session_state.analysis_result
        has_verify = "[VERIFY" in result_text or "[ESTIMATE" in result_text or "[INFERENCE" in result_text
        if has_verify:
            st.warning("This analysis contains items marked for verification. Cross-check before official use.")

        st.markdown(f'<div class="result-container">', unsafe_allow_html=True)
        st.markdown(result_text)
        st.markdown('</div>', unsafe_allow_html=True)

        action_col1, action_col2, action_col3 = st.columns(3)
        with action_col1:
            if st.button("Save to Archives", use_container_width=True, key="save_result"):
                filepath = save_analysis_to_disk(result_text, st.session_state.analysis_type, st.session_state.copilot_filename)
                st.success(f"Saved: {filepath}")
        with action_col2:
            st.download_button(
                "Download",
                result_text,
                file_name=f"{st.session_state.analysis_type}_{st.session_state.copilot_filename[:20]}.md",
                use_container_width=True
            )
        with action_col3:
            if st.button("Re-run", use_container_width=True, key="rerun"):
                st.session_state.analysis_result = ""
                st.rerun()

        with st.expander("Metadata"):
            st.caption(f"**Document:** {st.session_state.copilot_filename}")
            st.caption(f"**Type:** {st.session_state.analysis_type}")
            st.caption(f"**Generated:** {datetime.now().strftime('%d %B %Y, %H:%M')}")
            st.caption(f"**Pages:** {len(st.session_state.pages_data)}")
            st.caption("**Status:** Draft — requires verification before official use")

    # --- Footer ---
    st.divider()
    st.caption("All analyses are for research and preparation purposes only. Verify citations before official use. This tool does not constitute legal advice.")