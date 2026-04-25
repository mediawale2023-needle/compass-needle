from modules.sansadai_api import _effective_topic_for_row, infer_issue_topic


def test_infer_issue_topic_prefers_budget_and_finance_signals():
    topic = infer_issue_topic(
        "Details of funds allocated and expenditure under PMGSY",
        ministry="Ministry of Rural Development",
    )
    assert topic == "Budget & Finance"


def test_infer_issue_topic_catches_challenges_and_delays():
    topic = infer_issue_topic(
        "Delay in completion of railway bridge projects and pending clearances",
        ministry="Ministry of Railways",
    )
    assert topic == "Challenges & Delays"


def test_effective_topic_for_row_uses_fallback_when_topic_is_missing():
    row = {
        "subject": "State-wise number of beneficiaries covered under Ayushman Bharat",
        "ministry": "Ministry of Health and Family Welfare",
        "topic": None,
        "topic_tags": ["beneficiaries", "state-wise"],
    }
    assert _effective_topic_for_row(row) == "Data & Statistics"


def test_effective_topic_for_row_preserves_existing_canonical_topic():
    row = {
        "subject": "Random subject text",
        "ministry": "Ministry of External Affairs",
        "topic": "International & Bilateral",
        "topic_tags": [],
    }
    assert _effective_topic_for_row(row) == "International & Bilateral"
