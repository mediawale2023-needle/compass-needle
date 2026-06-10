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
                {"station_number": "1", "locality": "Shahapur", "building_name": ""},
                {"station_number": "1a", "locality": "Khasbag", "building_name": ""},
                {"station_number": "1b", "locality": "Kariyappa Colony Tilakwadi", "building_name": ""},
                {
                    "station_number": "1c",
                    "locality": "R.C Nagar, Belagavi",
                    "building_name": "Community Hall, 2nd Western Side,\nRani Channamma Nagar, Belagavi",
                },
                {"station_number": "2", "locality": "Meerapur Galli, Shahapur Belagavi", "building_name": ""},
                {"station_number": "2a", "locality": "Teli Patil Galli Shahapur, Belagavi", "building_name": ""},
                {"station_number": "2b", "locality": "Teachers Colony - Khasbag", "building_name": ""},
                {"station_number": "2c", "locality": "Navi Galli - Shahapur", "building_name": ""},
                {"station_number": "3", "locality": "Somawar Peth Tilakwadi, Belagavi", "building_name": ""},
                {"station_number": "3a", "locality": "Vaccine Depot.Tilakwadi, Belagavi", "building_name": ""},
                {"station_number": "4", "locality": "Vadagaon Belagavi", "building_name": ""},
                {"station_number": "5", "locality": "Nath Pai Circle\nShahapur, Belagavi", "building_name": ""},
                {"station_number": "6", "locality": "Gomatesh Vidya Peetha Hindwadi", "building_name": ""},
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
                {"station_number": "3", "locality": "Peeranwadi", "building_name": ""},
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
    assert result["matched_type"] == "locality"


def test_resolve_location_indexes_each_multiline_locality_line(stub_geography_index):
    geography_resolver.reload_index()

    result = geography_resolver.resolve_location(
        "Nath Pai Circle cha rasta tutla aahe",
        scope_parliamentary="Belagavi",
    )

    assert result["location_resolved"] is True
    assert result["assembly_constituency"] == "Belgaum Dakshin"
    assert result["matched_value"] == "Nath Pai Circle"
    assert result["matched_type"] == "sub_locality"
    assert result["parent_locality"] == "Shahapur"


def test_resolve_location_preserves_user_level_detail(stub_geography_index):
    geography_resolver.reload_index()

    result = geography_resolver.resolve_location(
        "Meerapur Galli Shahapur madhe light nhi",
        scope_parliamentary="Belagavi",
    )

    assert result["location_resolved"] is True
    assert result["assembly_constituency"] == "Belgaum Dakshin"
    assert result["matched_value"] == "Meerapur Galli"
    assert result["matched_type"] == "sub_locality"
    assert result["parent_locality"] == "Shahapur"


def test_resolve_location_uses_short_user_location_not_polling_detail(stub_geography_index):
    geography_resolver.reload_index()

    result = geography_resolver.resolve_location("Tilakwadi madhe rasta kharab aahe", scope_parliamentary="Belagavi")

    assert result["location_resolved"] is True
    assert result["assembly_constituency"] == "Belgaum Dakshin"
    assert result["matched_value"] == "Tilakwadi"
    assert result["matched_type"] == "locality"


def test_resolve_location_infers_parent_from_specific_sub_locality(stub_geography_index):
    geography_resolver.reload_index()

    result = geography_resolver.resolve_location(
        "Teli Patil Galli madhe paani nahi",
        scope_parliamentary="Belagavi",
    )

    assert result["location_resolved"] is True
    assert result["assembly_constituency"] == "Belgaum Dakshin"
    assert result["matched_value"] == "Teli Patil Galli"
    assert result["matched_type"] == "sub_locality"
    assert result["parent_locality"] == "Shahapur"


def test_resolve_location_supports_marathi_voice_drift_for_vadgaon(stub_geography_index):
    geography_resolver.reload_index()

    result = geography_resolver.resolve_location(
        "फळगावच्या सरकारी शाळेमध्ये पाणी भरला आहे",
        scope_parliamentary="Belagavi",
    )

    assert result["location_resolved"] is True
    assert result["assembly_constituency"] == "Belgaum Dakshin"
    assert result["matched_value"] in {"Vadagaon Belagavi", "Vadagaon", "Vadgaon"}


def test_resolve_location_uses_building_name_locality_aliases_for_abbreviated_rows(stub_geography_index):
    geography_resolver.reload_index()

    result = geography_resolver.resolve_location(
        "rani chennamma nagar madhe khup chori hot aahe",
        scope_parliamentary="Belagavi",
    )

    assert result["location_resolved"] is True
    assert result["assembly_constituency"] == "Belgaum Dakshin"
    assert result["matched_value"] == "Rani Channamma Nagar"


