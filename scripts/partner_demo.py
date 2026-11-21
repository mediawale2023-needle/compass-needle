"""
Local demo of the partner (consultancy) channel.

Runs the real backend (`main:app`) against a throwaway SQLite database seeded with
demo data. It never reads `.env`, never touches your real database, and disables
every startup background job (WhatsApp sweepers, government sync, keep-alive), so
nothing external is called.

    python scripts/partner_demo.py            # fresh DB each run, serves on :8000
    python scripts/partner_demo.py --keep     # reuse the DB from the last run
    python scripts/partner_demo.py --port 8010

Normally launched through `scripts/partner_demo.sh`, which also starts both frontends.
"""
import argparse
import os
import random
import sys
import tempfile
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, default=8000)
parser.add_argument("--keep", action="store_true", help="keep the existing demo database instead of re-seeding")
parser.add_argument("--db", default=os.path.join(tempfile.gettempdir(), "needle_partner_demo.db"))
args = parser.parse_args()

# Isolated environment — set BEFORE importing anything from the app.
fresh = not args.keep or not os.path.exists(args.db)
if fresh:
    for suffix in ("", "-journal", "-wal", "-shm"):
        try:
            os.remove(args.db + suffix)
        except FileNotFoundError:
            pass
os.environ.update({
    "DATABASE_URL": f"sqlite:///{args.db}",
    "JWT_SECRET": "partner-demo-secret-not-for-production-use-0123456789",
    "ENV": "development",
    "OPENAI_API_KEY": "sk-demo-not-used",
    "ALLOWED_ORIGINS": "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001",
})
for var in ("RAILWAY_PUBLIC_DOMAIN", "KEEP_ALIVE_URL", "META_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID"):
    os.environ.pop(var, None)

from sqlalchemy import event  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402


@event.listens_for(Engine, "connect")
def _sqlite_pg_lock_shims(dbapi_connection, _record):
    """The app's startup takes Postgres advisory locks; give SQLite harmless stand-ins."""
    try:
        for name in ("pg_try_advisory_lock", "pg_advisory_unlock", "pg_try_advisory_xact_lock"):
            dbapi_connection.create_function(name, 1, lambda _key: 1)
    except Exception:
        pass


import main  # noqa: E402
import admin_api  # noqa: E402
import sansadx_backend.db as dbmod  # noqa: E402
from sansadx_backend.db import Base, Case, Tenant, User  # noqa: E402
from modules.partners import PartnerOrg, PartnerSeat, PartnerUser  # noqa: E402

ADMIN = ("sysadmin", "AdminDemo1!")
PARTNER_READY = ("ops@rajdhani.in", "PartnerDemo1")
PARTNER_TEMP = ("new@rajdhani.in", "TempDemo123")
PARTNER_BRAVO = ("ops@bravo.in", "PartnerDemo1")

CATEGORIES = [("Water Supply", 30), ("Roads & Potholes", 24), ("Sanitation", 18), ("Electricity", 16), ("Healthcare", 7), ("Education", 5)]
WARDS = ["Tilakwadi", "Hanuman Nagar", "Ward 12", "Shahapur", "Angol", "Ward 5"]


