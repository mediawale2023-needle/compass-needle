#!/usr/bin/env python3
"""Phase 2 (contract) of the partner seat-limit removal: drop the retired `partners.seat_cap` column.

Phase 1 (the release that removed seat limits) stopped reading and writing the column but kept it so that
instances still running the previous release keep working during a rolling deploy. Run this ONLY after every
instance (Railway services, EC2 `backend` AND `backend_govt_live`, any worker) runs that release or newer.

    python scripts/partner_drop_seat_cap.py                 # dry run: reports what it would do
    python scripts/partner_drop_seat_cap.py --execute --confirm-no-old-instances

Uses DATABASE_URL from the environment of the process it runs in. Takes the startup migration advisory lock,
refuses if the phase-1 schema is incomplete, and is a no-op when the column is already gone (safe to re-run).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--execute", action="store_true", help="actually drop the column (default: dry run)")
    parser.add_argument("--confirm-no-old-instances", action="store_true",
                        help="required with --execute: you have verified no instance runs a release that uses seat_cap")
    args = parser.parse_args(argv)
    if args.execute and not args.confirm_no_old_instances:
        print("Refusing: --execute needs --confirm-no-old-instances (verify every instance runs the new release first).", file=sys.stderr)
        return 2

    from modules.partners import PartnerMigrationError, contract_seat_cap
    try:
        result = contract_seat_cap(execute=args.execute)
    except PartnerMigrationError as exc:
        print(f"Not dropped: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    if not args.execute and result.get("column_present"):
        print("Dry run only. Re-run with --execute --confirm-no-old-instances to drop partners.seat_cap.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
