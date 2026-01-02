# sansadx_backend/db.py

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

# --- 1. FORCE THE PATH TO 'needle.db' ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "sql_app.db")  # <--- CHANGED FROM needle.db
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- MODELS (Keep exactly as they were) ---
class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    constituency = Column(String)
    whatsapp_number = Column(String, unique=True)
    config = Column(JSON, default={})
    
    users = relationship("User", back_populates="tenant")
    cases = relationship("Case", back_populates="tenant")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    role = Column(String, default="staff")
    tenant_id = Column(Integer, ForeignKey("tenants.id"))
    
    tenant = relationship("Tenant", back_populates="users")

class Case(Base):
    __tablename__ = "cases"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"))
    user_phone = Column(String, index=True)
    raw_message = Column(Text)
    category = Column(String, index=True)
    status = Column(String, default="new")
    response_to_citizen = Column(Text)
    notes_for_staff = Column(Text)
    case_metadata = Column(JSON, default={}) 
    created_at = Column(DateTime, default=datetime.utcnow)
    tenant = relationship("Tenant", back_populates="cases")

def init_db():
    Base.metadata.create_all(bind=engine)