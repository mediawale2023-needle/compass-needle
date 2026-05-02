from unittest.mock import MagicMock

import modules.case_query_parser as parser


def test_parse_query_gpt_path_normalizes_and_clamps(query_filters_factory, monkeypatch):
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[
            MagicMock(
                message=MagicMock(
                    content='{"location":"Tilakwadi","constituency":"","days":999,"issue_type":"Water","status":"PENDING"}'
                )
            )
        ]
    )
    monkeypatch.setattr(parser, "_get_client", lambda: mock_client)

    result = parser.parse_query("Pending water cases in Tilakwadi last 999 days", tenant_id=7)

    assert result == query_filters_factory(
        location="Tilakwadi",
        days=365,
        issue_type="Water",
        status="pending",
    )


def test_parse_query_falls_back_to_regex_on_bad_gpt_json(query_filters_factory, monkeypatch):
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="{not valid json"))]
    )
    monkeypatch.setattr(parser, "_get_client", lambda: mock_client)

    result = parser.parse_query("Pending water cases in Tilakwadi last month", tenant_id=3)

    assert result == query_filters_factory(
        location="Tilakwadi",
        days=30,
        issue_type="Water",
        status="pending",
    )


def test_regex_fallback_handles_hinglish_time_and_status(query_filters_factory, monkeypatch):
    monkeypatch.setattr(parser, "_get_client", lambda: None)
    result = parser.parse_query("Resolved road complaints in Bhandup ek mahina", tenant_id=1)

    assert result == query_filters_factory(
        location="Bhandup",
        days=30,
        issue_type="Road",
        status="resolved",
    )


def test_regex_fallback_maps_this_month_and_clamps_days(query_filters_factory, monkeypatch):
    monkeypatch.setattr(parser, "_get_client", lambda: None)
    this_month = parser._regex_fallback("water issues in Bhandup this month")
    huge_range = parser._regex_fallback("water cases in Koil last 999 days")

    assert this_month == query_filters_factory(
        location="Bhandup",
        days=30,
        issue_type="Water",
    )
    assert huge_range["days"] == 365
