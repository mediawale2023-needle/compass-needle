"""
db.py — Single source of truth for all database connections and ORM models.
All other files import engine, SessionLocal, and models from here.
"""
import os
import json
import time
import bcrypt
import logging
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Date, Text, ForeignKey, JSON, Float, LargeBinary, text as sa_text, UniqueConstraint
try:
    from sqlalchemy.orm import declarative_base
except ImportError:
    from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

logger = logging.getLogger("needle.db")

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
    tenant_type = Column(String, default="mp")        # "mp" or "aspirant"
    account_stage = Column(String, default="elected")  # "aspirant" | "elected"
    seat_type = Column(String, default="mp")           # "mp" | "mla"
    config = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True)
    onboarding_state = Column(JSON, default=dict)   # {geography: bool, staff: bool, test_sent: bool, live: bool}
    created_at = Column(DateTime, default=datetime.utcnow)

    # Parliamentary data sync fields (18th Lok Sabha)
    parliament_member_id    = Column(String, nullable=True)   # Sansad.in / Lok Sabha member ID
    parliament_house        = Column(String, nullable=True)   # 'lok_sabha' | 'rajya_sabha'
    parliament_sync_enabled = Column(Boolean, default=True)
    parliament_last_synced  = Column(DateTime, nullable=True)
    parliament_sync_status  = Column(String, default="pending")  # pending|active|error|unmatched
    prs_profile_slug        = Column(String, nullable=True)       # PRS India profile slug (e.g. "atul-garg")

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
    phone = Column(String, nullable=True, index=True)
    display_name = Column(String, nullable=True)
    last_login = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    must_change_password = Column(Boolean, default=False)
    password_reset_by_admin_at = Column(DateTime, nullable=True)
    password_changed_at = Column(DateTime, nullable=True)
    force_password_reason = Column(String, nullable=True)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)

    tenant = relationship("Tenant", back_populates="users")


class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"))
    user_phone = Column(String, index=True)
    raw_message = Column(Text)
    category = Column(String, default="Infrastructure & Utilities")
    problem_domain = Column(String, nullable=True, index=True)
    problem_subdomain = Column(String, nullable=True)
    convergence_program_type = Column(String, nullable=True)
    status = Column(String, default="new")
    location = Column(String, nullable=True)
    ward = Column(String, nullable=True)
    assembly = Column(String, nullable=True)
    is_critical = Column(Boolean, default=False)
    response_to_citizen = Column(Text, nullable=True)
    notes_for_staff = Column(Text, nullable=True)
    assigned_to = Column(String, nullable=True)
    case_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(String, nullable=True)
    case_ref = Column(String, nullable=True, index=True)

    tenant = relationship("Tenant", back_populates="cases")


class CaseActivityLog(Base):
    __tablename__ = "case_activity_log"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"))
    case_id = Column(Integer, ForeignKey("cases.id"))
    username = Column(String)
    action = Column(String)
    old_value = Column(String, nullable=True)
    new_value = Column(String, nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class DashboardEngagement(Base):
    __tablename__ = "dashboard_engagements"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), index=True, nullable=False)
    entry_type = Column(String, nullable=False, default="schedule")  # schedule | note | calendar
    title = Column(String, nullable=False)
    notes = Column(Text, nullable=True)
    location = Column(String, nullable=True)
    scheduled_for = Column(Date, nullable=False)
    starts_at = Column(DateTime, nullable=True)
    ends_at = Column(DateTime, nullable=True)
    calendar_url = Column(String, nullable=True)
    is_all_day = Column(Boolean, default=False)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)

    tenant = relationship("Tenant")


class CaseMedia(Base):
    """Original WhatsApp source media attached to a citizen grievance."""
    __tablename__ = "case_media"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), index=True, nullable=False)
    case_id = Column(Integer, ForeignKey("cases.id"), index=True, nullable=False)
    source = Column(String, default="whatsapp")
    media_type = Column(String, nullable=False)
    mime_type = Column(String, nullable=False)
    file_name = Column(String, nullable=True)
    media_data = Column(LargeBinary, nullable=False)
    caption = Column(Text, nullable=True)
    extracted_text = Column(Text, nullable=True)
    meta_message_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant")
    case = relationship("Case")


class Officer(Base):
    __tablename__ = "officers"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"))
    name = Column(String)
    designation = Column(String)
    department = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    jurisdiction = Column(String, nullable=True)
    categories = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Escalation(Base):
    __tablename__ = "escalations"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"))
    case_id = Column(Integer, ForeignKey("cases.id"))
    officer_id = Column(Integer, ForeignKey("officers.id"))
    letter_content = Column(Text)
    email_sent = Column(Boolean, default=False)
    email_sent_at = Column(DateTime, nullable=True)
    email_message_id = Column(String, nullable=True)
    deadline = Column(DateTime, nullable=True)
    status = Column(String, default="sent")
    created_by = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True)


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


class SeatMapManifest(Base):
    """DB-backed seat map manifest registry for constituency dashboard maps."""
    __tablename__ = "seat_map_manifests"

    id = Column(Integer, primary_key=True, index=True)
    seat_key = Column(String, unique=True, index=True, nullable=False)
    seat_type = Column(String, index=True, nullable=False)
    seat_name = Column(String, index=True, nullable=False)
    state = Column(String, nullable=True)
    aliases = Column(JSON, default=list)
    asset = Column(JSON, default=dict)
    features = Column(JSON, default=list)
    fallback_anchors = Column(JSON, default=list)
    status = Column(String, default="draft")
    version = Column(Integer, default=1)
    source = Column(String, default="admin")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SeatBoundaryAsset(Base):
    """DB-backed boundary asset registry for real constituency geometry."""
    __tablename__ = "seat_boundary_assets"

    id = Column(Integer, primary_key=True, index=True)
    seat_key = Column(String, unique=True, index=True, nullable=False)
    seat_type = Column(String, index=True, nullable=False)
    seat_name = Column(String, index=True, nullable=False)
    state = Column(String, nullable=True)
    asset_type = Column(String, default="svg", nullable=False)
    asset_path = Column(String, nullable=True)
    inline_svg = Column(Text, nullable=True)
    geojson = Column(JSON, default=dict)
    metadata_json = Column(JSON, default=dict)
    status = Column(String, default="draft")
    source = Column(String, default="admin")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Archive(Base):
    """Stores saved drafts/archives for users."""
    __tablename__ = "archives"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), index=True, nullable=True)
    user = Column(String, index=True)
    date = Column(String)
    category = Column(String, default="General")
    title = Column(String)
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", backref="archives")

