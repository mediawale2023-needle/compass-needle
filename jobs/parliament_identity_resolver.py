"""
jobs/parliament_identity_resolver.py — MP identity resolution against sansad.in (18th Lok Sabha)

Maps each subscribed tenant's MP name + constituency to their sansad.in parliament
member ID (mpsno). This is the one-time anchor that unlocks all future parliamentary
data scraping for that tenant.

API used:
  GET https://sansad.in/api_ls/member?loksabha=18&sitting=1&locale=en&page=1&size=600
  Headers: Referer: https://sansad.in/ls/members
  → Returns all ~543 sitting 18th Lok Sabha members as JSON.

Confidence thresholds:
  ≥ 85  → AUTO_MATCHED  : stored immediately, no admin action needed
  60–84 → NEEDS_REVIEW  : stored as candidate, admin must confirm in Parliament Sync screen
  < 60  → UNMATCHED     : admin must manually enter the mpsno from sansad.in

Usage:
  # Resolve all tenants without a member_id (run once for existing tenants)
  from jobs.parliament_identity_resolver import resolve_all_unmatched
  results = resolve_all_unmatched()

  # Resolve a single tenant (called at onboarding)
  from jobs.parliament_identity_resolver import resolve_tenant
  result = resolve_tenant(tenant_id=5)
"""

import os
import sys
import logging
import time
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Optional

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sansadx_backend.db import SessionLocal, Tenant, TenantProfile
from sqlalchemy import text

logger = logging.getLogger("needle.parliament.resolver")

# ─────────────────────────────────────────
# SANSAD.IN API CONFIG
# ─────────────────────────────────────────
SANSAD_API_URL = (
    "https://sansad.in/api_ls/member"
    "?loksabha=18&sitting=1&locale=en&page=1&size=600"
)
SANSAD_HEADERS = {
    "Referer": "https://sansad.in/ls/members",
    "User-Agent": "Mozilla/5.0 (compatible; NeedleParliamentSync/1.0)",
    "Accept": "application/json",
}
SANSAD_TIMEOUT_SECS = 15

# Confidence bands
CONFIDENCE_AUTO_MATCH  = 85.0   # auto-store, no review
CONFIDENCE_NEEDS_REVIEW = 60.0  # store as candidate, admin confirms
# < 60 → UNMATCHED

# Honorifics to strip before name comparison
_HONORIFICS = {"shri", "smt", "dr", "adv", "prof", "col", "brig", "capt",
               "maj", "lt", "ms", "mr", "mrs", "kumar", "kumari"}

# ─────────────────────────────────────────
# IN-MEMORY MEMBER CACHE (refreshed every 24h)
# ─────────────────────────────────────────
_member_cache: list[dict] = []
_cache_fetched_at: Optional[datetime] = None
_CACHE_TTL_HOURS = 24


def _normalize_name(name: str) -> str:
    """Strip honorifics and punctuation, lowercase, collapse whitespace."""
    if not name:
        return ""
    words = name.lower().replace(".", " ").replace(",", " ").split()
    return " ".join(w for w in words if w not in _HONORIFICS).strip()


def _normalize_constituency(name: str) -> str:
    """Lowercase + strip common suffixes that vary across sources."""
    if not name:
        return ""
    return (
        name.lower()
        .replace(" (sc)", "").replace(" (st)", "").replace(" (gen)", "")
        .strip()
    )


def fetch_all_members(force_refresh: bool = False) -> list[dict]:
    """
    Return all sitting 18th Lok Sabha members from sansad.in.
    Results are cached in memory for 24 hours.
    """
    global _member_cache, _cache_fetched_at

    if (
        not force_refresh
        and _member_cache
        and _cache_fetched_at
        and datetime.utcnow() - _cache_fetched_at < timedelta(hours=_CACHE_TTL_HOURS)
    ):
        return _member_cache

    logger.info("Fetching 18th Lok Sabha member list from sansad.in …")
    try:
        resp = requests.get(SANSAD_API_URL, headers=SANSAD_HEADERS, timeout=SANSAD_TIMEOUT_SECS)
        resp.raise_for_status()
        data = resp.json()
        # API returns either a list or {"data": [...]} — handle both
        members = data if isinstance(data, list) else data.get("data", data.get("members", []))
        if not isinstance(members, list) or len(members) < 100:
            raise ValueError(f"Unexpected response shape — got {len(members) if isinstance(members, list) else type(members)}")
        _member_cache = members
        _cache_fetched_at = datetime.utcnow()
        logger.info("Cached %d 18th Lok Sabha members", len(_member_cache))
        return _member_cache
    except Exception as e:
        logger.error("Failed to fetch member list from sansad.in: %s", e)
        if _member_cache:
            logger.warning("Returning stale cache (%d members)", len(_member_cache))
            return _member_cache
        raise RuntimeError(f"sansad.in member list unavailable: {e}") from e


