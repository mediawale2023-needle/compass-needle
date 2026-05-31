import pytest

import modules.geography_resolver as geography_resolver
import sansadx_backend.db as dbmod


@pytest.fixture
def stub_geography_index(monkeypatch):
    rows = [
        {
            "tenant_id": 1,
            "seat_type": "mp",
            "seat_name": "Aligarh",
            "parliamentary_constituency": "Aligarh",
            "assembly": "Koil",
            "stations": [
                {"station_number": "1", "locality": "District", "building_name": "Aligarh"},
                {"station_number": "2", "locality": "Total", "building_name": ""},
                {
                    "station_number": "3",
                    "locality": "3. Average number of voters per polling station",
                    "building_name": "",
                },
                {"station_number": "4", "locality": "Ramghat Road", "building_name": ""},
            ],
        },
        {
            "tenant_id": 2,
            "seat_type": "mp",
            "seat_name": "Ghaziabad",
            "parliamentary_constituency": "Ghaziabad",
            "assembly": "Ghaziabad",
            "stations": [
                {"station_number": "1", "locality": "Lohiya Nagar", "building_name": ""},
                {"station_number": "2", "locality": "Unique Colony", "building_name": ""},
            ],
        },
        {
            "tenant_id": 22,
            "seat_type": "mp",
            "seat_name": "Ghaziabad",
            "parliamentary_constituency": "Ghaziabad",
            "assembly": "Muradnagar",
            "stations": [
                {"station_number": "1", "locality": "Lohiya Nagar", "building_name": ""},
            ],
        },
        {
            "tenant_id": 3,
            "seat_type": "mp",
            "seat_name": "Belagavi",
            "parliamentary_constituency": "Belagavi",
            "assembly": "Belgaum Uttar",
            "stations": [
                {"station_number": "1", "locality": "Shahu Nagar", "building_name": ""},
            ],
        },
        {
            "tenant_id": 3,
            "seat_type": "mp",
            "seat_name": "Belagavi",
            "parliamentary_constituency": "Belagavi",
            "assembly": "Belgaum Dakshin",
            "stations": [
                {"station_number": "1", "locality": "Shahapur Belagavi", "building_name": ""},
                {"station_number": "2", "locality": "Meerapur Galli, Shahapur Belagavi", "building_name": ""},
                {"station_number": "3", "locality": "Somawar Peth Tilakwadi, Belagavi", "building_name": ""},
                {"station_number": "4", "locality": "Vadagaon Belagavi", "building_name": ""},
                {"station_number": "5", "locality": "Nath Pai Circle\nShahapur, Belagavi", "building_name": ""},
            ],
        },
        {
            "tenant_id": 3,
            "seat_type": "mp",
            "seat_name": "Belagavi",
            "parliamentary_constituency": "Belagavi",
            "assembly": "Belgaum Rural",
            "stations": [
                {"station_number": "1", "locality": "Balekundri KH", "building_name": ""},
                {"station_number": "2", "locality": "Santibastawad", "building_name": ""},
            ],
        },
        {
            "tenant_id": 31,
            "seat_type": "mp",
            "seat_name": "Belagavi",
            "parliamentary_constituency": "Belagavi",
            "assembly": "Core Zone",
            "stations": [
                {"station_number": "1", "locality": "Market Road", "building_name": ""},
            ],
        },
        {
            "tenant_id": 32,
            "seat_type": "mla",
            "seat_name": "Belagavi North",
            "parliamentary_constituency": "Belagavi North",
            "assembly": "Core Zone",
            "stations": [
                {"station_number": "1", "locality": "Sector 1", "building_name": ""},
            ],
        },
    ]

    monkeypatch.setattr(dbmod, "get_all_geography_data", lambda: rows)
    monkeypatch.setattr(geography_resolver, "GEOGRAPHY_BASE_PATH", None)
    monkeypatch.setattr(geography_resolver, "_geography_index", {"assemblies": {}, "loaded": False})
    yield rows
    monkeypatch.setattr(geography_resolver, "_geography_index", {"assemblies": {}, "loaded": False})


def test_load_geography_index_skips_meta_rows(stub_geography_index):
    geography_resolver.reload_index()

    assert geography_resolver.resolve_location("District", scope_parliamentary="Aligarh") == {
        "location_resolved": False
    }
    assert geography_resolver.resolve_location("Total", scope_parliamentary="Aligarh") == {
        "location_resolved": False
    }
    assert geography_resolver.resolve_location(
        "Average number of voters per polling station",
        scope_parliamentary="Aligarh",
    ) == {"location_resolved": False}


