"""
csr_data_loader.py — Migrate static CSR JSON files into the csr_companies DB table.

Parses ₹-amount strings, normalises emoji-contaminated type/status/sector values,
computes derived fields (avg_ticket_size, total_3y), and upserts all records.
Called once from main.py on startup — safe to run repeatedly (upsert logic).
"""
import json
import re
import logging
from datetime import datetime

logger = logging.getLogger("needle.csr_data_loader")


# ─────────────────────────────────────────
# AMOUNT PARSING
# ─────────────────────────────────────────
def parse_spend_amount(s) -> float | None:
    """
    Parse Indian rupee spend strings to float in ₹ Lakhs.

    Examples:
      "₹79 L"       → 79.0
      "₹248 Lakhs"  → 248.0
      "₹2.5 Cr"     → 250.0   (1 Crore = 100 Lakhs)
      "N/A" / ""    → None
    """
    if not s:
        return None
    s = str(s).replace('₹', '').replace(',', '').strip()
    if not s or s.upper() in ('N/A', 'NIL', '-', '0'):
        return None
    m = re.match(r'([\d.]+)\s*(L|Lakh|Lakhs|lakh|lakhs|Cr|Crore|crore|cr)?', s, re.IGNORECASE)
    if not m:
        return None
    value = float(m.group(1))
    unit = (m.group(2) or '').lower()
    if unit in ('cr', 'crore'):
        return round(value * 100, 2)   # Crore → Lakhs
    return round(value, 2)


# ─────────────────────────────────────────
# NORMALISATION MAPS
# ─────────────────────────────────────────
_SECTOR_MAP = {
    'education & skill development': ['Education', 'Skill Dev'],
    'education and skill development': ['Education', 'Skill Dev'],
    'rural development': ['Rural Dev'],
    'rural dev': ['Rural Dev'],
    'water & sanitation': ['Water', 'Sanitation'],
    'water and sanitation': ['Water', 'Sanitation'],
    'healthcare': ['Health'],
    'health': ['Health'],
    'community dev': ['Community Dev'],
    'community development': ['Community Dev'],
    'skill dev': ['Skill Dev'],
    'skill development': ['Skill Dev'],
    'renewable energy': ['Renewable Energy'],
    'energy': ['Renewable Energy'],
    'education': ['Education'],
    'water': ['Water'],
    'sanitation': ['Sanitation'],
    'infrastructure': ['Infrastructure'],
    'cancer care': ['Health'],
    'n/a': [],
}


def derive_sector_priorities(sector: str) -> list:
    """Return a normalised list of sector priority tags from the raw sector string."""
    key = (sector or '').lower().strip()
    if key in _SECTOR_MAP:
        return _SECTOR_MAP[key]
    # Not in map — clean up the raw value and return as single-item list
    cleaned = sector.strip() if sector else ''
    return [cleaned] if cleaned and cleaned.upper() != 'N/A' else []


def normalize_company_type(t: str) -> str:
    """Normalise type variants (including emoji prefixes) to 'local' or 'remote'."""
    t = (t or '').lower()
    if 'local' in t:
        return 'local'
    return 'remote'


def normalize_status(s: str) -> str:
    """Normalise status variants to 'active', 'zero_spend', or 'compliant'."""
    s = (s or '').lower()
    if 'zero' in s or 'violation' in s:
        return 'zero_spend'
    if 'compli' in s:
        return 'compliant'
    return 'active'


def make_slug(name: str) -> str:
    """Convert company name to a URL-safe slug."""
    slug = (name or '').lower()
    slug = re.sub(r'[^\w\s-]', '', slug)       # remove special chars
    slug = re.sub(r'[\s_]+', '-', slug)         # spaces → hyphens
    slug = re.sub(r'-{2,}', '-', slug)          # collapse multiple hyphens
    return slug.strip('-')


