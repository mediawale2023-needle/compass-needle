from modules import seat_map_generator


def test_generate_seat_map_manifest_uses_shared_geography(monkeypatch):
    monkeypatch.setattr(seat_map_generator, "get_seat_boundary_for_identity", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        seat_map_generator,
        "import_builtin_assembly_boundary_for_seat",
        lambda **kwargs: (_ for _ in ()).throw(ValueError("no built-in boundary")),
    )
    monkeypatch.setattr(
        seat_map_generator,
        "get_geography_data",
        lambda **kwargs: {
            "Belgaum South": [
                {"locality": "Nath Pai Circle"},
                {"locality": "Shahapur"},
                {"locality": "Nath Pai Circle"},
            ],
            "Yellur": [
                {"locality": "Yellur"},
            ],
        },
    )

    manifest = seat_map_generator.generate_seat_map_manifest(
        seat_type="mla",
        seat_name="Belgaum Dakshin",
        state="Karnataka",
        aliases=["Belgaum Dakshin", "Belgaum South"],
    )

    assert manifest["seat_key"] == "mla:Belgaum Dakshin"
    assert manifest["asset"]["type"] == "generated-svg"
    assert manifest["asset"]["generated"] is True
    assert "<svg" in manifest["asset"]["inline_svg"]
    assert manifest["features"]
    labels = {feature["label"] for feature in manifest["features"]}
    assert "Nath Pai Circle" in labels
    assert "Shahapur" in labels
    assert "Yellur" in labels
    assert all("anchor" in feature for feature in manifest["features"])
    assert manifest["fallback_anchors"]


def test_generate_seat_map_manifest_prefers_registered_boundary(monkeypatch):
    monkeypatch.setattr(
        seat_map_generator,
        "get_geography_data",
        lambda **kwargs: {
            "Belgaum South": [{"locality": "Nath Pai Circle"}],
        },
    )
    monkeypatch.setattr(
        seat_map_generator,
        "get_seat_boundary_for_identity",
        lambda *_args, **_kwargs: {
            "source": "admin",
            "asset": {
                "type": "svg",
                "path": "/maps/mla/belgaum-dakshin-real.svg",
                "inline_svg": "",
                "geojson": {},
            },
            "metadata": {"aspect_ratio": "72 / 63"},
        },
    )

    manifest = seat_map_generator.generate_seat_map_manifest(
        seat_type="mla",
        seat_name="Belgaum Dakshin",
        state="Karnataka",
    )

    assert manifest["asset"]["type"] == "svg"
    assert manifest["asset"]["path"] == "/maps/mla/belgaum-dakshin-real.svg"
    assert manifest["asset"]["generated"] is False
    assert manifest["source"] == "generated-from-boundary"


def test_generate_seat_map_manifest_prefers_registered_geojson_boundary(monkeypatch):
    monkeypatch.setattr(
        seat_map_generator,
        "get_geography_data",
        lambda **kwargs: {
            "Belagavi": [{"locality": "Belagavi City"}],
        },
    )
    monkeypatch.setattr(
        seat_map_generator,
        "get_seat_boundary_for_identity",
        lambda *_args, **_kwargs: {
            "source": "datameet-parliamentary-2019",
            "asset": {
                "type": "geojson",
                "path": "",
                "inline_svg": "",
                "geojson": {"type": "FeatureCollection", "features": []},
            },
            "metadata": {"aspect_ratio": "100 / 60"},
        },
    )

    manifest = seat_map_generator.generate_seat_map_manifest(
        seat_type="mp",
        seat_name="Belagavi",
        state="Karnataka",
    )

    assert manifest["asset"]["type"] == "geojson"
    assert manifest["asset"]["geojson"]["type"] == "FeatureCollection"
    assert manifest["asset"]["generated"] is False
    assert manifest["source"] == "generated-from-boundary"


