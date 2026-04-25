"""
Authoritative grievance taxonomy for classification and convergence workflows.

This module is the single source of truth for:
1) problem_domain (the official 9 grievance categories)
2) problem_subdomain (controlled operational taxonomy)
3) convergence_program_type (controlled bridge layer for convergence / CSR)
4) ingestion aliases and legacy labels that must normalize into canonical values
"""

from __future__ import annotations

from typing import Iterable


CANONICAL_CATEGORIES = (
    "Infrastructure & Utilities",
    "Housing & Land",
    "Health",
    "Education",
    "Government Schemes & Welfare",
    "Agriculture",
    "Social Issues",
    "Law & Order",
    "Bureaucratic / Administrative",
)

VALID_CATEGORIES = set(CANONICAL_CATEGORIES)
DEFAULT_PROBLEM_DOMAIN = CANONICAL_CATEGORIES[0]
GENERIC_DOMAIN_INPUTS = {"", "general", "general grievance", "uncategorised", "uncategorized"}


PROBLEM_SUBDOMAINS_BY_DOMAIN = {
    "Infrastructure & Utilities": (
        "Roads & Bridges",
        "Power & Street Lighting",
        "Water Supply",
        "Drainage/Sewage",
        "Solid Waste",
        "Public Transport",
        "Telecom/Connectivity",
    ),
    "Housing & Land": (
        "PMAY/Housing Eligibility",
        "Land Records/Mutation",
        "Encroachment/Dispute",
        "Eviction/Slum",
        "Building Permission/Illegal Construction",
    ),
    "Health": (
        "Facility Access (PHC/CHC/Hospital)",
        "Staff Availability",
        "Medicines/Diagnostics",
        "Emergency/Ambulance",
        "Maternal/Child Health",
        "Public Health Outbreak/Vector",
    ),
    "Education": (
        "Teacher Availability",
        "School Infrastructure",
        "Mid-day Meal/Anganwadi",
        "Scholarships/Benefits",
        "Higher Education/Admissions",
    ),
    "Government Schemes & Welfare": (
        "PDS/Ration",
        "Pension",
        "MGNREGA",
        "PM-KISAN",
        "Ujjwala/LPG",
        "Financial Inclusion (Jan Dhan/Banking)",
        "Labour/Social Security",
    ),
    "Agriculture": (
        "Crop Loss/Compensation",
        "Irrigation",
        "MSP/Procurement/Mandi",
        "Fertilizer/Seed/Input",
        "KCC/Credit",
        "Livestock/Veterinary",
    ),
    "Social Issues": (
        "Caste Discrimination",
        "Gender-based Violence",
        "Child Marriage/Child Labour",
        "Substance Abuse",
        "Communal Tension",
        "Community Conflict",
    ),
    "Law & Order": (
        "FIR/Police Inaction",
        "Theft/Assault/Violent Crime",
        "Sexual Crimes",
        "Kidnapping/Missing",
        "Cybercrime/Fraud",
        "Threat/Extortion",
    ),
    "Bureaucratic / Administrative": (
        "Certificates/ID Documents",
        "Application Delays",
        "Bribery/Corruption",
        "Office Accessibility/Service Failure",
        "Tax/Registration/Revenue Office",
    ),
}

SUBDOMAIN_TO_DOMAIN = {
    subdomain: domain
    for domain, subdomains in PROBLEM_SUBDOMAINS_BY_DOMAIN.items()
    for subdomain in subdomains
}
VALID_PROBLEM_SUBDOMAINS = set(SUBDOMAIN_TO_DOMAIN)

DEFAULT_PROBLEM_SUBDOMAIN_BY_DOMAIN = {
    domain: subdomains[0]
    for domain, subdomains in PROBLEM_SUBDOMAINS_BY_DOMAIN.items()
}


CONVERGENCE_PROGRAM_TYPES = (
    "Public Asset Upgrade",
    "Service Delivery Strengthening",
    "Digitization/Data Systems",
    "Last-mile Access & Outreach",
    "Community Capacity/O&M",
    "Safety & Inclusion Add-on",
    "Livelihood Enablement",
    "Monitoring & Transparency",
)

