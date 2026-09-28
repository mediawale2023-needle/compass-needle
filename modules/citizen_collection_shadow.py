"""Offline-only collection evaluator. Never sends WhatsApp messages.

A trusted upstream classifier must supply issue grouping and intent. This
module deliberately does not infer either from citizen free text.
"""
from dataclasses import dataclass
from typing import Sequence

from modules.citizen_communication_shadow import (
    CitizenReplyDecision, propose_citizen_reply, shadow_policy_enabled,
)


@dataclass(frozen=True)
class SyntheticMessage:
    text: str
    issue_key: str
    intent: str = "new_issue"


@dataclass(frozen=True)
class VerifiedIssueState:
    issue_key: str
    issue_type: str
    case_recorded: bool
    missing_information: tuple[str, ...] = ()
    emergency: bool = False
    silent_category: bool = False


@dataclass(frozen=True)
class CollectionDecision:
    decisions: tuple[CitizenReplyDecision, ...]
    proposed_message_count: int
    reason: str


def evaluate_collection(
    messages: Sequence[SyntheticMessage],
    issues: Sequence[VerifiedIssueState],
    *,
    language: str,
    permitted_to_reply: bool,
    max_proposed_messages: int = 1,
    provenance_verified: bool = False,
) -> CollectionDecision:
    """Evaluate a flushed synthetic collection, not each individual message.

    No database, AI or network calls. If segmentation or state is ambiguous,
    require review rather than guessing which issue a message belongs to.
    """
    if not provenance_verified:
        return CollectionDecision((), 0, "unverified_segment_provenance")
    if not messages:
        return CollectionDecision((), 0, "empty_collection")
    if not permitted_to_reply:
        return CollectionDecision((), 0, "outbound_not_authorized")
    if max_proposed_messages < 1:
        return CollectionDecision((), 0, "message_budget_exhausted")
    if any(not m.text.strip() or not m.issue_key.strip() for m in messages):
        return CollectionDecision((), 0, "unclassified_message")
    by_key = {issue.issue_key: issue for issue in issues}
    if len(by_key) != len(issues) or any(m.issue_key not in by_key for m in messages):
        return CollectionDecision((), 0, "ambiguous_issue_mapping")
    keys = tuple(dict.fromkeys(m.issue_key for m in messages))
    if len(keys) > max_proposed_messages:
        return CollectionDecision((), 0, "multiple_issues_require_review")
    results = []
    for key in keys:
        grouped = [m for m in messages if m.issue_key == key]
        intents = {m.intent for m in grouped}
        if len(intents) != 1:
            return CollectionDecision((), 0, "mixed_intents_require_review")
        issue = by_key[key]
        decision = propose_citizen_reply(
            concern=" ".join(m.text for m in grouped),
            language=language,
            case_recorded=issue.case_recorded,
            missing_information=issue.missing_information,
            emergency=issue.emergency,
            silent_category=issue.silent_category,
            permitted_to_reply=permitted_to_reply,
            issue_type=issue.issue_type,
            conversation_intent=grouped[0].intent,
        )
        results.append(decision)
    # Review is not an outbound proposal. Never partially reply to a collection
    # that contains an unresolved issue.
    if any(result.action == "review" for result in results):
        return CollectionDecision(tuple(results), 0, "review_required")
    count = sum(bool(result.text) for result in results)
    return CollectionDecision(tuple(results), count, "shadow_only")


def evaluate_collection_if_enabled(*args, **kwargs) -> CollectionDecision:
    """Feature-flagged offline entry point; flag cannot enable outbound sends."""
    if not shadow_policy_enabled():
        return CollectionDecision((), 0, "shadow_disabled")
    return evaluate_collection(*args, **kwargs)