def test_resolve_location_prefers_parent_fragment_over_combined_roll_label(stub_geography_index):
    geography_resolver.reload_index()

    result = geography_resolver.resolve_location(
        "Hindwadi mein light problem hai",
        scope_parliamentary="Belagavi",
    )

    assert result["location_resolved"] is True
    assert result["assembly_constituency"] == "Belgaum Dakshin"
    assert result["matched_value"] == "Hindwadi"
    assert result["matched_type"] == "locality"


def test_extract_building_location_seeds_strips_neutral_prefixes():
    seeds = geography_resolver._extract_building_location_seeds(
        "Govt School\n2nd Stage Rani Channamma Nagar\nBelagavi",
        parliamentary_constituency="Belagavi",
    )

    assert "2nd stage rani channamma nagar" in {geography_resolver.normalize(seed) for seed in seeds}
    assert "rani channamma nagar" in {geography_resolver.normalize(seed) for seed in seeds}


def test_extract_building_location_seeds_ignores_generic_venue_lines():
    seeds = geography_resolver._extract_building_location_seeds(
        "Govt Kannada Higher Primary School 4th Std Class Room\nCommunity Hall Western Side",
        parliamentary_constituency="Belagavi",
    )

    assert seeds == set()


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


def test_resolve_location_supports_hyphenated_sub_locality_without_parent(stub_geography_index):
    geography_resolver.reload_index()

    result = geography_resolver.resolve_location(
        "Teacher Colony nalli 3 din neer illa",
        scope_parliamentary="Belagavi",
    )

    assert result["location_resolved"] is True
    assert result["assembly_constituency"] == "Belgaum Dakshin"
    assert result["matched_value"] == "Teachers Colony"
    assert result["matched_type"] == "sub_locality"
    assert result["parent_locality"] == "Khasbag"


def test_resolve_location_rejects_generic_colony_overlap_false_positive(stub_geography_index):
    geography_resolver.reload_index()

    candidates = geography_resolver._rank_location_candidates(
        "Teacher Colony nalli 3 din neer illa",
        scope_parliamentary="Belagavi",
    )

    assert all(candidate["matched_value"] != "Kariyappa Colony Tilakwadi" for candidate in candidates[:3])
    assert candidates[0]["matched_value"] == "Teachers Colony"


def test_resolve_location_prefers_explicit_parent_row_over_inherited_parent_alias(stub_geography_index):
    geography_resolver.reload_index()

    candidates = geography_resolver._rank_location_candidates(
        "Khasbag madhe 3 divasa pasun paani nahi",
        scope_parliamentary="Belagavi",
    )

    assert candidates[0]["name"] == "Khasbag"
    assert candidates[0]["matched_value"] == "Khasbag"
    assert candidates[0]["matched_type"] == "locality"


def test_resolve_location_supports_hyphenated_sub_locality_with_parent(stub_geography_index):
    geography_resolver.reload_index()

    result = geography_resolver.resolve_location(
        "Teachers Colony Khasbag madhe paani nahi",
        scope_parliamentary="Belagavi",
    )

    assert result["location_resolved"] is True
    assert result["assembly_constituency"] == "Belgaum Dakshin"
    assert result["matched_value"] == "Teachers Colony"
    assert result["matched_type"] == "sub_locality"
    assert result["parent_locality"] == "Khasbag"


def test_resolve_location_supports_parent_only_for_hyphenated_entry(stub_geography_index):
    geography_resolver.reload_index()

    result = geography_resolver.resolve_location(
        "Khasbag nalli water problem ide",
        scope_parliamentary="Belagavi",
    )

    assert result["location_resolved"] is True
    assert result["assembly_constituency"] == "Belgaum Dakshin"
    assert result["matched_value"] == "Khasbag"
    assert result["matched_type"] == "locality"


def test_resolve_location_supports_explicit_sub_locality_row_without_parent_mention(stub_geography_index):
    geography_resolver.reload_index()

    result = geography_resolver.resolve_location(
        "Navi Galli madhe paani nahi",
        scope_parliamentary="Belagavi",
    )

    assert result["location_resolved"] is True
    assert result["assembly_constituency"] == "Belgaum Dakshin"
    assert result["matched_value"] == "Navi Galli"
    assert result["matched_type"] == "sub_locality"
    assert result["parent_locality"] == "Shahapur"