VALID_CONVERGENCE_PROGRAM_TYPES = set(CONVERGENCE_PROGRAM_TYPES)


CATEGORY_ALIASES = {
    "infrastructure": "Infrastructure & Utilities",
    "infrastructure & utility": "Infrastructure & Utilities",
    "infrastructure (state)": "Infrastructure & Utilities",
    "infrastructure(state)": "Infrastructure & Utilities",
    "energy": "Infrastructure & Utilities",
    "water": "Infrastructure & Utilities",
    "sanitation": "Infrastructure & Utilities",
    "civic amenities": "Infrastructure & Utilities",
    "transport": "Infrastructure & Utilities",
    "telecom": "Infrastructure & Utilities",
    "railways": "Infrastructure & Utilities",
    "road": "Infrastructure & Utilities",
    "roads": "Infrastructure & Utilities",
    "electricity": "Infrastructure & Utilities",
    "general grievance": "Infrastructure & Utilities",
    "general": "Infrastructure & Utilities",
    "revenue & land": "Housing & Land",
    "land": "Housing & Land",
    "housing": "Housing & Land",
    "land records": "Housing & Land",
    "public health": "Health",
    "health & sanitation": "Health",
    "medical": "Health",
    "healthcare": "Health",
    "education (central)": "Education",
    "education (state)": "Education",
    "school": "Education",
    "food supply": "Government Schemes & Welfare",
    "banking & finance": "Government Schemes & Welfare",
    "labor & employment": "Government Schemes & Welfare",
    "labour & employment": "Government Schemes & Welfare",
    "welfare": "Government Schemes & Welfare",
    "government schemes": "Government Schemes & Welfare",
    "schemes": "Government Schemes & Welfare",
    "pension": "Government Schemes & Welfare",
    "ration": "Government Schemes & Welfare",
    "farming": "Agriculture",
    "farmer": "Agriculture",
    "crop": "Agriculture",
    "social issue": "Social Issues",
    "caste": "Social Issues",
    "women": "Social Issues",
    "law and order": "Law & Order",
    "police": "Law & Order",
    "crime": "Law & Order",
    "security": "Law & Order",
    "bureaucratic": "Bureaucratic / Administrative",
    "administrative": "Bureaucratic / Administrative",
    "bureaucratic/administrative": "Bureaucratic / Administrative",
    "bureaucratic/ administrative": "Bureaucratic / Administrative",
    "civic admin": "Bureaucratic / Administrative",
    "external affairs": "Bureaucratic / Administrative",
    "postal services": "Bureaucratic / Administrative",
    "corruption": "Bureaucratic / Administrative",
}


LEGACY_TO_CANONICAL = {
    "Water": "Infrastructure & Utilities",
    "Infrastructure": "Infrastructure & Utilities",
    "Infrastructure (State)": "Infrastructure & Utilities",
    "Energy": "Infrastructure & Utilities",
    "Education (Central)": "Education",
    "Public Health": "Health",
    "Sanitation": "Infrastructure & Utilities",
    "Civic Amenities": "Infrastructure & Utilities",
    "Transport": "Infrastructure & Utilities",
    "Food Supply": "Government Schemes & Welfare",
    "General Grievance": "Infrastructure & Utilities",
    "General": "Infrastructure & Utilities",
}


