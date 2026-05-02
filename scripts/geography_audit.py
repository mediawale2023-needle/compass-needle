#!/usr/bin/env python3
import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.geography_resolver import (
    _build_match_forms,
    _is_meta_locality,
    normalize,
    sanitize_and_validate_stations,
)


BASE_PATH = Path(__file__).resolve().parent.parent / "data" / "geography"


def _csv_rows_for_summary(summary: dict) -> list[dict]:
    rows = []
    for locality, assemblies in sorted(summary["ambiguous_localities"].items()):
        rows.append(
            {
                "parliamentary_constituency": summary["parliamentary_constituency"],
                "locality": locality,
                "ambiguous_assemblies": " | ".join(assemblies),
                "assembly_count": len(assemblies),
                "status": "needs_review",
                "curated_assembly": "",
                "suggested_action": "Choose one assembly or leave unresolved pending clarification",
                "notes": "",
            }
        )
    return rows


def _slugify_filename(value: str) -> str:
    safe = []
    for char in value.lower().strip():
        if char.isalnum():
            safe.append(char)
        elif char in {" ", "-", "_"}:
            safe.append("_")
    collapsed = "".join(safe)
    while "__" in collapsed:
        collapsed = collapsed.replace("__", "_")
    return collapsed.strip("_") or "constituency"


def _load_constituency_rows(parliamentary_constituency: str) -> list[dict]:
    pc_path = BASE_PATH / parliamentary_constituency
    if not pc_path.exists():
        raise FileNotFoundError(f"Constituency not found: {parliamentary_constituency}")

    rows = []
    for json_file in sorted(pc_path.glob("*.json")):
        try:
            stations = json.loads(json_file.read_text(encoding="utf-8"))
        except Exception:
            stations = []
        rows.append(
            {
                "parliamentary_constituency": parliamentary_constituency,
                "assembly": json_file.stem,
                "stations": stations if isinstance(stations, list) else [],
            }
        )
    return rows


def _audit_constituency(parliamentary_constituency: str) -> dict:
    rows = _load_constituency_rows(parliamentary_constituency)
    summary = {
        "parliamentary_constituency": parliamentary_constituency,
        "assemblies": len(rows),
        "raw_rows": 0,
        "clean_rows": 0,
        "meta_rows_removed": 0,
        "missing_locality_en": 0,
        "assemblies_report": {},
        "ambiguous_localities": {},
        "alias_collisions": {},
    }

    form_to_assemblies: dict[str, set[str]] = defaultdict(set)
    locality_to_assemblies: dict[str, set[str]] = defaultdict(set)

    for row in rows:
        assembly = row["assembly"]
        stations = row["stations"]
        summary["raw_rows"] += len(stations)
        cleaned, report = sanitize_and_validate_stations(
            stations,
            parliamentary_constituency=parliamentary_constituency,
            assembly=assembly,
            other_rows=rows,
        )
        summary["clean_rows"] += len(cleaned)
        summary["meta_rows_removed"] += report["meta_rows_removed"]
        summary["missing_locality_en"] += report["missing_locality_en_count"]
        summary["assemblies_report"][assembly] = report

        for station in cleaned:
            locality = station["locality"]
            locality_to_assemblies[locality].add(assembly)
            for form in _build_match_forms(locality, station.get("locality_en", "")):
                form_to_assemblies[form].add(assembly)

    summary["ambiguous_localities"] = {
        locality: sorted(assemblies)
        for locality, assemblies in sorted(locality_to_assemblies.items())
        if len(assemblies) > 1 and not _is_meta_locality(locality)
    }
    summary["alias_collisions"] = {
        form: sorted(assemblies)
        for form, assemblies in sorted(form_to_assemblies.items())
        if len(assemblies) > 1 and form != normalize(form)
    }
    return summary


def _print_human(summary: dict) -> None:
    print(f"Constituency: {summary['parliamentary_constituency']}")
    print(f"Assemblies: {summary['assemblies']}")
    print(f"Rows: {summary['raw_rows']} raw -> {summary['clean_rows']} clean")
    print(f"Meta rows removed: {summary['meta_rows_removed']}")
    print(f"Missing locality_en: {summary['missing_locality_en']}")
    print(f"Ambiguous localities: {len(summary['ambiguous_localities'])}")
    print(f"Alias collisions: {len(summary['alias_collisions'])}")
    print()

    if summary["ambiguous_localities"]:
        print("Ambiguous localities:")
        for locality, assemblies in summary["ambiguous_localities"].items():
            print(f"  - {locality}: {', '.join(assemblies)}")
        print()

    for assembly, report in summary["assemblies_report"].items():
        print(f"[{assembly}]")
        print(
            f"  received={report['rows_received']} saved={report['rows_saved']} "
            f"meta_removed={report['meta_rows_removed']} missing_locality_en={report['missing_locality_en_count']}"
        )
        if report["meta_row_samples"]:
            print(f"  meta_samples={', '.join(report['meta_row_samples'])}")
        if report["ambiguous_localities_against_constituency"]:
            print("  ambiguous_against_constituency:")
            for locality, assemblies in report["ambiguous_localities_against_constituency"].items():
                print(f"    - {locality}: {', '.join(assemblies)}")
        print()


def _write_curation_csv(summaries: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "parliamentary_constituency",
                "locality",
                "ambiguous_assemblies",
                "assembly_count",
                "status",
                "curated_assembly",
                "suggested_action",
                "notes",
            ],
        )
        writer.writeheader()
        for summary in summaries:
            for row in _csv_rows_for_summary(summary):
                writer.writerow(row)


def _write_split_curation_csvs(summaries: list[dict], output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written_paths: list[Path] = []
    for summary in summaries:
        filename = f"{_slugify_filename(summary['parliamentary_constituency'])}_ambiguities.csv"
        output_path = output_dir / filename
        with output_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "parliamentary_constituency",
                    "locality",
                    "ambiguous_assemblies",
                    "assembly_count",
                    "status",
                    "curated_assembly",
                    "suggested_action",
                    "notes",
                ],
            )
            writer.writeheader()
            for row in _csv_rows_for_summary(summary):
                writer.writerow(row)
        written_paths.append(output_path)
    return written_paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit constituency geography data before activation.")
    parser.add_argument("--pc", dest="pc", help="Parliamentary constituency name (directory under data/geography).")
    parser.add_argument("--json", dest="as_json", action="store_true", help="Print JSON instead of human-readable text.")
    parser.add_argument(
        "--csv-out",
        dest="csv_out",
        help="Write ambiguous localities to a curation-ready CSV file.",
    )
    parser.add_argument(
        "--split-dir",
        dest="split_dir",
        help="Write one curation CSV per constituency into this directory.",
    )
    args = parser.parse_args()

    pcs = [args.pc] if args.pc else sorted(path.name for path in BASE_PATH.iterdir() if path.is_dir())
    summaries = [_audit_constituency(pc) for pc in pcs]

    if args.csv_out:
        _write_curation_csv(summaries, Path(args.csv_out))
    split_paths: list[Path] = []
    if args.split_dir:
        split_paths = _write_split_curation_csvs(summaries, Path(args.split_dir))

    if args.as_json:
        print(json.dumps(summaries if len(summaries) > 1 else summaries[0], ensure_ascii=False, indent=2))
    else:
        for idx, summary in enumerate(summaries):
            if idx:
                print("=" * 72)
            _print_human(summary)
        if args.csv_out:
            print(f"Curation CSV written to: {args.csv_out}")
        if split_paths:
            print(f"Split curation CSVs written to: {args.split_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
