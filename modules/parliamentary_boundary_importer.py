from __future__ import annotations

import io
import json
import zipfile
from functools import lru_cache
from pathlib import Path
from typing import Any

from modules.seat_boundaries import upsert_seat_boundary


DATASET_SOURCE = "datameet-parliamentary-2019"
PARLIAMENTARY_GEOJSON_NAME = "india_pc_2019_simplified.geojson"
BUILTIN_PARLIAMENTARY_GEOJSON_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "maps"
    / "parliamentary"
    / PARLIAMENTARY_GEOJSON_NAME
)


def _normalize_token(value: str | None) -> str:
    return " ".join(
        "".join(ch.lower() if ch.isalnum() else " " for ch in str(value or "")).split()
    )


def _iter_points(node: Any):
    if isinstance(node, (list, tuple)):
        if len(node) >= 2 and all(isinstance(part, (int, float)) for part in node[:2]):
            yield float(node[0]), float(node[1])
            return
        for child in node:
            yield from _iter_points(child)


def _compute_bbox(geometry: dict[str, Any]) -> tuple[float, float, float, float]:
    points = list(_iter_points((geometry or {}).get("coordinates") or []))
    if not points:
        return (0.0, 0.0, 1.0, 1.0)
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return (min(xs), min(ys), max(xs), max(ys))


def _aspect_ratio_from_bbox(bbox: tuple[float, float, float, float]) -> str:
    min_x, min_y, max_x, max_y = bbox
    width = max(max_x - min_x, 1e-9)
    height = max(max_y - min_y, 1e-9)
    canvas_width = 100
    canvas_height = round(max(44, min(120, canvas_width * (height / width))))
    return f"{canvas_width} / {canvas_height}"


def _feature_collection_for_feature(feature: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "features": [feature],
    }


def _extract_parliamentary_geojson_from_zip_bytes(raw_bytes: bytes) -> dict[str, Any]:
    with zipfile.ZipFile(io.BytesIO(raw_bytes)) as archive:
        preferred = [
            name
            for name in archive.namelist()
            if name.endswith(PARLIAMENTARY_GEOJSON_NAME)
        ]
        if preferred:
            return json.loads(archive.read(preferred[0]))
        fallbacks = [
            name
            for name in archive.namelist()
            if "parliamentary-constituencies/" in name and name.endswith(".geojson")
        ]
        if fallbacks:
            return json.loads(archive.read(fallbacks[0]))
    raise ValueError("Could not find parliamentary GeoJSON inside the uploaded ZIP.")


def load_parliamentary_geojson_from_upload(raw_bytes: bytes, filename: str | None = None) -> dict[str, Any]:
    lower_name = str(filename or "").lower()
    if lower_name.endswith(".zip"):
        return _extract_parliamentary_geojson_from_zip_bytes(raw_bytes)
    if lower_name.endswith(".geojson") or lower_name.endswith(".json") or not lower_name:
        return json.loads(raw_bytes.decode("utf-8"))
    raise ValueError("Upload a .zip or .geojson file.")


@lru_cache(maxsize=1)
def load_builtin_parliamentary_geojson() -> dict[str, Any]:
    if not BUILTIN_PARLIAMENTARY_GEOJSON_PATH.exists():
        raise ValueError(f"Built-in parliamentary dataset is missing at {BUILTIN_PARLIAMENTARY_GEOJSON_PATH}")
    return json.loads(BUILTIN_PARLIAMENTARY_GEOJSON_PATH.read_text(encoding="utf-8"))


def _matching_parliamentary_features(
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
        feature_name = _normalize_token(props.get("pc_name"))
        feature_state = _normalize_token(props.get("st_name"))
        if target_state and feature_state != target_state:
            continue
        if feature_name == target_name:
            matches.append(feature)
    return matches


def build_boundary_payload_from_parliamentary_feature(
    feature: dict[str, Any],
    *,
    status: str = "verified",
    source: str = DATASET_SOURCE,
) -> dict[str, Any]:
    props = feature.get("properties") or {}
    seat_name = str(props.get("pc_name") or "").strip()
    state = str(props.get("st_name") or "").strip()
    bbox = _compute_bbox(feature.get("geometry") or {})
    aliases = [
        alias
        for alias in [
            seat_name,
            str(props.get("pc_name_hi") or "").strip(),
        ]
        if alias
    ]
    return {
        "seat_key": f"mp:{seat_name}",
        "seat_type": "mp",
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
            "dataset": PARLIAMENTARY_GEOJSON_NAME,
            "aliases": aliases,
            "pc_no": props.get("pc_no"),
            "pc_id": props.get("pc_id"),
            "pc_category": props.get("pc_category"),
        },
        "status": status,
        "source": source,
    }


def import_parliamentary_boundary_for_seat(
    feature_collection: dict[str, Any],
    *,
    seat_name: str,
    state: str = "",
    status: str = "verified",
    source: str = DATASET_SOURCE,
) -> dict[str, Any]:
    matches = _matching_parliamentary_features(feature_collection, seat_name=seat_name, state=state)
    if not matches:
        raise ValueError(f"No parliamentary boundary found for {seat_name}{f' ({state})' if state else ''}.")
    if len(matches) > 1:
        raise ValueError(f"Multiple parliamentary boundaries matched {seat_name}; refine the state or seat name.")

    payload = build_boundary_payload_from_parliamentary_feature(matches[0], status=status, source=source)
    return upsert_seat_boundary(payload)


def import_builtin_parliamentary_boundary_for_seat(
    *,
    seat_name: str,
    state: str = "",
    status: str = "verified",
    source: str = DATASET_SOURCE,
) -> dict[str, Any]:
    return import_parliamentary_boundary_for_seat(
        load_builtin_parliamentary_geojson(),
        seat_name=seat_name,
        state=state,
        status=status,
        source=source,
    )


def import_all_parliamentary_boundaries(
    feature_collection: dict[str, Any],
    *,
    state: str = "",
    status: str = "verified",
    source: str = DATASET_SOURCE,
) -> dict[str, Any]:
    target_state = _normalize_token(state)
    imported = 0
    skipped = 0
    seat_keys: list[str] = []

    for feature in feature_collection.get("features") or []:
        props = feature.get("properties") or {}
        if target_state and _normalize_token(props.get("st_name")) != target_state:
            skipped += 1
            continue
        boundary = upsert_seat_boundary(
            build_boundary_payload_from_parliamentary_feature(feature, status=status, source=source)
        )
        imported += 1
        seat_keys.append(boundary.get("seat_key") or "")

    return {
        "imported": imported,
        "skipped": skipped,
        "seat_keys": [key for key in seat_keys if key],
        "state": state or "",
    }
