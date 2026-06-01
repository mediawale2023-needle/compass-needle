from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import text

from sansadx_backend.db import SessionLocal


REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_MAPS_DIR = REPO_ROOT / "frontend" / "data" / "maps"
REGISTRY_PATH = FRONTEND_MAPS_DIR / "registry.json"


def _normalize(value: str | None) -> str:
    return " ".join(
        "".join(ch.lower() if ch.isalnum() else " " for ch in str(value or "")).split()
    )


def clear_seat_map_caches() -> None:
    load_seat_registry.cache_clear()
    load_repo_seat_manifest.cache_clear()


def _coerce_jsonish(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return fallback
    return fallback


def _build_manifest_payload(
    *,
    seat_key: str,
    seat_type: str,
    seat_name: str,
    state: str | None,
    aliases: list[Any] | None,
    asset: dict[str, Any] | None,
    features: list[Any] | None,
    fallback_anchors: list[Any] | None,
    status: str | None,
    version: int | None,
    source: str | None,
) -> dict[str, Any]:
    return {
        "seat_key": seat_key,
        "seat_type": seat_type,
        "seat_name": seat_name,
        "state": state,
        "aliases": _coerce_jsonish(aliases, []),
        "asset": _coerce_jsonish(asset, {}),
        "features": _coerce_jsonish(features, []),
        "fallback_anchors": _coerce_jsonish(fallback_anchors, []),
        "status": status or "draft",
        "version": version or 1,
        "source": source or "unknown",
    }


@lru_cache(maxsize=1)
def load_seat_registry() -> list[dict[str, Any]]:
    if not REGISTRY_PATH.exists():
        return []
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=32)
def load_repo_seat_manifest(manifest_key: str) -> dict[str, Any] | None:
    registry = {entry.get("manifest_key"): entry for entry in load_seat_registry()}
    entry = registry.get(manifest_key)
    if not entry:
        return None

    seat_type = str(entry.get("seat_type") or "").strip()
    slug = manifest_key.split(":", 1)[-1]
    manifest_path = FRONTEND_MAPS_DIR / seat_type / f"{slug}.manifest.json"
    if not manifest_path.exists():
        return None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return _build_manifest_payload(
        seat_key=manifest.get("seat_key"),
        seat_type=manifest.get("seat_type"),
        seat_name=manifest.get("seat_name"),
        state=manifest.get("state"),
        aliases=entry.get("aliases") or [],
        asset=manifest.get("asset"),
        features=manifest.get("features"),
        fallback_anchors=manifest.get("fallback_anchors"),
        status=entry.get("status"),
        version=entry.get("version"),
        source="repo",
    )


def get_db_seat_manifest(seat_key: str) -> dict[str, Any] | None:
    db = SessionLocal()
    try:
        row = db.execute(
            text(
                """
                SELECT seat_key, seat_type, seat_name, state, aliases, asset, features,
                       fallback_anchors, status, version, source
                FROM seat_map_manifests
                WHERE seat_key = :seat_key
                LIMIT 1
                """
            ),
            {"seat_key": seat_key},
        ).mappings().first()
        if not row:
            return None
        return _build_manifest_payload(
            seat_key=row.get("seat_key"),
            seat_type=row.get("seat_type"),
            seat_name=row.get("seat_name"),
            state=row.get("state"),
            aliases=row.get("aliases"),
            asset=row.get("asset"),
            features=row.get("features"),
            fallback_anchors=row.get("fallback_anchors"),
            status=row.get("status"),
            version=row.get("version"),
            source=row.get("source") or "admin",
        )
    finally:
        db.close()


def list_all_seat_manifests() -> list[dict[str, Any]]:
    manifests: dict[str, dict[str, Any]] = {}

    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT seat_key, seat_type, seat_name, state, aliases, asset, features,
                       fallback_anchors, status, version, source
                FROM seat_map_manifests
                ORDER BY seat_type, seat_name
                """
            )
        ).mappings().all()
    finally:
        db.close()

    for row in rows:
        payload = _build_manifest_payload(
            seat_key=row.get("seat_key"),
            seat_type=row.get("seat_type"),
            seat_name=row.get("seat_name"),
            state=row.get("state"),
            aliases=row.get("aliases"),
            asset=row.get("asset"),
            features=row.get("features"),
            fallback_anchors=row.get("fallback_anchors"),
            status=row.get("status"),
            version=row.get("version"),
            source=row.get("source") or "admin",
        )
        manifests[payload["seat_key"]] = payload

    for entry in load_seat_registry():
        manifest_key = str(entry.get("manifest_key") or "")
        if not manifest_key or manifest_key in manifests:
            continue
        payload = load_repo_seat_manifest(manifest_key)
        if payload:
            manifests[manifest_key] = payload

    return [manifests[key] for key in sorted(manifests)]


def upsert_db_seat_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    db = SessionLocal()
    try:
        existing = db.execute(
            text("SELECT id, version FROM seat_map_manifests WHERE seat_key = :seat_key"),
            {"seat_key": payload["seat_key"]},
        ).mappings().first()

        version = int(payload.get("version") or 1)
        if existing and not payload.get("version"):
            version = int(existing.get("version") or 1) + 1

        values = {
            "seat_key": payload["seat_key"],
            "seat_type": payload["seat_type"],
            "seat_name": payload["seat_name"],
            "state": payload.get("state"),
            "aliases": json.dumps(payload.get("aliases") or []),
            "asset": json.dumps(payload.get("asset") or {}),
            "features": json.dumps(payload.get("features") or []),
            "fallback_anchors": json.dumps(payload.get("fallback_anchors") or []),
            "status": payload.get("status") or "draft",
            "version": version,
            "source": payload.get("source") or "admin",
        }

        if existing:
            db.execute(
                text(
                    """
                    UPDATE seat_map_manifests
                    SET seat_type = :seat_type,
                        seat_name = :seat_name,
                        state = :state,
                        aliases = :aliases,
                        asset = :asset,
                        features = :features,
                        fallback_anchors = :fallback_anchors,
                        status = :status,
                        version = :version,
                        source = :source,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE seat_key = :seat_key
                    """
                ),
                values,
            )
        else:
            db.execute(
                text(
                    """
                    INSERT INTO seat_map_manifests
                        (seat_key, seat_type, seat_name, state, aliases, asset, features,
                         fallback_anchors, status, version, source, created_at, updated_at)
                    VALUES
                        (:seat_key, :seat_type, :seat_name, :state, :aliases, :asset, :features,
                         :fallback_anchors, :status, :version, :source, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """
                ),
                values,
            )
        db.commit()
        clear_seat_map_caches()
        return get_db_seat_manifest(payload["seat_key"]) or payload
    finally:
        db.close()


def get_seat_manifest_for_identity(seat_type: str | None, constituency: str | None) -> dict[str, Any] | None:
    normalized_seat_type = _normalize(seat_type)
    normalized_constituency = _normalize(constituency)

    if not normalized_seat_type or not normalized_constituency:
        return None

    # Prefer admin-managed DB manifests first.
    for manifest in list_all_seat_manifests():
        if _normalize(manifest.get("seat_type")) != normalized_seat_type:
            continue
        aliases = manifest.get("aliases") or []
        if any(_normalize(alias) == normalized_constituency for alias in aliases):
            return manifest
    return None
