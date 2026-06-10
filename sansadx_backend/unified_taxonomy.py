"""
Authoritative grievance taxonomy for classification and convergence workflows.

This module is the single source of truth for:
1) problem_domain (the official 9 grievance categories)
2) problem_subdomain (controlled operational taxonomy)
3) convergence_program_type (controlled bridge layer for convergence / CSR)
4) ingestion aliases and legacy labels that must normalize into canonical values
"""

from __future__ import annotations

import re
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
    "Water Supply": ("water", "paani", "pani", "neer", "neeru", "tap water", "water supply", "tanker", "drinking water", "nal", "nalko"),
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

_CORRUPTION_EXPLICIT_MARKERS = (
    "bribe", "bribery", "corrupt", "ghoos", "ghus", "rishwat",
    "लाच", "रिश्वत", "घूस", "भ्रष्टाचार",
)

_CORRUPTION_OFFICIAL_MARKERS = (
    "talathi", "talati", "तलाठी",
    "patwari", "पटवारी",
    "tehsildar", "tahsildar", "तहसीलदार",
    "lekhpal", "लेखपाल",
    "babu", "बाबू",
    "clerk", "क्लर्क",
    "officer", "अधिकारी",
    "official", "अफसर",
    "collector", "collectorate", "collector office",
    "sdm", "एसडीएम",
    "naib tehsildar", "नायब तहसीलदार",
    "revenue office", "revenue department",
    "block office", "sarkaari daftar", "karyalay", "कार्यालय",
)

_PAYMENT_MARKERS = (
    "money", "cash", "paisa", "paise", "payment",
    "पैसा", "पैसे", "रुपया", "रुपये",
)

_DEMAND_MARKERS = (
    "ask", "asking", "asked", "demand", "demanding", "demanded",
    "mang", "maang", "magt", "magat", "maga",
    "माग", "मांग",
)

_WORKFLOW_CONTEXT_MARKERS = (
    "work", "file", "application", "approval", "certificate", "sign", "service",
    "काम", "फाइल", "अर्ज", "प्रमाणपत्र", "साइन", "सेवा",
)

_WATER_SUPPLY_MARKERS = (
    "water", "water supply", "tap water", "drinking water",
    "paani", "pani", "neer", "neeru", "nal", "nalli neer",
)

_WATER_OUTAGE_MARKERS = (
    "no water", "not coming", "not available", "supply problem",
    "illa", "illai", "bandilla", "baralla", "barthilla",
    "nahi", "nahi aata", "nahin", "band", "stopped",
)

_VENUE_CONTEXT_MARKERS = (
    "school", "college", "hospital", "depot", "office", "market", "temple",
    "masjid", "mosque", "church", "bus stop", "circle", "peetha", "vidya peetha",
)

_VENUE_NEARNESS_MARKERS = (
    "paas", "pass", "ke paas", "near", "outside", "samor", "samore",
    "baju", "bajula", "hatra", "javal", "javalcha", "adjacent",
)

_SOLID_WASTE_MARKERS = (
    "garbage", "kachra", "kacra", "kachara", "khachra", "kachre",
    "dump", "dumping", "waste", "rubbish", "trash", "litter",
)

_DRAINAGE_FAILURE_MARKERS = (
    "drain", "drainage", "sewage", "sewer", "nala", "gutter",
    "water logging", "waterlogged", "stagnant water", "dirty water",
)

_POWER_FAILURE_MARKERS = (
    "street light", "street lights", "light band", "lights band",
    "bijli", "electricity", "transformer", "voltage", "power cut",
)

_ROAD_FAILURE_MARKERS = (
    "road", "roads", "sadak", "rasta", "pothole", "khadda", "khadde",
    "bridge", "culvert", "road tutla", "road broken",
)

_DISASTER_EMERGENCY_MARKERS = (
    "flood", "flooding", "fire", "burning", "building collapse", "collapsed building",
    "landslide", "storm", "cyclone", "earthquake", "chemical leak", "gas leak",
    "dam breach", "dam burst", "industrial accident", "factory blast", "factory explosion",
    "arson", "major accident", "bridge collapse",
    "बाढ़", "आग", "आग लगी", "भूकंप", "तूफान", "चक्रवात", "इमारत गिर", "भूस्खलन",
    "रासायनिक रिसाव", "गैस रिसाव", "बांध टूट", "फैक्ट्री में धमाका",
)

