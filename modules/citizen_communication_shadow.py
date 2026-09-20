"""Inert citizen communication policy: no WhatsApp calls, DB access or production wiring.

The policy is intentionally conservative. It can propose a response for synthetic
tests and shadow evaluation, but cannot authorize an outbound message.
"""
from dataclasses import dataclass
from typing import Literal

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
) -> CitizenReplyDecision:
    """Draft only; never treat a draft as proof of send or case progress.

    This prototype supports English synthetic fixtures only. Other languages
    require independently reviewed templates before any proposed rollout.
    """
    if emergency or silent_category or not permitted_to_reply:
        return CitizenReplyDecision("silent", "", "outbound_not_authorized")
    if language.strip().lower() != "english":
        return CitizenReplyDecision("review", "", "language_template_not_reviewed")
    if not case_recorded:
        return CitizenReplyDecision("review", "", "case_record_not_confirmed")
    concern = " ".join(concern.split()).strip()
    if not concern:
        return CitizenReplyDecision("review", "", "concern_not_available")
    # Do not echo untrusted free text into a citizen-facing message.
    if missing_information:
        allowed = {"village", "area", "ward", "location", "details"}
        fields = tuple(dict.fromkeys(x.strip().lower() for x in missing_information))
        if not fields or any(x not in allowed for x in fields):
            return CitizenReplyDecision("review", "", "unreviewed_clarification_field")
        question = "Could you please share your " + " and ".join(fields[:2]) + "?"
        return CitizenReplyDecision("clarify", "We have recorded your message. " + question, "verified_record_missing_information")
    return CitizenReplyDecision("acknowledge", "We have recorded your message for review.", "verified_record")
