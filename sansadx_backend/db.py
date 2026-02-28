"""
db.py — Single source of truth for all database connections and ORM models.
All other files import engine, SessionLocal, and models from here.
"""
import os
import bcrypt
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

# ─────────────────────────────────────────
# UNIFIED DATABASE CONNECTION
# ─────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "")

if DATABASE_URL:
    # Fix Heroku/Railway postgres:// → postgresql://
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20, pool_recycle=300)
else:
    # Local SQLite fallback
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
    config = Column(JSON, default={})
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
    profile_data = Column(JSON, default={})
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


# ─────────────────────────────────────────
# INIT — Create all tables
# ─────────────────────────────────────────
def init_db():
    """Create all tables. Safe to call on every startup."""
    Base.metadata.create_all(bind=engine)