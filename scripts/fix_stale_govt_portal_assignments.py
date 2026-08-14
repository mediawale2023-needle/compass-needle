#!/usr/bin/env python3
"""
One-off maintenance: cases prepared for a govt portal before their tenant's
state had proper coverage (e.g. before the govt_portals state-coverage
rollout added most states) got stuck pointing at whatever portal the
resolver fell back to at the time — usually CPGRAMS. Once the tenant's real
state portal exists, _resolve_govt_portal_for_tenant() would pick it
correctly for a *new* translate call, but nothing ever re-checks an
*existing* assignment.

This only touches cases still in 'pending_staff_submit' — nothing has
actually been filed with the government yet for those, so re-resolving and
re-translating is safe. Cases already 'submitted' or beyond are left alone;
a real-world filing already happened against whatever portal was assigned
at the time, and silently reassigning that after the fact would make the
audit trail (govt_submission_log) lie about what was actually submitted
where.

Usage (run inside the backend container, same DB the app uses):
    python -m scripts.fix_stale_govt_portal_assignments             # dry run, prints what would change
    python -m scripts.fix_stale_govt_portal_assignments --apply     # actually re-translate mismatched cases
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger("needle.scripts.fix_stale_govt_portal")


def main(apply: bool) -> None:
    from core.db_helpers import _q
    from api_router import _resolve_govt_portal_for_tenant, _prepare_govt_worksheet

    cases = _q(
        "SELECT id, tenant_id, category, raw_message, location, assembly, ward, govt_portal_id, govt_department "
        "FROM cases WHERE govt_status = 'pending_staff_submit' AND govt_portal_id IS NOT NULL "
        "AND (is_deleted = false OR is_deleted IS NULL)"
    )
    logger.info(f"{len(cases)} case(s) currently pending_staff_submit with a portal already assigned")

    mismatched = 0
    fixed = 0
    for case in cases:
        try:
            portal, state = _resolve_govt_portal_for_tenant(case["tenant_id"])
        except Exception as e:
            logger.warning(f"case={case['id']} tenant={case['tenant_id']}: portal resolution raised: {e}")
            continue

        if not portal:
            logger.warning(f"case={case['id']} tenant={case['tenant_id']}: no portal resolves for state='{state}' — skipping")
            continue
        if portal["id"] == case["govt_portal_id"]:
            continue  # already correct, nothing to do

        mismatched += 1
        logger.info(
            f"case={case['id']} tenant={case['tenant_id']} state='{state}': "
            f"assigned portal_id={case['govt_portal_id']} (dept='{case.get('govt_department')}') "
            f"-> should be portal_id={portal['id']} ('{portal['portal_name']}')"
        )
        if not apply:
            continue
        try:
            _prepare_govt_worksheet(case["tenant_id"], case, portal, actor_username="system:fix_stale_govt_portal_assignments")
            fixed += 1
        except Exception as e:
            logger.error(f"case={case['id']}: re-translate failed, left as-is: {e}")

    if apply:
        logger.info(f"Done — fixed {fixed}/{mismatched} mismatched case(s).")
    else:
        logger.info(f"Dry run complete — {mismatched} case(s) would be re-translated. Rerun with --apply to actually fix them.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Actually re-translate mismatched cases (default: dry run, prints only)")
    args = parser.parse_args()
    main(apply=args.apply)
