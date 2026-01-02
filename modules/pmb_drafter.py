import streamlit as st
import time

# NOTE: The function must accept 'username' as an argument to match main.py
def render_pmb_drafter(username):
    st.markdown("## 📜 Private Member's Bill (PMB) Studio")
    st.caption(f"Draft legislative bills for Parliament (Lok Sabha / Rajya Sabha) | User: {username}")
    
    # --- Session State for Draft ---
    if "pmb_data" not in st.session_state:
        st.session_state.pmb_data = {
            "title": "",
            "ministry": "Home Affairs",
            "category": "Constitutional Amendment",
            "objectives": "",
            "clauses": []
        }

    # --- INPUT SECTION ---
    with st.container():
        c1, c2 = st.columns([2, 1])
        with c1:
            topic = st.text_input("Bill Topic / Core Idea", placeholder="e.g. Right to Disconnect, Urban Heat Mitigation")
        with c2:
            ministry = st.selectbox("Target Ministry", ["Home Affairs", "Finance", "Environment", "Labour", "Health", "IT & Electronics"])
    
    st.markdown("---")
    
    col_left, col_right = st.columns([1, 1])
    
    # --- LEFT: DRAFTING INPUTS ---
    with col_left:
        st.subheader("1. Bill Framework")
        
        bill_type = st.radio("Bill Type", ["Ordinary Bill", "Constitutional Amendment", "Financial Bill"], horizontal=True)
        
        st.markdown("**Statement of Objects & Reasons (The 'Why')**")
        st.caption("Explain why this bill is necessary. Mention data/crises if applicable.")
        objectives = st.text_area("Objectives", height=150, placeholder="e.g. Due to rising temperatures in urban areas...")
        
        st.markdown("**Key Clauses (The 'What')**")
        st.caption("List the main provisions you want to enact.")
        clause_input = st.text_area("Clauses (Bullet points)", height=150, placeholder="- Define 'Heat Wave'\n- Mandate cool roofs for commercial buildings\n- Create a 'Heat Relief Fund'")

        if st.button("🚀 Generate Legislative Draft", type="primary"):
            if topic and objectives:
                with st.spinner("Consulting Parliamentary precedents..."):
                    time.sleep(2) # Mocking AI generation time
                    generate_draft(topic, ministry, bill_type, objectives, clause_input)
            else:
                st.warning("Please provide a Topic and Objectives.")

    # --- RIGHT: PREVIEW ---
    with col_right:
        st.subheader("2. Legislative Preview")
        
        if st.session_state.pmb_data["title"]:
            display_draft()
        else:
            st.info("Fill the form on the left and click 'Generate' to see the legal text.")

def generate_draft(topic, ministry, bill_type, objectives, clause_input):
    # This acts as the "Mock AI" for now. 
    # Later we will connect this to Groq/LLM.
    
    long_title = f"THE {topic.upper().replace(' ', ' ')} BILL, 2025"
    
    # Mocking the structured output
    st.session_state.pmb_data["title"] = long_title
    st.session_state.pmb_data["ministry"] = ministry
    st.session_state.pmb_data["type"] = bill_type
    
    # Mocking Clause Generation
    clauses = []
    raw_clauses = clause_input.split('\n')
    for i, raw in enumerate(raw_clauses):
        if raw.strip():
            clauses.append(f"**Clause {i+2}:** {raw.replace('-', '').strip()}. \n*Explanation: This clause ensures compliance with central standards.*")
            
    st.session_state.pmb_data["clauses"] = clauses
    st.session_state.pmb_data["objectives"] = objectives
    st.rerun()

def display_draft():
    data = st.session_state.pmb_data
    
    st.markdown(f"""
    <div style="background-color:white; padding:30px; border:1px solid #ddd; box-shadow: 2px 2px 10px rgba(0,0,0,0.1); color:black;">
        <div style="text-align:center; font-family:'Times New Roman';">
            <h3>AS INTRODUCED IN LOK SABHA</h3>
            <p>Bill No. _____ of 2025</p>
            <h2>{data['title']}</h2>
            <p><i>A Bill to provide for {data['title'].lower().replace('bill, 2025', '')} and for matters connected therewith.</i></p>
        </div>
        <hr>
        <p><b>BE it enacted by Parliament in the Seventy-sixth Year of the Republic of India as follows:—</b></p>
        
        <p><b>1. Short title, extent and commencement.</b><br>
        (1) This Act may be called the {data['title'].replace(', 2025', '')} Act, 2025.<br>
        (2) It extends to the whole of India.<br>
        (3) It shall come into force on such date as the Central Government may, by notification in the Official Gazette, appoint.</p>
        
        {''.join([f"<p>{c}</p>" for c in data['clauses']])}
        
        <br>
        <h4>STATEMENT OF OBJECTS AND REASONS</h4>
        <p>{data['objectives']}</p>
        <br>
        <p style="text-align:right;"><b>[MEMBER'S NAME]</b></p>
    </div>
    """, unsafe_allow_html=True)
    
    st.download_button(
        "📥 Download as .DOCX", 
        data=f"Draft Bill: {data['title']}", 
        file_name=f"{data['title']}.txt"
    )