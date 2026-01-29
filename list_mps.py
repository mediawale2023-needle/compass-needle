import sys
import os
from dotenv import load_dotenv

# --- 1. LOAD ENV FROM SUBFOLDER (THE FIX) ---
# Your .env is hiding inside 'sansadx_backend/', so we point to it directly.
current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(current_dir, 'sansadx_backend', '.env')
load_dotenv(dotenv_path=env_path)

# Check if it worked
db_url = os.getenv("DATABASE_URL")
if not db_url:
    print(f"\n❌ Error: Still cannot find DATABASE_URL in {env_path}")
    sys.exit(1)

# --- 2. SETUP PATH & IMPORT ---
sys.path.append(os.path.join(current_dir, 'sansadx_backend'))

try:
    from main import User, SessionLocal
except ImportError as e:
    print(f"\n❌ Import Error: {e}")
    sys.exit(1)

def list_all_mps():
    db = SessionLocal()
    
    try:
        users = db.query(User).all()
        
        print("\n----------------------------------------------------------------")
        print(f"   🏛️  CURRENT LOGIN REGISTRY")
        print("----------------------------------------------------------------")
        print(f"{'ID':<5} {'USERNAME / EMAIL':<30} {'ROLE':<10} {'CONSTITUENCY'}")
        print("-" * 75)
        
        count = 0
        for user in users:
            # Handle mixed field names (username vs email)
            name_display = getattr(user, 'username', None) or getattr(user, 'email', 'Unknown')
            u_role = getattr(user, 'role', 'user')
            u_loc = getattr(user, 'constituency', 'Unknown')
            
            print(f"{user.id:<5} {name_display:<30} {u_role:<10} {u_loc}")
            count += 1
            
        print("-" * 75)
        print(f"✅ Total Users Found: {count}")
        print("----------------------------------------------------------------\n")
        
    except Exception as e:
        print(f"❌ Database Query Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    list_all_mps()