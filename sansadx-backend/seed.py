from db import SessionLocal, init_db, Tenant, User

# --- 1. LOK SABHA CONFIG (Belagavi) ---
LS_CONFIG = {
    "type": "LOK_SABHA",
    "map_enabled": True,
    "language": "Kannada",
    "supported_languages": ["English", "Hindi", "Kannada", "Marathi"],
    "jurisdiction": {
        "Arabhavi": { "lat": 16.2250, "lon": 74.8250 },
        "Gokak": { "lat": 16.1691, "lon": 74.8298 },
        "Ramdurg": { "lat": 15.9447, "lon": 75.2975 }
    }
}

# --- 2. RAJYA SABHA CONFIG (Karnataka) ---
RS_CONFIG = {
    "type": "RAJYA_SABHA",
    "map_enabled": False,
    "language": "English",
    "supported_languages": ["English", "Hindi", "Kannada"],
    "jurisdiction": {
        "Bangalore Urban": "District",
        "Belagavi": "District",
        "Kalaburagi": "District"
    }
}

def boot_system():
    print("🚀 Initializing Needle SaaS...")
    init_db()
    db = SessionLocal()

    # 1. Create Super Admin (Needle HQ)
    if not db.query(Tenant).filter_by(name="Needle HQ").first():
        hq = Tenant(
            name="Needle HQ",
            constituency="System Admin",
            whatsapp_number="admin_console",
            subscription_plan="Enterprise",
            config={"language": "English"}
        )
        db.add(hq)
        db.commit()
        
        # Create 'admin' user
        admin = User(tenant_id=hq.id, username="admin", password_hash="admin", role="super_admin")
        db.add(admin)
        db.commit()
        print("✅ Created Super Admin: admin / admin")

    # 2. Create Lok Sabha Client (Shettar)
    if not db.query(Tenant).filter_by(name="Hon. Jagdish Shettar").first():
        shettar = Tenant(
            name="Hon. Jagdish Shettar",
            constituency="Belgaum (LS)",
            whatsapp_number="sim_ls",
            subscription_plan="Pro",
            config=LS_CONFIG
        )
        db.add(shettar)
        db.commit()
        print("✅ Created Client: Hon. Jagdish Shettar")

    # 3. Create Rajya Sabha Client
    if not db.query(Tenant).filter_by(name="Hon. RS Member").first():
        rs = Tenant(
            name="Hon. RS Member",
            constituency="Karnataka (RS)",
            whatsapp_number="sim_rs",
            subscription_plan="Pro",
            config=RS_CONFIG
        )
        db.add(rs)
        db.commit()
        print("✅ Created Client: Hon. RS Member")

    db.close()
    print("🎉 System Ready.")

if __name__ == "__main__":
    boot_system()