class TokenBlocklist(Base):
    """Revoked JWT tokens. Checked on every authenticated request."""
    __tablename__ = "token_blocklist"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True, nullable=False)
    revoked_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class LetterboxItem(Base):
    """Correspondence ledger for incoming and outgoing office letters."""
    __tablename__ = "letterbox"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), index=True)
    direction = Column(String, default="inbox", index=True)  # 'inbox' or 'outbox'
    image_data = Column(LargeBinary, nullable=True)
    image_mime = Column(String, nullable=True)
    citizen_name = Column(String, nullable=True)
    phone_number = Column(String, index=True, nullable=True)
    sender_phone = Column(String, nullable=True)
    village = Column(String, nullable=True)
    issue_summary = Column(Text)
    category = Column(String, default="General / Other")
    urgency_level = Column(String, default="Normal")
    ocr_text = Column(Text, nullable=True)
    ocr_raw_text = Column(Text, nullable=True)
    document_text = Column(Text, nullable=True)
    status = Column(String, default="new", index=True)
    diary_number = Column(String, nullable=True, unique=True)
    source = Column(String, default="upload", index=True)
    assigned_to = Column(String, nullable=True)
    date_of_letter = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    linked_letterbox_id = Column(Integer, ForeignKey("letterbox.id"), nullable=True)
    is_deleted = Column(Boolean, default=False, index=True)
    page_count = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    tenant = relationship("Tenant", backref="letterbox_items")
    linked_letterbox = relationship("LetterboxItem", remote_side=[id], uselist=False)


class LetterboxActivity(Base):
    """Immutable audit trail for Letterbox actions."""
    __tablename__ = "letterbox_activity_log"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), index=True, nullable=False)
    letterbox_id = Column(Integer, ForeignKey("letterbox.id"), index=True, nullable=False)
    action_type = Column(String(64), nullable=False, index=True)
    actor_username = Column(String(255), nullable=True)
    actor_channel = Column(String(64), nullable=False, default="system")
    summary = Column(String(500), nullable=True)
    details_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    tenant = relationship("Tenant")
    letterbox = relationship("LetterboxItem")


