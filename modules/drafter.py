import streamlit as st
import os
import json
from datetime import datetime
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# CONSTANTS: PARLIAMENTARY VOCABULARY & FORMATS
# ============================================================

# Formal Hindi (Rajbhasha) vocabulary mapping
RAJBHASHA_INSTRUCTIONS = """
HINDI LANGUAGE RULES (MANDATORY if Hindi selected):
- Use formal Rajbhasha (राजभाषा), NOT conversational Hindi
- MUST use these terms:
  • "Request" = "अनुरोध" (Anurodh), NOT "please batayein"
  • "Please" = "कृपया" (Kripya)
  • "Related to" = "संबंधित" (Sambandhit)
  • "Department" = "विभाग" (Vibhag)
  • "Regarding" = "के संदर्भ में" (Ke Sandarbh Mein)
  • "Necessary action" = "आवश्यक कार्यवाही" (Avashyak Karyavahi)
  • "Public interest" = "जनहित" (Janhit)
  • "Immediate attention" = "तत्काल ध्यान" (Tatkal Dhyan)
  • "Under your kind consideration" = "आपके संज्ञान में" (Aapke Sangyaan Mein)
  • "I hope" = "आशा है" (Asha Hai)
  • "Signed" = "हस्ताक्षरित" (Hastaksharit)
- Use formal sentence endings: "...किया जाए।", "...की जाए।"
- Avoid English words unless no Hindi equivalent exists
- Use honorifics: "माननीय" (Maananiya) for Ministers, "श्री/श्रीमती" for officials
"""

# Government of India letter format template
GOI_LETTER_FORMAT = """
EXACT OUTPUT FORMAT (Government of India Standard):
भारत सरकार / GOVERNMENT OF INDIA [SENDER DESIGNATION]

F.No. [DEPT]-[SECTION]/[YEAR] Dated: [DD Month YYYY]

To, [RECIPIENT DESIGNATION] [MINISTRY/DEPARTMENT NAME] [ADDRESS]

Subject: [CLEAR, SPECIFIC SUBJECT LINE]

Reference: [Any prior correspondence, if applicable, else remove this line]

[SALUTATION],

[Opening paragraph - Context and purpose]

[Main body - Key points, each numbered]

[Specific ask/demand with timeline]

[Closing paragraph - Expected action]

[COMPLIMENTARY CLOSE],

[SIGNATURE BLOCK] (NAME IN CAPITALS) Member of Parliament, [HOUSE] [CONSTITUENCY NAME]

Copy to:

[If applicable]

"""

# Tone presets
TONE_PRESETS = {
    "Assertive (Opposition Style)": {
        "instruction": """
TONE: ASSERTIVE & DEMANDING (Opposition MP Style)
- Use phrases like: "It is a matter of grave concern...", "The Government has failed to..."
- Demand accountability: "What action has been taken?", "Why has there been delay?"
- Reference RTI/Parliament rights: "As per my right under Article 105..."
- Imply consequences: "...failing which, I shall be constrained to raise this matter on the floor of the House."
- Use strong closings: "I expect urgent action", "This matter brooks no delay"
""",
        "salutation": "Sir",
        "close": "Yours faithfully"
    },
    "Requesting (Ministerial Courtesy)": {
        "instruction": """
TONE: RESPECTFUL & REQUESTING (Ruling Party/Cross-Party Courtesy)
- Use courteous phrases: "I would be grateful if...", "May I request your kind intervention..."
- Acknowledge government efforts: "While appreciating the Government's initiatives..."
- Request, don't demand: "I request your good offices to...", "Your kind consideration would be appreciated"
- Offer collaboration: "I remain available to discuss this matter at your convenience"
- Use soft closings: "With warm regards", "Thanking you in anticipation"
""",
        "salutation": "Respected Sir/Madam",
        "close": "With warm regards"
    },
    "Neutral (Factual Brief)": {
        "instruction": """
TONE: NEUTRAL & FACTUAL (Official Correspondence)
- State facts without emotional language
- Use bureaucratic precision: "It is submitted that...", "For your kind information..."
- Reference rules/schemes by exact name and date
- Neutral closing: "Necessary action may kindly be taken"
""",
        "salutation": "Dear Sir/Madam",
        "close": "Yours sincerely"
    }
}

