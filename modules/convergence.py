"""Deterministic convergence planning helpers.

This module bridges three signals:
- grievance clusters (citizen demand)
- government scheme / department route (public delivery path)
- CSR complement (company-funded support that should not replace government duty)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SchemeRoute:
    name: str
    ministry: str
    fit: str


@dataclass(frozen=True)
class ConvergenceRule:
    department: str
    schemes: tuple[SchemeRoute, ...]
    gap_type: str
    recommended_pathway: str
    csr_complement: str
    evidence_needed: tuple[str, ...]
    next_action: str


_DEFAULT_RULE = ConvergenceRule(
    department="District Administration / relevant line department",
    schemes=(
        SchemeRoute(
            name="Relevant Central or State Department Programme",
            ministry="Concerned Ministry / State Department",
            fit="Use official department route for eligibility, permissions, and execution ownership.",
        ),
    ),
    gap_type="implementation_or_access_gap",
    recommended_pathway="government_first",
    csr_complement="Use CSR only for complementary support after the department route is verified.",
    evidence_needed=(
        "Affected area list",
        "Representative grievance samples",
        "Department note or field verification",
    ),
    next_action="Verify the issue with the responsible department before CSR outreach.",
)


_RULES: dict[str, ConvergenceRule] = {
    "infrastructure & utilities": ConvergenceRule(
        department="PWD / Urban Local Body / Water Board / Rural Development Department",
        schemes=(
            SchemeRoute("AMRUT 2.0", "Ministry of Housing and Urban Affairs", "Urban water, sewerage, and local infrastructure gaps."),
            SchemeRoute("Jal Jeevan Mission", "Ministry of Jal Shakti", "Rural drinking water access and service delivery gaps."),
            SchemeRoute("PMGSY", "Ministry of Rural Development", "Rural road connectivity and last-mile access gaps."),
            SchemeRoute("Swachh Bharat Mission", "Ministry of Jal Shakti / MoHUA", "Sanitation, waste, and drainage-linked public health gaps."),
        ),
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
    ),
    "health": ConvergenceRule(
        department="District Health Office / Health Department",
        schemes=(
            SchemeRoute("National Health Mission", "Ministry of Health and Family Welfare", "Primary healthcare access, PHC/CHC strengthening, and service gaps."),
            SchemeRoute("Ayushman Bharat Health and Wellness Centres", "Ministry of Health and Family Welfare", "Primary care access and frontline facility gaps."),
            SchemeRoute("PM-ABHIM", "Ministry of Health and Family Welfare", "Health infrastructure and emergency preparedness gaps."),
        ),
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
    ),
    "education": ConvergenceRule(
        department="Education Department / Samagra Shiksha Office",
        schemes=(
            SchemeRoute("Samagra Shiksha", "Ministry of Education", "School infrastructure, learning support, teacher and digital gaps."),
            SchemeRoute("PM SHRI Schools", "Ministry of Education", "Model school strengthening and quality improvement opportunities."),
            SchemeRoute("PM POSHAN", "Ministry of Education", "School nutrition and kitchen/infrastructure-related support context."),
        ),
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
    ),
    "housing & land": ConvergenceRule(
        department="Revenue Department / Housing Department / Urban Local Body",
        schemes=(
            SchemeRoute("PMAY-Gramin", "Ministry of Rural Development", "Rural housing eligibility and beneficiary access gaps."),
            SchemeRoute("PMAY-Urban", "Ministry of Housing and Urban Affairs", "Urban housing eligibility, allotment, and completion gaps."),
            SchemeRoute("SVAMITVA", "Ministry of Panchayati Raj", "Property records and village land mapping context."),
        ),
        gap_type="eligibility_or_documentation_gap",
        recommended_pathway="government_first",
        csr_complement="CSR should not replace housing entitlement delivery; it may support documentation camps, awareness, assistive services, or community facilities.",
        evidence_needed=(
            "Beneficiary list or sample cases",
            "Eligibility/document gap",
            "Revenue or housing office verification",
        ),
        next_action="Resolve entitlement and documentation route first; use CSR only for facilitation or community support.",
    ),
    "government schemes & welfare": ConvergenceRule(
        department="District Welfare Office / Scheme Nodal Department",
        schemes=(
            SchemeRoute("PM-KISAN", "Ministry of Agriculture and Farmers Welfare", "Farmer benefit access and record correction gaps."),
            SchemeRoute("National Food Security Act / PDS", "Department of Food and Public Distribution", "Ration access and delivery gaps."),
            SchemeRoute("National Social Assistance Programme", "Ministry of Rural Development", "Pension and vulnerable beneficiary access gaps."),
        ),
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
    ),
    "agriculture": ConvergenceRule(
        department="Agriculture Department / Krishi Vigyan Kendra",
        schemes=(
            SchemeRoute("PM-KISAN", "Ministry of Agriculture and Farmers Welfare", "Farmer income support access and record gaps."),
            SchemeRoute("PMFBY", "Ministry of Agriculture and Farmers Welfare", "Crop insurance claim and coverage issues."),
            SchemeRoute("RKVY", "Ministry of Agriculture and Farmers Welfare", "State agriculture infrastructure and innovation support."),
        ),
        gap_type="livelihood_or_access_gap",
        recommended_pathway="hybrid",
        csr_complement="Fund farmer training, soil testing, water conservation, FPO support, equipment access, or market linkage pilots with agriculture department alignment.",
        evidence_needed=(
            "Affected farmer/area list",
            "Crop or scheme issue evidence",
            "Agriculture officer/KVK note",
        ),
        next_action="Confirm department scheme route, then package CSR support around training, equipment, or facilitation gaps.",
    ),
    "social issues": ConvergenceRule(
        department="Social Welfare Department / Women and Child Development / District Administration",
        schemes=(
            SchemeRoute("Mission Shakti", "Ministry of Women and Child Development", "Women safety, support services, and empowerment gaps."),
            SchemeRoute("Saksham Anganwadi and Poshan 2.0", "Ministry of Women and Child Development", "Nutrition, anganwadi, and child development gaps."),
            SchemeRoute("Accessible India Campaign", "Department of Empowerment of Persons with Disabilities", "Accessibility and disability inclusion gaps."),
        ),
        gap_type="inclusion_or_support_gap",
        recommended_pathway="hybrid",
        csr_complement="Fund counselling, awareness, accessibility upgrades, nutrition support, skill-building, or NGO-led community support where department permissions exist.",
        evidence_needed=(
            "Community or beneficiary need summary",
            "Department/NGO verification",
            "Safeguarding and privacy review",
        ),
        next_action="Verify sensitivity and department ownership before involving CSR or NGO partners.",
    ),
    "law & order": ConvergenceRule(
        department="Police Department / District Administration",
        schemes=(
            SchemeRoute("Nirbhaya Fund initiatives", "Ministry of Women and Child Development / Home Affairs", "Women safety and public safety infrastructure context."),
            SchemeRoute("Police Modernisation / State Police Schemes", "Ministry of Home Affairs / State Home Department", "Public safety infrastructure and response gaps."),
        ),
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
    ),
    "bureaucratic / administrative": ConvergenceRule(
        department="District Administration / Department owning the service",
        schemes=(
            SchemeRoute("Digital India", "Ministry of Electronics and Information Technology", "Digital service access and citizen facilitation gaps."),
            SchemeRoute("Common Service Centres", "Ministry of Electronics and Information Technology", "Last-mile digital service access and documentation support."),
        ),
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
    ),
}


def build_convergence_plan(category: str | None, csr_sector: str | None = None) -> dict:
    """Return a product-ready convergence plan for a grievance opportunity."""
    key = (category or "").strip().lower()
    rule = _RULES.get(key, _DEFAULT_RULE)
    return {
        "department": rule.department,
        "schemes": [
            {"name": s.name, "ministry": s.ministry, "fit": s.fit}
            for s in rule.schemes
        ],
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