PROBLEM_SUBDOMAIN_ALIASES = {
    "roads": "Roads & Bridges",
    "road": "Roads & Bridges",
    "bridge": "Roads & Bridges",
    "bridges": "Roads & Bridges",
    "street light": "Power & Street Lighting",
    "street lights": "Power & Street Lighting",
    "electricity": "Power & Street Lighting",
    "power": "Power & Street Lighting",
    "water": "Water Supply",
    "water supply": "Water Supply",
    "drainage": "Drainage/Sewage",
    "sewage": "Drainage/Sewage",
    "sewer": "Drainage/Sewage",
    "solid waste": "Solid Waste",
    "garbage": "Solid Waste",
    "waste": "Solid Waste",
    "public transport": "Public Transport",
    "transport": "Public Transport",
    "telecom": "Telecom/Connectivity",
    "connectivity": "Telecom/Connectivity",
    "internet": "Telecom/Connectivity",
    "network": "Telecom/Connectivity",
    "pmay": "PMAY/Housing Eligibility",
    "pm awas": "PMAY/Housing Eligibility",
    "housing eligibility": "PMAY/Housing Eligibility",
    "land record": "Land Records/Mutation",
    "land records": "Land Records/Mutation",
    "mutation": "Land Records/Mutation",
    "encroachment": "Encroachment/Dispute",
    "dispute": "Encroachment/Dispute",
    "eviction": "Eviction/Slum",
    "slum": "Eviction/Slum",
    "illegal construction": "Building Permission/Illegal Construction",
    "building permission": "Building Permission/Illegal Construction",
    "phc": "Facility Access (PHC/CHC/Hospital)",
    "chc": "Facility Access (PHC/CHC/Hospital)",
    "hospital": "Facility Access (PHC/CHC/Hospital)",
    "doctor": "Staff Availability",
    "nurse": "Staff Availability",
    "staff": "Staff Availability",
    "medicine": "Medicines/Diagnostics",
    "medicines": "Medicines/Diagnostics",
    "diagnostic": "Medicines/Diagnostics",
    "diagnostics": "Medicines/Diagnostics",
    "ambulance": "Emergency/Ambulance",
    "maternal": "Maternal/Child Health",
    "child health": "Maternal/Child Health",
    "dengue": "Public Health Outbreak/Vector",
    "malaria": "Public Health Outbreak/Vector",
    "vector": "Public Health Outbreak/Vector",
    "teacher": "Teacher Availability",
    "teachers": "Teacher Availability",
    "school infrastructure": "School Infrastructure",
    "mid day meal": "Mid-day Meal/Anganwadi",
    "mid-day meal": "Mid-day Meal/Anganwadi",
    "anganwadi": "Mid-day Meal/Anganwadi",
    "scholarship": "Scholarships/Benefits",
    "scholarships": "Scholarships/Benefits",
    "admission": "Higher Education/Admissions",
    "admissions": "Higher Education/Admissions",
    "higher education": "Higher Education/Admissions",
    "pds": "PDS/Ration",
    "ration": "PDS/Ration",
    "pension": "Pension",
    "mgnrega": "MGNREGA",
    "pm-kisan": "PM-KISAN",
    "pm kisan": "PM-KISAN",
    "ujjwala": "Ujjwala/LPG",
    "lpg": "Ujjwala/LPG",
    "jan dhan": "Financial Inclusion (Jan Dhan/Banking)",
    "banking": "Financial Inclusion (Jan Dhan/Banking)",
    "bank": "Financial Inclusion (Jan Dhan/Banking)",
    "labour": "Labour/Social Security",
    "labor": "Labour/Social Security",
    "social security": "Labour/Social Security",
    "crop loss": "Crop Loss/Compensation",
    "compensation": "Crop Loss/Compensation",
    "irrigation": "Irrigation",
    "mandi": "MSP/Procurement/Mandi",
    "msp": "MSP/Procurement/Mandi",
    "procurement": "MSP/Procurement/Mandi",
    "fertilizer": "Fertilizer/Seed/Input",
    "seed": "Fertilizer/Seed/Input",
    "input": "Fertilizer/Seed/Input",
    "kcc": "KCC/Credit",
    "credit": "KCC/Credit",
    "loan": "KCC/Credit",
    "livestock": "Livestock/Veterinary",
    "veterinary": "Livestock/Veterinary",
    "caste discrimination": "Caste Discrimination",
    "discrimination": "Caste Discrimination",
    "gender based violence": "Gender-based Violence",
    "domestic violence": "Gender-based Violence",
    "child marriage": "Child Marriage/Child Labour",
    "child labour": "Child Marriage/Child Labour",
    "substance abuse": "Substance Abuse",
    "alcohol": "Substance Abuse",
    "drug": "Substance Abuse",
    "communal tension": "Communal Tension",
    "community conflict": "Community Conflict",
    "fir": "FIR/Police Inaction",
    "police inaction": "FIR/Police Inaction",
    "theft": "Theft/Assault/Violent Crime",
    "assault": "Theft/Assault/Violent Crime",
    "violent crime": "Theft/Assault/Violent Crime",
    "sexual crime": "Sexual Crimes",
    "sexual crimes": "Sexual Crimes",
    "rape": "Sexual Crimes",
    "molestation": "Sexual Crimes",
    "kidnapping": "Kidnapping/Missing",
    "missing": "Kidnapping/Missing",
    "cybercrime": "Cybercrime/Fraud",
    "fraud": "Cybercrime/Fraud",
    "online fraud": "Cybercrime/Fraud",
    "threat": "Threat/Extortion",
    "extortion": "Threat/Extortion",
    "certificate": "Certificates/ID Documents",
    "id documents": "Certificates/ID Documents",
    "aadhaar": "Certificates/ID Documents",
    "aadhar": "Certificates/ID Documents",
    "voter card": "Certificates/ID Documents",
    "application delay": "Application Delays",
    "delays": "Application Delays",
    "delay": "Application Delays",
    "bribery": "Bribery/Corruption",
    "corruption": "Bribery/Corruption",
    "office accessibility": "Office Accessibility/Service Failure",
    "service failure": "Office Accessibility/Service Failure",
    "tax": "Tax/Registration/Revenue Office",
    "registration": "Tax/Registration/Revenue Office",
    "revenue office": "Tax/Registration/Revenue Office",
}