def log_letterbox_activity(
    tenant_id: int,
    letterbox_id: int,
    action_type: str,
    actor_username: str | None = None,
    actor_channel: str = "system",
    summary: str | None = None,
    details: dict | None = None,
    created_at: datetime | None = None,
) -> None:
    """Best-effort append-only Letterbox audit logging."""
    try:
        payload = json.dumps(details, ensure_ascii=True) if details else None
        with engine.begin() as conn:
            conn.execute(
                sa_text(
                    """
                    INSERT INTO letterbox_activity_log (
                        tenant_id, letterbox_id, action_type, actor_username,
                        actor_channel, summary, details_json, created_at
                    ) VALUES (
                        :tenant_id, :letterbox_id, :action_type, :actor_username,
                        :actor_channel, :summary, :details_json, :created_at
                    )
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "letterbox_id": letterbox_id,
                    "action_type": action_type,
                    "actor_username": actor_username,
                    "actor_channel": actor_channel,
                    "summary": summary,
                    "details_json": payload,
                    "created_at": created_at or datetime.utcnow(),
                },
            )
    except Exception:
        logger.exception("Failed to append letterbox activity log")


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


class ResearchSession(Base):
    __tablename__ = "research_sessions"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), index=True, nullable=False)
    username = Column(String(255), nullable=False)
    title = Column(String(255), nullable=True)
    latest_analysis = Column(Text, nullable=True)
    analysis_language = Column(String(32), nullable=True)
    analysis_depth = Column(String(32), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_activity_at = Column(DateTime, default=datetime.utcnow, index=True)


class ResearchDocument(Base):
    __tablename__ = "research_documents"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("research_sessions.id"), index=True, nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), index=True, nullable=False)
    filename = Column(String(255), nullable=False)
    page_count = Column(Integer, default=0)
    char_count = Column(Integer, default=0)
    content_text = Column(Text, nullable=False)
    pages_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ResearchMessage(Base):
    __tablename__ = "research_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("research_sessions.id"), index=True, nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), index=True, nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    citations = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class Contact(Base):
    """Constituent profile — one record per (tenant, phone) pair."""
    __tablename__ = "contacts"
    __table_args__ = (
        # Composite unique: each phone number can only have one contact record per tenant.
        # Two different MPs can both have the same constituent phone without collision.
        UniqueConstraint("tenant_id", "phone", name="uq_contacts_tenant_phone"),
    )
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), index=True)
    phone = Column(String, index=True)
    display_name = Column(String, nullable=True)
    tags = Column(Text, nullable=True)          # JSON-encoded list e.g. '["Ward Councillor"]'
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True)


class Announcement(Base):
    """System-wide banners composed by admin, shown to all MP dashboard users."""
    __tablename__ = "announcements"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    body = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class TenantOverride(Base):
    __tablename__ = "tenant_overrides"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), index=True)
    override_type = Column(String)   # e.g. "phone_mapping", "geo_override" (legacy), "geo_manual_override", "geo_alias", "geography_data"
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


class CSRCompany(Base):
    """Enriched corporate CSR profile — migrated from csr_db.json + csr_discovery.json."""
    __tablename__ = "csr_companies"

    id = Column(Integer, primary_key=True, index=True)
    # Identification
    name = Column(String, unique=True, nullable=False, index=True)
    slug = Column(String, unique=True, nullable=False, index=True)   # URL-safe key
    district = Column(String, index=True)
    state = Column(String, default="Maharashtra")
    # Classification
    company_type = Column(String)                 # 'local' | 'remote'
    sector = Column(String)                       # primary sector (normalised)
    sector_priorities = Column(Text)              # JSON-encoded list e.g. '["Education","Health"]'
    # Spending (all values in ₹ Lakhs)
    spend_2022_23 = Column(Float, nullable=True)
    spend_2023_24 = Column(Float, nullable=True)
    spend_2024_25 = Column(Float, nullable=True)
    total_3y_lakhs = Column(Float, nullable=True)
    avg_ticket_size_lakhs = Column(Float, nullable=True)
    # Compliance
    status = Column(String, default='active')     # active | zero_spend | compliant
    has_unspent_obligation = Column(Boolean, default=False)
    unspent_obligation_lakhs = Column(Float, nullable=True)  # NULL until MCA data available
    gap_analysis = Column(String, nullable=True)
    # Relationship tracking
    contact_person = Column(String, nullable=True)
    contact_email = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    # Metadata
    last_enriched_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)


class CSROpportunity(Base):
    """Auto-detected CSR opportunities from grievance clustering."""
    __tablename__ = "csr_opportunities"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), index=True)
    category = Column(String)
    location = Column(String)       # constituency name
    affected_areas = Column(Text, nullable=True)  # JSON: [{area, volume}, ...]
    complaint_count = Column(Integer, default=0)
    velocity_7d = Column(Integer, default=0)   # new complaints in last 7 days
    velocity_30d = Column(Integer, default=0)  # new complaints in last 30 days
    opportunity_score = Column(Float, default=0.0)  # composite 0–100
    status = Column(String, default='emerging')  # emerging | monitoring | ready | funded
    detected_at = Column(DateTime, default=datetime.utcnow)
    last_scored_at = Column(DateTime, nullable=True)

    tenant = relationship("Tenant", backref="csr_opportunities")


class CSRPipelineEntry(Base):
    """Tracks a company being pursued for CSR funding against an opportunity."""
    __tablename__ = "csr_pipeline_entries"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), index=True)
    opportunity_id = Column(Integer, ForeignKey("csr_opportunities.id"), nullable=True)
    company_name = Column(String, nullable=False)
    sector = Column(String, nullable=True)
    stage = Column(String, default='identified')  # identified | contacted | proposal_sent | negotiating | approved | funded
    opportunity_score = Column(Float, default=0.0)
    contact_person = Column(String, nullable=True)
    estimated_amount = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)

    tenant = relationship("Tenant", backref="csr_pipeline_entries")


# ─────────────────────────────────────────
# TENANT OVERRIDE HELPERS
# ─────────────────────────────────────────
# Inbound WhatsApp routing depends on the phone→tenant mapping. Re-reading it
# from the DB on every message is wasteful, but caching it forever means an
# admin's routing change is ignored until the process restarts (and different
# Railway instances can disagree for that whole window). A short TTL bounds the
# staleness to a few seconds while keeping the hot path cheap; writes invalidate
# the cache immediately for good measure.
_PHONE_MAP_TTL_SECONDS = 60
_phone_map_cache: dict | None = None
_phone_map_cached_at: float = 0.0


def invalidate_phone_tenant_mapping_cache() -> None:
    """Force the next get_phone_tenant_mapping() call to re-read from the DB."""
    global _phone_map_cache, _phone_map_cached_at
    _phone_map_cache = None
    _phone_map_cached_at = 0.0


def get_phone_tenant_mapping() -> dict:
    """Return {phone_number: tenant_id} from DB overrides (TTL-cached)."""
    global _phone_map_cache, _phone_map_cached_at
    now = time.monotonic()
    if _phone_map_cache is not None and (now - _phone_map_cached_at) < _PHONE_MAP_TTL_SECONDS:
        return _phone_map_cache
    db = SessionLocal()
    try:
        rows = db.query(TenantOverride).filter(
            TenantOverride.override_type == "phone_mapping"
        ).all()
        mapping = {r.key: int(r.value) for r in rows}
        _phone_map_cache = mapping
        _phone_map_cached_at = now
        return mapping
    finally:
        db.close()


def get_tenant_phone_number_id(tenant_id: int) -> str | None:
    """Return the Meta Phone Number ID for a tenant, or None if not set.

    The ID is stored in tenants.config->>'meta_phone_number_id' and is set
    via the PATCH /admin/mps/{id}/whatsapp endpoint.  Falls back to None so
    callers can degrade to the global WHATSAPP_PHONE_NUMBER_ID env var.
    """
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            return None
        config = tenant.config or {}
        return config.get("meta_phone_number_id") or None
    finally:
        db.close()


def get_geo_overrides(tenant_id: int) -> dict:
    """Return manual {location_name: constituency} corrections for a tenant."""
    db = SessionLocal()
    try:
        rows = db.query(TenantOverride).filter(
            TenantOverride.override_type.in_(["geo_manual_override", "geo_override"]),
            TenantOverride.tenant_id == tenant_id,
        ).all()
        overrides = {}
        for row in rows:
            key = str(row.key or "").strip()
            overrides[key] = row.value
        return overrides
    finally:
        db.close()


def get_tenant_constituency(tenant_id: int) -> str | None:
    """Return a tenant's parliamentary constituency, if known."""
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        return tenant.constituency if tenant and tenant.constituency else None
    finally:
        db.close()


def derive_account_stage(tenant, house: str | None = None) -> str:
    stage = getattr(tenant, "account_stage", None) if tenant is not None else None
    if stage in {"aspirant", "elected"}:
        return stage
    tenant_type = (getattr(tenant, "tenant_type", None) or "").strip().lower() if tenant is not None else ""
    if tenant_type == "aspirant":
        return "aspirant"
    return "elected"


def derive_seat_type(tenant, house: str | None = None) -> str:
    seat_type = getattr(tenant, "seat_type", None) if tenant is not None else None
    if seat_type in {"mp", "mla"}:
        return seat_type
    tenant_type = (getattr(tenant, "tenant_type", None) or "").strip().lower() if tenant is not None else ""
    effective_house = (house or "").strip().lower()
    if tenant_type == "mla" or effective_house == "vidhan sabha":
        return "mla"
    return "mp"


def seat_label(seat_type: str | None) -> str:
    return "MLA" if (seat_type or "").strip().lower() == "mla" else "MP"


def build_seat_key(seat_type: str | None, seat_name: str | None) -> str:
    clean_type = "mla" if (seat_type or "").strip().lower() == "mla" else "mp"
    clean_name = (seat_name or "").strip()
    return f"{clean_type}:{clean_name}"


def build_geography_key(seat_type: str | None, seat_name: str | None, assembly_name: str | None) -> str:
    return f"{build_seat_key(seat_type, seat_name)}/{(assembly_name or '').strip()}"


def parse_geography_key(key: str | None) -> tuple[str | None, str | None, str | None]:
    raw = (key or "").strip()
    if "/" not in raw:
        return None, None, None
    seat_part, assembly_name = raw.split("/", 1)
    if ":" in seat_part:
        seat_type, seat_name = seat_part.split(":", 1)
        return (seat_type or "mp").strip().lower(), seat_name.strip(), assembly_name.strip()
    # Backward compatibility: old keys were "<Constituency>/<Assembly>" and implied MP seat geography.
    return "mp", seat_part.strip(), assembly_name.strip()


def get_geography_data(
    tenant_id: int | None = None,
    parliamentary_constituency: str | None = None,
    seat_type: str | None = None,
    seat_name: str | None = None,
) -> dict[str, list[dict]]:
    """Return {assembly_name: [station, ...]} geography rows stored in DB.

    Geography data is persisted in tenant_overrides as override_type='geography_data'
    with keys in the format "<Parliamentary Constituency>/<Assembly>".
    """
    db = SessionLocal()
    try:
        query = db.query(TenantOverride).filter(
            TenantOverride.override_type == "geography_data"
        )
        if tenant_id is not None:
            tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
            if tenant:
                seat_type = seat_type or derive_seat_type(tenant)
                seat_name = seat_name or tenant.constituency
            # Prefer shared seat geography; allow legacy tenant-bound rows as fallback.

        assemblies: dict[str, list[dict]] = {}
        for row in query.all():
            row_seat_type, row_seat_name, assembly_name = parse_geography_key(row.key)
            if not row_seat_name or not assembly_name:
                continue
            if parliamentary_constituency and row_seat_name.lower() != parliamentary_constituency.lower():
                continue
            if seat_type and row_seat_type != seat_type:
                continue
            if seat_name and row_seat_name.lower() != seat_name.lower():
                continue
            try:
                payload = json.loads(row.value) if isinstance(row.value, str) else row.value
            except Exception:
                continue
            if isinstance(payload, list):
                assemblies[assembly_name] = payload
        return assemblies
    finally:
        db.close()


def get_all_geography_data() -> list[dict]:
    """Return all persisted geography rows with parsed payloads."""
    db = SessionLocal()
    try:
        rows = db.query(TenantOverride).filter(
            TenantOverride.override_type == "geography_data"
        ).all()
        result: list[dict] = []
        for row in rows:
            row_seat_type, row_seat_name, assembly_name = parse_geography_key(row.key)
            if not row_seat_name or not assembly_name:
                continue
            try:
                payload = json.loads(row.value) if isinstance(row.value, str) else row.value
            except Exception:
                continue
            if not isinstance(payload, list):
                continue
            result.append(
                {
                    "tenant_id": row.tenant_id,
                    "seat_type": row_seat_type or "mp",
                    "seat_name": row_seat_name,
                    "parliamentary_constituency": row_seat_name,
                    "assembly": assembly_name,
                    "stations": payload,
                }
            )
        return result
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
            elif r.override_type in ("geo_manual_override", "geo_override"):
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
    """Bulk replace phone mappings and manual geo corrections without touching shared geography."""
    db = SessionLocal()
    try:
        db.query(TenantOverride).filter(
            TenantOverride.override_type.in_(["phone_mapping", "geo_override", "geo_manual_override"])
        ).delete(synchronize_session=False)
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
                    override_type="geo_manual_override",
                    key=loc,
                    value=constituency,
                ))
        db.commit()
        invalidate_phone_tenant_mapping_cache()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def cleanup_legacy_generated_geo_overrides() -> dict:
    """Delete stale legacy geo_override rows that duplicate generated alias keys.

    These rows were historically produced from shared geography generation and
    can keep forcing wrong matches even after alias logic is corrected. Manual
    corrections now live in `geo_manual_override`, so any `geo_override` row
    that shares the same tenant/key as a generated `geo_alias` is safe to drop.
    """
    db = SessionLocal()
    try:
        alias_rows = db.query(TenantOverride).filter(
            TenantOverride.override_type == "geo_alias"
        ).all()
        alias_pairs = {
            (row.tenant_id, str(row.key or "").strip())
            for row in alias_rows
            if row.tenant_id is not None and str(row.key or "").strip()
        }
        if not alias_pairs:
            return {"deleted": 0, "tenants": 0}

        legacy_rows = db.query(TenantOverride).filter(
            TenantOverride.override_type == "geo_override"
        ).all()
        deleted = 0
        touched_tenants: set[int] = set()
        for row in legacy_rows:
            key = str(row.key or "").strip()
            pair = (row.tenant_id, key)
            if row.tenant_id is None or not key:
                continue
            if pair in alias_pairs:
                db.delete(row)
                deleted += 1
                touched_tenants.add(int(row.tenant_id))
        if deleted:
            db.commit()
        else:
            db.rollback()
        return {"deleted": deleted, "tenants": len(touched_tenants)}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def purge_generated_geo_aliases(tenant_id: int | None = None) -> dict:
    """Delete deprecated generated geo_alias rows.

    Generated aliases are no longer a supported runtime layer. This helper can
    wipe them globally or for one tenant without touching shared geography or
    manual corrections.
    """
    db = SessionLocal()
    try:
        query = db.query(TenantOverride).filter(TenantOverride.override_type == "geo_alias")
        if tenant_id is not None:
            query = query.filter(TenantOverride.tenant_id == tenant_id)
        rows = query.all()
        touched_tenants = {
            int(row.tenant_id)
            for row in rows
            if row.tenant_id is not None
        }
        deleted = len(rows)
        for row in rows:
            db.delete(row)
        if deleted:
            db.commit()
        else:
            db.rollback()
        return {"deleted": deleted, "tenants": len(touched_tenants)}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def wipe_all_geography_data() -> dict:
    """Delete all shared geography rows and tenant-scoped geography helpers.

    This removes:
    - shared `geography_data`
    - manual corrections (`geo_manual_override`)
    - legacy manual/generated overrides (`geo_override`)
    - deprecated generated aliases (`geo_alias`)
    """
    db = SessionLocal()
    try:
        rows = db.query(TenantOverride).filter(
            TenantOverride.override_type.in_([
                "geography_data",
                "geo_manual_override",
                "geo_override",
                "geo_alias",
            ])
        ).all()
        counts = {
            "geography_data": 0,
            "geo_manual_override": 0,
            "geo_override": 0,
            "geo_alias": 0,
        }
        for row in rows:
            counts[row.override_type] = counts.get(row.override_type, 0) + 1
            db.delete(row)
        if rows:
            db.commit()
        else:
            db.rollback()
        counts["deleted_total"] = len(rows)
        return counts
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def run_one_time_geography_reset(reset_key: str) -> dict:
    """Run a destructive geography reset exactly once for a given migration key."""
    db = SessionLocal()
    try:
        existing = db.query(TenantOverride).filter(
            TenantOverride.override_type == "system_migration",
            TenantOverride.key == reset_key,
        ).first()
        if existing:
            return {"applied": False, "reason": "already_applied"}

        rows = db.query(TenantOverride).filter(
            TenantOverride.override_type.in_([
                "geography_data",
                "geo_manual_override",
                "geo_override",
                "geo_alias",
            ])
        ).all()
        summary = {
            "geography_data": 0,
            "geo_manual_override": 0,
            "geo_override": 0,
            "geo_alias": 0,
            "deleted_total": len(rows),
        }
        for row in rows:
            summary[row.override_type] = summary.get(row.override_type, 0) + 1
            db.delete(row)
        db.add(TenantOverride(
            tenant_id=None,
            override_type="system_migration",
            key=reset_key,
            value=json.dumps(summary),
        ))
        db.commit()
        return {"applied": True, "summary": summary}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


