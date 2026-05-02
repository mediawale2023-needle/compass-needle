import os
from datetime import datetime

import pytest


os.environ.setdefault("JWT_SECRET", "x" * 32)
os.environ.setdefault("ENV", "test")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-testing")


@pytest.fixture
def fixed_now():
    return datetime(2026, 4, 29, 12, 0, 0)


@pytest.fixture
def query_filters_factory():
    def _make(**overrides):
        base = {
            "location": "",
            "constituency": "",
            "days": 7,
            "issue_type": "",
            "status": "",
        }
        base.update(overrides)
        return base

    return _make


@pytest.fixture
def sample_case_row_factory():
    def _make(**overrides):
        base = {
            "id": 101,
            "user_phone": "919876543210",
            "category": "Water",
            "status": "pending",
            "raw_message": "No water supply in Tilakwadi since two days",
            "location": "Tilakwadi",
            "assembly": "Belagavi North",
            "ward": "Ward 5",
            "is_critical": False,
            "created_at": datetime(2026, 4, 28, 10, 30, 0),
            "case_metadata": {"matched_value": "Tilakwadi", "assembly_constituency": "Belagavi North"},
            "case_ref": "CN-101",
        }
        base.update(overrides)
        return base

    return _make