# Hallucination safety rules
HALLUCINATION_GUARDRAILS = """
CRITICAL DATA ACCURACY RULES:
1. If you do not have a SPECIFIC statistic (number, date, amount), use placeholder: [INSERT DATA HERE]
2. If referencing a scheme/act, use: [VERIFY: Scheme Name and Year]
3. If mentioning a budget figure, use: [VERIFY: ₹XX Crore as per Budget 20XX-XX]
4. NEVER invent: casualty numbers, financial figures, dates of events, or names
5. Add this footer if ANY placeholder used: "⚠️ Note: Placeholders marked [...] require verification before sending."
"""

# Parliamentary Question format
PQ_FORMAT_RULES = """
PARLIAMENTARY QUESTION FORMAT (Lok Sabha/Rajya Sabha Standard):

Each question MUST follow this EXACT structure:
(a) Whether the Government/Minister is aware of [specific issue with location]?
(b) If so, the details/status of [specific data request]?
(c) The funds allocated and utilized for [relevant scheme] during the last [3/5] years, State/UT-wise?
(d) The reasons for delay/shortfall/inaction, if any?
(e) The time-bound corrective steps proposed by the Government?

RULES:
- Each sub-part (a) to (e) must be ONE sentence only
- Use "whether...?" format for (a)
- Use "if so, the..." format for (b)
- Always ask for State-wise/Year-wise data in (c)
- Part (e) must ask for TIMELINE
"""

# Ministry-specific context
MINISTRY_CONTEXT = {
    "Ministry of Railways": "Reference relevant schemes: PM Gati Shakti, Vande Bharat, Kavach system, Station Redevelopment",
    "Ministry of Road Transport & Highways": "Reference: Bharatmala Pariyojana, NHAI projects, road safety initiatives",
    "Ministry of Jal Shakti": "Reference: Jal Jeevan Mission, AMRUT, Namami Gange, Dam Rehabilitation",
    "Ministry of Agriculture": "Reference: PM-KISAN, MSP policy, e-NAM, Soil Health Card",
    "Ministry of Finance": "Reference: Budget allocations, GST matters, fiscal policy, PM Mudra Yojana",
    "Ministry of Home Affairs": "Reference: Border security, internal security, police modernization, disaster response",
    "Ministry of Health & Family Welfare": "Reference: Ayushman Bharat, PM-JAY, immunization, AIIMS expansion",
    "Ministry of Education": "Reference: NEP 2020, PM SHRI Schools, Samagra Shiksha, higher education",
    "Ministry of External Affairs": "Reference: Visa matters, diaspora welfare, bilateral relations",
    "Ministry of Rural Development": "Reference: MGNREGA, PMAY-G, DAY-NRLM, Pradhan Mantri Gram Sadak Yojana"
}

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def load_tenant_profile():
    """Loads MP details from local JSON profile."""
    file_path = "tenant_profile.json"
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "mp_name": "Member of Parliament",
        "constituency": "India",
        "house": "Lok Sabha",
        "party": "Independent",
        "languages": ["English", "Hindi"]
    }


def save_draft_to_disk(content, subject, doc_type="Draft"):
    """Saves the generated text to a local folder with audit trail."""
    folder = "saved_drafts"
    if not os.path.exists(folder):
        os.makedirs(folder)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_subject = "".join(c for c in subject if c.isalnum() or c in (' ', '_')).strip().replace(" ", "_")[:20]
    filename = f"{folder}/{doc_type}_{timestamp}_{safe_subject}.txt"

    # Add audit header
    audit_header = f"""
================================================================================
DOCUMENT AUDIT TRAIL
Generated: {datetime.now().strftime("%d %B %Y, %H:%M:%S")}
Type: {doc_type}
Subject: {subject}
Status: DRAFT - REQUIRES VERIFICATION BEFORE SENDING
================================================================================

"""
    with open(filename, "w", encoding="utf-8") as f:
        f.write(audit_header + content)
    return filename


