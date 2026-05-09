"""Convergence planning helpers.

This module bridges three signals:
- grievance clusters (citizen demand)
- government scheme route from prs_schemes (public delivery path)
- CSR complement (company-funded support that should not replace government duty)
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re

from sqlalchemy import text


@dataclass(frozen=True)
class ConvergenceRule:
    department: str
    gap_type: str
    recommended_pathway: str
    csr_complement: str
    evidence_needed: tuple[str, ...]
    next_action: str
    keywords: tuple[str, ...]
    ministry_terms: tuple[str, ...]


_DEFAULT_RULE = ConvergenceRule(
    department="District Administration / relevant line department",
    gap_type="implementation_or_access_gap",
    recommended_pathway="government_first",
    csr_complement="Use CSR only for complementary support after the department route is verified.",
    evidence_needed=(
        "Affected area list",
        "Representative grievance samples",
        "Department note or field verification",
    ),
    next_action="Verify the issue with the responsible department before CSR outreach.",
    keywords=("scheme", "mission", "programme", "beneficiary", "district", "service"),
    ministry_terms=("ministry", "department"),
)


_RULES: dict[str, ConvergenceRule] = {
    "infrastructure & utilities": ConvergenceRule(
        department="PWD / Urban Local Body / Water Board / Rural Development Department",
        gap_type="infrastructure_implementation_gap",
        recommended_pathway="hybrid",
        csr_complement="Fund complementary assets such as water filters, community monitoring, school WASH facilities, lighting support, awareness, or maintenance pilots without replacing government infrastructure obligations.",
        evidence_needed=(
            "Location-wise complaint cluster",
            "Photos or field verification note",
            "Relevant department/scheme status",
            "Basic beneficiary estimate",
        ),
        next_action="Ask the line department to verify scheme coverage, then prepare a CSR complement note for non-statutory support.",
        keywords=("water", "drinking", "jal", "road", "sadak", "sanitation", "swachh", "drainage", "urban", "rural", "infrastructure", "amrut", "pmgsy"),
        ministry_terms=("jal shakti", "rural development", "housing and urban affairs", "urban", "water", "sanitation", "road"),
    ),
    "health": ConvergenceRule(
        department="District Health Office / Health Department",
        gap_type="service_access_or_equipment_gap",
        recommended_pathway="hybrid",
        csr_complement="Fund ambulances, equipment, screening camps, telemedicine support, health awareness, or facility upgrades where legally permissible and department-owned.",
        evidence_needed=(
            "Facility or area list",
            "Health officer verification",
            "Service gap description",
            "Potential implementing NGO or hospital partner",
        ),
        next_action="Confirm the health department ownership and identify a CSR-eligible complementary intervention.",
        keywords=("health", "hospital", "clinic", "phc", "chc", "ayushman", "medical", "ambulance", "nutrition", "mission"),
        ministry_terms=("health", "family welfare", "ayush"),
    ),
    "education": ConvergenceRule(
        department="Education Department / Samagra Shiksha Office",
        gap_type="school_infrastructure_or_learning_gap",
        recommended_pathway="hybrid",
        csr_complement="Fund smart classrooms, toilets, drinking water, libraries, labs, remedial learning, career guidance, or digital access with school permission.",
        evidence_needed=(
            "School list",
            "Headmaster/block education officer note",
            "Student beneficiary estimate",
            "Photos or inspection note",
        ),
        next_action="Map affected schools to Samagra Shiksha coverage, then approach CSR partners for complementary facilities or learning support.",
        keywords=("education", "school", "student", "teacher", "shiksha", "poshan", "classroom", "digital", "learning", "scholarship"),
        ministry_terms=("education", "school", "women and child"),
    ),
    "housing & land": ConvergenceRule(
        department="Revenue Department / Housing Department / Urban Local Body",
        gap_type="eligibility_or_documentation_gap",
        recommended_pathway="government_first",
        csr_complement="CSR should not replace housing entitlement delivery; it may support documentation camps, awareness, assistive services, or community facilities.",
        evidence_needed=(
            "Beneficiary list or sample cases",
            "Eligibility/document gap",
            "Revenue or housing office verification",
        ),
        next_action="Resolve entitlement and documentation route first; use CSR only for facilitation or community support.",
        keywords=("housing", "awas", "pmay", "land", "property", "svamitva", "revenue", "allotment", "beneficiary"),
        ministry_terms=("housing", "urban affairs", "rural development", "panchayati raj"),
    ),
    "government schemes & welfare": ConvergenceRule(
        department="District Welfare Office / Scheme Nodal Department",
        gap_type="beneficiary_access_gap",
        recommended_pathway="government_first",
        csr_complement="CSR may support awareness camps, help desks, documentation drives, digital assistance, or NGO facilitation; it must not substitute statutory benefits.",
        evidence_needed=(
            "Beneficiary issue list",
            "Scheme name or entitlement type",
            "Nodal officer verification",
            "Documentation gap summary",
        ),
        next_action="Route through the scheme nodal officer first; consider CSR only for outreach and facilitation.",
        keywords=("welfare", "beneficiary", "pension", "ration", "pds", "food", "kisan", "subsidy", "scholarship", "social assistance", "dbt"),
        ministry_terms=("social justice", "rural development", "food", "agriculture", "minority", "tribal", "women"),
    ),
    "agriculture": ConvergenceRule(
        department="Agriculture Department / Krishi Vigyan Kendra",
        gap_type="livelihood_or_access_gap",
        recommended_pathway="hybrid",
        csr_complement="Fund farmer training, soil testing, water conservation, FPO support, equipment access, or market linkage pilots with agriculture department alignment.",
        evidence_needed=(
            "Affected farmer/area list",
            "Crop or scheme issue evidence",
            "Agriculture officer/KVK note",
        ),
        next_action="Confirm department scheme route, then package CSR support around training, equipment, or facilitation gaps.",
        keywords=("agriculture", "farmer", "kisan", "crop", "insurance", "pmfby", "irrigation", "soil", "fpo", "livelihood"),
        ministry_terms=("agriculture", "farmers", "rural development", "water"),
    ),
    "social issues": ConvergenceRule(
        department="Social Welfare Department / Women and Child Development / District Administration",
        gap_type="inclusion_or_support_gap",
        recommended_pathway="hybrid",
        csr_complement="Fund counselling, awareness, accessibility upgrades, nutrition support, skill-building, or NGO-led community support where department permissions exist.",
        evidence_needed=(
            "Community or beneficiary need summary",
            "Department/NGO verification",
            "Safeguarding and privacy review",
        ),
        next_action="Verify sensitivity and department ownership before involving CSR or NGO partners.",
        keywords=("women", "child", "anganwadi", "poshan", "nutrition", "disability", "accessible", "social", "safety", "empowerment"),
        ministry_terms=("women", "child", "social justice", "tribal", "minority", "disabilities"),
    ),
    "law & order": ConvergenceRule(
        department="Police Department / District Administration",
        gap_type="public_safety_gap",
        recommended_pathway="government_first",
        csr_complement="CSR may support non-policing complements such as lighting, CCTV in public spaces with permissions, awareness, victim support, or safe community infrastructure.",
        evidence_needed=(
            "Police or district administration verification",
            "Affected location list",
            "Safety risk assessment",
            "Permission requirements",
        ),
        next_action="Route active safety issues to authorities first; only consider CSR for lawful public-safety complements.",
        keywords=("police", "safety", "crime", "women safety", "nirbhaya", "security", "home", "victim", "cctv"),
        ministry_terms=("home affairs", "women", "child"),
    ),
    "bureaucratic / administrative": ConvergenceRule(
        department="District Administration / Department owning the service",
        gap_type="service_delivery_or_transparency_gap",
        recommended_pathway="government_first",
        csr_complement="CSR may support citizen help desks, digital literacy, documentation camps, or monitoring tools, but not replace official service delivery.",
        evidence_needed=(
            "Service issue type",
            "Office or department involved",
            "Sample cases",
            "Administrative verification",
        ),
        next_action="Escalate service-delivery failures through government channels; use CSR only for facilitation support.",
        keywords=("digital", "service", "csc", "governance", "administration", "certificate", "documentation", "transparency", "portal"),
        ministry_terms=("electronics", "information technology", "personnel", "panchayati raj"),
    ),
}


def _get_engine():
    try:
        from sansadx_backend.db import engine
        return engine
    except Exception:
        return None


def _words(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", (value or "").lower())
        if len(token) >= 3
    }


def _scheme_haystack(row: dict) -> str:
    aliases = row.get("aliases") or []
    if not isinstance(aliases, (list, tuple)):
        aliases = [str(aliases)]
    return " ".join(
        str(part or "")
        for part in (
            row.get("name"),
            row.get("full_name"),
            row.get("ministry"),
            " ".join(aliases),
        )
    ).lower()


def _fit_reason(row: dict, matched_terms: list[str], answer_count: int) -> str:
    terms = ", ".join(matched_terms[:4])
    if terms:
        return f"Ranked from prs_schemes because it matches: {terms}."
    if answer_count > 0:
        return "Ranked from prs_schemes because it has parliamentary answer history."
    return "Ranked from prs_schemes; verify fit with the responsible department."


def _date_out(value) -> str | None:
    if not value:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _fetch_prs_schemes() -> list[dict]:
    engine = _get_engine()
    if not engine:
        return []
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT id, name, full_name, ministry, aliases, answer_count, first_seen, last_seen
                FROM prs_schemes
            """)).mappings().all()
        return [dict(row) for row in rows]
    except Exception:
        return []