class OpportunityCompanyMatch(Base):
    """
    Multi-dimensional match score between a grievance opportunity and a CSR company.
    Computed by the matching engine and stored for fast retrieval.
    """
    __tablename__ = "opportunity_company_matches"

    id = Column(Integer, primary_key=True, index=True)
    opportunity_id = Column(Integer, ForeignKey("csr_opportunities.id"), index=True)
    company_id = Column(Integer, ForeignKey("csr_companies.id"), index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), index=True)

    # Composite score (0–100)
    match_score = Column(Float, default=0.0)

    # Sub-dimension scores (each 0–100)
    sector_alignment_score = Column(Float, default=0.0)   # sector tag overlap
    geographic_score = Column(Float, default=0.0)          # same district / region
    urgency_score = Column(Float, default=0.0)             # velocity × complaint count
    relationship_score = Column(Float, default=0.0)        # existing pipeline entries, prior contact

    # Recommended engagement
    recommended_ask_amount = Column(Float, nullable=True)  # ₹ Lakhs
    ask_rationale = Column(Text, nullable=True)

    computed_at = Column(DateTime, default=datetime.utcnow)

    opportunity = relationship("CSROpportunity", backref="company_matches")
    company = relationship("CSRCompany", backref="opportunity_matches")


class CSRDocument(Base):
    """
    Document registry for RAG — stores CSR reports, policies, annual reports.
    Embeddings are stored externally (pgvector or file-based); this table tracks metadata.
    """
    __tablename__ = "csr_documents"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("csr_companies.id"), nullable=True, index=True)
    document_type = Column(String)   # csr_report | annual_report | policy | news | project_report
    title = Column(String, nullable=False)
    source_url = Column(String, nullable=True)
    fiscal_year = Column(String, nullable=True)    # e.g. "2024-25"
    raw_text = Column(Text, nullable=True)         # extracted text (truncated to 50K chars)
    summary = Column(Text, nullable=True)          # AI-generated summary
    key_sectors = Column(Text, nullable=True)      # JSON list extracted from doc
    total_csr_spend_mentioned = Column(Float, nullable=True)  # ₹ Lakhs if found in doc
    embedding_id = Column(String, nullable=True)   # external vector DB reference
    ingested_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("CSRCompany", backref="documents")


