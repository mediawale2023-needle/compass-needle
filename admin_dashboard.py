import streamlit as st
import pandas as pd
import json
import os
import pdfplumber
from pathlib import Path
from datetime import datetime
import hashlib
import re

# --- Database Connection ---
import sys
sys.path.insert(0, str(Path(__file__).parent / "sansadx-backend"))
from db import SessionLocal, Tenant, User, init_db

# --- Constants ---
GEOGRAPHY_BASE_PATH = Path(__file__).parent / "data" / "geography"
METADATA_PATH = Path(__file__).parent / "data" / "constituency_metadata.json"

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
    """Simple password hashing for storage"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_admin_login(username: str, password: str) -> dict:
    """Verify admin credentials against the database"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if user and user.role == "admin":
            # For simplicity, we check plain password or hashed
            # Accept both "admin" and "super_admin" roles
            if user.password_hash == password or user.password_hash == hash_password(password):
                return {"success": True, "username": user.username, "tenant_id": user.tenant_id}
        return {"success": False}
    finally:
        db.close()

def get_all_mps() -> list:
    """Get all MPs (Tenants with their Users)"""
    db = SessionLocal()
    try:
        tenants = db.query(Tenant).all()
        result = []
        for t in tenants:
            users = db.query(User).filter(User.tenant_id == t.id).all()
            for u in users:
                result.append({
                    "tenant_id": t.id,
                    "user_id": u.id,
                    "mp_name": t.name,
                    "username": u.username,
                    "role": u.role,
                    "parliamentary_constituency": t.constituency,
                    "whatsapp_number": t.whatsapp_number,
                    "created_at": t.created_at.strftime("%Y-%m-%d") if t.created_at else "N/A"
                })
        return result
    finally:
        db.close()

def create_mp(name: str, username: str, password: str, constituency: str, whatsapp_number: str = "") -> dict:
    """Create a new MP (Tenant + User)"""
    db = SessionLocal()
    try:
        # Check if username exists
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            return {"success": False, "error": "Username already exists"}
        
        # Create Tenant
        new_tenant = Tenant(
            name=name,
            constituency=constituency,
            whatsapp_number=whatsapp_number or f"temp_{datetime.now().timestamp()}",
            subscription_plan="Pro",
            config={"language": "English", "type": "LOK_SABHA", "map_enabled": True}
        )
        db.add(new_tenant)
        db.flush()  # Get the ID
        
        # Create User
        new_user = User(
            tenant_id=new_tenant.id,
            username=username,
            password_hash=password,  # Store plain for now (as per existing system)
            role="mp"
        )
        db.add(new_user)
        db.commit()
        
        return {"success": True, "tenant_id": new_tenant.id, "user_id": new_user.id}
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
        
        user.password_hash = new_password  # Store plain for now
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
            # Create default admin tenant and user
            admin_tenant = db.query(Tenant).filter(Tenant.name == "System Admin").first()
            if not admin_tenant:
                admin_tenant = Tenant(
                    name="System Admin",
                    constituency="System",
                    whatsapp_number="system_admin",
                    subscription_plan="Admin",
                    config={}
                )
                db.add(admin_tenant)
                db.flush()
            
            admin_user = User(
                tenant_id=admin_tenant.id,
                username="sysadmin",
                password_hash="admin123",  # Default password
                role="admin"
            )
            db.add(admin_user)
            db.commit()
            return True
        return False
    except Exception:
        db.rollback()
        return False
    finally:
        db.close()

# --- PDF Parsing Functions ---
def parse_polling_station_pdf(pdf_file) -> list:
    """
    Parse Election Commission polling station PDF using pdfplumber.
    NO AI, NO translation - just extract raw text and structure.
    Returns list of polling station dicts.
    """
    stations = []
    
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page_num, page in enumerate(pdf.pages):
                # Try to extract tables first
                tables = page.extract_tables()
                
                if tables:
                    for table in tables:
                        for row in table:
                            if row and len(row) >= 2:
                                # Try to identify station number and locality
                                station_data = extract_station_from_row(row)
                                if station_data:
                                    stations.append(station_data)
                else:
                    # Fall back to text extraction
                    text = page.extract_text()
                    if text:
                        text_stations = extract_stations_from_text(text)
                        stations.extend(text_stations)
    except Exception as e:
        st.error(f"PDF parsing error: {e}")
        return []
    
    # Remove duplicates based on station_number
    seen = set()
    unique_stations = []
    for s in stations:
        if s.get("station_number") and s["station_number"] not in seen:
            seen.add(s["station_number"])
            unique_stations.append(s)
    
    return unique_stations

