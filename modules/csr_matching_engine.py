"""
csr_matching_engine.py — Multi-dimensional CSR opportunity ↔ company scoring.

Scoring dimensions (weights):
  35%  Sector Alignment   — overlap between opportunity sector and company sector_priorities
  25%  Geographic Score   — same district / same state / national
  25%  Urgency Score      — complaint volume + 7-day velocity
  15%  Relationship Score — existing pipeline entries, prior contact established

Final match_score = weighted sum, 0–100.
Recommended ask amount = company avg_ticket_size_lakhs × urgency_multiplier.
"""
import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger("needle.csr_matching_engine")

# ─────────────────────────────────────────
# SECTOR ALIAS MAP
# Maps normalised grievance sectors → company sector_priority tags
# ─────────────────────────────────────────
SECTOR_ALIASES: dict[str, list[str]] = {
    "Water & Sanitation": ["Water", "Sanitation", "Rural Dev"],
    "Swachh Bharat":      ["Sanitation", "Water", "Community Dev"],
    "Healthcare":         ["Health"],
    "Education & Skill Development": ["Education", "Skill Dev"],
    "Renewable Energy":   ["Renewable Energy"],
    "Rural Development":  ["Rural Dev", "Infrastructure", "Community Dev"],
    "Community Development": ["Community Dev", "Rural Dev"],
    "Food Security":      ["Health", "Community Dev"],
    "General CSR":        ["Community Dev"],
}

# ─────────────────────────────────────────
# DIMENSION SCORING FUNCTIONS
# ─────────────────────────────────────────

def score_sector_alignment(opportunity_sector: str, company: dict) -> float:
    """
    0–100 score for how well the company's sectors match the opportunity.
    Uses tag overlap between the mapped tags and company sector_priorities.
    """
    opp_tags = set(t.lower() for t in SECTOR_ALIASES.get(opportunity_sector, [opportunity_sector]))
    raw_priorities = company.get("sector_priorities") or []
    if isinstance(raw_priorities, str):
        try:
            raw_priorities = json.loads(raw_priorities)
        except Exception:
            raw_priorities = [raw_priorities]
    company_tags = set(t.lower() for t in raw_priorities)

    # Also add the raw sector field as a tag
    raw_sector = (company.get("Sector") or company.get("sector") or "").lower()
    if raw_sector:
        company_tags.add(raw_sector)

    if not opp_tags or not company_tags:
        return 10.0  # minimum non-zero for unknown sectors

    overlap = len(opp_tags & company_tags)
    max_possible = max(len(opp_tags), 1)
    # Bonus for exact primary sector match
    primary_match = any(tag in raw_sector for tag in opp_tags)
    base = min(90.0, (overlap / max_possible) * 90.0)
    bonus = 10.0 if primary_match else 0.0
    return round(min(100.0, base + bonus), 1)


def score_geographic(opportunity_area: str, company: dict) -> float:
    """
    0–100 score for geographic relevance.
      Local company, same district  → 100
      Local company, different area → 60
      Remote company                → 30
      No district info              → 20
    """
    company_type = (company.get("company_type") or company.get("Type") or "").lower()
    is_local = "local" in company_type
    company_district = (company.get("District") or company.get("district") or "").lower()
    opp_area_lower = (opportunity_area or "").lower()

    if is_local:
        if company_district and company_district in opp_area_lower:
            return 100.0
        if company_district and opp_area_lower and (
            company_district[:4] in opp_area_lower or opp_area_lower[:4] in company_district
        ):
            return 75.0
        return 60.0
    else:
        # Remote company — still viable but deprioritised
        return 30.0


def score_urgency(volume: int, velocity_7d: int) -> float:
    """
    0–100 urgency score from complaint volume and recent velocity.
    Volume contribution  (cap 500): 60%
    Velocity contribution (cap 50): 40%
    """
    vol_score = min(60.0, (volume / 500.0) * 60.0)
    vel_score = min(40.0, (velocity_7d / 50.0) * 40.0)
    return round(vol_score + vel_score, 1)


