"""
tests/test_govt_status_normalization.py — dedicated tests for
normalize_status_keywords() (fixation-plan Step 5: fail closed on
cross-bucket ambiguity, not just on no-match).

No dedicated test file exercised this function directly before this one —
Karnataka's and Maharashtra's suites only cover it incidentally, through
their own real captured strings, and neither ManualAssistedAdapter's
whole-page scan nor OtpGatedStatusMixin's (Rajasthan's real shape) had any
direct coverage at all. This file is that direct coverage.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.govt_sync.adapters.base import normalize_status_keywords


def test_no_match_returns_none():
    assert normalize_status_keywords("Waiting for departmental action") is None


def test_single_bucket_single_keyword():
    assert normalize_status_keywords("Rejected") == "rejected"


def test_single_bucket_multiple_keywords_still_resolves():
    # Real Rajasthan-shaped value — "disposed" and "resolved" are both in
    # the SAME `resolved` bucket. Multiple hits within one bucket must not
    # be treated as ambiguous.
    assert normalize_status_keywords("Disposed / Resolved") == "resolved"


def test_two_different_buckets_returns_none():
    # "rejected" (rejected bucket) + "closed" (resolved bucket) — a genuine
    # cross-bucket collision, unlike the superficially similar example
    # checked below.
    assert normalize_status_keywords("Grievance rejected and case closed") is None


def test_three_or_four_different_buckets_returns_none():
    text = "submitted, then under review, then rejected, then resolved"
    assert normalize_status_keywords(text) is None


def test_concrete_example_from_the_review_is_not_actually_a_collision():
    """The illustrative ambiguous example used throughout the resilience
    review and fixation plan — "closed as duplicate — see resolved ticket
    #4471" — was meant to demonstrate the general risk of cross-bucket
    collisions, but verified directly against the real STATUS_KEYWORDS
    content before writing this test: "closed" and "resolved" are BOTH in
    the same `resolved` bucket ("rejected"/"declined"/"अस्वीकृत" never
    appear in this string at all). This is a single-bucket, multiple-
    keyword match — per the rule this Step exists to implement, that must
    still resolve cleanly to "resolved", not None. Asserting the correct
    behavior here rather than the originally-assumed one; see
    test_two_different_buckets_returns_none above for an actual collision
    matching this exact concern."""
    text = "closed as duplicate — see resolved ticket #4471"
    assert normalize_status_keywords(text) == "resolved"


def test_real_karnataka_string_unchanged():
    assert normalize_status_keywords("Registered & Sent for Scrutiny") == "submitted"


def test_real_maharashtra_string_unchanged():
    assert normalize_status_keywords("Submitted") == "submitted"


def test_real_rajasthan_strings_unchanged():
    assert normalize_status_keywords("Disposed / Resolved") == "resolved"
    assert normalize_status_keywords("Registered") == "submitted"


def test_hindi_keywords_still_single_bucket():
    assert normalize_status_keywords("निस्तारित") == "resolved"
    assert normalize_status_keywords("अस्वीकृत") == "rejected"
    assert normalize_status_keywords("प्रक्रियाधीन") == "under_review"


def test_hindi_and_english_cross_bucket_still_detected():
    # "अस्वीकृत" (rejected bucket) + "resolved" (resolved bucket) — mixed
    # script, still a genuine two-bucket collision.
    assert normalize_status_keywords("अस्वीकृत but marked resolved") is None


def test_empty_and_none_input_returns_none():
    assert normalize_status_keywords("") is None
    assert normalize_status_keywords(None) is None


# ─── Integration: does a collision correctly reach checked=False on the ───
# ─── real poller/manual-adapter path (Step 2's audit logging depends on ───
# ─── that boolean, not on why it's False) ──────────────────────────────

def test_manual_adapter_reports_unchecked_on_cross_bucket_collision(monkeypatch):
    """ManualAssistedAdapter.check_status() is the generic fallback every
    future state uses first, and the one path poll_all_pending() actually
    calls for such portals. This confirms a genuine two-bucket collision in
    the scraped page text reaches StatusResult(checked=False) exactly the
    same way "no keyword matched at all" already did — which is the only
    thing poller.py's Step 2 logging (status_check_inconclusive, not
    status_polled) actually checks. Step 2 itself is unmodified and
    untested here; this only proves Step 5's new behavior feeds correctly
    into the boolean Step 2 already handles."""
    import requests
    from modules.govt_sync.adapters.manual import ManualAssistedAdapter

    class _FakeResponse:
        text = "<html><body>Grievance rejected and case closed</body></html>"
        def raise_for_status(self):
            pass

    monkeypatch.setattr(requests, "get", lambda *a, **kw: _FakeResponse())

    adapter = ManualAssistedAdapter({
        "portal_name": "Test Portal",
        "status_check_mode": "public_reference",
        "status_check_url": "https://example.test/status",
    })
    result = adapter.check_status("REF123")
    assert result.checked is False
    assert result.status == ""
