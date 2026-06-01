from modules.parliamentary_boundary_importer import (
    build_boundary_payload_from_parliamentary_feature,
    load_builtin_parliamentary_geojson,
    load_parliamentary_geojson_from_upload,
)


def test_build_boundary_payload_from_parliamentary_feature_uses_geojson_asset():
    feature = {
        "type": "Feature",
        "properties": {
            "pc_id": 2902,
            "st_name": "Karnataka",
            "pc_no": 2,
            "pc_name": "Belagavi",
            "pc_name_hi": "बेलगाम",
            "pc_category": "GEN",
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[74.4, 15.7], [74.9, 15.7], [74.9, 16.0], [74.4, 16.0], [74.4, 15.7]]],
        },
    }

    payload = build_boundary_payload_from_parliamentary_feature(feature)

    assert payload["seat_key"] == "mp:Belagavi"
    assert payload["asset"]["type"] == "geojson"
    assert payload["asset"]["geojson"]["type"] == "FeatureCollection"
    assert payload["metadata"]["dataset"] == "india_pc_2019_simplified.geojson"
    assert payload["metadata"]["aliases"] == ["Belagavi", "बेलगाम"]


def test_load_parliamentary_geojson_from_upload_accepts_geojson_bytes():
    raw = b'{"type":"FeatureCollection","features":[]}'
    payload = load_parliamentary_geojson_from_upload(raw, "india_pc_2019_simplified.geojson")
    assert payload["type"] == "FeatureCollection"


def test_load_builtin_parliamentary_geojson_reads_repo_dataset():
    payload = load_builtin_parliamentary_geojson()
    assert payload["type"] == "FeatureCollection"
    assert len(payload["features"]) > 500
