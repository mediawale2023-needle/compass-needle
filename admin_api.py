"""
Admin API Router — REST endpoints for the Next.js admin dashboard.
Mounted in main.py as app.include_router(admin_router, prefix="/api/admin")
"""
import os
import io
import json
import bcrypt
import logging
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import jwt
from jwt.exceptions import PyJWTError as JWTError
from sqlalchemy import text, func

from sansadx_backend.db import engine, SessionLocal, Tenant, User, Case, TenantProfile, validate_password, get_all_overrides, save_overrides_to_db
from core.db_helpers import _q, _q_one, _parse_meta
from modules.constituencies import ALL_CONSTITUENCIES
from modules.auth import get_tenant_or_fail

logger = logging.getLogger("needle.admin_api")

# ─── Rate limiting (optional) ───
try:
    from core.rate_limiter import limiter, RATE_LOGIN
    _limit_login = limiter.limit(RATE_LOGIN)
except Exception:
    def _limit_login(f): return f

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────
JWT_SECRET = os.getenv("JWT_SECRET", "")
if not JWT_SECRET or len(JWT_SECRET) < 32:
    raise RuntimeError("JWT_SECRET must be set and at least 32 characters long")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 4  # Longer session for admin

GEOGRAPHY_BASE_PATH = Path(__file__).parent / "data" / "geography"
METADATA_PATH = Path(__file__).parent / "data" / "constituency_metadata.json"
OVERRIDES_PATH = Path("tenant_overrides.json")

security = HTTPBearer()
router = APIRouter()


# ─────────────────────────────────────────
# INPUT SANITIZERS
# ─────────────────────────────────────────
def _sanitize_path_param(value: str) -> str:
    """Reject path traversal attempts in geography params."""
    if not value or ".." in value or "/" in value or "\\" in value or "\x00" in value:
        raise HTTPException(400, "Invalid path parameter")
    return value


# ─────────────────────────────────────────
# AUTH HELPERS
# ─────────────────────────────────────────
ADMIN_ROLES = {"admin", "super_admin", "sysadmin"}


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        if stored_hash.startswith("$2b$") or stored_hash.startswith("$2a$"):
            return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
    except Exception:
        pass
    return False


def create_admin_token(data: dict) -> str:
    payload = {**data, "iat": datetime.utcnow().timestamp(), "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _is_token_revoked(username: str, token_issued_at: float) -> bool:
    """Check if a user's tokens were revoked after this token was issued."""
    try:
        row = _q_one(
            "SELECT revoked_at FROM token_blocklist WHERE username = :u ORDER BY revoked_at DESC LIMIT 1",
            {"u": username}
        )
        if row and row.get("revoked_at"):
            revoked_at = row["revoked_at"]
            if hasattr(revoked_at, 'timestamp'):
                return token_issued_at < revoked_at.timestamp()
    except Exception:
        pass
    return False


def _revoke_user_tokens(username: str):
    """Revoke all existing tokens for a user."""
    try:
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO token_blocklist (username, revoked_at) VALUES (:u, :now)"),
                {"u": username, "now": datetime.utcnow()}
            )
        logger.info(f"Revoked all tokens for user: {username}")
    except Exception as e:
        logger.error(f"Token revocation failed for {username}: {e}")