PROGRAM_TYPE_ALIASES = {
    "public asset": "Public Asset Upgrade",
    "asset upgrade": "Public Asset Upgrade",
    "service delivery": "Service Delivery Strengthening",
    "service delivery strengthening": "Service Delivery Strengthening",
    "digitization": "Digitization/Data Systems",
    "digital": "Digitization/Data Systems",
    "data systems": "Digitization/Data Systems",
    "last mile": "Last-mile Access & Outreach",
    "last-mile": "Last-mile Access & Outreach",
    "outreach": "Last-mile Access & Outreach",
    "community capacity": "Community Capacity/O&M",
    "o&m": "Community Capacity/O&M",
    "operations & maintenance": "Community Capacity/O&M",
    "safety": "Safety & Inclusion Add-on",
    "inclusion": "Safety & Inclusion Add-on",
    "safety and inclusion": "Safety & Inclusion Add-on",
    "livelihood": "Livelihood Enablement",
    "livelihood enablement": "Livelihood Enablement",
    "monitoring": "Monitoring & Transparency",
    "transparency": "Monitoring & Transparency",
}


SUBDOMAIN_TO_PROGRAM_TYPE = {
    "Roads & Bridges": "Public Asset Upgrade",
    "Power & Street Lighting": "Public Asset Upgrade",
    "Water Supply": "Public Asset Upgrade",
    "Drainage/Sewage": "Public Asset Upgrade",
    "Solid Waste": "Service Delivery Strengthening",
    "Public Transport": "Service Delivery Strengthening",
    "Telecom/Connectivity": "Digitization/Data Systems",
    "PMAY/Housing Eligibility": "Last-mile Access & Outreach",
    "Land Records/Mutation": "Digitization/Data Systems",
    "Encroachment/Dispute": "Monitoring & Transparency",
    "Eviction/Slum": "Safety & Inclusion Add-on",
    "Building Permission/Illegal Construction": "Monitoring & Transparency",
    "Facility Access (PHC/CHC/Hospital)": "Service Delivery Strengthening",
    "Staff Availability": "Service Delivery Strengthening",
    "Medicines/Diagnostics": "Service Delivery Strengthening",
    "Emergency/Ambulance": "Safety & Inclusion Add-on",
    "Maternal/Child Health": "Last-mile Access & Outreach",
    "Public Health Outbreak/Vector": "Community Capacity/O&M",
    "Teacher Availability": "Service Delivery Strengthening",
    "School Infrastructure": "Public Asset Upgrade",
    "Mid-day Meal/Anganwadi": "Last-mile Access & Outreach",
    "Scholarships/Benefits": "Last-mile Access & Outreach",
    "Higher Education/Admissions": "Livelihood Enablement",
    "PDS/Ration": "Last-mile Access & Outreach",
    "Pension": "Last-mile Access & Outreach",
    "MGNREGA": "Livelihood Enablement",
    "PM-KISAN": "Livelihood Enablement",
    "Ujjwala/LPG": "Last-mile Access & Outreach",
    "Financial Inclusion (Jan Dhan/Banking)": "Digitization/Data Systems",
    "Labour/Social Security": "Last-mile Access & Outreach",
    "Crop Loss/Compensation": "Monitoring & Transparency",
    "Irrigation": "Public Asset Upgrade",
    "MSP/Procurement/Mandi": "Service Delivery Strengthening",
    "Fertilizer/Seed/Input": "Last-mile Access & Outreach",
    "KCC/Credit": "Livelihood Enablement",
    "Livestock/Veterinary": "Service Delivery Strengthening",
    "Caste Discrimination": "Safety & Inclusion Add-on",
    "Gender-based Violence": "Safety & Inclusion Add-on",
    "Child Marriage/Child Labour": "Safety & Inclusion Add-on",
    "Substance Abuse": "Community Capacity/O&M",
    "Communal Tension": "Safety & Inclusion Add-on",
    "Community Conflict": "Community Capacity/O&M",
    "FIR/Police Inaction": "Monitoring & Transparency",
    "Theft/Assault/Violent Crime": "Safety & Inclusion Add-on",
    "Sexual Crimes": "Safety & Inclusion Add-on",
    "Kidnapping/Missing": "Safety & Inclusion Add-on",
    "Cybercrime/Fraud": "Digitization/Data Systems",
    "Threat/Extortion": "Safety & Inclusion Add-on",
    "Certificates/ID Documents": "Digitization/Data Systems",
    "Application Delays": "Monitoring & Transparency",
    "Bribery/Corruption": "Monitoring & Transparency",
    "Office Accessibility/Service Failure": "Service Delivery Strengthening",
    "Tax/Registration/Revenue Office": "Monitoring & Transparency",
}


