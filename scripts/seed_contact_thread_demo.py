#!/usr/bin/env python3
"""
Seed a demo tenant with curated Briefcase cases that showcase contact-thread states.

This script is idempotent for the demo rows it manages:
- upserts the target tenant, owner user, and tenant profile
- deletes only prior cases marked with `thread_demo_seed=true` for that tenant
- inserts three demo cases:
  1. valid_multi_issue
  2. high_frequency
  3. spam_suspected

Usage example:
    python scripts/seed_contact_thread_demo.py \
      --tenant-id 10 \
      --username Jadhav \
      --password 'Jadhav@123'
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta

from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sansadx_backend.db import (
    SessionLocal,
    Tenant,
    TenantProfile,
    User,
    hash_password,
)


def _utcnow() -> datetime:
    return datetime.utcnow()


def _thread_case(
    *,
    tenant_id: int,
    case_ref: str,
    phone: str,
    thread_id: str,
    thread_demo_case: str,
    raw_message: str,
    category: str,
    subdomain: str,
    location: str,
    assembly: str,
    created_at: datetime,
    updated_at: datetime | None = None,
    status: str = "new",
    notes_for_staff: str = "",
    response_to_citizen: str = "",
    is_critical: bool = False,
    distinct_issue_count: int = 1,
    contact_thread_state: str = "normal",
    thread_started_at: datetime | None = None,
    thread_last_activity_at: datetime | None = None,
    events: list[dict] | None = None,
    spam_messages: list[dict] | None = None,
    spam_flagged: bool = False,
) -> dict:
    updated_at = updated_at or created_at
    thread_started_at = thread_started_at or created_at
    thread_last_activity_at = thread_last_activity_at or updated_at
    problem_domain = category
    return {
        "tenant_id": tenant_id,
        "user_phone": phone,
        "raw_message": raw_message,
        "category": category,
        "problem_domain": problem_domain,
        "problem_subdomain": subdomain,
        "convergence_program_type": "Service Delivery Strengthening",
        "status": status,
        "location": location,
        "ward": location,
        "assembly": assembly,
        "is_critical": is_critical,
        "response_to_citizen": response_to_citizen,
        "notes_for_staff": notes_for_staff,
        "case_metadata": {
            "thread_demo_seed": True,
            "thread_demo_case": thread_demo_case,
            "summary": f"{subdomain} issue in {location}",
            "matched_value": location,
            "assembly_constituency": assembly,
            "detected_language": "English",
            "language": "English",
            "problem_domain": problem_domain,
            "problem_subdomain": subdomain,
            "convergence_program_type": "Service Delivery Strengthening",
            "contact_thread_id": thread_id,
            "contact_thread_started_at": thread_started_at.isoformat(),
            "contact_thread_last_activity_at": thread_last_activity_at.isoformat(),
            "contact_thread_state": contact_thread_state,
            "distinct_issue_count": distinct_issue_count,
            "contact_message_events": events or [],
            "contact_intake_action": "spam_suspected" if spam_flagged else "thread_distinct_issue",
            "contact_thread_spam_flagged": spam_flagged,
            "contact_thread_spam_messages": spam_messages or [],
        },
        "created_at": created_at,
        "updated_at": updated_at,
        "case_ref": case_ref,
    }


def _ensure_tenant(db: Session, args) -> Tenant:
    tenant = db.query(Tenant).filter(Tenant.id == args.tenant_id).first()
    tenant_exists = tenant is not None
    if not tenant:
        tenant = Tenant(id=args.tenant_id)
        db.add(tenant)

    if not tenant_exists or args.allow_identity_overwrite:
        tenant.name = args.tenant_name
        tenant.constituency = args.constituency
        tenant.whatsapp_number = args.whatsapp_number
        tenant.subscription_plan = "Demo"
        tenant.tenant_type = args.tenant_type
        tenant.account_stage = args.account_stage
        tenant.seat_type = args.seat_type
        tenant.is_active = True
    else:
        tenant.name = tenant.name or args.tenant_name
        tenant.whatsapp_number = tenant.whatsapp_number or args.whatsapp_number
        tenant.subscription_plan = tenant.subscription_plan or "Demo"
        if tenant.is_active is None:
            tenant.is_active = True
    tenant.config = {**(tenant.config or {}), "thread_demo_seeded": True}
    if not tenant.created_at:
        tenant.created_at = _utcnow()
    return tenant


def _ensure_profile(db: Session, tenant: Tenant, args) -> TenantProfile:
    profile = db.query(TenantProfile).filter(TenantProfile.tenant_id == tenant.id).first()
    profile_exists = profile is not None
    if not profile:
        profile = TenantProfile(tenant_id=tenant.id)
        db.add(profile)

    if not profile_exists or args.allow_identity_overwrite:
        profile.mp_name = args.display_name
        profile.constituency = args.constituency
        profile.state = args.state
        profile.house = args.house
        profile.party = args.party
    else:
        profile.mp_name = profile.mp_name or args.display_name
        profile.constituency = profile.constituency or tenant.constituency or args.constituency
        profile.state = profile.state or args.state
        profile.house = profile.house or args.house
        profile.party = profile.party or args.party
    profile.profile_data = {**(profile.profile_data or {}), "thread_demo_seeded": True}
    if not profile.created_at:
        profile.created_at = _utcnow()
    return profile


def _ensure_user(db: Session, tenant: Tenant, args) -> User:
    user = db.query(User).filter(User.username == args.username).first()
    user_exists = user is not None
    if not user:
        user = User(username=args.username)
        db.add(user)

    user.tenant_id = tenant.id
    user.password_hash = hash_password(args.password)
    user.role = args.role
    user.display_name = args.display_name
    user.phone = args.user_phone
    user.is_active = True
    user.must_change_password = False
    user.failed_login_attempts = 0
    user.locked_until = None
    user.force_password_reason = None
    if not user_exists or args.allow_identity_overwrite:
        user.constituency = args.constituency
        user.house = args.house
    else:
        user.constituency = user.constituency or tenant.constituency or args.constituency
        user.house = user.house or args.house
    return user


def _delete_prior_demo_cases(db: Session, tenant_id: int) -> int:
    result = db.execute(
        sa_text(
            """
            DELETE FROM cases
            WHERE tenant_id = :tenant_id
              AND COALESCE(case_metadata::json->>'thread_demo_seed', 'false') = 'true'
            """
        ),
        {"tenant_id": tenant_id},
    )
    return result.rowcount or 0


_ASSEMBLY_LOCATION_PRESETS = {
    "belgaum south": [
        "Shahapur",
        "Khasbag",
        "Rani Channamma Nagar",
        "Hindwadi",
        "Tilakwadi",
        "Vadgaon",
        "Nath Pai Circle",
        "Teachers Colony",
        "Somawar Peth",
        "Mahadwar Road",
    ],
    "belgaum dakshin": [
        "Shahapur",
        "Khasbag",
        "Rani Channamma Nagar",
        "Hindwadi",
        "Tilakwadi",
        "Vadgaon",
        "Nath Pai Circle",
        "Teachers Colony",
        "Somawar Peth",
        "Mahadwar Road",
    ],
}


def _normalize(value: str | None) -> str:
    return " ".join("".join(ch.lower() if ch.isalnum() else " " for ch in str(value or "")).split())


def _get_geo_assemblies_for_tenant(db: Session, tenant: Tenant) -> list[str]:
    seat_type = str(tenant.seat_type or "").strip() or "mp"
    seat_name = str(tenant.constituency or "").strip()
    if not seat_name:
        return []
    prefix = f"{seat_type}:{seat_name}/"
    rows = db.execute(
        sa_text(
            """
            SELECT key
            FROM tenant_overrides
            WHERE override_type = 'geography_data'
              AND (tenant_id = :tenant_id OR tenant_id IS NULL)
              AND key LIKE :prefix
            ORDER BY tenant_id NULLS LAST, key
            """
        ),
        {"tenant_id": tenant.id, "prefix": f"{prefix}%"},
    ).fetchall()
    assemblies: list[str] = []
    for (key,) in rows:
        text_key = str(key or "")
        assembly = text_key.split("/", 1)[-1].strip()
        if assembly and assembly not in assemblies:
            assemblies.append(assembly)
    return assemblies


def _resolve_demo_assembly(db: Session, tenant: Tenant, args) -> str:
    if args.demo_assembly:
        return args.demo_assembly

    assemblies = _get_geo_assemblies_for_tenant(db, tenant)
    if len(assemblies) == 1:
        return assemblies[0]

    if str(tenant.seat_type or "").strip().lower() == "mla":
        raise ValueError(
            f"Tenant {tenant.id} has ambiguous MLA geography assemblies {assemblies or '[]'}. "
            "Pass --demo-assembly explicitly to keep the seed seat-safe."
        )

    if assemblies:
        return assemblies[0]

    if tenant.constituency:
        return str(tenant.constituency)
    raise ValueError(f"Tenant {tenant.id} has no constituency/assembly context for demo seeding.")


def _locations_for_assembly(assembly: str) -> list[str]:
    normalized = _normalize(assembly)
    preset = _ASSEMBLY_LOCATION_PRESETS.get(normalized)
    if preset:
        return list(preset)
    return [
        "Central Ward",
        "Market Road",
        "Station Area",
        "Main Bazaar",
        "Old Town",
        "New Layout",
        "Bus Stand",
        "College Circle",
        "Temple Road",
        "North Extension",
    ]


def _build_demo_cases(tenant_id: int, *, demo_assembly: str) -> list[dict]:
    now = _utcnow()
    category = "Infrastructure & Utilities"
    cases: list[dict] = []
    locations = _locations_for_assembly(demo_assembly)

    valid_thread_started = now - timedelta(hours=3, minutes=10)
    valid_thread_last = valid_thread_started + timedelta(hours=2, minutes=30)
    valid_thread_id = f"ct-demo-{tenant_id}-919811110001"
    valid_specs = [
        (
            "NDL-T10-001A",
            f"Streetlights are not working in {locations[0]} after 9 pm.",
            "Power & Street Lighting",
            locations[0],
            valid_thread_started,
            valid_thread_started + timedelta(minutes=35),
            [{"message": "Lights are still off after 10 pm too.", "event_type": "duplicate_followup", "created_at": (valid_thread_started + timedelta(minutes=28)).isoformat()}],
        ),
        (
            "NDL-T10-001B",
            f"Road near {locations[1]} has deep potholes since last week.",
            "Roads & Bridges",
            locations[1],
            valid_thread_started + timedelta(minutes=50),
            valid_thread_started + timedelta(hours=1, minutes=5),
            [{"message": "Please repair before school traffic starts.", "event_type": "duplicate_followup", "created_at": (valid_thread_started + timedelta(minutes=58)).isoformat()}],
        ),
        (
            "NDL-T10-001",
            f"Garbage has not been picked up in {locations[2]} for 4 days.",
            "Solid Waste",
            locations[2],
            valid_thread_started + timedelta(hours=2, minutes=5),
            valid_thread_last,
            [],
        ),
    ]
    for case_ref, raw_message, subdomain, location, created_at, updated_at, events in valid_specs:
        cases.append(
            _thread_case(
                tenant_id=tenant_id,
                case_ref=case_ref,
                phone="919811110001",
                thread_id=valid_thread_id,
                thread_demo_case="valid_multi_issue",
                raw_message=raw_message,
                category=category,
                subdomain=subdomain,
                location=location,
                assembly=demo_assembly,
                created_at=created_at,
                updated_at=updated_at,
                notes_for_staff="Demo: valid multi-issue thread with independent sibling complaints.",
                distinct_issue_count=3,
                contact_thread_state="valid_multi_issue",
                thread_started_at=valid_thread_started,
                thread_last_activity_at=valid_thread_last,
                events=events,
            )
        )

    high_thread_started = now - timedelta(hours=9)
    high_thread_last = high_thread_started + timedelta(hours=4)
    high_thread_id = f"ct-demo-{tenant_id}-919811110002"
    high_specs = [
        ("NDL-T10-002A", f"Water tanker has not come to {locations[3]} today either.", "Water Supply", locations[3]),
        ("NDL-T10-002B", f"Issue number 1 reported from {locations[4]}.", "Water Supply", locations[4]),
        ("NDL-T10-002C", f"Issue number 2 reported from {locations[5]}.", "Drainage/Sewage", locations[5]),
        ("NDL-T10-002D", f"Issue number 3 reported from {locations[6]}.", "Water Supply", locations[6]),
        ("NDL-T10-002E", f"Issue number 4 reported from {locations[7]}.", "Drainage/Sewage", locations[7]),
        ("NDL-T10-002", f"Issue number 5 reported from {locations[8]}.", "Water Supply", locations[8]),
    ]
    for idx, (case_ref, raw_message, subdomain, location) in enumerate(high_specs):
        created_at = high_thread_started + timedelta(minutes=idx * 35)
        updated_at = created_at + timedelta(minutes=12 if idx < len(high_specs) - 1 else 20)
        events = []
        if idx == len(high_specs) - 1:
            events = [{
                "message": "Please note this is the sixth distinct issue today.",
                "event_type": "duplicate_followup",
                "created_at": (high_thread_last - timedelta(minutes=10)).isoformat(),
            }]
        cases.append(
            _thread_case(
                tenant_id=tenant_id,
                case_ref=case_ref,
                phone="919811110002",
                thread_id=high_thread_id,
                thread_demo_case="high_frequency",
                raw_message=raw_message,
                category=category,
                subdomain=subdomain,
                location=location,
                assembly=demo_assembly,
                created_at=created_at,
                updated_at=updated_at,
                notes_for_staff="Demo: high-frequency thread with six distinct sibling complaints.",
                distinct_issue_count=6,
                contact_thread_state="high_frequency",
                thread_started_at=high_thread_started,
                thread_last_activity_at=high_thread_last,
                events=events,
            )
        )

    spam_thread_started = now - timedelta(hours=20)
    spam_thread_last = spam_thread_started + timedelta(hours=6)
    spam_thread_id = f"ct-demo-{tenant_id}-919811110003"
    spam_specs = [
        ("NDL-T10-003A", f"Distinct civic complaint 1 from {locations[0]}.", "Solid Waste", locations[0]),
        ("NDL-T10-003B", f"Distinct civic complaint 2 from {locations[1]}.", "Roads & Bridges", locations[1]),
        ("NDL-T10-003C", f"Distinct civic complaint 3 from {locations[2]}.", "Solid Waste", locations[2]),
        ("NDL-T10-003D", f"Distinct civic complaint 4 from {locations[3]}.", "Roads & Bridges", locations[3]),
        ("NDL-T10-003E", f"Distinct civic complaint 5 from {locations[4]}.", "Solid Waste", locations[4]),
        ("NDL-T10-003F", f"Distinct civic complaint 6 from {locations[5]}.", "Roads & Bridges", locations[5]),
        ("NDL-T10-003G", f"Distinct civic complaint 7 from {locations[6]}.", "Solid Waste", locations[6]),
        ("NDL-T10-003H", f"Distinct civic complaint 8 from {locations[7]}.", "Roads & Bridges", locations[7]),
        ("NDL-T10-003", f"There is dumping and road damage near {locations[9]} bus stop too.", "Solid Waste", locations[9]),
    ]
    for idx, (case_ref, raw_message, subdomain, location) in enumerate(spam_specs):
        created_at = spam_thread_started + timedelta(minutes=idx * 40)
        updated_at = created_at + timedelta(minutes=10 if idx < len(spam_specs) - 1 else 18)
        events = []
        spam_messages = []
        spam_flagged = False
        if idx == len(spam_specs) - 1:
            events = [{
                "message": "All these complaints came from the same contact in one day.",
                "event_type": "duplicate_followup",
                "created_at": (spam_thread_last - timedelta(minutes=50)).isoformat(),
            }]
            spam_flagged = True
            spam_messages = [{
                "message": "Another unrelated complaint about dumping near Peeranwadi bus stop.",
                "created_at": spam_thread_last.isoformat(),
            }]
        cases.append(
            _thread_case(
                tenant_id=tenant_id,
                case_ref=case_ref,
                phone="919811110003",
                thread_id=spam_thread_id,
                thread_demo_case="spam_suspected",
                raw_message=raw_message,
                category=category,
                subdomain=subdomain,
                location=location,
                assembly=demo_assembly,
                created_at=created_at,
                updated_at=updated_at,
                notes_for_staff="Demo: spam-suspected thread after 10 distinct issues in one 24-hour window.",
                distinct_issue_count=10,
                contact_thread_state="spam_suspected",
                thread_started_at=spam_thread_started,
                thread_last_activity_at=spam_thread_last,
                events=events,
                spam_messages=spam_messages,
                spam_flagged=spam_flagged,
            )
        )

    return cases


def _insert_demo_case(db: Session, case: dict) -> None:
    db.execute(
        sa_text(
            """
            INSERT INTO cases (
                tenant_id,
                user_phone,
                raw_message,
                category,
                status,
                location,
                ward,
                assembly,
                problem_domain,
                problem_subdomain,
                convergence_program_type,
                is_critical,
                response_to_citizen,
                notes_for_staff,
                case_metadata,
                created_at,
                updated_at,
                case_ref,
                is_deleted
            ) VALUES (
                :tenant_id,
                :user_phone,
                :raw_message,
                :category,
                :status,
                :location,
                :ward,
                :assembly,
                :problem_domain,
                :problem_subdomain,
                :convergence_program_type,
                :is_critical,
                :response_to_citizen,
                :notes_for_staff,
                CAST(:case_metadata AS json),
                :created_at,
                :updated_at,
                :case_ref,
                false
            )
            """
        ),
        {
            **case,
            "case_metadata": json.dumps(case["case_metadata"]),
        },
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed curated contact-thread demo data.")
    parser.add_argument("--tenant-id", type=int, default=10)
    parser.add_argument("--tenant-name", default="Sanket Jadhav")
    parser.add_argument("--constituency", default="Belagavi")
    parser.add_argument("--state", default="Karnataka")
    parser.add_argument("--house", default="Lok Sabha")
    parser.add_argument("--party", default="Independent")
    parser.add_argument("--tenant-type", default="aspirant")
    parser.add_argument("--account-stage", default="aspirant")
    parser.add_argument("--seat-type", default="mp")
    parser.add_argument("--whatsapp-number", default="demo_tenant10_thread_seed")
    parser.add_argument("--username", default="Jadhav")
    parser.add_argument("--password", required=True)
    parser.add_argument("--display-name", default="Sanket Jadhav")
    parser.add_argument("--role", default="owner")
    parser.add_argument("--user-phone", default="919900001010")
    parser.add_argument("--preserve-existing-cases", action="store_true")
    parser.add_argument("--demo-assembly", default=None)
    parser.add_argument("--allow-identity-overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db = SessionLocal()
    try:
        tenant = _ensure_tenant(db, args)
        _ensure_profile(db, tenant, args)
        _ensure_user(db, tenant, args)
        demo_assembly = _resolve_demo_assembly(db, tenant, args)
        demo_cases = _build_demo_cases(tenant.id, demo_assembly=demo_assembly)

        deleted = 0
        if not args.preserve_existing_cases:
            deleted = _delete_prior_demo_cases(db, tenant.id)

        for case in demo_cases:
            _insert_demo_case(db, case)

        db.commit()
        thread_count = len({case["case_metadata"]["contact_thread_id"] for case in demo_cases})
        print(
            f"Seeded tenant {tenant.id} ({args.username}) with {len(demo_cases)} sibling demo cases "
            f"across {thread_count} contact threads in assembly {demo_assembly}. "
            f"Deleted prior demo cases: {deleted}."
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
