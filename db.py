import os
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

# --- 1. CONNECT TO REAL CLOUD DATABASE ---
# We look for the Cloud URL first. If missing (Local), we use a temp sqlite file.
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    # Local fallback
    SQLALCHEMY_DATABASE_URL = "sqlite:///./sansadx.db"
    connect_args = {"check_same_thread": False}
else:
    # Cloud (Railway) Fix: Postgres URL must start with postgresql://
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URL = DATABASE_URL
    connect_args = {}

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# --- 2. TENANT (The MP/Client) ---
class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    party = Column(String)              # Added to match script
    constituency = Column(String)
    subscription_status = Column(String, default="active") # Changed to match script
    # Note: We keep these purely for compatibility if needed later, but script didn't use them:
    # whatsapp_number = Column(String, unique=True, nullable=True) 
    # config = Column(JSON, default={})  

    users = relationship("User", back_populates="tenant")
    # cases = relationship("Case", back_populates="tenant") # Commented out until Case model is fixed

# --- 3. USERS (The Staff) ---
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"))
    
    # 🟢 THE FIX: Match the Postgres Database exactly
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    full_name = Column(String)
    role = Column(String)
    
    tenant = relationship("Tenant", back_populates="users")

# --- 4. INIT FUNCTION ---
def init_db():
    # In production, we usually use migrations (Alembic), but this is fine for Pilot
    Base.metadata.create_all(bind=engine)