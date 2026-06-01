from __future__ import annotations

import math
import re
from collections import defaultdict
from html import escape
from typing import Any

from sansadx_backend.db import build_seat_key, get_geography_data
from modules.seat_boundaries import get_seat_boundary_for_identity
from modules.parliamentary_boundary_importer import import_builtin_parliamentary_boundary_for_seat


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
    features: list[dict[str, Any]] = []
    seen_feature_keys: dict[str, int] = defaultdict(int)

    for assembly in assembly_names:
        localities = assemblies[assembly]
        center_x, center_y = assembly_centers[assembly]
        total = len(localities)
        for index, locality in enumerate(localities):
            x, y = _point_for_locality(center_x, center_y, index, total)
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
    if not boundary and clean_seat_type == "mp":
        try:
            boundary = import_builtin_parliamentary_boundary_for_seat(
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
        asset = {
            "type": (boundary.get("asset") or {}).get("type") or "svg",
            "path": (boundary.get("asset") or {}).get("path") or "",
            "inline_svg": (boundary.get("asset") or {}).get("inline_svg") or "",
            "geojson": (boundary.get("asset") or {}).get("geojson") or {},
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