class AdminAuditLog(Base):
    """Append-only audit trail for all admin/editor actions."""
    __tablename__ = "admin_audit_log"
    id = Column(Integer, primary_key=True, index=True)
    admin_username = Column(String, nullable=False, index=True)
    action = Column(String, nullable=False, index=True)       # created, updated, deleted, suspended, etc.
    target_type = Column(String, nullable=False, index=True)   # mp, staff, geography, announcement, editor, etc.
    target_name = Column(String, nullable=True)                # human-readable target identifier
    change_summary = Column(Text, nullable=True)               # e.g. "constituency: 'Belagavi' → 'Belgaum'"
    created_at = Column(DateTime, default=datetime.utcnow)


class AdminNote(Base):
    """Append-only admin notes per tenant (MP/PR)."""
    __tablename__ = "admin_notes"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), index=True)
    admin_username = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class IncidentCluster(Base):
    """
    Rolling incident window for emergency surge detection.

    Each cluster represents a group of emergency reports that share the same
    hazard type and geographic area within a configurable time window.
    Alert levels: t0 (silent) → t1 (WhatsApp) → t2 (call+WA) → t3 (escalate).
    """
    __tablename__ = "incident_clusters"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), index=True)
    hazard_type = Column(String)                         # fire/flood/violence/medical/stampede/accident/missing/emergency
    assembly = Column(String)                            # assembly constituency (cluster geo key)
    ward = Column(String, nullable=True)                 # ward if available (finer key)
    window_start = Column(DateTime)                      # when first report arrived
    unique_sender_count = Column(Integer, default=1)     # deduplicated sender count
    raw_case_ids = Column(JSON, default=list)            # list of Case IDs in this cluster
    fingerprint_hashes = Column(JSON, default=list)      # normalised text hashes for forward dedup
    sender_events = Column(JSON, default=list)           # [{phone, ts}] — one entry per unique sender
    alert_level = Column(String, default="t0")           # t0 / t1 / t2 / t3 / unacknowledged
    alert_acknowledged = Column(Boolean, default=False)  # PA confirmed via WhatsApp reply
    last_alert_at = Column(DateTime, nullable=True)      # when last PA alert was sent
    call_attempt_count = Column(Integer, default=0)      # number of Exotel call attempts
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WAMessageDedup(Base):
    """
    Indexed deduplication table for Meta WhatsApp webhook message IDs.

    Replaces the `case_metadata::text LIKE '%msg_id%'` full-table-scan dedup
    with a primary-key lookup (sub-millisecond at any scale).

    Pruned on startup: entries older than 30 days are deleted (Meta never
    retries messages older than a few hours, so 30 days is very conservative).
    """
    __tablename__ = "wa_message_dedup"
    message_id = Column(String, primary_key=True, nullable=False)
    processed_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