def test_generate_mp_seat_map_manifest_uses_assembly_segments_for_hotspots(monkeypatch):
    monkeypatch.setattr(
        seat_map_generator,
        "get_geography_data",
        lambda **kwargs: {
            "Belgaum South": [{"locality": "Nath Pai Circle"}],
            "Bailhongal": [{"locality": "Bailhongal Town"}],
        },
    )
    monkeypatch.setattr(
        seat_map_generator,
        "get_seat_boundary_for_identity",
        lambda *_args, **_kwargs: {
            "source": "datameet-parliamentary-2019",
            "asset": {
                "type": "geojson",
                "path": "",
                "inline_svg": "",
                "geojson": {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "geometry": {
                                "type": "Polygon",
                                "coordinates": [[[0, 0], [30, 0], [30, 15], [0, 15], [0, 0]]],
                            },
                            "properties": {},
                        }
                    ],
                },
            },
            "metadata": {"aspect_ratio": "100 / 50", "pc_no": "2", "aliases": ["Belgaum"]},
        },
    )
    calls = {}
    def _assembly_lookup(**kwargs):
        calls.update(kwargs)
        return [
            {
                "type": "Feature",
                "properties": {"AC_NAME": "Belgaum South"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[2, 2], [14, 2], [14, 13], [2, 13], [2, 2]]],
                },
            },
            {
                "type": "Feature",
                "properties": {"AC_NAME": "Bailhongal"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[17, 3], [28, 3], [28, 12], [17, 12], [17, 3]]],
                },
            },
        ]
    monkeypatch.setattr(
        seat_map_generator,
        "get_builtin_assembly_features_for_parliamentary_seat",
        _assembly_lookup,
    )

    manifest = seat_map_generator.generate_seat_map_manifest(
        seat_type="mp",
        seat_name="Belagavi",
        state="Karnataka",
    )

    assert manifest["asset"]["type"] == "geojson"
    assert manifest["asset"]["assembly_geojson"]["type"] == "FeatureCollection"
    assert len(manifest["asset"]["assembly_geojson"]["features"]) == 2
    assert calls["parliamentary_pc_no"] == "2"
    assert "Belgaum" in calls["aliases"]
    anchors = {feature["label"]: feature["anchor"] for feature in manifest["features"]}
    assert anchors["Nath Pai Circle"]["x"] < anchors["Bailhongal Town"]["x"]
    assert "assembly" in manifest["features"][0]


def test_generate_seat_map_manifest_auto_imports_builtin_assembly_boundary(monkeypatch):
    monkeypatch.setattr(
        seat_map_generator,
        "get_geography_data",
        lambda **kwargs: {
            "Belgaum South": [{"locality": "Nath Pai Circle"}],
        },
    )
    monkeypatch.setattr(seat_map_generator, "get_seat_boundary_for_identity", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        seat_map_generator,
        "import_builtin_assembly_boundary_for_seat",
        lambda **kwargs: {
            "source": "datameet-assembly-2022-normalized",
            "asset": {
                "type": "geojson",
                "path": "",
                "inline_svg": "",
                "geojson": {"type": "FeatureCollection", "features": []},
            },
            "metadata": {"aspect_ratio": "100 / 65"},
        },
    )

    manifest = seat_map_generator.generate_seat_map_manifest(
        seat_type="mla",
        seat_name="Belgaum Dakshin",
        state="Karnataka",
    )

    assert manifest["asset"]["type"] == "geojson"
    assert manifest["asset"]["generated"] is False
    assert manifest["source"] == "generated-from-boundary"


def test_generate_seat_map_manifest_requires_geography(monkeypatch):
    monkeypatch.setattr(seat_map_generator, "get_geography_data", lambda **kwargs: {})
    monkeypatch.setattr(
        seat_map_generator,
        "import_builtin_assembly_boundary_for_seat",
        lambda **kwargs: (_ for _ in ()).throw(ValueError("no built-in boundary")),
    )
    monkeypatch.setattr(
        seat_map_generator,
        "import_builtin_parliamentary_boundary_for_seat",
        lambda **kwargs: (_ for _ in ()).throw(ValueError("no built-in boundary")),
    )
    try:
        seat_map_generator.generate_seat_map_manifest(
            seat_type="mp",
            seat_name="Belagavi",
            state="Karnataka",
        )
    except ValueError as exc:
        assert "Upload geography first" in str(exc)
    else:
        raise AssertionError("Expected generator to fail without geography")
