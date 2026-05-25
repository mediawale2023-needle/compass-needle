from __future__ import annotations


_LOCATION_REQUIRED_DOMAINS = {
    "Infrastructure & Utilities",
    "Housing & Land",
    "Health",
    "Education",
    "Agriculture",
}


def location_required_for_domain(problem_domain: str | None) -> bool:
    return str(problem_domain or "").strip() in _LOCATION_REQUIRED_DOMAINS


def location_required_for_grievance(grievance: dict | None = None) -> bool:
    grievance = grievance or {}
    problem_domain = grievance.get("problem_domain")
    if problem_domain:
        return location_required_for_domain(str(problem_domain))

    categories = grievance.get("categories") or []
    if isinstance(categories, list) and categories:
        return location_required_for_domain(str(categories[0]))

    return True