_LAW_ORDER_EMERGENCY_MARKERS = (
    "murder", "attempt to murder", "assault in progress", "mob violence", "riot",
    "lynching", "mob lynching", "armed violence", "death threat", "death threats",
    "extortion threat", "kidnapping", "kidnap", "human trafficking", "public disorder",
    "religious clash", "religious clashes", "communal violence", "stone pelting",
    "attack", "attacking", "beating", "violent clash",
    "दंगा", "हिंसा", "सांप्रदायिक हिंसा", "भीड़ हिंसा", "मॉब लिंचिंग", "लिंचिंग",
    "हत्या", "मारपीट", "हमला", "अपहरण", "मानव तस्करी", "फिरौती", "धमकी",
    "पत्थरबाजी", "पथराव", "मस्जिद पर पत्थर", "धार्मिक झड़प", "सार्वजनिक अशांति",
)

_WOMEN_CHILD_DANGER_MARKERS = (
    "child marriage happening now", "child trafficking", "child labour", "child labor",
    "child abuse", "missing child", "domestic violence in progress", "sexual assault",
    "rape", "stalking", "immediate threat to woman", "woman in danger", "girl kidnapped",
    "marital rape", "molestation",
    "बाल विवाह", "बाल तस्करी", "बाल मजदूरी", "बच्चा गायब", "लापता बच्चा",
    "बच्चे के साथ मारपीट", "बच्चे के साथ दुर्व्यवहार", "घरेलू हिंसा", "बलात्कार",
    "यौन उत्पीड़न", "छेड़छाड़", "महिला को जान से खतरा", "महिला पर हमला",
)

_HEALTH_EMERGENCY_MARKERS = (
    "ambulance not available", "ambulance needed", "accident victims", "critical patient",
    "severe bleeding", "maternal emergency", "child medical emergency", "oxygen shortage",
    "hospital refusing emergency treatment", "not breathing", "heart attack", "stroke",
    "poisoning", "critical condition", "collapsed", "suicide attempt medical",
    "ambulance nahi", "ambulance bhejo",
    "एंबुलेंस नहीं", "एम्बुलेंस नहीं", "एंबुलेंस भेजो", "गंभीर मरीज", "भारी खून बह",
    "प्रसूति आपातकाल", "बच्चे की तबीयत गंभीर", "ऑक्सीजन की कमी", "अस्पताल ने इमरजेंसी इलाज से मना किया",
    "सांस नहीं आ रही", "दिल का दौरा", "जहर खा", "बेहोश",
)

_SUICIDE_RISK_MARKERS = (
    "suicide threat", "attempted suicide", "self harm", "self-harm",
    "threatening to end life", "want to die", "will kill myself", "end my life",
    "farmer suicide risk", "student suicide risk",
    "आत्महत्या", "खुदकुशी", "जान दे दूंगा", "जान दे दूँगा", "मर जाना चाहता", "अपनी जान ले",
    "किसान आत्महत्या", "छात्र आत्महत्या",
)

_PERSONAL_REQUEST_FIRST_PERSON_MARKERS = (
    "mera", "meri", "mere", "mujhe", "mere liye", "meri taraf se",
    "hamara", "hamari", "hamare", "hume", "humare liye",
    "my", "for me", "for my", "my son", "my daughter", "my brother", "my sister",
    "मेरी", "मेरा", "मेरे", "मुझे", "हमारा", "हमारी", "हमारे",
)

_PERSONAL_REQUEST_HELP_MARKERS = (
    "madad karo", "madad kijiye", "madad kare", "sahayata kijiye", "help karo",
    "help kijiye", "meri madad", "humari madad", "kripya madad", "please help",
    "aap meri madad", "office se madad", "guide karo", "margdarshan",
    "मदद करो", "मदद कीजिए", "मदद करें", "सहायता करें", "मार्गदर्शन",
)

