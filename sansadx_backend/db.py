"""
db.py — Single source of truth for all database connections and ORM models.
All other files import engine, SessionLocal, and models from here.
"""
import os
import bcrypt
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, ForeignKey, JSON
try:
    from sqlalchemy.orm import declarative_base
except ImportError:
    from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

# ─────────────────────────────────────────
# UNIFIED DATABASE CONNECTION
# ─────────────────────────────────────────
_ENV = os.getenv("ENV", "development").lower()
DATABASE_URL = os.getenv("DATABASE_URL", "")

if DATABASE_URL:
    # Fix Heroku/Railway postgres:// → postgresql://
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20, pool_recycle=300)
else:
    if _ENV == "production":
        raise RuntimeError("DATABASE_URL must be set in production; refusing to use SQLite fallback")
    # Local SQLite fallback (development only)
    engine = create_engine(
        "sqlite:///./sansadx.db",
        connect_args={"check_same_thread": False}
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ─────────────────────────────────────────
# PASSWORD HASHING UTILITIES
# ─────────────────────────────────────────
def hash_password(password: str) -> str:
    """Hash password using bcrypt. Always use this for new passwords."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against bcrypt hash. No plaintext fallback."""
    try:
        if password_hash.startswith("$2b$") or password_hash.startswith("$2a$"):
            return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    except Exception:
        pass
    return False


def validate_password(password: str) -> str | None:
    """Validate password against security policy. Returns error message or None if valid."""
    if len(password) < 8:
        return "Password must be at least 8 characters long"
    if not any(c.isupper() for c in password):
        return "Password must contain at least one uppercase letter"
    if not any(c.isdigit() for c in password):
        return "Password must contain at least one number"
    return None


# ─────────────────────────────────────────
# DEPENDENCY HELPER (for FastAPI routes)
# ─────────────────────────────────────────
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ─────────────────────────────────────────
# ORM MODELS
# ─────────────────────────────────────────
class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    constituency = Column(String)
    whatsapp_number = Column(String, unique=True)
    subscription_plan = Column(String, default="Pro")
    config = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship("User", back_populates="tenant")
    cases = relationship("Case", back_populates="tenant")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"))
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    role = Column(String, default="user")
    constituency = Column(String, default="India")
    house = Column(String, default="Lok Sabha")
    display_name = Column(String, nullable=True)
    last_login = Column(DateTime, nullable=True)

    tenant = relationship("Tenant", back_populates="users")


class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"))
    user_phone = Column(String, index=True)
    raw_message = Column(Text)
    category = Column(String, default="General")
    status = Column(String, default="new")
    location = Column(String, nullable=True)
    ward = Column(String, nullable=True)
    assembly = Column(String, nullable=True)
    is_critical = Column(Boolean, default=False)
    response_to_citizen = Column(Text, nullable=True)
    notes_for_staff = Column(Text, nullable=True)
    case_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    tenant = relationship("Tenant", back_populates="cases")


class TenantProfile(Base):
    """Per-tenant profile: constituency context, news keywords, drafter identity."""
    __tablename__ = "tenant_profiles"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), unique=True, index=True)
    mp_name = Column(String)
    constituency = Column(String)
    state = Column(String)
    house = Column(String, default="Lok Sabha")
    party = Column(String, default="Independent")
    profile_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", backref="profile")


class Archive(Base):
    """Stores saved drafts/archives for users."""
    __tablename__ = "archives"
    id = Column(Integer, primary_key=True, index=True)
    user = Column(String, index=True)
    date = Column(String)
    category = Column(String, default="General")
    title = Column(String)
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class LetterboxItem(Base):
    """Unified tracking for physical Inbox (grievances) and Outbox (official MP letters)."""
    __tablename__ = "letterbox"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), index=True)
    direction = Column(String, default="inbox")  # 'inbox' or 'outbox'
    citizen_name = Column(String, nullable=True)
    phone_number = Column(String, index=True, nullable=True)
    village = Column(String, nullable=True)
    issue_summary = Column(Text)
    urgency_level = Column(String, default="Normal")
    ocr_raw_text = Column(Text, nullable=True)
    status = Column(String, default="Pending-Intake") # 'Pending-Intake', 'Drafted', 'Sent'
    created_at = Column(DateTime, default=datetime.utcnow)
    
    tenant = relationship("Tenant", backref="letterbox_items")


