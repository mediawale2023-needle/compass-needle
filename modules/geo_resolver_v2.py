"""Gazetteer-backed geography resolver (v2).

Entity linking in three stages with honest boundaries:

1. Extraction happened upstream (AI or resolver text) — we receive a span.
2. Candidate generation: relation-aware lookup against the closed gazetteer
   (modules/gazetteer.py). Non-place text cannot match — no blocklists.
3. Decision: context-scored, three-way — ``accept`` (single confident
   candidate), ``ask`` (2-3 named candidates for citizen disambiguation),
   ``abstain`` (route to staff / discovery queue). Ambiguity produces a
   question, never a coin flip.

Runs in SHADOW MODE alongside the legacy resolver: it logs every decision
with full evidence and never influences the citizen-facing outcome until the
golden set proves it wins. Same champion/challenger pattern as the ack-policy
and classification rollouts.
"""
from __future__ import annotations

import logging

from modules.gazetteer import (
    lookup_candidates,
    log_resolution,
    note_unresolved_span,
)
from modules.geo_relations import parse_location_phrase

logger = logging.getLogger("needle.geo_resolver_v2")

RESOLVER_VERSION = "v2-shadow"

ACCEPT_SCORE = 82          # minimum score for a lone winner to auto-accept
ASK_MARGIN = 10            # runner-up within this of the winner → ambiguous
MAX_ASK_CANDIDATES = 3


def _seat_context(tenant_id: int | None) -> dict | None:
    if not tenant_id:
        return None
    try:
        from modules.geography_resolver import _get_tenant_seat_context
        return _get_tenant_seat_context(tenant_id)
    except Exception as exc:
        logger.warning("geo v2: seat context lookup failed for tenant %s: %s", tenant_id, exc)
        return None


def _citizen_history_assemblies(tenant_id: int | None, citizen_phone: str) -> set[str]:
    """Assemblies of the citizen's recent prior cases — a strong prior."""
    if not tenant_id or not citizen_phone:
        return set()
    try:
        from sansadx_backend.db import SessionLocal
        from sqlalchemy import text as sa_text
        db = SessionLocal()
        try:
            rows = db.execute(
                sa_text(
                    """
                    SELECT DISTINCT assembly FROM cases
                    WHERE tenant_id = :tid AND user_phone = :phone
                      AND assembly IS NOT NULL AND assembly != ''
                    ORDER BY assembly LIMIT 5
                    """
                ),
                {"tid": tenant_id, "phone": citizen_phone},
            ).fetchall()
            return {str(r[0]) for r in rows if r[0]}
        finally:
            db.close()
    except Exception:
        return set()


