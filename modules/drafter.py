import streamlit as st
import os
import json
import time
from datetime import datetime
from modules.settings import get_valid_model, init_keys

# --- HELPER FUNCTIONS ---
def load_tenant_profile():
    """Loads MP details from local JSON profile."""
    file_path = "tenant_profile.json"
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f: return json.load(f)
        except: pass
    return {"mp_name": "Member of Parliament", "constituency": "India", "languages": ["English"]}

def save_draft_to_disk(content, subject, doc_type="Draft"):
    """Saves the generated text to a local folder."""
    folder = "saved_drafts"
    if not os.path.exists(folder): os.makedirs(folder)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_subject = "".join(c for c in subject if c.isalnum() or c in (' ','_')).strip().replace(" ", "_")[:20]
    filename = f"{folder}/{doc_type}_{timestamp}_{safe_subject}.txt"
    
    with open(filename, "w", encoding="utf-8") as f: f.write(content)
    return filename

# --- MAIN RENDERER ---
def render_drafter(username):
    st.title("✍️ Smart Drafter")
    init_keys() # Ensure API keys are loaded
    
    profile = load_tenant_profile()
    model = get_valid_model() # Load Gemini/AI Model
    
    # Updated Tabs (Removed Press Release)
    tab_letter, tab_pq = st.tabs(["📝 Official Letter", "🏛️ Parliamentary Question (PQ)"])

    # ---------------------------------------------------------
    # TAB 1: OFFICIAL LETTER (AI Powered)
    # ---------------------------------------------------------
    with tab_letter:
        st.caption("Draft formal letters to Ministries, Collectors, or Officials.")
        
        c1, c2 = st.columns([1, 1])
        with c1:
            l_recipient = st.text_input("Recipient", placeholder="e.g. Hon. Minister of Railways")
            l_subject = st.text_input("Subject", placeholder="e.g. Urgent repair of Station Road")
            l_points = st.text_area("Key Instructions / Raw Notes", height=150, placeholder="Mention the delay, public anger, and request inspection within 7 days.")
            l_lang = st.selectbox("Language", profile.get("languages", ["English"]), key="l_lang")
            
            if st.button("✨ Draft Letter", type="primary", use_container_width=True):
                if l_recipient and l_subject and model:
                    with st.spinner("AI is drafting..."):
                        prompt = f"""
                        ROLE: You are {profile.get('mp_name')}, MP for {profile.get('constituency')}.
                        TASK: Write a formal letter to {l_recipient} regarding "{l_subject}".
                        TONE: Formal, Authoritative, yet Polite.
                        LANGUAGE: {l_lang}.
                        KEY POINTS TO COVER: {l_points}
                        FORMAT: Standard Official Letter format. Return ONLY the body and signature.
                        """
                        try:
                            resp = model.generate_content(prompt)
                            st.session_state["draft_letter"] = resp.text
                        except Exception as e:
                            st.error(f"AI Error: {e}")
                elif not model:
                    st.error("⚠️ AI Model not connected. Check Settings.")
                else:
                    st.toast("⚠️ Please fill Recipient and Subject")

        with c2:
            st.markdown("##### Preview")
            if "draft_letter" in st.session_state:
                full_text = f"To,\n{l_recipient}\n\nSubject: {l_subject}\n\n{st.session_state['draft_letter']}"
                st.text_area("Final Output", value=full_text, height=450, key="letter_output")
                
                b1, b2 = st.columns(2)
                with b1:
                    if st.button("💾 Save Letter", key="save_letter"):
                        save_draft_to_disk(full_text, l_subject, "Letter")
                        st.toast("Draft Saved!")
                with b2:
                    st.download_button("📥 Download", full_text, file_name=f"Letter_{l_subject[:10]}.txt")

    # ---------------------------------------------------------
    # TAB 2: PARLIAMENTARY QUESTION (Generator Mode)
    # ---------------------------------------------------------
    with tab_pq:
        st.caption("Auto-generate 5 strategic Parliamentary Questions based on a topic.")
        
        pq_ministry = st.selectbox("Target Ministry", [
            "Ministry of Railways", "Ministry of Road Transport & Highways", 
            "Ministry of Jal Shakti", "Ministry of Agriculture", 
            "Ministry of Finance", "Ministry of Home Affairs", 
            "Ministry of Health & Family Welfare", "Ministry of Education",
            "Ministry of External Affairs", "Ministry of Rural Development"
        ])
        
        pq_subject = st.text_input("Subject / Issue", placeholder="e.g. Delay in highway construction in Belagavi")
        
        if st.button("✨ Generate 5 PQ Options", type="primary", use_container_width=True):
            if pq_subject and model:
                with st.spinner("Analyzing Parliamentary Precedents & Formatting..."):
                    
                    # Engineered Prompt for 5 Distinct Options
                    prompt = f"""
                    ROLE: You are a Senior Parliamentary Consultant for an Indian MP.
                    TASK: Create 5 DISTINCT "Parliamentary Question" options for the {pq_ministry} regarding "{pq_subject}".
                    
                    STRICT FORMATTING RULES:
                    1. Each option must follow the standard Lok Sabha/Rajya Sabha format: (a), (b), (c), (d), (e).
                    2. Part (a) must ask if the Government is aware of the issue.
                    3. Part (b) must ask for specific details/status.
                    4. Part (c) must ask for FUNDS (allocated vs utilized) or Data.
                    5. Part (d) must ask for reasons for delay/inaction.
                    6. Part (e) must ask for the timeline of completion.
                    
                    OUTPUT FORMAT:
                    Present the 5 options clearly separated by "---".
                    Do not add introductory text. Just the questions.
                    
                    Example Style:
                    OPTION 1: Focus on Funds
                    (a) whether the Govt is aware...
                    (b) ...
                    
                    OPTION 2: Focus on Timeline
                    ...
                    """
                    try:
                        resp = model.generate_content(prompt)
                        st.session_state["pq_options"] = resp.text
                    except Exception as e:
                        st.error(f"AI Error: {e}")
            elif not model:
                st.error("⚠️ AI Model not connected.")
            else:
                st.toast("⚠️ Enter a Subject")

        # --- Display Results ---
        if "pq_options" in st.session_state:
            st.markdown("---")
            st.subheader("📝 Select Your Question")
            
            # Split the AI response into options for better UI
            options = st.session_state["pq_options"].split("OPTION")
            
            for opt in options:
                if len(opt.strip()) > 10:
                    with st.expander(f"📄 Option {opt[:30].strip()}...", expanded=True):
                        # Clean up the text
                        clean_opt = "OPTION " + opt if not opt.startswith(" ") else opt
                        st.text_area("Copy this text:", value=clean_opt.strip(), height=200)
                        
                        if st.button("💾 Save this Option", key=f"save_{opt[:10]}"):
                             save_draft_to_disk(clean_opt, pq_subject, "PQ_Option")
                             st.toast("Saved to Archives!")