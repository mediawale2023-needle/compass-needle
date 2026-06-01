#!/usr/bin/env python3
"""
Tenant-scoped backfill for missing or obviously defaulted case languages.

Usage:
  venv/bin/python scripts/backfill_case_languages.py --tenant-id 10
  venv/bin/python scripts/backfill_case_languages.py --tenant-id 10 --limit 200 --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.localized_replies import normalize_language_name
from sansadx_backend.ai_engine import detect_input_language
from sansadx_backend.db import engine


def _best_language_source(row: dict[str, Any]) -> str:
    meta = row.get("case_metadata") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except Exception:
            meta = {}

    candidates = [
        meta.get("source_media_raw_transcript"),
        row.get("raw_message"),
        meta.get("summary"),
    ]
    for candidate in candidates:
        text_value = str(candidate or "").strip()
        if text_value:
            return text_value
    return ""


def _current_language(meta: dict[str, Any]) -> str:
    if not isinstance(meta, dict):
        return ""
    return normalize_language_name(
        str(meta.get("detected_language") or meta.get("language") or "").strip(),
        "",
    )


def _should_backfill(meta: dict[str, Any], source_text: str) -> bool:
    current = _current_language(meta)
    if not source_text.strip():
        return False
    if not current:
        return True
    # Legacy rows often showed EN in the UI because language was missing.
    # If a stored English label exists but the text itself is clearly not
    # English, allow correction.
    if current == "English" and detect_input_language(source_text) != "English":
        return True
    return False


def backfill_case_languages(*, tenant_id: int, limit: int = 500, dry_run: bool = False) -> dict[str, int]:
    updated = 0
    scanned = 0

    select_sql = text(
        """
        SELECT id, raw_message, case_metadata
        FROM cases
        WHERE tenant_id = :tenant_id
        ORDER BY id DESC
        LIMIT :limit
        """
    )

    update_sql = text(
        """
        UPDATE cases
        SET case_metadata = CAST(:meta AS jsonb)
        WHERE id = :case_id
        """
    )

    with engine.begin() as conn:
        rows = conn.execute(select_sql, {"tenant_id": tenant_id, "limit": limit}).mappings().all()
        for row in rows:
            scanned += 1
            meta = row.get("case_metadata") or {}
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    meta = {}
            source_text = _best_language_source(dict(row))
            if not _should_backfill(meta, source_text):
                continue
            detected = normalize_language_name(detect_input_language(source_text), "")
            if not detected:
                continue

            next_meta = dict(meta)
            next_meta["detected_language"] = detected
            next_meta["language"] = detected
            diag = dict(next_meta.get("language_backfill") or {})
            diag.update({"source": "scripts/backfill_case_languages.py", "detected": detected})
            next_meta["language_backfill"] = diag

            if not dry_run:
                conn.execute(update_sql, {"meta": json.dumps(next_meta), "case_id": row["id"]})
            updated += 1

    return {"scanned": scanned, "updated": updated}


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill missing detected_language fields on cases")
    parser.add_argument("--tenant-id", type=int, required=True)
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    result = backfill_case_languages(
        tenant_id=args.tenant_id,
        limit=args.limit,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
