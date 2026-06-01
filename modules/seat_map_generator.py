from __future__ import annotations

import math
import re
from collections import defaultdict
from html import escape
from typing import Any

from sansadx_backend.db import build_seat_key, get_geography_data
from modules.assembly_boundary_importer import (
    get_builtin_assembly_features_for_parliamentary_seat,
    import_builtin_assembly_boundary_for_seat,
)
from modules.seat_boundaries import get_seat_boundary_for_identity
from modules.parliamentary_boundary_importer import _compute_bbox, import_builtin_parliamentary_boundary_for_seat


CANVAS_WIDTH = 100
CANVAS_HEIGHT = 72


def _normalize(value: str | None) -> str:
    return " ".join(
        "".join(ch.lower() if ch.isalnum() else " " for ch in str(value or "")).split()
    )


def _slugify(value: str) -> str:
    parts = re.findall(r"[a-z0-9]+", _normalize(value))
    return "-".join(parts) or "feature"


def _dedupe_preserve(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        clean = str(item or "").strip()
        if not clean:
            continue
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(clean)
    return result


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _assembly_centers(assembly_names: list[str]) -> dict[str, tuple[float, float]]:
    count = max(len(assembly_names), 1)
    if count == 1:
        return {assembly_names[0]: (50.0, 36.0)}

    cx, cy = 50.0, 36.0
    rx = 22 + min(count, 6) * 1.8
    ry = 14 + min(count, 6) * 1.25
    centers: dict[str, tuple[float, float]] = {}
    for index, name in enumerate(assembly_names):
        angle = (-math.pi / 2) + (2 * math.pi * index / count)
        centers[name] = (
            round(cx + rx * math.cos(angle), 2),
            round(cy + ry * math.sin(angle), 2),
        )
    return centers


def _point_for_locality(center_x: float, center_y: float, index: int, total: int) -> tuple[float, float]:
    if total <= 1:
        return (round(center_x, 2), round(center_y, 2))

    ring = 1 + (index // 8)
    angle = (2 * math.pi * (index % 8) / min(total, 8)) + (ring * 0.32)
    radius = min(11.5, 4.2 + ring * 2.3 + max(total - 1, 0) * 0.12)
    x = _clamp(center_x + math.cos(angle) * radius, 8, 92)
    y = _clamp(center_y + math.sin(angle) * radius, 10, 64)
    return (round(x, 2), round(y, 2))


def _point_for_locality_with_bounds(
    center_x: float,
    center_y: float,
    index: int,
    total: int,
    bounds: tuple[float, float, float, float] | None = None,
) -> tuple[float, float]:
    x, y = _point_for_locality(center_x, center_y, index, total)
    if not bounds:
        return (x, y)

    min_x, max_x, min_y, max_y = bounds
    inset_x = min(2.4, max((max_x - min_x) * 0.15, 0.6))
    inset_y = min(2.2, max((max_y - min_y) * 0.15, 0.6))
    clamped_min_x = min_x + inset_x
    clamped_max_x = max_x - inset_x
    clamped_min_y = min_y + inset_y
    clamped_max_y = max_y - inset_y
    if clamped_min_x > clamped_max_x:
        mid_x = (min_x + max_x) / 2
        clamped_min_x = clamped_max_x = mid_x
    if clamped_min_y > clamped_max_y:
        mid_y = (min_y + max_y) / 2
        clamped_min_y = clamped_max_y = mid_y
    return (
        round(_clamp(x, clamped_min_x, clamped_max_x), 2),
        round(_clamp(y, clamped_min_y, clamped_max_y), 2),
    )


def _midpoint(a: tuple[float, float], b: tuple[float, float]) -> tuple[float, float]:
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def _build_blob_path(points: list[tuple[float, float]]) -> str:
    if len(points) < 3:
        points = [(22.0, 22.0), (78.0, 22.0), (84.0, 50.0), (24.0, 56.0)]

    centroid_x = sum(x for x, _ in points) / len(points)
    centroid_y = sum(y for _, y in points) / len(points)
    expanded: list[tuple[float, float]] = []
    for x, y in points:
        dx, dy = x - centroid_x, y - centroid_y
        mag = math.hypot(dx, dy) or 1
        expanded.append(
            (
                round(_clamp(x + (dx / mag) * 10, 4, 96), 2),
                round(_clamp(y + (dy / mag) * 10, 5, 67), 2),
            )
        )

    start = _midpoint(expanded[-1], expanded[0])
    commands = [f"M {start[0]:.2f} {start[1]:.2f}"]
    for index, point in enumerate(expanded):
        nxt = expanded[(index + 1) % len(expanded)]
        end = _midpoint(point, nxt)
        commands.append(f"Q {point[0]:.2f} {point[1]:.2f} {end[0]:.2f} {end[1]:.2f}")
    commands.append("Z")
    return " ".join(commands)


def _build_generated_svg(
    seat_name: str,
    assembly_centers: dict[str, tuple[float, float]],
) -> str:
    ordered_points = list(assembly_centers.values())
    if len(ordered_points) == 1:
        cx, cy = ordered_points[0]
        ordered_points = [
            (cx - 22, cy - 10),
            (cx + 12, cy - 15),
            (cx + 24, cy + 4),
            (cx + 10, cy + 17),
            (cx - 18, cy + 14),
        ]

    path = _build_blob_path(ordered_points)
    labels = []
    if len(assembly_centers) <= 10:
        for assembly, (x, y) in assembly_centers.items():
            short_label = escape((assembly or "").strip()[:18] or "Assembly")
            labels.append(
                f'<text x="{x:.2f}" y="{y + 0.8:.2f}" text-anchor="middle" '
                f'font-family="Georgia, serif" font-size="3.1" fill="#6B7F76" opacity="0.75">{short_label}</text>'
            )

    title = escape(seat_name or "Constituency")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}" '
        f'width="{CANVAS_WIDTH}" height="{CANVAS_HEIGHT}" role="img" aria-label="{title} generated constituency map">'
        '<defs>'
        '<linearGradient id="seatFill" x1="0%" x2="100%" y1="0%" y2="100%">'
        '<stop offset="0%" stop-color="#F6F0E1" />'
        '<stop offset="100%" stop-color="#ECE3CE" />'
        '</linearGradient>'
        '</defs>'
        f'<rect width="{CANVAS_WIDTH}" height="{CANVAS_HEIGHT}" fill="#FBF7EE" />'
        f'<path d="{path}" fill="url(#seatFill)" stroke="#B7B09A" stroke-width="0.7" stroke-dasharray="1.4 1.8" />'
        '<path d="M 8 56 C 24 49, 37 53, 52 49 S 79 46, 94 45" stroke="#8FA2B1" stroke-width="0.7" fill="none" opacity="0.48" />'
        + "".join(labels)
        + "</svg>"
    )