def _score_candidate(candidate: dict, mp_name: str, constituency: str) -> tuple[float, float, float]:
    """
    Score one sansad.in member record against the given mp_name + constituency.

    Returns: (combined_score, constituency_score, name_score)  — all 0–100.

    Constituency is weighted 70% because Lok Sabha constituencies are globally
    unique — an exact constituency match almost always identifies the right MP.
    Name is 30% as a confirmation signal.
    """
    cand_const = _normalize_constituency(candidate.get("constName", ""))
    cand_name  = _normalize_name(candidate.get("mpFirstLastName", ""))

    query_const = _normalize_constituency(constituency)
    query_name  = _normalize_name(mp_name)

    const_score = SequenceMatcher(None, cand_const, query_const).ratio() * 100
    name_score  = SequenceMatcher(None, cand_name,  query_name).ratio()  * 100

    combined = 0.70 * const_score + 0.30 * name_score
    return combined, const_score, name_score


def find_best_match(mp_name: str, constituency: str) -> Optional[dict]:
    """
    Search the cached member list for the best matching sansad.in record.

    Returns a result dict with all fields + confidence info, or None if
    no candidate scores above the NEEDS_REVIEW threshold.
    """
    members = fetch_all_members()

    best_score    = 0.0
    best_const    = 0.0
    best_name     = 0.0
    best_candidate: Optional[dict] = None

    for m in members:
        combined, c_score, n_score = _score_candidate(m, mp_name, constituency)
        if combined > best_score:
            best_score     = combined
            best_const     = c_score
            best_name      = n_score
            best_candidate = m

    if best_candidate is None or best_score < CONFIDENCE_NEEDS_REVIEW:
        return None

    status = (
        "auto_matched"  if best_score >= CONFIDENCE_AUTO_MATCH  else
        "needs_review"
    )

    return {
        "member_id":             str(best_candidate["mpsno"]),
        "matched_name":          best_candidate.get("mpFirstLastName", ""),
        "matched_constituency":  best_candidate.get("constName", "").strip(),
        "matched_state":         best_candidate.get("stateName", ""),
        "party":                 best_candidate.get("partyFname", ""),
        "photo_url":             best_candidate.get("imageUrl", ""),
        "confidence":            round(best_score, 1),
        "constituency_score":    round(best_const, 1),
        "name_score":            round(best_name, 1),
        "status":                status,
    }


# ─────────────────────────────────────────
# TENANT-LEVEL RESOLUTION
# ─────────────────────────────────────────

def resolve_tenant(tenant_id: int) -> dict:
    """
    Resolve parliament member identity for one tenant and persist the result.

    Returns a result dict describing the outcome. Does NOT overwrite an
    already-confirmed member_id (status='active').

    Called:
      - Automatically at MP onboarding (background task)
      - Manually via admin POST /parliament/sync/resolve-all
    """
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            return {"tenant_id": tenant_id, "error": "Tenant not found"}

        # Don't re-resolve if already confirmed (active)
        if tenant.parliament_sync_status == "active" and tenant.parliament_member_id:
            return {
                "tenant_id":  tenant_id,
                "member_id":  tenant.parliament_member_id,
                "status":     "already_confirmed",
                "skipped":    True,
            }

        # Get MP name + constituency from TenantProfile (richer data) or Tenant itself
        profile = db.query(TenantProfile).filter(TenantProfile.tenant_id == tenant_id).first()
        mp_name      = (profile.mp_name      if profile else None) or tenant.name or ""
        constituency = (profile.constituency if profile else None) or tenant.constituency or ""
        house        = (profile.house        if profile else None) or "Lok Sabha"

        if not mp_name or not constituency:
            _update_sync_status(db, tenant, "unmatched", None)
            return {
                "tenant_id":    tenant_id,
                "status":       "unmatched",
                "reason":       "Missing mp_name or constituency on tenant profile",
            }

        # Only 18th Lok Sabha for now
        if "rajya" in house.lower():
            _update_sync_status(db, tenant, "unmatched", None)
            return {
                "tenant_id": tenant_id,
                "status":    "unmatched",
                "reason":    "Rajya Sabha not yet supported",
            }

        # Search sansad.in
        try:
            match = find_best_match(mp_name, constituency)
        except RuntimeError as e:
            _update_sync_status(db, tenant, "error", None)
            return {"tenant_id": tenant_id, "status": "error", "reason": str(e)}

        if match is None:
            _update_sync_status(db, tenant, "unmatched", None)
            return {
                "tenant_id":    tenant_id,
                "mp_name":      mp_name,
                "constituency": constituency,
                "status":       "unmatched",
                "reason":       "No candidate above confidence threshold (60)",
            }

        # Persist based on confidence
        if match["status"] == "auto_matched":
            _update_sync_status(db, tenant, "active", match["member_id"])
            logger.info(
                "Auto-matched tenant %d (%s / %s) → mpsno=%s (confidence=%.1f)",
                tenant_id, mp_name, constituency, match["member_id"], match["confidence"]
            )
        else:
            # needs_review: store candidate in config, not in parliament_member_id yet
            tenant.config = {**(tenant.config or {}), "parliament_candidate": match}
            db.commit()
            logger.info(
                "Flagged tenant %d (%s / %s) for review — candidate mpsno=%s (confidence=%.1f)",
                tenant_id, mp_name, constituency, match["member_id"], match["confidence"]
            )

        return {
            "tenant_id":    tenant_id,
            "mp_name":      mp_name,
            "constituency": constituency,
            **match,
        }

    except Exception as e:
        logger.exception("resolve_tenant(%d) failed: %s", tenant_id, e)
        return {"tenant_id": tenant_id, "status": "error", "reason": "Internal error"}
    finally:
        db.close()


