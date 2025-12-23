from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

# Database URL
SQLALCHEMY_DATABASE_URL = "sqlite:///./sansadx.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# --- 1. TENANT (The MP/Client) ---
class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)               # "Hon. Milind Deora"
    constituency = Column(String)       # "Mumbai South"
    whatsapp_number = Column(String, unique=True)    # The key to routing
    subscription_plan = Column(String, default="Pro")
    
    # 🧠 THE BRAIN: Dynamic Config
    # Stores: {"talukas": ["Colaba", "Worli"], "map_coords": {...}, "language": "Marathi"}
    config = Column(JSON, default={})  
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    users = relationship("User", back_populates="tenant")
    cases = relationship("Case", back_populates="tenant")

# --- 2. USERS (The Staff) ---
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"))
    
    username = Column(String, unique=True, index=True) # rahul@office
    password_hash = Column(String) # For now, plain text (we upgrade later)
    role = Column(String) # "admin", "staff", "viewer"
    
    tenant = relationship("Tenant", back_populates="users")

# --- 3. CASES (Grievances) ---
class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id")) # Partition key
    
    user_phone = Column(String, index=True)
    raw_message = Column(Text)
    
    category = Column(String, default="General")
    status = Column(String, default="new")
    
    # Classification
    location = Column(String, nullable=True)
    ward = Column(String, nullable=True) # Taluka/Constituency
    
    is_critical = Column(Boolean, default=False)
    
    # AI Response
    response_to_citizen = Column(Text, nullable=True)
    notes_for_staff = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    tenant = relationship("Tenant", back_populates="cases")

def init_db():
    Base.metadata.create_all(bind=engine)