def _extract_localities(
    seat_type: str,
    seat_name: str,
) -> dict[str, list[str]]:
    raw = get_geography_data(seat_type=seat_type, seat_name=seat_name)
    assemblies: dict[str, list[str]] = defaultdict(list)
    for assembly_name, stations in (raw or {}).items():
        for station in stations or []:
            locality = str((station or {}).get("locality") or "").strip()
            if locality:
                assemblies[assembly_name.strip()].append(locality)
    return {assembly: _dedupe_preserve(localities) for assembly, localities in assemblies.items() if localities}


def _collect_geojson_points(geojson: dict[str, Any]) -> list[tuple[float, float]]:
    features = []
    if geojson.get("type") == "FeatureCollection":
        features = geojson.get("features") or []
    elif geojson.get("type") == "Feature":
        features = [geojson]

    points: list[tuple[float, float]] = []
    for feature in features:
        geometry = feature.get("geometry") or {}
        min_x, min_y, max_x, max_y = _compute_bbox(geometry)
        if max_x > min_x or max_y > min_y:
            for node in ((geometry or {}).get("coordinates") or []):
                points.extend(_iter_points(node))
    return points


def _iter_points(node: Any):
    if isinstance(node, (list, tuple)):
        if len(node) >= 2 and all(isinstance(part, (int, float)) for part in node[:2]):
            yield float(node[0]), float(node[1])
            return
        for child in node:
            yield from _iter_points(child)


