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
try:
    from db import SessionLocal, Tenant, User, TenantProfile, Case, init_db
except ImportError:
    st.error("Could not import 'db.py'. Please ensure 'db.py' exists in the project root.")
    sys.exit(1)

# --- Constants ---
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000") 
GEOGRAPHY_BASE_PATH = Path(__file__).parent / "data" / "geography"
METADATA_PATH = Path(__file__).parent / "data" / "constituency_metadata.json"
OVERRIDES_PATH = Path("tenant_overrides.json")

from modules.constituencies import ALL_CONSTITUENCIES

# --- Page Config ---
st.set_page_config(
    page_title="Needle Command Center",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ─────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────
if 'admin_authenticated' not in st.session_state:
    st.session_state.admin_authenticated = False
if 'admin_user' not in st.session_state:
    st.session_state.admin_user = None
if 'show_settings' not in st.session_state:
    st.session_state.show_settings = False

# ─────────────────────────────────────────
# PREMIUM CSS
# ─────────────────────────────────────────
def inject_premium_css():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
        
        /* Global — White + Emerald Green (Lok Sabha) */
        html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
        .stApp { background: #f8faf9; }
        
        /* Hide Streamlit defaults */
        #MainMenu, footer, header { visibility: hidden; }
        .block-container { padding-top: 1rem; }
        
        /* Dashboard Header */
        .dash-header {
            background: linear-gradient(135deg, #006a4d 0%, #00875f 50%, #006a4d 100%);
            border-radius: 16px;
            padding: 1.8rem 2rem;
            margin-bottom: 1.5rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 4px 20px rgba(0, 106, 77, 0.15);
        }
        .dash-header h1 {
            color: #ffffff;
            font-size: 1.6rem;
            font-weight: 700;
            margin: 0;
            letter-spacing: -0.5px;
        }
        .dash-header .subtitle {
            color: rgba(255,255,255,0.7);
            font-size: 0.85rem;
            margin-top: 4px;
        }
        .dash-header .badge {
            background: rgba(255,255,255,0.2);
            color: #ffffff;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
            letter-spacing: 0.5px;
        }
        
        /* Stat Cards */
        .stat-row { display: flex; gap: 16px; margin-bottom: 1.5rem; }
        .stat-card {
            flex: 1;
            background: #ffffff;
            border: 1px solid #e8efe9;
            border-radius: 14px;
            padding: 1.2rem 1.4rem;
            transition: all 0.3s ease;
            box-shadow: 0 1px 4px rgba(0,0,0,0.04);
        }
        .stat-card:hover {
            border-color: #006a4d;
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(0, 106, 77, 0.08);
        }
        .stat-card .stat-icon {
            font-size: 1.4rem;
            margin-bottom: 6px;
        }
        .stat-card .stat-value {
            font-size: 2rem;
            font-weight: 800;
            color: #1a2e28;
            line-height: 1;
        }
        .stat-card .stat-label {
            color: #6b7f76;
            font-size: 0.78rem;
            font-weight: 500;
            margin-top: 4px;
            text-transform: uppercase;
            letter-spacing: 0.8px;
        }
        .stat-accent-indigo .stat-value { color: #006a4d; }
        .stat-accent-green .stat-value { color: #059669; }
        .stat-accent-amber .stat-value { color: #d97706; }
        .stat-accent-rose .stat-value { color: #8d153a; }
        .stat-accent-cyan .stat-value { color: #0891b2; }
        
        /* Glass Panels */
        .glass-panel {
            background: #ffffff;
            border: 1px solid #e2ebe5;
            border-radius: 14px;
            padding: 1.5rem;
            margin-bottom: 1rem;
            box-shadow: 0 1px 4px rgba(0,0,0,0.03);
        }
        .glass-panel h3 {
            color: #1a2e28;
            font-size: 1rem;
            font-weight: 600;
            margin: 0 0 1rem 0;
        }
        
        /* MP Cards */
        .mp-card {
            background: #ffffff;
            border: 1px solid #e2ebe5;
            border-radius: 12px;
            padding: 1rem 1.2rem;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 14px;
            transition: all 0.2s ease;
            box-shadow: 0 1px 3px rgba(0,0,0,0.03);
        }
        .mp-card:hover {
            border-color: #006a4d;
            box-shadow: 0 4px 12px rgba(0, 106, 77, 0.08);
        }
        .mp-avatar {
            width: 44px;
            height: 44px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 1rem;
            color: white;
            flex-shrink: 0;
        }
        .mp-avatar-ls { background: linear-gradient(135deg, #006a4d, #00875f); }
        .mp-avatar-rs { background: linear-gradient(135deg, #8d153a, #b91c50); }
        .mp-info { flex: 1; }
        .mp-info .mp-name { color: #1a2e28; font-weight: 600; font-size: 0.9rem; }
        .mp-info .mp-meta { color: #6b7f76; font-size: 0.75rem; margin-top: 2px; }
        .mp-tag {
            padding: 3px 10px;
            border-radius: 6px;
            font-size: 0.68rem;
            font-weight: 600;
            letter-spacing: 0.3px;
        }
        .tag-ls { background: rgba(0, 106, 77, 0.08); color: #006a4d; }
        .tag-rs { background: rgba(141, 21, 58, 0.08); color: #8d153a; }
        
        /* Section Headers */
        .section-title {
            color: #006a4d;
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1.2px;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 2px solid #e2ebe5;
        }
        
        /* Profile Completeness */
        .completeness-bar {
            background: #e8efe9;
            border-radius: 6px;
            height: 6px;
            margin-top: 8px;
            overflow: hidden;
        }
        .completeness-fill {
            height: 100%;
            border-radius: 6px;
            transition: width 0.5s ease;
        }
        .fill-good { background: linear-gradient(90deg, #006a4d, #059669); }
        .fill-mid { background: linear-gradient(90deg, #d97706, #f59e0b); }
        .fill-low { background: linear-gradient(90deg, #dc2626, #ef4444); }
        
        /* Form Styling */
        .stTextInput > label, .stTextArea > label, .stSelectbox > label {
            color: #4a635a !important;
            font-size: 0.78rem !important;
            font-weight: 500 !important;
        }
        .stTextInput input, .stTextArea textarea {
            background: #f8faf9 !important;
            border-color: #d4e0d9 !important;
            color: #1a2e28 !important;
            border-radius: 10px !important;
        }
        .stTextInput input:focus, .stTextArea textarea:focus {
            border-color: #006a4d !important;
            box-shadow: 0 0 0 2px rgba(0, 106, 77, 0.12) !important;
        }
        
        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {
            background: #ffffff;
            border-radius: 12px;
            padding: 6px 8px;
            gap: 8px;
            border: 1px solid #e2ebe5;
        }
        .stTabs [data-baseweb="tab"] {
            border-radius: 8px;
            color: #6b7f76;
            font-weight: 500;
            font-size: 0.82rem;
            padding: 10px 20px;
        }
        .stTabs [aria-selected="true"] {
            background: rgba(0, 106, 77, 0.08) !important;
            color: #006a4d !important;
        }
        
        /* Buttons */
        .stButton > button {
            border-radius: 10px !important;
            font-weight: 600 !important;
            font-size: 0.82rem !important;
            transition: all 0.2s ease !important;
        }
        .stButton > button:hover {
            transform: translateY(-1px) !important;
        }
        .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #006a4d, #00875f) !important;
            border: none !important;
            color: white !important;
        }
        
        /* Login */
        .login-container {
            max-width: 400px;
            margin: 80px auto;
            background: #ffffff;
            border: 1px solid #e2ebe5;
            border-radius: 20px;
            padding: 2.5rem;
            box-shadow: 0 4px 24px rgba(0,0,0,0.06);
        }
        .login-title {
            color: #006a4d;
            font-size: 1.4rem;
            font-weight: 700;
            text-align: center;
            margin-bottom: 0.3rem;
        }
        .login-subtitle {
            color: #6b7f76;
            font-size: 0.82rem;
            text-align: center;
            margin-bottom: 1.5rem;
        }
        
        /* Data Tables */
        .stDataFrame { border-radius: 12px; overflow: hidden; }
        
        /* Dividers */
        hr { border-color: #e2ebe5 !important; }
        
        /* Expanders */
        .streamlit-expanderHeader { color: #1a2e28 !important; font-weight: 600 !important; }
    </style>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, stored_hash: str) -> bool:
    try:
        if stored_hash.startswith('$2b$') or stored_hash.startswith('$2a$'):
            return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))
    except Exception:
        pass
    return stored_hash == password

def verify_admin_login(username: str, password: str) -> dict:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if user and user.role in ("admin", "super_admin", "sysadmin"):
            if verify_password(password, user.password_hash):
                if not (user.password_hash.startswith('$2b$') or user.password_hash.startswith('$2a$')):
                    user.password_hash = hash_password(password)
                    db.commit()
                return {"success": True, "username": user.username, "tenant_id": user.tenant_id}
        return {"success": False}
    finally:
        db.close()

def get_all_mps() -> list:
    from sqlalchemy.orm import joinedload
    db = SessionLocal()
    try:
        tenants = db.query(Tenant).options(joinedload(Tenant.users)).all()
        result = []
        for t in tenants:
            for u in t.users:
                result.append({
                    "tenant_id": t.id,
                    "user_id": u.id,
                    "mp_name": t.name,
                    "display_name": getattr(u, 'display_name', None) or t.name,
                    "username": u.username,
                    "role": u.role,
                    "house": getattr(u, 'house', None) or "Lok Sabha",
                    "parliamentary_constituency": getattr(u, 'constituency', None) or t.constituency or "India",
                    "whatsapp_number": t.whatsapp_number,
                    "created_at": t.created_at.strftime("%Y-%m-%d") if t.created_at else "N/A"
                })
        return result
    finally:
        db.close()

def get_system_stats() -> dict:
    """Get aggregate system statistics."""
    db = SessionLocal()
    try:
        from sqlalchemy import func
        total_mps = db.query(User).filter(User.role == "mp").count()
        ls_count = db.query(User).filter(User.role == "mp", User.house == "Lok Sabha").count()
        rs_count = db.query(User).filter(User.role == "mp", User.house == "Rajya Sabha").count()
        total_profiles = db.query(TenantProfile).count()
        try:
            total_cases = db.query(Case).count()
        except Exception:
            total_cases = 0
        return {
            "total_mps": total_mps,
            "lok_sabha": ls_count,
            "rajya_sabha": rs_count,
            "total_profiles": total_profiles,
            "total_cases": total_cases,
        }
    finally:
        db.close()

def get_mp_profile(tenant_id: int) -> dict:
    """Get TenantProfile for a given tenant_id."""
    db = SessionLocal()
    try:
        profile = db.query(TenantProfile).filter(TenantProfile.tenant_id == tenant_id).first()
        if profile:
            extra = profile.profile_data or {}
            return {
                "exists": True,
                "mp_name": profile.mp_name or "",
                "constituency": profile.constituency or "",
                "state": profile.state or "",
                "house": profile.house or "Lok Sabha",
                "party": profile.party or "Independent",
                "key_facts": extra.get("key_facts", []),
                "languages": extra.get("languages", ["English", "Hindi"]),
                "alt_names": extra.get("alt_names", []),
                "sovereignty_rules": extra.get("sovereignty_rules", ""),
                "vocabulary_guide": extra.get("vocabulary_guide", {}),
            }
        return {"exists": False}
    finally:
        db.close()

def save_mp_profile(tenant_id: int, data: dict) -> dict:
    """Create or update TenantProfile for a tenant."""
    db = SessionLocal()
    try:
        profile = db.query(TenantProfile).filter(TenantProfile.tenant_id == tenant_id).first()
        
        profile_data = {
            "key_facts": data.get("key_facts", []),
            "languages": data.get("languages", ["English", "Hindi"]),
            "alt_names": data.get("alt_names", []),
            "sovereignty_rules": data.get("sovereignty_rules", ""),
            "vocabulary_guide": data.get("vocabulary_guide", {}),
        }
        
        if profile:
            profile.mp_name = data.get("mp_name", profile.mp_name)
            profile.constituency = data.get("constituency", profile.constituency)
            profile.state = data.get("state", profile.state)
            profile.house = data.get("house", profile.house)
            profile.party = data.get("party", profile.party)
            profile.profile_data = profile_data
        else:
            profile = TenantProfile(
                tenant_id=tenant_id,
                mp_name=data.get("mp_name", ""),
                constituency=data.get("constituency", ""),
                state=data.get("state", ""),
                house=data.get("house", "Lok Sabha"),
                party=data.get("party", "Independent"),
                profile_data=profile_data,
            )
            db.add(profile)
        
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()

def calculate_profile_completeness(profile: dict) -> int:
    """Calculate profile completeness percentage."""
    if not profile.get("exists"):
        return 0
    fields = ["mp_name", "constituency", "state", "party"]
    score = sum(1 for f in fields if profile.get(f))
    if profile.get("key_facts"):
        score += 1
    if profile.get("languages") and len(profile["languages"]) > 1:
        score += 1
    if profile.get("alt_names"):
        score += 1
    if profile.get("sovereignty_rules"):
        score += 1
    return int((score / 8) * 100)

def create_mp(name, username, password, constituency, whatsapp_number="", house="Lok Sabha", display_name="", state="", party="Independent", key_facts=None, languages=None, alt_names=None) -> dict:
    db = SessionLocal()
    try:
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            return {"success": False, "error": "Username already exists"}
        
        new_tenant = Tenant(
            name=name, constituency=constituency,
            whatsapp_number=whatsapp_number or f"temp_{datetime.now().timestamp()}",
            subscription_plan="Pro",
            config={"language": "English", "type": house.upper().replace(" ", "_"), "map_enabled": True}
        )
        db.add(new_tenant)
        db.flush()
        
        new_user = User(
            tenant_id=new_tenant.id, username=username,
            password_hash=hash_password(password), role="mp",
            constituency=constituency, house=house,
            display_name=display_name or name
        )
        db.add(new_user)
        
        profile_data = {
            "key_facts": key_facts or [], "languages": languages or ["English", "Hindi"],
            "vocabulary_guide": {}, "sovereignty_rules": "", "alt_names": alt_names or [],
        }
        new_profile = TenantProfile(
            tenant_id=new_tenant.id, mp_name=display_name or name,
            constituency=constituency, state=state, house=house,
            party=party, profile_data=profile_data,
        )
        db.add(new_profile)
        db.commit()
        return {"success": True, "tenant_id": new_tenant.id, "user_id": new_user.id}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()

def delete_mp(tenant_id: int) -> dict:
    """Delete an MP (User + Tenant + TenantProfile)."""
    db = SessionLocal()
    try:
        db.query(TenantProfile).filter(TenantProfile.tenant_id == tenant_id).delete()
        db.query(User).filter(User.tenant_id == tenant_id).delete()
        db.query(Tenant).filter(Tenant.id == tenant_id).delete()
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()

def update_mp_constituency(username, new_constituency):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return {"success": False, "error": "User not found"}
        user.constituency = new_constituency
        if user.tenant_id:
            tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
            if tenant: tenant.constituency = new_constituency
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()

def reset_mp_password(username, new_password):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user: return {"success": False, "error": "User not found"}
        user.password_hash = hash_password(new_password)
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()

def ensure_admin_exists():
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
            db.add(User(tenant_id=admin_tenant.id, username="sysadmin", password_hash=hash_password("admin123"), role="admin"))
            db.commit()
    except Exception: db.rollback()
    finally: db.close()

def get_all_editors() -> list:
    """Get all editor users."""
    db = SessionLocal()
    try:
        editors = db.query(User).filter(User.role == "editor").all()
        return [{
            "id": e.id,
            "username": e.username,
            "tenant_id": e.tenant_id,
            "display_name": getattr(e, 'display_name', None) or e.username,
            "house": getattr(e, 'house', None) or "",
        } for e in editors]
    finally:
        db.close()

def create_editor(username: str, password: str, display_name: str = "", permissions: list = None) -> dict:
    """Create an editor user with restricted permissions."""
    db = SessionLocal()
    try:
        if db.query(User).filter(User.username == username).first():
            return {"success": False, "error": "Username already exists"}
        # Editors are attached to the System Admin tenant
        admin_tenant = db.query(Tenant).filter(Tenant.name == "System Admin").first()
        if not admin_tenant:
            return {"success": False, "error": "System Admin tenant not found. Login first."}
        new_editor = User(
            tenant_id=admin_tenant.id,
            username=username,
            password_hash=hash_password(password),
            role="editor",
            display_name=display_name or username,
        )
        db.add(new_editor)
        db.commit()
        return {"success": True, "user_id": new_editor.id}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()

def delete_editor(user_id: int) -> dict:
    """Delete an editor user."""
    db = SessionLocal()
    try:
        db.query(User).filter(User.id == user_id, User.role == "editor").delete()
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


# ─────────────────────────────────────────
# GEOGRAPHY & OVERRIDES HELPERS
# ─────────────────────────────────────────

def load_overrides():
    if OVERRIDES_PATH.exists():
        with open(OVERRIDES_PATH, 'r', encoding='utf-8') as f: return json.load(f)
    return {}

def save_overrides(data):
    try:
        with open(OVERRIDES_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except: return False

def parse_polling_station_pdf(pdf_file):
    """Parse Election Commission polling station PDF — handles diverse formats."""
    stations = []
    debug_info = {"pages": 0, "tables_found": 0, "text_pages": 0, "raw_rows": 0}
    
    try:
        with pdfplumber.open(pdf_file) as pdf:
            debug_info["pages"] = len(pdf.pages)
            
            for page_num, page in enumerate(pdf.pages, 1):
                # Try table extraction first (with relaxed settings)
                table_settings = {
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                    "snap_tolerance": 5,
                    "join_tolerance": 5,
                }
                tables = page.extract_tables(table_settings)
                
                # If lines-based extraction fails, try text-based
                if not tables:
                    table_settings_text = {
                        "vertical_strategy": "text",
                        "horizontal_strategy": "text",
                    }
                    tables = page.extract_tables(table_settings_text)
                
                if tables:
                    debug_info["tables_found"] += len(tables)
                    for table in tables:
                        for row in table:
                            if not row: continue
                            debug_info["raw_rows"] += 1
                            s = extract_station_from_row(row)
                            if s: stations.append(s)
                else:
                    # Fallback: extract raw text
                    text = page.extract_text()
                    if text:
                        debug_info["text_pages"] += 1
                        stations.extend(extract_stations_from_text(text))
    
    except Exception as e:
        st.error(f"PDF error: {e}")
        import traceback
        st.code(traceback.format_exc())
    
    # Show debug info
    with st.expander("Parse Debug Info", expanded=False):
        st.json(debug_info)
        st.write(f"Raw stations extracted: {len(stations)}")
    
    # Dedup — keep all entries, generate station numbers if missing
    result = []
    seen = set()
    auto_num = 1
    for s in stations:
        # Generate station number if missing
        if not s.get("station_number"):
            s["station_number"] = str(auto_num)
            auto_num += 1
        
        key = f"{s['station_number']}_{s.get('locality', '')}"
        if key not in seen:
            seen.add(key)
            result.append(s)
    
    return result

def extract_station_from_row(row):
    """Extract station data from a table row — handles diverse ECI PDF formats."""
    if not row: return None
    
    # Clean all cells
    cleaned = []
    for cell in row:
        c = str(cell).strip() if cell else ""
        # Handle multi-line cells (common in ECI PDFs)
        c = c.replace("\n", " ").strip()
        cleaned.append(c)
    
    # Skip header/empty rows
    skip_words = {"station", "number", "part", "polling", "booth", "name", "address", "building",
                  "sl.no", "sl no", "serial", "location", "constituency", "total", "page", "sr.no"}
    row_text = " ".join(cleaned).lower()
    if any(w in row_text for w in skip_words) and not any(c.isdigit() and len(c) <= 4 for c in cleaned[:3]):
        return None
    
    num, loc, bldg = "", "", ""
    
    for cell in cleaned:
        if not cell: continue
        
        # Station number: 1-4 digits, possibly with leading zeros or dots
        if not num and re.match(r'^\d{1,4}\.?$', cell.strip('.')):
            num = cell.strip('.')
        # Text cell — assign to locality then building
        elif len(cell) > 2 and not cell.replace('.', '').replace(',', '').isdigit():
            if not loc:
                loc = cell
            elif not bldg:
                bldg = cell
    
    # Accept if we got at least a locality (station number may be missing in some formats)
    if loc:
        return {"station_number": num, "locality": loc, "building_name": bldg}
    return None

def extract_stations_from_text(text):
    """Extract station data from raw text — handles multiple ECI formats."""
    stations = []
    lines = text.split('\n')
    
    # Multiple patterns for ECI PDF formats
    patterns = [
        # "1 - Location Name"  or  "1: Location Name"
        re.compile(r'(\d{1,4})\s*[-:\.]\s*(.+)'),
        # "Station 1 - Location" or "Station No. 1 Location"
        re.compile(r'(?:Station|Booth|Part)\s*(?:No\.?\s*)?(\d{1,4})\s*[-:\.]\s*(.+)', re.IGNORECASE),
        # "1. Location Name, Building"
        re.compile(r'^(\d{1,4})\.\s+(.+)'),
        # "001 Location Name" (number then space then text)
        re.compile(r'^(\d{1,4})\s{2,}(.+)'),
    ]
    
    for line in lines:
        line = line.strip()
        if not line or len(line) < 5: continue
        
        # Skip obvious headers
        if any(h in line.lower() for h in ["station name", "part number", "page ", "total ", "polling station list"]):
            continue
        
        for pat in patterns:
            match = pat.match(line)
            if match:
                num = match.group(1)
                rest = match.group(2).strip()
                
                # Split on comma for locality/building
                parts = [p.strip() for p in rest.split(",", 1)]
                loc = parts[0] if parts else rest
                bldg = parts[1] if len(parts) > 1 else ""
                
                if len(loc) > 2:
                    stations.append({
                        "station_number": num,
                        "locality": loc,
                        "building_name": bldg
                    })
                break
    
    return stations

def get_parliamentary_constituencies():
    GEOGRAPHY_BASE_PATH.mkdir(parents=True, exist_ok=True)
    return [d.name for d in GEOGRAPHY_BASE_PATH.iterdir() if d.is_dir()]

def get_assembly_constituencies(parliamentary):
    path = GEOGRAPHY_BASE_PATH / parliamentary
    if not path.exists(): return []
    return [f.stem for f in path.glob("*.json")]

def save_geography_data(parliamentary, assembly, data):
    try:
        path = GEOGRAPHY_BASE_PATH / parliamentary
        path.mkdir(parents=True, exist_ok=True)
        with open(path / f"{assembly}.json", 'w', encoding='utf-8') as f: json.dump(data, f, indent=2, ensure_ascii=False)
        # Auto-generate overrides for all tenants after upload
        try:
            from modules.geography_resolver import auto_generate_overrides
            auto_generate_overrides()
        except Exception as e:
            print(f"Override auto-gen warning: {e}")
        return True
    except: return False

def load_geography_data(parliamentary, assembly):
    filepath = GEOGRAPHY_BASE_PATH / parliamentary / f"{assembly}.json"
    if filepath.exists():
        with open(filepath, 'r', encoding='utf-8') as f: return json.load(f)
    return []

def load_metadata():
    if METADATA_PATH.exists():
        with open(METADATA_PATH, 'r', encoding='utf-8') as f: return json.load(f)
    return {}

def save_metadata(data):
    try:
        METADATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(METADATA_PATH, 'w', encoding='utf-8') as f: json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except: return False


# ─────────────────────────────────────────
# RENDER: STAT CARDS
# ─────────────────────────────────────────
def render_stat_cards(stats):
    st.markdown(f"""
    <div class="stat-row">
        <div class="stat-card stat-accent-indigo">
            <div class="stat-icon">👥</div>
            <div class="stat-value">{stats['total_mps']}</div>
            <div class="stat-label">Total MPs</div>
        </div>
        <div class="stat-card stat-accent-green">
            <div class="stat-icon">🏛️</div>
            <div class="stat-value">{stats['lok_sabha']}</div>
            <div class="stat-label">Lok Sabha</div>
        </div>
        <div class="stat-card stat-accent-rose">
            <div class="stat-icon">🏛️</div>
            <div class="stat-value">{stats['rajya_sabha']}</div>
            <div class="stat-label">Rajya Sabha</div>
        </div>
        <div class="stat-card stat-accent-amber">
            <div class="stat-icon">📋</div>
            <div class="stat-value">{stats['total_profiles']}</div>
            <div class="stat-label">Profiles</div>
        </div>
        <div class="stat-card stat-accent-cyan">
            <div class="stat-icon">📩</div>
            <div class="stat-value">{stats['total_cases']}</div>
            <div class="stat-label">Total Cases</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────
# RENDER: MP CARD
# ─────────────────────────────────────────
def render_mp_card(mp, profile=None):
    initials = "".join([w[0] for w in mp["display_name"].split()[:2]]).upper()
    house = mp.get("house", "Lok Sabha")
    avatar_cls = "mp-avatar-ls" if house == "Lok Sabha" else "mp-avatar-rs"
    tag_cls = "tag-ls" if house == "Lok Sabha" else "tag-rs"
    tag_label = "LS" if house == "Lok Sabha" else "RS"
    
    completeness = calculate_profile_completeness(profile) if profile else 0
    fill_cls = "fill-good" if completeness >= 70 else "fill-mid" if completeness >= 40 else "fill-low"
    
    st.markdown(f"""
    <div class="mp-card">
        <div class="mp-avatar {avatar_cls}">{initials}</div>
        <div class="mp-info">
            <div class="mp-name">{mp['display_name']}</div>
            <div class="mp-meta">@{mp['username']} · {mp['parliamentary_constituency']}</div>
            <div class="completeness-bar"><div class="completeness-fill {fill_cls}" style="width: {completeness}%"></div></div>
        </div>
        <span class="mp-tag {tag_cls}">{tag_label}</span>
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────
# MAIN APPLICATION
# ─────────────────────────────────────────
def main():
    inject_premium_css()
    init_db()
    ensure_admin_exists()

    # ── LOGIN ──
    if not st.session_state.admin_authenticated:
        st.markdown("""
        <div class="login-container">
            <div class="login-title">Needle Command Center</div>
            <div class="login-subtitle">Administrative Control Panel</div>
        </div>
        """, unsafe_allow_html=True)
        _, col, _ = st.columns([1.2, 1, 1.2])
        with col:
            with st.form("admin_login"):
                u = st.text_input("Username", placeholder="admin username")
                p = st.text_input("Password", type="password", placeholder="password")
                if st.form_submit_button("Sign In", use_container_width=True, type="primary"):
                    res = verify_admin_login(u, p)
                    if res["success"]:
                        st.session_state.admin_authenticated = True
                        st.session_state.admin_user = res["username"]
                        st.rerun()
                    else:
                        st.error("Invalid credentials")
        return

    # ── HEADER ──
    hdr_left, hdr_right = st.columns([6, 1])
    with hdr_left:
        st.markdown("""
        <div class="dash-header">
            <div>
                <h1>Needle Command Center</h1>
                <div class="subtitle">Multi-tenant MP management, geography, and system configuration</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    with hdr_right:
        st.write("")
        if st.button("⚙️ Settings", use_container_width=True):
            st.session_state.show_settings = not st.session_state.show_settings
            st.rerun()
        if st.button("Logout", use_container_width=True):
            st.session_state.admin_authenticated = False
            st.rerun()

    # ══════════════════════════════════════
    # SETTINGS PAGE (overlays main content)
    # ══════════════════════════════════════
    if st.session_state.show_settings:
        st.markdown('<div class="section-title">Settings</div>', unsafe_allow_html=True)
        if st.button("← Back to Dashboard"):
            st.session_state.show_settings = False
            st.rerun()

        settings_col1, settings_col2 = st.columns([1, 1])

        # --- Admin Password Reset ---
        with settings_col1:
            st.markdown('<div class="glass-panel"><h3>Reset Admin Password</h3></div>', unsafe_allow_html=True)
            with st.form("reset_admin_pw"):
                adm_current = st.text_input("Current Password", type="password")
                adm_new = st.text_input("New Password", type="password")
                adm_confirm = st.text_input("Confirm New Password", type="password")
                if st.form_submit_button("Update Password", use_container_width=True, type="primary"):
                    if not adm_current or not adm_new:
                        st.warning("Fill all fields")
                    elif adm_new != adm_confirm:
                        st.error("Passwords don't match")
                    else:
                        # Verify current password
                        v = verify_admin_login(st.session_state.admin_user, adm_current)
                        if v["success"]:
                            res = reset_mp_password(st.session_state.admin_user, adm_new)
                            if res["success"]:
                                st.success("Admin password updated")
                            else:
                                st.error(res.get("error"))
                        else:
                            st.error("Current password is incorrect")

        # --- Editor Management ---
        with settings_col2:
            st.markdown('<div class="glass-panel"><h3>Editors (Restricted Access)</h3></div>', unsafe_allow_html=True)
            st.caption("Editors can view MP data and geography but cannot create/delete MPs or change settings.")

            # Create Editor
            with st.form("create_editor_form"):
                ed_username = st.text_input("Editor Username *", placeholder="editor_name")
                ed_display = st.text_input("Display Name", placeholder="Editor display name")
                ed_password = st.text_input("Password *", type="password")
                if st.form_submit_button("Create Editor", use_container_width=True, type="primary"):
                    if ed_username and ed_password:
                        res = create_editor(ed_username, ed_password, display_name=ed_display)
                        if res["success"]:
                            st.success(f"Editor '{ed_username}' created")
                            st.rerun()
                        else:
                            st.error(res.get("error"))
                    else:
                        st.warning("Username and password required")

            # List Editors
            editors = get_all_editors()
            if editors:
                st.markdown("---")
                st.markdown(f"**{len(editors)} editor(s)**")
                for ed in editors:
                    ec1, ec2 = st.columns([4, 1])
                    with ec1:
                        st.markdown(f"**{ed['display_name']}** &nbsp; `@{ed['username']}`", unsafe_allow_html=True)
                    with ec2:
                        if st.button("Remove", key=f"del_ed_{ed['id']}"):
                            delete_editor(ed['id'])
                            st.rerun()
            else:
                st.info("No editors created yet.")

        return  # Don't show main tabs when in settings

    # ── STATS ──
    stats = get_system_stats()
    render_stat_cards(stats)

    # ── TABS ──
    tab_mp, tab_profile, tab_geo, tab_rules, tab_intel = st.tabs([
        "MP Management", "Profile Editor", "Geography Upload", "Geography Rules", "Case Intelligence"
    ])

    # ══════════════════════════════════════
    # TAB 1: MP MANAGEMENT
    # ══════════════════════════════════════
    with tab_mp:
        # Existing MPs — main view
        st.markdown('<div class="section-title">Members of Parliament</div>', unsafe_allow_html=True)
        mps = get_all_mps()
        mp_list = [mp for mp in mps if mp["role"] != "admin"]

        if mp_list:
            search = st.text_input("Search MPs", placeholder="Search by name, constituency, or username...", label_visibility="collapsed")
            if search:
                s = search.lower()
                mp_list = [m for m in mp_list if s in m["display_name"].lower() or s in m["username"].lower() or s in m["parliamentary_constituency"].lower()]

            # Render as card grid (3 columns)
            cols = st.columns(3)
            for i, mp in enumerate(mp_list):
                with cols[i % 3]:
                    profile = get_mp_profile(mp["tenant_id"])
                    render_mp_card(mp, profile)
        else:
            st.info("No MPs registered yet. Use the form below to add one.")

        # Add New MP — collapsible
        st.markdown("---")
        with st.expander("➕ Add New MP", expanded=False):
            c_form_left, c_form_right = st.columns([1, 1])
            with c_form_left:
                with st.form("create_mp_form"):
                    mp_name = st.text_input("MP Full Name *", placeholder="Hon. Shri/Smt...")
                    mp_display = st.text_input("Display Name", placeholder="Dashboard display name")
                    mp_house = st.selectbox("House *", ["Lok Sabha", "Rajya Sabha"])
                    c1, c2 = st.columns(2)
                    with c1: mp_username = st.text_input("Username *", placeholder="username")
                    with c2: mp_password = st.text_input("Password *", type="password")

                    if mp_house == "Lok Sabha":
                        mp_constituency = st.selectbox("Parliamentary Constituency *", ALL_CONSTITUENCIES)
                    else:
                        mp_constituency = st.text_input("State/Nominated", placeholder="e.g. Maharashtra")

                    c3, c4 = st.columns(2)
                    with c3: mp_state = st.text_input("State *", placeholder="e.g. Karnataka")
                    with c4: mp_party = st.text_input("Party", placeholder="e.g. BJP, INC")
                    mp_whatsapp = st.text_input("WhatsApp", placeholder="+91...")

                    st.markdown("---")
                    st.caption("PROFILE DATA")
                    mp_languages = st.text_input("Languages", placeholder="English, Hindi, Kannada", value="English, Hindi")
                    mp_key_facts = st.text_area("Key Facts (one per line)", placeholder="Major industrial hub\nBorder district", height=80)
                    mp_alt_names = st.text_input("Alt Constituency Names", placeholder="Belagavi, Belgaum")

                    if st.form_submit_button("Create MP", use_container_width=True, type="primary"):
                        if mp_name and mp_username and mp_password:
                            langs = [l.strip() for l in mp_languages.split(",") if l.strip()] if mp_languages else ["English", "Hindi"]
                            facts = [f.strip() for f in mp_key_facts.strip().split("\n") if f.strip()] if mp_key_facts else []
                            alts = [a.strip() for a in mp_alt_names.split(",") if a.strip()] if mp_alt_names else []

                            result = create_mp(
                                mp_name, mp_username, mp_password,
                                mp_constituency or "India", mp_whatsapp,
                                house=mp_house, display_name=mp_display or mp_name,
                                state=mp_state, party=mp_party or "Independent",
                                key_facts=facts, languages=langs, alt_names=alts,
                            )
                            if result["success"]:
                                st.success(f"Created {mp_name}")
                                st.rerun()
                            else:
                                st.error(result.get("error"))
                        else:
                            st.warning("Fill all required fields")

    # ══════════════════════════════════════
    # TAB 2: PROFILE EDITOR
    # ══════════════════════════════════════
    with tab_profile:
        mps = get_all_mps()
        mp_list = [mp for mp in mps if mp["role"] != "admin"]

        if not mp_list:
            st.info("No MPs registered. Create one first.")
        else:
            mp_options = {f"{m['display_name']} (@{m['username']})": m for m in mp_list}
            selected_label = st.selectbox("Select MP to Edit", list(mp_options.keys()))
            selected_mp = mp_options[selected_label]
            tid = selected_mp["tenant_id"]

            profile = get_mp_profile(tid)
            completeness = calculate_profile_completeness(profile)
            fill_cls = "fill-good" if completeness >= 70 else "fill-mid" if completeness >= 40 else "fill-low"

            # Profile completeness header
            st.markdown(f"""
            <div class="glass-panel">
                <h3>Profile: {selected_mp['display_name']}</h3>
                <div style="display: flex; align-items: center; gap: 12px;">
                    <div style="flex: 1;">
                        <div class="completeness-bar" style="height: 8px;">
                            <div class="completeness-fill {fill_cls}" style="width: {completeness}%"></div>
                        </div>
                    </div>
                    <span style="color: {'#34d399' if completeness >= 70 else '#fbbf24' if completeness >= 40 else '#f87171'}; font-weight: 700; font-size: 0.9rem;">{completeness}%</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            col_a, col_b = st.columns([1, 1])

            with col_a:
                st.markdown('<div class="section-title">Identity & Credentials</div>', unsafe_allow_html=True)
                with st.form("edit_identity"):
                    e_name = st.text_input("MP Name", value=profile.get("mp_name", selected_mp["display_name"]))
                    c1, c2 = st.columns(2)
                    with c1:
                        curr_const = selected_mp["parliamentary_constituency"]
                        if selected_mp["house"] == "Lok Sabha":
                            idx = ALL_CONSTITUENCIES.index(curr_const) if curr_const in ALL_CONSTITUENCIES else 0
                            e_const = st.selectbox("Constituency", ALL_CONSTITUENCIES, index=idx)
                        else:
                            e_const = st.text_input("Constituency", value=profile.get("constituency", curr_const))
                    with c2:
                        e_state = st.text_input("State", value=profile.get("state", ""))

                    c3, c4 = st.columns(2)
                    with c3:
                        house_opts = ["Lok Sabha", "Rajya Sabha"]
                        e_house = st.selectbox("House", house_opts, index=house_opts.index(profile.get("house", selected_mp["house"])))
                    with c4:
                        e_party = st.text_input("Party", value=profile.get("party", "Independent"))

                    st.markdown("---")
                    new_pass = st.text_input("Reset Password", type="password", placeholder="Leave blank to keep current")

                    if st.form_submit_button("Save Identity", use_container_width=True, type="primary"):
                        # Save profile
                        save_data = {
                            "mp_name": e_name, "constituency": e_const, "state": e_state,
                            "house": e_house, "party": e_party,
                            "key_facts": profile.get("key_facts", []),
                            "languages": profile.get("languages", ["English", "Hindi"]),
                            "alt_names": profile.get("alt_names", []),
                            "sovereignty_rules": profile.get("sovereignty_rules", ""),
                            "vocabulary_guide": profile.get("vocabulary_guide", {}),
                        }
                        res = save_mp_profile(tid, save_data)
                        if res["success"]:
                            st.success("Identity saved")
                        else:
                            st.error(res.get("error"))

                        # Update constituency on User/Tenant too
                        if e_const != curr_const:
                            update_mp_constituency(selected_mp["username"], e_const)

                        # Reset password if provided
                        if new_pass:
                            p_res = reset_mp_password(selected_mp["username"], new_pass)
                            if p_res["success"]:
                                st.success("Password updated")

                        st.rerun()

            with col_b:
                st.markdown('<div class="section-title">News & Drafter Profile</div>', unsafe_allow_html=True)
                with st.form("edit_profile_data"):
                    e_langs = st.text_input("Languages (comma-separated)", value=", ".join(profile.get("languages", ["English", "Hindi"])))
                    e_facts = st.text_area("Key Facts (one per line)", value="\n".join(profile.get("key_facts", [])), height=120)
                    e_alts = st.text_input("Alt Constituency Names (comma-separated)", value=", ".join(profile.get("alt_names", [])))
                    e_sovereignty = st.text_area("Sovereignty Rules", value=profile.get("sovereignty_rules", ""), height=80, help="Special rules for the AI drafter (e.g. border stance)")

                    if st.form_submit_button("Save Profile Data", use_container_width=True, type="primary"):
                        langs = [l.strip() for l in e_langs.split(",") if l.strip()]
                        facts = [f.strip() for f in e_facts.strip().split("\n") if f.strip()]
                        alts = [a.strip() for a in e_alts.split(",") if a.strip()]

                        save_data = {
                            "mp_name": profile.get("mp_name", e_name if 'e_name' in dir() else ""),
                            "constituency": profile.get("constituency", ""),
                            "state": profile.get("state", ""),
                            "house": profile.get("house", "Lok Sabha"),
                            "party": profile.get("party", "Independent"),
                            "key_facts": facts,
                            "languages": langs,
                            "alt_names": alts,
                            "sovereignty_rules": e_sovereignty,
                            "vocabulary_guide": profile.get("vocabulary_guide", {}),
                        }
                        res = save_mp_profile(tid, save_data)
                        if res["success"]:
                            st.success("Profile data saved")
                        else:
                            st.error(res.get("error"))
                        st.rerun()

            # Danger Zone
            st.markdown("---")
            with st.expander("Danger Zone", expanded=False):
                st.warning(f"Permanently delete **{selected_mp['display_name']}** and all their data?")
                c_del1, c_del2 = st.columns([3, 1])
                with c_del1:
                    confirm_text = st.text_input("Type the username to confirm", placeholder=selected_mp["username"])
                with c_del2:
                    st.write("")
                    if st.button("Delete MP", type="primary", use_container_width=True):
                        if confirm_text == selected_mp["username"]:
                            res = delete_mp(tid)
                            if res["success"]:
                                st.success("Deleted successfully")
                                st.rerun()
                            else:
                                st.error(res.get("error"))
                        else:
                            st.error("Username doesn't match")

    # ══════════════════════════════════════
    # TAB 3: GEOGRAPHY UPLOAD
    # ══════════════════════════════════════
    with tab_geo:
        st.markdown('<div class="section-title">Upload Polling Station Data</div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)

        with col1:
            p_const = st.selectbox(
                "Parliamentary Constituency",
                options=[""] + ALL_CONSTITUENCIES,
                index=0,
                key="geo_p",
                help="Select the Lok Sabha constituency"
            )

        with col2:
            if p_const:
                # Show existing assemblies for this PC + option to add new
                existing_assemblies = get_assembly_constituencies(p_const)
                assembly_options = existing_assemblies + ["➕ Add New Assembly..."]
                a_selection = st.selectbox(
                    "Assembly Constituency",
                    options=assembly_options,
                    index=0 if existing_assemblies else len(assembly_options) - 1,
                    key="geo_a_select",
                )
                if a_selection == "➕ Add New Assembly...":
                    a_const = st.text_input("New Assembly Name", key="geo_a_new", placeholder="e.g. Belgaum Uttar")
                else:
                    a_const = a_selection
            else:
                st.selectbox("Assembly Constituency", options=["Select a Parliamentary Constituency first"], disabled=True, key="geo_a_disabled")
                a_const = ""

        uploaded_pdf = st.file_uploader("Upload Election Commission PDF", type=["pdf"])
        if uploaded_pdf and p_const and a_const:
            if st.button("Parse PDF", use_container_width=True, type="primary"):
                with st.spinner("Parsing..."):
                    stations = parse_polling_station_pdf(uploaded_pdf)
                    if stations:
                        st.session_state['parsed_stations'] = stations
                        st.session_state['curr_p'] = p_const
                        st.session_state['curr_a'] = a_const
                        st.success(f"Extracted {len(stations)} stations")
                    else:
                        st.warning("No data found")

        if 'parsed_stations' in st.session_state:
            st.divider()
            json_str = json.dumps(st.session_state['parsed_stations'], indent=2, ensure_ascii=False)
            edited_json = st.text_area("JSON Editor", value=json_str, height=350)
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Save", use_container_width=True, type="primary"):
                    try:
                        data = json.loads(edited_json)
                        if save_geography_data(st.session_state['curr_p'], st.session_state['curr_a'], data):
                            st.success("Saved!")
                            del st.session_state['parsed_stations']
                            try: requests.post(f"{API_URL}/geography/reload")
                            except: pass
                    except: st.error("Invalid JSON")
            with c2:
                if st.button("Discard"):
                    del st.session_state['parsed_stations']
                    st.rerun()

        st.divider()
        st.markdown('<div class="section-title">Saved Geography Files</div>', unsafe_allow_html=True)
        pl = get_parliamentary_constituencies()
        if pl:
            for p in pl:
                with st.expander(f"🏛️ {p}"):
                    al = get_assembly_constituencies(p)
                    st.caption(f"{len(al)} assembly constituencies")
                    for a in al:
                        cx, cd = st.columns([4, 1])
                        with cx: st.write(f"**{a}** ({len(load_geography_data(p, a))} locations)")
                        with cd:
                            if st.button("Delete", key=f"del_{p}_{a}"):
                                try:
                                    os.remove(GEOGRAPHY_BASE_PATH / p / f"{a}.json")
                                    st.rerun()
                                except: pass
        else:
            st.info("No geography data uploaded yet.")

    # ══════════════════════════════════════
    # TAB 4: GEOGRAPHY RULES
    # ══════════════════════════════════════
    with tab_rules:
        st.markdown('<div class="section-title">Geography Override Rules (per MP)</div>', unsafe_allow_html=True)
        overrides = load_overrides()
        geo_rules = overrides.get("geo_overrides", {})
        mps = get_all_mps()
        mp_list = [m for m in mps if m["role"] != "admin"]

        if mp_list:
            t_opts = {f"{m['display_name']} — {m['parliamentary_constituency']} [ID {m['tenant_id']}]": str(m['tenant_id']) for m in mp_list}
            sel_mp = st.selectbox("Select MP", list(t_opts.keys()))
            if sel_mp:
                tid = t_opts[sel_mp]
                rules = geo_rules.get(tid, {})

                st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
                st.markdown(f"<h3>Add New Rule</h3>", unsafe_allow_html=True)
                c1, c2, c3 = st.columns([2, 2, 1])
                with c1: loc_in = st.text_input("Location Input", placeholder="e.g. tilakwadi")
                with c2: const_out = st.text_input("Maps To (Assembly Constituency)", placeholder="e.g. Belgaum Dakshin")
                with c3:
                    st.write("")
                    st.write("")
                    if st.button("Add Rule", type="primary", use_container_width=True):
                        if loc_in and const_out:
                            if "geo_overrides" not in overrides: overrides["geo_overrides"] = {}
                            if tid not in overrides["geo_overrides"]: overrides["geo_overrides"][tid] = {}
                            overrides["geo_overrides"][tid][loc_in.strip().lower()] = const_out
                            save_overrides(overrides)
                            st.success("Rule added")
                            st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

                if rules:
                    st.markdown(f"**{len(rules)} rules** for this MP")
                    df = pd.DataFrame([{"Location": k, "Assembly Constituency": v} for k, v in rules.items()])
                    edited = st.data_editor(df, use_container_width=True, num_rows="dynamic", key=f"ed_{tid}")
                    if st.button("Save Table", type="primary"):
                        new_r = {row["Location"]: row["Assembly Constituency"] for _, row in edited.iterrows() if row["Location"] and row["Assembly Constituency"]}
                        if "geo_overrides" not in overrides: overrides["geo_overrides"] = {}
                        overrides["geo_overrides"][tid] = new_r
                        save_overrides(overrides)
                        st.success("Saved")
                else:
                    st.info("No rules defined for this MP yet.")
        else:
            st.info("Create an MP first.")

    # ══════════════════════════════════════
    # TAB 5: CASE INTELLIGENCE
    # ══════════════════════════════════════
    with tab_intel:
        from modules.case_intelligence import render_case_intelligence
        render_case_intelligence()


if __name__ == "__main__":
    main()