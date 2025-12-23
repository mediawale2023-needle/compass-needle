import os

FOLDER = "sansadx-backend"

# --- 1. JURISDICTION TAXONOMY (The Knowledge Base) ---
jurisdiction_code = """
# TAXONOMY: Governance Issues Mapping
# Fields: Level (Central/State/Local), Authority, MP Role (Direct/Coordinate/No Role)

TAXONOMY = [
    # --- CENTRAL / MP DIRECT ---
    {"keywords": ["railway", "train", "station", "platform", "stoppage"], "category": "Railways", "authority": "Ministry of Railways", "level": "Central", "mp_role": "Direct", "response": "Your MP can directly raise this in Parliament or with the Railway Ministry."},
    {"keywords": ["national highway", "nh", "nhai", "toll plaza", "flyover on highway"], "category": "Infrastructure", "authority": "NHAI / MoRTH", "level": "Central", "mp_role": "Direct", "response": "This falls under Central Govt. Your MP will take this up with NHAI."},
    {"keywords": ["passport", "visa", "embassy", "immigration"], "category": "External Affairs", "authority": "Ministry of External Affairs", "level": "Central", "mp_role": "Direct", "response": "Passport issues are Central subjects. We will expedite this with the RPO."},
    {"keywords": ["bsnl", "telecom", "tower", "network issue", "post office"], "category": "Telecom & Post", "authority": "Ministry of Communications", "level": "Central", "mp_role": "Direct", "response": "This is a Central Ministry issue. We will flag it to the department."},
    {"keywords": ["central school", "kendriya vidyalaya", "navodaya", "cbse", "iit", "aiims"], "category": "Education (Central)", "authority": "Ministry of Education", "level": "Central", "mp_role": "Direct", "response": "Central Educational Institutes are under MP's oversight committee."},
    {"keywords": ["bank", "loan", "mudra", "sbi", "atm"], "category": "Banking", "authority": "Ministry of Finance", "level": "Central", "mp_role": "Direct", "response": "Banking policy is Central. We can guide you to the right grievance cell."},

    # --- STATE / MLA (MP Coordinates) ---
    {"keywords": ["police", "fir", "theft", "crime", "law and order"], "category": "Law & Order", "authority": "State Police / Home Dept", "level": "State", "mp_role": "Coordinate", "response": "Police is a State subject. However, the MP will forward your request to the SP/Commissioner."},
    {"keywords": ["electricity", "power cut", "voltage", "pole", "transformer", "bill"], "category": "Electricity", "authority": "State Electricity Board (Discom)", "level": "State", "mp_role": "Coordinate", "response": "Electricity is a State Board matter. We will forward this to the local JE/AE."},
    {"keywords": ["state highway", "district road", "pwd road"], "category": "Infrastructure", "authority": "State PWD", "level": "State", "mp_role": "Coordinate", "response": "This road belongs to the State PWD. We will request the local MLA/Official to inspect."},
    {"keywords": ["ration", "pds", "food grain", "ration card"], "category": "Food Supply", "authority": "State Civil Supplies Dept", "level": "State", "mp_role": "Coordinate", "response": "Ration Cards are managed by the State. We will pass this to the District Supply Officer."},
    
    # --- LOCAL / MUNICIPAL (MP Influences) ---
    {"keywords": ["garbage", "trash", "dustbin", "cleaning", "drainage", "gutter", "sewage", "sanitation"], "category": "Sanitation", "authority": "Municipal Corporation / Ward Office", "level": "Local", "mp_role": "Influence", "response": "Sanitation is a Municipal task. We have logged this ticket with your Ward Officer."},
    {"keywords": ["water supply", "drinking water", "pipeline", "borewell", "tanker"], "category": "Water", "authority": "Municipal Water Dept / Jal Board", "level": "Local", "mp_role": "Influence", "response": "Water supply is a local body function. We are notifying the Municipal Engineer."},
    {"keywords": ["street light", "lamp post", "dark spot"], "category": "Civic Amenities", "authority": "Municipal Corporation", "level": "Local", "mp_role": "Influence", "response": "Street lights are maintained by the Municipality. We will alert the zone office."},
    {"keywords": ["stray dog", "mosquito", "fogging", "cattle"], "category": "Public Health", "authority": "Municipal Health Dept", "level": "Local", "mp_role": "Influence", "response": "Vector control is a Municipal duty. We will request fogging in your area."},
    {"keywords": ["property tax", "khata", "birth certificate", "death certificate"], "category": "Civic Admin", "authority": "Municipal Corporation", "level": "Local", "mp_role": "Influence", "response": "These certificates are issued by the local civic body."},

    # --- NOT IN SCOPE ---
    {"keywords": ["private dispute", "neighbor fight", "property dispute", "divorce", "court case"], "category": "Private/Legal", "authority": "Judiciary / Police", "level": "Private", "mp_role": "Not In Scope", "response": "This is a private legal matter/civil dispute. Public representatives cannot intervene in court sub-judice matters."},
]

def get_classification(text):
    text = text.lower()
    # 1. Exact Keyword Match
    for item in TAXONOMY:
        for kw in item["keywords"]:
            if kw in text:
                return item
    
    # 2. Default Fallback
    return {
        "category": "General Grievance",
        "authority": "District Collector's Office",
        "level": "Admin",
        "mp_role": "Coordinate",
        "response": "Your issue has been noted and will be forwarded to the relevant department."
    }
"""

