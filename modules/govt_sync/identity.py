"""Stable identities for repeatable government-portal observations.

Identity normalization is deliberately separate from stored source values:
callers may normalize whitespace and dates for hashing, but must retain the
original portal text in their own persistence model.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any


def _clean_identity_text(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", unicodedata.normalize("NFC", str(value))).strip()
    return cleaned or None


def _identity_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=False)


def _legacy_clean_text(value: Any) -> str | None:
    if value is None:
        return None
    return re.sub(r"\s+", " ", str(value)).strip()


def _legacy_identity_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def communication_identity(item: dict) -> dict:
    """Preserve the pre-existing snapshot comment/reply identity contract."""
    stable_id = item.get("id") or item.get("portal_message_id") or item.get("message_id")
    if stable_id:
        return {"identity": f"stable:{stable_id}", "identity_quality": "stable"}
    author = _legacy_clean_text(item.get("author") or item.get("by") or item.get("sender"))
    posted_at = _legacy_clean_text(item.get("posted_at") or item.get("created_at") or item.get("date") or item.get("time"))
    text_value = _legacy_clean_text(item.get("text") or item.get("message") or item.get("body") or item.get("reply"))
    if author and posted_at and text_value:
        digest = hashlib.sha256(_legacy_identity_json({"author": author, "posted_at": posted_at, "text": text_value}).encode("utf-8")).hexdigest()
        return {"identity": f"derived:{digest}", "identity_quality": "derived"}
    digest = hashlib.sha256(_legacy_identity_json(item).encode("utf-8")).hexdigest()
    return {"identity": f"weak:{digest}", "identity_quality": "weak"}


def portal_history_identity(event: dict) -> dict:
    """Return a stable, derived, or controlled weak portal-event identity."""
    source = _clean_identity_text(event.get("source")) or "unknown"
    source_event_id = _clean_identity_text(event.get("source_event_id"))
    if source_event_id:
        return {
            "identity": f"stable:{source}:{source_event_id}",
            "identity_quality": "stable",
        }

    documents = event.get("documents") or []
    document_ids = sorted(
        filter(
            None,
            (_clean_identity_text(item.get("source_document_id")) for item in documents if isinstance(item, dict)),
        )
    )
    semantic = {
        "source": source,
        "occurred_at": _clean_identity_text(event.get("occurred_at")),
        "event_type": _clean_identity_text(event.get("event_type")),
        "status": _clean_identity_text(event.get("status")),
        "raw_status": _clean_identity_text(event.get("raw_status")),
        "sub_status": _clean_identity_text(event.get("sub_status")),
        "from_department": _clean_identity_text(event.get("from_department")),
        "from_office": _clean_identity_text(event.get("from_office")),
        "from_display": _clean_identity_text(event.get("from_display")),
        "to_department": _clean_identity_text(event.get("to_department")),
        "to_office": _clean_identity_text(event.get("to_office")),
        "to_display": _clean_identity_text(event.get("to_display")),
        "actor": _clean_identity_text(event.get("actor")),
        "designation": _clean_identity_text(event.get("designation")),
        "comment": _clean_identity_text(event.get("comment")),
        "document_ids": document_ids,
    }
    if any(value for key, value in semantic.items() if key != "source"):
        digest = hashlib.sha256(_identity_json(semantic).encode("utf-8")).hexdigest()
        return {"identity": f"derived:{digest}", "identity_quality": "derived"}

    safe_fallback = {
        "source": source,
        "source_metadata": event.get("source_metadata") or {},
        "documents": documents,
    }
    digest = hashlib.sha256(_identity_json(safe_fallback).encode("utf-8")).hexdigest()
    return {"identity": f"weak:{digest}", "identity_quality": "weak"}
