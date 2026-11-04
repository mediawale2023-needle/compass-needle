#!/usr/bin/env python3
"""Fail-closed lifecycle for Tenant 9's Delhi synthetic filing dataset.

Dry-run is read-only. Execute and rollback are intentionally impossible until
the production database proves tenant identity and shared-seat geography.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.synthetic_cases import CANONICAL_FLAG  # noqa: E402
from sansadx_backend.db import engine, parse_geography_key  # noqa: E402
from sansadx_backend.unified_taxonomy import PROBLEM_SUBDOMAINS_BY_DOMAIN, VALID_CATEGORIES  # noqa: E402

MANIFEST_PATH = ROOT / "data" / "synthetic" / "tenant9_delhi_filing_v1.json"
CATALOGUE_PATH = ROOT / "modules" / "data" / "delhi_catalogue.json"
EXPECTED_CONFIRMATION = "TENANT9-BANSURI-SWARAJ-NEW-DELHI"
EXPECTED_ASSEMBLIES = {
    "Karol Bagh", "Patel Nagar", "Moti Nagar", "Delhi Cantt", "Rajinder Nagar",
    "New Delhi", "Kasturba Nagar", "Malviya Nagar", "R K Puram", "Greater Kailash",
}
EXPECTED_DISTRIBUTION = {
    "municipal_services": 5, "water_and_sewerage": 4, "electricity": 3,
    "public_infrastructure": 3, "social_welfare": 3, "miscellaneous_civic": 2,
}


class PreflightBlocked(RuntimeError):
    pass


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _norm(value) -> str:
    return " ".join(str(value or "").strip().lower().split())


def validate_static_manifest(manifest: dict) -> list[str]:
    errors: list[str] = []
    cases = manifest.get("cases") or []
    refs = [item.get("case_ref") for item in cases]
    expected_refs = [f"SYN-T9-DL-{idx:03d}" for idx in range(1, 21)]
    if refs != expected_refs:
        errors.append("case references must be exactly SYN-T9-DL-001 through SYN-T9-DL-020 in order")
    if len(cases) != 20:
        errors.append("manifest must contain exactly 20 cases")
    if dict(Counter(item.get("group") for item in cases)) != EXPECTED_DISTRIBUTION:
        errors.append("case-group distribution does not match the approved 5/4/3/3/3/2 split")
    if {item.get("assembly") for item in cases} - EXPECTED_ASSEMBLIES:
        errors.append("manifest contains an assembly outside New Delhi parliamentary constituency")
    if {item.get("assembly") for item in cases} != EXPECTED_ASSEMBLIES:
        errors.append("manifest must exercise all ten verified New Delhi assembly segments")
    for item in cases:
        domain = item.get("problem_domain")
        if item.get("category") not in VALID_CATEGORIES or domain not in VALID_CATEGORIES:
            errors.append(f"{item.get('case_ref')}: unsupported category/domain")
        elif item.get("problem_subdomain") not in PROBLEM_SUBDOMAINS_BY_DOMAIN[domain]:
            errors.append(f"{item.get('case_ref')}: unsupported subdomain")
        if not all(item.get(field) for field in ("title", "description", "locality", "department", "created_at")):
            errors.append(f"{item.get('case_ref')}: required manifest field missing")
    catalogue = json.loads(CATALOGUE_PATH.read_text(encoding="utf-8"))
    departments = {row["name"] for row in catalogue.get("departments", [])}
    for item in cases:
        if item.get("department") not in departments:
            errors.append(f"{item.get('case_ref')}: department is absent from Delhi catalogue")
    return errors


def _tenant_preflight(conn, manifest: dict) -> dict:
    tenant = conn.execute(text("""
        SELECT t.id, t.name, t.constituency, t.tenant_type, t.account_stage,
               t.seat_type, t.is_active, tp.mp_name, tp.constituency AS profile_constituency,
               tp.state, tp.house
        FROM tenants t LEFT JOIN tenant_profiles tp ON tp.tenant_id = t.id
        WHERE t.id = :tid
    """), {"tid": manifest["tenant_id"]}).mappings().first()
    if not tenant:
        raise PreflightBlocked("Tenant 9 does not exist")
    checks = {
        "name": _norm(tenant["name"]) == _norm(manifest["expected_tenant_name"]),
        "profile_name": not tenant.get("mp_name") or _norm(tenant["mp_name"]) == _norm(manifest["expected_tenant_name"]),
        "constituency": _norm(tenant["constituency"]) == "new delhi",
        "profile_constituency": not tenant.get("profile_constituency") or _norm(tenant["profile_constituency"]) == "new delhi",
        "seat_type": _norm(tenant["seat_type"] or tenant["tenant_type"]) == "mp",
        "state": _norm(tenant["state"]) in {"delhi", "nct of delhi", "national capital territory of delhi"},
        "active": tenant["is_active"] is not False,
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise PreflightBlocked("Tenant identity mismatch: " + ", ".join(failed))
    return dict(tenant)


def _geography_preflight(conn, manifest: dict) -> dict[str, str]:
    rows = conn.execute(text("""
        SELECT key, value FROM tenant_overrides
        WHERE override_type = 'geography_data'
          AND (tenant_id = :tid OR tenant_id IS NULL)
    """), {"tid": manifest["tenant_id"]}).mappings().all()
    mapped: dict[str, set[str]] = {}
    keys: dict[str, str] = {}
    for row in rows:
        seat_type, seat_name, assembly = parse_geography_key(row["key"])
        if seat_type != "mp" or _norm(seat_name) != "new delhi" or assembly not in EXPECTED_ASSEMBLIES:
            continue
        keys[assembly] = row["key"]
        try:
            payload = row["value"] if isinstance(row["value"], (list, dict)) else json.loads(row["value"])
        except (TypeError, ValueError):
            raise PreflightBlocked(f"Invalid geography JSON for {row['key']}")
        entries = payload if isinstance(payload, list) else [payload]
        mapped.setdefault(assembly, set()).update(
            _norm(entry.get("locality") or entry.get("building_name"))
            for entry in entries if isinstance(entry, dict) and (entry.get("locality") or entry.get("building_name"))
        )
    missing_assemblies = EXPECTED_ASSEMBLIES - set(keys)
    if missing_assemblies:
        raise PreflightBlocked("NEEDLE geography missing assemblies: " + ", ".join(sorted(missing_assemblies)))
    missing_localities = [
        f"{item['case_ref']}:{item['locality']}" for item in manifest["cases"]
        if _norm(item["locality"]) not in mapped.get(item["assembly"], set())
    ]
    if missing_localities:
        raise PreflightBlocked("NEEDLE geography does not verify localities: " + ", ".join(missing_localities))
    return keys


def _counts(conn, tenant_id: int) -> dict:
    return dict(conn.execute(text("""
        SELECT COUNT(*) AS total,
               COUNT(*) FILTER (WHERE is_deleted IS NOT TRUE) AS active,
               COUNT(*) FILTER (WHERE is_deleted IS TRUE) AS deleted,
               COUNT(*) FILTER (WHERE govt_reference_number IS NOT NULL AND govt_reference_number <> '') AS government_linked
        FROM cases WHERE tenant_id = :tid
    """), {"tid": tenant_id}).mappings().one())


def _collision_preflight(conn, manifest: dict) -> None:
    refs = [item["case_ref"] for item in manifest["cases"]]
    collisions = conn.execute(text("""
        SELECT id, tenant_id, case_ref FROM cases
        WHERE case_ref = ANY(:refs)
           OR (tenant_id = :tid AND case_metadata::jsonb->>'synthetic_batch_id' = :batch)
    """), {"refs": refs, "tid": manifest["tenant_id"], "batch": manifest["batch_id"]}).mappings().all()
    if collisions:
        raise PreflightBlocked(f"Existing case-reference/batch collision ({len(collisions)} rows); refusing to continue")


def run_preflight(conn, manifest: dict) -> dict:
    errors = validate_static_manifest(manifest)
    if errors:
        raise PreflightBlocked("; ".join(errors))
    tenant = _tenant_preflight(conn, manifest)
    geography_keys = _geography_preflight(conn, manifest)
    _collision_preflight(conn, manifest)
    return {"tenant": tenant, "geography_keys": geography_keys, "counts": _counts(conn, manifest["tenant_id"])}


def _metadata(manifest: dict, item: dict, geography_key: str) -> dict:
    return {
        CANONICAL_FLAG: True,
        "source": manifest["source"],
        "synthetic_batch_id": manifest["batch_id"],
        "synthetic_manifest_version": manifest["schema_version"],
        "title": item["title"],
        "summary": item["title"],
        "synthetic_group": item["group"],
        "suggested_delhi_department": item["department"],
        "suggestion_only_not_forwarded": True,
        "parliamentary_constituency": manifest["parliamentary_constituency"],
        "assembly_constituency": item["assembly"],
        "matched_value": item["locality"],
        "geography_key": geography_key,
        "location_resolved": True,
        "user_intent": "complaint",
        "external_actions_disabled": True,
    }


def execute(conn, manifest: dict, preflight: dict) -> list[int]:
    inserted: list[int] = []
    for idx, item in enumerate(manifest["cases"], start=1):
        row = conn.execute(text("""
            INSERT INTO cases (
                tenant_id, user_phone, raw_message, category, problem_domain, problem_subdomain,
                status, location, ward, assembly, is_critical, priority, response_to_citizen,
                notes_for_staff, case_metadata, created_at, updated_at, status_changed_at,
                is_deleted, case_ref, govt_portal_id, govt_department, govt_reference_number,
                govt_status, govt_status_updated_at, govt_last_forwarded_to_citizen_at,
                govt_submission_worksheet
            ) VALUES (
                :tid, :phone, :description, :category, :domain, :subdomain,
                'new', :locality, :locality, :assembly, false, 'standard', NULL,
                :notes, CAST(:metadata AS JSONB), :created_at, :created_at, :created_at,
                false, :case_ref, NULL, NULL, NULL, 'not_forwarded', NULL, NULL, NULL
            ) RETURNING id
        """), {
            "tid": manifest["tenant_id"], "phone": f"synthetic:test:tenant9:{idx:03d}",
            "description": item["description"], "category": item["category"],
            "domain": item["problem_domain"], "subdomain": item["problem_subdomain"],
            "locality": item["locality"], "assembly": item["assembly"],
            "notes": "SYNTHETIC TEST DATA — do not contact a citizen or submit to a government portal.",
            "metadata": json.dumps(_metadata(manifest, item, preflight["geography_keys"][item["assembly"]])),
            "created_at": datetime.fromisoformat(item["created_at"].replace("Z", "+00:00")).replace(tzinfo=None),
            "case_ref": item["case_ref"],
        }).scalar_one()
        inserted.append(row)
    if len(inserted) != 20:
        raise PreflightBlocked("transaction did not insert exactly 20 rows")
    return inserted


def rollback_preflight(conn, manifest: dict) -> list[int]:
    rows = conn.execute(text("""
        SELECT id, case_ref, govt_portal_id, govt_reference_number, govt_status,
               govt_last_forwarded_to_citizen_at
        FROM cases
        WHERE tenant_id = :tid AND case_metadata::jsonb->>'synthetic_batch_id' = :batch
        ORDER BY case_ref
    """), {"tid": manifest["tenant_id"], "batch": manifest["batch_id"]}).mappings().all()
    expected = [item["case_ref"] for item in manifest["cases"]]
    if [row["case_ref"] for row in rows] != expected:
        raise PreflightBlocked("rollback batch is partial, duplicated or has unexpected references")
    ids = [row["id"] for row in rows]
    if any(row["govt_portal_id"] or row["govt_reference_number"] or row["govt_last_forwarded_to_citizen_at"] or row["govt_status"] not in (None, "not_forwarded") for row in rows):
        raise PreflightBlocked("rollback aborted: a case acquired government or notification state")
    activity = conn.execute(text("SELECT COUNT(*) FROM case_activity_log WHERE tenant_id = :tid AND case_id = ANY(:ids)"), {"tid": manifest["tenant_id"], "ids": ids}).scalar_one()
    govt_logs = conn.execute(text("SELECT COUNT(*) FROM govt_submission_log WHERE tenant_id = :tid AND case_id = ANY(:ids)"), {"tid": manifest["tenant_id"], "ids": ids}).scalar_one()
    if activity or govt_logs:
        raise PreflightBlocked("rollback aborted: cases have staff or government activity")
    return ids


def _environment_guard(args, conn) -> str:
    env = os.getenv("ENV", "development").strip().lower()
    db_name = conn.execute(text("SELECT current_database()")) .scalar_one()
    if args.execute or args.rollback:
        if env == "production":
            if args.confirm_production != EXPECTED_CONFIRMATION:
                raise PreflightBlocked("production execution requires the exact --confirm-production phrase")
            if args.confirm_database_name != db_name:
                raise PreflightBlocked("--confirm-database-name does not match the connected database")
        if conn.dialect.name == "postgresql":
            privilege = conn.execute(text("SELECT has_table_privilege(current_user, 'cases', 'INSERT,DELETE')")) .scalar_one()
            if not privilege:
                raise PreflightBlocked("database user lacks required case-table permissions")
    return db_name


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--rollback", action="store_true")
    parser.add_argument("--confirm-production", default="")
    parser.add_argument("--confirm-database-name", default="")
    args = parser.parse_args(argv)
    manifest = load_manifest()
    try:
        if args.rollback:
            with engine.begin() as conn:
                db_name = _environment_guard(args, conn)
                _tenant_preflight(conn, manifest)
                ids = rollback_preflight(conn, manifest)
                conn.execute(text("DELETE FROM cases WHERE tenant_id = :tid AND id = ANY(:ids)"), {"tid": manifest["tenant_id"], "ids": ids})
                print(json.dumps({"mode": "rollback", "database": db_name, "deleted_ids": ids}, default=str))
        else:
            context = engine.begin() if args.execute else engine.connect()
            with context as conn:
                db_name = _environment_guard(args, conn)
                preflight = run_preflight(conn, manifest)
                result = {"mode": "execute" if args.execute else "dry-run", "database": db_name, "preflight": preflight, "manifest_count": 20}
                if args.execute:
                    result["inserted_ids"] = execute(conn, manifest, preflight)
                print(json.dumps(result, default=str))
        return 0
    except PreflightBlocked as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
