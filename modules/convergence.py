"""Convergence planning helpers.

This module bridges three signals:
- grievance clusters (citizen demand)
- government scheme route from prs_schemes (public delivery path)
- CSR complement (company-funded support that should not replace government duty)
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
import re

from sqlalchemy import text


@dataclass(frozen=True)
class ConvergenceRule:
    department: str
    gap_type: str
    recommended_pathway: str
    csr_suitability: str
    csr_complement: str
    evidence_needed: tuple[str, ...]
    next_action: str
    keywords: tuple[str, ...]
    ministry_terms: tuple[str, ...]


_DEFAULT_RULE = ConvergenceRule(
    department="District Administration / relevant line department",
    gap_type="implementation_or_access_gap",
    recommended_pathway="government_first",
    csr_suitability="facilitation_only",
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
        csr_suitability="csr_complement_allowed",
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
        csr_suitability="csr_complement_allowed",
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
        csr_suitability="csr_complement_allowed",
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
        csr_suitability="facilitation_only",
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
        csr_suitability="facilitation_only",
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
        csr_suitability="csr_complement_allowed",
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
        csr_suitability="csr_complement_allowed",
        csr_complement="Fund counselling, awareness, accessibility upgrades, nutrition support, skill-building, or NGO-led community support where department permissions exist.",
        evidence_needed=(
            "Community or beneficiary need summary",
            "Department/NGO verification",
            "Safeguarding and privacy review",
        ),
        next_action="Verify sensitivity and department ownership before involving CSR or NGO partners.",
        keywords=("women", "child", "anganwadi", "poshan", "nutrition", "disability", "accessible", "safety", "empowerment"),
        ministry_terms=("women", "child", "social justice", "tribal", "minority", "disabilities"),
    ),
    "law & order": ConvergenceRule(
        department="Police Department / District Administration",
        gap_type="public_safety_gap",
        recommended_pathway="government_first",
        csr_suitability="government_only",
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
}

_EXCLUDED_CATEGORIES = {
    "bureaucratic / administrative",
    "bureaucratic",
    "administrative",
    "personal",
    "personal request",
    "individual grievance",
}

_CONVERGENCE_CATEGORIES = set(_RULES.keys())

_ISSUE_TERMS = {
    "water": ("water", "drinking", "jal", "pipeline", "tap", "paani", "pani"),
    "road": ("road", "sadak", "street", "pothole", "connectivity", "bridge"),
    "sanitation": ("sanitation", "swachh", "toilet", "drain", "drainage", "sewer", "garbage", "waste"),
    "electricity": ("electricity", "power", "light", "streetlight", "transformer", "bijli"),
    "school": ("school", "student", "classroom", "teacher", "education", "shiksha"),
    "health": ("health", "hospital", "clinic", "phc", "ambulance", "medical"),
    "housing": ("housing", "awas", "pmay", "house", "allotment", "land"),
    "welfare": ("pension", "ration", "beneficiary", "subsidy", "pds", "dbt"),
}

_RURAL_TERMS = {
    "village", "gram", "gramin", "panchayat", "rural", "taluka", "block", "gaon", "wadi",
}
_URBAN_TERMS = {
    "urban", "municipal", "municipality", "city", "ward", "nagar", "slum", "corporation",
}
_GENERIC_MATCH_TERMS = {
    "issue", "issues", "support", "community", "service", "delivery", "scheme", "mission",
}
_REGION_TERMS_BY_STATE = {
    "andhra pradesh": ("andhra pradesh", "vijayawada", "visakhapatnam", "amaravati"),
    "arunachal pradesh": ("arunachal pradesh", "itanagar"),
    "assam": ("assam", "guwahati"),
    "bihar": ("bihar", "patna"),
    "chhattisgarh": ("chhattisgarh", "raipur"),
    "delhi": ("delhi", "new delhi", "nct of delhi"),
    "goa": ("goa", "panaji"),
    "gujarat": ("gujarat", "ahmedabad", "surat", "vadodara", "gandhinagar"),
    "haryana": ("haryana", "gurugram", "faridabad", "panchkula"),
    "himachal pradesh": ("himachal pradesh", "shimla"),
    "jharkhand": ("jharkhand", "ranchi"),
    "karnataka": ("karnataka", "bengaluru", "bangalore", "belagavi", "belgaum", "mysuru", "mangalore"),
    "kerala": ("kerala", "kochi", "thiruvananthapuram", "kozhikode"),
    "madhya pradesh": ("madhya pradesh", "bhopal", "indore", "jabalpur"),
    "maharashtra": ("maharashtra", "mumbai", "pune", "nagpur", "aurangabad", "nashik"),
    "manipur": ("manipur", "imphal"),
    "meghalaya": ("meghalaya", "shillong"),
    "mizoram": ("mizoram", "aizawl"),
    "nagaland": ("nagaland", "kohima"),
    "odisha": ("odisha", "bhubaneswar", "cuttack"),
    "punjab": ("punjab", "amritsar", "ludhiana", "jalandhar"),
    "rajasthan": ("rajasthan", "jaipur", "jodhpur", "udaipur"),
    "sikkim": ("sikkim", "gangtok"),
    "tamil nadu": ("tamil nadu", "chennai", "coimbatore", "madurai"),
    "telangana": ("telangana", "hyderabad", "warangal"),
    "tripura": ("tripura", "agartala"),
    "uttar pradesh": ("uttar pradesh", "lucknow", "kanpur", "varanasi", "ghaziabad"),
    "uttarakhand": ("uttarakhand", "dehradun"),
    "west bengal": ("west bengal", "kolkata", "howrah"),
    "andaman and nicobar islands": ("andaman", "nicobar", "port blair"),
    "chandigarh": ("chandigarh",),
    "dadra and nagar haveli and daman and diu": ("dadra", "nagar haveli", "daman", "diu"),
    "jammu and kashmir": ("jammu", "kashmir", "srinagar"),
    "ladakh": ("ladakh", "leh", "kargil"),
    "lakshadweep": ("lakshadweep",),
    "puducherry": ("puducherry", "pondicherry"),
}


def is_convergence_eligible(category: str | None) -> bool:
    key = (category or "").strip().lower()
    if not key or key in _EXCLUDED_CATEGORIES:
        return False
    return key in _CONVERGENCE_CATEGORIES


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


def _context_text(affected_areas: list[dict] | None, representative_messages: list[dict] | None) -> str:
    areas = " ".join(str(area.get("area", "")) for area in (affected_areas or []) if isinstance(area, dict))
    messages = " ".join(
        str(item.get("message", "")) for item in (representative_messages or []) if isinstance(item, dict)
    )
    assemblies = " ".join(
        str(item.get("assembly", "")) for item in (representative_messages or []) if isinstance(item, dict)
    )
    return " ".join([areas, messages, assemblies]).strip()


def _issue_terms_from_text(text_value: str) -> set[str]:
    lowered = (text_value or "").lower()
    terms: set[str] = set()
    for canonical, variants in _ISSUE_TERMS.items():
        matched_variants = {variant for variant in variants if variant in lowered}
        if matched_variants:
            terms.update(matched_variants)
            terms.add(canonical)
    return terms


def infer_settlement_context(affected_areas: list[dict] | None, representative_messages: list[dict] | None) -> str:
    words = _words(_context_text(affected_areas, representative_messages))
    rural_hits = len(words & _RURAL_TERMS)
    urban_hits = len(words & _URBAN_TERMS)
    if rural_hits > urban_hits:
        return "rural"
    if urban_hits > rural_hits:
        return "urban"
    return "unknown"


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


def _region_terms_for_state(state: str | None) -> set[str]:
    state_key = (state or "").strip().lower()
    if not state_key:
        return set()
    terms = set(_REGION_TERMS_BY_STATE.get(state_key, ()))
    terms.add(state_key)
    return terms


def _scheme_region_terms(haystack: str) -> set[str]:
    found: set[str] = set()
    lowered = (haystack or "").lower()
    for terms in _REGION_TERMS_BY_STATE.values():
        for term in terms:
            if term and term in lowered:
                found.add(term)
    return found


def _is_region_compatible(row: dict, state: str | None) -> bool:
    """Reject schemes that explicitly belong to another state/UT or city."""
    expected_terms = _region_terms_for_state(state)
    if not expected_terms:
        return True

    scheme_terms = _scheme_region_terms(_scheme_haystack(row))
    if not scheme_terms:
        return True
    return bool(scheme_terms & expected_terms)


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


def _parse_jsonish(value):
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return None


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


def _fetch_scheme_intelligence(names: list[str], state: str | None = None) -> dict[str, dict]:
    engine = _get_engine()
    if not engine or not names:
        return {}

    out = {}
    for name in names:
        row = None
        try:
            with engine.connect() as conn:
                row = conn.execute(text("""
                    SELECT scheme_name, structured_intel, pq_count_at_gen, generated_at, is_stale
                    FROM scheme_intelligence_cache
                    WHERE scheme_name = :name
                      AND (:state = '' OR state = :state)
                    ORDER BY CASE WHEN state = :state THEN 0 ELSE 1 END, generated_at DESC
                    LIMIT 1
                """), {"name": name, "state": state or ""}).mappings().fetchone()
        except Exception:
            try:
                with engine.connect() as conn:
                    row = conn.execute(text("""
                        SELECT scheme_name, structured_intel, pq_count_at_gen, generated_at, is_stale
                        FROM scheme_intelligence_cache
                        WHERE scheme_name = :name
                        LIMIT 1
                    """), {"name": name}).mappings().fetchone()
            except Exception:
                row = None

        if row:
            out[name] = {
                "structured_intel": _parse_jsonish(row.get("structured_intel")) or {},
                "pq_count_at_gen": int(row.get("pq_count_at_gen") or 0),
                "generated_at": _date_out(row.get("generated_at")),
                "is_stale": bool(row.get("is_stale")),
            }
    return out


def _first_present(*values) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()[:260]
    return None


def _scheme_intel_highlights(intel: dict) -> dict:
    payload = intel.get("structured_intel") or {}
    your_state = payload.get("your_state") or {}
    national = payload.get("national_picture") or {}
    state_fund = your_state.get("fund_flow") or {}
    state_impl = your_state.get("implementation") or {}
    national_fund = national.get("fund_flow") or {}
    national_gaps = national.get("challenges_acknowledged") or {}
    latest = national.get("latest_position") or {}

    return {
        "state_specific_fact": _first_present(
            state_fund.get("received"),
            state_fund.get("utilization"),
            your_state.get("beneficiaries"),
            state_impl.get("progress"),
        ),
        "implementation_gap": _first_present(
            state_impl.get("challenges"),
            state_fund.get("discrepancies"),
            national_gaps.get("gaps"),
            national_gaps.get("pending_issues"),
            national_gaps.get("delays"),
        ),
        "fund_signal": _first_present(
            state_fund.get("received"),
            state_fund.get("utilization"),
            national_fund.get("allocated"),
            national_fund.get("released"),
            national_fund.get("utilization_pct"),
        ),
        "recent_parliament_position": _first_present(latest.get("statement")),
        "cache_generated_at": intel.get("generated_at"),
        "cache_stale": intel.get("is_stale", False),
        "pq_count_at_generation": intel.get("pq_count_at_gen", 0),
    }


def rank_prs_schemes(
    category: str | None,
    csr_sector: str | None = None,
    affected_areas: list[dict] | None = None,
    representative_messages: list[dict] | None = None,
    state: str | None = None,
    *,
    limit: int = 5,
) -> list[dict]:
    """Rank relevant government schemes from prs_schemes only."""
    key = (category or "").strip().lower()
    rule = _RULES.get(key, _DEFAULT_RULE)
    context_text = _context_text(affected_areas, representative_messages)
    context_words = _words(context_text)
    issue_terms = _issue_terms_from_text(" ".join([category or "", csr_sector or "", context_text]))
    settlement_context = infer_settlement_context(affected_areas, representative_messages)
    query_terms = (
        _words(category or "")
        | _words(csr_sector or "")
        | _words(context_text)
        | issue_terms
        | set(rule.keywords)
        | set(rule.ministry_terms)
    )

    ranked = []
    for row in _fetch_prs_schemes():
        if not _is_region_compatible(row, state):
            continue
        haystack = _scheme_haystack(row)
        ministry = str(row.get("ministry") or "").lower()
        name = str(row.get("name") or "").lower()
        answer_count = int(row.get("answer_count") or 0)
        matched_terms = sorted(term for term in query_terms if term and term in haystack)
        if not matched_terms:
            continue
        strong_terms = (set(matched_terms) & (issue_terms | set(rule.keywords) | set(rule.ministry_terms))) - _GENERIC_MATCH_TERMS
        if not strong_terms:
            continue

        score = 0.0
        score += len(matched_terms) * 6
        score += sum(24 for term in issue_terms if term in haystack)
        score += sum(16 for term in issue_terms if term in name)
        score += sum(12 for term in rule.keywords if term in name)
        score += sum(10 for term in rule.ministry_terms if term in ministry)
        score += min(20, answer_count) * 1.5
        score += math.log1p(max(answer_count, 0)) * 4
        if settlement_context == "urban" and any(term in haystack for term in ("urban", "amrut", "municipal")):
            score += 28
        if settlement_context == "rural" and any(term in haystack for term in ("rural", "gram", "gramin", "jal jeevan", "pmgsy")):
            score += 28
        explicit_sanitation = bool({"sanitation", "drain", "drainage", "garbage", "waste", "toilet"} & context_words)
        if (
            settlement_context == "urban"
            and "amrut" in haystack
            and ({"water", "sewer", "sewerage"} & issue_terms)
            and not explicit_sanitation
        ):
            score += 35
        if "swachh" in haystack and explicit_sanitation:
            score += 75
        if "sadak" in haystack and ({"road", "sadak", "pothole", "connectivity"} & issue_terms):
            score += 35
        if "jal jeevan" in haystack and settlement_context == "rural" and ({"water", "drinking", "jal"} & issue_terms):
            score += 35

        ranked.append((score, answer_count, row, matched_terms))

    ranked.sort(key=lambda item: (item[0], item[1], item[2].get("name") or ""), reverse=True)
    selected = [
        {
            "id": row.get("id"),
            "name": row.get("name"),
            "full_name": row.get("full_name") or row.get("name"),
            "ministry": row.get("ministry"),
            "answer_count": answer_count,
            "fit_score": round(score, 1),
            "fit": _fit_reason(row, matched_terms, answer_count),
            "matched_terms": matched_terms[:8],
            "source": "prs_schemes",
            "first_seen": _date_out(row.get("first_seen")),
            "last_seen": _date_out(row.get("last_seen")),
        }
        for score, answer_count, row, matched_terms in ranked[:limit]
    ]

    intelligence = _fetch_scheme_intelligence(
        [scheme["name"] for scheme in selected if scheme.get("name")],
        state,
    )
    for scheme in selected:
        scheme["intelligence"] = _scheme_intel_highlights(intelligence.get(scheme["name"], {}))
    return selected


def build_convergence_plan(
    category: str | None,
    csr_sector: str | None = None,
    affected_areas: list[dict] | None = None,
    representative_messages: list[dict] | None = None,
    state: str | None = None,
) -> dict:
    """Return a product-ready convergence plan using prs_schemes for scheme matches."""
    key = (category or "").strip().lower()
    rule = _RULES.get(key, _DEFAULT_RULE)
    ranked_schemes = rank_prs_schemes(
        category,
        csr_sector,
        affected_areas,
        representative_messages,
        state,
        limit=5,
    )
    settlement_context = infer_settlement_context(affected_areas, representative_messages)
    return {
        "eligible_for_convergence": is_convergence_eligible(category),
        "department": rule.department,
        "schemes": ranked_schemes,
        "scheme_source": "prs_schemes",
        "scheme_match_status": "ranked" if ranked_schemes else "no_prs_schemes_match",
        "settlement_context": settlement_context,
        "state": state or "",
        "representative_messages": representative_messages or [],
        "gap_type": rule.gap_type,
        "recommended_pathway": rule.recommended_pathway,
        "csr_suitability": rule.csr_suitability,
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
