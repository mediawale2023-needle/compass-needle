from modules.assembly_boundary_importer import (
    build_boundary_payload_from_assembly_feature,
    load_builtin_assembly_geojson,
)


def test_build_boundary_payload_from_assembly_feature_uses_geojson_asset():
    feature = {
        "type": "Feature",
        "properties": {
            "ST_NAME": "KARNATAKA",
            "DIST_NAME": "BELAGAVI",
            "AC_NO": "11",
            "AC_NAME": "Belgaum Dakshin",
            "PC_NO": "2",
            "PC_NAME": "Belagavi",
            "STATUS": "",
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[74.4, 15.8], [74.6, 15.8], [74.6, 15.95], [74.4, 15.95], [74.4, 15.8]]],
        },
    }

    payload = build_boundary_payload_from_assembly_feature(feature)

    assert payload["seat_key"] == "mla:Belgaum Dakshin"
    assert payload["asset"]["type"] == "geojson"
    assert payload["asset"]["geojson"]["type"] == "FeatureCollection"
    assert payload["metadata"]["dataset"] == "india_ac_normalized.geojson"


def test_load_builtin_assembly_geojson_reads_repo_dataset():
    payload = load_builtin_assembly_geojson()
    assert payload["type"] == "FeatureCollection"
    assert len(payload["features"]) > 4000