# --- 2. PROMPTS (The AI Persona) ---
prompts_code = """
SYSTEM_PROMPT = \"\"\"
You are the AI Chief of Staff for an Indian Member of Parliament (MP).
Your job is to classify incoming citizen grievances into the correct jurisdiction.

### RULES FOR CLASSIFICATION:
1. **Central Govt / MP Direct**: Railways, National Highways, Passports, Telecom, Banking, Central Universities.
   -> ACTION: "Direct Intervention"
2. **State Govt / MLA**: Police, Electricity, State Roads, RTO, State Schools, Hospitals.
   -> ACTION: "Forward & Monitor"
3. **Local Body / Municipality**: Garbage, Drains, Street Lights, Water Supply, Stray Animals, Birth/Death Certs.
   -> ACTION: "Lodge Ticket with Corp"
4. **Private/Legal**: Neighbor disputes, private loans, court cases.
   -> ACTION: "Decline (Private Matter)"

### OUTPUT FORMAT (JSON ONLY):
{
    "summary": "Brief 5-word summary of issue",
    "category": "e.g. Sanitation / Railways / Police",
    "authority": "e.g. Municipal Corp / DRM / SP Office",
    "level": "Central / State / Local",
    "mp_role": "Direct / Coordinate / Influence / Not In Scope",
    "political_response": "Polite, empathetic response to citizen explaining who is responsible and what the MP will do. (Max 2 sentences)"
}
\"\"\"
"""

# --- 3. DATABASE (SQLite) ---
db_code = """
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

SQLALCHEMY_DATABASE_URL = "sqlite:///./sansadx.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Case(Base):
    __tablename__ = "cases"
    id = Column(Integer, primary_key=True, index=True)
    raw_message = Column(Text)
    
    # Classification
    category = Column(String)
    authority = Column(String)
    level = Column(String)
    mp_role = Column(String) # Direct, Coordinate, Influence
    
    # Tracking
    status = Column(String, default="new") # new, resolved, escalated
    should_track = Column(Boolean, default=True)
    
    # Responses
    response_to_citizen = Column(Text)
    notes_for_staff = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)
"""

# --- 4. LLM CLIENT (Groq Integration) ---
llm_code = """
import os
import json
from groq import Groq

# ⚠️ ENSURE YOU SET THIS ENV VAR OR HARDCODE FOR DEMO
# os.environ["GROQ_API_KEY"] = "your_api_key_here"

def call_sansadx_model(user_message, system_prompt):
    try:
        # Fallback if no key
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            return json.dumps({
                "summary": "System Error",
                "category": "Unclassified",
                "authority": "Admin",
                "level": "Unknown",
                "mp_role": "Coordinate",
                "political_response": "AI API Key missing. Please configure backend."
            })

        client = Groq(api_key=api_key)
        
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"LLM Error: {e}")
        return json.dumps({
            "summary": "Error Processing",
            "category": "Error",
            "authority": "Admin",
            "level": "Unknown",
            "mp_role": "Coordinate",
            "political_response": "Technical error in analysis."
        })
"""

