"""Synthetic collection tests: no citizen data and no outbound calls."""
from modules.citizen_collection_shadow import (
    SyntheticMessage, VerifiedIssueState, evaluate_collection,
    evaluate_collection_if_enabled,
)


def issue(key="one", **overrides):
    args = dict(issue_key=key, issue_type="streetlight", case_recorded=True)
    args.update(overrides)
    return VerifiedIssueState(**args)


def evaluate(messages, issues=None, **kwargs):
    return evaluate_collection(messages, [issue()] if issues is None else issues,
        language="English", permitted_to_reply=True, provenance_verified=True, **kwargs)


def test_multiple_messages_one_issue_one_proposed_reply():
    result = evaluate([
        SyntheticMessage("Streetlight is broken", "one"),
        SyntheticMessage("Near the school", "one"),
        SyntheticMessage("Please check", "one"),
    ])
    assert result.proposed_message_count == 1
    assert result.decisions[0].action == "acknowledge"


def test_separate_issues_require_review_not_multiple_messages():
    result = evaluate([SyntheticMessage("Streetlight", "one"),
        SyntheticMessage("Water supply", "two")],
        [issue(), issue("two", issue_type="water_supply")])
    assert result.proposed_message_count == 0
    assert result.reason == "multiple_issues_require_review"


def test_unknown_issue_mapping_fails_closed():
    result = evaluate([SyntheticMessage("Streetlight", "unknown")])
    assert result.proposed_message_count == 0
    assert result.reason == "ambiguous_issue_mapping"


def test_mixed_new_issue_and_follow_up_requires_review():
    result = evaluate([SyntheticMessage("Streetlight", "one"),
        SyntheticMessage("Any update?", "one", intent="status_inquiry")])
    assert result.proposed_message_count == 0


def test_status_inquiry_needs_verified_status():
    result = evaluate([SyntheticMessage("Any update?", "one", intent="status_inquiry")])
    assert result.proposed_message_count == 0
    assert result.reason == "review_required"


def test_no_reply_when_not_permitted():
    result = evaluate_collection([SyntheticMessage("Streetlight", "one")],
        [issue()], language="English", permitted_to_reply=False, provenance_verified=True)
    assert result.proposed_message_count == 0


def test_emergency_remains_silent():
    result = evaluate([SyntheticMessage("Emergency", "one")],
        [issue(emergency=True)])
    assert result.proposed_message_count == 0


def test_unconfirmed_case_does_not_claim_recorded():
    result = evaluate([SyntheticMessage("Streetlight", "one")],
        [issue(case_recorded=False)])
    assert result.proposed_message_count == 0


def test_disabled_flag_never_evaluates(monkeypatch):
    monkeypatch.delenv("CITIZEN_COMMUNICATION_SHADOW_ENABLED", raising=False)
    result = evaluate_collection_if_enabled([SyntheticMessage("Streetlight", "one")],
        [issue()], language="English", permitted_to_reply=True, provenance_verified=True)
    assert result.reason == "shadow_disabled"
    assert result.proposed_message_count == 0


def test_unverified_segment_provenance_fails_closed():
    result = evaluate_collection([SyntheticMessage("Streetlight", "one")],
        [issue()], language="English", permitted_to_reply=True)
    assert result.reason == "unverified_segment_provenance"
    assert result.proposed_message_count == 0
