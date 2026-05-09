"""
CSR Pipeline — Connects SansadX grievances to CSR funding opportunities.

Complaint clusters are surfaced as areas that need field verification before
any outreach to companies. Volume thresholds are internal signals only.
"""
import logging
from sqlalchemy import text
from sansadx_backend.unified_taxonomy import canonicalize_category, convergence_sector_for

logger = logging.getLogger("needle.csr_pipeline")

# --- CONFIGURATION ---
CSR_PROPOSAL_THRESHOLD = 200 # Internal threshold to surface cluster for field verification
CSR_MONITOR_THRESHOLD = 100 # Internal threshold to begin tracking a cluster

# Category → Convergence Sector mapping now lives in unified_taxonomy.py


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
    Clusters are internal signals for where to investigate — not eligibility certificates.
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

    sample_query = text("""
        SELECT category, raw_message, location, assembly
        FROM cases
        WHERE tenant_id = :tid
          AND status = 'completed'
          AND raw_message IS NOT NULL
          AND raw_message != ''
        ORDER BY created_at DESC
        LIMIT 80
    """)

    try:
        with engine.connect() as conn:
            rows = conn.execute(category_query, {"tid": tenant_id, "threshold": min_threshold}).fetchall()
            area_rows = conn.execute(area_query, {"tid": tenant_id}).fetchall()
            sample_rows = conn.execute(sample_query, {"tid": tenant_id}).fetchall()

        # Build per-area lookup keyed by category
        areas_by_category = {}
        for row in area_rows:
            cat = row[0]
            if cat not in areas_by_category:
                areas_by_category[cat] = []
            areas_by_category[cat].append({"area": row[1], "volume": row[2]})

        samples_by_category = {}
        for row in sample_rows:
            cat = row[0]
            if cat not in samples_by_category:
                samples_by_category[cat] = []
            if len(samples_by_category[cat]) >= 5:
                continue
            samples_by_category[cat].append({
                "message": (row[1] or "")[:260],
                "location": row[2],
                "assembly": row[3],
            })

        clusters = []
        for row in rows:
            raw_category = row[0]
            category = canonicalize_category(raw_category)
            volume = row[1]
            clusters.append({
                "category": category,
                "volume": volume,
                "first_report": row[2],
                "last_report": row[3],
                "progress_pct": min(100, int((volume / CSR_PROPOSAL_THRESHOLD) * 100)),
                "status": "verify" if volume >= CSR_PROPOSAL_THRESHOLD else "watch",
                "csr_sector": convergence_sector_for(category),
                "affected_areas": areas_by_category.get(raw_category, []),
                "representative_messages": samples_by_category.get(raw_category, []),
            })
        return clusters
    except Exception as e:
        logger.warning(f"Pipeline query failed: {e}")
        return []


def get_csr_candidates(tenant_id):
    """Returns clusters above the upper threshold — flagged for field verification."""
    clusters = get_grievance_clusters(tenant_id, CSR_PROPOSAL_THRESHOLD)
    return [c for c in clusters if c["status"] == "verify"]


def get_monitoring_clusters(tenant_id):
    """Returns clusters being tracked (100-199 complaints)."""
    clusters = get_grievance_clusters(tenant_id, CSR_MONITOR_THRESHOLD)
    return [c for c in clusters if c["status"] == "watch"]


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
    You are drafting a CSR Concept Note on behalf of a constituency office.
    This is a pre-meeting document to initiate dialogue with a company's CSR team.
    It is NOT a formal proposal and does not constitute any approval or commitment.

    TARGET COMPANY: {company_name}
    CONSTITUENCY: {constituency}

    CONTEXT:
    - Issue: {cluster['category']} ({cluster['csr_sector']})
    - Constituency: {constituency}
    - Affected areas: {', '.join(a['area'] for a in cluster.get('affected_areas', [])) or constituency}
    - Active period: {days_active}

    STRUCTURE:
    1. Problem Summary: What the issue is and its geographic scope in {constituency}.
    2. Proposed Intervention: What type of project could address the need.
    3. Estimated Beneficiaries: Conservative estimate.
    4. Indicative Budget: Conservative cost range for discussion.
    5. SDG Alignment: Relevant UN Sustainable Development Goals.
    6. Contact: Office of the MP, {constituency} (for follow-up queries).

    IMPORTANT CONSTRAINTS:
    - The MP is not in the statutory CSR approval chain. Decisions rest with the company's
      CSR Committee and Board under Section 135 of the Companies Act 2013.
    - Do not frame the MP as a decision-maker, approver, or project champion in the document.
    - Do not include any MP endorsement or sign-off line implying authority over the project.
    - Tone: Professional, factual. Do NOT fabricate any statistics beyond what is provided.
    """
    return ask_openai(prompt, temperature=0.5)