SUBDOMAIN_SIGNALS = {
    "Roads & Bridges": ("road", "roads", "sadak", "bridge", "culvert", "pothole"),
    "Power & Street Lighting": ("bijli", "electricity", "power", "street light", "transformer", "voltage"),
    "Water Supply": ("water", "paani", "tap water", "water supply", "tanker", "drinking water"),
    "Drainage/Sewage": ("drain", "drainage", "sewage", "sewer", "nala", "water logging"),
    "Solid Waste": ("garbage", "waste", "kachra", "dumping", "cleaning"),
    "Public Transport": ("bus", "transport", "public transport", "route", "auto stand"),
    "Telecom/Connectivity": ("network", "internet", "tower", "telecom", "connectivity", "signal"),
    "PMAY/Housing Eligibility": ("pmay", "pm awas", "awas", "housing scheme", "house allotment"),
    "Land Records/Mutation": ("mutation", "khata", "khasra", "land record", "patta", "registry"),
    "Encroachment/Dispute": ("encroachment", "kabza", "dispute", "boundary", "illegal possession"),
    "Eviction/Slum": ("eviction", "slum", "jhuggi", "rehabilitation"),
    "Building Permission/Illegal Construction": ("illegal construction", "building permission", "building plan", "construction"),
    "Facility Access (PHC/CHC/Hospital)": ("hospital", "phc", "chc", "dispensary", "clinic"),
    "Staff Availability": ("doctor", "nurse", "staff", "specialist", "vacant post"),
    "Medicines/Diagnostics": ("medicine", "medicines", "test", "diagnostic", "xray", "lab"),
    "Emergency/Ambulance": ("ambulance", "emergency", "accident", "critical", "bleeding"),
    "Maternal/Child Health": ("pregnant", "delivery", "maternal", "child health", "infant", "immunization"),
    "Public Health Outbreak/Vector": ("dengue", "malaria", "outbreak", "vector", "mosquito", "epidemic"),
    "Teacher Availability": ("teacher", "teachers", "shikshak", "faculty"),
    "School Infrastructure": ("school building", "classroom", "toilet", "school infrastructure", "bench"),
    "Mid-day Meal/Anganwadi": ("mid day meal", "mid-day meal", "anganwadi", "nutrition"),
    "Scholarships/Benefits": ("scholarship", "scholarships", "stipend", "benefit"),
    "Higher Education/Admissions": ("college", "admission", "admissions", "university", "higher education"),
    "PDS/Ration": ("ration", "pds", "ration card", "food grain"),
    "Pension": ("pension", "old age", "widow pension", "disability pension"),
    "MGNREGA": ("mgnrega", "nrega", "job card", "work demand"),
    "PM-KISAN": ("pm-kisan", "pm kisan"),
    "Ujjwala/LPG": ("ujjwala", "lpg", "gas cylinder", "gas connection"),
    "Financial Inclusion (Jan Dhan/Banking)": ("jan dhan", "bank account", "banking", "bank", "atm"),
    "Labour/Social Security": ("e-shram", "eshram", "labour", "labor", "worker card", "social security"),
    "Crop Loss/Compensation": ("crop loss", "fasal nuksan", "compensation", "hailstorm", "insurance claim"),
    "Irrigation": ("irrigation", "canal", "borewell", "watering", "sprinkler"),
    "MSP/Procurement/Mandi": ("msp", "procurement", "mandi", "purchase center"),
    "Fertilizer/Seed/Input": ("fertilizer", "seed", "pesticide", "input", "urea"),
    "KCC/Credit": ("kcc", "credit", "crop loan", "loan", "bank loan"),
    "Livestock/Veterinary": ("livestock", "veterinary", "cattle", "animal", "dairy"),
    "Caste Discrimination": ("caste", "dalit", "discrimination", "untouchability", "atrocity"),
    "Gender-based Violence": ("domestic violence", "violence against women", "dowry", "harassment"),
    "Child Marriage/Child Labour": ("child marriage", "child labour", "child labor"),
    "Substance Abuse": ("alcohol", "liquor", "drug", "substance abuse", "nasha"),
    "Communal Tension": ("communal", "religious tension", "riot"),
    "Community Conflict": ("community conflict", "village clash", "local dispute"),
    "FIR/Police Inaction": ("fir", "police nahi", "police not", "police inaction", "complaint not taken"),
    "Theft/Assault/Violent Crime": ("theft", "assault", "beating", "attack", "murder", "fight"),
    "Sexual Crimes": ("rape", "molestation", "sexual harassment", "sexual assault"),
    "Kidnapping/Missing": ("kidnap", "kidnapping", "missing", "abduction"),
    "Cybercrime/Fraud": ("cyber", "fraud", "online fraud", "otp", "scam", "digital arrest"),
    "Threat/Extortion": ("threat", "extortion", "dhamki", "rangdari"),
    "Certificates/ID Documents": ("certificate", "aadhaar", "aadhar", "id card", "voter card", "domicile"),
    "Application Delays": ("delay", "delayed", "pending", "file atki", "application"),
    "Bribery/Corruption": ("bribe", "bribery", "corruption", "ghoos", "rishwat", "paise mang"),
    "Office Accessibility/Service Failure": ("office closed", "service failure", "not hearing", "seva", "accessibility"),
    "Tax/Registration/Revenue Office": ("tax", "registration", "revenue office", "stamp duty"),
}