def get_gemini_model():
    """Configures and returns the Gemini model."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        api_key = st.session_state.get("GLOBAL_GEMINI_KEY")
    
    if not api_key:
        return None
    
    try:
        genai.configure(api_key=api_key)
        # Using a slightly lower temperature for precision
        return genai.GenerativeModel('gemini-2.5-flash', generation_config={"temperature": 0.2})
    except Exception as e:
        print(f"Gemini Error: {e}")
        return None


def generate_reference_number(ministry_code="GEN"):
    """Generates a realistic file reference number."""
    year = datetime.now().year
    return f"MP/{ministry_code}/{year}/[SEQ]"


# ============================================================
# MAIN RENDERER
# ============================================================

def render_drafter(username):
    st.title("✍️ Smart Drafter")
    st.caption("Parliamentary-Grade Document Generator | Powered by AI")

    # Load model and profile
    model = get_gemini_model()
    profile = load_tenant_profile()

    if not model:
        st.error("⚠️ AI Model not connected.")
        st.info("Please add `GEMINI_API_KEY` to your environment variables.")
        return

    # Display MP context
    with st.expander("📋 Current MP Profile", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Name:** {profile.get('mp_name')}")
            st.write(f"**Constituency:** {profile.get('constituency')}")
        with col2:
            st.write(f"**House:** {profile.get('house', 'Lok Sabha')}")
            st.write(f"**Party:** {profile.get('party', 'Independent')}")

    tab_letter, tab_pq = st.tabs(["📝 Official Letter", "🏛️ Parliamentary Question (PQ)"])

    # ==========================================================
    # TAB 1: OFFICIAL LETTER (Enhanced)
    # ==========================================================
    with tab_letter:
        st.markdown("##### Draft Formal Letters to Ministries & Officials")
        
        c1, c2 = st.columns([1, 1])
        
        with c1:
            # RECIPIENT SECTION
            st.markdown("###### 📬 Recipient Details")
            l_recipient_type = st.selectbox(
                "Recipient Type", 
                ["Cabinet Minister", "Minister of State", "Secretary to GoI", 
                 "Chief Secretary", "District Collector", "Other Official"],
                key="l_rec_type"
            )
            l_recipient_name = st.text_input(
                "Recipient Name & Designation", 
                placeholder="e.g., Shri Ashwini Vaishnaw, Hon'ble Minister of Railways"
            )
            l_ministry = st.text_input(
                "Ministry/Department/Office", 
                placeholder="e.g., Ministry of Railways, Rail Bhavan, New Delhi"
            )

            st.markdown("###### 📄 Letter Content")
            l_subject = st.text_input(
                "Subject", 
                placeholder="e.g., Urgent need for platform extension at Belagavi Railway Station"
            )
            l_reference = st.text_input(
                "Reference (Prior correspondence, if any)",
                placeholder="e.g., Letter dated 15.01.2025 / RTI Reply No. XYZ"
            )
            l_points = st.text_area(
                "Key Points to Cover (Raw Notes)",
                height=120,
                placeholder="• Platform too short for 24-coach trains\n• 3 accidents in last 6 months\n• Request inspection by Railway Board"
            )
            
            st.markdown("###### ⚙️ Settings")
            settings_col1, settings_col2 = st.columns(2)
            with settings_col1:
                l_lang = st.selectbox(
                    "Language",
                    profile.get("languages", ["English", "Hindi"]),
                    key="l_lang"
                )
            with settings_col2:
                l_tone = st.selectbox(
                    "Tone",
                    list(TONE_PRESETS.keys()),
                    key="l_tone",
                    help="Assertive for Opposition-style demands, Requesting for cross-party courtesy"
                )

            # GENERATE BUTTON
            if st.button("✨ Generate Letter", type="primary", use_container_width=True):
                if l_recipient_name and l_subject:
                    with st.spinner("Drafting parliamentary-grade letter..."):
                        tone_config = TONE_PRESETS[l_tone]
                        
                        # Build the master prompt
                        prompt = f"""
You are drafting a formal letter as {profile.get('mp_name')}, Member of Parliament ({profile.get('house', 'Lok Sabha')}) representing {profile.get('constituency')}.

RECIPIENT HIERARCHY: {l_recipient_type}
- If Cabinet Minister: Use "Respected Sir/Madam", highest formality
- If Secretary/Collector: Use "Dear Sir/Madam", professional tone

{tone_config['instruction']}

{HALLUCINATION_GUARDRAILS}

{"" if l_lang == "English" else RAJBHASHA_INSTRUCTIONS}

{GOI_LETTER_FORMAT}

SPECIFIC INPUTS:
- Recipient: {l_recipient_name}
- Ministry/Office: {l_ministry}
- Subject: {l_subject}
- Reference: {l_reference if l_reference else "None"}
- Key Points from MP: {l_points}
- Language: {l_lang}
- Salutation to use: {tone_config['salutation']}
- Closing to use: {tone_config['close']}

