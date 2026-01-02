import os

def create_backend():
    # 1. Create the Directory
    folder = "sansadx-backend"
    if not os.path.exists(folder):
        os.makedirs(folder)
        print(f"✅ Created folder: {folder}")
    else:
        print(f"ℹ️ Folder '{folder}' already exists.")

    # 2. Create requirements.txt
    req_content = """fastapi
uvicorn
pandas
requests
"""
    with open(f"{folder}/requirements.txt", "w") as f:
        f.write(req_content)
    print("✅ Created requirements.txt")

    # 3. Create dummy database (grievances.csv)
    csv_content = """id,user,issue,category,status,timestamp
101,Ramesh Pawar,No water supply in Ward 4,Water,Pending,2025-12-08 09:30
102,Sita Devi,Street light broken near school,Infrastructure,Resolved,2025-12-08 10:15
103,Amit Shah (Local),Garbage truck missed collection,Sanitation,Pending,2025-12-08 11:00
104,Priya M.,Pension status inquiry,Welfare,In Progress,2025-12-08 11:45
105,Vikram S.,Potholes on Main Road,Roads,Pending,2025-12-08 12:30
"""
    with open(f"{folder}/grievances.csv", "w") as f:
        f.write(csv_content)
    print("✅ Created grievances.csv")

    # 4. Create main.py (The Server Code)
    main_code = """from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pandas as pd
import os

app = FastAPI(title="SansadX API")
DB_FILE = "grievances.csv"

# --- HELPERS ---
def read_db():
    if not os.path.exists(DB_FILE):
        return pd.DataFrame(columns=["id", "user", "issue", "category", "status", "timestamp"])
    return pd.read_csv(DB_FILE)

def save_db(df):
    df.to_csv(DB_FILE, index=False)

# --- ENDPOINTS ---
@app.get("/")
def home():
    return {"status": "SansadX Backend Online"}

@app.get("/cases")
def list_cases():
    df = read_db()
    return df.to_dict(orient="records")[::-1]

@app.get("/api/stats")
def get_stats():
    df = read_db()
    if df.empty: return {"total": 0, "resolved": 0, "pending": 0}
    return {
        "total": int(len(df)),
        "resolved": int(len(df[df['status'] == 'Resolved'])),
        "pending": int(len(df[df['status'] != 'Resolved'])) # Anything not Resolved is Pending
    }

@app.get("/api/grievances")
def get_grievances():
    return list_cases()

class StatusUpdate(BaseModel):
    status: str

@app.put("/cases/{case_id}")
def update_case(case_id: int, update: StatusUpdate):
    df = read_db()
    if case_id not in df['id'].values:
        raise HTTPException(status_code=404, detail="Case not found")
    
    df.loc[df['id'] == case_id, 'status'] = update.status
    save_db(df)
    return {"status": "success", "new_state": update.status}

# For compatibility with older endpoint styles if needed
@app.put("/api/grievances/{case_id}")
def update_grievance(case_id: int, update: StatusUpdate):
    return update_case(case_id, update)
"""
    with open(f"{folder}/main.py", "w") as f:
        f.write(main_code)
    print("✅ Created main.py")
    
    print("\n🚀 SETUP COMPLETE!")
    print("Run these commands next:")
    print(f"1. cd {folder}")
    print("2. pip install -r requirements.txt")
    print("3. uvicorn main:app --reload")

if __name__ == "__main__":
    create_backend()