def score_relationship(company_name: str, tenant_id: int) -> float:
    """
    0–100 score from relationship signals:
      Pipeline entry exists                      → +40
      Pipeline entry at contacted/proposal_sent  → +20 extra
      Pipeline entry at negotiating/approved     → +30 extra
      contact_person set in company record       → +10
    """
    try:
        from core.db_helpers import _q, _q_one
        # Check pipeline entries for this tenant + company
        entries = _q("""
            SELECT stage FROM csr_pipeline_entries
            WHERE tenant_id = :tid AND LOWER(company_name) = LOWER(:name)
            ORDER BY created_at DESC
            LIMIT 3
        """, {"tid": tenant_id, "name": company_name})

        if not entries:
            return 0.0

        base = 40.0
        stages = [e.get("stage", "") for e in entries]
        advanced_stages = {"contacted", "proposal_sent", "negotiating", "approved", "funded"}
        if any(s in advanced_stages for s in stages):
            if any(s in {"negotiating", "approved", "funded"} for s in stages):
                base += 30.0
            else:
                base += 20.0

        # Check if contact_person set
        co = _q_one("SELECT contact_person FROM csr_companies WHERE LOWER(name) = LOWER(:n)", {"n": company_name})
        if co and co.get("contact_person"):
            base += 10.0

        return min(100.0, base)
    except Exception:
        return 0.0


def compute_match_score(
    opportunity_sector: str,
    opportunity_area: str,
    volume: int,
    velocity_7d: int,
    company: dict,
    tenant_id: int,
) -> dict:
    """
    Compute the full multi-dimensional match score for one company against one opportunity.

    Returns a dict with all sub-scores and the composite match_score.
    """
    sector_score = score_sector_alignment(opportunity_sector, company)
    geo_score = score_geographic(opportunity_area, company)
    urgency_score = score_urgency(volume, velocity_7d)
    rel_score = score_relationship(company.get("Company") or company.get("name", ""), tenant_id)

    # Weighted composite
    composite = round(
        sector_score * 0.35
        + geo_score * 0.25
        + urgency_score * 0.25
        + rel_score * 0.15,
        1
    )

    # Recommended ask amount: avg ticket × urgency multiplier
    avg_ticket = company.get("avg_ticket_size_lakhs") or 0.0
    urgency_mult = 1.0 + (urgency_score / 100.0) * 0.5  # 1.0 → 1.5×
    recommended_ask = round(avg_ticket * urgency_mult, 1) if avg_ticket else None

    return {
        "match_score": composite,
        "sector_alignment_score": sector_score,
        "geographic_score": geo_score,
        "urgency_score": urgency_score,
        "relationship_score": rel_score,
        "recommended_ask_amount": recommended_ask,
        "ask_rationale": _build_rationale(sector_score, geo_score, urgency_score, rel_score, recommended_ask),
    }


def _build_rationale(sector: float, geo: float, urgency: float, rel: float, ask: float | None) -> str:
    """Generate a one-line human-readable rationale for the match score."""
    parts = []
    if sector >= 70:
        parts.append("strong sector alignment")
    elif sector >= 40:
        parts.append("moderate sector overlap")
    else:
        parts.append("weak sector match")

    if geo >= 80:
        parts.append("same district (local)")
    elif geo >= 50:
        parts.append("regional proximity")
    else:
        parts.append("national reach only")

    if urgency >= 70:
        parts.append("high-urgency cluster")
    elif urgency >= 40:
        parts.append("moderate urgency")

    if rel >= 40:
        parts.append("existing relationship")

    rationale = "Match based on: " + ", ".join(parts) + "."
    if ask:
        rationale += f" Suggested ask: ₹{ask}L."
    return rationale


# ─────────────────────────────────────────
# BULK SCORING — score all companies against an opportunity
# ─────────────────────────────────────────

def rank_companies_for_opportunity(
    opportunity: dict,
    companies: list,
    tenant_id: int,
    top_n: int = 10,
) -> list:
    """
    Score all companies against a single opportunity and return top_n ranked results.

    opportunity: dict with keys category, area, volume, velocity_7d, csr_sector
    companies: list of company dicts from _load_csr_data()
    Returns sorted list of {company, scores...} dicts.
    """
    results = []
    sector = opportunity.get("csr_sector") or opportunity.get("category", "General CSR")
    area = opportunity.get("area", "")
    volume = opportunity.get("volume", 0)
    velocity_7d = opportunity.get("velocity_7d", 0)

    for company in companies:
        try:
            scores = compute_match_score(
                opportunity_sector=sector,
                opportunity_area=area,
                volume=volume,
                velocity_7d=velocity_7d,
                company=company,
                tenant_id=tenant_id,
            )
            results.append({
                "company_name": company.get("Company") or company.get("name"),
                "company_id": company.get("id"),
                "slug": company.get("slug"),
                "district": company.get("District") or company.get("district"),
                "sector": company.get("Sector") or company.get("sector"),
                "total_3y_lakhs": company.get("total_3y_lakhs"),
                "avg_ticket_size_lakhs": company.get("avg_ticket_size_lakhs"),
                "company_type": company.get("company_type") or company.get("Type"),
                **scores,
            })
        except Exception as e:
            logger.debug(f"Scoring failed for {company.get('Company')}: {e}")

    results.sort(key=lambda x: x["match_score"], reverse=True)
    return results[:top_n]


