#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path


VALID_STATUSES = {"needs_review", "resolved", "leave_unresolved"}


def _parse_assemblies(raw_value: str) -> list[str]:
    return [part.strip() for part in raw_value.split("|") if part.strip()]


def _validate_row(row: dict, row_num: int) -> list[str]:
    errors = []
    status = (row.get("status") or "").strip()
    curated = (row.get("curated_assembly") or "").strip()
    assemblies = _parse_assemblies(row.get("ambiguous_assemblies", ""))

    if status not in VALID_STATUSES:
        errors.append(f"row {row_num}: invalid status '{status}'")

    if status == "resolved":
        if not curated:
            errors.append(f"row {row_num}: resolved rows must set curated_assembly")
        elif curated not in assemblies:
            errors.append(
                f"row {row_num}: curated_assembly '{curated}' is not one of ambiguous_assemblies {assemblies}"
            )

    if status == "leave_unresolved" and curated:
        errors.append(f"row {row_num}: leave_unresolved rows must leave curated_assembly blank")

    if not row.get("parliamentary_constituency", "").strip():
        errors.append(f"row {row_num}: missing parliamentary_constituency")
    if not row.get("locality", "").strip():
        errors.append(f"row {row_num}: missing locality")
    if not assemblies:
        errors.append(f"row {row_num}: ambiguous_assemblies is empty")

    return errors


def _summarize_rows(rows: list[dict]) -> dict:
    summary = {
        "rows": len(rows),
        "needs_review": 0,
        "resolved": 0,
        "leave_unresolved": 0,
        "decisions": [],
    }
    for row in rows:
        status = row["status"].strip()
        summary[status] += 1
        if status in {"resolved", "leave_unresolved"}:
            summary["decisions"].append(
                {
                    "parliamentary_constituency": row["parliamentary_constituency"].strip(),
                    "locality": row["locality"].strip(),
                    "status": status,
                    "curated_assembly": row["curated_assembly"].strip(),
                }
            )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a completed geography curation CSV.")
    parser.add_argument("csv_file", help="Path to the curation CSV file")
    parser.add_argument("--json", dest="as_json", action="store_true", help="Print JSON summary")
    args = parser.parse_args()

    csv_path = Path(args.csv_file)
    if not csv_path.exists():
        raise SystemExit(f"File not found: {csv_path}")

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    errors = []
    for index, row in enumerate(rows, start=2):  # header is line 1
        errors.extend(_validate_row(row, index))

    summary = _summarize_rows(rows)
    result = {"valid": not errors, "summary": summary, "errors": errors}

    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"File: {csv_path}")
        print(f"Rows: {summary['rows']}")
        print(f"Resolved: {summary['resolved']}")
        print(f"Leave unresolved: {summary['leave_unresolved']}")
        print(f"Needs review: {summary['needs_review']}")
        if errors:
            print("Errors:")
            for error in errors:
                print(f"  - {error}")
        else:
            print("Validation: OK")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
