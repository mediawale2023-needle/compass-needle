import os
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

# --- 1. SMART CONNECTION (Local vs Cloud) ---
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # CLOUD MODE (Railway)
    # Postgres requires 'postgresql://' (Railway provides 'postgres://')
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    
    SQLALCHEMY_DATABASE_URL = DATABASE_URL
    connect_args = {}
else:
    # LOCAL MODE (MacBook)
    SQLALCHEMY_DATABASE_URL = "sqlite:///./sansadx.db"
    connect_args = {"check_same_thread": False}

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# --- 2. MODELS (EXACTLY AS REVERTED) ---

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
    username = Column(String, unique=True, index=True) # We will store email here
    password_hash = Column(String)
    role = Column(String)
    
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
    is_critical = Column(Boolean, default=False)
    response_to_citizen = Column(Text, nullable=True)
    notes_for_staff = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    tenant = relationship("Tenant", back_populates="cases")

def init_db():
    Base.metadata.create_all(bind=engine)