def _build_geojson_projector(geojson: dict[str, Any]) -> tuple[tuple[float, float, float, float], Any] | None:
    points = _collect_geojson_points(geojson)
    if not points:
        return None

    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    min_x = min(xs)
    max_x = max(xs)
    min_y = min(ys)
    max_y = max(ys)
    width = max(max_x - min_x, 1)
    height = max(max_y - min_y, 1)
    padding = 6
    usable_width = 100 - padding * 2
    usable_height = 72 - padding * 2
    scale = min(usable_width / width, usable_height / height)
    offset_x = (100 - width * scale) / 2
    offset_y = (72 - height * scale) / 2

    def project(point: tuple[float, float]) -> tuple[float, float]:
        x = offset_x + (point[0] - min_x) * scale
        y = 72 - (offset_y + (point[1] - min_y) * scale)
        return (round(x, 2), round(y, 2))

    return ((min_x, min_y, max_x, max_y), project)


def _assembly_segments_for_parliamentary_map(
    *,
    seat_name: str,
    state: str,
    parliamentary_geojson: dict[str, Any],
    parliamentary_boundary_metadata: dict[str, Any] | None = None,
    seat_aliases: list[str] | None = None,
) -> tuple[dict[str, tuple[float, float]], dict[str, tuple[float, float, float, float]], dict[str, Any] | None]:
    assembly_features = get_builtin_assembly_features_for_parliamentary_seat(
        seat_name=seat_name,
        parliamentary_pc_no=(parliamentary_boundary_metadata or {}).get("pc_no"),
        aliases=(seat_aliases or []) + list((parliamentary_boundary_metadata or {}).get("aliases") or []),
        state=state,
    )
    if not assembly_features:
        return {}, {}, None

    projected = _build_geojson_projector(parliamentary_geojson)
    if not projected:
        return {}, {}, None

    _, project = projected
    centers: dict[str, tuple[float, float]] = {}
    bounds_by_assembly: dict[str, tuple[float, float, float, float]] = {}
    overlay_features: list[dict[str, Any]] = []

    for feature in assembly_features:
        props = feature.get("properties") or {}
        assembly_name = str(props.get("AC_NAME") or "").strip()
        if not assembly_name:
            continue
        geometry = feature.get("geometry") or {}
        min_x, min_y, max_x, max_y = _compute_bbox(geometry)
        if max_x <= min_x and max_y <= min_y:
            continue
        center = project(((min_x + max_x) / 2, (min_y + max_y) / 2))
        top_left = project((min_x, max_y))
        bottom_right = project((max_x, min_y))
        bounds_by_assembly[assembly_name] = (
            min(top_left[0], bottom_right[0]),
            max(top_left[0], bottom_right[0]),
            min(top_left[1], bottom_right[1]),
            max(top_left[1], bottom_right[1]),
        )
        centers[assembly_name] = center
        overlay_features.append(feature)

    if not overlay_features:
        return {}, {}, None

    return centers, bounds_by_assembly, {"type": "FeatureCollection", "features": overlay_features}


