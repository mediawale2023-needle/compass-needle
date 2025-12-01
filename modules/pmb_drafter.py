import streamlit as st
from langchain_groq import ChatGroq
import textwrap

def render_pmb_drafter():
    st.title("🏛️ Private Member Bill Drafter")
    st.caption("Generate a structurally sound draft of a Private Member Bill (PMB).")

    # --- INPUTS ---
    bill_topic = st.text_input("Bill Title (e.g., The Right to Mental Health Care Bill, 2026)", 
                               placeholder="The [Your Topic] Bill, [Year]")
    
    intent_summary = st.text_area(
        "Statement of Objects and Reasons (The Policy Goal)", 
        placeholder="Briefly state why this law is needed (e.g., To ensure citizens have a legal right to internet access as a basic service). Max 200 words.",
        height=150
    )
    
    if st.button("Generate Legal Draft"):
        if not bill_topic or not intent_summary:
            st.error("Please provide both the Bill Title and the Policy Goal.")
            return

        # Check API Key
        api_key = st.session_state.get('groq_api_key')
        if not api_key:
            st.error("Please enter the Groq API Key in the Co-Pilot sidebar.")
            return

        with st.spinner("Generating legal structure and provisions..."):
            try:
                llm = ChatGroq(temperature=0.2, groq_api_key=api_key, model_name="llama-3.1-8b-instant")
                
                # --- THE STRICT LEGAL PROMPT ---
                prompt = f"""
                You are a Legislative Drafting Consultant specializing in Indian Union Law. 
                Your task is to generate the complete, formal structure for a Private Member's Bill, following the rigid format of a Union Act.

                Draft MUST include:
                1. A brief 'Statement of Objects and Reasons' based on the user's input.
                2. The standard 'Enacting Formula' for a Bill introduced in Parliament.
                3. A minimum of 5, maximum of 7 Clauses, using formal legal language.
                
                User's Bill Title: {bill_topic}
                User's Policy Goal (for SOR): {intent_summary}
                
                Generate the full, single-block text draft now.
                """
                
                draft = llm.invoke(prompt).content
                
                st.success("Draft Generated!")
                st.caption("Review required by legal counsel before submission.")
                
                # Use st.code to preserve formatting, which is critical for legal drafts
                st.code(draft, language="text", line_numbers=True)

            except Exception as e:
                st.error(f"Generation Failed: {e}. Check key and network.")

# Ensure the module can run if imported
if __name__ == '__main__':
    render_pmb_drafter()