from __future__ import annotations


def location_required_for_grievance(grievance: dict | None = None) -> bool:
    """Every citizen grievance must resolve to a known constituency before it
    proceeds — location is required unconditionally, independent of domain/
    category (and independent of classification mode, which may leave those
    fields null)."""
    return True
