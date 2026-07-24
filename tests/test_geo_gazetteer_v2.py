"""Gazetteer + resolver v2: entity linking, learning loop, discovery, golden cases.

Golden regression cases at the bottom encode the exact failure classes that
drove 39 geography patches (May–July 2026): generic-word phantom matches,
short-name fuzzy coin flips, same-name-two-assemblies guesses. A fixed
failure class failing again fails this suite.
"""
import os
import sys

os.environ.setdefault("JWT_SECRET", "x" * 32)
os.environ.setdefault("ENV", "test")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import sansadx_backend.db as dbmod
from sansadx_backend.db import Base

TEST_DB_URL = "sqlite:///./test_geo_gazetteer.db"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, expire_on_commit=False)

import modules.gazetteer as gazetteer
import modules.geo_resolver_v2 as resolver_v2
from sansadx_backend.db import GeoPlace, GeoPlaceVariant, GeoDiscoveryItem, GeoResolutionLog, Tenant


def _seed():
    dbmod.engine = test_engine
    dbmod.SessionLocal = TestSession
    gazetteer.SessionLocal = TestSession
    Base.metadata.create_all(bind=test_engine)
    db = TestSession()
    try:
        for model in (GeoPlaceVariant, GeoDiscoveryItem, GeoResolutionLog, GeoPlace):
            db.query(model).delete(synchronize_session=False)
        db.query(Tenant).delete(synchronize_session=False)
        db.add(Tenant(id=1, name="Test MP", constituency="Ghaziabad", whatsapp_number="+911", is_active=True))
        db.commit()
    finally:
        db.close()


def _add_place(name, assembly, seat_name="Ghaziabad", seat_type="mp", status="verified", variants=()):
    db = TestSession()
    try:
        place = GeoPlace(
            seat_type=seat_type, seat_name=seat_name,
            parliamentary_constituency=seat_name, assembly=assembly,
            canonical_name=name, canonical_norm=gazetteer.normalize(name),
            place_type="locality", status=status, source="import_geography_data",
        )
        db.add(place)
        db.flush()
        db.add(GeoPlaceVariant(
            place_id=place.id, variant=name,
            variant_norm=gazetteer.normalize(name), provenance="canonical",
        ))
        for v in variants:
            db.add(GeoPlaceVariant(
                place_id=place.id, variant=v,
                variant_norm=gazetteer.normalize(v), provenance="import_manual_override",
            ))
        db.commit()
        return place.id
    finally:
        db.close()


# ── Candidate lookup ─────────────────────────────────────────────────────────

def test_exact_lookup_resolves():
    _seed()
    pid = _add_place("Unique Colony", "Loni")
    result = resolver_v2.resolve_v2("Unique Colony", tenant_id=1)
    assert result["decision"] == "accept"
    assert result["place_id"] == pid
    assert result["assembly"] == "Loni"
    assert result["confidence"] == "high"


def test_misspelling_within_budget_resolves_medium():
    _seed()
    _add_place("Unique Colony", "Loni")
    result = resolver_v2.resolve_v2("Uniqe Colony", tenant_id=1)
    assert result["decision"] == "accept"
    assert result["assembly"] == "Loni"
    assert result["confidence"] == "medium"


def test_seat_scoping_excludes_other_seats():
    _seed()
    _add_place("Shivaji Nagar", "Belgaum Uttar", seat_name="Belagavi")
    result = resolver_v2.resolve_v2("Shivaji Nagar", tenant_id=1)  # tenant 1 = Ghaziabad
    assert result["decision"] == "no_candidates"


# ── Golden failure classes ───────────────────────────────────────────────────

def test_golden_generic_words_cannot_match():
    """'compound', 'towers' etc. were blocklist whack-a-mole. In a closed
    registry non-places match nothing — no blocklist exists to maintain."""
    _seed()
    _add_place("Unique Colony", "Loni")
    for noise in ("compound", "towers ke paas", "basti", "kacheri road corner"):
        result = resolver_v2.resolve_v2(noise, tenant_id=1)
        assert result["decision"] == "no_candidates", noise


def test_golden_short_names_never_fuzzy():
    """'Loni' (4 chars) gets edit budget 0 — 'Boni' must not coin-flip onto it."""
    _seed()
    _add_place("Loni", "Loni")
    result = resolver_v2.resolve_v2("Boni", tenant_id=1)
    assert result["decision"] == "no_candidates"


def test_golden_same_name_two_assemblies_asks():
    """The tenant-10 class bug: same locality name in two assemblies must
    produce a disambiguation ask, never a silent guess."""
    _seed()
    _add_place("Gandhi Nagar", "Loni")
    _add_place("Gandhi Nagar", "Ghaziabad")
    result = resolver_v2.resolve_v2("Gandhi Nagar", tenant_id=1)
    assert result["decision"] == "ask"
    assert result["assembly"] is None
    assemblies = {c["assembly"] for c in result["candidates"]}
    assert assemblies == {"Loni", "Ghaziabad"}


