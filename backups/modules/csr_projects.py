import streamlit as st
import json
from modules.settings import get_valid_model, init_keys
from modules.persistence import save_draft
from modules.utils import show_download_button, track_action

def render_csr_projects(username):
    st.header("📋 CSR Project Catalog")
    st.caption("Pitch ready-to-deploy products to corporates.")
    
    init_keys()

    # 1. Load Data
    try:
        # Fallback Mock Data if file is missing (Prevents Crash)
        menu = [
            {"Name": "Smart Classroom", "Code": "EDU01", "Cost_Per_Unit": "₹2.5L", "Cost_Raw": 250000, "Impact": "50 Students", "Specs": "75inch Panel, UPS", "Pitch": "Digital literacy for rural kids"},
            {"Name": "Solar Street Light", "Code": "INF01", "Cost_Per_Unit": "₹25k", "Cost_Raw": 25000, "Impact": "Safety for 10 homes", "Specs": "20W LED, Lithium Bat", "Pitch": "Safety for women at night"},
            {"Name": "RO Water Plant", "Code": "WAT01", "Cost_Per_Unit": "₹4.5L", "Cost_Raw": 450000, "Impact": "Whole Village", "Specs": "1000 LPH, SS Tank", "Pitch": "Clean water, disease free"}
        ]
        
        # Try to load real file if exists
        try:
            with open("project_menu.json", "r") as f:
                menu = json.load(f)
        except: pass
        
        # Company List
        company_list = ["Reliance Industries", "Tata Group", "HDFC Bank", "Adani Foundation", "Infosys Foundation"]
        try:
            with open("csr_db.json", "r") as f:
                companies = json.load(f)
                company_list = [c['Company'] for c in companies]
        except: pass
            
    except Exception as e:
        st.error(f"Data Error: {e}")
        return

    # 2. The "Shopping Cart" Session
    if 'cart' not in st.session_state: st.session_state.cart = {}

    # 3. Layout: Catalog vs Cart
    col_catalog, col_cart = st.columns([2, 1])

    with col_catalog:
        st.subheader("Select Projects")
        for item in menu:
            with st.expander(f"🛠️ {item.get('Name', 'Project')} ({item.get('Cost_Per_Unit', 'N/A')})"):
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.write(f"**Impact:** {item.get('Impact', '')}")
                    st.caption(f"**Specs:** {item.get('Specs', '')}")
                    st.info(f"💡 *{item.get('Pitch', '')}*")
                with c2:
                    code = item.get('Code', 'UNKNOWN')
                    # Use a unique key for every input to avoid duplicate ID errors
                    qty = st.number_input("Qty", min_value=0, max_value=50, key=f"q_{code}_{item.get('Name')}")
                    
                    if st.button("Add", key=f"add_{code}_{item.get('Name')}"):
                        if qty > 0:
                            cost = item.get('Cost_Raw', 0)
                            st.session_state.cart[code] = {
                                "Name": item.get('Name', 'Project'),
                                "Qty": qty,
                                "Unit_Cost": cost,
                                "Total": qty * cost
                            }
                            st.toast(f"Added {qty} {item.get('Name')}")

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
            
            target_comp = st.selectbox("Pitch To:", company_list)
            
            if st.button("🚀 Generate DPR", type="primary"):
                with st.spinner("Writing Detailed Project Report (Gemini)..."):
                    # 👇 CHANGED: Switched from Groq to Gemini
                    model = get_valid_model()
                    
                    if model:
                        try:
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
                            
                            response = model.generate_content(prompt)
                            dpr = response.text
                            
                            st.subheader("Final Proposal")
                            with st.container(border=True):
                                st.markdown(dpr)
                            
                            save_draft(username, f"DPR: {target_comp} (₹{total_cost})", dpr, "CSR Proposal")
                            show_download_button(dpr, f"DPR_{target_comp}")
                            track_action(f"Generated DPR for {target_comp}")
                            
                        except Exception as e:
                            st.error(f"AI Error: {e}")
                    else:
                        st.error("System Offline. Check Settings > API Key.")
                        
            if st.button("Clear Cart"):
                st.session_state.cart = {}
                st.rerun()