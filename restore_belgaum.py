import os
import json
from sqlalchemy import create_engine, text

# --- CONNECT TO RAILWAY DATABASE ---
# This uses your specific Railway credentials
DATABASE_URL = "postgresql://postgres:qavOCQWrfITqxVGUFHCVkSdosvHhmQHe@shortline.proxy.rlwy.net:57534/railway"

engine = create_engine(DATABASE_URL)
print("🚀 Connecting to Railway Database...")

with engine.connect() as conn:
    # 1. CLEAN SLATE (Remove any incomplete data)
    print("🧹 Cleaning up old data...")
    conn.execute(text("DELETE FROM cases WHERE tenant_id = 1;"))
    
    # 2. RESTORE ADMIN LOGIN (Jagdish Shettar)
    print("👤 Restoring Admin Access...")
    conn.execute(text("""
        INSERT INTO users (username, password_hash, role, tenant_id) 
        VALUES ('admin', 'password', 'admin', 1)
        ON CONFLICT (username) DO NOTHING;
    """))

    # 3. RESTORE BELGAUM SPECIFIC DATA
    # These are the specific cases for Belagavi South/North/Rural
    print("📝 Injecting Belgaum Grievances...")

    # Helper function to format the data correctly for the database
    def make_case(phone, cat, msg, status, area, ac):
        # We inject the JSON metadata so the Map/Red Zones work immediately
        meta = json.dumps({
            "location_resolved": True,
            "matched_value": area,
            "assembly_constituency": ac
        })
        return {
            "p": phone, "c": cat, "m": msg, "s": status, "meta": meta
        }

    # The Data List
    cases = [
        make_case("9900112233", "Water", "Severe water shortage in Tilakwadi 2nd cross. No supply for 4 days.", "new", "Tilakwadi", "Belgaum South"),
        make_case("9900112234", "Roads", "Dangerous potholes on College Road near RPD Cross causing accidents.", "progress", "Tilakwadi", "Belgaum South"),
        make_case("9900112235", "Sanitation", "Garbage uncollected in Camp area, near Bishop Cotton School.", "new", "Camp", "Belgaum North"),
        make_case("9900112236", "Electricity", "Street lights non-functional in Shahapur market. Safety risk at night.", "new", "Shahapur", "Belgaum South"),
        make_case("9900112237", "Water", "Contaminated water supply reported in Vadgaon.", "critical", "Vadgaon", "Belgaum South"),
        make_case("9900112238", "Health", "Shortage of staff at Civil Hospital night shift.", "new", "Civil Hospital", "Belgaum North"),
        make_case("9900112239", "Traffic", "Traffic signal at Chennamma Circle is malfunctioning.", "closed", "Chennamma Circle", "Belgaum North"),
        make_case("9900112240", "Education", "Roof leakage reported at Government School in Hindwadi.", "new", "Hindwadi", "Belgaum South"),
        make_case("9900112241", "Water", "Low pressure water supply in Angol main road.", "progress", "Angol", "Belgaum South"),
        make_case("9900112242", "Roads", "Smart City road work stalled in Sadashiv Nagar causing huge jams.", "new", "Sadashiv Nagar", "Belgaum North"),
    ]

    # SQL Command
    sql = text("""
        INSERT INTO cases (tenant_id, user_phone, category, raw_message, status, case_metadata)
        VALUES (1, :p, :c, :m, :s, :meta)
    """)

    # Run the insertion loop
    for case in cases:
        conn.execute(sql, case)
    
    conn.commit()

print("✅ SUCCESS! Belgaum Data Restored.")
print("👉 You can now log in as 'admin' / 'password' and see the data.")