def test_resolve_location_supports_common_spelling_aliases(stub_geography_index):
    geography_resolver.reload_index()

    result = geography_resolver.resolve_location("Unique Colony drainage issue", scope_parliamentary="Ghaziabad")

    assert result["location_resolved"] is True
    assert result["assembly_constituency"] == "Ghaziabad"
    assert result["matched_value"] == "Unique Colony"


def test_resolve_location_supports_spaceless_aliases(stub_geography_index):
    geography_resolver.reload_index()

    result = geography_resolver.resolve_location("Shahunagar drainage issue", scope_parliamentary="Belagavi")

    assert result["location_resolved"] is True
    assert result["assembly_constituency"] == "Belgaum Uttar"
    assert result["matched_value"] == "Shahu Nagar"


def test_resolve_location_supports_city_suffix_aliases(stub_geography_index):
    geography_resolver.reload_index()

    result = geography_resolver.resolve_location("Shahapur madhe light nhi", scope_parliamentary="Belagavi")

    assert result["location_resolved"] is True
    assert result["assembly_constituency"] == "Belgaum Dakshin"
    assert result["matched_value"] == "Shahapur"


def test_resolve_location_indexes_each_multiline_locality_line(stub_geography_index):
    geography_resolver.reload_index()

    result = geography_resolver.resolve_location(
        "Nath Pai Circle cha rasta tutla aahe",
        scope_parliamentary="Belagavi",
    )

    assert result["location_resolved"] is True
    assert result["assembly_constituency"] == "Belgaum Dakshin"
    assert result["matched_value"] in {"Nath Pai Circle", "Pai Circle"}


def test_resolve_location_preserves_user_level_detail(stub_geography_index):
    geography_resolver.reload_index()

    result = geography_resolver.resolve_location(
        "Meerapur Galli Shahapur madhe light nhi",
        scope_parliamentary="Belagavi",
    )

    assert result["location_resolved"] is True
    assert result["assembly_constituency"] == "Belgaum Dakshin"
    assert result["matched_value"] == "Meerapur Galli Shahapur"


def test_resolve_location_uses_short_user_location_not_polling_detail(stub_geography_index):
    geography_resolver.reload_index()

    result = geography_resolver.resolve_location("Tilakwadi madhe rasta kharab aahe", scope_parliamentary="Belagavi")

    assert result["location_resolved"] is True
    assert result["assembly_constituency"] == "Belgaum Dakshin"
    assert result["matched_value"] == "Tilakwadi"


def test_resolve_location_supports_marathi_voice_drift_for_vadgaon(stub_geography_index):
    geography_resolver.reload_index()

    result = geography_resolver.resolve_location(
        "फळगावच्या सरकारी शाळेमध्ये पाणी भरला आहे",
        scope_parliamentary="Belagavi",
    )

    assert result["location_resolved"] is True
    assert result["assembly_constituency"] == "Belgaum Dakshin"
    assert result["matched_value"] in {"Vadagaon Belagavi", "Vadagaon", "Vadgaon"}


def test_resolve_location_supports_marathi_vadgaon_suffix(stub_geography_index):
    geography_resolver.reload_index()

    result = geography_resolver.resolve_location(
        "वडगावच्या सरकारी शाळेमध्ये पाणी भरला आहे",
        scope_parliamentary="Belagavi",
    )

    assert result["location_resolved"] is True
    assert result["assembly_constituency"] == "Belgaum Dakshin"
    assert result["matched_value"] in {"Vadagaon Belagavi", "Vadagaon", "Vadgaon"}


def test_resolve_location_supports_hindi_input_via_transliteration(stub_geography_index):
    geography_resolver.reload_index()

    result = geography_resolver.resolve_location("रामघाट रोड पर पानी नहीं", scope_parliamentary="Aligarh")

    assert result["location_resolved"] is True
    assert result["assembly_constituency"] == "Koil"
    assert result["matched_value"] == "Ramghat Road"


def test_resolve_location_supports_kannada_voice_transcript_for_balekundri(stub_geography_index):
    geography_resolver.reload_index()

    result = geography_resolver.resolve_location(
        "ಬಾಳೆಗುಂದ್ರಿನಲ್ಲಿ ಬಹಳ ಕಚ್ಚರ ಆಗಿದೆ ಸ್ವಲ್ಪ ಕ್ಲಿಯರ್ ಮಾಡಬೇಕು",
        scope_parliamentary="Belagavi",
    )

    assert result["location_resolved"] is True
    assert result["assembly_constituency"] == "Belgaum Rural"
    assert result["matched_value"] == "Balekundri"


def test_resolve_location_supports_voice_note_spelling_drift_for_santibastawad(stub_geography_index):
    geography_resolver.reload_index()

    result = geography_resolver.resolve_location(
        "shanti baswad madhe rasta kharab aahe",
        scope_parliamentary="Belagavi",
    )

    assert result["location_resolved"] is True
    assert result["assembly_constituency"] == "Belgaum Rural"
    assert result["matched_value"] in {"Santibaswad", "Santi Baswad"}


