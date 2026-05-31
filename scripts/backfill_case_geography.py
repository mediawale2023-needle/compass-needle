#!/usr/bin/env python3
"""Tenant-scoped backfill for blank case geography fields."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from sqlalchemy import text

import sansadx_backend.db as dbmod
from modules.geography_resolver import resolve_location, _get_tenant_constituency


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_meta(meta):
    if meta is None:
        return {}
    if isinstance(meta, dict):
        return dict(meta)
    try:
        return json.loads(meta)
    except Exception:
        return {}


def _normalize_confidence(resolution: dict) -> str:
    value = str(resolution.get("confidence_level") or "").strip().lower()
    if value in {"exact", "boundary", "fuzzy", "speech_phonetic", "manual", "unknown"}:
        return value
    match_type = str(resolution.get("match_type") or "").strip().lower()
    if match_type == "speech_phonetic":
        return "speech_phonetic"
    if match_type in {"exact_full", "exact_substring", "db_alias_exact", "god_mode"}:
        return "exact"
    if match_type in {"word_boundary", "spaceless", "db_alias_boundary"}:
        return "boundary"
    if match_type.startswith("fuzzy_") or match_type.startswith("fuzzy_phrase"):
        return "fuzzy"
    return "unknown"


def backfill_tenant_case_geography(
    *,
    tenant_id: int,
    limit: int = 500,
    overwrite: bool = False,
    dry_run: bool = False,
) -> dict:
    tenant_scope = _get_tenant_constituency(tenant_id)
    params = {"tenant_id": tenant_id, "limit": limit}
    rows = []
    query = """
        SELECT id, raw_message, location, assembly, case_metadata
        FROM cases
        WHERE tenant_id = :tenant_id
          AND is_deleted = false
        ORDER BY created_at DESC
    """
    with dbmod.engine.connect() as conn:
        result = conn.execute(text(query), params)
        rows = [dict(row._mapping) for row in result]

    candidates = []
    for row in rows:
        meta = _parse_meta(row.get("case_metadata"))
        current_location = str(row.get("location") or meta.get("matched_value") or "").strip()
        current_assembly = str(row.get("assembly") or meta.get("assembly_constituency") or "").strip()
        needs_fill = not current_location or not current_assembly or current_assembly == "Unknown"
        if overwrite or needs_fill:
            candidates.append(row)
        if len(candidates) >= limit:
            break

    updated = 0
    unresolved = 0
    examined = 0
    samples = []

    for row in candidates:
        examined += 1
        resolution = resolve_location(
            row.get("raw_message") or row.get("location") or "",
            scope_parliamentary=tenant_scope,
            tenant_id=tenant_id,
        )
        meta = _parse_meta(row.get("case_metadata"))
        diagnostics = {
            "version": 1,
            "tenant_id": tenant_id,
            "tenant_scope": tenant_scope,
            "source": "backfill_case_geography",
            "attempts": [
                {
                    "source": "raw_message",
                    "input_excerpt": str(row.get("raw_message") or "")[:160],
                    "location_resolved": bool(resolution.get("location_resolved")),
                    "matched_value": str(resolution.get("matched_value") or "")[:160],
                    "assembly_constituency": str(resolution.get("assembly_constituency") or ""),
                    "confidence_level": _normalize_confidence(resolution),
                    "match_type": str(resolution.get("match_type") or ""),
                    "reason": str(resolution.get("reason") or ""),
                }
            ],
        }

        if resolution.get("location_resolved"):
            location = str(resolution.get("matched_value") or "").strip()
            assembly = str(resolution.get("assembly_constituency") or "").strip()
            meta["matched_value"] = location
            meta["assembly_constituency"] = assembly
            meta["location_resolved"] = bool(location and assembly and assembly != "Unknown")
            meta["geography_confidence"] = _normalize_confidence(resolution)
            meta["geography_source"] = "backfill_raw_message"
            meta["needs_geography_review"] = meta["geography_confidence"] in {"fuzzy", "speech_phonetic"}
            if meta["needs_geography_review"]:
                meta["geography_review_reason"] = "low_confidence_match"
            else:
                meta.pop("geography_review_reason", None)
            diagnostics["final"] = {
                "location_resolved": True,
                "matched_value": location,
                "assembly_constituency": assembly,
                "status": "backfilled",
                "geography_confidence": meta["geography_confidence"],
                "geography_source": "backfill_raw_message",
                "needs_geography_review": meta["needs_geography_review"],
                "review_reason": meta.get("geography_review_reason", ""),
            }
            meta["geography_diagnostics"] = diagnostics
            if len(samples) < 10:
                samples.append({"case_id": row["id"], "location": location, "assembly": assembly, "resolved": True})
            if not dry_run:
                with dbmod.engine.begin() as conn:
                    conn.execute(
                        text(
                            """
                            UPDATE cases
                            SET location = :location,
                                assembly = :assembly,
                                case_metadata = :meta,
                                updated_at = :updated_at
                            WHERE id = :case_id AND tenant_id = :tenant_id
                            """
                        ),
                        {
                            "case_id": row["id"],
                            "tenant_id": tenant_id,
                            "location": location,
                            "assembly": assembly,
                            "meta": json.dumps(meta),
                            "updated_at": _utcnow(),
                        },
                    )
            updated += 1
        else:
            diagnostics["final"] = {
                "location_resolved": False,
                "matched_value": "",
                "assembly_constituency": "",
                "status": "unresolved",
                "geography_confidence": "unknown",
                "geography_source": "backfill_raw_message",
                "needs_geography_review": False,
                "review_reason": str(resolution.get("reason") or "unresolved"),
            }
            meta["geography_diagnostics"] = diagnostics
            if len(samples) < 10:
                samples.append({"case_id": row["id"], "resolved": False, "reason": str(resolution.get("reason") or "unresolved")})
            if not dry_run:
                with dbmod.engine.begin() as conn:
                    conn.execute(
                        text(
                            """
                            UPDATE cases
                            SET case_metadata = :meta,
                                updated_at = :updated_at
                            WHERE id = :case_id AND tenant_id = :tenant_id
                            """
                        ),
                        {
                            "case_id": row["id"],
                            "tenant_id": tenant_id,
                            "meta": json.dumps(meta),
                            "updated_at": _utcnow(),
                        },
                    )
            unresolved += 1

    return {
        "tenant_id": tenant_id,
        "tenant_scope": tenant_scope,
        "examined": examined,
        "updated": updated,
        "unresolved": unresolved,
        "dry_run": dry_run,
        "overwrite": overwrite,
        "samples": samples,
    }


def main():
    parser = argparse.ArgumentParser(description="Backfill blank case geography for one tenant.")
    parser.add_argument("--tenant-id", type=int, required=True)
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = backfill_tenant_case_geography(
        tenant_id=args.tenant_id,
        limit=args.limit,
        overwrite=args.overwrite,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
