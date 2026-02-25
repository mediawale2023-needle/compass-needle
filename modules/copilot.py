import streamlit as st
import os
import json
import google.generativeai as genai
import pymupdf  # Requires: pip install pymupdf
from io import BytesIO
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# CONFIGURATION & PROMPTS
# ============================================================

# Rajbhasha (Formal Hindi) Instructions
RAJBHASHA_INSTRUCTIONS = """
LANGUAGE DIRECTIVE - HINDI OUTPUT:
You MUST use formal Rajbhasha (राजभाषा) Hindi throughout:
- "Assessment" = "आकलन" (Aakalan)
- "Analysis" = "विश्लेषण" (Vishleshan)  
- "Impact" = "प्रभाव" (Prabhav)
- "Stakeholder" = "हितधारक" (Hitdharak)
- "Beneficiary" = "लाभार्थी" (Laabharthi)
- "Provision" = "प्रावधान" (Praavdhan)
- "Amendment" = "संशोधन" (Sanshodhan)
- "Recommendation" = "अनुशंसा" (Anushansa)
- "Evidence" = "साक्ष्य" (Saakshya)
- "Pursuant to" = "के अनुसरण में" (Ke Anusaran Mein)

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
                pages_data.append({
                    "page": page_num + 1,
                    "content": text
                })
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
    
    audit_header = f""""""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(audit_header + content)
    
    return filepath


# ============================================================
# BACKEND FUNCTION (For WhatsApp/API Integration)
# ============================================================

def ask_agent(prompt, tenant_id=1):
    """
    Standalone function for Backend (FastAPI/WhatsApp).
    Does NOT use Streamlit session state.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "⚠️ Error: GEMINI_API_KEY not found in environment variables."

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        full_prompt = f"""
        System: You are a helpful political aide named 'Needle'. Keep answers concise (under 200 words) for WhatsApp.
        User: {prompt}
        """
        
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        print(f"❌ Gemini Backend Error: {e}")
        return "I am currently overloaded. Please try again later."


# Backwards compatibility alias
ask_groq_agent = ask_agent


# ============================================================
# MAIN RENDER FUNCTION
# ============================================================