_PERSONAL_REQUEST_TRANSFER_MARKERS = (
    "transfer", "transfer request", "tabadla", "badli", "posting", "posting request",
    "transfer karwa", "badli karwa", "tabadla karwa", "mujhe transfer",
    "ट्रांसफर", "तबादला", "बदली", "पोस्टिंग",
)

_PERSONAL_REQUEST_ADMISSION_MARKERS = (
    "admission", "school admission", "college admission", "dakhila", "pravesh",
    "seat dilwa", "admission kara", "school me admission", "college me admission",
    "school mein admission", "college mein admission",
    "एडमिशन", "दाखिला", "प्रवेश", "सीट दिलवा",
)

_PERSONAL_REQUEST_RECOMMENDATION_MARKERS = (
    "sifarish", "shifarish", "recommendation", "recommend", "recommend letter",
    "job lagwa", "naukri lagwa", "kaam karwa do", "personal favour", "personal favor",
    "सिफारिश", "नौकरी लगवा", "काम करवा",
)

_PERSONAL_REQUEST_RELATION_MARKERS = (
    "bhai", "behen", "beta", "beti", "pita", "maa", "father", "mother",
    "brother", "sister", "husband", "wife", "family", "parivar", "relative", "rishtedar",
    "भाई", "बहन", "बेटा", "बेटी", "पिता", "माँ", "मां", "परिवार", "रिश्तेदार",
)

_PERSONAL_REQUEST_PRIVATE_ASSET_MARKERS = (
    "zameen", "jameen", "land", "property", "plot", "ghar",
    "ज़मीन", "जमीन", "मकान", "घर", "प्लॉट", "संपत्ति",
)

_PERSONAL_REQUEST_CONFLICT_MARKERS = (
    "jhagda", "dispute", "vivaad", "quarrel", "ladai", "fight",
    "झगड़ा", "झगडा", "विवाद", "लड़ाई",
)

_POLITICAL_SUPPORT_MARKERS = (
    "thank you", "thanks", "thank u", "shukriya", "dhanyavaad", "dhanyavad",
    "badhai", "congratulations", "congrats", "happy birthday", "janmadin",
    "best wishes", "support you", "we support you", "samarthan", "volunteer",
    "join your campaign", "karyakarta banna", "aapka samarthan", "धन्यवाद",
    "शुक्रिया", "बधाई", "जन्मदिन", "समर्थन", "शुभकामनाएं", "शुभकामनाएँ",
)

_POLITICAL_SUPPORT_EXCLUSION_MARKERS = (
    "issue", "problem", "samasya", "complaint", "grievance", "madad", "help",
    "paani", "water", "road", "bijli", "ration", "hospital", "police", "apply",
    "status", "update", "problem", "समस्या", "मदद", "शिकायत", "पानी", "सड़क",
)

# Pure greetings / pleasantries with no grievance content. Detected via the
# residue check in looks_like_pure_greeting() (not raw substring matching) so
# that "good morning, paani problem" still routes as a grievance.
_GREETING_PHRASES = (
    "good morning", "good afternoon", "good evening", "good night", "good day",
    "very good morning", "gud morning", "gud mrng", "good mrng",
    "hello", "helo", "hii", "hiii", "hey", "hi",
    "namaste", "namaskar", "namaskaar", "namaskara", "namaskaram",
    "pranam", "pranaam", "ram ram", "jai hind", "jai shri ram", "jai shree ram",
    "jai shri krishna", "radhe radhe", "suprabhat", "shubh prabhat", "subh prabhat",
    "salaam", "salam", "adaab", "aadab", "sat sri akal", "sat sri akaal",
    "khamma ghani", "vanakkam", "shubh din", "greetings", "greeting",
    "नमस्ते", "नमस्कार", "सुप्रभात", "शुभ प्रभात", "राम राम", "जय हिंद",
    "जय श्री राम", "प्रणाम", "गुड मॉर्निंग", "शुभ दिन", "राधे राधे", "जय श्रीराम",
)

# Honorifics / filler that may accompany a bare greeting without making it a
# grievance (e.g. "Good morning sir ji").
_GREETING_FILLER = {
    "sir", "madam", "maam", "saheb", "sahab", "sahib", "sirji", "ji", "respected",
    "dear", "the", "to", "you", "u", "good", "very", "and", "a",
    "dada", "tai", "bhai", "behen", "saab", "namaste",
    "सर", "साहेब", "जी", "महोदय", "आदरणीय", "श्रीमान",
}