def _norm(value: str | None) -> str:
    return str(value or "").strip()


def _lower(value: str | None) -> str:
    return _norm(value).lower()


def _search_text_blob(parts: Iterable[str | None]) -> str:
    return " ".join(_lower(part) for part in parts if _norm(part))


def _infer_subdomain_from_text(blob: str) -> tuple[str | None, str | None]:
    if not blob:
        return None, None

    for domain in CANONICAL_CATEGORIES:
        for subdomain in PROBLEM_SUBDOMAINS_BY_DOMAIN[domain]:
            for signal in SUBDOMAIN_SIGNALS.get(subdomain, ()):
                if signal in blob:
                    return domain, subdomain
    return None, None


def canonicalize_category(category: str | None) -> str:
    """Normalize any incoming category or legacy label to the canonical domain."""
    value = _norm(category)
    if not value:
        return DEFAULT_PROBLEM_DOMAIN

    if value in VALID_CATEGORIES:
        return value

    if value in LEGACY_TO_CANONICAL:
        return LEGACY_TO_CANONICAL[value]

    lowered = value.lower()
    if lowered in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[lowered]

    return DEFAULT_PROBLEM_DOMAIN


def canonicalize_problem_domain(category: str | None) -> str:
    return canonicalize_category(category)


def canonicalize_problem_subdomain(
    subdomain: str | None,
    problem_domain: str | None = None,
    raw_text: str = "",
    scheme: str | None = None,
    department: str | None = None,
) -> str:
    """
    Normalize or infer a controlled problem_subdomain for the selected domain.
    """
    domain = canonicalize_problem_domain(problem_domain)
    value = _norm(subdomain)

    if value in VALID_PROBLEM_SUBDOMAINS:
        if SUBDOMAIN_TO_DOMAIN[value] == domain:
            return value
        return DEFAULT_PROBLEM_SUBDOMAIN_BY_DOMAIN[domain]

    lowered = value.lower()
    if lowered in PROBLEM_SUBDOMAIN_ALIASES:
        candidate = PROBLEM_SUBDOMAIN_ALIASES[lowered]
        if SUBDOMAIN_TO_DOMAIN[candidate] == domain:
            return candidate

    blob = _search_text_blob((value, scheme, department, raw_text))
    if blob:
        for candidate in PROBLEM_SUBDOMAINS_BY_DOMAIN[domain]:
            for signal in SUBDOMAIN_SIGNALS.get(candidate, ()):
                if signal in blob:
                    return candidate

    return DEFAULT_PROBLEM_SUBDOMAIN_BY_DOMAIN[domain]


