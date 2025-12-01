import json
import random
from datetime import datetime, timedelta

def generate_large_pq_db():
    print("🏭 Starting Mass Production of 5,000 Parliamentary Questions...")
    
    # --- 1. EXTENDED INTELLIGENCE ASSETS ---
    ministries_data = {
        "Ministry of Railways": [
            "Safety of tracks", "Vande Bharat routes", "Railway recruitment", "Kavach system", 
            "Electrification progress", "Station redevelopment (Amrit Bharat)", "Ticket concessions", "Freight corridor delays"
        ],
        "Ministry of Finance": [
            "GST Collection", "Inflation rates", "Cryptocurrency regulation", "Loan write-offs",
            "Fiscal deficit targets", "Bank privatization", "Disinvestment status", "Demonetization impact study"
        ],
        "Ministry of Home Affairs": [
            "Cybercrime statistics", "Border fencing", "Disaster relief funds", "Police modernization",
            "Naxalism control", "Official language usage", "Census delay", "Prison reforms"
        ],
        "Ministry of Health and Family Welfare": [
            "New AIIMS status", "Doctor-patient ratio", "Generic medicine availability", "Malnutrition data",
            "Ayushman Bharat card usage", "Medical college seats", "Mental health budget", "Rural ambulance services"
        ],
        "Ministry of Agriculture": [
            "MSP for wheat", "Fertilizer subsidy", "Crop insurance claims", "Organic farming promotion",
            "PM-KISAN payouts", "Cold storage chain", "Stubble burning", "Drone usage in farming"
        ],
        "Ministry of Education": [
            "NEP implementation", "IIT vacancies", "Digital literacy", "School dropout rates",
            "PM-SHRI school selection", "Kendriya Vidyalaya construction", "Research grants", "Mid-day meal quality"
        ],
        "Ministry of Road Transport and Highways": [
            "NHAI debt", "EV charging infrastructure", "Road accidents", "Green highways",
            "Toll plaza removal", "Ethanol blending", "Bridge safety audit", "Bharatmala Phase 2"
        ],
        "Ministry of Urban Affairs": [
            "AMRUT 2.0 progress", "Smart City completion", "Metro rail ridership", "Swachh Bharat 2.0",
            "Urban housing shortage", "Water treatment plants", "Street vendor loans", "Waste segregation"
        ],
        "Ministry of Fisheries": [
            "PM Matsya Sampada funds", "Deep sea fishing vessels", "Kisan Credit Card for fishermen", "Inland fisheries growth",
            "Shrimp export data", "Fishing harbor construction", "Insurance for fishermen", "Algae farming"
        ]
    }

    # Templates to make questions sound different
    q_templates = [
        "Will the Minister be pleased to state the current status of {topic}?",
        "Whether the Government has taken note of issues regarding {topic}?",
        "The details of funds allocated and utilized for {topic} in the last fiscal year?",
        "Whether there is any proposal to expand {topic} in the state of Maharashtra?",
        "The state-wise progress report of {topic} as of date?",
        "Whether any deadline has been fixed for the completion of {topic}?"
    ]

    questions_db = []
    start_date = datetime(2023, 1, 1)
    
    # --- 2. GENERATE 5,000 RECORDS ---
    for i in range(1, 5001):
        ministry = random.choice(list(ministries_data.keys()))
        topic = random.choice(ministries_data[ministry])
        q_id = f"LS-{random.randint(10000, 99999)}" # 5-digit ID
        
        # Random date between Jan 2023 and today
        days_offset = random.randint(0, 700)
        date = (start_date + timedelta(days=days_offset)).strftime("%Y-%m-%d")
        
        # Randomize Question Text
        q_text = random.choice(q_templates).format(topic=topic)
        
        # Simulate Answer Logic (Weighted for realism)
        # 10% Exhausted (Red), 30% Unspent (Green), 60% Routine (Yellow/Gray)
        outcome = random.choices(["exhausted", "available", "routine"], weights=[10, 30, 60])[0]
        
        if outcome == "exhausted":
            ans = f"The budgetary allocation for {topic} has been fully utilized (99%) for the current financial year. No further proposals can be entertained until the next Budget cycle."
        elif outcome == "available":
            ans = f"An unspent balance of ₹{random.randint(50, 500)} Crore is available under the {topic} head. State Governments have been requested to submit Utilization Certificates to claim fresh installments."
        else:
            ans = f"The Government is actively implementing measures for {topic}. A committee has been set up to monitor progress. State-wise details are placed at Annexure-A."

        entry = {
            "question_id": q_id,
            "date": date,
            "ministry": ministry,
            "text": q_text,
            "answer": ans
        }
        questions_db.append(entry)
        
        # Progress bar for terminal
        if i % 500 == 0:
            print(f"   ...Minted {i} questions...")

    # --- 3. SAVE ---
    with open("questions_db.json", "w") as f:
        json.dump(questions_db, f, indent=4)

    print(f"✅ SUCCESS! Generated 'questions_db.json' with {len(questions_db)} entries.")
    print(f"📂 File Size: Approx {len(json.dumps(questions_db))/1024/1024:.2f} MB")

if __name__ == "__main__":
    generate_large_pq_db()
