import streamlit as st
import pandas as pd
import json
import os
import requests
import pdfplumber
from pathlib import Path
from datetime import datetime
import bcrypt
import re
import sys
from dotenv import load_dotenv

# --- Load Environment Variables ---
load_dotenv()

# --- Database Connection ---
# Import from root db.py (NOT sansadx_backend/db.py) to use the same sansadx.db as mp_dashboard
try:
    from db import SessionLocal, Tenant, User, TenantProfile, init_db
except ImportError:
    st.error("Could not import 'db.py'. Please ensure 'db.py' exists in the project root.")
    sys.exit(1)

# --- Constants ---
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000") 
GEOGRAPHY_BASE_PATH = Path(__file__).parent / "data" / "geography"
METADATA_PATH = Path(__file__).parent / "data" / "constituency_metadata.json"
OVERRIDES_PATH = Path("tenant_overrides.json")

# --- 🇮🇳 MASTER LIST OF 543 LOK SABHA SEATS ---
from modules.constituencies import ALL_CONSTITUENCIES

# --- Page Config ---
st.set_page_config(
    page_title="Needle Admin Dashboard",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Session State ---
if 'admin_authenticated' not in st.session_state:
    st.session_state.admin_authenticated = False
if 'admin_user' not in st.session_state:
    st.session_state.admin_user = None

# --- Helper Functions ---
def hash_password(password: str) -> str:
    """Hash password using bcrypt for secure storage"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, stored_hash: str) -> bool:
    """Verify password against stored hash. Supports bcrypt and legacy plaintext fallback."""
    # Try bcrypt first
    try:
        if stored_hash.startswith('$2b$') or stored_hash.startswith('$2a$'):
            return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))
    except Exception:
        pass
    # Fallback: legacy plaintext match
    return stored_hash == password

def verify_admin_login(username: str, password: str) -> dict:
    """Verify admin credentials against the database"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if user and user.role in ("admin", "super_admin", "sysadmin"):
            if verify_password(password, user.password_hash):
                # Auto-rehash legacy passwords to bcrypt
                if not (user.password_hash.startswith('$2b$') or user.password_hash.startswith('$2a$')):
                    user.password_hash = hash_password(password)
                    db.commit()
                return {"success": True, "username": user.username, "tenant_id": user.tenant_id}
        return {"success": False}
    finally:
        db.close()

def get_all_mps() -> list:
    """Get all MPs with User-level data (single query)"""
    from sqlalchemy.orm import joinedload
    db = SessionLocal()
    try:
        tenants = db.query(Tenant).options(joinedload(Tenant.users)).all()
        result = []
        for t in tenants:
            for u in t.users:
                user_constituency = getattr(u, 'constituency', None) or t.constituency or "India"
                result.append({
                    "tenant_id": t.id,
                    "user_id": u.id,
                    "mp_name": t.name,
                    "display_name": getattr(u, 'display_name', None) or t.name,
                    "username": u.username,
                    "role": u.role,
                    "house": getattr(u, 'house', None) or "Lok Sabha",
                    "parliamentary_constituency": user_constituency, 
                    "whatsapp_number": t.whatsapp_number,
                    "created_at": t.created_at.strftime("%Y-%m-%d") if t.created_at else "N/A"
                })
        return result
    finally:
        db.close()

def create_mp(name: str, username: str, password: str, constituency: str, whatsapp_number: str = "", house: str = "Lok Sabha", display_name: str = "", state: str = "", party: str = "Independent", key_facts: list = None, languages: list = None, alt_names: list = None) -> dict:
    """Create a new MP (Tenant + User + TenantProfile) with full profile data"""
    db = SessionLocal()
    try:
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            return {"success": False, "error": "Username already exists"}
        
        # Create Tenant
        new_tenant = Tenant(
            name=name,
            constituency=constituency,
            whatsapp_number=whatsapp_number or f"temp_{datetime.now().timestamp()}",
            subscription_plan="Pro",
            config={"language": "English", "type": house.upper().replace(" ", "_"), "map_enabled": True}
        )
        db.add(new_tenant)
        db.flush()
        
        # Create User with House and Display Name
        new_user = User(
            tenant_id=new_tenant.id,
            username=username,
            password_hash=hash_password(password),
            role="mp",
            constituency=constituency,
            house=house,
            display_name=display_name or name
        )
        db.add(new_user)
        
        # Create TenantProfile
        profile_data = {
            "key_facts": key_facts or [],
            "languages": languages or ["English", "Hindi"],
            "vocabulary_guide": {},
            "sovereignty_rules": "",
            "alt_names": alt_names or [],
        }
        new_profile = TenantProfile(
            tenant_id=new_tenant.id,
            mp_name=display_name or name,
            constituency=constituency,
            state=state,
            house=house,
            party=party,
            profile_data=profile_data,
        )
        db.add(new_profile)
        db.commit()
        
        return {"success": True, "tenant_id": new_tenant.id, "user_id": new_user.id}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()

def update_mp_constituency(username: str, new_constituency: str) -> dict:
    """Update constituency for existing MP (User & Tenant)"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return {"success": False, "error": "User not found"}
        
        # Update User level (Primary for Dashboard)
        user.constituency = new_constituency
        
        # Update Tenant level
        if user.tenant_id:
            tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
            if tenant:
                tenant.constituency = new_constituency
        
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()

def reset_mp_password(username: str, new_password: str) -> dict:
    """Reset an MP's password"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return {"success": False, "error": "User not found"}
        
        user.password_hash = hash_password(new_password)
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()

def ensure_admin_exists():
    """Ensure at least one admin user exists for login"""
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.role == "admin").first()
        if not admin:
            admin_tenant = db.query(Tenant).filter(Tenant.name == "System Admin").first()
            if not admin_tenant:
                admin_tenant = Tenant(
                    name="System Admin", constituency="System", whatsapp_number="system_admin",
                    subscription_plan="Admin", config={}
                )
                db.add(admin_tenant)
                db.flush()
            
            admin_user = User(
                tenant_id=admin_tenant.id, username="sysadmin", password_hash=hash_password("admin123"), role="admin"
            )
            db.add(admin_user)
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

