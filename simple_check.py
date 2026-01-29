import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

def check_users_raw():
    # 1. LOAD ENV (Forcefully from the backend folder)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(current_dir, 'sansadx_backend', '.env')
    
    print(f"🔍 Looking for .env at: {env_path}")
    if os.path.exists(env_path):
        load_dotenv(dotenv_path=env_path)
        print("✅ Loaded .env file.")
    else:
        print("⚠️  .env not found in sansadx_backend. Trying root...")
        load_dotenv() # Fallback to root

    # 2. GET DATABASE URL
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("\n❌ CRITICAL: No DATABASE_URL found.")
        print("Please create a .env file with your Railway URL.")
        return

    # 3. FIX URL FOR PYTHON
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    print(f"🔌 Connecting to Database...")
    
    try:
        # 4. CONNECT DIRECTLY (No Models, No App Logic)
        engine = create_engine(db_url)
        
        with engine.connect() as conn:
            # 5. EXECUTE RAW SQL
            print("📊 Querying 'users' table...")
            result = conn.execute(text("SELECT * FROM users"))
            
            # 6. PRINT RESULTS
            print("\n" + "="*80)
            print(f"{'ID':<5} {'USERNAME':<20} {'ROLE':<10} {'CONSTITUENCY'}")
            print("="*80)
            
            count = 0
            # Iterate through rows safely
            for row in result.mappings():
                # Get fields safely (handles different column names)
                uid = row.get('id', 'N/A')
                name = row.get('username') or row.get('email') or "Unknown"
                role = row.get('role', 'user')
                constituency = row.get('constituency', ' - ')
                
                print(f"{uid:<5} {name:<20} {role:<10} {constituency}")
                count += 1
            
            print("="*80)
            print(f"✅ Total Users: {count}")
            print("="*80 + "\n")

    except Exception as e:
        print(f"\n❌ CONNECTION ERROR: {e}")
        print("Tip: Check if your IP is allowed on Railway, or if the URL is correct.")

if __name__ == "__main__":
    check_users_raw()