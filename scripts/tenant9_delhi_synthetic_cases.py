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
# Audit rows the Delhi staff-assisted worksheet endpoints write on a case. They are the ONLY
# dependent rows --rollback --allow-worksheet-artifacts will remove; anything else aborts.
WORKSHEET_LOG_ACTIONS = {"ai_translated", "delhi_ai_suggested", "delhi_filing_worksheet_saved"}
WORKSHEET_ACTIVITY_ACTIONS = {"govt_delhi_worksheet_drafted", "govt_delhi_filing_saved"}
WORKSHEET_STATUSES = (None, "not_forwarded", "pending_staff_submit")
REQUIRED_CASE_COLUMNS = {
    "id", "tenant_id", "user_phone", "raw_message", "category", "problem_domain", "problem_subdomain",
    "status", "location", "ward", "assembly", "is_critical", "priority", "response_to_citizen",
    "notes_for_staff", "case_metadata", "created_at", "updated_at", "status_changed_at", "is_deleted",
    "case_ref", "govt_portal_id", "govt_department", "govt_reference_number", "govt_status",
    "govt_status_updated_at", "govt_last_forwarded_to_citizen_at", "govt_submission_worksheet", "resolved_at",
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
    # Mirrors sansadx_backend.db.get_geography_data(): geography_data rows are shared seat geography and are
    # matched by seat, NOT by tenant_id (the app never filters them by tenant).
    rows = conn.execute(text("""
        SELECT key, value FROM tenant_overrides WHERE override_type = 'geography_data'
    """)).mappings().all()
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
        if not isinstance(payload, list):
            continue  # the app ignores non-list payloads, so they cannot verify anything
        entries = payload
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


def _schema_preflight(conn) -> list[tuple[str, str]]:
    """Fail closed unless this is the PostgreSQL schema the script was written for. Returns every
    (table, column) that holds a foreign key to cases(id), discovered from the catalogue."""
    if conn.dialect.name != "postgresql":
        raise PreflightBlocked("a PostgreSQL database is required")
    columns = {r[0]: r[1] for r in conn.execute(text(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = current_schema() AND table_name = 'cases'")).all()}
    missing = sorted(REQUIRED_CASE_COLUMNS - set(columns))
    if missing:
        raise PreflightBlocked("cases table is missing columns: " + ", ".join(missing))
    if columns["case_metadata"] not in {"json", "jsonb"}:
        raise PreflightBlocked(f"cases.case_metadata is {columns['case_metadata']}, expected json/jsonb")
    return [(r[0], r[1]) for r in conn.execute(text("""
        SELECT cl.relname, a.attname
        FROM pg_constraint c
        JOIN pg_class cl ON cl.oid = c.conrelid
        JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
        WHERE c.contype = 'f' AND c.confrelid = 'cases'::regclass
        ORDER BY 1, 2""")).all()]


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
    _schema_preflight(conn)
    tenant = _tenant_preflight(conn, manifest)
    geography_keys = _geography_preflight(conn, manifest)
    _collision_preflight(conn, manifest)
    return {"tenant": tenant, "geography_keys": geography_keys, "counts": _counts(conn, manifest["tenant_id"])}


def redacted_report(preflight: dict) -> dict:
    """What a dry-run may print. CI logs of this repository are public, so no tenant name, database name,
    phone number, geography key or any other identifying value is included - only pass/fail and counts."""
    tenant = preflight["tenant"]
    return {
        "tenant_id": tenant["id"],
        "tenant_identity_verified": True,
        "constituency_verified": True,
        "geography_segments_verified": len(preflight["geography_keys"]),
        "localities_verified": 20,
        "taxonomy_and_departments_verified": True,
        "reference_and_batch_collisions": 0,
        "existing_case_counts": preflight["counts"],
    }


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
        # Same mechanism staff use for a manual correction: stops _apply_tenant_safe_case_geography from
        # re-resolving the assembly from the (synthetic) complaint text on read.
        "geography_locked": True,
        "geography_source": "synthetic_manifest",
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


def _worksheet_portal_id(conn):
    from modules.govt_sync.delhi_portal import PORTAL_NAME
    return conn.execute(text("SELECT id FROM govt_portals WHERE portal_name = :n"), {"n": PORTAL_NAME}).scalar()


def rollback_preflight(conn, manifest: dict, allow_worksheet_artifacts: bool = False) -> tuple[list[int], dict]:
    """Validate that exactly the 20 batch rows exist and nothing real depends on them.

    Returns (case ids, removable worksheet-artifact row counts). By default ANY dependent row aborts.
    With allow_worksheet_artifacts, only the audit rows the Delhi staff-assisted worksheet endpoints write
    (see WORKSHEET_*) - plus the Delhi portal link and 'pending_staff_submit' they set - may be removed.
    Anything else (government reference, citizen forward, other tables, other actions) still aborts.
    """
    rows = conn.execute(text("""
        SELECT id, case_ref, govt_portal_id, govt_reference_number, govt_status,
               govt_last_forwarded_to_citizen_at, resolved_at
        FROM cases
        WHERE tenant_id = :tid AND case_metadata::jsonb->>'synthetic_batch_id' = :batch
        ORDER BY case_ref
    """), {"tid": manifest["tenant_id"], "batch": manifest["batch_id"]}).mappings().all()
    expected = [item["case_ref"] for item in manifest["cases"]]
    if [row["case_ref"] for row in rows] != expected:
        raise PreflightBlocked("rollback batch is partial, duplicated or has unexpected references")
    ids = [row["id"] for row in rows]
    delhi_portal_id = _worksheet_portal_id(conn) if allow_worksheet_artifacts else None
    allowed_statuses = WORKSHEET_STATUSES if allow_worksheet_artifacts else (None, "not_forwarded")
    for row in rows:
        portal_ok = row["govt_portal_id"] is None or (allow_worksheet_artifacts and row["govt_portal_id"] == delhi_portal_id)
        if (not portal_ok or row["govt_reference_number"] or row["govt_last_forwarded_to_citizen_at"]
                or row["resolved_at"] or row["govt_status"] not in allowed_statuses):
            raise PreflightBlocked("rollback aborted: a case acquired government or notification state")

    artifacts: dict[str, int] = {}
    unexpected: list[str] = []
    for table, column in _schema_preflight(conn):
        # Identifiers come from the PostgreSQL catalogue (not user input) and are quoted.
        total = conn.execute(text(f'SELECT COUNT(*) FROM "{table}" WHERE "{column}" = ANY(:ids)'), {"ids": ids}).scalar_one()  # nosec B608
        if not total:
            continue
        actions = {"govt_submission_log": WORKSHEET_LOG_ACTIONS, "case_activity_log": WORKSHEET_ACTIVITY_ACTIONS}.get(table)
        removable = 0
        if actions and column == "case_id":
            removable = conn.execute(text(f'SELECT COUNT(*) FROM "{table}" WHERE case_id = ANY(:ids) AND tenant_id = :tid AND action = ANY(:actions)'),  # nosec B608
                                     {"ids": ids, "tid": manifest["tenant_id"], "actions": sorted(actions)}).scalar_one()
        if removable != total or not allow_worksheet_artifacts:
            unexpected.append(f"{table}={total}")
        else:
            artifacts[table] = removable
    if unexpected:
        raise PreflightBlocked("rollback aborted: cases have dependent rows (" + ", ".join(unexpected) + ")"
                               + ("" if allow_worksheet_artifacts else "; worksheet-only artifacts need --allow-worksheet-artifacts"))
    return ids, artifacts


def _environment_guard(args, conn) -> str:
    env = os.getenv("ENV", "development").strip().lower()
    if conn.dialect.name != "postgresql":
        raise PreflightBlocked("a PostgreSQL database is required")
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
    parser.add_argument("--allow-worksheet-artifacts", action="store_true",
                        help="rollback only: also remove the Delhi worksheet audit rows/link written while testing the staff-assisted workflow")
    args = parser.parse_args(argv)
    manifest = load_manifest()
    environment = os.getenv("ENV", "development").strip().lower()
    try:
        if args.rollback:
            with engine.begin() as conn:
                _environment_guard(args, conn)
                _tenant_preflight(conn, manifest)
                ids, artifacts = rollback_preflight(conn, manifest, args.allow_worksheet_artifacts)
                for table in artifacts:
                    conn.execute(text(f'DELETE FROM "{table}" WHERE case_id = ANY(:ids) AND tenant_id = :tid'),  # nosec B608
                                 {"ids": ids, "tid": manifest["tenant_id"]})
                deleted = conn.execute(text("DELETE FROM cases WHERE tenant_id = :tid AND id = ANY(:ids)"), {"tid": manifest["tenant_id"], "ids": ids})
                if deleted.rowcount != len(ids):
                    raise PreflightBlocked("rollback deleted an unexpected number of rows; transaction aborted")
                print(json.dumps({"mode": "rollback", "environment": environment, "deleted_ids": ids, "removed_worksheet_artifacts": artifacts}, default=str))
        else:
            context = engine.begin() if args.execute else engine.connect()
            with context as conn:
                if not args.execute and conn.dialect.name == "postgresql":
                    # Hard guarantee that a dry run cannot write, whatever the code below does.
                    conn.execute(text("SET TRANSACTION READ ONLY"))
                _environment_guard(args, conn)
                preflight = run_preflight(conn, manifest)
                result = {"mode": "execute" if args.execute else "dry-run", "environment": environment,
                          "dialect": conn.dialect.name, "manifest_count": 20}
                if args.execute:
                    result["inserted_ids"] = execute(conn, manifest, preflight)
                else:
                    result.update(status="OK", would_insert=20, **redacted_report(preflight))
                print(json.dumps(result, default=str))
        return 0
    except PreflightBlocked as exc:
        print(json.dumps({"status": "BLOCKED", "environment": environment, "reason": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