def resolve_all_unmatched() -> list[dict]:
    """
    Batch-resolve all tenants that don't yet have a parliament_member_id.
    Rate-limited to 1 request/sec to be polite to sansad.in.

    Called from admin API: POST /admin/parliament/sync/resolve-all
    """
    db = SessionLocal()
    try:
        unresolved = db.query(Tenant).filter(
            Tenant.parliament_member_id.is_(None),
            Tenant.parliament_sync_status != "active",
            Tenant.is_active == True,
        ).all()
        tenant_ids = [t.id for t in unresolved]
    finally:
        db.close()

    logger.info("Starting batch identity resolution for %d tenants …", len(tenant_ids))
    results = []
    for i, tid in enumerate(tenant_ids):
        result = resolve_tenant(tid)
        results.append(result)
        logger.info("[%d/%d] tenant_id=%d → %s", i + 1, len(tenant_ids), tid, result.get("status", "?"))
        # 1 request per second — polite to sansad.in
        if i < len(tenant_ids) - 1:
            time.sleep(1.0)

    summary = {s: sum(1 for r in results if r.get("status") == s)
               for s in ("auto_matched", "needs_review", "unmatched", "error", "already_confirmed")}
    logger.info("Batch resolve complete: %s", summary)
    return results


# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────

def _update_sync_status(db, tenant: Tenant, status: str, member_id: Optional[str]):
    """Persist sync status + optional member_id on the tenant row."""
    tenant.parliament_sync_status  = status
    tenant.parliament_last_synced  = datetime.utcnow()
    if member_id is not None:
        tenant.parliament_member_id = member_id
        tenant.parliament_house     = "lok_sabha"
    db.commit()


def confirm_tenant_match(tenant_id: int, member_id: str) -> dict:
    """
    Admin explicitly confirms a parliament member_id for a tenant.
    Used for both 'needs_review' confirmations and fully manual overrides.
    """
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            return {"error": "Tenant not found"}
        _update_sync_status(db, tenant, "active", str(member_id))
        # Clear any pending candidate from config
        config = tenant.config or {}
        config.pop("parliament_candidate", None)
        tenant.config = config
        db.commit()
        logger.info("Admin confirmed parliament member_id=%s for tenant %d", member_id, tenant_id)
        return {
            "tenant_id": tenant_id,
            "member_id": member_id,
            "status":    "active",
        }
    finally:
        db.close()


# ─────────────────────────────────────────
# CLI RUNNER (for testing / one-off backfill)
# ─────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")

    import argparse
    parser = argparse.ArgumentParser(description="Needle Parliament Identity Resolver")
    parser.add_argument("--tenant-id", type=int, help="Resolve a specific tenant")
    parser.add_argument("--all",       action="store_true", help="Resolve all unmatched tenants")
    parser.add_argument("--search",    nargs=2, metavar=("NAME", "CONSTITUENCY"),
                        help="Test search without writing to DB")
    args = parser.parse_args()

    if args.search:
        name, const = args.search
        print(f"\nSearching sansad.in for: {name!r} / {const!r}")
        result = find_best_match(name, const)
        if result:
            print(f"  ✅ {result['status'].upper()} — mpsno={result['member_id']}")
            print(f"     Matched: {result['matched_name']} / {result['matched_constituency']} ({result['matched_state']})")
            print(f"     Confidence: {result['confidence']} (const={result['constituency_score']}, name={result['name_score']})")
        else:
            print("  ❌ No match above threshold")
    elif args.tenant_id:
        r = resolve_tenant(args.tenant_id)
        print(r)
    elif args.all:
        results = resolve_all_unmatched()
        for r in results:
            print(r)
    else:
        parser.print_help()
