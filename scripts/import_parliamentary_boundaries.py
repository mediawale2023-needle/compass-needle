#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.parliamentary_boundary_importer import (  # noqa: E402
    import_all_parliamentary_boundaries,
    load_parliamentary_geojson_from_upload,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Import parliamentary constituency boundaries into seat_boundary_assets.")
    parser.add_argument("--file", required=True, help="Path to maps-master.zip or a parliamentary GeoJSON file")
    parser.add_argument("--state", default="", help="Optional state filter, e.g. Karnataka")
    parser.add_argument("--status", default="verified", help="Boundary status to store (default: verified)")
    args = parser.parse_args()

    source_path = Path(args.file).expanduser()
    if not source_path.exists():
        raise SystemExit(f"File not found: {source_path}")

    payload = load_parliamentary_geojson_from_upload(source_path.read_bytes(), source_path.name)
    result = import_all_parliamentary_boundaries(
        payload,
        state=(args.state or "").strip(),
        status=(args.status or "verified").strip().lower(),
    )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
