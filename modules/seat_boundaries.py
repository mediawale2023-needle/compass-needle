from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from sansadx_backend.db import SessionLocal, build_seat_key


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


def _build_boundary_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "seat_key": row.get("seat_key"),
        "seat_type": row.get("seat_type"),
        "seat_name": row.get("seat_name"),
        "state": row.get("state") or "",
        "asset": {
            "type": row.get("asset_type") or "svg",
            "path": row.get("asset_path") or "",
            "inline_svg": row.get("inline_svg") or "",
            "geojson": _coerce_jsonish(row.get("geojson"), {}),
        },
        "metadata": _coerce_jsonish(row.get("metadata_json"), {}),
        "status": row.get("status") or "draft",
        "source": row.get("source") or "admin",
    }


def get_seat_boundary(seat_key: str) -> dict[str, Any] | None:
    db = SessionLocal()
    try:
        row = db.execute(
            text(
                """
                SELECT seat_key, seat_type, seat_name, state, asset_type, asset_path, inline_svg,
                       geojson, metadata_json, status, source
                FROM seat_boundary_assets
                WHERE seat_key = :seat_key
                LIMIT 1
                """
            ),
            {"seat_key": seat_key},
        ).mappings().first()
        if not row:
            return None
        return _build_boundary_payload(row)
    finally:
        db.close()


def get_seat_boundary_for_identity(seat_type: str | None, seat_name: str | None) -> dict[str, Any] | None:
    return get_seat_boundary(build_seat_key(seat_type, seat_name))


def upsert_seat_boundary(payload: dict[str, Any]) -> dict[str, Any]:
    db = SessionLocal()
    try:
        values = {
            "seat_key": payload["seat_key"],
            "seat_type": payload["seat_type"],
            "seat_name": payload["seat_name"],
            "state": payload.get("state") or "",
            "asset_type": payload.get("asset", {}).get("type") or "svg",
            "asset_path": payload.get("asset", {}).get("path") or "",
            "inline_svg": payload.get("asset", {}).get("inline_svg") or "",
            "geojson": json.dumps(payload.get("asset", {}).get("geojson") or {}),
            "metadata_json": json.dumps(payload.get("metadata") or {}),
            "status": payload.get("status") or "draft",
            "source": payload.get("source") or "admin",
        }
        existing = db.execute(
            text("SELECT id FROM seat_boundary_assets WHERE seat_key = :seat_key"),
            {"seat_key": values["seat_key"]},
        ).mappings().first()
        if existing:
            db.execute(
                text(
                    """
                    UPDATE seat_boundary_assets
                    SET seat_type = :seat_type,
                        seat_name = :seat_name,
                        state = :state,
                        asset_type = :asset_type,
                        asset_path = :asset_path,
                        inline_svg = :inline_svg,
                        geojson = :geojson,
                        metadata_json = :metadata_json,
                        status = :status,
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
                    INSERT INTO seat_boundary_assets
                        (seat_key, seat_type, seat_name, state, asset_type, asset_path, inline_svg,
                         geojson, metadata_json, status, source, created_at, updated_at)
                    VALUES
                        (:seat_key, :seat_type, :seat_name, :state, :asset_type, :asset_path, :inline_svg,
                         :geojson, :metadata_json, :status, :source, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """
                ),
                values,
            )
        db.commit()
        return get_seat_boundary(values["seat_key"]) or payload
    finally:
        db.close()
