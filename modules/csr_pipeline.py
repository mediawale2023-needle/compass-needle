"""
CSR Pipeline — Connects SansadX grievances to CSR funding opportunities.

When 200+ complaints about the same issue accumulate in a specific area,
the system auto-flags it as a CSR Proposal Candidate.
"""
import logging
from sqlalchemy import text
from datetime import datetime, timedelta

logger = logging.getLogger("needle.csr_pipeline")

# --- CONFIGURATION ---
CSR_PROPOSAL_THRESHOLD = 200 # Minimum complaints to qualify for CSR proposal
CSR_MONITOR_THRESHOLD = 100 # Minimum complaints to start monitoring

# Category → CSR Sector mapping
CATEGORY_SECTOR_MAP = {
    "Water": "Water & Sanitation",
    "Infrastructure": "Rural Development",
    "Infrastructure (State)": "Rural Development",
    "Energy": "Renewable Energy",
    "Education (Central)": "Education & Skill Development",
    "Public Health": "Healthcare",
    "Sanitation": "Swachh Bharat",
    "Civic Amenities": "Community Development",
    "Transport": "Rural Development",
    "Food Supply": "Food Security",
}


def _get_engine():
    """Safely import the database engine."""
    try:
        from sansadx_backend.db import engine
        return engine
    except ImportError:
        return None


def get_grievance_clusters(tenant_id, min_threshold=CSR_MONITOR_THRESHOLD):
    """
    Fetch grievance clusters grouped by category (constituency-level) that meet the threshold.
    Each cluster aggregates complaints across all micro-areas into one opportunity per issue type.
    Returns list of dicts with cluster data including affected_areas breakdown.
    """
    engine = _get_engine()
    if not engine:
        return []

    # Total volume per issue type across the whole constituency
    category_query = text("""
        SELECT
            category,
            COUNT(*) as volume,
            MIN(created_at) as first_report,
            MAX(created_at) as last_report
        FROM cases
        WHERE tenant_id = :tid
          AND status = 'completed'
          AND location IS NOT NULL
          AND location != ''
        GROUP BY category
        HAVING COUNT(*) >= :threshold
        ORDER BY volume DESC
    """)

    # Per-area breakdown for the dropdown
    area_query = text("""
        SELECT
            category,
            location,
            COUNT(*) as area_volume
        FROM cases
        WHERE tenant_id = :tid
          AND status = 'completed'
          AND location IS NOT NULL
          AND location != ''
        GROUP BY category, location
        ORDER BY category, area_volume DESC
    """)

    try:
        with engine.connect() as conn:
            rows = conn.execute(category_query, {"tid": tenant_id, "threshold": min_threshold}).fetchall()
            area_rows = conn.execute(area_query, {"tid": tenant_id}).fetchall()

        # Build per-area lookup keyed by category
        areas_by_category = {}
        for row in area_rows:
            cat = row[0]
            if cat not in areas_by_category:
                areas_by_category[cat] = []
            areas_by_category[cat].append({"area": row[1], "volume": row[2]})

        clusters = []
        for row in rows:
            category = row[0]
            volume = row[1]
            clusters.append({
                "category": category,
                "volume": volume,
                "first_report": row[2],
                "last_report": row[3],
                "progress_pct": min(100, int((volume / CSR_PROPOSAL_THRESHOLD) * 100)),
                "status": "ready" if volume >= CSR_PROPOSAL_THRESHOLD else "monitoring",
                "csr_sector": CATEGORY_SECTOR_MAP.get(category, "General CSR"),
                "affected_areas": areas_by_category.get(category, []),
            })
        return clusters
    except Exception as e:
        logger.warning(f"Pipeline query failed: {e}")
        return []


def get_csr_candidates(tenant_id):
    """Returns clusters that have crossed the 200-complaint threshold (CSR-ready)."""
    clusters = get_grievance_clusters(tenant_id, CSR_PROPOSAL_THRESHOLD)
    return [c for c in clusters if c["status"] == "ready"]


def get_monitoring_clusters(tenant_id):
    """Returns clusters approaching threshold (100-199 complaints)."""
    clusters = get_grievance_clusters(tenant_id, CSR_MONITOR_THRESHOLD)
    return [c for c in clusters if c["status"] == "monitoring"]


def match_companies(csr_sector, csr_data):
    """Match a CSR sector with companies from the discovery database."""
    matches = []
    for company in csr_data:
        company_sector = company.get("Sector", "")
        if csr_sector.lower() in company_sector.lower() or company_sector.lower() in csr_sector.lower():
            matches.append(company)
    return matches[:5] # Top 5 matches


def generate_csr_proposal(cluster, company_name, constituency="the constituency"):
    """Generate a data-backed CSR proposal using real grievance data."""
    days_active = "N/A"
    if cluster.get("first_report") and cluster.get("last_report"):
        try:
            delta = cluster["last_report"] - cluster["first_report"]
            days_active = f"{delta.days} days"
        except Exception:
            pass

    prompt = f"""
    Act as a Senior CSR Consultant for an Indian Member of Parliament.
    Write a 'Detailed Project Proposal' (DPR) Executive Summary.

    TARGET COMPANY: {company_name}
    CONSTITUENCY: {constituency}

    DATA-BACKED EVIDENCE:
    - Issue: {cluster['category']} ({cluster['csr_sector']})
    - Constituency: {constituency}
    - Affected areas: {', '.join(a['area'] for a in cluster.get('affected_areas', [])) or constituency}
    - Verified citizen reports: {cluster['volume']} unique complaints
    - Active period: {days_active}
    - This is NOT an estimate — these are real, verified citizen grievances collected via WhatsApp.

    STRUCTURE:
    1. Executive Summary: Why this project is urgent (cite the {cluster['volume']} verified reports).
    2. Project Scope: What needs to be built/fixed across the affected areas in {constituency}.
    3. Impact Assessment: Number of beneficiaries (based on complaint volume).
    4. Budget Estimate: Conservative cost estimate for the project.
    5. SDG Alignment: Which UN Sustainable Development Goals this addresses.
    6. Branding Value: How {company_name} gets visibility (wall branding, plaques, press coverage).
    7. MP Endorsement Line: Space for the MP to sign as the project champion.

    Tone: Professional, data-driven, ready-to-sign. Do NOT fabricate any statistics beyond what is provided.
    """
    return ask_openai(prompt, temperature=0.5)
