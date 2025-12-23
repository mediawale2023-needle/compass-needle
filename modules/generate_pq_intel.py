import json
import random
from datetime import datetime, timedelta

def generate_pq_intelligence():
    print("🏛️ Minting Parliamentary Question (PQ) Database...")

    # Ministries that run Schemes (NOT Corporate stuff)
    ministries = [
        "Ministry of Jal Shakti", "Ministry of Rural Development", "Ministry of Housing & Urban Affairs",
        "Ministry of Agriculture", "Ministry of Health", "Ministry of Education", "Ministry of Textiles"
    ]

    # Schemes mapped to Ministries
    scheme_map = {
        "Ministry of Jal Shakti": ["Jal Jeevan Mission", "Swachh Bharat (Rural)"],
        "Ministry of Housing & Urban Affairs": ["AMRUT 2.0", "PM Awas Yojana (Urban)", "Smart Cities"],
        "Ministry of Rural Development": ["MGNREGA", "PM Awas Yojana (Rural)", "PM Gram Sadak"],
        "Ministry of Agriculture": ["PM-KISAN", "Crop Insurance", "Agri-Infra Fund"],
        "Ministry of Health": ["Ayushman Bharat", "National Health Mission"],
        "Ministry of Education": ["PM-SHRI", "Mid-Day Meal"],
        "Ministry of Textiles": ["PM MITRA", "Samarth Scheme"]
    }

    pq_db = []
    
    for i in range(500):
        ministry = random.choice(ministries)
        scheme = random.choice(scheme_map[ministry])
        q_id = f"LS-{random.randint(10000, 99999)}"
        date = (datetime.now() - timedelta(days=random.randint(1, 365))).strftime("%Y-%m-%d")
        
        # Logic: 20% of answers indicate "Funds Exhausted" (Red Flag)
        status_roll = random.random()
        if status_roll < 0.2:
            ans = f"The budgetary allocation for {scheme} has been fully utilized for the current financial year. No further sanctions can be made."
            tags = ["Funds Exhausted", "Critical"]
        elif status_roll < 0.5:
             ans = f"An amount of ₹{random.randint(100, 500)} Cr is unspent under {scheme}. States are requested to expedite proposals."
             tags = ["Funds Available", "Opportunity"]
        else:
            ans = f"The implementation of {scheme} is progressing as per schedule. State-wise details are in Annexure A."
            tags = ["Routine"]

        entry = {
            "question_id": q_id,
            "date": date,
            "ministry": ministry,
            "scheme_ref": scheme,
            "text": f"Will the Minister be pleased to state the fund utilization status of {scheme}?",
            "answer": ans,
            "tags": tags
        }
        pq_db.append(entry)

    with open("questions_db.json", "w") as f:
        json.dump(pq_db, f, indent=4)
        
    print(f"✅ Generated {len(pq_db)} Parliamentary Intelligence Records.")

if __name__ == "__main__":
    generate_pq_intelligence()