def test_resolve_constituency_scopes_lookup_by_tenant(monkeypatch, stub_geography_index):
    geography_resolver.reload_index()
    monkeypatch.setattr(geography_resolver, "_get_tenant_constituency", lambda tenant_id: "Belagavi")

    matched, assembly = geography_resolver.resolve_constituency("shanti baswad road issue", tenant_id=3)

    assert matched in {"Santibaswad", "Santi Baswad"}
    assert assembly == "Belgaum Rural"


def test_get_tenant_constituency_resolves_mla_assembly_to_parent_parliamentary(monkeypatch, stub_geography_index):
    geography_resolver.reload_index()
    monkeypatch.setattr(
        geography_resolver,
        "_get_tenant_seat_context",
        lambda tenant_id: {
            "seat_type": "mla",
            "seat_name": "Belgaum Dakshin",
            "scope_parliamentary": "Belagavi",
            "constituency": "Belgaum Dakshin",
        },
    )

    resolved_scope = geography_resolver._get_tenant_constituency(10)

    assert resolved_scope == "Belagavi"


def test_resolve_location_uses_db_backed_geo_aliases(monkeypatch, stub_geography_index):
    geography_resolver.reload_index()
    monkeypatch.setattr(
        geography_resolver,
        "_load_tenant_geo_aliases",
        lambda tenant_id: {
            "ಬಾಳೆಗುಂದ್ರಿ": {
                "assembly": "Belgaum Rural",
                "display": "Balekundri",
            }
        },
    )

    result = geography_resolver.resolve_location(
        "ಬಾಳೆಗುಂದ್ರಿಯಲ್ಲಿ ಕಸ ಇದೆ",
        scope_parliamentary="Belagavi",
        tenant_id=3,
    )

    assert result["location_resolved"] is True
    assert result["assembly_constituency"] == "Belgaum Rural"
    assert result["matched_value"] == "Balekundri"


def test_resolve_location_filters_by_tenant_seat_context(monkeypatch, stub_geography_index):
    geography_resolver.reload_index()
    monkeypatch.setattr(
        geography_resolver,
        "_get_tenant_seat_context",
        lambda tenant_id: {
            "seat_type": "mla",
            "seat_name": "Belagavi North",
            "scope_parliamentary": "Belagavi",
            "constituency": "Belagavi North",
        } if tenant_id == 21 else {
            "seat_type": "mp",
            "seat_name": "Belagavi",
            "scope_parliamentary": "Belagavi",
            "constituency": "Belagavi",
        },
    )

    mla_result = geography_resolver.resolve_location("Sector 1 drainage issue", tenant_id=21)
    mp_result = geography_resolver.resolve_location("Market Road drainage issue", tenant_id=13)

    assert mla_result["location_resolved"] is True
    assert mla_result["assembly_constituency"] == "Core Zone"
    assert mla_result["matched_value"] == "Sector 1"
    assert mp_result["location_resolved"] is True
    assert mp_result["assembly_constituency"] == "Core Zone"
    assert mp_result["matched_value"] == "Market Road"


def test_get_assembly_parliamentary_constituency_returns_none_for_cross_seat_duplicates(stub_geography_index):
    geography_resolver.reload_index()

    assert geography_resolver.get_assembly_parliamentary_constituency("Core Zone") is None


def test_resolve_location_fails_closed_on_ambiguous_locality(stub_geography_index):
    geography_resolver.reload_index()

    result = geography_resolver.resolve_location("Lohia Nagar drainage issue", scope_parliamentary="Ghaziabad")

    assert result["location_resolved"] is False
    assert result["reason"] == "ambiguous_match"
    assert result["ambiguous_assemblies"] == ["Ghaziabad", "Muradnagar"]


def test_sanitize_and_validate_stations_reports_meta_and_ambiguity(stub_geography_index):
    incoming = [
        {"station_number": "1", "locality": "District", "building_name": "Aligarh"},
        {"station_number": "2", "locality": "Lohiya Nagar", "building_name": ""},
        {"station_number": "3", "locality": "रामघाट रोड", "building_name": ""},
    ]

    cleaned, report = geography_resolver.sanitize_and_validate_stations(
        incoming,
        parliamentary_constituency="Ghaziabad",
        assembly="Loni",
        other_rows=stub_geography_index,
    )

    assert [row["locality"] for row in cleaned] == ["Lohiya Nagar", "रामघाट रोड"]
    assert report["meta_rows_removed"] == 1
    assert report["meta_row_samples"] == ["District"]
    assert report["ambiguous_localities_against_constituency"] == {"Lohiya Nagar": ["Ghaziabad", "Muradnagar"]}
