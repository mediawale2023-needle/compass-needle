from datetime import datetime

from modules import staff_schedule_parser as parser


def test_fallback_parser_extracts_schedule_from_english_message(monkeypatch):
    monkeypatch.setattr(parser, "_get_client", lambda: None)
    monkeypatch.setattr(parser, "_today_india", lambda: datetime(2026, 6, 4, 10, 0))

    result = parser.parse_staff_schedule_message("Meeting with Chief Minister on Wednesday at 5 PM")

    assert result is not None
    assert result["entry_type"] == "schedule"
    assert result["scheduled_for"] == "2026-06-10"
    assert result["start_time"] == "17:00"


def test_fallback_parser_ignores_case_query_like_messages(monkeypatch):
    monkeypatch.setattr(parser, "_get_client", lambda: None)
    monkeypatch.setattr(parser, "_today_india", lambda: datetime(2026, 6, 4, 10, 0))

    result = parser.parse_staff_schedule_message("Pending water cases in Tilakwadi last 1 month")

    assert result is None
