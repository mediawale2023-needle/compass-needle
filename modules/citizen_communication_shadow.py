"""Inert citizen communication policy: no WhatsApp calls, DB access or production wiring.

The policy is intentionally conservative. It can propose a response for synthetic
tests and shadow evaluation, but cannot authorize an outbound message.
"""
from dataclasses import dataclass
from typing import Literal
import os

Action = Literal["silent", "acknowledge", "clarify", "review"]

@dataclass(frozen=True)
class CitizenReplyDecision:
    action: Action
    text: str
    reason: str


def propose_citizen_reply(
    *,
    concern: str,
    language: str,
    case_recorded: bool,
    missing_information: tuple[str, ...] = (),
    emergency: bool = False,
    silent_category: bool = False,
    permitted_to_reply: bool = False,
    issue_type: str = "",
    conversation_intent: str = "new_issue",
) -> CitizenReplyDecision:
    """Draft only; never treat a draft as proof of send or case progress.

    This prototype supports English synthetic fixtures only. Other languages
    require independently reviewed templates before any proposed rollout.
    """
    if emergency or silent_category or not permitted_to_reply:
        return CitizenReplyDecision("silent", "", "outbound_not_authorized")
    if language.strip().lower() != "english":
        return CitizenReplyDecision("review", "", "language_template_not_reviewed")
    if conversation_intent not in {"new_issue", "follow_up", "status_inquiry"}:
        return CitizenReplyDecision("review", "", "unreviewed_intent")
    if not case_recorded:
        return CitizenReplyDecision("review", "", "case_record_not_confirmed")
    concern = " ".join(concern.split()).strip()
    if not concern:
        return CitizenReplyDecision("review", "", "concern_not_available")
    # Only controlled, pre-reviewed issue labels may appear in outgoing text.
    issue_labels = {
        "streetlight": "the streetlight problem",
        "water_supply": "the water supply problem",
        "road": "the road problem",
        "pension": "the pension issue",
        "drainage": "the drainage problem",
    }
    if issue_type and issue_type not in issue_labels:
        return CitizenReplyDecision("review", "", "unreviewed_issue_type")
    subject = issue_labels.get(issue_type, "your message")
    if conversation_intent in {"follow_up", "status_inquiry"}:
        return CitizenReplyDecision("review", "", "case_status_must_be_verified_before_reply")
    if missing_information:
        allowed = {"village", "area", "ward", "location", "details"}
        fields = tuple(dict.fromkeys(x.strip().lower() for x in missing_information))
        if not fields or any(x not in allowed for x in fields):
            return CitizenReplyDecision("review", "", "unreviewed_clarification_field")
        question = "Could you please share your " + " and ".join(fields[:2]) + "?"
        return CitizenReplyDecision("clarify", "We have recorded " + subject + ". " + question, "verified_record_missing_information")
    return CitizenReplyDecision("acknowledge", "We have recorded " + subject + " for review.", "verified_record")


def shadow_policy_enabled() -> bool:
    """Explicit opt-in for offline shadow comparisons; never authorizes sending."""
    return os.getenv("CITIZEN_COMMUNICATION_SHADOW_ENABLED", "").strip().lower() in {"1", "true", "yes"}