def extract_station_from_row(row: list) -> dict:
    """Extract station data from a table row"""
    # Clean row values
    cleaned = [str(cell).strip() if cell else "" for cell in row]
    
    # Look for patterns
    station_number = ""
    locality = ""
    building_name = ""
    
    for i, cell in enumerate(cleaned):
        # Check if cell looks like a station number (digits)
        if re.match(r'^\d+$', cell) and not station_number:
            station_number = cell
        # Check if this might be a locality name
        elif len(cell) > 3 and not cell.isdigit():
            if not locality:
                locality = cell
            elif not building_name:
                building_name = cell
    
    if station_number or locality:
        return {
            "station_number": station_number,
            "locality": locality,
            "building_name": building_name
        }
    return None

def extract_stations_from_text(text: str) -> list:
    """Extract station data from plain text"""
    stations = []
    lines = text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Look for patterns like "123 - Locality Name" or "Station 123: Building"
        patterns = [
            r'(\d+)\s*[-:]\s*(.+)',  # "123 - Locality"
            r'Station\s*(\d+)\s*[-:]?\s*(.+)',  # "Station 123: Locality"
            r'(\d+)\.\s*(.+)',  # "123. Locality"
        ]
        
        for pattern in patterns:
            match = re.match(pattern, line, re.IGNORECASE)
            if match:
                stations.append({
                    "station_number": match.group(1),
                    "locality": match.group(2).strip(),
                    "building_name": ""
                })
                break
    
    return stations

# --- Geography File Functions ---
def get_parliamentary_constituencies() -> list:
    """Get list of parliamentary constituencies from saved geography data"""
    GEOGRAPHY_BASE_PATH.mkdir(parents=True, exist_ok=True)
    return [d.name for d in GEOGRAPHY_BASE_PATH.iterdir() if d.is_dir()]

def get_assembly_constituencies(parliamentary: str) -> list:
    """Get assembly constituencies for a parliamentary constituency"""
    path = GEOGRAPHY_BASE_PATH / parliamentary
    if not path.exists():
        return []
    return [f.stem for f in path.glob("*.json")]

def save_geography_data(parliamentary: str, assembly: str, data: list) -> bool:
    """Save geography JSON to disk"""
    try:
        path = GEOGRAPHY_BASE_PATH / parliamentary
        path.mkdir(parents=True, exist_ok=True)
        
        filepath = path / f"{assembly}.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"Save error: {e}")
        return False

def load_geography_data(parliamentary: str, assembly: str) -> list:
    """Load geography JSON from disk"""
    filepath = GEOGRAPHY_BASE_PATH / parliamentary / f"{assembly}.json"
    if filepath.exists():
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