def looks_like_pure_greeting(blob: str) -> bool:
    """Return True only when the message is a standalone greeting/pleasantry.

    Greeting phrases are stripped out along with common honorifics/filler; if
    nothing meaningful remains, the message carries no grievance and should be
    silently logged rather than acknowledged as a complaint.
    """
    if not blob:
        return False
    lowered = blob.lower().strip()
    if not lowered or len(lowered) > 80:
        return False
    if not any(phrase in lowered for phrase in _GREETING_PHRASES):
        return False

    residue = lowered
    for phrase in sorted(_GREETING_PHRASES, key=len, reverse=True):
        residue = residue.replace(phrase, " ")
    residue = re.sub(r"[^\w\s]", " ", residue)
    tokens = [tok for tok in residue.split() if tok and tok not in _GREETING_FILLER]
    return len(tokens) == 0

_COMMUNITY_INVITATION_MARKERS = (
    "invite", "invitation", "aamantran", "amantran", "chief guest", "please attend",
    "program", "function", "event", "ceremony", "inauguration", "meeting request",
    "kindly attend", "upasthit rahein", "samaroha", "karyakram", "nimantran",
    "आमंत्रण", "कार्यक्रम", "समारोह", "उद्घाटन", "मुख्य अतिथि", "उपस्थित रहें",
)

_MEDIA_OUTREACH_MARKERS = (
    "press", "media", "interview", "press note", "statement", "clarification",
    "journalist", "reporter", "coverage", "press conference", "news byte",
    "media query", "पत्रकार", "मीडिया", "इंटरव्यू", "बयान", "स्पष्टीकरण",
    "प्रेस", "कवरेज",
)

_DONATION_REQUEST_MARKERS = (
    "donation", "donate", "sponsorship", "sponsor", "fund", "funding",
    "financial help", "financial assistance", "chanda", "arthik madad",
    "arthik sahayata", "raise funds", "CSR support", "डोनेशन", "दान",
    "सहायता राशि", "आर्थिक मदद", "आर्थिक सहायता", "स्पॉन्सरशिप", "फंड",
)

_SUGGESTION_MARKERS = (
    "suggestion", "suggestions", "idea", "ideas", "proposal", "feedback",
    "sujhav", "salah", "mera sujhav", "hamara sujhav", "citizen proposal",
    "suggest", "recommendation for improvement", "सुझाव", "सलाह", "प्रस्ताव",
    "विचार", "फीडबैक",
)

_SPAM_PROMO_MARKERS = (
    "buy now", "limited offer", "discount", "sale", "subscribe", "click link",
    "business proposal", "marketing", "promotion", "promotional", "advertisement",
    "advt", "earn money", "free recharge", "loan offer", "insurance offer",
    "chain message", "forward this", "promo", "sponsored post", "ऑफर",
    "छूट", "प्रमोशन", "विज्ञापन", "लिंक पर क्लिक", "फॉरवर्ड करें",
)

_CONTEXTLESS_MEDIA_MARKERS = (
    "photo", "image", "video", "audio", "voice note", "document", "pdf",
    "see attached", "pls see", "please see", "check this", "dekhiye", "yeh dekho",
    "attachment", "file", "फोटो", "वीडियो", "ऑडियो", "दस्तावेज", "पीडीएफ",
    "अटैचमेंट", "फाइल", "देखिए",
)

_LOCATION_CONTAINER_MARKERS = (
    "colony", "layout", "road", "street", "lane", "camp", "nagar",
    "galli", "circle", "cross", "extension", "quarters", "wadi", "peth",
)

_LOCATION_AMBIGUOUS_ISSUE_WORDS = (
    "teacher", "teachers", "doctor", "doctors", "nurse", "nurses",
    "police", "school",
)


def _has_any_marker(blob: str, markers: tuple[str, ...]) -> bool:
    return any(marker in blob for marker in markers)


def _looks_like_payment_demand(blob: str) -> bool:
    has_payment = _has_any_marker(blob, _PAYMENT_MARKERS)
    has_demand = _has_any_marker(blob, _DEMAND_MARKERS)
    return has_payment and has_demand


