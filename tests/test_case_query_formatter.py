from datetime import datetime

import modules.case_query_formatter as formatter


def test_format_cases_for_whatsapp_no_results_message(query_filters_factory):
    message = formatter.format_cases_for_whatsapp(
        {
            "cases": [],
            "total": 0,
            "high_priority": 0,
            "top_issue": "",
            "top_location": "",
            "filters_applied": query_filters_factory(location="Tilakwadi", days=30),
        }
    )

    assert "No cases found" in message
    assert "*Tilakwadi*" in message
    assert "last 30 days" in message.lower()


def test_format_cases_for_whatsapp_renders_summary_and_truncates_messages(query_filters_factory):
    long_message = "Water line broken " * 10
    result = {
        "cases": [
            {
                "id": 1,
                "phone": "+919876543210",
                "category": "Water",
                "status": "pending",
                "message": long_message,
                "location": "Tilakwadi",
                "assembly": "Belagavi North",
                "ward": "Ward 5",
                "is_critical": True,
                "created_at": datetime(2026, 4, 28, 9, 15, 0),
                "case_ref": "CN-1",
            },
            {
                "id": 2,
                "phone": "919123456789",
                "category": "Road",
                "status": "completed",
                "message": "Pothole fixed",
                "location": "Camp",
                "assembly": "Belagavi North",
                "ward": "",
                "is_critical": False,
                "created_at": "2026-04-27T10:00:00",
                "case_ref": "",
            },
        ],
        "total": 12,
        "high_priority": 1,
        "top_issue": "Water",
        "top_location": "Tilakwadi",
        "filters_applied": query_filters_factory(constituency="Belagavi", days=7),
    }

    message = formatter.format_cases_for_whatsapp(result)

    assert "📍 *Belagavi Assembly – Last 7 Days*" in message
    assert "*Total: 12 complaints*  _(10 shown)_" in message
    assert "🚨 *URGENT*" in message
    assert '💬 "Water line broken' in message
    assert "..." in message
    assert "#CN-1" in message
    assert "📊 Top Issue: *Water* (1 cases)" in message
    assert "📍 Most Affected: *Tilakwadi*" in message
    assert "🔁 Pending: 1" in message
    assert "✅ Resolved: 1" in message


def test_format_cases_for_whatsapp_error_message_is_friendly():
    message = formatter.format_cases_for_whatsapp({"error": "DB query failed"})

    assert "couldn't fetch the cases" in message.lower()
    assert "try again" in message.lower()


def test_format_clarification_request_contains_examples():
    message = formatter.format_clarification_request()

    assert "What would you like to know?" in message
    assert "Cases in Kazimabad" in message
    assert "Road issues this week" in message