# --- Overrides (Rulebook) Functions ---
def load_overrides() -> dict:
    if OVERRIDES_PATH.exists():
        with open(OVERRIDES_PATH, 'r', encoding='utf-8') as f: return json.load(f)
    return {}

def save_overrides(data: dict) -> bool:
    try:
        with open(OVERRIDES_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e: return False

# --- PDF Parsing Functions ---
def parse_polling_station_pdf(pdf_file) -> list:
    stations = []
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        for row in table:
                            if row and len(row) >= 2:
                                station_data = extract_station_from_row(row)
                                if station_data: stations.append(station_data)
                else:
                    text = page.extract_text()
                    if text: stations.extend(extract_stations_from_text(text))
    except Exception as e: st.error(f"PDF error: {e}")
    seen = set()
    unique = []
    for s in stations:
        if s.get("station_number") and s["station_number"] not in seen:
            seen.add(s["station_number"])
            unique.append(s)
    return unique

def extract_station_from_row(row: list) -> dict:
    cleaned = [str(cell).strip() if cell else "" for cell in row]
    num, loc, bldg = "", "", ""
    for cell in cleaned:
        if re.match(r'^\d+$', cell) and not num: num = cell
        elif len(cell) > 3 and not cell.isdigit():
            if not loc: loc = cell
            elif not bldg: bldg = cell
    if num or loc: return {"station_number": num, "locality": loc, "building_name": bldg}
    return None

def extract_stations_from_text(text: str) -> list:
    stations = []
    for line in text.split('\n'):
        line = line.strip()
        if not line: continue
        match = re.match(r'(\d+)\s*[-:]\s*(.+)', line) or re.match(r'Station\s*(\d+)\s*[-:]?\s*(.+)', line)
        if match: stations.append({"station_number": match.group(1), "locality": match.group(2).strip(), "building_name": ""})
    return stations

# --- Geography File Functions ---
def get_parliamentary_constituencies() -> list:
    GEOGRAPHY_BASE_PATH.mkdir(parents=True, exist_ok=True)
    return [d.name for d in GEOGRAPHY_BASE_PATH.iterdir() if d.is_dir()]

def get_assembly_constituencies(parliamentary: str) -> list:
    path = GEOGRAPHY_BASE_PATH / parliamentary
    if not path.exists(): return []
    return [f.stem for f in path.glob("*.json")]

def save_geography_data(parliamentary: str, assembly: str, data: list) -> bool:
    try:
        path = GEOGRAPHY_BASE_PATH / parliamentary
        path.mkdir(parents=True, exist_ok=True)
        with open(path / f"{assembly}.json", 'w', encoding='utf-8') as f: json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception: return False

def load_geography_data(parliamentary: str, assembly: str) -> list:
    filepath = GEOGRAPHY_BASE_PATH / parliamentary / f"{assembly}.json"
    if filepath.exists():
        with open(filepath, 'r', encoding='utf-8') as f: return json.load(f)
    return []

# --- Metadata Functions ---
def load_metadata() -> dict:
    if METADATA_PATH.exists():
        with open(METADATA_PATH, 'r', encoding='utf-8') as f: return json.load(f)
    return {}

def save_metadata(data: dict) -> bool:
    try:
        METADATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(METADATA_PATH, 'w', encoding='utf-8') as f: json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception: return False

# --- Custom CSS ---
def inject_css():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
        html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
        .admin-header { 
            background: linear-gradient(135deg, #1e3a5f 0%, #0d2137 100%); 
            padding: 1.5rem; 
            border-radius: 10px; 
            margin-bottom: 2rem;
            color: white;
        }
        .admin-header h1 { color: white; margin: 0; }
        .admin-header p { color: #a0c4e8; margin: 0.5rem 0 0 0; }
    </style>
    """, unsafe_allow_html=True)

# --- Main Application ---
def main():
    inject_css()
    init_db()
    ensure_admin_exists()
    
    # Login Screen
    if not st.session_state.admin_authenticated:
        st.markdown("<div style='text-align: center; margin-top: 100px;'><h1>⚙️ Needle Admin Dashboard</h1><p>Administrative Control Panel</p></div>", unsafe_allow_html=True)
        _, col, _ = st.columns([1, 1, 1])
        with col:
            with st.form("admin_login"):
                u = st.text_input("Username")
                p = st.text_input("Password", type="password")
                if st.form_submit_button("Login", use_container_width=True):
                    res = verify_admin_login(u, p)
                    if res["success"]:
                        st.session_state.admin_authenticated = True
                        st.session_state.admin_user = res["username"]
                        st.rerun()
                    else: st.error("❌ Invalid credentials")
        return
    
    # Dashboard Header
    st.markdown("""
    <div class="admin-header">
        <h1>⚙️ Needle Admin Dashboard</h1>
        <p>Manage MPs, Geography Data, and System Configuration</p>
    </div>
    """, unsafe_allow_html=True)
    
    with st.sidebar:
        st.write(f"Logged in as: **{st.session_state.admin_user}**")
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.admin_authenticated = False
            st.rerun()
        st.divider()
        st.caption("Needle Admin v1.1")
    
    tab1, tab2, tab3, tab4 = st.tabs(["👥 MP Management", "🗺️ Geography Upload", "📋 Constituency Metadata", "🌍 Geography Rules"])
    
    # ===================
    # TAB 1: MP Management
    # ===================
    with tab1:
        st.header("👥 MP Management")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("Add New MP")
            with st.form("create_mp_form"):
                mp_name = st.text_input("MP Name *", placeholder="Hon. Shri/Smt...")
                mp_display = st.text_input("Display Name", placeholder="Name shown in dashboard (defaults to MP Name)")
                mp_house = st.selectbox("House *", options=["Lok Sabha", "Rajya Sabha"], index=0)
                mp_username = st.text_input("Username *", placeholder="username")
                mp_password = st.text_input("Password *", type="password")
                if mp_house == "Lok Sabha":
                    mp_constituency = st.selectbox("Parliamentary Constituency *", options=ALL_CONSTITUENCIES, index=0)
                else:
                    mp_constituency = st.text_input("State / Nominated", placeholder="e.g. Maharashtra")
                mp_state = st.text_input("State *", placeholder="e.g. Karnataka, Maharashtra")
                mp_party = st.text_input("Party", placeholder="e.g. BJP, INC (defaults to Independent)")
                mp_whatsapp = st.text_input("WhatsApp Number", placeholder="+91...")
                
                st.caption("PROFILE DATA (for News & Drafter)")
                mp_languages = st.text_input("Languages (comma-separated)", placeholder="English, Hindi, Kannada", value="English, Hindi")
                mp_key_facts = st.text_area("Key Facts (one per line)", placeholder="Major industrial hub\nBorder district\nKey crops: wheat, rice", height=100)
                mp_alt_names = st.text_input("Alt Names (comma-separated)", placeholder="e.g. Belagavi, Belgaum", help="Alternate spellings for constituency used in news search")
                
                if st.form_submit_button("Create MP", use_container_width=True):
                    if mp_name and mp_username and mp_password:
                        # Parse comma-separated fields
                        langs = [l.strip() for l in mp_languages.split(",") if l.strip()] if mp_languages else ["English", "Hindi"]
                        facts = [f.strip() for f in mp_key_facts.strip().split("\n") if f.strip()] if mp_key_facts else []
                        alts = [a.strip() for a in mp_alt_names.split(",") if a.strip()] if mp_alt_names else []
                        
                        result = create_mp(
                            mp_name, mp_username, mp_password,
                            mp_constituency or "India", mp_whatsapp,
                            house=mp_house,
                            display_name=mp_display or mp_name,
                            state=mp_state,
                            party=mp_party or "Independent",
                            key_facts=facts,
                            languages=langs,
                            alt_names=alts,
                        )
                        if result["success"]:
                            st.success(f"Created MP '{mp_name}' ({mp_house}) with full profile")
                            st.rerun()
                        else: st.error(result.get('error'))
                    else: st.warning("Fill all required fields")
        
        with col2:
            st.subheader("✏️ Manage Existing MP")
            mps = get_all_mps()
            mp_usernames = [mp["username"] for mp in mps if mp["role"] != "admin"]
            
            if mp_usernames:
                selected_user = st.selectbox("Select MP to Edit", mp_usernames)
                current_mp_data = next((item for item in mps if item["username"] == selected_user), None)
                curr_const = current_mp_data['parliamentary_constituency'] if current_mp_data else "New Delhi"
                default_idx = ALL_CONSTITUENCIES.index(curr_const) if curr_const in ALL_CONSTITUENCIES else 0

                with st.form("edit_mp_form"):
                    st.write(f"Editing: **{selected_user}**")
                    new_const = st.selectbox("Constituency (Local Pulse)", options=ALL_CONSTITUENCIES, index=default_idx)
                    new_pass = st.text_input("New Password (Optional)", type="password", placeholder="Leave blank to keep current")
                    
                    if st.form_submit_button("💾 Save Changes", use_container_width=True):
                        if new_const and new_const != curr_const:
                            c_res = update_mp_constituency(selected_user, new_const)
                            if c_res["success"]: st.success(f"✅ Constituency updated to: {new_const}")
                            else: st.error(f"❌ Failed to update constituency: {c_res.get('error')}")
                        if new_pass:
                            p_res = reset_mp_password(selected_user, new_pass)
                            if p_res["success"]: st.success("✅ Password updated")
                            else: st.error("❌ Failed to update password")
                        if (new_const and new_const != curr_const) or new_pass:
                            st.rerun()
            else:
                st.info("No MPs found.")
        
        st.divider()
        st.subheader("Registered MPs")
        if mps:
            mp_list = [mp for mp in mps if mp["role"] != "admin"]
            if mp_list:
                df = pd.DataFrame(mp_list)
                st.dataframe(
                    df[["tenant_id", "display_name", "username", "house", "parliamentary_constituency", "whatsapp_number", "created_at"]], 
                    use_container_width=True, 
                    hide_index=True
                )

    # ===================
    # TAB 2: Geography Upload
    # ===================
    with tab2:
        st.header("🗺️ Geography Upload")
        col1, col2 = st.columns(2)
        with col1: p_const = st.text_input("Parliamentary Constituency", key="geo_p")
        with col2: a_const = st.text_input("Assembly Constituency", key="geo_a")
        
        uploaded_pdf = st.file_uploader("Upload Election Commission PDF", type=["pdf"])
        if uploaded_pdf and p_const and a_const:
            if st.button("🔍 Parse PDF", use_container_width=True):
                with st.spinner("Parsing..."):
                    stations = parse_polling_station_pdf(uploaded_pdf)
                    if stations:
                        st.session_state['parsed_stations'] = stations
                        st.session_state['curr_p'] = p_const
                        st.session_state['curr_a'] = a_const
                        st.success(f"✅ Extracted {len(stations)} stations")
                    else: st.warning("⚠️ No data found")

        if 'parsed_stations' in st.session_state:
            st.divider()
            st.subheader("✏️ Edit JSON")
            json_str = json.dumps(st.session_state['parsed_stations'], indent=2, ensure_ascii=False)
            edited_json = st.text_area("JSON Editor", value=json_str, height=400)
            
            c1, c2 = st.columns(2)
            with c1:
                if st.button("💾 Save", use_container_width=True, type="primary"):
                    try:
                        data = json.loads(edited_json)
                        if save_geography_data(st.session_state['curr_p'], st.session_state['curr_a'], data):
                            st.success("✅ Saved!")
                            del st.session_state['parsed_stations']
                            try: requests.post(f"{API_URL}/geography/reload") 
                            except: pass
                    except: st.error("Invalid JSON")
            with c2:
                if st.button("🗑️ Discard"): 
                    del st.session_state['parsed_stations']
                    st.rerun()

        st.divider()
        st.subheader("📁 Saved Files")
        pl = get_parliamentary_constituencies()
        if pl:
            for p in pl:
                with st.expander(f"🏛️ {p}"):
                    al = get_assembly_constituencies(p)
                    for a in al:
                        cx, cd = st.columns([4,1])
                        with cx: st.write(f"**{a}** ({len(load_geography_data(p, a))} locs)")
                        with cd:
                            if st.button("🗑️", key=f"del_{p}_{a}"):
                                try: 
                                    os.remove(GEOGRAPHY_BASE_PATH / p / f"{a}.json")
                                    st.rerun()
                                except: pass

    # ===================
    # TAB 3: Metadata
    # ===================
    with tab3:
        st.header("📋 Metadata")
        meta = load_metadata()
        plist = get_parliamentary_constituencies()
        sel_p = st.selectbox("Select Constituency", [""] + plist) if plist else st.text_input("Enter Constituency")
        
        if sel_p:
            curr_data = meta.get(sel_p, {"mp_name":"", "party":"", "district":"", "state":""})
            m_json = st.text_area("Metadata JSON", value=json.dumps(curr_data, indent=2), height=400)
            if st.button("💾 Save Metadata", type="primary"):
                try:
                    meta[sel_p] = json.loads(m_json)
                    save_metadata(meta)
                    st.success("✅ Saved")
                except: st.error("Invalid JSON")

    # ===================
    # TAB 4: Rules
    # ===================
    with tab4:
        st.header("🌍 Geography Rules")
        overrides = load_overrides()
        geo_rules = overrides.get("geo_overrides", {})
        mps = get_all_mps()
        if mps:
            t_opts = {f"{m['mp_name']} ({m['parliamentary_constituency']}) [ID: {m['tenant_id']}]": str(m['tenant_id']) for m in mps}
            sel_mp = st.selectbox("Select MP", list(t_opts.keys()))
            if sel_mp:
                tid = t_opts[sel_mp]
                rules = geo_rules.get(tid, {})
                
                c1, c2, c3 = st.columns([2,2,1])
                with c1: loc_in = st.text_input("Location (Input)")
                with c2: const_out = st.text_input("Correct Constituency", value=next(m['parliamentary_constituency'] for m in mps if str(m['tenant_id']) == tid))
                with c3: 
                    st.write("")
                    st.write("")
                    if st.button("Add Rule"):
                        if loc_in and const_out:
                            if "geo_overrides" not in overrides: overrides["geo_overrides"] = {}
                            if tid not in overrides["geo_overrides"]: overrides["geo_overrides"][tid] = {}
                            overrides["geo_overrides"][tid][loc_in.strip().lower()] = const_out
                            save_overrides(overrides)
                            st.success("✅ Rule Added")
                            st.rerun()

                if rules:
                    df = pd.DataFrame([{"Input": k, "Output": v} for k,v in rules.items()])
                    edited = st.data_editor(df, use_container_width=True, num_rows="dynamic", key=f"ed_{tid}")
                    if st.button("💾 Save Table"):
                        new_r = {row["Input"]: row["Output"] for _, row in edited.iterrows() if row["Input"] and row["Output"]}
                        if "geo_overrides" not in overrides: overrides["geo_overrides"] = {}
                        overrides["geo_overrides"][tid] = new_r
                        save_overrides(overrides)
                        st.success("✅ Saved")
        else: st.warning("Create MP first")

if __name__ == "__main__":
    main()