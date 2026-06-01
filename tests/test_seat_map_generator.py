from modules import seat_map_generator


def test_generate_seat_map_manifest_uses_shared_geography(monkeypatch):
    monkeypatch.setattr(seat_map_generator, "get_seat_boundary_for_identity", lambda *_args, **_kwargs: None)
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


def test_generate_seat_map_manifest_requires_geography(monkeypatch):
    monkeypatch.setattr(seat_map_generator, "get_geography_data", lambda **kwargs: {})
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
