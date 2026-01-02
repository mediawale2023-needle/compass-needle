import streamlit as st
from groq import Groq
import os

def render_translator(username):
    st.markdown("## 🗣️ Bhashini: Neural Translator")
    st.caption("AI-Powered Translation for Official Legislative Correspondence")

    # Layout
    col_input, col_output = st.columns(2)

    with col_input:
        st.subheader("📝 Source Text")
        source_text = st.text_area("Paste English or Regional text here...", height=300)

    with col_output:
        st.subheader("🎯 Target Output")
        
        # Language Selector
        target_lang = st.selectbox(
            "Select Target Language",
            ["Hindi", "Marathi", "Gujarati", "Tamil", "Telugu", "Kannada", "Malayalam", "Bengali", "English"],
            index=0
        )
        
        # Tone Selector
        tone = st.radio("Tone", ["Formal (Official)", "Conversational (Social Media)"], horizontal=True)

        # Action Button
        if st.button("🚀 Translate Now", type="primary", use_container_width=True):
            if not source_text:
                st.warning("Please enter text to translate.")
            else:
                api_key = st.session_state.get('groq_api_key')
                if not api_key:
                    st.error("⚠️ Groq API Key missing. Please set it in the Sidebar.")
                else:
                    try:
                        with st.spinner(f"Translating to {target_lang}..."):
                            client = Groq(api_key=api_key)
                            
                            prompt = f"""
                            You are an expert translator for the Indian Government. 
                            Translate the following text into {target_lang}.
                            
                            Context: This is for {tone} use by a Member of Parliament.
                            Requirement: Ensure grammatical correctness and appropriate honorifics.
                            
                            Text to translate:
                            "{source_text}"
                            
                            Output ONLY the translation. No explanations.
                            """
                            
                            completion = client.chat.completions.create(
                                model="llama-3.1-8b-instant",
                                messages=[{"role": "user", "content": prompt}],
                                temperature=0.3
                            )
                            
                            translated_text = completion.choices[0].message.content
                            st.text_area("Result", value=translated_text, height=300)
                            st.success("✅ Translation Complete")
                            
                    except Exception as e:
                        st.error(f"Translation Error: {e}")

    # History / Notes
    with st.expander("ℹ️ Translation Tips"):
        st.markdown("""
        * **Formal:** Use for letters to Ministers, official press releases.
        * **Conversational:** Use for WhatsApp replies, Tweets, or public addresses.
        * **Accuracy:** The AI understands Indian context (e.g., 'Yojanas', 'Mantralaya').
        """)