def render_copilot(username):
    """Main Co-Pilot UI — two tabs: Analyse + Ask."""
    
    # --- SESSION STATE ---
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
    
    # --- HEADER ---
    header_col1, header_col2 = st.columns([4, 1])
    with header_col1:
        st.title("🤖 Document Co-Pilot")
        st.caption(f"Strategic Intelligence for Parliamentary Use | User: {username}")
    with header_col2:
        if st.button("🔄 New Analysis", use_container_width=True):
            st.session_state.pages_data = []
            st.session_state.copilot_filename = ""
            st.session_state.analysis_result = ""
            st.session_state.analysis_type = ""
            st.session_state.copilot_chat_history = []
            st.rerun()
    
    st.divider()
    
    # --- DOCUMENT UPLOAD ---
    if not st.session_state.pages_data:
        st.markdown("### 📄 Upload Document")
        
        upload_col1, upload_col2 = st.columns([2, 1])
        with upload_col1:
            uploaded_file = st.file_uploader(
                "Upload Legislative Document (PDF)",
                type=["pdf"],
                help="Bills, Acts, Ordinances, Committee Reports, Policy Documents"
            )
            
            if uploaded_file:
                with st.spinner("📑 Extracting document structure..."):
                    st.session_state.pages_data = extract_structured_pages(uploaded_file)
                    st.session_state.copilot_filename = uploaded_file.name
                    
                    if st.session_state.pages_data:
                        st.success(f"✅ Loaded: **{uploaded_file.name}** ({len(st.session_state.pages_data)} pages)")
                        st.rerun()
                    else:
                        st.error("Failed to extract text from PDF. Please try another file.")
        
        with upload_col2:
            st.markdown("**Supported Documents:**")
            st.caption("• Bills & Acts")
            st.caption("• Ordinances")
            st.caption("• Committee Reports")
            st.caption("• Policy Documents")
            st.caption("• Budget Documents")
        
        return  # Stop here if no document
    
    # --- DOCUMENT LOADED ---
    doc_col1, doc_col2, doc_col3 = st.columns([3, 1, 1])
    with doc_col1:
        st.success(f"📄 **Active Document:** {st.session_state.copilot_filename}")
    with doc_col2:
        st.metric("Pages", len(st.session_state.pages_data))
    with doc_col3:
        if st.button("📂 Change Document"):
            st.session_state.pages_data = []
            st.session_state.copilot_filename = ""
            st.session_state.analysis_result = ""
            st.session_state.copilot_chat_history = []
            st.rerun()
    
    st.divider()
    
    # --- TWO TABS: ANALYSE + ASK ---
    tab_analyse, tab_ask = st.tabs(["🔍 Analyse", "💬 Ask"])
    
    model = get_gemini_model()
    
    if not model:
        st.error("⚠️ AI Model not connected. Please add `GEMINI_API_KEY` to environment variables.")
        return
    
    # ==========================================================
    # TAB 1: ANALYSE
    # ==========================================================
    with tab_analyse:
        st.markdown("#### 🔍 Comprehensive Document Analysis")
        st.caption("One-click analysis: legal risks, key clauses, stakeholder impact, and talking points.")
        
        col1, col2 = st.columns(2)
        with col1:
            analyse_language = st.selectbox(
                "Language",
                ["English", "Hindi (राजभाषा)", "Bilingual"],
                key="analyse_lang"
            )
        with col2:
            analyse_depth = st.radio(
                "Depth",
                ["Quick Scan", "Comprehensive"],
                index=0,
                horizontal=True,
                key="analyse_depth"
            )
        
        if st.button("🔍 Analyse Document", type="primary", use_container_width=True, key="btn_analyse"):
            with st.spinner("⚖️ Analysing document — clauses, risks, impact, and strategy..."):
                context = get_document_context(st.session_state.pages_data)
                
                lang_instruction = RAJBHASHA_INSTRUCTIONS if "Hindi" in analyse_language else ""
                depth_note = "Focus on top 5 most significant findings." if analyse_depth == "Quick Scan" else "Be comprehensive — cover all significant findings."
                
                prompt = f"""
ROLE: Senior Parliamentary Research Officer.
TASK: Provide a complete intelligence briefing on this document for a Member of Parliament.

DOCUMENT: {st.session_state.copilot_filename}

{context}

PRODUCE THE FOLLOWING SECTIONS:

## 📋 EXECUTIVE SUMMARY
A 3-4 line summary of what this document is about and why it matters.

## ⚠️ KEY RISKS & RED FLAGS
| Clause/Section | Risk Level (🔴🟡🟢) | Issue | Why It Matters | Citation |
|---|---|---|---|---|
(Identify clauses with legal ambiguity, constitutional concerns, or implementation risks)

## 👥 WHO IS AFFECTED
- **Beneficiaries:** Who gains and how
- **Adversely Affected:** Who loses and how
- **Constituency Impact:** How this affects the MP's voters

## 🎤 TALKING POINTS (For Parliament Floor)
3-5 ready-to-use arguments the MP can deploy in debate — both FOR and AGAINST positions.

## 💡 RECOMMENDED ACTION
What should the MP do? (Support/Oppose/Seek amendments — with specific suggestions)

RULES:
1. {depth_note}
2. EVERY claim must cite [Page X]
3. If inferring, mark [INFERENCE]
4. Language: {analyse_language.split()[0]}
{lang_instruction}
"""
                
                try:
                    response = model.generate_content(prompt)
                    result_text = response.text
                    st.session_state.analysis_result = result_text
                    st.session_state.analysis_type = "Document_Analysis"
                    st.session_state.copilot_chat_history.append({"role": "user", "parts": ["Analyse this document comprehensively."]})
                    st.session_state.copilot_chat_history.append({"role": "model", "parts": [result_text]})
                    st.rerun()
                except Exception as e:
                    st.error(f"Analysis Error: {e}")
    
    # ==========================================================
    # TAB 2: ASK
    # ==========================================================
    with tab_ask:
        st.markdown("#### 💬 Ask Anything About This Document")
        st.caption("The AI remembers your analysis and previous questions.")
        
        # Show conversation history
        chat_history = st.session_state.copilot_chat_history
        if chat_history:
            with st.container(height=350):
                for msg in chat_history:
                    role = msg["role"]
                    text = msg["parts"][0] if msg["parts"] else ""
                    if role == "user":
                        st.markdown(f"**🧑 You:** {text}")
                    else:
                        with st.expander("🤖 Co-Pilot Response", expanded=False):
                            st.markdown(text)
            st.caption(f"💬 {len([m for m in chat_history if m['role'] == 'user'])} questions in this session")
        else:
            st.info("💡 **Tip:** Run Analyse first, then ask follow-ups here — *'What about clause 3?'* or *'How does this affect farmers?'*")
        
        custom_query = st.text_input(
            "Your Question",
            placeholder="e.g., What's the budget implication of clause 3?",
            key="custom_query"
        )
        
        btn_col1, btn_col2 = st.columns([3, 1])
        with btn_col1:
            send_pressed = st.button("🚀 Ask", type="primary", use_container_width=True, key="btn_ask")
        with btn_col2:
            if st.button("🗑️ Clear Chat", use_container_width=True, key="btn_clear_chat"):
                st.session_state.copilot_chat_history = []
                st.session_state.analysis_result = ""
                st.rerun()
        
        if send_pressed:
            if not custom_query:
                st.warning("Please enter a question.")
            else:
                with st.spinner("🔎 Searching document..."):
                    context = get_document_context(st.session_state.pages_data)
                    
                    system_prompt = f"""
You are a Senior Legislative Research Officer. Answer based ONLY on this document.

DOCUMENT: {st.session_state.copilot_filename}
{context}

RULES:
1. EVERY claim must cite [Page X]
2. If not in the document: "This information is not found in the document."
3. If inferring: mark [INFERENCE]
4. Be concise and actionable.

You have the full conversation history — give contextual answers to follow-ups.
"""
                    
                    try:
                        chat = model.start_chat(history=chat_history)
                        response = chat.send_message(f"{system_prompt}\n\nUSER QUERY: {custom_query}")
                        result_text = response.text
                        
                        st.session_state.copilot_chat_history.append({"role": "user", "parts": [custom_query]})
                        st.session_state.copilot_chat_history.append({"role": "model", "parts": [result_text]})
                        
                        st.session_state.analysis_result = result_text
                        st.session_state.analysis_type = "Custom_Query"
                        st.rerun()
                    except Exception as e:
                        st.error(f"Query Error: {e}")
    
    # ==========================================================
    # RESULTS DISPLAY
    # ==========================================================
    if st.session_state.analysis_result:
        st.divider()
        
        result_header_col1, result_header_col2 = st.columns([3, 1])
        with result_header_col1:
            analysis_labels = {
                "Document_Analysis": "🔍 Document Analysis Results",
                "Custom_Query": "💬 Query Response"
            }
            st.markdown(f"### {analysis_labels.get(st.session_state.analysis_type, 'Analysis Results')}")
        
        with result_header_col2:
            if st.button("🗑️ Clear Results"):
                st.session_state.analysis_result = ""
                st.session_state.analysis_type = ""
                st.rerun()
        
        # Verification warnings
        result_text = st.session_state.analysis_result
        has_verify_tags = "[VERIFY" in result_text or "[ESTIMATE" in result_text or "[INFERENCE" in result_text
        
        if has_verify_tags:
            st.warning("⚠️ **VERIFICATION REQUIRED:** This analysis contains items marked for verification. Please cross-check before official use.")
        
        # Display results
        with st.container(border=True):
            st.markdown(result_text)
        
        # Action buttons
        action_col1, action_col2, action_col3 = st.columns(3)
        
        with action_col1:
            if st.button("💾 Save to Archives", use_container_width=True, key="save_result"):
                filepath = save_analysis_to_disk(
                    result_text,
                    st.session_state.analysis_type,
                    st.session_state.copilot_filename
                )
                st.success(f"Saved: {filepath}")
        
        with action_col2:
            st.download_button(
                "📥 Download (.md)",
                result_text,
                file_name=f"{st.session_state.analysis_type}_{st.session_state.copilot_filename[:20]}.md",
                use_container_width=True
            )
        
        with action_col3:
            if st.button("🔄 Run Again", use_container_width=True, key="rerun"):
                st.session_state.analysis_result = ""
                st.rerun()
        
        # Audit trail
        with st.expander("📋 Analysis Metadata", expanded=False):
            st.caption(f"**Document:** {st.session_state.copilot_filename}")
            st.caption(f"**Analysis Type:** {st.session_state.analysis_type}")
            st.caption(f"**Generated:** {datetime.now().strftime('%d %B %Y, %H:%M:%S')}")
            st.caption(f"**Pages Analyzed:** {len(st.session_state.pages_data)}")
            st.caption("**Status:** DRAFT - Requires Verification Before Official Use")
    
    # --- FOOTER ---
    st.divider()
    st.caption("""
    ⚠️ **IMPORTANT DISCLAIMER:** All analyses generated by this tool are for research and preparation purposes only.
    - Verify all citations against the original document before official use
    - Items marked [VERIFY], [ESTIMATE], or [INFERENCE] require independent confirmation
    - This tool does not constitute legal advice
    - The MP/User is solely responsible for content used in Parliament
    """)