TASK: Generate ONLY the letter. No explanations. Follow the exact format above.
Use reference number format: {generate_reference_number()}
Date: {datetime.now().strftime("%d %B %Y")}
"""
                        try:
                            resp = model.generate_content(prompt)
                            st.session_state["draft_letter"] = resp.text
                            st.session_state["letter_meta"] = {
                                "subject": l_subject,
                                "recipient": l_recipient_name,
                                "generated_at": datetime.now().isoformat()
                            }
                        except Exception as e:
                            st.error(f"Generation Error: {e}")
                else:
                    st.warning("⚠️ Please fill Recipient Name and Subject")

        with c2:
            st.markdown("###### 📄 Preview")
            
            if "draft_letter" in st.session_state:
                # Show verification warning if placeholders exist
                letter_content = st.session_state["draft_letter"]
                has_placeholders = "[" in letter_content and "]" in letter_content
                
                if has_placeholders:
                    st.warning("⚠️ **VERIFICATION REQUIRED:** This draft contains placeholders marked with [...]. Please verify all data before sending.")
                
                st.text_area(
                    "Generated Letter",
                    value=letter_content,
                    height=450,
                    key="letter_output"
                )
                
                # Action buttons
                b1, b2, b3 = st.columns(3)
                with b1:
                    if st.button("💾 Save to Archives", key="save_letter"):
                        filename = save_draft_to_disk(letter_content, l_subject, "Letter")
                        st.success(f"Saved: {filename}")
                with b2:
                    st.download_button(
                        "📥 Download (.txt)", 
                        letter_content, 
                        file_name=f"Letter_{l_subject[:15].replace(' ', '_')}.txt"
                    )
                with b3:
                    if st.button("🔄 Regenerate", key="regen_letter"):
                        if "draft_letter" in st.session_state:
                            del st.session_state["draft_letter"]
                        st.rerun()
                
                # Audit trail
                if "letter_meta" in st.session_state:
                    with st.expander("📊 Audit Trail", expanded=False):
                        meta = st.session_state["letter_meta"]
                        st.caption(f"Generated: {meta.get('generated_at', 'N/A')}")
                        st.caption(f"Subject: {meta.get('subject', 'N/A')}")
                        st.caption("Status: DRAFT - Not Verified")

    # ==========================================================
    # TAB 2: PARLIAMENTARY QUESTION (Enhanced)
    # ==========================================================
    with tab_pq:
        st.markdown("##### Generate Strategic Parliamentary Questions")
        
        pq_col1, pq_col2 = st.columns([1, 1])
        
        with pq_col1:
            st.markdown("###### 🎯 Target")
            pq_ministry = st.selectbox(
                "Ministry", 
                list(MINISTRY_CONTEXT.keys()),
                key="pq_ministry"
            )
            
            # Show ministry context
            st.info(f"💡 **Relevant Context:** {MINISTRY_CONTEXT.get(pq_ministry, '')}")
            
            pq_subject = st.text_input(
                "Issue/Subject", 
                placeholder="e.g., Delay in completion of Belagavi-Dharwad Highway NH-4",
                key="pq_subject"
            )
            
            pq_location = st.text_input(
                "Specific Location (State/District)", 
                placeholder="e.g., Belagavi District, Karnataka",
                key="pq_loc"
            )
            
            st.markdown("###### ⚙️ Question Type")
            pq_type = st.radio(
                "Question Focus",
                ["Balanced (All aspects)", "Fund Utilization Focus", "Timeline & Accountability Focus", "Data & Statistics Focus"],
                key="pq_type",
                horizontal=True
            )
            
            pq_lang = st.selectbox(
                "Language",
                profile.get("languages", ["English", "Hindi"]),
                key="pq_lang"
            )
            
            # GENERATE BUTTON
            if st.button("✨ Generate 5 PQ Options", type="primary", use_container_width=True, key="gen_pq"):
                if pq_subject:
                    with st.spinner("Analyzing Parliamentary precedents..."):
                        focus_instruction = {
                            "Balanced (All aspects)": "Cover funds, timeline, accountability, and data equally.",
                            "Fund Utilization Focus": "Emphasize budget allocation vs utilization, CAG observations, financial irregularities.",
                            "Timeline & Accountability Focus": "Emphasize delays, missed deadlines, officer accountability.",
                            "Data & Statistics Focus": "Emphasize state-wise data, year-wise trends, beneficiary numbers."
                        }
                        
                        prompt = f"""