# ─────────────────────────────────────────
# PERSIST MATCHES — upsert into DB
# ─────────────────────────────────────────

def persist_matches(opportunity_id: int, tenant_id: int, ranked: list):
    """
    Upsert scored matches into opportunity_company_matches table.
    Called by the background scoring job.
    """
    try:
        from sansadx_backend.db import engine
        from sqlalchemy import text
        now = datetime.utcnow()
        with engine.begin() as conn:
            # Delete stale matches for this opportunity
            conn.execute(
                text("DELETE FROM opportunity_company_matches WHERE opportunity_id = :oid"),
                {"oid": opportunity_id}
            )
            for r in ranked:
                if not r.get("company_id"):
                    continue
                conn.execute(text("""
                    INSERT INTO opportunity_company_matches
                        (opportunity_id, company_id, tenant_id, match_score,
                         sector_alignment_score, geographic_score, urgency_score,
                         relationship_score, recommended_ask_amount, ask_rationale, computed_at)
                    VALUES
                        (:oid, :cid, :tid, :ms, :ss, :gs, :us, :rs, :ask, :rat, :now)
                """), {
                    "oid": opportunity_id,
                    "cid": r["company_id"],
                    "tid": tenant_id,
                    "ms": r["match_score"],
                    "ss": r["sector_alignment_score"],
                    "gs": r["geographic_score"],
                    "us": r["urgency_score"],
                    "rs": r["relationship_score"],
                    "ask": r.get("recommended_ask_amount"),
                    "rat": r.get("ask_rationale"),
                    "now": now,
                })
        logger.info(f"Persisted {len(ranked)} matches for opportunity {opportunity_id}")
    except Exception as e:
        logger.warning(f"Failed to persist matches for opportunity {opportunity_id}: {e}")


# ─────────────────────────────────────────
# FIT SCORE — Company-first 5-dimensional matching
#
# Distinct from compute_match_score:
#   - Replaces urgency_score (an opportunity property) with:
#       funding_window_score  — is it the right time in the budget cycle?
#       historical_score      — has the company funded this sector before?
#   - Urgency is still used for ask-amount calculation but not for fit
#   - Weights: sector 30%, geo 20%, funding_window 20%, history 15%, relationship 15%
# ─────────────────────────────────────────

def score_funding_window() -> float:
    """
    0–100 score based on India's CSR budget cycle (April–March FY).
    Companies set annual CSR budgets in April. By January most budgets are exhausted.
    Used to time outreach — a high score means now is a good time to pitch.
    """
    month = datetime.utcnow().month
    if month == 4:            # Fresh FY — Board just approved budget
        return 100.0
    elif month in (5, 6):     # Q1 — active decisions, most budget available
        return 85.0
    elif month in (7, 8, 9):  # Q2 — mid-cycle, ~50% committed
        return 65.0
    elif month in (10, 11):   # Q3 — 70–80% committed
        return 40.0
    elif month == 12:          # Q3 end — nearly locked, pitch for next FY
        return 25.0
    else:                      # Jan–Mar (Q4) — budget exhausted or already allocated
        return 15.0


def score_historical_similarity(opportunity_sector: str, company_name: str, tenant_id: int) -> tuple:
    """
    Check csr_impact_reports for prior projects by this company in the same sector.
    Returns (score 0–100, list of similar project summaries, up to 3).
    """
    try:
        from core.db_helpers import _q
        rows = _q("""
            SELECT project_title, sector, location, utilised_amount_lakhs,
                   beneficiary_count, status
            FROM csr_impact_reports
            WHERE tenant_id = :tid AND LOWER(company_name) = LOWER(:name)
            ORDER BY created_at DESC
            LIMIT 10
        """, {"tid": tenant_id, "name": company_name})

        if not rows:
            return 0.0, []

        opp_tags = set(t.lower() for t in SECTOR_ALIASES.get(opportunity_sector, [opportunity_sector]))
        similar = []
        sector_match_count = 0

        for r in rows:
            project_sector = (r.get("sector") or "").lower()
            is_similar = bool(opp_tags) and any(tag in project_sector for tag in opp_tags)
            if is_similar:
                sector_match_count += 1
                similar.append({
                    "title": r.get("project_title"),
                    "sector": r.get("sector"),
                    "location": r.get("location"),
                    "amount_lakhs": r.get("utilised_amount_lakhs"),
                    "beneficiaries": r.get("beneficiary_count"),
                    "status": r.get("status"),
                })

        # base 30 if any CSR history exists, +25 per similar-sector project (capped at +70)
        base = 30.0
        bonus = min(70.0, sector_match_count * 25.0)
        return round(min(100.0, base + bonus), 1), similar[:3]
    except Exception:
        return 0.0, []