def rank_prs_schemes(
    category: str | None,
    csr_sector: str | None = None,
    affected_areas: list[dict] | None = None,
    *,
    limit: int = 5,
) -> list[dict]:
    """Rank relevant government schemes from prs_schemes only."""
    key = (category or "").strip().lower()
    rule = _RULES.get(key, _DEFAULT_RULE)
    area_terms = " ".join(str(area.get("area", "")) for area in (affected_areas or []) if isinstance(area, dict))
    query_terms = (
        _words(category or "")
        | _words(csr_sector or "")
        | _words(area_terms)
        | set(rule.keywords)
        | set(rule.ministry_terms)
    )

    ranked = []
    for row in _fetch_prs_schemes():
        haystack = _scheme_haystack(row)
        ministry = str(row.get("ministry") or "").lower()
        name = str(row.get("name") or "").lower()
        answer_count = int(row.get("answer_count") or 0)
        matched_terms = sorted(term for term in query_terms if term and term in haystack)
        if not matched_terms:
            continue

        score = 0.0
        score += len(matched_terms) * 12
        score += sum(16 for term in rule.keywords if term in name)
        score += sum(10 for term in rule.ministry_terms if term in ministry)
        score += min(20, answer_count) * 1.5
        score += math.log1p(max(answer_count, 0)) * 4

        ranked.append((score, answer_count, row, matched_terms))

    ranked.sort(key=lambda item: (item[0], item[1], item[2].get("name") or ""), reverse=True)
    return [
        {
            "id": row.get("id"),
            "name": row.get("name"),
            "full_name": row.get("full_name") or row.get("name"),
            "ministry": row.get("ministry"),
            "answer_count": answer_count,
            "fit_score": round(score, 1),
            "fit": _fit_reason(row, matched_terms, answer_count),
            "source": "prs_schemes",
            "first_seen": _date_out(row.get("first_seen")),
            "last_seen": _date_out(row.get("last_seen")),
        }
        for score, answer_count, row, matched_terms in ranked[:limit]
    ]


def build_convergence_plan(
    category: str | None,
    csr_sector: str | None = None,
    affected_areas: list[dict] | None = None,
) -> dict:
    """Return a product-ready convergence plan using prs_schemes for scheme matches."""
    key = (category or "").strip().lower()
    rule = _RULES.get(key, _DEFAULT_RULE)
    ranked_schemes = rank_prs_schemes(category, csr_sector, affected_areas, limit=5)
    return {
        "department": rule.department,
        "schemes": ranked_schemes,
        "scheme_source": "prs_schemes",
        "scheme_match_status": "ranked" if ranked_schemes else "no_prs_schemes_match",
        "gap_type": rule.gap_type,
        "recommended_pathway": rule.recommended_pathway,
        "csr_complement": rule.csr_complement,
        "evidence_needed": list(rule.evidence_needed),
        "next_action": rule.next_action,
        "csr_sector": csr_sector,
    }


def pathway_label(value: str | None) -> str:
    labels = {
        "government_first": "Government first",
        "csr_first": "CSR first",
        "hybrid": "Government + CSR",
    }
    return labels.get(value or "", "Government first")