# ─────────────────────────────────────────
# PARLIAMENTARY DATA MODELS (18th Lok Sabha)
# ─────────────────────────────────────────

class ParliamentaryQuestion(Base):
    """Questions asked by the MP in Lok Sabha / Rajya Sabha, scraped from sansad.in."""
    __tablename__ = "parliamentary_questions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "session_name", "question_number", "question_type",
                         name="uq_pq_tenant_session_number_type"),
    )
    id              = Column(Integer, primary_key=True, index=True)
    tenant_id       = Column(Integer, ForeignKey("tenants.id"), index=True, nullable=False)
    house           = Column(String, nullable=False)              # lok_sabha | rajya_sabha
    session_name    = Column(String, nullable=False)              # e.g. "Budget Session 2025"
    session_number  = Column(String, nullable=True)               # e.g. "4" (4th session of 18th LS)
    question_number = Column(String, nullable=False)
    question_type   = Column(String, nullable=False)              # starred | unstarred | short_notice
    subject         = Column(String, nullable=True)
    ministry        = Column(String, nullable=True)
    question_text   = Column(Text, nullable=True)
    answer_text     = Column(Text, nullable=True)
    date_asked      = Column(Date, nullable=True)
    scraped_at      = Column(DateTime, default=datetime.utcnow)


class ParliamentaryDebate(Base):
    """Speeches / debate participations by the MP, scraped from sansad.in."""
    __tablename__ = "parliamentary_debates"
    __table_args__ = (
        UniqueConstraint("tenant_id", "session_name", "date", "topic",
                         name="uq_pd_tenant_session_date_topic"),
    )
    id             = Column(Integer, primary_key=True, index=True)
    tenant_id      = Column(Integer, ForeignKey("tenants.id"), index=True, nullable=False)
    house          = Column(String, nullable=False)
    session_name   = Column(String, nullable=False)
    date           = Column(Date, nullable=True)
    topic          = Column(String, nullable=True)
    bill_reference = Column(String, nullable=True)               # bill number if debate was on a bill
    speech_excerpt = Column(Text, nullable=True)                 # first ~500 chars of speech
    full_speech_url = Column(String, nullable=True)
    scraped_at     = Column(DateTime, default=datetime.utcnow)


class PrivateMembersBill(Base):
    """Private Members' Bills introduced by the MP."""
    __tablename__ = "private_members_bills"
    __table_args__ = (
        UniqueConstraint("tenant_id", "session_name", "bill_number",
                         name="uq_pmb_tenant_session_bill"),
    )
    id              = Column(Integer, primary_key=True, index=True)
    tenant_id       = Column(Integer, ForeignKey("tenants.id"), index=True, nullable=False)
    house           = Column(String, nullable=False)
    session_name    = Column(String, nullable=False)
    bill_number     = Column(String, nullable=False)
    title           = Column(String, nullable=True)
    subject         = Column(Text, nullable=True)
    date_introduced = Column(Date, nullable=True)
    current_status  = Column(String, nullable=True)              # introduced | lapsed | withdrawn | passed
    bill_text_url   = Column(String, nullable=True)
    scraped_at      = Column(DateTime, default=datetime.utcnow)