def test_golden_relation_anchor_resolves_not_fragment():
    """'X ke paas wale compound mein' resolves the anchor X — the descriptive
    tail can no longer become a phantom match."""
    _seed()
    pid = _add_place("Unique Colony", "Loni")
    result = resolver_v2.resolve_v2("Unique Colony ke paas wale compound mein", tenant_id=1)
    assert result["decision"] == "accept"
    assert result["place_id"] == pid
    assert result["relation"] == "near"
    assert result["anchor"] == "Unique Colony"


# ── Learning loop ────────────────────────────────────────────────────────────

def test_correction_becomes_variant_and_resolves():
    _seed()
    pid = _add_place("Unique Colony", "Loni")
    before = resolver_v2.resolve_v2("Yunik Kaloni", tenant_id=1)
    assert before["decision"] == "no_candidates"

    outcome = gazetteer.record_correction(
        "Yunik Kaloni", "Loni", seat_type="mp", seat_name="Ghaziabad",
    )
    # Attached as a variant of the existing place (edit-distance anchored)
    # or created as a candidate — either way it must now resolve to Loni.
    assert outcome["action"] in ("variant_added", "candidate_created")

    after = resolver_v2.resolve_v2("Yunik Kaloni", tenant_id=1)
    assert after["decision"] == "accept"
    assert after["assembly"] == "Loni"


def test_correction_for_unknown_place_creates_candidate():
    _seed()
    outcome = gazetteer.record_correction(
        "Ashiyana Enclave", "Loni", seat_type="mp", seat_name="Ghaziabad",
    )
    assert outcome["action"] == "candidate_created"
    result = resolver_v2.resolve_v2("Ashiyana Enclave", tenant_id=1)
    assert result["decision"] == "accept"
    assert result["confidence"] == "medium"  # candidate entities never claim high


# ── Discovery queue ──────────────────────────────────────────────────────────

def test_unresolved_spans_cluster_in_discovery_queue():
    _seed()
    for phone in ("919911111111", "919922222222", "919933333333"):
        resolver_v2.resolve_v2(
            "Madhopura Chowk", tenant_id=1, citizen_phone=phone,
            message_excerpt="Paani nahi hai Madhopura Chowk",
        )
    queue = gazetteer.get_discovery_queue(seat_name="Ghaziabad")
    assert len(queue) == 1
    item = queue[0]
    assert item["span"] == "Madhopura Chowk"
    assert item["occurrences"] == 3
    assert item["distinct_citizens"] == 3


def test_discovery_promotion_makes_span_resolvable():
    _seed()
    resolver_v2.resolve_v2("Madhopura Chowk", tenant_id=1, citizen_phone="919911111111")
    queue = gazetteer.get_discovery_queue(seat_name="Ghaziabad")
    outcome = gazetteer.promote_discovery_item(queue[0]["id"], assembly="Loni", promoted_by="test")
    assert outcome["action"] == "promoted"

    result = resolver_v2.resolve_v2("Madhopura Chowk", tenant_id=1)
    assert result["decision"] == "accept"
    assert result["assembly"] == "Loni"

    remaining = gazetteer.get_discovery_queue(seat_name="Ghaziabad")
    assert remaining == []


# ── Import with provenance ───────────────────────────────────────────────────

def test_import_builds_entities_with_hierarchy(monkeypatch):
    _seed()
    monkeypatch.setattr(gazetteer, "_load_geography_sources", lambda: [
        ("mp", "Ghaziabad", "Ghaziabad", "Loni", [
            {"station_number": "1", "locality": "Unique Colony", "building_name": "School"},
            {"station_number": "2", "locality": "Unique Colony", "building_name": "Other Wing"},
            {"station_number": "3", "locality": "Ashok Vihar", "building_name": "",
             "parent_locality": "Unique Colony"},
        ]),
    ])
    monkeypatch.setattr(gazetteer, "_load_manual_override_rows", lambda: [
        ("mp", "Ghaziabad", "Loni", "Yoonik Colony", "import_manual_override"),
    ])
    stats = gazetteer.import_gazetteer()
    assert stats["places"] == 2  # dedup across stations
    db = TestSession()
    try:
        child = db.query(GeoPlace).filter(GeoPlace.canonical_norm == "ashok vihar").first()
        parent = db.query(GeoPlace).filter(GeoPlace.canonical_norm == "unique colony").first()
        assert child.parent_id == parent.id
        assert child.place_type == "sub_locality"
    finally:
        db.close()
    # Override alias attached as variant (fuzzy-anchored to Unique Colony)
    result = resolver_v2.resolve_v2("Yoonik Colony", tenant_id=1)
    assert result["decision"] == "accept"
    assert result["assembly"] == "Loni"


def test_resolution_trace_written():
    _seed()
    _add_place("Unique Colony", "Loni")
    resolver_v2.resolve_v2("Unique Colony", tenant_id=1)
    db = TestSession()
    try:
        rows = db.query(GeoResolutionLog).all()
        assert len(rows) == 1
        assert rows[0].decision == "accept"
        assert rows[0].assembly == "Loni"
        assert rows[0].resolver_version == "v2-shadow"
    finally:
        db.close()
