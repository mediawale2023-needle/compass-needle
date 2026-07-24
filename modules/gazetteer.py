"""Geography gazetteer — canonical place registry and entity lookup.

The gazetteer replaces string-vs-string geography matching with entity
linking against a closed, curated registry:

- ``GeoPlace``: a place with identity, type, hierarchy (parent_id), assembly,
  status (verified/candidate/deprecated) and provenance.
- ``GeoPlaceVariant``: every known spelling/script/romanization of a place,
  individually deprecatable, each with provenance.
- ``GeoResolutionLog``: full evidence trace per resolution attempt.
- ``GeoDiscoveryItem``: system-surfaced missing places clustered from
  unresolved spans — discovery is the system's job, not staff's.

Matching only ever links text to entities in this registry. Free text that is
not a curated place ("compound", "towers", venue fragments) structurally
cannot match anything, which removes the need for generic-word blocklists.

Import provenance: existing shared geography (``geography_data`` override
rows / repo JSON) seeds verified locality entities; approved manual overrides
(``geo_manual_override`` / ``geo_seat_manual_override``) become variants (or
candidate entities when no matching place exists) tagged with their origin.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

from sansadx_backend.db import (
    SessionLocal,
    GeoPlace,
    GeoPlaceVariant,
    GeoResolutionLog,
    GeoDiscoveryItem,
)
from modules.geography_resolver import normalize

logger = logging.getLogger("needle.gazetteer")

# Auto-promotion guardrails for discovery items: this many *distinct citizens*
# must have used an unresolved span (with no name collision in the seat)
# before it may be promoted without a human tap.
AUTO_PROMOTE_DISTINCT_CITIZENS = 3

_MAX_SAMPLE_MESSAGES = 5
_MAX_TRACKED_PHONES = 20


# ── Edit distance (bounded, early-exit) ──────────────────────────────────────

def _edit_distance_within(a: str, b: str, limit: int) -> int | None:
    """Levenshtein distance if ≤ limit, else None. Bands row-wise to exit early."""
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if abs(la - lb) > limit:
        return None
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        cur = [i] + [0] * lb
        row_min = cur[0]
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            row_min = min(row_min, cur[j])
        if row_min > limit:
            return None
        prev = cur
    return prev[lb] if prev[lb] <= limit else None


def edit_budget_for(name_norm: str) -> int:
    """Distance budget scales with name length — never one global threshold.

    Short Indian locality names ("Loni", "Koil") are one edit away from each
    other; they only match exactly. Longer names earn tolerance.
    """
    n = len(name_norm)
    if n <= 4:
        return 0
    if n <= 7:
        return 1
    if n <= 11:
        return 2
    return 3


# ── Import / seeding ─────────────────────────────────────────────────────────

def _seat_key(seat_type: str, seat_name: str) -> tuple[str, str]:
    st = "mla" if normalize(seat_type or "") == "mla" else "mp"
    return st, str(seat_name or "").strip()


def import_gazetteer(replace: bool = False) -> dict:
    """Seed the gazetteer from existing geography sources with provenance.

    Sources, in authority order:
    1. Shared geography (``geography_data`` rows via get_all_geography_data,
       falling back to repo JSON files) → verified ``locality`` entities.
       Explicit hierarchy in the rows (parent_locality / sub_locality fields
       persisted by the Core Geography editor) becomes parent edges.
    2. Approved manual overrides → variants on the matching place, or
       candidate entities when the alias names a place we don't know yet.

    Idempotent: existing (seat, assembly, canonical_norm) places are reused.
    ``replace=True`` wipes and re-imports (dev/test only).
    """
    stats = {"places": 0, "variants": 0, "override_variants": 0, "override_candidates": 0}
    sources = _load_geography_sources()
    db = SessionLocal()
    try:
        if replace:
            for model in (GeoPlaceVariant, GeoDiscoveryItem, GeoResolutionLog, GeoPlace):
                db.query(model).delete(synchronize_session=False)
            db.commit()

        # Pass 1: places from shared geography.
        for seat_type, seat_name, parl, assembly, stations in sources:
            st, sn = _seat_key(seat_type, seat_name)
            seen_norms: dict[str, GeoPlace] = {}
            pending_parent: list[tuple[GeoPlace, str]] = []
            for row in stations or []:
                locality = str((row or {}).get("locality") or "").strip()
                norm = normalize(locality)
                if not norm:
                    continue
                place = seen_norms.get(norm) or _get_place(db, st, sn, assembly, norm)
                if place is None:
                    place = GeoPlace(
                        seat_type=st,
                        seat_name=sn,
                        parliamentary_constituency=parl,
                        assembly=assembly,
                        canonical_name=locality,
                        canonical_norm=norm,
                        place_type="locality",
                        status="verified",
                        source="import_geography_data",
                    )
                    db.add(place)
                    db.flush()
                    db.add(GeoPlaceVariant(
                        place_id=place.id, variant=locality, variant_norm=norm,
                        provenance="canonical",
                    ))
                    stats["places"] += 1
                    stats["variants"] += 1
                seen_norms[norm] = place
                explicit_parent = str((row or {}).get("parent_locality") or "").strip()
                if explicit_parent and normalize(explicit_parent) != norm:
                    pending_parent.append((place, normalize(explicit_parent)))
            # Parent edges only from explicitly authored hierarchy — never inferred.
            for place, parent_norm in pending_parent:
                parent = seen_norms.get(parent_norm) or _get_place(db, st, sn, place.assembly, parent_norm)
                if parent is not None and parent.id != place.id and place.parent_id is None:
                    place.parent_id = parent.id
                    place.place_type = "sub_locality"
        db.commit()

        # Pass 2: approved manual overrides → variants (or candidate places).
        for st, sn, assembly, alias, provenance in _load_manual_override_rows():
            norm = normalize(alias)
            if not norm:
                continue
            place = _find_place_for_override(db, st, sn, assembly, norm)
            if place is not None:
                if not _variant_exists(db, place.id, norm):
                    db.add(GeoPlaceVariant(
                        place_id=place.id, variant=alias, variant_norm=norm,
                        provenance=provenance,
                    ))
                    stats["override_variants"] += 1
            else:
                candidate = GeoPlace(
                    seat_type=st, seat_name=sn,
                    parliamentary_constituency=sn if st == "mp" else "",
                    assembly=assembly,
                    canonical_name=alias, canonical_norm=norm,
                    place_type="locality", status="candidate",
                    source=provenance,
                )
                db.add(candidate)
                db.flush()
                db.add(GeoPlaceVariant(
                    place_id=candidate.id, variant=alias, variant_norm=norm,
                    provenance=provenance,
                ))
                stats["override_candidates"] += 1
        db.commit()
        logger.info("Gazetteer import: %s", stats)
        return stats
    finally:
        db.close()


def _load_geography_sources() -> list[tuple]:
    """(seat_type, seat_name, parl, assembly, stations) — DB first, repo JSON fallback."""
    sources: list[tuple] = []
    try:
        from sansadx_backend.db import get_all_geography_data
        for row in get_all_geography_data() or []:
            sources.append((
                row.get("seat_type") or "mp",
                row.get("seat_name") or row.get("parliamentary_constituency"),
                row.get("parliamentary_constituency"),
                row.get("assembly"),
                row.get("stations"),
            ))
    except Exception as exc:
        logger.warning("Gazetteer: DB geography load failed: %s", exc)
    if sources:
        return sources
    try:
        from modules.geography_resolver import GEOGRAPHY_BASE_PATH
        base = GEOGRAPHY_BASE_PATH
        if base and base.exists():
            for parl_dir in base.iterdir():
                if not parl_dir.is_dir():
                    continue
                for json_file in parl_dir.glob("*.json"):
                    try:
                        with open(json_file, "r", encoding="utf-8") as fh:
                            stations = json.load(fh)
                    except Exception:
                        continue
                    sources.append(("mp", parl_dir.name, parl_dir.name, json_file.stem, stations))
    except Exception as exc:
        logger.warning("Gazetteer: repo JSON geography load failed: %s", exc)
    return sources


def _load_manual_override_rows() -> list[tuple]:
    """(seat_type, seat_name, assembly, alias, provenance) from approved overrides."""
    rows: list[tuple] = []
    try:
        from sansadx_backend.db import SessionLocal as _SL, TenantOverride, Tenant
        db = _SL()
        try:
            for r in db.query(TenantOverride).filter(
                TenantOverride.override_type.in_(
                    ["geo_manual_override", "geo_override", "geo_seat_manual_override"]
                )
            ).all():
                alias, assembly = str(r.key or ""), str(r.value or "")
                if r.override_type == "geo_seat_manual_override":
                    # key format: "<seat_type>:<seat_name>|<alias>"
                    head, _, alias_part = alias.partition("|")
                    st, _, sn = head.partition(":")
                    if alias_part and sn:
                        rows.append((st or "mp", sn, assembly, alias_part, "import_manual_override"))
                    continue
                seat_name = None
                seat_type = "mp"
                if r.tenant_id:
                    t = db.query(Tenant).filter(Tenant.id == r.tenant_id).first()
                    if t is not None and t.constituency:
                        seat_name = t.constituency
                        try:
                            from sansadx_backend.db import derive_seat_type
                            seat_type = derive_seat_type(t) or "mp"
                        except Exception:
                            pass
                if seat_name:
                    rows.append((seat_type, seat_name, assembly, alias, "import_manual_override"))
        finally:
            db.close()
    except Exception as exc:
        logger.warning("Gazetteer: manual override load failed: %s", exc)
    return rows


def _get_place(db, seat_type: str, seat_name: str, assembly: str, norm: str) -> GeoPlace | None:
    return (
        db.query(GeoPlace)
        .filter(
            GeoPlace.seat_type == seat_type,
            GeoPlace.seat_name == seat_name,
            GeoPlace.assembly == assembly,
            GeoPlace.canonical_norm == norm,
            GeoPlace.status != "deprecated",
        )
        .first()
    )


def _find_place_for_override(db, seat_type: str, seat_name: str, assembly: str, norm: str) -> GeoPlace | None:
    """An override alias attaches to a same-assembly place whose name it matches."""
    exact = _get_place(db, seat_type, seat_name, assembly, norm)
    if exact:
        return exact
    # The alias may be a variant spelling of a known place in that assembly.
    budget = edit_budget_for(norm)
    if budget == 0:
        return None
    for place in (
        db.query(GeoPlace)
        .filter(
            GeoPlace.seat_type == seat_type,
            GeoPlace.seat_name == seat_name,
            GeoPlace.assembly == assembly,
            GeoPlace.status != "deprecated",
        )
        .all()
    ):
        if _edit_distance_within(norm, place.canonical_norm, budget) is not None:
            return place
    return None


def _variant_exists(db, place_id: int, norm: str) -> bool:
    return (
        db.query(GeoPlaceVariant.id)
        .filter(GeoPlaceVariant.place_id == place_id, GeoPlaceVariant.variant_norm == norm)
        .first()
        is not None
    )


# ── Candidate lookup ─────────────────────────────────────────────────────────

def lookup_candidates(span: str, *, seat_type: str | None = None, seat_name: str | None = None) -> list[dict]:
    """Return scored entity candidates for a text span, seat-scoped.

    Match tiers (score): exact variant (100), variant containing the span as a
    whole word or vice versa (82), bounded edit distance (90 - 8*distance).
    Only active variants of non-deprecated entities are searchable.
    """
    norm = normalize(span)
    if not norm or len(norm) < 3:
        return []
    db = SessionLocal()
    try:
        query = (
            db.query(GeoPlaceVariant, GeoPlace)
            .join(GeoPlace, GeoPlaceVariant.place_id == GeoPlace.id)
            .filter(GeoPlaceVariant.status == "active", GeoPlace.status != "deprecated")
        )
        if seat_name:
            st, sn = _seat_key(seat_type or "mp", seat_name)
            query = query.filter(GeoPlace.seat_type == st, GeoPlace.seat_name == sn)
        best: dict[int, dict] = {}
        budget = edit_budget_for(norm)
        span_words = set(norm.split())
        for variant, place in query.all():
            vn = variant.variant_norm
            score = None
            match_type = None
            if vn == norm:
                score, match_type = 100, "exact"
            else:
                dist = _edit_distance_within(norm, vn, budget) if budget else None
                if dist is not None and dist > 0:
                    score, match_type = 90 - 8 * dist, f"edit_{dist}"
                elif len(vn) >= 5 and (
                    vn in norm and set(vn.split()) <= span_words
                ):
                    # Variant appears inside the span as whole words
                    score, match_type = 82, "contains"
            if score is None:
                continue
            entry = best.get(place.id)
            if entry is None or score > entry["score"]:
                best[place.id] = {
                    "place_id": place.id,
                    "canonical_name": place.canonical_name,
                    "assembly": place.assembly,
                    "parliamentary_constituency": place.parliamentary_constituency,
                    "place_type": place.place_type,
                    "place_status": place.status,
                    "parent_id": place.parent_id,
                    "matched_variant": variant.variant,
                    "match_type": match_type,
                    "score": score,
                }
        return sorted(best.values(), key=lambda c: -c["score"])
    finally:
        db.close()


# ── Learning loop ────────────────────────────────────────────────────────────

def record_correction(
    alias: str,
    assembly: str,
    *,
    seat_type: str = "mp",
    seat_name: str,
    provenance: str = "learned_from_correction",
) -> dict:
    """Harvest a human correction as permanent gazetteer data.

    Attaches the alias as a variant of the matching place in that assembly, or
    creates a candidate entity when the correction names an unknown place.
    Called as a side effect of staff doing normal casework — never as a
    separate curation task.
    """
    norm = normalize(alias)
    if not norm:
        return {"action": "skipped"}
    st, sn = _seat_key(seat_type, seat_name)
    db = SessionLocal()
    try:
        place = _find_place_for_override(db, st, sn, assembly, norm)
        if place is not None:
            if _variant_exists(db, place.id, norm):
                return {"action": "exists", "place_id": place.id}
            db.add(GeoPlaceVariant(
                place_id=place.id, variant=alias, variant_norm=norm, provenance=provenance,
            ))
            db.commit()
            logger.info("Gazetteer learned variant %r -> place %s (%s)", alias, place.id, provenance)
            return {"action": "variant_added", "place_id": place.id}
        candidate = GeoPlace(
            seat_type=st, seat_name=sn,
            parliamentary_constituency=sn if st == "mp" else "",
            assembly=assembly, canonical_name=alias, canonical_norm=norm,
            place_type="locality", status="candidate", source=provenance,
        )
        db.add(candidate)
        db.flush()
        db.add(GeoPlaceVariant(
            place_id=candidate.id, variant=alias, variant_norm=norm, provenance=provenance,
        ))
        db.commit()
        logger.info("Gazetteer learned candidate place %r in %s (%s)", alias, assembly, provenance)
        return {"action": "candidate_created", "place_id": candidate.id}
    finally:
        db.close()


# ── Discovery queue ──────────────────────────────────────────────────────────

def note_unresolved_span(
    span: str,
    *,
    seat_type: str = "mp",
    seat_name: str,
    citizen_phone: str = "",
    message_excerpt: str = "",
    proposed_assembly: str | None = None,
) -> None:
    """Cluster an unresolved extraction into the discovery queue.

    Recurring spans accumulate occurrence/citizen counts; the queue is the
    system surfacing missing places instead of waiting for staff to notice.
    """
    norm = normalize(span)
    if not norm or len(norm) < 3:
        return
    st, sn = _seat_key(seat_type, seat_name)
    db = SessionLocal()
    try:
        item = (
            db.query(GeoDiscoveryItem)
            .filter(
                GeoDiscoveryItem.seat_type == st,
                GeoDiscoveryItem.seat_name == sn,
                GeoDiscoveryItem.span_norm == norm,
                GeoDiscoveryItem.status == "open",
            )
            .first()
        )
        now = datetime.utcnow()
        phone_tail = str(citizen_phone or "")[-10:]
        if item is None:
            item = GeoDiscoveryItem(
                seat_type=st, seat_name=sn,
                span_norm=norm, span_display=span.strip(),
                occurrence_count=1, distinct_citizens=1 if phone_tail else 0,
                citizen_phones=json.dumps([phone_tail] if phone_tail else []),
                sample_messages=json.dumps([message_excerpt[:200]] if message_excerpt else []),
                proposed_assembly=proposed_assembly,
                first_seen_at=now, last_seen_at=now,
            )
            db.add(item)
        else:
            item.occurrence_count += 1
            item.last_seen_at = now
            phones = json.loads(item.citizen_phones or "[]")
            if phone_tail and phone_tail not in phones:
                phones = (phones + [phone_tail])[:_MAX_TRACKED_PHONES]
                item.citizen_phones = json.dumps(phones)
                item.distinct_citizens = len(phones)
            samples = json.loads(item.sample_messages or "[]")
            if message_excerpt and len(samples) < _MAX_SAMPLE_MESSAGES:
                samples.append(message_excerpt[:200])
                item.sample_messages = json.dumps(samples)
            if proposed_assembly and not item.proposed_assembly:
                item.proposed_assembly = proposed_assembly
        db.commit()
    except Exception as exc:
        logger.warning("Gazetteer discovery upsert failed for %r: %s", span, exc)
    finally:
        db.close()


def get_discovery_queue(seat_name: str | None = None, limit: int = 50) -> list[dict]:
    """Open discovery items ranked by citizen impact (distinct citizens, then volume)."""
    db = SessionLocal()
    try:
        query = db.query(GeoDiscoveryItem).filter(GeoDiscoveryItem.status == "open")
        if seat_name:
            query = query.filter(GeoDiscoveryItem.seat_name == seat_name)
        items = (
            query.order_by(
                GeoDiscoveryItem.distinct_citizens.desc(),
                GeoDiscoveryItem.occurrence_count.desc(),
            )
            .limit(limit)
            .all()
        )
        return [
            {
                "id": i.id,
                "seat_name": i.seat_name,
                "span": i.span_display,
                "occurrences": i.occurrence_count,
                "distinct_citizens": i.distinct_citizens,
                "proposed_assembly": i.proposed_assembly,
                "sample_messages": json.loads(i.sample_messages or "[]"),
                "first_seen_at": i.first_seen_at.isoformat() if i.first_seen_at else None,
                "last_seen_at": i.last_seen_at.isoformat() if i.last_seen_at else None,
                "auto_promotable": bool(
                    i.distinct_citizens >= AUTO_PROMOTE_DISTINCT_CITIZENS and i.proposed_assembly
                ),
            }
            for i in items
        ]
    finally:
        db.close()


def promote_discovery_item(item_id: int, *, assembly: str | None = None, promoted_by: str = "") -> dict:
    """Turn a discovery item into a candidate place entity (one-tap promote)."""
    db = SessionLocal()
    try:
        item = db.query(GeoDiscoveryItem).filter(GeoDiscoveryItem.id == item_id).first()
        if item is None:
            return {"error": "not_found"}
        if item.status != "open":
            return {"error": "not_open", "status": item.status}
        target_assembly = str(assembly or item.proposed_assembly or "").strip()
        if not target_assembly:
            return {"error": "assembly_required"}
        existing = _get_place(db, item.seat_type, item.seat_name, target_assembly, item.span_norm)
        if existing is not None:
            item.status = "merged"
            item.promoted_place_id = existing.id
            db.commit()
            return {"action": "merged", "place_id": existing.id}
        place = GeoPlace(
            seat_type=item.seat_type, seat_name=item.seat_name,
            parliamentary_constituency=item.seat_name if item.seat_type == "mp" else "",
            assembly=target_assembly,
            canonical_name=item.span_display, canonical_norm=item.span_norm,
            place_type="locality", status="candidate", source="auto_discovered",
        )
        db.add(place)
        db.flush()
        db.add(GeoPlaceVariant(
            place_id=place.id, variant=item.span_display, variant_norm=item.span_norm,
            provenance="auto_discovered",
        ))
        item.status = "promoted"
        item.promoted_place_id = place.id
        db.commit()
        logger.info(
            "Gazetteer discovery item %s promoted to place %s (%r in %s) by %s",
            item_id, place.id, item.span_display, target_assembly, promoted_by or "system",
        )
        return {"action": "promoted", "place_id": place.id}
    finally:
        db.close()


# ── Resolution trace ─────────────────────────────────────────────────────────

def log_resolution(
    *,
    tenant_id: int | None,
    extracted_span: str,
    relation: str | None,
    anchor_text: str | None,
    decision: str,
    place_id: int | None = None,
    assembly: str | None = None,
    confidence: str | None = None,
    candidates: list | None = None,
    evidence: dict | None = None,
    resolver_version: str = "v2-shadow",
    agrees_with_legacy: bool | None = None,
    legacy_result: dict | None = None,
) -> None:
    db = SessionLocal()
    try:
        db.add(GeoResolutionLog(
            tenant_id=tenant_id,
            extracted_span=(extracted_span or "")[:300],
            relation=relation,
            anchor_text=(anchor_text or "")[:300] or None,
            decision=decision,
            place_id=place_id,
            assembly=assembly,
            confidence=confidence,
            candidates=json.dumps(candidates or [])[:4000],
            evidence=json.dumps(evidence or {})[:4000],
            resolver_version=resolver_version,
            agrees_with_legacy=agrees_with_legacy,
            legacy_result=json.dumps(legacy_result or {})[:2000],
        ))
        db.commit()
    except Exception as exc:
        logger.warning("Gazetteer resolution log failed: %s", exc)
    finally:
        db.close()