class ZeroHourSubmission(Base):
    """Zero Hour / Special Mentions raised by the MP."""
    __tablename__ = "zero_hour_submissions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "session_name", "date", "subject",
                         name="uq_zh_tenant_session_date_subject"),
    )
    id           = Column(Integer, primary_key=True, index=True)
    tenant_id    = Column(Integer, ForeignKey("tenants.id"), index=True, nullable=False)
    house        = Column(String, nullable=False)
    session_name = Column(String, nullable=False)
    date         = Column(Date, nullable=True)
    subject      = Column(String, nullable=True)
    text_excerpt = Column(Text, nullable=True)
    scraped_at   = Column(DateTime, default=datetime.utcnow)


class WAOutboundMessage(Base):
    """Persistent audit log for outbound WhatsApp sends and retries."""
    __tablename__ = "wa_outbound_messages"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), index=True, nullable=True)
    case_id = Column(Integer, ForeignKey("cases.id"), index=True, nullable=True)
    to_number = Column(String, index=True, nullable=False)
    phone_number_id = Column(String, nullable=True)
    message_body = Column(Text, nullable=False)
    template_key = Column(String, nullable=True)
    initiated_by = Column(String, nullable=True)
    initiated_via = Column(String, nullable=True)
    status = Column(String, default="pending", index=True)  # pending|sent|failed|retrying
    attempt_count = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    meta_message_id = Column(String, nullable=True)
    request_payload = Column(JSON, default=dict)
    meta_response = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    last_attempt_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)


class ParliamentBackfillJob(Base):
    """Tracks per-tenant per-session backfill progress for the 6-session historical import."""
    __tablename__ = "parliament_backfill_jobs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "session_name", "data_type",
                         name="uq_pbj_tenant_session_type"),
    )
    id              = Column(Integer, primary_key=True, index=True)
    tenant_id       = Column(Integer, ForeignKey("tenants.id"), index=True, nullable=False)
    session_name    = Column(String, nullable=False)             # e.g. "Budget Session 2025"
    data_type       = Column(String, nullable=False)             # questions|debates|pmbs|zero_hour
    status          = Column(String, default="pending")          # pending|running|done|error
    records_fetched = Column(Integer, default=0)
    error_message   = Column(Text, nullable=True)
    started_at      = Column(DateTime, nullable=True)
    completed_at    = Column(DateTime, nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)


# ─────────────────────────────────────────
# INIT — Create all tables
# ─────────────────────────────────────────
def init_db():
    """Create all tables and run additive column migrations. Safe to call on every startup."""
    import logging
    Base.metadata.create_all(bind=engine)

    # Additive migrations — safe to run repeatedly (IF NOT EXISTS / DO NOTHING)
    _migrations = [
        # incident_clusters: additive columns (table created by create_all above)
        "ALTER TABLE incident_clusters ADD COLUMN IF NOT EXISTS call_attempt_count INTEGER DEFAULT 0",
        "ALTER TABLE incident_clusters ADD COLUMN IF NOT EXISTS alert_acknowledged BOOLEAN DEFAULT FALSE",
        "ALTER TABLE incident_clusters ADD COLUMN IF NOT EXISTS last_alert_at TIMESTAMP",
        "ALTER TABLE incident_clusters ADD COLUMN IF NOT EXISTS sender_events JSONB DEFAULT '[]'",
        # Added for AI classification metadata and criticality flag
        "ALTER TABLE cases ADD COLUMN IF NOT EXISTS is_critical BOOLEAN DEFAULT FALSE",
        "ALTER TABLE cases ADD COLUMN IF NOT EXISTS case_metadata JSONB",
        "ALTER TABLE cases ADD COLUMN IF NOT EXISTS problem_domain VARCHAR",
        "ALTER TABLE cases ADD COLUMN IF NOT EXISTS problem_subdomain VARCHAR",
        "ALTER TABLE cases ADD COLUMN IF NOT EXISTS convergence_program_type VARCHAR",
        # Added for soft-delete support
        "ALTER TABLE cases ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE",
        "ALTER TABLE cases ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP",
        "ALTER TABLE cases ADD COLUMN IF NOT EXISTS deleted_by VARCHAR",
        # Added for case reference numbers
        "ALTER TABLE cases ADD COLUMN IF NOT EXISTS case_ref VARCHAR",
        # Added for geography fields (assembly constituency and ward)
        "ALTER TABLE cases ADD COLUMN IF NOT EXISTS assembly VARCHAR",
        "ALTER TABLE cases ADD COLUMN IF NOT EXISTS ward VARCHAR",
        # Added for case assignment and staff notes
        "ALTER TABLE cases ADD COLUMN IF NOT EXISTS assigned_to VARCHAR",
        "ALTER TABLE cases ADD COLUMN IF NOT EXISTS notes_for_staff TEXT",
        "ALTER TABLE cases ADD COLUMN IF NOT EXISTS response_to_citizen TEXT",
        "ALTER TABLE cases ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMP",
        # Parliamentary sync fields on tenants (18th Lok Sabha integration)
        "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS parliament_member_id VARCHAR",
        "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS parliament_house VARCHAR DEFAULT 'lok_sabha'",
        "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS parliament_sync_enabled BOOLEAN DEFAULT TRUE",
        "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS parliament_last_synced TIMESTAMP",
        "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS parliament_sync_status VARCHAR DEFAULT 'pending'",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN DEFAULT FALSE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS password_reset_by_admin_at TIMESTAMP",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS password_changed_at TIMESTAMP",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS force_password_reason VARCHAR",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS failed_login_attempts INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS locked_until TIMESTAMP",
        "ALTER TABLE dashboard_engagements ADD COLUMN IF NOT EXISTS notes TEXT",
        "ALTER TABLE dashboard_engagements ADD COLUMN IF NOT EXISTS location VARCHAR",
        "ALTER TABLE dashboard_engagements ADD COLUMN IF NOT EXISTS scheduled_for DATE",
        "ALTER TABLE dashboard_engagements ADD COLUMN IF NOT EXISTS starts_at TIMESTAMP",
        "ALTER TABLE dashboard_engagements ADD COLUMN IF NOT EXISTS ends_at TIMESTAMP",
        "ALTER TABLE dashboard_engagements ADD COLUMN IF NOT EXISTS calendar_url VARCHAR",
        "ALTER TABLE dashboard_engagements ADD COLUMN IF NOT EXISTS is_all_day BOOLEAN DEFAULT FALSE",
        "ALTER TABLE dashboard_engagements ADD COLUMN IF NOT EXISTS created_by VARCHAR",
        "ALTER TABLE dashboard_engagements ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP",
    ]
    with engine.connect() as conn:
        for stmt in _migrations:
            try:
                conn.execute(sa_text(stmt))
            except Exception as e:
                logging.warning("Migration skipped (%s): %s", stmt[:60], e)
        conn.commit()

    try:
        updated = backfill_case_taxonomy_fields()
        logging.info("Case taxonomy backfill verified (rows updated: %d)", updated)
    except Exception as e:
        logging.warning("Case taxonomy backfill skipped: %s", e)


