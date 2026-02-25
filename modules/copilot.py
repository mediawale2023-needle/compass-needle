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
# CONFIGURATION & PROMPTS (SOPHISTICATED VERSION)
# ============================================================

LEGISLATIVE_SCRUTINY_PROMPT = """
ROLE: Senior Legislative Research Officer.
TASK: Conduct a "Legislative Scrutiny" (Clause-by-Clause Analysis) on the provided document.
GOAL: Identify clauses that require parliamentary attention due to legal ambiguity, public impact, or implementation risks.

DOCUMENT: {filename}
CONTEXT:
{context}

OUTPUT FORMAT (Strict Markdown Table):
| Clause/Section | Scrutiny Score (1-10) | Legislative Concern (Precise) | Parliamentary Argument (For the Floor) | Citation (Page/Para) |
|---|---|---|---|---|
| Sec 12(a) | 9/10 | Ambiguity regarding executive powers | "This provision grants excessive delegated legislation powers." | [Page 12, Para 3] |

REQUIREMENTS:
1. Identify significant clauses based on the requested depth.
2. Scrutiny Score: 10 = Constitutional/Public Interest Risk, 1 = Minor Procedural Detail.
3. CITATION IS MANDATORY: You must cite the specific Page Number or Section Number.
4. Tone: Formal, Legalistic, and Objective.
5. Language: {language}
"""

FLOOR_STRATEGY_PROMPT = """
ROLE: Parliamentary Strategy Advisor.
TASK: Draft a "Floor Intervention Note" (Debate Brief) for the Member of Parliament.

DOCUMENT: {filename}
POSITION: {stance}
SPEAKING TIME: {speaking_time} Minutes
LANGUAGE: {language}

CONTEXT:
{context}

STRUCTURE:

# 🏛️ PARLIAMENTARY INTERVENTION BRIEF

## 1. OPENING SUBMISSION (30 Seconds)
(A formal, dignified opening statement establishing the MP's position)

## 2. SUBSTANTIVE ARGUMENTS
* **Point 1:** [Primary Contention]
    * *The Argument:* [Legal/Policy basis]
    * *Evidence:* [Quote specific text & Citation]
    * *Key Phrase:* [A formal rhetorical point for the record]

* **Point 2:** [Secondary Contention]
    * ... (Same format)

* **Point 3:** [Constituency Relevance]
    * *Local Implication:* How this specifically impacts the development or welfare of the constituency.

## 3. ANTICIPATED COUNTER-ARGUMENTS
| If the Government/Opposition argues... | The Rebuttal should be... |
|---|---|
| [Predict opposing view] | [Your factual counter-point with evidence] |

## 4. CONCLUDING REMARKS
(A strong, statesman-like conclusion summarizing the demand)
"""