# --- Metadata Functions ---
def load_metadata() -> dict:
    """Load constituency metadata from disk"""
    if METADATA_PATH.exists():
        with open(METADATA_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_metadata(data: dict) -> bool:
    """Save constituency metadata to disk"""
    try:
        METADATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(METADATA_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"Save error: {e}")
        return False

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
        .stat-card {
            background: white;
            padding: 1.5rem;
            border-radius: 8px;
            border-left: 4px solid #1e3a5f;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        }
        .success-box {
            background: #d4edda;
            border: 1px solid #c3e6cb;
            border-radius: 8px;
            padding: 1rem;
            color: #155724;
        }
        .warning-box {
            background: #fff3cd;
            border: 1px solid #ffc107;
            border-radius: 8px;
            padding: 1rem;
            color: #856404;
        }
    </style>
    """, unsafe_allow_html=True)

# --- Main Application ---
def main():
    inject_css()
    
    # Initialize database
    init_db()
    ensure_admin_exists()
    
    # --- Login Screen ---
    if not st.session_state.admin_authenticated:
        st.markdown("""
        <div style="text-align: center; margin-top: 100px;">
            <h1>⚙️ Needle Admin Dashboard</h1>
            <p style="color: #666;">Administrative Control Panel</p>
        </div>
        """, unsafe_allow_html=True)
        
        _, col, _ = st.columns([1, 1, 1])
        with col:
            with st.form("admin_login"):
                st.subheader("🔐 Admin Login")
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                
                if st.form_submit_button("Login", use_container_width=True):
                    result = verify_admin_login(username, password)
                    if result["success"]:
                        st.session_state.admin_authenticated = True
                        st.session_state.admin_user = result["username"]
                        st.rerun()
                    else:
                        st.error("❌ Invalid credentials or insufficient permissions")
            
            st.caption("💡 Default admin: sysadmin / admin123")
        return
    
    # --- Admin Dashboard ---
    st.markdown("""
    <div class="admin-header">
        <h1>⚙️ Needle Admin Dashboard</h1>
        <p>Manage MPs, Geography Data, and System Configuration</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown(f"**Logged in as:** {st.session_state.admin_user}")
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.admin_authenticated = False
            st.session_state.admin_user = None
            st.rerun()
        
        st.divider()
        st.caption("Needle Admin v1.0")
    
    # Main Tabs
    tab1, tab2, tab3 = st.tabs(["👥 MP Management", "🗺️ Geography Upload", "📋 Constituency Metadata"])
    
    # ===================
    # TAB 1: MP Management
    # ===================
    with tab1:
        st.header("👥 MP Management")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("➕ Create New MP")
            with st.form("create_mp_form"):
                mp_name = st.text_input("MP Name *", placeholder="Hon. Shri/Smt...")
                mp_username = st.text_input("Username *", placeholder="username")
                mp_password = st.text_input("Password *", type="password")
                mp_constituency = st.text_input("Parliamentary Constituency *", placeholder="e.g., Belagavi")
                mp_whatsapp = st.text_input("WhatsApp Number (optional)", placeholder="+91...")
                
                if st.form_submit_button("Create MP", use_container_width=True):
                    if mp_name and mp_username and mp_password and mp_constituency:
                        result = create_mp(mp_name, mp_username, mp_password, mp_constituency, mp_whatsapp)
                        if result["success"]:
                            st.success(f"✅ MP '{mp_name}' created successfully!")
                            st.rerun()
                        else:
                            st.error(f"❌ Error: {result.get('error', 'Unknown error')}")
                    else:
                        st.warning("⚠️ Please fill all required fields")
        
        with col2:
            st.subheader("🔑 Reset Password")
            with st.form("reset_password_form"):
                mps = get_all_mps()
                mp_usernames = [mp["username"] for mp in mps if mp["role"] != "admin"]
                
                if mp_usernames:
                    selected_user = st.selectbox("Select MP", mp_usernames)
                    new_password = st.text_input("New Password", type="password")
                    confirm_password = st.text_input("Confirm Password", type="password")
                    
                    if st.form_submit_button("Reset Password", use_container_width=True):
                        if new_password and new_password == confirm_password:
                            result = reset_mp_password(selected_user, new_password)
                            if result["success"]:
                                st.success(f"✅ Password reset for '{selected_user}'")
                            else:
                                st.error(f"❌ Error: {result.get('error', 'Unknown error')}")
                        else:
                            st.warning("⚠️ Passwords don't match or are empty")
                else:
                    st.info("No MPs available. Create one first.")
                    st.form_submit_button("Reset Password", disabled=True)
        
        st.divider()
        
        # MP List Table
        st.subheader("📋 All MPs")
        mps = get_all_mps()
        if mps:
            # Filter out admin users for display
            mp_list = [mp for mp in mps if mp["role"] != "admin"]
            if mp_list:
                df = pd.DataFrame(mp_list)
                df = df[["mp_name", "username", "parliamentary_constituency", "whatsapp_number", "created_at"]]
                df.columns = ["Name", "Username", "Constituency", "WhatsApp", "Created"]
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("No MPs found. Create one above.")
        else:
            st.info("No MPs found. Create one above.")
    
    # ===================
    # TAB 2: Geography Upload
    # ===================
    with tab2:
        st.header("🗺️ Geography Upload")
        st.caption("Upload Election Commission polling station PDFs and convert to JSON")
        
        col1, col2 = st.columns(2)
        
        with col1:
            parliamentary_const = st.text_input(
                "Parliamentary Constituency", 
                placeholder="e.g., Belagavi",
                help="Enter the Lok Sabha constituency name"
            )
        
        with col2:
            assembly_const = st.text_input(
                "Assembly Constituency",
                placeholder="e.g., Belgaum North",
                help="Enter the Vidhan Sabha constituency name"
            )
        
        # PDF Upload
        st.subheader("📄 Upload Polling Station PDF")
        uploaded_pdf = st.file_uploader(
            "Choose Election Commission PDF",
            type=["pdf"],
            help="Upload the polling station list PDF from Election Commission"
        )
        
        if uploaded_pdf and parliamentary_const and assembly_const:
            if st.button("🔍 Parse PDF", use_container_width=True):
                with st.spinner("Parsing PDF with pdfplumber..."):
                    stations = parse_polling_station_pdf(uploaded_pdf)
                    
                    if stations:
                        st.session_state['parsed_stations'] = stations
                        st.session_state['current_parliamentary'] = parliamentary_const
                        st.session_state['current_assembly'] = assembly_const
                        st.success(f"✅ Extracted {len(stations)} polling stations")
                    else:
                        st.warning("⚠️ No polling stations found. PDF may need manual editing.")
                        st.session_state['parsed_stations'] = []
        
        # Show parsed data for editing
        if 'parsed_stations' in st.session_state:
            st.divider()
            st.subheader("✏️ Edit JSON Preview")
            st.caption("Review and edit the extracted data before saving")
            
            # JSON Editor
            json_str = json.dumps(st.session_state['parsed_stations'], indent=2, ensure_ascii=False)
            edited_json = st.text_area(
                "Polling Stations JSON",
                value=json_str,
                height=400,
                help="Edit the JSON directly. Ensure valid JSON format."
            )
            
            col1, col2, col3 = st.columns([1, 1, 1])
            
            with col1:
                if st.button("✅ Validate JSON", use_container_width=True):
                    try:
                        validated = json.loads(edited_json)
                        st.success(f"✅ Valid JSON! {len(validated)} entries")
                        st.session_state['validated_json'] = validated
                    except json.JSONDecodeError as e:
                        st.error(f"❌ Invalid JSON: {e}")
            
            with col2:
                if st.button("💾 Save to Disk", use_container_width=True, type="primary"):
                    try:
                        data_to_save = json.loads(edited_json)
                        parl = st.session_state.get('current_parliamentary', parliamentary_const)
                        assm = st.session_state.get('current_assembly', assembly_const)
                        
                        if parl and assm:
                            if save_geography_data(parl, assm, data_to_save):
                                st.success(f"✅ Saved to: data/geography/{parl}/{assm}.json")
                                # Clear session state
                                del st.session_state['parsed_stations']
                            else:
                                st.error("❌ Failed to save")
                        else:
                            st.warning("⚠️ Please specify constituency names")
                    except json.JSONDecodeError as e:
                        st.error(f"❌ Invalid JSON: {e}")
            
            with col3:
                if st.button("🗑️ Clear", use_container_width=True):
                    if 'parsed_stations' in st.session_state:
                        del st.session_state['parsed_stations']
                    st.rerun()
        
        # Show existing geography files
        st.divider()
        st.subheader("📁 Existing Geography Files")
        
        parliamentary_list = get_parliamentary_constituencies()
        if parliamentary_list:
            for parl in parliamentary_list:
                with st.expander(f"🏛️ {parl}"):
                    assemblies = get_assembly_constituencies(parl)
                    if assemblies:
                        for assm in assemblies:
                            data = load_geography_data(parl, assm)
                            st.markdown(f"**{assm}** - {len(data)} polling stations")
                    else:
                        st.caption("No assembly data yet")
        else:
            st.info("No geography data uploaded yet.")
    
    # ===================
    # TAB 3: Constituency Metadata
    # ===================
    with tab3:
        st.header("📋 Constituency Metadata")
        st.caption("Store free-text JSON metadata for constituencies")
        
        # Load existing metadata
        metadata = load_metadata()
        
        # Constituency selector
        parliamentary_list = get_parliamentary_constituencies()
        if parliamentary_list:
            selected_parl = st.selectbox(
                "Select Parliamentary Constituency",
                options=[""] + parliamentary_list,
                help="Select a constituency to view/edit metadata"
            )
        else:
            selected_parl = st.text_input(
                "Parliamentary Constituency",
                placeholder="Enter constituency name",
                help="No constituencies found. Enter name to create metadata."
            )
        
        if selected_parl:
            st.subheader(f"Metadata for: {selected_parl}")
            
            # Get existing metadata for this constituency
            existing_data = metadata.get(selected_parl, {})
            
            # JSON Editor
            default_template = {
                "mp_name": "",
                "party": "",
                "assembly_constituencies": [],
                "district": "",
                "state": "",
                "population": 0,
                "key_issues": [],
                "custom_fields": {}
            }
            
            if not existing_data:
                existing_data = default_template
            
            json_str = json.dumps(existing_data, indent=2, ensure_ascii=False)
            edited_json = st.text_area(
                "Metadata JSON",
                value=json_str,
                height=400,
                help="Edit constituency metadata as JSON"
            )
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("✅ Validate", use_container_width=True):
                    try:
                        json.loads(edited_json)
                        st.success("✅ Valid JSON!")
                    except json.JSONDecodeError as e:
                        st.error(f"❌ Invalid JSON: {e}")
            
            with col2:
                if st.button("💾 Save Metadata", use_container_width=True, type="primary"):
                    try:
                        new_data = json.loads(edited_json)
                        metadata[selected_parl] = new_data
                        if save_metadata(metadata):
                            st.success(f"✅ Metadata saved for {selected_parl}")
                        else:
                            st.error("❌ Failed to save")
                    except json.JSONDecodeError as e:
                        st.error(f"❌ Invalid JSON: {e}")
        
        # Show all metadata
        st.divider()
        st.subheader("📁 All Constituency Metadata")
        if metadata:
            for const, data in metadata.items():
                with st.expander(f"🏛️ {const}"):
                    st.json(data)
        else:
            st.info("No metadata saved yet.")

if __name__ == "__main__":
    main()
