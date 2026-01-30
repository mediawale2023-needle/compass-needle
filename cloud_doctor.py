import streamlit as st
import os

st.set_page_config(page_title="Cloud Doctor", page_icon="🕵️‍♂️")

st.title("🕵️‍♂️ Railway Environment Doctor")

# 1. READ THE RAW VARIABLE
raw_key = os.getenv("GEMINI_API_KEY")

st.subheader("Diagnostic Results")

if raw_key is None:
    st.error("❌ RESULT: The variable 'GEMINI_API_KEY' does NOT exist.")
    st.markdown("""
    **Diagnosis:** Railway is not injecting the variable.
    **Fix:**
    1. Go to Railway > Variables.
    2. Check for typos (e.g. `GEMINI_API_KEY ` with a space?).
    3. Delete it and add it again.
    """)
elif raw_key == "":
    st.error("❌ RESULT: The variable exists, but it is EMPTY.")
else:
    st.success("✅ RESULT: The variable was found!")
    st.info(f"Key Length: {len(raw_key)} characters")
    st.text(f"First 4 chars: {raw_key[:4]}...")
    st.text(f"Last 4 chars: ...{raw_key[-4:]}")
    
    # Check for hidden spaces (VERY COMMON)
    if raw_key.strip() != raw_key:
        st.warning("⚠️ WARNING: Your key has hidden spaces at the start or end!")
        st.markdown("Go to Railway and remove the spaces.")

# 2. LIST ALL VARIABLES (Safe Mode)
with st.expander("View All Server Variables (Safe List)"):
    st.write("The following variables are visible to Python:")
    for key in os.environ.keys():
        if "KEY" in key or "SECRET" in key or "TOKEN" in key:
            st.write(f"- `{key}`: [HIDDEN]")
        else:
            st.write(f"- `{key}`: {os.environ[key]}")