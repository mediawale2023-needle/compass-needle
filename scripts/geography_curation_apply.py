#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import func

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.geography_resolver import _build_match_forms, _spaceless_forms, normalize
from sansadx_backend.db import SessionLocal, Tenant, TenantOverride
from scripts.geography_curation_import import validate_csv_file


def _lookup_tenant_id(db, parliamentary_constituency: str) -> int:
    rows = (
        db.query(Tenant.id)
        .filter(func.lower(Tenant.constituency) == parliamentary_constituency.strip().lower())
        .all()
    )
    tenant_ids = sorted({row[0] for row in rows if row and row[0] is not None})
    if not tenant_ids:
        raise ValueError(f"No tenant found for parliamentary constituency '{parliamentary_constituency}'")
    if len(tenant_ids) > 1:
        raise ValueError(
            f"Multiple tenants found for parliamentary constituency '{parliamentary_constituency}': {tenant_ids}"
        )
    return tenant_ids[0]


def _override_keys_for_locality(locality: str) -> list[str]:
    forms = _build_match_forms(locality)
    forms |= _spaceless_forms(forms)
    keys = {normalize(form) for form in forms if normalize(form)}
    return sorted(keys)


def apply_curation_rows(rows: list[dict], dry_run: bool = False) -> dict:
    db = SessionLocal()
    tenant_ids_by_pc: dict[str, int] = {}
    try:
        for row in rows:
            pc = (row.get("parliamentary_constituency") or "").strip()
            if pc and pc not in tenant_ids_by_pc:
                tenant_ids_by_pc[pc] = _lookup_tenant_id(db, pc)

        summary = {
            "rows": len(rows),
            "tenants": tenant_ids_by_pc,
            "resolved_applied": 0,
            "left_unresolved_cleared": 0,
            "needs_review_skipped": 0,
            "rows_changed": 0,
            "override_keys_written": 0,
            "override_keys_deleted": 0,
            "changes": [],
            "dry_run": dry_run,
        }

        for row in rows:
            status = (row.get("status") or "").strip()
            pc = (row.get("parliamentary_constituency") or "").strip()
            locality = (row.get("locality") or "").strip()

            if status == "needs_review":
                summary["needs_review_skipped"] += 1
                continue

            tenant_id = tenant_ids_by_pc[pc]
            keys = _override_keys_for_locality(locality)
            delete_count = (
                db.query(TenantOverride)
                .filter(
                    TenantOverride.tenant_id == tenant_id,
                    TenantOverride.override_type == "geo_override",
                    TenantOverride.key.in_(keys),
                )
                .delete(synchronize_session=False)
            )
            summary["override_keys_deleted"] += delete_count

            change = {
                "tenant_id": tenant_id,
                "parliamentary_constituency": pc,
                "locality": locality,
                "status": status,
                "keys": keys,
                "deleted_existing_rows": delete_count,
            }

            if status == "resolved":
                curated_assembly = (row.get("curated_assembly") or "").strip()
                for key in keys:
                    db.add(
                        TenantOverride(
                            tenant_id=tenant_id,
                            override_type="geo_override",
                            key=key,
                            value=curated_assembly,
                        )
                    )
                summary["resolved_applied"] += 1
                summary["override_keys_written"] += len(keys)
                change["curated_assembly"] = curated_assembly
                change["written_rows"] = len(keys)
            else:
                summary["left_unresolved_cleared"] += 1
                change["written_rows"] = 0

            summary["rows_changed"] += 1
            summary["changes"].append(change)

        if dry_run:
            db.rollback()
        else:
            db.commit()
        return summary
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def apply_curation_csv(csv_path: Path, dry_run: bool = False) -> dict:
    result = validate_csv_file(csv_path)
    if not result["valid"]:
        raise ValueError("CSV validation failed:\n" + "\n".join(result["errors"]))
    apply_summary = apply_curation_rows(result["rows"], dry_run=dry_run)
    return {
        "csv_file": str(csv_path),
        "validation": {
            "valid": result["valid"],
            "summary": result["summary"],
        },
        "apply": apply_summary,
    }


def _print_human(result: dict) -> None:
    validation = result["validation"]["summary"]
    apply_summary = result["apply"]
    print(f"File: {result['csv_file']}")
    print(f"Rows: {validation['rows']}")
    print(f"Resolved decisions: {validation['resolved']}")
    print(f"Leave unresolved decisions: {validation['leave_unresolved']}")
    print(f"Needs review skipped: {apply_summary['needs_review_skipped']}")
    print(f"Tenants: {apply_summary['tenants']}")
    print(f"Resolved applied: {apply_summary['resolved_applied']}")
    print(f"Leave unresolved cleared: {apply_summary['left_unresolved_cleared']}")
    print(f"Override keys written: {apply_summary['override_keys_written']}")
    print(f"Override keys deleted: {apply_summary['override_keys_deleted']}")
    print(f"Mode: {'DRY RUN' if apply_summary['dry_run'] else 'APPLIED'}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply validated geography curation CSV decisions to DB overrides.")
    parser.add_argument("csv_file", help="Path to the validated curation CSV file")
    parser.add_argument("--dry-run", action="store_true", help="Validate and preview DB changes without committing")
    parser.add_argument("--json", dest="as_json", action="store_true", help="Print JSON summary")
    args = parser.parse_args()

    csv_path = Path(args.csv_file)
    if not csv_path.exists():
        raise SystemExit(f"File not found: {csv_path}")

    result = apply_curation_csv(csv_path, dry_run=args.dry_run)
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_human(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