def fit_score(opportunity: dict, company: dict, tenant_id: int) -> dict:
    """
    5-dimensional fit score measuring how well a company aligns with an opportunity.

    Uses company-first logic internally: company priorities drive the match.
    Urgency (complaint volume/velocity) is an opportunity property — kept for ask-amount
    calculation but not counted in the fit score itself.

    Weights:
        30%  Sector Alignment      — does the company fund this sector?
        20%  Geographic Score      — local presence vs national reach
        20%  Funding Window        — is it the right time in the budget cycle?
        15%  Historical Similarity — has the company funded similar projects before?
        15%  Relationship Score    — existing pipeline entries / prior contact

    Returns a dict with all sub-scores, composite fit_score, similar_projects, and
    recommended_ask_amount (derived from urgency, separate from fit).
    """
    company_name = company.get("Company") or company.get("name", "")
    sector = opportunity.get("csr_sector") or opportunity.get("category", "General CSR")
    area = opportunity.get("area", "")

    sector_s = score_sector_alignment(sector, company)
    geo_s = score_geographic(area, company)
    window_s = score_funding_window()
    hist_s, similar_projects = score_historical_similarity(sector, company_name, tenant_id)
    rel_s = score_relationship(company_name, tenant_id)

    composite = round(
        sector_s * 0.30
        + geo_s * 0.20
        + window_s * 0.20
        + hist_s * 0.15
        + rel_s * 0.15,
        1,
    )

    # Ask amount uses urgency (opportunity property) — kept separate from fit
    avg_ticket = company.get("avg_ticket_size_lakhs") or 0.0
    urgency_s = score_urgency(opportunity.get("volume", 0), opportunity.get("velocity_7d", 0))
    urgency_mult = 1.0 + (urgency_s / 100.0) * 0.5
    recommended_ask = round(avg_ticket * urgency_mult, 1) if avg_ticket else None

    return {
        "fit_score": composite,
        "sector_alignment_score": sector_s,
        "geographic_score": geo_s,
        "funding_window_score": window_s,
        "historical_score": hist_s,
        "relationship_score": rel_s,
        "similar_projects": similar_projects,
        "recommended_ask_amount": recommended_ask,
    }


def _build_recommendation_reason(
    company_name: str,
    scores: dict,
    company: dict,
    opportunity: dict,
) -> str:
    """Generate an MP-readable briefing line explaining why this company is recommended."""
    parts = []
    sector_s = scores.get("sector_alignment_score", 0)
    geo_s = scores.get("geographic_score", 0)
    window_s = scores.get("funding_window_score", 0)
    hist_s = scores.get("historical_score", 0)
    rel_s = scores.get("relationship_score", 0)
    similar = scores.get("similar_projects", [])
    area = opportunity.get("area", "the area")
    opp_sector = opportunity.get("csr_sector") or opportunity.get("category", "this sector")

    if sector_s >= 70:
        parts.append(f"{opp_sector} is a core priority sector for this company")
    elif sector_s >= 40:
        parts.append(f"partial overlap with {opp_sector}")

    if geo_s >= 90:
        parts.append(f"local presence in {area}")
    elif geo_s >= 60:
        parts.append("regional presence in the state")
    else:
        parts.append("national-level funder, no local office")

    if similar:
        prev = similar[0]
        parts.append(
            f"funded similar project: {prev.get('title', 'similar work')} "
            f"in {prev.get('location', 'the region')}"
        )
    elif hist_s >= 30:
        parts.append("prior CSR spending history on record")

    if window_s >= 85:
        parts.append("Q1 budget window is open")
    elif window_s >= 60:
        parts.append("mid-cycle — some budget still available")
    elif window_s >= 30:
        parts.append("late cycle — target April for fresh allocation")
    else:
        parts.append("Q4 — pitch now to get on next FY plan")

    if rel_s >= 60:
        parts.append("existing relationship on record")
    elif rel_s >= 40:
        parts.append("prior contact established")

    if not parts:
        return "Potential fit based on sector and geography."
    return ". ".join(p[0].upper() + p[1:] for p in parts) + "."