# --- 5. UPDATED MAIN SERVER ---
main_code = """
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
import json
import os

# Import our new modules
from db import SessionLocal, init_db, Case
from jurisdiction import get_classification
from prompts import SYSTEM_PROMPT
from llm_client import call_sansadx_model

app = FastAPI(title="SansadX Intelligent Backend")

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.on_event("startup")
def on_startup():
    init_db()

# Request Model
class IssueRequest(BaseModel):
    message: str

@app.get("/")
def home():
    return {"status": "SansadX AI Router Online"}

@app.post("/analyze_issue")
def analyze_issue(req: IssueRequest, db: Session = Depends(get_db)):
    # 1. HYBRID ANALYSIS
    # First, try strict taxonomy matching (Fast & Deterministic)
    rule_based = get_classification(req.message)
    
    # Second, use LLM for nuance and response generation
    # We feed the rule-based finding into the LLM context
    context_prompt = SYSTEM_PROMPT + f"\\n\\nContext: The rule-based system identified this as: {json.dumps(rule_based)}"
    
    llm_raw = call_sansadx_model(req.message, context_prompt)
    
    try:
        ai_data = json.loads(llm_raw)
    except:
        ai_data = rule_based # Fallback
    
    # 2. SAVE TO DB
    # Determine tracking logic: If 'Not In Scope', maybe don't track actively?
    should_track = ai_data.get("mp_role") != "Not In Scope"
    
    case = Case(
        raw_message=req.message,
        category=ai_data.get("category"),
        authority=ai_data.get("authority"),
        level=ai_data.get("level"),
        mp_role=ai_data.get("mp_role"),
        should_track=should_track,
        response_to_citizen=ai_data.get("political_response"),
        notes_for_staff=f"Summary: {ai_data.get('summary')}",
        status="new"
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    
    # 3. RETURN RESPONSE
    return {
        "id": case.id,
        "classification": {
            "category": case.category,
            "authority": case.authority,
            "level": case.level,
            "mp_role": case.mp_role
        },
        "response_to_citizen": case.response_to_citizen,
        "internal_recommendation": {
            "should_MP_office_track": case.should_track
        }
    }

@app.get("/cases")
def list_cases(db: Session = Depends(get_db)):
    cases = db.query(Case).order_by(Case.created_at.desc()).all()
    return cases

@app.post("/cases/{case_id}")
def update_status(case_id: int, payload: dict, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    case.status = payload.get("status", "new")
    db.commit()
    return {"status": "updated"}
"""

# --- WRITE FILES ---
def write_file(filename, content):
    with open(f"{FOLDER}/{filename}", "w") as f:
        f.write(content)
    print(f"✅ Created {filename}")

def run_upgrade():
    if not os.path.exists(FOLDER):
        os.makedirs(FOLDER)
    
    write_file("jurisdiction.py", jurisdiction_code)
    write_file("prompts.py", prompts_code)
    write_file("db.py", db_code)
    write_file("llm_client.py", llm_code)
    write_file("main.py", main_code)
    
    # Add requirements for SQL & Groq
    with open(f"{FOLDER}/requirements.txt", "w") as f:
        f.write("fastapi\\nuvicorn\\nsqlalchemy\\npandas\\ngroq\\nrequests\\n")
    
    print("\\n🚀 SANSADX UPGRADE COMPLETE!")
    print("1. cd sansadx-backend")
    print("2. pip install -r requirements.txt")
    print("3. export GROQ_API_KEY='your_key'")
    print("4. uvicorn main:app --reload")

if __name__ == "__main__":
    run_upgrade()