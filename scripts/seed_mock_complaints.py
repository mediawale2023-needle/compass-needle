#!/usr/bin/env python3
"""
Seed an existing tenant's Briefcase with realistic mock citizen complaints,
scattered across their real constituency geography where available.

Does NOT touch tenant/profile/user identity — the tenant must already exist
(this is for populating a live demo dashboard, not bootstrapping a new one;
see scripts/seed_contact_thread_demo.py for that). Dry-run by default,
prints what it would insert; --apply actually writes.

Idempotent: every inserted row carries case_metadata.mock_seed=true and a
case_ref prefixed "MOCK-<tenant_id>-". Re-running with --apply deletes prior
mock rows for that tenant first (unless --preserve-existing), so re-seeding
doesn't pile up duplicates.

Usage:
    python -m scripts.seed_mock_complaints --tenant-id 11                  # dry run
    python -m scripts.seed_mock_complaints --tenant-id 11 --count 100 --apply
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger("needle.scripts.seed_mock_complaints")

# {location} is filled from real geography (if found) or the generic fallback
# list below. Each entry: (category, subdomain, message templates).
_TEMPLATES = [
    ("Infrastructure & Utilities", "Water Supply", [
        "No water supply in {location} for the last {days} days.",
        "Water tanker has not come to {location} this week.",
        "Low water pressure in {location}, taps are almost dry.",
        "Contaminated/dirty water coming from the pipeline in {location}.",
        "Pipeline burst near {location}, water is being wasted on the road.",
    ]),
    ("Infrastructure & Utilities", "Roads & Bridges", [
        "Deep potholes on the main road near {location}, causing accidents.",
        "Road near {location} has not been repaired since last monsoon.",
        "No streetlights on the road connecting {location}, unsafe at night.",
        "Broken culvert near {location} is flooding the approach road.",
        "Road widening work near {location} has been stalled for months.",
    ]),
    ("Infrastructure & Utilities", "Power & Street Lighting", [
        "Frequent power cuts in {location}, sometimes lasting 6-8 hours.",
        "Streetlights not working in {location} for over a week.",
        "Transformer near {location} keeps tripping every evening.",
        "New electricity connection application pending for 2 months in {location}.",
    ]),
    ("Infrastructure & Utilities", "Drainage/Sewage", [
        "Open drain overflowing near {location}, foul smell in the area.",
        "Sewage water entering homes in {location} after every rain.",
        "Blocked drainage line in {location} causing waterlogging.",
    ]),
    ("Infrastructure & Utilities", "Solid Waste", [
        "Garbage has not been collected in {location} for 4-5 days.",
        "No dustbins provided in {location}, people are dumping on the roadside.",
        "Garbage truck skipped {location} again this week.",
    ]),
    ("Health", "Primary Health Centre", [
        "No doctor available at the PHC near {location} for the last few visits.",
        "Medicines out of stock at the health centre in {location}.",
        "Ambulance took over an hour to reach {location} during an emergency.",
        "PHC in {location} is short-staffed, long queues every morning.",
    ]),
    ("Education", "School Infrastructure", [
        "Government school in {location} has no proper toilets for girls.",
        "No teachers assigned to the school in {location} for the new session.",
        "School building in {location} needs urgent repair, roof is leaking.",
        "Mid-day meal quality has dropped at the school in {location}.",
    ]),
    ("Agriculture", "Irrigation", [
        "Canal water not reaching farms near {location} this season.",
        "Crop insurance claim pending for over 3 months for farmers in {location}.",
        "Irrigation pump station near {location} has been non-functional for weeks.",
        "Fertilizer shortage at the cooperative society near {location}.",
    ]),
    ("Housing & Land", "Land Records", [
        "Land mutation application pending for months for a plot in {location}.",
        "Property tax records incorrect for a house in {location}.",
        "Encroachment on the common land/park in {location} not being addressed.",
    ]),
    ("Government Schemes & Welfare", "Pension & Ration", [
        "Old-age pension has not been credited for 2 months for a resident of {location}.",
        "Ration card application stuck for months for a family in {location}.",
        "Widow pension scheme application pending for a resident of {location}.",
        "PM Awas Yojana house not yet allotted despite approval, family in {location}.",
    ]),
    ("Law & Order", "Local Policing", [
        "Repeated chain-snatching incidents reported near {location}.",
        "No police patrolling at night near {location}, residents feel unsafe.",
        "Illegal liquor sale near {location}, repeated complaints ignored.",
    ]),
    ("Bureaucratic / Administrative", "Certificates", [
        "Caste certificate application pending for over 2 months, applicant from {location}.",
        "Income certificate not issued despite multiple visits to the office, {location}.",
        "Birth certificate correction request pending for weeks, family in {location}.",
    ]),
    ("Social Issues", "Women & Child Safety", [
        "No streetlights near the girls' college in {location}, safety concern raised by parents.",
        "Anganwadi centre in {location} lacks basic supplies for children.",
        "Domestic violence helpline response was delayed for a case in {location}.",
    ]),
]

_GENERIC_LOCATIONS = [
    "Ward 1", "Ward 2", "Ward 3", "Gandhi Nagar", "Station Road", "Old Bus Stand",
    "New Colony", "Main Bazaar", "College Road", "Temple Street", "Industrial Area",
    "Housing Board Colony", "Panchayat Bhavan Road", "Model Town", "Ambedkar Nagar",
]

_STATUS_WEIGHTS = [("new", 0.40), ("in_progress", 0.35), ("resolved", 0.25)]

_FIRST_NAMES = [
    "Ramesh", "Suresh", "Anita", "Priya", "Vijay", "Sunita", "Rajesh", "Kavita",
    "Amit", "Pooja", "Deepak", "Meena", "Sanjay", "Geeta", "Ashok", "Rekha",
]


def _utcnow() -> datetime:
    return datetime.utcnow()


def _weighted_status() -> str:
    r = random.random()
    cumulative = 0.0
    for status, weight in _STATUS_WEIGHTS:
        cumulative += weight
        if r <= cumulative:
            return status
    return _STATUS_WEIGHTS[-1][0]


def _fetch_tenant(conn, tenant_id: int) -> dict | None:
    from sqlalchemy import text
    row = conn.execute(
        text(
            """
            SELECT t.id, t.constituency, t.seat_type, tp.state, tp.constituency AS profile_constituency
            FROM tenants t
            LEFT JOIN tenant_profiles tp ON tp.tenant_id = t.id
            WHERE t.id = :tid
            """
        ),
        {"tid": tenant_id},
    ).mappings().first()
    return dict(row) if row else None


def _fetch_real_locations(conn, tenant_id: int, seat_type: str, constituency: str) -> list[str]:
    """Best-effort: pull real locality names from this tenant's shared seat
    geography (tenant_overrides, override_type='geography_data'), same source
    scripts/seed_contact_thread_demo.py's resolver reads. Falls back to the
    generic list if none found — never blocks seeding on missing geography."""
    from sqlalchemy import text
    if not constituency:
        return []
    prefix = f"{seat_type}:{constituency}/"
    rows = conn.execute(
        text(
            """
            SELECT value
            FROM tenant_overrides
            WHERE override_type = 'geography_data'
              AND (tenant_id = :tid OR tenant_id IS NULL)
              AND key LIKE :prefix
            LIMIT 5
            """
        ),
        {"tid": tenant_id, "prefix": f"{prefix}%"},
    ).fetchall()
    locations: list[str] = []
    for (value,) in rows:
        try:
            payload = json.loads(value) if isinstance(value, str) else value
        except (TypeError, ValueError):
            continue
        entries = payload if isinstance(payload, list) else [payload]
        for entry in entries:
            if isinstance(entry, dict):
                loc = entry.get("locality") or entry.get("building_name")
                if loc and loc not in locations:
                    locations.append(str(loc))
    return locations[:40]


def _build_mock_case(tenant_id: int, assembly: str, locations: list[str], created_at: datetime, seq: int) -> dict:
    category, subdomain, templates = random.choice(_TEMPLATES)
    location = random.choice(locations)
    message = random.choice(templates).format(location=location, days=random.choice([2, 3, 4, 5, 7]))
    status = _weighted_status()
    phone = f"91900{tenant_id:03d}{seq:04d}"
    name = random.choice(_FIRST_NAMES)
    resolved_note = ""
    response_to_citizen = ""
    if status == "resolved":
        resolved_note = "Resolved: issue addressed by the concerned department. (Mock data)"
        response_to_citizen = "Your complaint has been resolved. Thank you for reporting it."
    elif status == "in_progress":
        resolved_note = "Forwarded to the concerned department for action. (Mock data)"

    return {
        "tenant_id": tenant_id,
        "user_phone": phone,
        "raw_message": message,
        "category": category,
        "problem_domain": category,
        "problem_subdomain": subdomain,
        "status": status,
        "location": location,
        "ward": location,
        "assembly": assembly,
        "is_critical": random.random() < 0.08,
        "response_to_citizen": response_to_citizen,
        "notes_for_staff": resolved_note,
        "case_metadata": json.dumps({
            "mock_seed": True,
            "summary": f"{subdomain} issue in {location}",
            "matched_value": location,
            "assembly_constituency": assembly,
            "detected_language": "English",
            "language": "English",
            "problem_domain": category,
            "problem_subdomain": subdomain,
            "citizen_name_guess": name,
        }),
        "created_at": created_at,
        "updated_at": created_at + timedelta(hours=random.randint(1, 72)) if status != "new" else created_at,
        "case_ref": f"MOCK-{tenant_id}-{seq:04d}",
    }


def _delete_prior_mock_cases(conn, tenant_id: int) -> int:
    from sqlalchemy import text
    result = conn.execute(
        text(
            """
            DELETE FROM cases
            WHERE tenant_id = :tid
              AND COALESCE(case_metadata::json->>'mock_seed', 'false') = 'true'
            """
        ),
        {"tid": tenant_id},
    )
    return result.rowcount or 0


def _insert_case(conn, case: dict) -> None:
    from sqlalchemy import text
    conn.execute(
        text(
            """
            INSERT INTO cases (
                tenant_id, user_phone, raw_message, category, status, location, ward,
                assembly, problem_domain, problem_subdomain,
                is_critical, response_to_citizen, notes_for_staff, case_metadata,
                created_at, updated_at, case_ref, is_deleted
            ) VALUES (
                :tenant_id, :user_phone, :raw_message, :category, :status, :location, :ward,
                :assembly, :problem_domain, :problem_subdomain,
                :is_critical, :response_to_citizen, :notes_for_staff, CAST(:case_metadata AS json),
                :created_at, :updated_at, :case_ref, false
            )
            """
        ),
        case,
    )


def main(tenant_id: int, count: int, apply: bool, preserve_existing: bool, seed: int | None) -> None:
    if seed is not None:
        random.seed(seed)

    from sansadx_backend.db import engine

    with engine.connect() as conn:
        tenant = _fetch_tenant(conn, tenant_id)
        if not tenant:
            logger.error(f"Tenant {tenant_id} not found — refusing to seed. Create the tenant first.")
            return
        assembly = tenant.get("profile_constituency") or tenant.get("constituency") or ""
        if not assembly:
            logger.error(f"Tenant {tenant_id} has no constituency on file — refusing to guess one.")
            return
        seat_type = tenant.get("seat_type") or "mp"
        state = tenant.get("state") or "(unknown)"

        real_locations = _fetch_real_locations(conn, tenant_id, seat_type, assembly)
        locations = real_locations if real_locations else _GENERIC_LOCATIONS
        source = "real shared geography" if real_locations else "generic fallback names"
        logger.info(f"Tenant {tenant_id}: constituency='{assembly}' state='{state}' seat_type='{seat_type}'. "
                    f"Using {len(locations)} locations from {source}.")

        now = _utcnow()
        cases = []
        for i in range(count):
            # Spread over the last 75 days so the dashboard shows an organic
            # backlog, not 100 cases all created in the same second.
            created_at = now - timedelta(days=random.uniform(0, 75), hours=random.uniform(0, 23))
            cases.append(_build_mock_case(tenant_id, assembly, locations, created_at, i + 1))

        status_counts: dict[str, int] = {}
        for c in cases:
            status_counts[c["status"]] = status_counts.get(c["status"], 0) + 1
        logger.info(f"Would insert {len(cases)} mock cases. Status mix: {status_counts}")

        if not apply:
            logger.info("Dry run — no changes made. Re-run with --apply to actually insert.")
            for c in cases[:5]:
                logger.info(f"  sample: [{c['category']} / {c['problem_subdomain']}] {c['raw_message']}")
            return

        with engine.begin() as write_conn:
            deleted = 0
            if not preserve_existing:
                deleted = _delete_prior_mock_cases(write_conn, tenant_id)
            for c in cases:
                _insert_case(write_conn, c)

        logger.info(f"Inserted {len(cases)} mock cases for tenant {tenant_id} ({assembly}). "
                    f"Deleted {deleted} prior mock rows first.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-id", type=int, required=True)
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--apply", action="store_true", help="Actually insert (default: dry run, prints only)")
    parser.add_argument("--preserve-existing", action="store_true", help="Don't delete prior mock_seed rows first")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducible output")
    args = parser.parse_args()
    main(args.tenant_id, args.count, args.apply, args.preserve_existing, args.seed)