def generate_seat_map_manifest(
    *,
    seat_type: str,
    seat_name: str,
    state: str = "",
    aliases: list[str] | None = None,
    seat_key: str | None = None,
) -> dict[str, Any]:
    clean_seat_type = "mla" if (seat_type or "").strip().lower() == "mla" else "mp"
    clean_seat_name = (seat_name or "").strip()
    if not clean_seat_name:
        raise ValueError("seat_name is required")

    assemblies = _extract_localities(clean_seat_type, clean_seat_name)
    if not assemblies:
        raise ValueError("No shared geography found for this seat. Upload geography first.")

    assembly_names = sorted(assemblies)
    assembly_centers = _assembly_centers(assembly_names)
    assembly_bounds: dict[str, tuple[float, float, float, float]] = {}
    features: list[dict[str, Any]] = []
    seen_feature_keys: dict[str, int] = defaultdict(int)

    for assembly in assembly_names:
        localities = assemblies[assembly]
        center_x, center_y = assembly_centers[assembly]
        total = len(localities)
        for index, locality in enumerate(localities):
            x, y = _point_for_locality_with_bounds(
                center_x,
                center_y,
                index,
                total,
                assembly_bounds.get(assembly),
            )
            base_key = _slugify(locality)
            seen_feature_keys[base_key] += 1
            feature_key = base_key if seen_feature_keys[base_key] == 1 else f"{base_key}-{seen_feature_keys[base_key]}"
            feature_aliases = _dedupe_preserve([
                locality,
                f"{locality} {assembly}".strip(),
                f"{locality} {clean_seat_name}".strip(),
            ])
            features.append(
                {
                    "feature_key": feature_key,
                    "label": locality,
                    "aliases": feature_aliases,
                    "anchor": {"x": x, "y": y},
                }
            )

    fallback_anchors = []
    ordered_centers = [assembly_centers[assembly] for assembly in assembly_names]
    for index in range(max(8, len(ordered_centers))):
        if ordered_centers:
            source_x, source_y = ordered_centers[index % len(ordered_centers)]
            fallback_anchors.append(
                {
                    "x": round(_clamp(source_x + ((index % 3) - 1) * 5.5, 8, 92), 2),
                    "y": round(_clamp(source_y + ((index % 2) * 5.5) - 2.75, 10, 64), 2),
                }
            )

    auto_aliases = _dedupe_preserve((aliases or []) + [clean_seat_name])
    boundary = get_seat_boundary_for_identity(clean_seat_type, clean_seat_name)
    if not boundary:
        try:
            if clean_seat_type == "mp":
                boundary = import_builtin_parliamentary_boundary_for_seat(
                    seat_name=clean_seat_name,
                    state=(state or "").strip(),
                )
            else:
                boundary = import_builtin_assembly_boundary_for_seat(
                    seat_name=clean_seat_name,
                    state=(state or "").strip(),
                )
        except Exception:
            boundary = None
    if boundary and (
        (boundary.get("asset") or {}).get("path")
        or (boundary.get("asset") or {}).get("inline_svg")
        or (boundary.get("asset") or {}).get("geojson")
    ):
        parliamentary_geojson = (boundary.get("asset") or {}).get("geojson") or {}
        assembly_geojson = None
        if clean_seat_type == "mp" and parliamentary_geojson:
            real_centers, real_bounds, assembly_geojson = _assembly_segments_for_parliamentary_map(
                seat_name=clean_seat_name,
                state=(state or "").strip(),
                parliamentary_geojson=parliamentary_geojson,
                parliamentary_boundary_metadata=boundary.get("metadata") or {},
                seat_aliases=auto_aliases,
            )
            if real_centers:
                assembly_centers = {**assembly_centers, **real_centers}
                assembly_bounds = real_bounds
                features = []
                seen_feature_keys = defaultdict(int)
                for assembly in assembly_names:
                    localities = assemblies[assembly]
                    center_x, center_y = assembly_centers.get(assembly, (50.0, 36.0))
                    total = len(localities)
                    for index, locality in enumerate(localities):
                        x, y = _point_for_locality_with_bounds(
                            center_x,
                            center_y,
                            index,
                            total,
                            assembly_bounds.get(assembly),
                        )
                        base_key = _slugify(locality)
                        seen_feature_keys[base_key] += 1
                        feature_key = base_key if seen_feature_keys[base_key] == 1 else f"{base_key}-{seen_feature_keys[base_key]}"
                        feature_aliases = _dedupe_preserve([
                            locality,
                            f"{locality} {assembly}".strip(),
                            f"{locality} {clean_seat_name}".strip(),
                        ])
                        features.append(
                            {
                                "feature_key": feature_key,
                                "label": locality,
                                "aliases": feature_aliases,
                                "anchor": {"x": x, "y": y},
                                "assembly": assembly,
                            }
                        )
        asset = {
            "type": (boundary.get("asset") or {}).get("type") or "svg",
            "path": (boundary.get("asset") or {}).get("path") or "",
            "inline_svg": (boundary.get("asset") or {}).get("inline_svg") or "",
            "geojson": parliamentary_geojson,
            "assembly_geojson": assembly_geojson or {},
            "aspect_ratio": (boundary.get("metadata") or {}).get("aspect_ratio") or f"{CANVAS_WIDTH} / {CANVAS_HEIGHT}",
            "generated": False,
            "boundary_source": boundary.get("source") or "admin",
        }
        source = "generated-from-boundary"
    else:
        svg_markup = _build_generated_svg(clean_seat_name, assembly_centers)
        asset = {
            "type": "generated-svg",
            "aspect_ratio": f"{CANVAS_WIDTH} / {CANVAS_HEIGHT}",
            "inline_svg": svg_markup,
            "generated": True,
        }
        source = "generated"
    return {
        "seat_key": seat_key or build_seat_key(clean_seat_type, clean_seat_name),
        "seat_type": clean_seat_type,
        "seat_name": clean_seat_name,
        "state": (state or "").strip(),
        "aliases": auto_aliases,
        "asset": asset,
        "features": features,
        "fallback_anchors": fallback_anchors[:12],
        "status": "draft",
        "version": 1,
        "source": source,
    }