You are a Senior Parliamentary Research Officer preparing Starred/Unstarred Questions for an MP.

MINISTRY: {pq_ministry}
SUBJECT: {pq_subject}
LOCATION: {pq_location if pq_location else "National level"}
LANGUAGE: {pq_lang}
FOCUS: {focus_instruction.get(pq_type, '')}

{HALLUCINATION_GUARDRAILS}

{PQ_FORMAT_RULES}

{"" if pq_lang == "English" else RAJBHASHA_INSTRUCTIONS}

MINISTRY CONTEXT: {MINISTRY_CONTEXT.get(pq_ministry, '')}

TASK: Generate exactly 5 DISTINCT Parliamentary Question options.
- Each option must have a DIFFERENT strategic angle
- Option 1: Focus on Government awareness and status
- Option 2: Focus on Fund allocation and utilization
- Option 3: Focus on Delays and accountability
- Option 4: Focus on State-wise/Year-wise data
- Option 5: Focus on Future plans and timeline

FORMAT OUTPUT AS:
---
**OPTION 1: [Strategic Angle]**
Will the Minister of {pq_ministry.replace('Ministry of ', '')} be pleased to state:

(a) ...
(b) ...
(c) ...
(d) ...
(e) ...

---
**OPTION 2: [Strategic Angle]**
...

(Continue for all 5 options)
"""
                        try:
                            resp = model.generate_content(prompt)
                            st.session_state["pq_options"] = resp.text
                            st.session_state["pq_meta"] = {
                                "ministry": pq_ministry,
                                "subject": pq_subject,
                                "generated_at": datetime.now().isoformat()
                            }
                        except Exception as e:
                            st.error(f"Generation Error: {e}")
                else:
                    st.warning("⚠️ Please enter the subject/issue")

        with pq_col2:
            st.markdown("###### 📄 Generated Options")
            
            if "pq_options" in st.session_state:
                pq_content = st.session_state["pq_options"]
                has_placeholders = "[" in pq_content and "]" in pq_content
                
                if has_placeholders:
                    st.warning("⚠️ **VERIFICATION REQUIRED:** Contains placeholders that need data.")
                
                # Split into options
                options = pq_content.split("---")
                
                for i, opt in enumerate(options):
                    opt = opt.strip()
                    if len(opt) > 50:  # Valid option
                        # Extract title
                        if "**OPTION" in opt:
                            title = opt.split("**")[1] if "**" in opt else f"Option {i}"
                        else:
                            title = f"Option {i}"
                            
                        with st.expander(f"📄 {title}", expanded=(i == 1)):
                            st.text_area(
                                "Question Text",
                                value=opt,
                                height=200,
                                key=f"pq_opt_{i}",
                                label_visibility="collapsed"
                            )
                            
                            opt_col1, opt_col2 = st.columns(2)
                            with opt_col1:
                                if st.button("💾 Save", key=f"save_pq_{i}"):
                                    filename = save_draft_to_disk(opt, pq_subject, f"PQ_Option{i}")
                                    st.success(f"Saved!")
                            with opt_col2:
                                st.download_button(
                                    "📥 Download", 
                                    opt, 
                                    file_name=f"PQ_{pq_subject[:10]}_Opt{i}.txt",
                                    key=f"dl_pq_{i}"
                                )
                
                # Audit trail
                if "pq_meta" in st.session_state:
                    with st.expander("📊 Audit Trail", expanded=False):
                        meta = st.session_state["pq_meta"]
                        st.caption(f"Ministry: {meta.get('ministry', 'N/A')}")
                        st.caption(f"Generated: {meta.get('generated_at', 'N/A')}")
                        st.caption("Status: DRAFT - Verify before submission")

    # ==========================================================
    # FOOTER: Safety Disclaimer
    # ==========================================================
    st.divider()
    st.caption("""
    ⚠️ **IMPORTANT DISCLAIMER:** All documents generated by this tool are DRAFTS requiring human verification.
    - Verify all statistics, dates, and figures before official use
    - Placeholders marked [...] MUST be replaced with verified data
    - This tool does not guarantee accuracy of AI-generated content
    - The MP/User is solely responsible for final content submitted to Parliament
    """)