def resolve_v2(
    span: str,
    *,
    tenant_id: int | None = None,
    citizen_phone: str = "",
    message_excerpt: str = "",
    log: bool = True,
) -> dict:
    """Resolve one extracted location span to a place entity.

    Returns a decision dict:
      {decision, place_id, assembly, confidence, relation, anchor,
       candidates, evidence}
    and always writes a GeoResolutionLog row. Unresolvable spans feed the
    discovery queue when a seat context exists.
    """
    parsed = parse_location_phrase(span)
    relation, anchor = parsed["relation"], parsed["anchor"]

    seat = _seat_context(tenant_id)
    seat_type = (seat or {}).get("seat_type")
    seat_name = (seat or {}).get("seat_name")

    candidates = lookup_candidates(anchor, seat_type=seat_type, seat_name=seat_name)

    evidence: dict = {
        "span": span,
        "relation": relation,
        "anchor": anchor,
        "seat": seat_name,
        "boosts": [],
    }

    # Context scoring: history prior — citizens mostly report where they live.
    history = _citizen_history_assemblies(tenant_id, citizen_phone)
    if history:
        for cand in candidates:
            if cand["assembly"] in history:
                cand["score"] += 8
                evidence["boosts"].append(
                    {"place_id": cand["place_id"], "boost": "citizen_history", "points": 8}
                )
        candidates.sort(key=lambda c: -c["score"])

    def _finish(decision: str, *, place=None, confidence=None) -> dict:
        result = {
            "decision": decision,
            "place_id": place["place_id"] if place else None,
            "assembly": place["assembly"] if place else None,
            "canonical_name": place["canonical_name"] if place else None,
            "confidence": confidence,
            "relation": relation,
            "anchor": anchor,
            "candidates": candidates[:MAX_ASK_CANDIDATES],
            "evidence": evidence,
        }
        if not log:
            return result
        try:
            log_resolution(
                tenant_id=tenant_id,
                extracted_span=span,
                relation=relation,
                anchor_text=anchor,
                decision=decision,
                place_id=result["place_id"],
                assembly=result["assembly"],
                confidence=confidence,
                candidates=[
                    {k: c[k] for k in ("place_id", "canonical_name", "assembly", "match_type", "score")}
                    for c in candidates[:5]
                ],
                evidence=evidence,
                resolver_version=RESOLVER_VERSION,
            )
        except Exception as exc:
            logger.warning("geo v2: resolution log failed: %s", exc)
        return result

    if not candidates:
        if seat_name and anchor:
            try:
                note_unresolved_span(
                    anchor,
                    seat_type=seat_type or "mp",
                    seat_name=seat_name,
                    citizen_phone=citizen_phone,
                    message_excerpt=message_excerpt,
                )
            except Exception as exc:
                logger.warning("geo v2: discovery note failed: %s", exc)
        return _finish("no_candidates")

    winner = candidates[0]
    contenders = [c for c in candidates if c["score"] >= winner["score"] - ASK_MARGIN]
    contender_assemblies = {c["assembly"] for c in contenders}

    if len(contenders) > 1 and len(contender_assemblies) > 1:
        # Real ambiguity across assemblies → ask, never coin-flip.
        return _finish("ask")

    if winner["score"] >= ACCEPT_SCORE:
        confidence = "high" if winner["match_type"] == "exact" else "medium"
        # Candidate-status entities resolve but stay flagged for review.
        if winner.get("place_status") == "candidate":
            confidence = "medium"
        return _finish("accept", place=winner, confidence=confidence)

    return _finish("abstain")


def shadow_compare(
    *,
    span: str,
    tenant_id: int | None,
    citizen_phone: str = "",
    message_excerpt: str = "",
    legacy_assembly: str | None = None,
    legacy_resolved: bool = False,
) -> None:
    """Run v2 in shadow next to the legacy resolver and log agreement.

    Never raises, never changes the citizen-facing outcome. Disagreement data
    is what qualifies v2 to take over.
    """
    try:
        result = resolve_v2(
            span,
            tenant_id=tenant_id,
            citizen_phone=citizen_phone,
            message_excerpt=message_excerpt,
            log=False,
        )
        v2_assembly = result.get("assembly")
        if legacy_resolved and result["decision"] == "accept":
            agrees = bool(v2_assembly and legacy_assembly and v2_assembly == legacy_assembly)
        elif not legacy_resolved and result["decision"] in ("ask", "abstain", "no_candidates"):
            agrees = True  # both declined to guess
        else:
            agrees = False
        log_resolution(
            tenant_id=tenant_id,
            extracted_span=span,
            relation=result.get("relation"),
            anchor_text=result.get("anchor"),
            decision=f"shadow_{result['decision']}",
            place_id=result.get("place_id"),
            assembly=v2_assembly,
            confidence=result.get("confidence"),
            candidates=[
                {k: c[k] for k in ("place_id", "canonical_name", "assembly", "match_type", "score")}
                for c in result.get("candidates", [])
            ],
            evidence=result.get("evidence"),
            resolver_version=RESOLVER_VERSION,
            agrees_with_legacy=agrees,
            legacy_result={"resolved": legacy_resolved, "assembly": legacy_assembly},
        )
    except Exception as exc:
        logger.warning("geo v2 shadow compare failed (non-blocking): %s", exc)