def canonicalize_convergence_program_type(
    program_type: str | None,
    problem_domain: str | None = None,
    problem_subdomain: str | None = None,
    raw_text: str = "",
    scheme: str | None = None,
    department: str | None = None,
) -> str:
    """
    Normalize or infer the convergence bridge label for the taxonomy tuple.
    """
    value = _norm(program_type)
    if value in VALID_CONVERGENCE_PROGRAM_TYPES:
        return value

    lowered = value.lower()
    if lowered in PROGRAM_TYPE_ALIASES:
        return PROGRAM_TYPE_ALIASES[lowered]

    subdomain = canonicalize_problem_subdomain(
        problem_subdomain,
        problem_domain=problem_domain,
        raw_text=raw_text,
        scheme=scheme,
        department=department,
    )
    return SUBDOMAIN_TO_PROGRAM_TYPE.get(subdomain, "Service Delivery Strengthening")


def build_taxonomy_fields(
    problem_domain: str | None = None,
    problem_subdomain: str | None = None,
    convergence_program_type: str | None = None,
    raw_text: str = "",
    scheme: str | None = None,
    department: str | None = None,
) -> dict:
    """
    Return canonical taxonomy fields for storage and API responses.
    """
    blob = _search_text_blob((problem_subdomain, scheme, department, raw_text))
    inferred_domain = None
    inferred_subdomain = None
    if _lower(problem_domain) in GENERIC_DOMAIN_INPUTS:
        inferred_domain, inferred_subdomain = _infer_subdomain_from_text(blob)

    domain = canonicalize_problem_domain(inferred_domain or problem_domain)
    subdomain = canonicalize_problem_subdomain(
        inferred_subdomain or problem_subdomain,
        problem_domain=domain,
        raw_text=raw_text,
        scheme=scheme,
        department=department,
    )
    program_type = canonicalize_convergence_program_type(
        convergence_program_type,
        problem_domain=domain,
        problem_subdomain=subdomain,
        raw_text=raw_text,
        scheme=scheme,
        department=department,
    )
    return {
        "problem_domain": domain,
        "problem_subdomain": subdomain,
        "convergence_program_type": program_type,
        "categories": [domain],  # legacy compatibility layer until schema migration is complete
    }


def convergence_sector_for(category: str | None) -> str:
    """
    Backwards-compatible shim for older CSR pipeline call sites.

    This now returns the canonical convergence_program_type derived from the
    authoritative taxonomy instead of a separate drifting sector label set.
    """
    fields = build_taxonomy_fields(problem_domain=category)
    return fields["convergence_program_type"]
