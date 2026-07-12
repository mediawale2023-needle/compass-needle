"""Validation layer for outbound citizen messages.

Runs deterministic policy checks (modules/ack_policy.py) over any text that
is about to be sent to a citizen. Composer/template output is golden-tested
to always pass; the real purpose of this layer is the free-text lane —
staff-typed or AI-suggested notify messages from Briefcase.

Modes (ACK_POLICY_MODE env var):
- "shadow"  (default): violations are logged/recorded but never block a send.
- "enforce": free-text messages with violations are rejected by the API.

The validator itself only *reports*; mode handling belongs to callers so the
same checks can back both lanes.
"""
import os
import logging

from modules.ack_policy import (
    ALL_PATTERNS,
    ALLOWED_EMOJI,
    EMOJI_SCAN,
    MAX_ACK_LENGTH,
    MAX_NOTIFY_LENGTH,
    POLICY_VERSION,
)

logger = logging.getLogger("needle.ack_validator")


def ack_policy_mode() -> str:
    mode = (os.getenv("ACK_POLICY_MODE") or "shadow").strip().lower()
    return mode if mode in {"shadow", "enforce"} else "shadow"


def validate_citizen_message(text: str, *, lane: str = "notify") -> dict:
    """Check one outbound citizen message against the communication policy.

    Returns {"ok": bool, "violations": [{"code", "reason"}], "policy_version"}.
    Empty text is treated as valid — callers skip empty sends themselves.
    """
    violations = []
    value = str(text or "")
    if not value.strip():
        return {"ok": True, "violations": [], "policy_version": POLICY_VERSION}

    max_length = MAX_ACK_LENGTH if lane == "ack" else MAX_NOTIFY_LENGTH
    if len(value) > max_length:
        violations.append({
            "code": "too_long",
            "reason": f"message is {len(value)} chars (max {max_length} for {lane})",
        })

    seen_codes = set()
    for code, pattern, reason in ALL_PATTERNS:
        if (code, reason) in seen_codes:
            continue
        if pattern.search(value):
            violations.append({"code": code, "reason": reason})
            seen_codes.add((code, reason))

    stray_emoji = sorted({ch for ch in EMOJI_SCAN.findall(value) if ch not in ALLOWED_EMOJI})
    if stray_emoji:
        violations.append({
            "code": "emoji_not_allowed",
            "reason": f"only 🙏 is permitted; found: {' '.join(stray_emoji)}",
        })

    return {
        "ok": not violations,
        "violations": violations,
        "policy_version": POLICY_VERSION,
    }


def violation_codes(result: dict) -> list[str]:
    return sorted({v["code"] for v in (result or {}).get("violations", [])})