def get_admin_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify JWT and ensure user has an admin role."""
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        username = payload.get("sub")
        role = payload.get("role", "")
        if not username or role not in ADMIN_ROLES:
            raise HTTPException(403, "Admin access required")
        # Check blocklist
        token_iat = payload.get("iat", 0)
        if _is_token_revoked(username, token_iat):
            raise HTTPException(401, "Token has been revoked. Please login again.")
        user = _q_one("SELECT * FROM users WHERE username = :u", {"u": username})
        if not user or user.get("role") not in ADMIN_ROLES:
            raise HTTPException(403, "Admin access required")
        return user
    except JWTError:
        raise HTTPException(401, "Invalid or expired token")


# ─────────────────────────────────────────
# REQUEST MODELS
# ─────────────────────────────────────────
class AdminLoginRequest(BaseModel):
    username: str
    password: str


class CreateMPRequest(BaseModel):
    name: str
    username: str
    password: str
    constituency: str = "India"
    whatsapp_number: str = ""
    house: str = "Lok Sabha"
    display_name: str = ""
    state: str = ""
    party: str = "Independent"
    key_facts: List[str] = []
    languages: List[str] = ["English", "Hindi"]
    alt_names: List[str] = []


class CreatePRRequest(BaseModel):
    name: str
    username: str
    password: str
    constituency: str = ""
    whatsapp_number: str = ""
    display_name: str = ""
    state: str = ""
    party: str = ""
    key_facts: List[str] = []
    languages: List[str] = ["English", "Hindi"]
    alt_names: List[str] = []


class UpdateProfileRequest(BaseModel):
    mp_name: str = ""
    constituency: str = ""
    state: str = ""
    house: str = "Lok Sabha"
    party: str = "Independent"
    key_facts: List[str] = []
    languages: List[str] = ["English", "Hindi"]
    alt_names: List[str] = []
    sovereignty_rules: str = ""
    vocabulary_guide: dict = {}


class ResetPasswordRequest(BaseModel):
    new_password: str


class UpdateConstituencyRequest(BaseModel):
    constituency: str


class AdminPasswordResetRequest(BaseModel):
    current_password: str
    new_password: str


class CreateEditorRequest(BaseModel):
    username: str
    password: str
    display_name: str = ""


class SaveGeographyRequest(BaseModel):
    data: list


class SaveOverridesRequest(BaseModel):
    data: dict


class AddRuleRequest(BaseModel):
    location: str
    assembly_constituency: str


# ═══════════════════════════════════════════
# AUTH
# ═══════════════════════════════════════════

@router.post("/auth/login")
@_limit_login
def admin_login(req: AdminLoginRequest, request: Request):
    user = _q_one("SELECT * FROM users WHERE username = :u", {"u": req.username})
    if not user:
        raise HTTPException(401, "Invalid credentials")

    if user.get("role") not in ADMIN_ROLES:
        raise HTTPException(403, "Admin access required")

    if not verify_password(req.password, user.get("password_hash", "")):
        raise HTTPException(401, "Invalid credentials")

    if user.get("is_active") is False:
        raise HTTPException(403, "Account suspended. Contact your administrator.")

    # Auto-upgrade plain text passwords to bcrypt
    stored_hash = user.get("password_hash", "")
    if not (stored_hash.startswith("$2b$") or stored_hash.startswith("$2a$")):
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE users SET password_hash = :h WHERE username = :u"),
                {"h": hash_password(req.password), "u": req.username},
            )

    # Update last_login
    try:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE users SET last_login = :now WHERE username = :u"),
                {"now": datetime.utcnow(), "u": req.username},
            )
    except Exception:
        pass

    admin_tid = get_tenant_or_fail(user)
    token = create_admin_token({
        "sub": user["username"],
        "tid": admin_tid,
        "role": user.get("role", "admin"),
    })

    return {
        "token": token,
        "user": {
            "username": user["username"],
            "display_name": user.get("display_name") or user["username"].title(),
            "role": user.get("role", "admin"),
        },
    }


# ═══════════════════════════════════════════
# STATS
# ═══════════════════════════════════════════

@router.get("/stats")
def admin_stats(_=Depends(get_admin_user)):
    db = SessionLocal()
    try:
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


# ═══════════════════════════════════════════
# MP MANAGEMENT
# ═══════════════════════════════════════════

@router.get("/mps")
def list_mps(_=Depends(get_admin_user)):
    """List all MPs with profile and completeness data."""
    db = SessionLocal()
    try:
        from sqlalchemy.orm import joinedload
        tenants = db.query(Tenant).options(joinedload(Tenant.users)).all()
        result = []
        for t in tenants:
            for u in t.users:
                if u.role in ADMIN_ROLES:
                    continue
                # Get profile
                profile = db.query(TenantProfile).filter(TenantProfile.tenant_id == t.id).first()
                profile_data = {}
                completeness = 0
                if profile:
                    extra = profile.profile_data or {}
                    profile_data = {
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
                    # Calculate completeness
                    fields = ["mp_name", "constituency", "state", "party"]
                    score = sum(1 for f in fields if profile_data.get(f))
                    if profile_data.get("key_facts"):
                        score += 1
                    if profile_data.get("languages") and len(profile_data["languages"]) > 1:
                        score += 1
                    if profile_data.get("alt_names"):
                        score += 1
                    if profile_data.get("sovereignty_rules"):
                        score += 1
                    completeness = int((score / 8) * 100)

                result.append({
                    "tenant_id": t.id,
                    "user_id": u.id,
                    "mp_name": t.name,
                    "display_name": u.display_name or t.name,
                    "username": u.username,
                    "role": u.role,
                    "house": u.house or "Lok Sabha",
                    "parliamentary_constituency": u.constituency or t.constituency or "India",
                    "whatsapp_number": t.whatsapp_number,
                    "created_at": t.created_at.strftime("%Y-%m-%d") if t.created_at else "N/A",
                    "completeness": completeness,
                    "profile": profile_data,
                })
        return {"mps": result}
    finally:
        db.close()


@router.post("/mps")
def create_mp(req: CreateMPRequest, _=Depends(get_admin_user)):
    """Create a new MP — tenant + user + profile."""
    pw_err = validate_password(req.password)
    if pw_err:
        raise HTTPException(400, pw_err)
    db = SessionLocal()
    try:
        if db.query(User).filter(User.username == req.username).first():
            raise HTTPException(400, "Username already exists")

        new_tenant = Tenant(
            name=req.name,
            constituency=req.constituency,
            whatsapp_number=req.whatsapp_number or f"temp_{datetime.now().timestamp()}",
            subscription_plan="Pro",
            config={"language": "English", "type": req.house.upper().replace(" ", "_"), "map_enabled": True},
        )
        db.add(new_tenant)
        db.flush()

        new_user = User(
            tenant_id=new_tenant.id,
            username=req.username,
            password_hash=hash_password(req.password),
            role="mp",
            constituency=req.constituency,
            house=req.house,
            display_name=req.display_name or req.name,
        )
        db.add(new_user)

        profile_data = {
            "key_facts": req.key_facts or [],
            "languages": req.languages or ["English", "Hindi"],
            "vocabulary_guide": {},
            "sovereignty_rules": "",
            "alt_names": req.alt_names or [],
        }
        new_profile = TenantProfile(
            tenant_id=new_tenant.id,
            mp_name=req.display_name or req.name,
            constituency=req.constituency,
            state=req.state,
            house=req.house,
            party=req.party,
            profile_data=profile_data,
        )
        db.add(new_profile)
        db.commit()

        return {"success": True, "tenant_id": new_tenant.id, "user_id": new_user.id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception("Admin operation failed")
        raise HTTPException(500, "Internal server error")
    finally:
        db.close()


@router.post("/prs")
def create_pr(req: CreatePRRequest, _=Depends(get_admin_user)):
    """Create a new PR (Needle AI login) — tenant + user + profile."""
    pw_err = validate_password(req.password)
    if pw_err:
        raise HTTPException(400, pw_err)
    db = SessionLocal()
    try:
        if db.query(User).filter(User.username == req.username).first():
            raise HTTPException(400, "Username already exists")

        import uuid
        wa_number = req.whatsapp_number or f"pr_{uuid.uuid4().hex[:12]}"
        if req.whatsapp_number:
            existing = db.query(Tenant).filter(Tenant.whatsapp_number == req.whatsapp_number).first()
            if existing:
                raise HTTPException(400, f"WhatsApp number already registered to tenant '{existing.name}'")

        new_tenant = Tenant(
            name=req.name,
            constituency=req.constituency or "General",
            whatsapp_number=wa_number,
            subscription_plan="Pro",
            config={"language": "English", "type": "PR", "map_enabled": True},
        )
        db.add(new_tenant)
        db.flush()

        new_user = User(
            tenant_id=new_tenant.id,
            username=req.username,
            password_hash=hash_password(req.password),
            role="pr",
            constituency=req.constituency or "General",
            house="None",
            display_name=req.display_name or req.name,
        )
        db.add(new_user)

        profile_data = {
            "key_facts": req.key_facts or [],
            "languages": req.languages or ["English", "Hindi"],
            "vocabulary_guide": {},
            "sovereignty_rules": "",
            "alt_names": req.alt_names or [],
        }
        new_profile = TenantProfile(
            tenant_id=new_tenant.id,
            mp_name=req.display_name or req.name,
            constituency=req.constituency or "General",
            state=req.state,
            house="None",
            party=req.party or "Independent",
            profile_data=profile_data,
        )
        db.add(new_profile)
        db.commit()

        return {"success": True, "tenant_id": new_tenant.id, "user_id": new_user.id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception("Admin operation failed")
        raise HTTPException(500, "Internal server error")
    finally:
        db.close()


@router.delete("/mps/{tenant_id}")
def delete_mp(tenant_id: int, _=Depends(get_admin_user)):
    """Delete MP + tenant + profile cascade."""
    db = SessionLocal()
    try:
        db.query(TenantProfile).filter(TenantProfile.tenant_id == tenant_id).delete()
        db.query(Case).filter(Case.tenant_id == tenant_id).delete()
        db.query(User).filter(User.tenant_id == tenant_id).delete()
        db.query(Tenant).filter(Tenant.id == tenant_id).delete()
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        logger.exception("Admin operation failed")
        raise HTTPException(500, "Internal server error")
    finally:
        db.close()


# ═══════════════════════════════════════════
# MP PROFILE
# ═══════════════════════════════════════════

@router.get("/mps/{tenant_id}/profile")
def get_mp_profile(tenant_id: int, _=Depends(get_admin_user)):
    db = SessionLocal()
    try:
        profile = db.query(TenantProfile).filter(TenantProfile.tenant_id == tenant_id).first()
        if not profile:
            return {"exists": False}

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
    finally:
        db.close()


@router.patch("/mps/{tenant_id}/profile")
def update_mp_profile(tenant_id: int, req: UpdateProfileRequest, _=Depends(get_admin_user)):
    db = SessionLocal()
    try:
        profile = db.query(TenantProfile).filter(TenantProfile.tenant_id == tenant_id).first()

        profile_data = {
            "key_facts": req.key_facts,
            "languages": req.languages,
            "alt_names": req.alt_names,
            "sovereignty_rules": req.sovereignty_rules,
            "vocabulary_guide": req.vocabulary_guide,
        }

        if profile:
            profile.mp_name = req.mp_name or profile.mp_name
            profile.constituency = req.constituency or profile.constituency
            profile.state = req.state or profile.state
            profile.house = req.house or profile.house
            profile.party = req.party or profile.party
            profile.profile_data = profile_data
        else:
            profile = TenantProfile(
                tenant_id=tenant_id,
                mp_name=req.mp_name,
                constituency=req.constituency,
                state=req.state,
                house=req.house,
                party=req.party,
                profile_data=profile_data,
            )
            db.add(profile)

        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        logger.exception("Admin operation failed")
        raise HTTPException(500, "Internal server error")
    finally:
        db.close()


@router.patch("/mps/{tenant_id}/constituency")
def update_constituency(tenant_id: int, req: UpdateConstituencyRequest, _=Depends(get_admin_user)):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.tenant_id == tenant_id, User.role == "mp").first()
        if user:
            user.constituency = req.constituency
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if tenant:
            tenant.constituency = req.constituency
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        logger.exception("Admin operation failed")
        raise HTTPException(500, "Internal server error")
    finally:
        db.close()


@router.patch("/mps/{tenant_id}/password")
def reset_mp_password(tenant_id: int, req: ResetPasswordRequest, _=Depends(get_admin_user)):
    pw_err = validate_password(req.new_password)
    if pw_err:
        raise HTTPException(400, pw_err)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.tenant_id == tenant_id, User.role == "mp").first()
        if not user:
            raise HTTPException(404, "MP not found")
        user.password_hash = hash_password(req.new_password)
        db.commit()
        # Revoke all existing tokens for this MP
        _revoke_user_tokens(user.username)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception("Admin operation failed")
        raise HTTPException(500, "Internal server error")
    finally:
        db.close()


# ═══════════════════════════════════════════
# EDITORS
# ═══════════════════════════════════════════

@router.get("/editors")
def list_editors(_=Depends(get_admin_user)):
    db = SessionLocal()
    try:
        editors = db.query(User).filter(User.role == "editor").all()
        return {
            "editors": [
                {
                    "id": e.id,
                    "username": e.username,
                    "tenant_id": e.tenant_id,
                    "display_name": e.display_name or e.username,
                    "house": e.house or "",
                }
                for e in editors
            ]
        }
    finally:
        db.close()


@router.post("/editors")
def create_editor(req: CreateEditorRequest, _=Depends(get_admin_user)):
    pw_err = validate_password(req.password)
    if pw_err:
        raise HTTPException(400, pw_err)
    db = SessionLocal()
    try:
        if db.query(User).filter(User.username == req.username).first():
            raise HTTPException(400, "Username already exists")
        admin_tenant = db.query(Tenant).filter(Tenant.name == "System Admin").first()
        if not admin_tenant:
            raise HTTPException(500, "System Admin tenant not found")
        new_editor = User(
            tenant_id=admin_tenant.id,
            username=req.username,
            password_hash=hash_password(req.password),
            role="editor",
            display_name=req.display_name or req.username,
        )
        db.add(new_editor)
        db.commit()
        return {"success": True, "user_id": new_editor.id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception("Admin operation failed")
        raise HTTPException(500, "Internal server error")
    finally:
        db.close()


@router.delete("/editors/{editor_id}")
def delete_editor(editor_id: int, _=Depends(get_admin_user)):
    db = SessionLocal()
    try:
        db.query(User).filter(User.id == editor_id, User.role == "editor").delete()
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        logger.exception("Admin operation failed")
        raise HTTPException(500, "Internal server error")
    finally:
        db.close()


# ═══════════════════════════════════════════
# ADMIN SETTINGS
# ═══════════════════════════════════════════

@router.patch("/settings/password")
def reset_admin_password(req: AdminPasswordResetRequest, user=Depends(get_admin_user)):
    if not verify_password(req.current_password, user.get("password_hash", "")):
        raise HTTPException(400, "Current password is incorrect")
    pw_err = validate_password(req.new_password)
    if pw_err:
        raise HTTPException(400, pw_err)
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.username == user["username"]).first()
        if u:
            u.password_hash = hash_password(req.new_password)
            db.commit()
            # Revoke all existing tokens for this admin
            _revoke_user_tokens(user["username"])
        return {"success": True}
    except Exception as e:
        db.rollback()
        logger.exception("Admin operation failed")
        raise HTTPException(500, "Internal server error")
    finally:
        db.close()


@router.post("/logout")
def admin_logout(user=Depends(get_admin_user)):
    """Revoke all tokens for the current admin — forces re-login."""
    _revoke_user_tokens(user.get("username", ""))
    return {"success": True, "message": "Logged out. All sessions invalidated."}


# ═══════════════════════════════════════════
# GEOGRAPHY
# ═══════════════════════════════════════════

@router.get("/constituencies")
def list_constituencies(_=Depends(get_admin_user)):
    return {"constituencies": ALL_CONSTITUENCIES}


@router.get("/geography/parliamentary")
def list_parliamentary(_=Depends(get_admin_user)):
    GEOGRAPHY_BASE_PATH.mkdir(parents=True, exist_ok=True)
    pcs = [d.name for d in GEOGRAPHY_BASE_PATH.iterdir() if d.is_dir()]
    return {"parliamentary_constituencies": pcs}


@router.get("/geography/{pc}/assemblies")
def list_assemblies(pc: str, _=Depends(get_admin_user)):
    pc = _sanitize_path_param(pc)
    path = GEOGRAPHY_BASE_PATH / pc
    if not path.exists():
        return {"assemblies": []}
    assemblies = [f.stem for f in path.glob("*.json")]
    return {"assemblies": assemblies}


@router.get("/geography/{pc}/{ac}")
def load_geography(pc: str, ac: str, _=Depends(get_admin_user)):
    pc = _sanitize_path_param(pc)
    ac = _sanitize_path_param(ac)
    filepath = GEOGRAPHY_BASE_PATH / pc / f"{ac}.json"
    if not filepath.exists():
        return {"data": []}
    with open(filepath, "r", encoding="utf-8") as f:
        return {"data": json.load(f)}


@router.put("/geography/{pc}/{ac}")
def save_geography(pc: str, ac: str, req: SaveGeographyRequest, _=Depends(get_admin_user)):
    pc = _sanitize_path_param(pc)
    ac = _sanitize_path_param(ac)
    try:
        path = GEOGRAPHY_BASE_PATH / pc
        path.mkdir(parents=True, exist_ok=True)
        with open(path / f"{ac}.json", "w", encoding="utf-8") as f:
            json.dump(req.data, f, indent=2, ensure_ascii=False)
        # Auto-generate overrides
        try:
            from modules.geography_resolver import auto_generate_overrides
            auto_generate_overrides()
        except Exception as e:
            logger.warning(f"Override auto-gen: {e}")
        return {"success": True}
    except Exception as e:
        logger.exception("Admin operation failed")
        raise HTTPException(500, "Internal server error")


@router.delete("/geography/{pc}/{ac}")
def delete_geography(pc: str, ac: str, _=Depends(get_admin_user)):
    pc = _sanitize_path_param(pc)
    ac = _sanitize_path_param(ac)
    filepath = GEOGRAPHY_BASE_PATH / pc / f"{ac}.json"
    if filepath.exists():
        filepath.unlink()
        return {"success": True}
    raise HTTPException(404, "File not found")


@router.post("/geography/upload-pdf")
async def upload_pdf(file: UploadFile = File(...), _=Depends(get_admin_user)):
    """Parse an Election Commission polling station PDF."""
    try:
        import pdfplumber
    except ImportError:
        raise HTTPException(500, "pdfplumber not installed")

    stations = []
    debug_info = {"pages": 0, "tables_found": 0, "text_pages": 0, "raw_rows": 0}

    try:
        content = await file.read()
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(413, "File too large (max 10MB)")
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            debug_info["pages"] = len(pdf.pages)
            for page in pdf.pages:
                tables = page.extract_tables({"vertical_strategy": "lines", "horizontal_strategy": "lines", "snap_tolerance": 5, "join_tolerance": 5})
                if not tables:
                    tables = page.extract_tables({"vertical_strategy": "text", "horizontal_strategy": "text"})
                if tables:
                    debug_info["tables_found"] += len(tables)
                    for table in tables:
                        for row in table:
                            if not row:
                                continue
                            debug_info["raw_rows"] += 1
                            s = _extract_station_from_row(row)
                            if s:
                                stations.append(s)
                else:
                    page_text = page.extract_text()
                    if page_text:
                        debug_info["text_pages"] += 1
                        stations.extend(_extract_stations_from_text(page_text))
    except Exception as e:
        raise HTTPException(500, f"PDF parse error: {e}")

    # Dedup
    result = []
    seen = set()
    auto_num = 1
    for s in stations:
        if not s.get("station_number"):
            s["station_number"] = str(auto_num)
            auto_num += 1
        key = f"{s['station_number']}_{s.get('locality', '')}"
        if key not in seen:
            seen.add(key)
            result.append(s)

    return {"stations": result, "debug": debug_info}


def _extract_station_from_row(row):
    if not row:
        return None
    cleaned = [str(cell).strip().replace("\n", " ").strip() if cell else "" for cell in row]
    skip_words = {"station", "number", "part", "polling", "booth", "name", "address", "building", "sl.no", "sl no", "serial", "location", "constituency", "total", "page", "sr.no"}
    row_text = " ".join(cleaned).lower()
    if any(w in row_text for w in skip_words) and not any(c.isdigit() and len(c) <= 4 for c in cleaned[:3]):
        return None
    num, loc, bldg = "", "", ""
    for cell in cleaned:
        if not cell:
            continue
        if not num and re.match(r"^\d{1,4}\.?$", cell.strip(".")):
            num = cell.strip(".")
        elif len(cell) > 2 and not cell.replace(".", "").replace(",", "").isdigit():
            if not loc:
                loc = cell
            elif not bldg:
                bldg = cell
    if loc:
        return {"station_number": num, "locality": loc, "building_name": bldg}
    return None


def _extract_stations_from_text(text):
    stations = []
    lines = text.split("\n")
    patterns = [
        re.compile(r"(\d{1,4})\s*[-:\.]\s*(.+)"),
        re.compile(r"(?:Station|Booth|Part)\s*(?:No\.?\s*)?(\d{1,4})\s*[-:\.]\s*(.+)", re.IGNORECASE),
        re.compile(r"^(\d{1,4})\.\s+(.+)"),
        re.compile(r"^(\d{1,4})\s{2,}(.+)"),
    ]
    for line in lines:
        line = line.strip()
        if not line or len(line) < 5:
            continue
        if any(h in line.lower() for h in ["station name", "part number", "page ", "total ", "polling station list"]):
            continue
        for pat in patterns:
            match = pat.match(line)
            if match:
                num = match.group(1)
                rest = match.group(2).strip()
                parts = [p.strip() for p in rest.split(",", 1)]
                loc = parts[0] if parts else rest
                bldg = parts[1] if len(parts) > 1 else ""
                if len(loc) > 2:
                    stations.append({"station_number": num, "locality": loc, "building_name": bldg})
                break
    return stations


# ═══════════════════════════════════════════
# OVERRIDES
# ═══════════════════════════════════════════

@router.get("/overrides")
def load_overrides(_=Depends(get_admin_user)):
    try:
        return get_all_overrides()
    except Exception:
        # Fallback to file if DB table doesn't exist yet
        if OVERRIDES_PATH.exists():
            with open(OVERRIDES_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}


@router.put("/overrides")
def save_overrides(req: SaveOverridesRequest, _=Depends(get_admin_user)):
    try:
        save_overrides_to_db(req.data)
        return {"success": True}
    except Exception as e:
        logger.exception("Admin operation failed")
        raise HTTPException(500, "Internal server error")


# ═══════════════════════════════════════════
# CASE INTELLIGENCE
# ═══════════════════════════════════════════



@router.get("/cases/health")
def case_health(_=Depends(get_admin_user)):
    """Platform Health — top-line metrics, status breakdown, MP cases, activity, volume."""

    total = _q_one("SELECT COUNT(*) AS cnt FROM cases") or {"cnt": 0}
    mps_row = _q_one("SELECT COUNT(*) AS cnt FROM tenants WHERE name != 'System Admin'") or {"cnt": 0}
    resolved = _q_one("SELECT COUNT(*) AS cnt FROM cases WHERE status = 'resolved'") or {"cnt": 0}
    critical = _q_one("SELECT COUNT(*) AS cnt FROM cases WHERE is_critical = true") or {"cnt": 0}

    status_data = _q("SELECT COALESCE(status, 'unknown') AS status, COUNT(*) AS count FROM cases GROUP BY status ORDER BY count DESC")

    mp_data = _q("""
        SELECT t.name, t.constituency, COUNT(c.id) AS cases
        FROM tenants t LEFT JOIN cases c ON t.id = c.tenant_id
        WHERE t.name != 'System Admin'
        GROUP BY t.id, t.name, t.constituency ORDER BY cases DESC
    """)

    activity_data = _q("""
        SELECT u.display_name, u.username, u.last_login,
               t.constituency, t.name AS mp_name, COUNT(c.id) AS total_cases
        FROM users u JOIN tenants t ON u.tenant_id = t.id
        LEFT JOIN cases c ON t.id = c.tenant_id
        WHERE u.role IN ('mp', 'user') AND t.name != 'System Admin'
        GROUP BY u.id, u.display_name, u.username, u.last_login, t.constituency, t.name
        ORDER BY total_cases DESC
    """)

    activity = []
    for a in activity_data:
        last = a.get("last_login")
        if last:
            last_str = last.strftime("%Y-%m-%d %H:%M") if hasattr(last, "strftime") else str(last)[:16]
        else:
            last_str = "Never"
        activity.append({
            "mp": a.get("display_name") or a["username"],
            "constituency": a.get("constituency", ""),
            "cases": a.get("total_cases", 0),
            "last_login": last_str,
            "active": last_str != "Never",
        })

    volume_data = _q("""
        SELECT DATE(created_at) AS day, COUNT(*) AS count
        FROM cases WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY DATE(created_at) ORDER BY day
    """)
    volume = []
    for v in volume_data:
        d = v.get("day")
        volume.append({
            "day": d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d),
            "count": v["count"],
        })

    return {
        "total_cases": total["cnt"],
        "active_mps": mps_row["cnt"],
        "resolved": resolved["cnt"],
        "critical": critical["cnt"],
        "status_breakdown": status_data,
        "mp_cases": mp_data,
        "activity": activity,
        "volume_30d": volume,
    }


@router.get("/cases/explorer")
def case_explorer(
    mp_id: Optional[int] = None,
    period: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    _=Depends(get_admin_user),
):
    """Case Explorer with filters."""
    conditions = ["1=1"]
    params = {}

    if mp_id:
        conditions.append("c.tenant_id = :tid")
        params["tid"] = mp_id

    if period == "7days":
        conditions.append("c.created_at >= CURRENT_DATE - INTERVAL '7 days'")
    elif period == "30days":
        conditions.append("c.created_at >= CURRENT_DATE - INTERVAL '30 days'")
    elif period == "90days":
        conditions.append("c.created_at >= CURRENT_DATE - INTERVAL '90 days'")

    if category:
        conditions.append("c.category = :cat")
        params["cat"] = category

    if status:
        conditions.append("c.status = :st")
        params["st"] = status

    where = " AND ".join(conditions)

    count_row = _q_one(f"SELECT COUNT(*) AS cnt FROM cases c WHERE {where}", params) or {"cnt": 0}
    total = count_row["cnt"]

    cases = _q(f"""
        SELECT c.id, c.tenant_id, t.name AS mp_name, t.constituency,
               c.user_phone, c.category, c.status, c.raw_message,
               c.case_metadata, c.is_critical, c.created_at, c.updated_at,
               c.response_to_citizen, c.notes_for_staff
        FROM cases c JOIN tenants t ON c.tenant_id = t.id
        WHERE {where} ORDER BY c.created_at DESC LIMIT 200
    """, params)

    rows = []
    for c in cases:
        meta = _parse_meta(c.get("case_metadata"))
        created = c.get("created_at")
        created_str = created.strftime("%Y-%m-%d %H:%M") if hasattr(created, "strftime") else str(created)[:16] if created else "-"
        rows.append({
            "id": c["id"],
            "mp": c.get("mp_name", "-"),
            "phone": c.get("user_phone", "-"),
            "category": c.get("category", "-"),
            "status": c.get("status", "-"),
            "location": meta.get("matched_value", "-"),
            "assembly": meta.get("assembly_constituency", "-"),
            "message": (c.get("raw_message") or "-")[:80],
            "created": created_str,
            "critical": c.get("is_critical", False),
        })

    # Get filter options
    categories = _q("SELECT DISTINCT category FROM cases WHERE category IS NOT NULL ORDER BY category")
    statuses = _q("SELECT DISTINCT status FROM cases WHERE status IS NOT NULL ORDER BY status")
    tenants = _q("SELECT id, name, constituency FROM tenants WHERE name != 'System Admin' ORDER BY name")

    return {
        "total": total,
        "cases": rows,
        "filter_options": {
            "categories": [c["category"] for c in categories if c["category"]],
            "statuses": [s["status"] for s in statuses if s["status"]],
            "mps": [{"id": t["id"], "name": t["name"], "constituency": t["constituency"]} for t in tenants],
        },
    }


@router.get("/cases/{case_id}")
def case_detail(case_id: int, _=Depends(get_admin_user)):
    detail = _q_one("""
        SELECT c.*, t.name AS mp_name, t.constituency AS mp_constituency
        FROM cases c JOIN tenants t ON c.tenant_id = t.id
        WHERE c.id = :cid
    """, {"cid": case_id})

    if not detail:
        raise HTTPException(404, "Case not found")

    meta = _parse_meta(detail.get("case_metadata"))

    def fmt_dt(dt):
        if not dt:
            return "-"
        return dt.strftime("%Y-%m-%d %H:%M") if hasattr(dt, "strftime") else str(dt)[:16]

    return {
        "id": detail["id"],
        "mp_name": detail.get("mp_name", "-"),
        "mp_constituency": detail.get("mp_constituency", "-"),
        "phone": detail.get("user_phone", "-"),
        "category": detail.get("category", "-"),
        "status": detail.get("status", "-"),
        "critical": detail.get("is_critical", False),
        "location": meta.get("matched_value", detail.get("location", "-")),
        "assembly": meta.get("assembly_constituency", detail.get("ward", "-")),
        "confidence": meta.get("confidence", "-"),
        "raw_message": detail.get("raw_message", "-"),
        "response_to_citizen": detail.get("response_to_citizen", ""),
        "notes_for_staff": detail.get("notes_for_staff", ""),
        "created_at": fmt_dt(detail.get("created_at")),
        "updated_at": fmt_dt(detail.get("updated_at")),
        "resolved_at": fmt_dt(detail.get("resolved_at")),
    }


@router.get("/cases/analytics/data")
def case_analytics(_=Depends(get_admin_user)):
    """Grievance Analytics — categories, resolution times, assembly distribution."""

    # Top categories per constituency
    cat_data = _q("""
        SELECT COALESCE(c.category, 'Uncategorized') AS category,
               t.constituency, COUNT(*) AS count
        FROM cases c JOIN tenants t ON c.tenant_id = t.id
        WHERE t.name != 'System Admin'
        GROUP BY c.category, t.constituency ORDER BY count DESC LIMIT 30
    """)

    # Category volume
    cat_vol = _q("""
        SELECT COALESCE(category, 'Uncategorized') AS category, COUNT(*) AS count
        FROM cases WHERE tenant_id != 1 GROUP BY category ORDER BY count DESC
    """)

    # Status distribution
    status_vol = _q("""
        SELECT COALESCE(status, 'unknown') AS status, COUNT(*) AS count
        FROM cases WHERE tenant_id != 1 GROUP BY status ORDER BY count DESC
    """)

    # Resolution time
    resolution_data = _q("""
        SELECT t.name AS mp_name, t.constituency,
               COUNT(*) AS resolved_cases,
               AVG(EXTRACT(EPOCH FROM (c.resolved_at - c.created_at)) / 3600) AS avg_hours
        FROM cases c JOIN tenants t ON c.tenant_id = t.id
        WHERE c.resolved_at IS NOT NULL AND c.created_at IS NOT NULL AND t.name != 'System Admin'
        GROUP BY t.id, t.name, t.constituency ORDER BY avg_hours
    """)

    resolution = []
    for r in resolution_data:
        avg_h = r.get("avg_hours")
        if avg_h is not None:
            time_str = f"{avg_h / 24:.1f} days" if avg_h > 24 else f"{avg_h:.1f} hours"
        else:
            time_str = "-"
        resolution.append({
            "mp": r["mp_name"],
            "constituency": r["constituency"],
            "resolved_cases": r["resolved_cases"],
            "avg_resolution_time": time_str,
        })

    # Assembly distribution
    assembly_data = _q("SELECT case_metadata FROM cases WHERE case_metadata IS NOT NULL AND tenant_id != 1")
    ac_counts = {}
    for row in assembly_data:
        meta = _parse_meta(row.get("case_metadata"))
        ac = meta.get("assembly_constituency")
        if ac:
            ac_counts[ac] = ac_counts.get(ac, 0) + 1

    ac_sorted = sorted(ac_counts.items(), key=lambda x: -x[1])

    return {
        "category_breakdown": cat_data,
        "category_volume": cat_vol,
        "status_distribution": status_vol,
        "resolution_times": resolution,
        "assembly_distribution": [{"assembly": a, "cases": c} for a, c in ac_sorted],
    }


# ═══════════════════════════════════════════
# SEED & TENANTS (admin JWT only; no separate secret)
# ═══════════════════════════════════════════

@router.post("/seed-test-cases")
def seed_test_cases(tid: int = 0, _=Depends(get_admin_user)):
    """Seed test cases for CSR pipeline testing. Requires admin JWT.
    Pass tid=0 (default) to target the first tenant."""
    import random

    db = SessionLocal()
    try:
        if tid == 0:
            first_tenant = db.query(Tenant).first()
            if not first_tenant:
                raise HTTPException(404, "No tenants found")
            tid = first_tenant.id

        target = db.query(Tenant).filter(Tenant.id == tid).first()
        if not target:
            raise HTTPException(404, f"Tenant {tid} not found")

        db.query(Case).filter(Case.tenant_id == tid, Case.user_phone.like("9199%")).delete(synchronize_session=False)
        db.commit()

        clusters = [
            {"category": "Water", "location": "Kelkar Bag", "count": 230},
            {"category": "Infrastructure (State)", "location": "Tilakwadi", "count": 210},
            {"category": "Education (Central)", "location": "Shahapur", "count": 150},
        ]
        phones = [f"9199{i:07d}" for i in range(600)]
        messages = {
            "Water": ["paani nahi aahe ithe", "water supply band aahe", "nali tutli aahe"],
            "Infrastructure (State)": ["rasta khrab aahe", "khade aahet rastawar", "street light nahi"],
            "Education (Central)": ["school madhe teacher nahi", "classroom tutla", "toilet nahi school la"],
        }

        total_inserted = 0
        for cluster in clusters:
            for i in range(cluster["count"]):
                msg_list = messages.get(cluster["category"], ["complaint"])
                case = Case(
                    tenant_id=tid,
                    user_phone=random.choice(phones),
                    raw_message=random.choice(msg_list),
                    category=cluster["category"],
                    status="completed",
                    location=cluster["location"],
                    ward=cluster["location"],
                    is_critical=(i % 20 == 0),
                    response_to_citizen="Noted",
                    case_metadata=json.dumps({
                        "user_intent": "complaint",
                        "location_resolved": True,
                        "matched_value": cluster["location"],
                        "assembly_constituency": cluster["location"],
                    }),
                    created_at=datetime.utcnow() - timedelta(days=random.randint(1, 90)),
                )
                db.add(case)
                total_inserted += 1

        db.commit()
        return {"status": "seeded", "tenant_id_used": tid, "total_cases": total_inserted}
    finally:
        db.close()


@router.get("/tenants")
def debug_tenants(_=Depends(get_admin_user)):
    """List tenants with case counts. Requires admin JWT."""
    db = SessionLocal()
    try:
        tenants = db.query(Tenant).all()
        result = []
        for t in tenants:
            case_count = db.query(func.count(Case.id)).filter(Case.tenant_id == t.id).scalar()
            result.append({"id": t.id, "name": t.name, "constituency": t.constituency, "cases": case_count})
        return {"tenants": result}
    finally:
        db.close()


# ═══════════════════════════════════════════
# PERMISSION HELPERS
# ═══════════════════════════════════════════
def require_super_admin(user=Depends(get_admin_user)):
    """Restrict endpoint to super_admin / sysadmin only."""
    if user.get("role") not in {"super_admin", "sysadmin"}:
        raise HTTPException(403, "Super-admin access required for this action.")
    return user


# ═══════════════════════════════════════════
# TENANT HEALTH MONITORING
# ═══════════════════════════════════════════
@router.get("/tenant-health")
def tenant_health(_=Depends(get_admin_user)):
    """Per-tenant health status: last case, last login, status bucket."""
    rows = _q("""
        SELECT t.id, t.name, t.constituency, t.is_active,
               MAX(c.created_at)  AS last_case,
               MAX(u.last_login)  AS last_login,
               COUNT(c.id)        AS total_cases,
               SUM(CASE WHEN c.status = 'new' THEN 1 ELSE 0 END) AS open_cases
        FROM tenants t
        LEFT JOIN cases c  ON c.tenant_id  = t.id
        LEFT JOIN users u  ON u.tenant_id  = t.id AND u.role = 'user'
        WHERE t.name != 'System Admin'
        GROUP BY t.id, t.name, t.constituency, t.is_active
        ORDER BY last_case DESC NULLS LAST
    """, {})
    now = datetime.utcnow()
    for r in rows:
        for f in ("last_case", "last_login"):
            if r.get(f) and hasattr(r[f], "isoformat"):
                r[f] = r[f].isoformat()
        last = r.get("last_case")
        if not last:
            r["health"] = "no_data"
        else:
            days = (now - datetime.fromisoformat(last)).days
            r["health"] = "active" if days <= 7 else ("stale" if days <= 30 else "inactive")
    return {"tenants": rows}


# ═══════════════════════════════════════════
# PER-TENANT USAGE ANALYTICS
# ═══════════════════════════════════════════
@router.get("/usage-analytics")
def usage_analytics(_=Depends(get_admin_user)):
    """Monthly usage breakdown per tenant: cases, AI drafts, letterbox items."""
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    tenants = _q("SELECT id, name, constituency FROM tenants WHERE name != 'System Admin' ORDER BY name", {})
    result = []
    for t in tenants:
        tid = t["id"]
        cases_month = (_q_one("SELECT COUNT(*) AS c FROM cases WHERE tenant_id=:t AND created_at>=:m", {"t": tid, "m": month_start}) or {}).get("c", 0)
        cases_total = (_q_one("SELECT COUNT(*) AS c FROM cases WHERE tenant_id=:t", {"t": tid}) or {}).get("c", 0)
        letters = (_q_one("SELECT COUNT(*) AS c FROM activity_history WHERE tenant_id=:t AND activity_type='draft_letter' AND created_at>=:m", {"t": tid, "m": month_start}) or {}).get("c", 0)
        questions = (_q_one("SELECT COUNT(*) AS c FROM activity_history WHERE tenant_id=:t AND activity_type='draft_question' AND created_at>=:m", {"t": tid, "m": month_start}) or {}).get("c", 0)
        analysis = (_q_one("SELECT COUNT(*) AS c FROM activity_history WHERE tenant_id=:t AND activity_type IN ('analysis','copilot_chat') AND created_at>=:m", {"t": tid, "m": month_start}) or {}).get("c", 0)
        letterbox = (_q_one("SELECT COUNT(*) AS c FROM letterbox WHERE tenant_id=:t AND created_at>=:m", {"t": tid, "m": month_start}) or {}).get("c", 0)
        result.append({
            "tenant_id": tid,
            "name": t["name"],
            "constituency": t["constituency"],
            "cases_this_month": cases_month,
            "cases_total": cases_total,
            "letters_drafted": letters,
            "questions_drafted": questions,
            "docs_analysed": analysis,
            "letterbox_items": letterbox,
        })
    return {"period": now.strftime("%B %Y"), "tenants": result}


# ═══════════════════════════════════════════
# STAFF ACCOUNT MANAGEMENT
# ═══════════════════════════════════════════
class StaffEditRequest(BaseModel):
    display_name: Optional[str] = None
    role: Optional[str] = None


class StaffReassignRequest(BaseModel):
    tenant_id: int


@router.get("/staff")
def list_all_staff(_=Depends(get_admin_user)):
    """List all non-admin users across all tenants."""
    rows = _q("""
        SELECT u.id, u.username, u.display_name, u.role, u.is_active,
               u.last_login, u.tenant_id, t.name AS tenant_name, t.constituency
        FROM users u
        JOIN tenants t ON t.id = u.tenant_id
        WHERE u.role NOT IN ('admin', 'super_admin', 'sysadmin')
        ORDER BY t.name, u.display_name
    """, {})
    for r in rows:
        if r.get("last_login") and hasattr(r["last_login"], "isoformat"):
            r["last_login"] = r["last_login"].isoformat()
        r["is_active"] = bool(r.get("is_active", True))
    return {"staff": rows}


@router.patch("/staff/{staff_id}")
def edit_staff(staff_id: int, req: StaffEditRequest, _=Depends(get_admin_user)):
    updates, params = [], {"id": staff_id}
    if req.display_name is not None:
        updates.append("display_name = :dn")
        params["dn"] = req.display_name
    if req.role is not None:
        if req.role in {"admin", "super_admin", "sysadmin"}:
            raise HTTPException(400, "Cannot grant admin roles via this endpoint.")
        updates.append("role = :role")
        params["role"] = req.role
    if not updates:
        raise HTTPException(400, "Nothing to update.")
    with engine.begin() as conn:
        result = conn.execute(text(f"UPDATE users SET {', '.join(updates)} WHERE id = :id AND role NOT IN ('admin','super_admin','sysadmin')"), params)
    if result.rowcount == 0:
        raise HTTPException(404, "Staff member not found.")
    return {"success": True}


@router.patch("/staff/{staff_id}/suspend")
def toggle_staff_suspension(staff_id: int, _=Depends(get_admin_user)):
    """Toggle is_active flag. Returns new state."""
    row = _q_one("SELECT is_active, role FROM users WHERE id = :id", {"id": staff_id})
    if not row:
        raise HTTPException(404, "Staff member not found.")
    if row.get("role") in {"admin", "super_admin", "sysadmin"}:
        raise HTTPException(400, "Cannot suspend admin accounts.")
    new_state = not bool(row.get("is_active", True))
    with engine.begin() as conn:
        conn.execute(text("UPDATE users SET is_active = :s WHERE id = :id"), {"s": new_state, "id": staff_id})
    return {"success": True, "is_active": new_state}


@router.patch("/staff/{staff_id}/reassign")
def reassign_staff(staff_id: int, req: StaffReassignRequest, _=Depends(get_admin_user)):
    """Move a staff member to a different tenant."""
    tenant = _q_one("SELECT id FROM tenants WHERE id = :t", {"t": req.tenant_id})
    if not tenant:
        raise HTTPException(404, "Target tenant not found.")
    with engine.begin() as conn:
        result = conn.execute(
            text("UPDATE users SET tenant_id = :t WHERE id = :id AND role NOT IN ('admin','super_admin','sysadmin')"),
            {"t": req.tenant_id, "id": staff_id},
        )
    if result.rowcount == 0:
        raise HTTPException(404, "Staff member not found or is an admin.")
    return {"success": True}


# ═══════════════════════════════════════════
# ONBOARDING STATE
# ═══════════════════════════════════════════
class OnboardingUpdate(BaseModel):
    geography: Optional[bool] = None
    staff: Optional[bool] = None
    test_sent: Optional[bool] = None
    live: Optional[bool] = None


@router.patch("/mps/{tenant_id}/onboarding")
def update_onboarding(tenant_id: int, req: OnboardingUpdate, _=Depends(get_admin_user)):
    row = _q_one("SELECT onboarding_state FROM tenants WHERE id = :t", {"t": tenant_id})
    if not row:
        raise HTTPException(404, "Tenant not found.")
    state = {}
    raw = row.get("onboarding_state")
    if raw:
        state = raw if isinstance(raw, dict) else json.loads(raw)
    for key in ("geography", "staff", "test_sent", "live"):
        val = getattr(req, key)
        if val is not None:
            state[key] = val
    # Setting live=true also activates the tenant
    updates = ["onboarding_state = :s"]
    params = {"s": json.dumps(state), "t": tenant_id}
    if req.live is True:
        updates.append("is_active = true")
    elif req.live is False:
        updates.append("is_active = false")
    with engine.begin() as conn:
        conn.execute(text(f"UPDATE tenants SET {', '.join(updates)} WHERE id = :t"), params)
    return {"success": True, "onboarding_state": state}


# ═══════════════════════════════════════════
# DATA EXPORT (ZIP of CSVs)
# ═══════════════════════════════════════════
@router.get("/tenants/{tenant_id}/export")
def export_tenant_data(tenant_id: int, admin=Depends(require_super_admin)):
    import csv, zipfile
    from fastapi.responses import StreamingResponse

    tenant = _q_one("SELECT name, constituency FROM tenants WHERE id = :t", {"t": tenant_id})
    if not tenant:
        raise HTTPException(404, "Tenant not found.")

    def rows_to_csv(rows):
        if not rows:
            return ""
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=rows[0].keys())
        writer.writeheader()
        for r in rows:
            safe = {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in r.items()}
            writer.writerow(safe)
        return buf.getvalue()

    datasets = {
        "cases": _q("SELECT * FROM cases WHERE tenant_id=:t ORDER BY created_at DESC", {"t": tenant_id}),
        "letterbox": _q("SELECT * FROM letterbox WHERE tenant_id=:t ORDER BY created_at DESC", {"t": tenant_id}),
        "activity_history": _q("SELECT * FROM activity_history WHERE tenant_id=:t ORDER BY created_at DESC", {"t": tenant_id}),
        "contacts": _q("SELECT * FROM contacts WHERE tenant_id=:t", {"t": tenant_id}),
        "users": _q("SELECT id, username, display_name, role, is_active, last_login FROM users WHERE tenant_id=:t", {"t": tenant_id}),
    }

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, rows in datasets.items():
            zf.writestr(f"{name}.csv", rows_to_csv(rows))
    zip_buf.seek(0)

    safe_name = (tenant.get("constituency") or "export").replace(" ", "_")
    filename = f"needle_export_{safe_name}_{datetime.utcnow().strftime('%Y%m%d')}.zip"
    return StreamingResponse(
        zip_buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ═══════════════════════════════════════════
# ANNOUNCEMENTS MANAGEMENT
# ═══════════════════════════════════════════
class AnnouncementCreate(BaseModel):
    title: str
    body: Optional[str] = None


@router.get("/announcements")
def list_announcements(_=Depends(get_admin_user)):
    rows = _q("SELECT id, title, body, is_active, created_at FROM announcements ORDER BY created_at DESC", {})
    for r in rows:
        if r.get("created_at") and hasattr(r["created_at"], "isoformat"):
            r["created_at"] = r["created_at"].isoformat()
        r["is_active"] = bool(r.get("is_active", True))
    return {"announcements": rows}


@router.post("/announcements")
def create_announcement(req: AnnouncementCreate, _=Depends(get_admin_user)):
    if not req.title.strip():
        raise HTTPException(400, "Title is required.")
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO announcements (title, body, is_active, created_at) VALUES (:t, :b, true, :now)"
        ), {"t": req.title.strip(), "b": req.body, "now": datetime.utcnow()})
    return {"success": True}


@router.patch("/announcements/{ann_id}")
def toggle_announcement(ann_id: int, _=Depends(get_admin_user)):
    row = _q_one("SELECT is_active FROM announcements WHERE id = :id", {"id": ann_id})
    if not row:
        raise HTTPException(404, "Announcement not found.")
    new_state = not bool(row.get("is_active", True))
    with engine.begin() as conn:
        conn.execute(text("UPDATE announcements SET is_active = :s WHERE id = :id"), {"s": new_state, "id": ann_id})
    return {"success": True, "is_active": new_state}


@router.delete("/announcements/{ann_id}")
def delete_announcement(ann_id: int, _=Depends(get_admin_user)):
    with engine.begin() as conn:
        result = conn.execute(text("DELETE FROM announcements WHERE id = :id"), {"id": ann_id})
    if result.rowcount == 0:
        raise HTTPException(404, "Announcement not found.")
    return {"success": True}
