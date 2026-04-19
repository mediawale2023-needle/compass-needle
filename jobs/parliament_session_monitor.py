"""
jobs/parliament_session_monitor.py — Detects active Lok Sabha sessions and
triggers incremental syncs on the right cadence.

Logic:
  - During an active session  → sync every 6 hours (questions appear within 24–48h)
  - Between sessions          → sync daily at 06:00 IST (catch late publications)
  - No completed sessions yet → do nothing

Run via cron or Railway cron service. Does NOT block — fires sync as background task.

Usage (cron, runs every hour):
  0 * * * * cd /app && python -m jobs.parliament_session_monitor

Or call from FastAPI startup / scheduler:
  from jobs.parliament_session_monitor import check_and_sync
  check_and_sync()
"""

import os
import sys
import logging
from datetime import datetime, date, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from jobs.parliament_scraper import (
    LOK_SABHA_18_SESSIONS,
    sync_all_active_tenants,
    backfill_all_confirmed_tenants,
)
from sqlalchemy import text
from sansadx_backend.db import engine

logger = logging.getLogger("needle.parliament.monitor")

# Sync cadences (hours between runs)
CADENCE_ACTIVE_SESSION   = 6    # during session: every 6h
CADENCE_BETWEEN_SESSIONS = 24   # between sessions: once a day


def get_session_state(today: date = None) -> dict:
    """
    Return the current session state based on today's date.

    Returns:
        {
          "in_session":    bool,
          "session_name":  str or None,
          "session_num":   int or None,
          "next_session":  (num, name, start) or None,   # upcoming session
          "latest_done":   (num, name) or None,           # most recently ended session
        }
    """
    today = today or date.today()

    in_session   = False
    session_name = None
    session_num  = None
    next_session = None
    latest_done  = None

    for num, name, start, end in LOK_SABHA_18_SESSIONS:
        if start <= today <= end:
            in_session   = True
            session_name = name
            session_num  = num
        elif start > today:
            if next_session is None:
                next_session = (num, name, start)
        elif end < today:
            latest_done = (num, name)

    return {
        "in_session":   in_session,
        "session_name": session_name,
        "session_num":  session_num,
        "next_session": next_session,
        "latest_done":  latest_done,
    }


def _hours_since_last_sync() -> float:
    """Return hours elapsed since any tenant was last synced. None if never."""
    try:
        with engine.connect() as conn:
            row = conn.execute(text("""
                SELECT MAX(parliament_last_synced) AS last
                FROM tenants
                WHERE parliament_sync_enabled = TRUE
                  AND parliament_member_id IS NOT NULL
            """)).mappings().fetchone()
        if row and row["last"]:
            delta = datetime.utcnow() - row["last"].replace(tzinfo=None)
            return delta.total_seconds() / 3600
    except Exception as e:
        logger.warning("Could not determine last sync time: %s", e)
    return float("inf")   # treat as never synced


def check_and_sync(force: bool = False) -> dict:
    """
    Main entry point. Checks session state and runs sync if cadence is due.

    Args:
        force: bypass cadence check and sync regardless

    Returns status dict.
    """
    state       = get_session_state()
    hours_since = _hours_since_last_sync()

    cadence = (
        CADENCE_ACTIVE_SESSION if state["in_session"]
        else CADENCE_BETWEEN_SESSIONS
    )

    logger.info(
        "Session monitor: in_session=%s session=%s hours_since_sync=%.1f cadence=%dh",
        state["in_session"], state["session_name"], hours_since, cadence,
    )

    if not force and hours_since < cadence:
        logger.info("Cadence not reached (%.1fh < %dh) — skipping sync", hours_since, cadence)
        return {**state, "action": "skipped", "reason": f"cadence not reached ({hours_since:.1f}h < {cadence}h)"}

    if state["latest_done"] is None and not state["in_session"]:
        logger.info("No completed sessions yet — nothing to sync")
        return {**state, "action": "skipped", "reason": "no completed sessions"}

    logger.info("Triggering incremental sync…")
    results = sync_all_active_tenants()
    total_new = sum(
        sum(v.values()) for v in results.values() if isinstance(v, dict)
    )

    logger.info("Sync complete: %d tenants, %d new records total", len(results), total_new)
    return {
        **state,
        "action":      "synced",
        "tenants":     len(results),
        "new_records": total_new,
    }


# ─────────────────────────────────────────
# CLI
# ─────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    import argparse
    parser = argparse.ArgumentParser(description="Parliament Session Monitor")
    parser.add_argument("--status",  action="store_true", help="Show session state only")
    parser.add_argument("--force",   action="store_true", help="Force sync regardless of cadence")
    args = parser.parse_args()

    if args.status:
        import json
        state = get_session_state()
        print(json.dumps({k: str(v) if isinstance(v, date) else v
                          for k, v in state.items()}, indent=2))
    else:
        result = check_and_sync(force=args.force)
        print(result)