class DNASample(Base):
    """Stores style templates (DNA samples) for users."""
    __tablename__ = "dna_samples"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True)
    title = Column(String)
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class ActivityHistory(Base):
    __tablename__ = "activity_history"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=False)
    username = Column(String(255), nullable=False)
    activity_type = Column(String(50), nullable=False)
    title = Column(String(500))
    content = Column(Text)
    extra_metadata = Column("metadata", Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class TenantOverride(Base):
    __tablename__ = "tenant_overrides"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), index=True)
    override_type = Column(String)   # "phone_mapping" or "geo_override"
    key = Column(String)             # phone number or location name
    value = Column(String)           # tenant_id or assembly constituency
    created_at = Column(DateTime, default=datetime.utcnow)


class SpamFlag(Base):
    """Tracks messages flagged by abuse or coordinated-flood detection."""
    __tablename__ = "spam_flags"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), index=True)
    phone = Column(String, index=True)
    flag_type = Column(String)          # 'abuse_keyword' | 'coordinated_flood'
    flag_reason = Column(Text)          # human-readable explanation
    message_preview = Column(String)    # first 120 chars of the raw message
    created_at = Column(DateTime, default=datetime.utcnow)


# ─────────────────────────────────────────
# TENANT OVERRIDE HELPERS
# ─────────────────────────────────────────
def get_phone_tenant_mapping() -> dict:
    """Return {phone_number: tenant_id} from DB overrides."""
    db = SessionLocal()
    try:
        rows = db.query(TenantOverride).filter(
            TenantOverride.override_type == "phone_mapping"
        ).all()
        return {r.key: int(r.value) for r in rows}
    finally:
        db.close()


def get_geo_overrides(tenant_id: int) -> dict:
    """Return {location_name: constituency} for a tenant."""
    db = SessionLocal()
    try:
        rows = db.query(TenantOverride).filter(
            TenantOverride.override_type == "geo_override",
            TenantOverride.tenant_id == tenant_id,
        ).all()
        return {r.key: r.value for r in rows}
    finally:
        db.close()


def get_all_overrides() -> dict:
    """Return full overrides dict matching the JSON format."""
    db = SessionLocal()
    try:
        result = {}
        geo_overrides = {}
        rows = db.query(TenantOverride).all()
        for r in rows:
            if r.override_type == "phone_mapping":
                result[r.key] = int(r.value)
            elif r.override_type == "geo_override":
                tid = str(r.tenant_id)
                if tid not in geo_overrides:
                    geo_overrides[tid] = {}
                geo_overrides[tid][r.key] = r.value
        if geo_overrides:
            result["geo_overrides"] = geo_overrides
        return result
    finally:
        db.close()


def save_overrides_to_db(data: dict):
    """Bulk replace all overrides from a dict matching JSON format."""
    db = SessionLocal()
    try:
        db.query(TenantOverride).delete()
        # Phone mappings (top-level keys that aren't "geo_overrides")
        for key, value in data.items():
            if key == "geo_overrides":
                continue
            db.add(TenantOverride(
                tenant_id=int(value) if isinstance(value, (int, str)) and str(value).isdigit() else 1,
                override_type="phone_mapping",
                key=key,
                value=str(value),
            ))
        # Geo overrides
        for tid_str, mappings in data.get("geo_overrides", {}).items():
            tid = int(tid_str)
            for loc, constituency in mappings.items():
                db.add(TenantOverride(
                    tenant_id=tid,
                    override_type="geo_override",
                    key=loc,
                    value=constituency,
                ))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ─────────────────────────────────────────
# INIT — Create all tables
# ─────────────────────────────────────────
def init_db():
    """Create all tables. Safe to call on every startup."""
    Base.metadata.create_all(bind=engine)