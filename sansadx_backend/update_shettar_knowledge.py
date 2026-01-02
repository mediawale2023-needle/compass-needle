from db import SessionLocal, Tenant
import json

db = SessionLocal()

# 1. Define Belgaum Knowledge
belgaum_knowledge = """
1. BELGAUM UTTAR (NORTH) includes:
   - Bogarves, CBT (Central Bus Stand), Market, Camp, Sadashiv Nagar, APMC, RTO Circle, Kakatives, Nehru Nagar, Malmaruti.

2. BELGAUM DAKSHIN (SOUTH) includes:
   - Tilakwadi, Shahapur, Vadgaon, Railway Station Area, Hindwadi, Angol, Udyambag, Yellur, Dhamne.

3. BELGAUM RURAL includes:
   - Sambra, Kakati, Honaga, Uchgaon, Peeranwadi, Macche.
"""

# 2. Find Shettar
tenant = db.query(Tenant).filter(Tenant.name == "Hon. Jagdish Shettar").first()

if tenant:
    # 3. Update his Config
    # We must copy the existing config, update it, and save it back
    current_config = dict(tenant.config) if tenant.config else {}
    current_config["jurisdiction_guide"] = belgaum_knowledge  # <--- INJECTING KNOWLEDGE
    
    tenant.config = current_config
    db.commit()
    print("✅ Belgaum Knowledge injected into Shettar's Brain.")
else:
    print("❌ Tenant not found.")

db.close()