def _strip_location_like_phrases(blob: str) -> str:
    if not blob:
        return ""

    cleaned = blob
    for word in _LOCATION_AMBIGUOUS_ISSUE_WORDS:
        for suffix in _LOCATION_CONTAINER_MARKERS:
            cleaned = re.sub(rf"\b{re.escape(word)}\s+{re.escape(suffix)}\b", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _looks_like_water_supply_outage(blob: str) -> bool:
    cleaned = _strip_location_like_phrases(blob)
    has_water = _has_any_marker(cleaned, _WATER_SUPPLY_MARKERS)
    has_outage = _has_any_marker(cleaned, _WATER_OUTAGE_MARKERS)
    return has_water and has_outage


def _looks_like_venue_context_civic_issue(blob: str) -> tuple[str | None, str | None]:
    """
    Rescue cases where a venue/locality word like "school" appears in the
    location context, but the actual grievance is civic infrastructure nearby.
    """
    if not blob:
        return None, None

    has_venue = _has_any_marker(blob, _VENUE_CONTEXT_MARKERS)
    has_nearness = _has_any_marker(blob, _VENUE_NEARNESS_MARKERS)
    if not has_venue or not has_nearness:
        return None, None

    if _has_any_marker(blob, _SOLID_WASTE_MARKERS):
        return "Infrastructure & Utilities", "Solid Waste"
    if _has_any_marker(blob, _DRAINAGE_FAILURE_MARKERS):
        return "Infrastructure & Utilities", "Drainage/Sewage"
    if _looks_like_water_supply_outage(blob):
        return "Infrastructure & Utilities", "Water Supply"
    if _has_any_marker(blob, _POWER_FAILURE_MARKERS):
        return "Infrastructure & Utilities", "Power & Street Lighting"
    if _has_any_marker(blob, _ROAD_FAILURE_MARKERS):
        return "Infrastructure & Utilities", "Roads & Bridges"
    return None, None


def infer_emergency_taxonomy_override(blob: str) -> tuple[str | None, str | None]:
    """Return a high-confidence emergency taxonomy override for no-ack severe cases."""
    if not blob:
        return None, None

    if _has_any_marker(blob, _SUICIDE_RISK_MARKERS):
        return "Health", "Emergency/Ambulance"
    if _has_any_marker(blob, _HEALTH_EMERGENCY_MARKERS):
        return "Health", "Emergency/Ambulance"
    if _has_any_marker(blob, _WOMEN_CHILD_DANGER_MARKERS):
        if any(marker in blob for marker in ("sexual assault", "rape", "बलात्कार", "यौन उत्पीड़न", "molestation", "छेड़छाड़")):
            return "Law & Order", "Sexual Crimes"
        if any(marker in blob for marker in ("missing child", "child trafficking", "girl kidnapped", "बाल तस्करी", "लापता बच्चा", "बच्चा गायब")):
            return "Law & Order", "Kidnapping/Missing"
        if any(marker in blob for marker in ("child marriage", "child labour", "child labor", "बाल विवाह", "बाल मजदूरी")):
            return "Social Issues", "Child Marriage/Child Labour"
        return "Social Issues", "Gender-based Violence"
    if _has_any_marker(blob, _LAW_ORDER_EMERGENCY_MARKERS):
        return "Law & Order", "Theft/Assault/Violent Crime"
    if _has_any_marker(blob, _DISASTER_EMERGENCY_MARKERS):
        return "Health", "Emergency/Ambulance"
    return None, None


def infer_personal_request_category(blob: str) -> str | None:
    """Return Personal Request for explicit discretionary/private-help asks."""
    if not blob:
        return None

    has_first_person = _has_any_marker(blob, _PERSONAL_REQUEST_FIRST_PERSON_MARKERS)
    has_help = _has_any_marker(blob, _PERSONAL_REQUEST_HELP_MARKERS)
    has_transfer = _has_any_marker(blob, _PERSONAL_REQUEST_TRANSFER_MARKERS)
    has_admission = _has_any_marker(blob, _PERSONAL_REQUEST_ADMISSION_MARKERS)
    has_recommendation = _has_any_marker(blob, _PERSONAL_REQUEST_RECOMMENDATION_MARKERS)
    has_relation = _has_any_marker(blob, _PERSONAL_REQUEST_RELATION_MARKERS)
    has_private_asset = _has_any_marker(blob, _PERSONAL_REQUEST_PRIVATE_ASSET_MARKERS)
    has_conflict = _has_any_marker(blob, _PERSONAL_REQUEST_CONFLICT_MARKERS)

    if has_first_person and (has_transfer or has_admission or has_recommendation):
        return "Personal Request"

    if has_relation and has_private_asset and has_conflict and (has_help or has_first_person):
        return "Personal Request"

    return None


def infer_silent_log_category(blob: str) -> str | None:
    """Return non-grievance categories that should be logged without auto-reply."""
    if not blob:
        return None

    lowered = blob.lower()

    if _has_any_marker(lowered, _SPAM_PROMO_MARKERS):
        return "Spam / Promotional / Irrelevant"

    if _has_any_marker(lowered, _MEDIA_OUTREACH_MARKERS):
        return "Media / Press Outreach"

    if _has_any_marker(lowered, _DONATION_REQUEST_MARKERS):
        return "Donation / Sponsorship Request"

    if _has_any_marker(lowered, _COMMUNITY_INVITATION_MARKERS):
        return "Community / Event Invitation"

    if _has_any_marker(lowered, _SUGGESTION_MARKERS):
        return "Suggestion / Idea"

    if _has_any_marker(lowered, _POLITICAL_SUPPORT_MARKERS) and not _has_any_marker(
        lowered, _POLITICAL_SUPPORT_EXCLUSION_MARKERS
    ):
        return "Political / Support Message"

    if looks_like_pure_greeting(blob):
        return "Greetings"

    return None


def looks_like_contextless_media_message(blob: str) -> bool:
    """Return True for bare attachment-style messages that need more details."""
    if not blob:
        return True

    lowered = blob.lower().strip()
    token_count = len([token for token in re.split(r"\s+", lowered) if token])
    if token_count <= 4 and _has_any_marker(lowered, _CONTEXTLESS_MEDIA_MARKERS):
        return True

    generic_phrases = {
        "photo", "image", "video", "audio", "document", "pdf", "attachment",
        "see", "please see", "pls see", "check", "check this", "dekhiye", "देखिए",
    }
    return lowered in generic_phrases


def _infer_strong_taxonomy_override(blob: str) -> tuple[str | None, str | None]:
    """
    Return a high-confidence taxonomy override only for patterns where the
    text itself clearly outweighs a bad model guess.

    Keep this intentionally narrow; it is for rescuing obvious misroutes such
    as official corruption/bribery complaints, not for general classification.
    """
    if not blob:
        return None, None

    emergency_domain, emergency_subdomain = infer_emergency_taxonomy_override(blob)
    if emergency_domain and emergency_subdomain:
        return emergency_domain, emergency_subdomain

    if _looks_like_water_supply_outage(blob):
        return "Infrastructure & Utilities", "Water Supply"

    venue_domain, venue_subdomain = _looks_like_venue_context_civic_issue(blob)
    if venue_domain and venue_subdomain:
        return venue_domain, venue_subdomain

    has_explicit_corruption = _has_any_marker(blob, _CORRUPTION_EXPLICIT_MARKERS)
    has_official_context = _has_any_marker(blob, _CORRUPTION_OFFICIAL_MARKERS)
    has_payment_demand = _looks_like_payment_demand(blob)
    has_workflow_context = _has_any_marker(blob, _WORKFLOW_CONTEXT_MARKERS)

    if (has_explicit_corruption or has_payment_demand) and (has_official_context or has_workflow_context):
        return "Bureaucratic / Administrative", "Bribery/Corruption"

    return None, None


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
    strong_domain, strong_subdomain = _infer_strong_taxonomy_override(blob)
    if strong_domain and strong_subdomain:
        return {
            "problem_domain": strong_domain,
            "problem_subdomain": strong_subdomain,
            "convergence_program_type": SUBDOMAIN_TO_PROGRAM_TYPE[strong_subdomain],
            "categories": [strong_domain],
        }

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