# ─────────────────────────────────────────
# SEEDER
# ─────────────────────────────────────────
def seed_csr_companies():
    """
    Read csr_db.json and csr_discovery.json, deduplicate by company name,
    enrich all fields, and upsert into the csr_companies table.

    - First occurrence of a company name wins (csr_db.json takes precedence).
    - Preserves manually-set contact_person, contact_email, notes on update.
    - Safe to call on every application startup.
    """
    try:
        from sansadx_backend.db import engine, Base
        from sqlalchemy import text as sql_text
    except ImportError:
        logger.error("DB engine not available — skipping CSR company seed")
        return

    # Ensure table exists
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        logger.error(f"csr_companies table creation failed: {e}")
        return

    # Load raw JSON data
    all_raw = []
    for path in ['csr_db.json', 'csr_discovery.json']:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                all_raw += json.load(f)
        except FileNotFoundError:
            logger.debug(f"{path} not found — skipping")
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error in {path}: {e}")

    if not all_raw:
        logger.warning("No CSR source data found — csr_companies table will be empty")
        return

    # Deduplicate: first occurrence wins
    seen = set()
    records = []
    for r in all_raw:
        name = (r.get('Company') or '').strip()
        if name and name not in seen:
            seen.add(name)
            records.append(r)

    logger.info(f"Seeding {len(records)} CSR companies (from {len(all_raw)} raw records)…")
    now = datetime.utcnow()
    inserted = updated = skipped = 0

    for r in records:
        name = (r.get('Company') or '').strip()
        if not name:
            skipped += 1
            continue

        # Parse spend amounts
        spend_history = r.get('Spend_History') or {}
        s2022 = parse_spend_amount(spend_history.get('2022-23'))
        s2023 = parse_spend_amount(spend_history.get('2023-24'))
        s2024 = parse_spend_amount(spend_history.get('2024-25'))

        # Compute totals from parsed values; fall back to Total_3Y string
        parsed_values = [x for x in (s2022, s2023, s2024) if x is not None]
        parsed_total = sum(parsed_values) if parsed_values else (parse_spend_amount(r.get('Total_3Y')) or 0.0)
        years_with_data = len(parsed_values) or 1
        avg_ticket = round(parsed_total / years_with_data, 2) if parsed_total else None

        raw_status = normalize_status(r.get('Status', ''))
        sector = (r.get('Sector') or 'N/A').strip()
        sector_priorities = derive_sector_priorities(sector)

        params = {
            'name': name,
            'slug': make_slug(name),
            'district': (r.get('District') or '').strip(),
            'state': 'Maharashtra',
            'company_type': normalize_company_type(r.get('Type', '')),
            'sector': sector,
            'sector_priorities': json.dumps(sector_priorities),
            'spend_2022_23': s2022,
            'spend_2023_24': s2023,
            'spend_2024_25': s2024,
            'total_3y_lakhs': round(parsed_total, 2) if parsed_total else None,
            'avg_ticket_size_lakhs': avg_ticket,
            'status': raw_status,
            'has_unspent_obligation': raw_status == 'zero_spend',
            'gap_analysis': (r.get('Gap_Analysis') or '').strip(),
            'last_enriched_at': now,
        }

        try:
            with engine.begin() as conn:
                existing = conn.execute(
                    sql_text("SELECT id FROM csr_companies WHERE name = :name"),
                    {'name': name}
                ).fetchone()

                if existing:
                    # Update enrichment fields; preserve manually-set relationship data
                    conn.execute(sql_text("""
                        UPDATE csr_companies SET
                            slug = :slug, district = :district, state = :state,
                            company_type = :company_type, sector = :sector,
                            sector_priorities = :sector_priorities,
                            spend_2022_23 = :spend_2022_23,
                            spend_2023_24 = :spend_2023_24,
                            spend_2024_25 = :spend_2024_25,
                            total_3y_lakhs = :total_3y_lakhs,
                            avg_ticket_size_lakhs = :avg_ticket_size_lakhs,
                            status = :status,
                            has_unspent_obligation = :has_unspent_obligation,
                            gap_analysis = :gap_analysis,
                            last_enriched_at = :last_enriched_at
                        WHERE name = :name
                    """), params)
                    updated += 1
                else:
                    conn.execute(sql_text("""
                        INSERT INTO csr_companies (
                            name, slug, district, state, company_type, sector,
                            sector_priorities, spend_2022_23, spend_2023_24, spend_2024_25,
                            total_3y_lakhs, avg_ticket_size_lakhs, status,
                            has_unspent_obligation, unspent_obligation_lakhs,
                            gap_analysis, last_enriched_at, created_at
                        ) VALUES (
                            :name, :slug, :district, :state, :company_type, :sector,
                            :sector_priorities, :spend_2022_23, :spend_2023_24, :spend_2024_25,
                            :total_3y_lakhs, :avg_ticket_size_lakhs, :status,
                            :has_unspent_obligation, NULL,
                            :gap_analysis, :last_enriched_at, :created_at
                        )
                    """), {**params, 'created_at': now})
                    inserted += 1
        except Exception as e:
            logger.warning(f"Seed failed for '{name}': {e}")
            skipped += 1

    logger.info(
        f"CSR company seed complete — inserted: {inserted}, updated: {updated}, skipped: {skipped}"
    )