def _determine_next_action(scores: dict, opportunity: dict) -> tuple:
    """
    Returns (action_key, approach_text) for the MP's recommended first step.

    Rules (in priority order):
    1. Existing relationship + good fit → DPR (skip cold outreach)
    2. Funded similar projects → Meeting (leverage their track record)
    3. Local company + no prior contact → Meeting (warm intro first)
    4. Strong sector fit, no relationship → DPR + MP cover letter
    5. Default → Meeting
    """
    rel_s = scores.get("relationship_score", 0)
    hist_s = scores.get("historical_score", 0)
    geo_s = scores.get("geographic_score", 0)
    sector_s = scores.get("sector_alignment_score", 0)
    volume = opportunity.get("volume", 0)
    area = opportunity.get("area", "the constituency")

    if rel_s >= 60:
        return (
            "dpr",
            f"You have an existing relationship. Generate a DPR citing the {volume} verified "
            f"complaints in {area} and share directly with their CSR head.",
        )
    if hist_s >= 50 and sector_s >= 60:
        return (
            "meeting",
            f"This company has funded similar projects before — a warm conversation beats a cold "
            f"DPR. Request a meeting and bring the {volume}-complaint cluster as evidence.",
        )
    if geo_s >= 90 and rel_s == 0:
        return (
            "meeting",
            "Local company with no prior contact. Identify the CSR head (HR or Sustainability "
            "dept) and request an introductory meeting before sending any formal proposal.",
        )
    if sector_s >= 70 and rel_s == 0:
        return (
            "dpr",
            "Strong sector alignment — send a well-structured DPR with an MP cover letter. "
            "Include grievance data to demonstrate verified community need.",
        )
    return (
        "meeting",
        "Start with an introductory call to understand their current CSR priorities "
        "before committing to a formal DPR.",
    )


def build_company_recommendation(opportunity: dict, company: dict, tenant_id: int) -> dict:
    """
    Build a full MP-facing recommendation for one company against one opportunity.
    Includes fit scores, narrative reason, prior project evidence, and next-action guidance.
    Called by get_top_companies_for_opportunity.
    """
    scores = fit_score(opportunity, company, tenant_id)
    company_name = company.get("Company") or company.get("name", "")
    similar = scores.get("similar_projects", [])
    reason = _build_recommendation_reason(company_name, scores, company, opportunity)
    action_key, approach = _determine_next_action(scores, opportunity)

    return {
        "name": company_name,
        "company_id": company.get("id"),
        "slug": company.get("slug"),
        "district": company.get("District") or company.get("district"),
        "sector": company.get("Sector") or company.get("sector"),
        "company_type": company.get("company_type") or company.get("Company_Type") or company.get("Type"),
        "avg_ticket_size_lakhs": company.get("avg_ticket_size_lakhs"),
        "total_3y_lakhs": company.get("total_3y_lakhs"),
        "match_score": scores["fit_score"],
        "sector_alignment_score": scores["sector_alignment_score"],
        "geographic_score": scores["geographic_score"],
        "funding_window_score": scores["funding_window_score"],
        "historical_score": scores["historical_score"],
        "relationship_score": scores["relationship_score"],
        "recommended_ask_amount": scores.get("recommended_ask_amount"),
        "reason": reason,
        "has_funded_similar": len(similar) > 0,
        "similar_projects": similar,
        "suggested_next_action": action_key,
        "suggested_approach": approach,
    }


def get_top_companies_for_opportunity(
    opportunity: dict,
    companies: list,
    tenant_id: int,
    top_n: int = 3,
) -> list:
    """
    Score all companies against one opportunity using fit_score (5-dimensional),
    return top N with full MP-facing recommendation enrichment.

    This is the primary entry point for the opportunity-first matching flow.
    Company-first logic is used internally: company priorities filter the match,
    but output is surfaced per-opportunity for the MP.
    """
    results = []
    for company in companies:
        try:
            rec = build_company_recommendation(opportunity, company, tenant_id)
            if rec["match_score"] > 0:
                results.append(rec)
        except Exception as e:
            logger.debug(
                f"fit_score failed for {company.get('Company') or company.get('name')}: {e}"
            )

    results.sort(key=lambda x: x["match_score"], reverse=True)
    return results[:top_n]