IMPACT_ASSESSMENT_PROMPT = """
ROLE: Policy Impact Assessor.
TASK: Conduct a "Socio-Economic Impact Assessment".
GOAL: Map the beneficiaries and adversely affected groups based on the text.

DOCUMENT: {filename}
LANGUAGE: {language}

FOCUS AREAS:
{focus_areas}

CONTEXT:
{context}

OUTPUT FORMAT:

### 📊 SOCIO-ECONOMIC IMPACT MATRIX

**🟢 BENEFICIARY GROUPS (Positive Impact)**
* **[Sector/Demographic]**
    * *Rationale:* [Explanation of benefit]
    * *Citation:* [Evidence from text]

**🔴 AFFECTED GROUPS (Adverse Impact)**
* **[Sector/Demographic]**
    * *Concern:* [Explanation of risk/cost]
    * *Citation:* [Evidence from text]

**⚖️ POLITICAL & SOCIAL CALCULUS**
* **Public Sentiment:** [Assessment of general public reaction]
* **Administrative Feasibility:** [Assessment of implementation challenges]
* **Constituency Implication:** [Specific impact on local voters]

STRICT RULES:
1. Be OBJECTIVE - this is analysis, not advocacy
2. EVERY impact claim must reference [Page X] from document
3. If estimating numbers not in document, clearly mark: [ESTIMATE - VERIFY]
4. Include BOTH positive and negative impacts regardless of political stance
5. The Political Calculus section should be analytical, not prescriptive
"""

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
    """Main Co-Pilot UI with three analysis modes."""
    
    # --- SESSION STATE INITIALIZATION ---
    if 'pages_data' not in st.session_state:
        st.session_state.pages_data = []
    if 'copilot_filename' not in st.session_state:
        st.session_state.copilot_filename = ""
    if 'analysis_result' not in st.session_state:
        st.session_state.analysis_result = ""
    if 'analysis_type' not in st.session_state:
        st.session_state.analysis_type = ""
    if 'copilot_chat_history' not in st.session_state:
        st.session_state.copilot_chat_history = []  # [{"role": "user"/"model", "parts": ["..."]}]
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
    
    # --- DOCUMENT UPLOAD SECTION ---
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
            st.caption("• Standing Committee Reports")
            st.caption("• Policy Documents")
            st.caption("• Budget Documents")
        
        return  # Stop here if no document
    
    # --- DOCUMENT LOADED: SHOW ANALYSIS OPTIONS ---
    
    # Document info bar
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
    
    # --- ANALYSIS TABS ---
    tab_scrutiny, tab_floor, tab_impact, tab_custom = st.tabs([
        "🔍 Legislative Scrutiny (विधायी समीक्षा)",
        "🎤 Floor Strategy (सदन की रणनीति)", 
        "📊 Socio-Economic Impact (सामाजिक-आर्थिक प्रभाव)",
        "💬 Custom Query"
    ])
    
    model = get_gemini_model()
    
    if not model:
        st.error("⚠️ AI Model not connected. Please add `GEMINI_API_KEY` to environment variables.")
        return
    
    # ==========================================================
    # TAB 1: LEGISLATIVE SCRUTINY (विधायी समीक्षा)
    # ==========================================================
    with tab_scrutiny:
        st.markdown("#### 🔍 Clause-by-Clause Legal Risk Analysis")
        st.caption("Identify constitutional risks, implementation gaps, and political vulnerabilities in each clause.")
        
        scr_col1, scr_col2 = st.columns([1, 1])
        
        with scr_col1:
            scr_language = st.selectbox(
                "Output Language",
                ["English", "Hindi (राजभाषा)", "Bilingual"],
                key="scr_lang"
            )
            
            scr_focus = st.multiselect(
                "Focus Areas",
                [
                    "Constitutional Validity",
                    "Fundamental Rights Impact",
                    "Federalism Concerns",
                    "Delegation of Powers",
                    "Implementation Feasibility",
                    "Judicial Vulnerability"
                ],
                default=["Constitutional Validity", "Fundamental Rights Impact"],
                key="scr_focus"
            )
        
        with scr_col2:
            scr_depth = st.radio(
                "Analysis Depth",
                ["Quick Scan (Top 5 Clauses)", "Standard (Top 10 Clauses)", "Comprehensive (All Significant Clauses)"],
                index=1,
                key="scr_depth"
            )
            
            st.info("💡 **Tip:** Quick Scan is ideal for first review. Comprehensive for detailed committee work.")
        
        if st.button("🔍 Run Legislative Scrutiny", type="primary", use_container_width=True, key="btn_scrutiny"):
            with st.spinner("⚖️ Analyzing clauses for legal and political risks..."):
                context = get_document_context(st.session_state.pages_data)
                
                lang_instruction = ""
                if "Hindi" in scr_language:
                    lang_instruction = RAJBHASHA_INSTRUCTIONS
                
                depth_instruction = {
                    "Quick Scan (Top 5 Clauses)": "Focus only on the TOP 5 most significant/controversial clauses.",
                    "Standard (Top 10 Clauses)": "Analyze the TOP 10 most significant clauses.",
                    "Comprehensive (All Significant Clauses)": "Analyze ALL significant clauses comprehensively."
                }
                
                prompt = LEGISLATIVE_SCRUTINY_PROMPT.format(
                    filename=st.session_state.copilot_filename,
                    context=context,
                    language=scr_language.split()[0]
                )
                
                prompt += f"\n\nADDITIONAL INSTRUCTIONS:\n- Depth: {depth_instruction.get(scr_depth, '')}\n- Focus Areas: {', '.join(scr_focus)}\n{lang_instruction}"
                
                try:
                    response = model.generate_content(prompt)
                    result_text = response.text
                    st.session_state.analysis_result = result_text
                    st.session_state.analysis_type = "Legislative_Scrutiny"
                    # Append to chat history for follow-up context
                    st.session_state.copilot_chat_history.append({"role": "user", "parts": [f"[Legislative Scrutiny Analysis requested]"]})
                    st.session_state.copilot_chat_history.append({"role": "model", "parts": [result_text]})
                    st.rerun()
                except Exception as e:
                    st.error(f"Analysis Error: {e}")
    
    # ==========================================================
    # TAB 2: FLOOR STRATEGY (सदन की रणनीति)
    # ==========================================================
    with tab_floor:
        st.markdown("#### 🎤 Parliamentary Debate Preparation")
        st.caption("Complete preparation kit for intervention on the Floor of the House.")
        
        floor_col1, floor_col2 = st.columns([1, 1])
        
        with floor_col1:
            floor_stance = st.radio(
                "Your Position",
                [
                    "🔴 OPPOSITION (Oppose the Bill/Policy)",
                    "🟢 SUPPORT (Defend the Bill/Policy)",
                    "🟡 NEUTRAL (Seek Clarifications/Amendments)"
                ],
                key="floor_stance"
            )
            
            floor_time = st.slider(
                "Speaking Time (minutes)",
                min_value=2,
                max_value=15,
                value=5,
                key="floor_time"
            )
        
        with floor_col2:
            floor_language = st.selectbox(
                "Output Language",
                ["English", "Hindi (राजभाषा)", "Bilingual"],
                key="floor_lang"
            )
            
            floor_style = st.selectbox(
                "Oratory Style",
                [
                    "Aggressive & Confrontational",
                    "Measured & Persuasive", 
                    "Data-Driven & Technical",
                    "Emotional & Public-Oriented"
                ],
                key="floor_style"
            )
        
        floor_specific = st.text_area(
            "Specific Points to Cover (Optional)",
            placeholder="e.g., Focus on Section 14 (Government exemption), mention recent RTI findings...",
            height=80,
            key="floor_specific"
        )
        
        if st.button("🎤 Generate Floor Strategy", type="primary", use_container_width=True, key="btn_floor"):
            with st.spinner("🏛️ Preparing your parliamentary intervention..."):
                context = get_document_context(st.session_state.pages_data)
                
                # Extract stance keyword
                stance_map = {
                    "🔴 OPPOSITION": "OPPOSITION",
                    "🟢 SUPPORT": "SUPPORT",
                    "🟡 NEUTRAL": "NEUTRAL-QUESTIONING"
                }
                stance = next((v for k, v in stance_map.items() if k in floor_stance), "NEUTRAL")
                
                lang_instruction = ""
                if "Hindi" in floor_language:
                    lang_instruction = RAJBHASHA_INSTRUCTIONS
                
                prompt = FLOOR_STRATEGY_PROMPT.format(
                    filename=st.session_state.copilot_filename,
                    context=context,
                    stance=stance,
                    speaking_time=floor_time,
                    language=floor_language.split()[0]
                )
                
                prompt += f"""

ADDITIONAL INSTRUCTIONS:
- Oratory Style: {floor_style}
- Specific Focus: {floor_specific if floor_specific else "None specified - use judgment"}
{lang_instruction}

STYLE GUIDELINES:
- "Aggressive & Confrontational": Use strong language, rhetorical questions, challenge the government directly
- "Measured & Persuasive": Balanced tone, acknowledge merits, then present concerns
- "Data-Driven & Technical": Focus on statistics, legal precedents, expert opinions
- "Emotional & Public-Oriented": Connect to common citizen, use storytelling, invoke national interest
"""
                
                try:
                    response = model.generate_content(prompt)
                    result_text = response.text
                    st.session_state.analysis_result = result_text
                    st.session_state.analysis_type = "Floor_Strategy"
                    st.session_state.copilot_chat_history.append({"role": "user", "parts": [f"[Floor Strategy requested — {stance} position, {floor_time} min]"]})
                    st.session_state.copilot_chat_history.append({"role": "model", "parts": [result_text]})
                    st.rerun()
                except Exception as e:
                    st.error(f"Analysis Error: {e}")
    
    # ==========================================================
    # TAB 3: SOCIO-ECONOMIC IMPACT (सामाजिक-आर्थिक प्रभाव)
    # ==========================================================
    with tab_impact:
        st.markdown("#### 📊 Objective Stakeholder & Impact Analysis")
        st.caption("Who benefits? Who loses? What's the political calculus?")
        
        impact_col1, impact_col2 = st.columns([1, 1])
        
        with impact_col1:
            impact_language = st.selectbox(
                "Output Language",
                ["English", "Hindi (राजभाषा)", "Bilingual"],
                key="impact_lang"
            )
            
            impact_focus = st.multiselect(
                "Focus Sectors",
                [
                    "Agriculture & Rural",
                    "Industry & Manufacturing",
                    "Services & IT",
                    "MSMEs",
                    "Banking & Finance",
                    "Healthcare",
                    "Education",
                    "Environment"
                ],
                default=["Agriculture & Rural", "MSMEs"],
                key="impact_focus"
            )
        
        with impact_col2:
            impact_demo = st.multiselect(
                "Focus Demographics",
                [
                    "Women",
                    "SC/ST Communities",
                    "OBC",
                    "Minorities",
                    "Youth (18-35)",
                    "Senior Citizens",
                    "Differently Abled",
                    "Urban Poor",
                    "Rural Population"
                ],
                default=["Women", "SC/ST Communities", "Youth (18-35)"],
                key="impact_demo"
            )
            
            impact_geo = st.multiselect(
                "Geographic Focus",
                [
                    "Metro Cities",
                    "Tier 2/3 Cities",
                    "Rural Areas",
                    "Tribal Areas",
                    "Border Regions",
                    "Aspirational Districts"
                ],
                default=["Rural Areas", "Aspirational Districts"],
                key="impact_geo"
            )
        
        if st.button("📊 Generate Impact Assessment", type="primary", use_container_width=True, key="btn_impact"):
            with st.spinner("📈 Analyzing socio-economic impacts across stakeholders..."):
                context = get_document_context(st.session_state.pages_data)
                
                lang_instruction = ""
                if "Hindi" in impact_language:
                    lang_instruction = RAJBHASHA_INSTRUCTIONS
                
                focus_areas = f"""
SECTORS TO ANALYZE: {', '.join(impact_focus)}
DEMOGRAPHICS TO ANALYZE: {', '.join(impact_demo)}
GEOGRAPHIC FOCUS: {', '.join(impact_geo)}
"""
                
                prompt = IMPACT_ASSESSMENT_PROMPT.format(
                    filename=st.session_state.copilot_filename,
                    context=context,
                    focus_areas=focus_areas,
                    language=impact_language.split()[0]
                )
                
                prompt += f"\n{lang_instruction}"
                
                try:
                    response = model.generate_content(prompt)
                    result_text = response.text
                    st.session_state.analysis_result = result_text
                    st.session_state.analysis_type = "Impact_Assessment"
                    st.session_state.copilot_chat_history.append({"role": "user", "parts": [f"[Impact Assessment requested]"]})
                    st.session_state.copilot_chat_history.append({"role": "model", "parts": [result_text]})
                    st.rerun()
                except Exception as e:
                    st.error(f"Analysis Error: {e}")
    
    # ==========================================================
    # TAB 4: CUSTOM QUERY
    # ==========================================================
    with tab_custom:
        st.markdown("#### 💬 Ask Anything About This Document")
        st.caption("Conversational — ask follow-ups without re-uploading. The AI remembers your previous questions and analyses.")
        
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
                        # Truncate long model responses in the history view
                        preview = text[:300] + "..." if len(text) > 300 else text
                        with st.expander(f"🤖 Co-Pilot Response", expanded=False):
                            st.markdown(text)
            st.caption(f"💬 {len([m for m in chat_history if m['role'] == 'user'])} questions in this session")
        
        # Input area
        custom_query = st.text_input(
            "Your Question",
            placeholder="e.g., What's the budget implication of clause 3? How does Section 14 affect farmers?",
            key="custom_query"
        )
        
        custom_col1, custom_col2 = st.columns(2)
        with custom_col1:
            custom_language = st.selectbox(
                "Output Language",
                ["English", "Hindi (राजभाषा)"],
                key="custom_lang"
            )
        with custom_col2:
            custom_style = st.selectbox(
                "Response Style",
                ["Detailed Analysis", "Brief Summary", "Bullet Points Only"],
                key="custom_style"
            )
        
        btn_col1, btn_col2 = st.columns([3, 1])
        with btn_col1:
            send_pressed = st.button("🚀 Ask", type="primary", use_container_width=True, key="btn_custom")
        with btn_col2:
            if st.button("🗑️ Clear Chat", use_container_width=True, key="btn_clear_chat"):
                st.session_state.copilot_chat_history = []
                st.session_state.analysis_result = ""
                st.rerun()
        
        if send_pressed:
            if not custom_query:
                st.warning("Please enter a question.")
            else:
                with st.spinner("🔎 Searching document for answers..."):
                    context = get_document_context(st.session_state.pages_data)
                    
                    lang_instruction = RAJBHASHA_INSTRUCTIONS if "Hindi" in custom_language else ""
                    
                    style_instruction = {
                        "Detailed Analysis": "Provide a comprehensive, detailed response with full explanations.",
                        "Brief Summary": "Keep the response concise, under 300 words.",
                        "Bullet Points Only": "Respond ONLY in bullet points, no prose."
                    }
                    
                    system_prompt = f"""
You are a Senior Legislative Research Officer analyzing a parliamentary document.

DOCUMENT: {st.session_state.copilot_filename}
DOCUMENT TEXT:
{context}

STRICT RULES:
1. Answer ONLY based on the document content
2. EVERY claim must have [Page X] citation
3. If the answer is not in the document, say: "This information is not found in the document."
4. If you need to infer, clearly mark: [INFERENCE - not explicitly stated]
5. Language: {custom_language.split()[0]}
6. Style: {style_instruction.get(custom_style, '')}

{lang_instruction}

You have access to the full conversation history. Use previous analyses and Q&A to give contextual, relevant answers to follow-up questions.
"""
                    
                    # Build conversation for Gemini with history
                    # Gemini chat expects alternating user/model messages
                    try:
                        chat = model.start_chat(history=chat_history)
                        response = chat.send_message(f"{system_prompt}\n\nUSER QUERY: {custom_query}")
                        result_text = response.text
                        
                        # Append to history
                        st.session_state.copilot_chat_history.append({"role": "user", "parts": [custom_query]})
                        st.session_state.copilot_chat_history.append({"role": "model", "parts": [result_text]})
                        
                        st.session_state.analysis_result = result_text
                        st.session_state.analysis_type = "Custom_Query"
                        st.rerun()
                    except Exception as e:
                        st.error(f"Query Error: {e}")
    
    # ==========================================================
    # RESULTS DISPLAY SECTION
    # ==========================================================
    if st.session_state.analysis_result:
        st.divider()
        
        # Results header
        result_header_col1, result_header_col2 = st.columns([3, 1])
        with result_header_col1:
            analysis_labels = {
                "Legislative_Scrutiny": "🔍 विधायी समीक्षा | Legislative Scrutiny Results",
                "Floor_Strategy": "🎤 सदन की रणनीति | Floor Strategy Brief",
                "Impact_Assessment": "📊 सामाजिक-आर्थिक प्रभाव | Impact Assessment",
                "Custom_Query": "💬 Query Response"
            }
            st.markdown(f"### {analysis_labels.get(st.session_state.analysis_type, 'Analysis Results')}")
        
        with result_header_col2:
            if st.button("🗑️ Clear Results"):
                st.session_state.analysis_result = ""
                st.session_state.analysis_type = ""
                st.rerun()
        
        # Check for verification warnings
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
    
    # ==========================================================
    # FOOTER DISCLAIMER
    # ==========================================================
    st.divider()
    st.caption("""
    ⚠️ **IMPORTANT DISCLAIMER:** All analyses generated by this tool are for research and preparation purposes only.
    - Verify all citations against the original document before official use
    - Items marked [VERIFY], [ESTIMATE], or [INFERENCE] require independent confirmation
    - This tool does not constitute legal advice
    - The MP/User is solely responsible for content used in Parliament
    """)