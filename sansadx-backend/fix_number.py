from db import SessionLocal, Tenant

db = SessionLocal()

# --- ⚙️ CONFIGURATION ---
# This must match EXACTLY what Twilio sends (usually with the +)
REAL_NUMBER = "+14155238886" 
TARGET_TENANT = "Hon. Jagdish Shettar"
# ------------------------

print(f"🔄 Attempting to link {TARGET_TENANT} to {REAL_NUMBER}...")

tenant = db.query(Tenant).filter(Tenant.name == TARGET_TENANT).first()

if tenant:
    print(f"   found tenant ID: {tenant.id}")
    print(f"   Old Number: {tenant.whatsapp_number}")
    
    # UPDATE THE NUMBER
    tenant.whatsapp_number = REAL_NUMBER
    db.commit()
    
    print(f"   ✅ SUCCESS! New Number is: {tenant.whatsapp_number}")
    print("   🚀 The system will now recognize incoming messages!")
else:
    print(f"❌ Error: Could not find tenant named '{TARGET_TENANT}'")

db.close()