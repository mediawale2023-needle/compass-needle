import os

os.environ.setdefault("JWT_SECRET", "x" * 32)

import api_router


def test_case_display_geography_repairs_cross_tenant_ai_assembly(monkeypatch):
    monkeypatch.setattr(
        api_router,
        "assembly_belongs_to_parliamentary",
        lambda assembly, constituency: assembly == "Belgaum Rural" and constituency == "Belagavi",
    )
    monkeypatch.setattr(
        api_router,
        "get_assembly_parliamentary_constituency",
        lambda assembly: "Kalyan" if assembly == "Ulhasnagar" else None,
    )
    monkeypatch.setattr(
        api_router,
        "resolve_location",
        lambda *_args, **_kwargs: {
            "location_resolved": True,
            "matched_value": "Santibastawad",
            "assembly_constituency": "Belgaum Rural",
        },
    )
    case = {
        "raw_message": "शांती बसवाड मध्ये रस्ता खराब आहे.",
        "location": "शांती बसवाड",
        "assembly": "Ulhasnagar",
        "case_metadata": {
            "matched_value": "शांती बसवाड",
            "assembly_constituency": "Ulhasnagar",
            "location_resolved": True,
        },
    }

    result = api_router._apply_tenant_safe_case_geography(case, "Belagavi", 2)

    assert result["location"] == "Santibastawad"
    assert result["assembly"] == "Belgaum Rural"
    assert result["case_metadata"]["matched_value"] == "Santibastawad"
    assert result["case_metadata"]["assembly_constituency"] == "Belgaum Rural"


def test_case_display_geography_hides_unresolvable_cross_tenant_ai_assembly(monkeypatch):
    monkeypatch.setattr(api_router, "assembly_belongs_to_parliamentary", lambda *_args: False)
    monkeypatch.setattr(
        api_router,
        "get_assembly_parliamentary_constituency",
        lambda assembly: "Kalyan" if assembly == "Ulhasnagar" else None,
    )
    monkeypatch.setattr(api_router, "resolve_location", lambda *_args, **_kwargs: {"location_resolved": False})
    case = {
        "raw_message": "Unknown location road issue",
        "location": "Unknown Place",
        "assembly": "Ulhasnagar",
        "case_metadata": {
            "matched_value": "Unknown Place",
            "assembly_constituency": "Ulhasnagar",
            "location_resolved": True,
        },
    }

    result = api_router._apply_tenant_safe_case_geography(case, "Belagavi", 2)

    assert result["location"] == "Unknown Place"
    assert result["assembly"] == "Unknown"
    assert result["case_metadata"]["assembly_constituency"] == "Unknown"
    assert result["case_metadata"]["location_resolved"] is False


def test_case_display_geography_preserves_unindexed_stored_assembly(monkeypatch):
    monkeypatch.setattr(api_router, "assembly_belongs_to_parliamentary", lambda *_args: False)
    monkeypatch.setattr(api_router, "get_assembly_parliamentary_constituency", lambda _assembly: None)
    monkeypatch.setattr(api_router, "resolve_location", lambda *_args, **_kwargs: {"location_resolved": False})
    case = {
        "raw_message": "No water supply in Whitefield for 3 days",
        "location": "Whitefield",
        "assembly": "Mahadevapura",
        "case_metadata": {
            "matched_value": "Whitefield",
            "assembly_constituency": "Mahadevapura",
            "location_resolved": True,
        },
    }

    result = api_router._apply_tenant_safe_case_geography(case, "Bangalore North", 1)

    assert result["location"] == "Whitefield"
    assert result["assembly"] == "Mahadevapura"
    assert result["case_metadata"]["assembly_constituency"] == "Mahadevapura"
    assert result["case_metadata"]["location_resolved"] is True
