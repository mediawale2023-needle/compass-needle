import streamlit as st
import json
import pandas as pd
from langchain_groq import ChatGroq
from modules.persistence import save_draft
from modules.utils import show_download_button, track_action

def render_csr_projects(username):
    st.header("📋 CSR Project Catalog")
    st.caption("Pitch ready-to-deploy products to corporates.")

    # 1. Load Data
    try:
        with open("project_menu.json", "r") as f:
            menu = json.load(f)
        
        # Load Company List for the Dropdown
        # We try to load csr_db.json. If missing, we use a generic list.
        try:
            with open("csr_db.json", "r") as f:
                companies = json.load(f)
                company_list = [c['Company'] for c in companies]
        except:
            company_list = ["Reliance Industries", "Tata Group", "HDFC Bank", "Adani Foundation"]
            
    except Exception as e:
        st.error(f"Menu Data missing: {e}. Please run 'generate_project_menu.py' locally and upload 'project_menu.json'.")
        return

    # 2. The "Shopping Cart" Session
    if 'cart' not in st.session_state:
        st.session_state.cart = {}

    # 3. Layout: Catalog vs Cart
    col_catalog, col_cart = st.columns([2, 1])

    with col_catalog:
        st.subheader("Select Projects")
        for item in menu:
            with st.expander(f"🛠️ {item.get('Name', 'Project')} ({item.get('Cost_Per_Unit', 'N/A')})"):
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.write(f"**Impact:** {item.get('Impact', '')}")
                    st.write(f"**Specs:** {item.get('Specs', '')}")
                    st.info(f"💡 *{item.get('Pitch', '')}*")
                with c2:
                    # Quantity Selector
                    code = item.get('Code', 'UNKNOWN')
                    qty = st.number_input("Qty", min_value=0, max_value=50, key=f"q_{code}")
                    
                    if st.button("Add", key=f"add_{code}"):
                        if qty > 0:
                            cost = item.get('Cost_Raw', 0)
                            st.session_state.cart[code] = {
                                "Name": item.get('Name', 'Project'),
                                "Qty": qty,
                                "Unit_Cost": cost,
                                "Total": qty * cost
                            }
                            st.success(f"Added {qty} {item.get('Name')}")

    # 4. The Cart & Generator
    with col_cart:
        st.subheader("📝 Your Proposal")
        
        if not st.session_state.cart:
            st.info("Select projects to build a proposal.")
        else:
            total_cost = 0
            cart_details = []
            
            for code, data in st.session_state.cart.items():
                st.write(f"**{data['Qty']} x {data['Name']}**")
                st.caption(f"₹{data['Total']:,}")
                total_cost += data['Total']
                cart_details.append(f"{data['Qty']} units of {data['Name']} (Total: ₹{data['Total']})")
                
            st.divider()
            st.metric("Total Ask", f"₹{total_cost:,}")
            
            # Target Company
            target_comp = st.selectbox("Pitch To:", company_list)
            
            if st.button("🚀 Generate DPR", type="primary"):
                api_key = st.session_state.get('groq_api_key')
                if not api_key:
                    st.error("Enter API Key in Sidebar")
                else:
                    with st.spinner("Writing Detailed Project Report..."):
                        try:
                            llm = ChatGroq(temperature=0.5, groq_api_key=api_key, model_name="llama-3.1-8b-instant")
                            
                            items_str = "\n".join(cart_details)
                            prompt = f"""
                            Act as a Professional Consultant for an Indian MP.
                            Write a 'Detailed Project Proposal' (DPR) Executive Summary for {target_comp}.
                            
                            The Ask:
                            {items_str}
                            Grand Total: ₹{total_cost:,}
                            
                            Structure:
                            1. Concept Note: Why this is urgent for the constituency.
                            2. Technical Specifications: Brief mention of high-quality standards.
                            3. Impact Assessment: How many lives changed.
                            4. Budget Summary.
                            5. Branding Value: How {target_comp} will get visibility (branding on walls/plaques).
                            
                            Tone: Professional, Technocratic, Ready-to-Sign.
                            """
                            
                            dpr = llm.invoke(prompt).content
                            
                            st.subheader("Final Proposal")
                            st.text_area("DPR Content", dpr, height=400)
                            
                            # Save & Download
                            save_draft(username, f"DPR: {target_comp} (₹{total_cost})", dpr, "CSR Proposal")
                            show_download_button(dpr, f"DPR_{target_comp}")
                            track_action(f"Generated DPR for {target_comp}")
                            
                        except Exception as e:
                            st.error(f"AI Error: {e}")
                        
            if st.button("Clear Cart"):
                st.session_state.cart = {}
                st.rerun()