def _parse_case_metadata_value(meta):
    if meta is None:
        return {}
    if isinstance(meta, dict):
        return dict(meta)
    try:
        return json.loads(meta)
    except Exception:
        return {}


def derive_case_taxonomy_state(
    *,
    category=None,
    raw_message="",
    status="",
    case_metadata=None,
    problem_domain=None,
    problem_subdomain=None,
    convergence_program_type=None,
):
    """
    Build canonical taxonomy fields and merged metadata for a case row.

    This powers the startup backfill and keeps historical rows aligned with the
    authoritative 3-layer taxonomy without needing DB-specific JSON SQL.
    """
    from sansadx_backend.unified_taxonomy import build_taxonomy_fields

    meta = _parse_case_metadata_value(case_metadata)
    lowered_status = str(status or "").lower().strip()

    if lowered_status in ("offensive", "irrelevant"):
        merged_meta = dict(meta)
        merged_meta["categories"] = []
        merged_meta["problem_domain"] = None
        merged_meta["problem_subdomain"] = None
        merged_meta["convergence_program_type"] = None
        return {
            "category": category if category not in (None, "General", "General Grievance") else "Uncategorised",
            "problem_domain": None,
            "problem_subdomain": None,
            "convergence_program_type": None,
            "case_metadata": merged_meta,
        }

    fields = build_taxonomy_fields(
        problem_domain=meta.get("problem_domain") or problem_domain or category,
        problem_subdomain=meta.get("problem_subdomain") or problem_subdomain,
        convergence_program_type=meta.get("convergence_program_type") or convergence_program_type,
        raw_text=raw_message or meta.get("summary", ""),
        scheme=meta.get("scheme"),
        department=meta.get("department"),
    )
    merged_meta = dict(meta)
    merged_meta.update(fields)
    return {
        "category": fields["problem_domain"],
        "problem_domain": fields["problem_domain"],
        "problem_subdomain": fields["problem_subdomain"],
        "convergence_program_type": fields["convergence_program_type"],
        "case_metadata": merged_meta,
    }


def backfill_case_taxonomy_fields(batch_size: int = 500) -> int:
    """
    Idempotently populate canonical taxonomy fields for historical case rows.
    """
    total_updated = 0

    while True:
        with engine.begin() as conn:
            rows = conn.execute(
                sa_text(
                    """
                    SELECT id, category, raw_message, status, case_metadata,
                           problem_domain, problem_subdomain, convergence_program_type
                    FROM cases
                    WHERE (
                            LOWER(COALESCE(status, '')) IN ('offensive', 'irrelevant')
                            AND (
                                category IS NULL
                                OR category IN ('General', 'General Grievance')
                            )
                        ) OR (
                            LOWER(COALESCE(status, '')) NOT IN ('offensive', 'irrelevant')
                            AND (
                                problem_domain IS NULL
                                OR problem_subdomain IS NULL
                                OR convergence_program_type IS NULL
                                OR category IS NULL
                                OR category IN ('General', 'General Grievance', 'Uncategorised')
                            )
                        )
                    ORDER BY id
                    LIMIT :lim
                    """
                ),
                {"lim": batch_size},
            ).mappings().all()

            if not rows:
                break

            for row in rows:
                payload = derive_case_taxonomy_state(
                    category=row.get("category"),
                    raw_message=row.get("raw_message") or "",
                    status=row.get("status") or "",
                    case_metadata=row.get("case_metadata"),
                    problem_domain=row.get("problem_domain"),
                    problem_subdomain=row.get("problem_subdomain"),
                    convergence_program_type=row.get("convergence_program_type"),
                )
                conn.execute(
                    sa_text(
                        """
                        UPDATE cases
                        SET category = :category,
                            problem_domain = :problem_domain,
                            problem_subdomain = :problem_subdomain,
                            convergence_program_type = :convergence_program_type,
                            case_metadata = :case_metadata
                        WHERE id = :id
                        """
                    ),
                    {
                        "id": row["id"],
                        "category": payload["category"],
                        "problem_domain": payload["problem_domain"],
                        "problem_subdomain": payload["problem_subdomain"],
                        "convergence_program_type": payload["convergence_program_type"],
                        "case_metadata": json.dumps(payload["case_metadata"]),
                    },
                )
                total_updated += 1

            if len(rows) < batch_size:
                break

    return total_updated