def test_resolve_location_supports_explicit_sub_locality_row_with_parent_mention(stub_geography_index):
    geography_resolver.reload_index()

    result = geography_resolver.resolve_location(
        "Navi Galli Shahapur madhe paani nahi",
        scope_parliamentary="Belagavi",
    )

    assert result["location_resolved"] is True
    assert result["assembly_constituency"] == "Belgaum Dakshin"
    assert result["matched_value"] == "Navi Galli"
    assert result["matched_type"] == "sub_locality"
    assert result["parent_locality"] == "Shahapur"


def test_resolve_location_supports_kannada_voice_transcript_for_balekundri(stub_geography_index):
    geography_resolver.reload_index()

    result = geography_resolver.resolve_location(
        "ಬಾಳೆಗುಂದ್ರಿನಲ್ಲಿ ಬಹಳ ಕಚ್ಚರ ಆಗಿದೆ ಸ್ವಲ್ಪ ಕ್ಲಿಯರ್ ಮಾಡಬೇಕು",
        scope_parliamentary="Belagavi",
    )

    assert result["location_resolved"] is True
    assert result["assembly_constituency"] == "Belgaum Rural"
    assert result["matched_value"] == "Balekundri"


def test_resolve_location_supports_kannada_inflected_peeranwadi(stub_geography_index):
    geography_resolver.reload_index()

    result = geography_resolver.resolve_location(
        "ಸಾಹೇಬ್ರೆ ಪಿರನ್ವಾಡಿನ ರಸ್ತೆ ಖರಾಬ್ ಇದೆ ಅದೇನ್ ಏನ್ ಮಾಡ್ತೀನಿ ನೋಡ್ರಿ",
        scope_parliamentary="Belagavi",
    )

    assert result["location_resolved"] is True
    assert result["assembly_constituency"] == "Belgaum Rural"
    assert result["matched_value"] == "Peeranwadi"


def test_resolve_location_supports_kannada_locative_depot_forms(stub_geography_index):
    geography_resolver.reload_index()

    result = geography_resolver.resolve_location(
        "ವ್ಯಾಕ್ಸಿನ್ ಡೆಪೋನಲ್ಲಿ ಬಹಳ ಕಸವಾಗಿದೆ ನೋಡಿ",
        scope_parliamentary="Belagavi",
    )

    assert result["location_resolved"] is True
    assert result["assembly_constituency"] == "Belgaum Dakshin"
    assert result["matched_value"] in {"Vaccine Depot", "Depot", "Tilakwadi"}


def test_resolve_location_supports_voice_note_spelling_drift_for_santibastawad(stub_geography_index):
    geography_resolver.reload_index()

    result = geography_resolver.resolve_location(
        "shanti baswad madhe rasta kharab aahe",
        scope_parliamentary="Belagavi",
    )

    assert result["location_resolved"] is True
    assert result["assembly_constituency"] == "Belgaum Rural"
    assert result["matched_value"] in {"Santibastawad", "Santibaswad", "Santi Baswad"}


def test_resolve_constituency_scopes_lookup_by_tenant(monkeypatch, stub_geography_index):
    monkeypatch.setattr(geography_resolver, "_get_tenant_constituency", lambda tenant_id: "Belagavi")
    seen = {}
    monkeypatch.setattr(
        geography_resolver,
        "resolve_location",
        lambda text, scope_parliamentary=None, tenant_id=None: seen.update({
            "text": text,
            "scope_parliamentary": scope_parliamentary,
            "tenant_id": tenant_id,
        }) or {
            "location_resolved": True,
            "matched_value": "Santibastawad",
            "assembly_constituency": "Belgaum Rural",
        },
    )

    matched, assembly = geography_resolver.resolve_constituency("shanti baswad road issue", tenant_id=3)

    assert seen == {
        "text": "shanti baswad road issue",
        "scope_parliamentary": "Belagavi",
        "tenant_id": 3,
    }
    assert matched == "Santibastawad"
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


def test_resolve_location_uses_manual_tenant_overrides_before_shared_geography(monkeypatch, stub_geography_index):
    geography_resolver.reload_index()
    monkeypatch.setattr(
        geography_resolver,
        "_load_tenant_overrides",
        lambda tenant_id: {
            "ಬಾಳೆಗುಂದ್ರಿ": "Belgaum Rural",
        },
    )

    result = geography_resolver.resolve_location(
        "ಬಾಳೆಗುಂದ್ರಿಯಲ್ಲಿ ಕಸ ಇದೆ",
        scope_parliamentary="Belagavi",
        tenant_id=3,
    )

    assert result["location_resolved"] is True
    assert result["assembly_constituency"] == "Belgaum Rural"
    assert result["matched_value"] == "ಬಾಳೆಗುಂದ್ರಿ".title()


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