def seed():
    Base.metadata.create_all(bind=dbmod.engine)
    rnd = random.Random(7)
    now = datetime.utcnow()
    db = dbmod.SessionLocal()
    try:
        hp = admin_api.hash_password
        tenants = {
            1: Tenant(id=1, name="System Admin", constituency="India", whatsapp_number="+910000000001", subscription_plan="System",
                      tenant_type="mp", account_stage="elected", seat_type="mp", is_active=True),
            2: Tenant(id=2, name="Asha Patil", constituency="Belagavi South", whatsapp_number="+910000000002", subscription_plan="Pro",
                      tenant_type="aspirant", account_stage="aspirant", seat_type="mla", is_active=True),
            3: Tenant(id=3, name="Ravi Kulkarni", constituency="Pune Cantonment", whatsapp_number="+910000000003", subscription_plan="Pro",
                      tenant_type="aspirant", account_stage="aspirant", seat_type="mla", is_active=True),
            4: Tenant(id=4, name="Meera Naik", constituency="Panaji", whatsapp_number="+910000000004", subscription_plan="Pro",
                      tenant_type="aspirant", account_stage="aspirant", seat_type="mla", is_active=True),
            5: Tenant(id=5, name="Sunil Deshpande", constituency="Hubballi-Dharwad West", whatsapp_number="+910000000005", subscription_plan="Pro",
                      tenant_type="aspirant", account_stage="aspirant", seat_type="mla", is_active=True),
            6: Tenant(id=6, name="Kavita Joshi", constituency="Nashik Central", whatsapp_number="+910000000006", subscription_plan="Pro",
                      tenant_type="aspirant", account_stage="aspirant", seat_type="mla", is_active=True),
        }
        db.add_all(tenants.values())
        db.flush()
        db.add(User(tenant_id=1, username=ADMIN[0], password_hash=hp(ADMIN[1]), role="sysadmin", constituency="India",
                    house="Lok Sabha", display_name="Needle Admin", is_active=True, must_change_password=False))
        for tid in range(2, 7):
            t = tenants[tid]
            db.add(User(tenant_id=tid, username=f"owner_{tid}", password_hash=hp("OwnerDemo1"), role="owner",
                        constituency=t.constituency, house="Vidhan Sabha", display_name=t.name, is_active=True,
                        must_change_password=False))

        # Grievance volume per client: (tenant, cases, resolution rate, critical share)
        weights = [c[1] for c in CATEGORIES]
        case_id = 1
        for tid, total, rate in ((2, 140, 0.68), (3, 85, 0.45), (4, 40, 0.30)):
            for _ in range(total):
                age_days = rnd.random() ** 1.4 * 62  # more recent cases than old
                created = now - timedelta(days=age_days, hours=rnd.random() * 20)
                resolved = rnd.random() < rate and age_days > 1
                done = created + timedelta(days=rnd.uniform(0.5, 6)) if resolved else None
                if done and done > now:
                    done = now - timedelta(hours=1)
                category = rnd.choices([c[0] for c in CATEGORIES], weights=weights)[0]
                db.add(Case(
                    id=case_id, tenant_id=tid, user_phone=f"9199{rnd.randint(10000000, 99999999)}",
                    raw_message="(demo grievance)", category=category, status="resolved" if resolved else rnd.choice(["new", "pending"]),
                    ward=rnd.choice(WARDS), is_critical=(not resolved and rnd.random() < 0.08), is_deleted=False,
                    created_at=created, resolved_at=done,
                ))
                case_id += 1

        rajdhani = PartnerOrg(name="Rajdhani Strategy", slug="rajdhani-strategy", brand_name="Rajdhani Strategy",
                              brand_color="#B45309", show_powered_by=True, contact_email="ops@rajdhani.in",
                              wholesale_price_inr=15000, is_active=True)
        bravo = PartnerOrg(name="Bravo Campaigns", slug="bravo-campaigns", brand_name="Bravo",
                           brand_color="#1D4ED8", show_powered_by=False, contact_email="ops@bravo.in",
                           wholesale_price_inr=18000, is_active=True)
        db.add_all([rajdhani, bravo])
        db.flush()
        db.add_all([
            PartnerUser(partner_id=rajdhani.id, email=PARTNER_READY[0], display_name="Priya (Ops Lead)", password_hash=hp(PARTNER_READY[1]),
                        must_change_password=False),
            PartnerUser(partner_id=rajdhani.id, email=PARTNER_TEMP[0], display_name="New Analyst", password_hash=hp(PARTNER_TEMP[1]),
                        must_change_password=True),
            PartnerUser(partner_id=bravo.id, email=PARTNER_BRAVO[0], display_name="Bravo Ops", password_hash=hp(PARTNER_BRAVO[1]),
                        must_change_password=False),
        ])
        day = lambda n: now - timedelta(days=n)  # noqa: E731
        db.add_all([
            PartnerSeat(partner_id=rajdhani.id, tenant_id=2, client_label="Asha Patil", constituency="Belagavi South", seat_type="mla",
                        status="active", created_at=day(40), activated_at=day(38)),
            PartnerSeat(partner_id=rajdhani.id, tenant_id=3, client_label="Ravi Kulkarni", constituency="Pune Cantonment", seat_type="mla",
                        status="active", created_at=day(30), activated_at=day(28)),
            PartnerSeat(partner_id=rajdhani.id, tenant_id=4, client_label="Meera Naik", constituency="Panaji", seat_type="mla",
                        status="paused", created_at=day(25), activated_at=day(22)),
            PartnerSeat(partner_id=rajdhani.id, client_label="Sunil Deshpande", constituency="Hubballi-Dharwad West", seat_type="mla",
                        status="requested", notes="Nominations open in three weeks; needs ward-level view first.", created_at=day(2)),
            PartnerSeat(partner_id=bravo.id, client_label="Kavita Joshi", constituency="Nashik Central", seat_type="mla",
                        status="requested", notes="Pilot seat, aspirant stage.", created_at=day(1)),
        ])
        # tenants 5 and 6 are intentionally unattributed: create more tenants through the onboarding form
        # to exercise Direct vs Partner attribution; the two "requested" seats are legacy rows kept for history.
        db.commit()
    finally:
        db.close()
    # Same idempotent step the backend runs at startup: records attribution for the seeded active/paused seats.
    from modules.partners import ensure_partner_schema  # noqa: E402
    print("attribution backfill:", ensure_partner_schema())


if fresh:
    seed()

# No background jobs, sweepers, pollers or keep-alive pings in the demo.
main.app.router.on_startup.clear()

BANNER = f"""
================ Compass Needle: partner channel demo ================
 Backend        http://localhost:{args.port}        (isolated SQLite: {args.db})

 Needle admin   http://localhost:3001               {ADMIN[0]} / {ADMIN[1]}
                -> Customers -> Partners
 Partner portal http://localhost:3000/partner       {PARTNER_READY[0]} / {PARTNER_READY[1]}
   first-login  forced password change flow         {PARTNER_TEMP[0]} / {PARTNER_TEMP[1]}
   2nd partner  (cannot see Rajdhani's clients)     {PARTNER_BRAVO[0]} / {PARTNER_BRAVO[1]}
=======================================================================
"""

if __name__ == "__main__":
    import uvicorn

    print(BANNER, flush=True)
    uvicorn.run(main.app, host="127.0.0.1", port=args.port, log_level="warning")
