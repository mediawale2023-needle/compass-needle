from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from modules.parliamentary_boundary_importer import _aspect_ratio_from_bbox, _compute_bbox, _normalize_token
from modules.seat_boundaries import upsert_seat_boundary


DATASET_SOURCE = "datameet-assembly-2022-normalized"
ASSEMBLY_GEOJSON_NAME = "india_ac_normalized.geojson"
BUILTIN_ASSEMBLY_GEOJSON_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "maps"
    / "assembly"
    / ASSEMBLY_GEOJSON_NAME
)


def _feature_collection_for_feature(feature: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "features": [feature],
    }


@lru_cache(maxsize=1)
def load_builtin_assembly_geojson() -> dict[str, Any]:
    if not BUILTIN_ASSEMBLY_GEOJSON_PATH.exists():
        raise ValueError(f"Built-in assembly dataset is missing at {BUILTIN_ASSEMBLY_GEOJSON_PATH}")
    return json.loads(BUILTIN_ASSEMBLY_GEOJSON_PATH.read_text(encoding="utf-8"))


def _matching_assembly_features(
    feature_collection: dict[str, Any],
    *,
    seat_name: str,
    state: str = "",
) -> list[dict[str, Any]]:
    target_name = _normalize_token(seat_name)
    target_state = _normalize_token(state)
    matches: list[dict[str, Any]] = []
    for feature in feature_collection.get("features") or []:
        props = feature.get("properties") or {}
        feature_name = _normalize_token(props.get("AC_NAME"))
        feature_state = _normalize_token(props.get("ST_NAME"))
        if target_state and feature_state != target_state:
            continue
        if feature_name == target_name:
            matches.append(feature)
    return matches


def build_boundary_payload_from_assembly_feature(
    feature: dict[str, Any],
    *,
    status: str = "verified",
    source: str = DATASET_SOURCE,
) -> dict[str, Any]:
    props = feature.get("properties") or {}
    seat_name = str(props.get("AC_NAME") or "").strip()
    state = str(props.get("ST_NAME") or "").strip().title()
    bbox = _compute_bbox(feature.get("geometry") or {})
    aliases = [
        alias
        for alias in [
            seat_name,
            str(props.get("DIST_NAME") or "").strip(),
        ]
        if alias
    ]
    return {
        "seat_key": f"mla:{seat_name}",
        "seat_type": "mla",
        "seat_name": seat_name,
        "state": state,
        "asset": {
            "type": "geojson",
            "path": "",
            "inline_svg": "",
            "geojson": _feature_collection_for_feature(feature),
        },
        "metadata": {
            "aspect_ratio": _aspect_ratio_from_bbox(bbox),
            "bbox": list(bbox),
            "dataset": ASSEMBLY_GEOJSON_NAME,
            "aliases": aliases,
            "ac_no": props.get("AC_NO"),
            "pc_name": props.get("PC_NAME"),
            "pc_no": props.get("PC_NO"),
            "status_label": props.get("STATUS"),
            "district_name": props.get("DIST_NAME"),
        },
        "status": status,
        "source": source,
    }


def import_assembly_boundary_for_seat(
    feature_collection: dict[str, Any],
    *,
    seat_name: str,
    state: str = "",
    status: str = "verified",
    source: str = DATASET_SOURCE,
) -> dict[str, Any]:
    matches = _matching_assembly_features(feature_collection, seat_name=seat_name, state=state)
    if not matches:
        raise ValueError(f"No assembly boundary found for {seat_name}{f' ({state})' if state else ''}.")
    if len(matches) > 1:
        raise ValueError(f"Multiple assembly boundaries matched {seat_name}; refine the state or seat name.")
    payload = build_boundary_payload_from_assembly_feature(matches[0], status=status, source=source)
    return upsert_seat_boundary(payload)


def import_builtin_assembly_boundary_for_seat(
    *,
    seat_name: str,
    state: str = "",
    status: str = "verified",
    source: str = DATASET_SOURCE,
) -> dict[str, Any]:
    return import_assembly_boundary_for_seat(
        load_builtin_assembly_geojson(),
        seat_name=seat_name,
        state=state,
        status=status,
        source=source,
    )
