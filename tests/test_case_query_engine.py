from datetime import datetime, timedelta

import modules.case_query_engine as engine


def test_query_cases_builds_expected_filters_and_enriches_results(
    query_filters_factory,
    sample_case_row_factory,
    monkeypatch,
):
    captured = []

    def fake_q(sql, params=None):
        captured.append((sql, dict(params or {})))
        if "FROM cases c" in sql and "ORDER BY c.is_critical DESC" in sql:
            return [
                sample_case_row_factory(),
                sample_case_row_factory(
                    id=102,
                    category="Water",
                    status="completed",
                    user_phone="+919912345678",
                    raw_message="Pipeline repaired yesterday",
                    location=None,
                    assembly="Belagavi North",
                    ward=None,
                    is_critical=True,
                    case_metadata='{"matched_value":"Camp","assembly_constituency":"Belagavi North"}',
                    case_ref="CN-102",
                ),
            ]
        return []

    def fake_q_one(sql, params=None):
        captured.append((sql, dict(params or {})))
        if "COUNT(*) AS total" in sql:
            return {"total": 12}
        if "GROUP BY c.category" in sql:
            return {"category": "Water", "cnt": 6}
        if "GROUP BY loc" in sql:
            return {"loc": "Tilakwadi", "cnt": 4}
        return None

    monkeypatch.setattr(engine, "_q", fake_q)
    monkeypatch.setattr(engine, "_q_one", fake_q_one)

    filters = query_filters_factory(
        location="Tilakwadi",
        constituency="Belagavi",
        days=30,
        issue_type="Water",
        status="pending",
    )
    result = engine.query_cases(filters, tenant_id=99)

    main_sql, main_params = captured[0]
    assert "c.tenant_id = :tid" in main_sql
    assert "c.location ILIKE :loc" in main_sql
    assert "c.assembly ILIKE :assembly" in main_sql
    assert "c.category ILIKE :cat" in main_sql
    assert "c.status IN (:st0, :st1)" in main_sql
    assert main_params["tid"] == 99
    assert main_params["loc"] == "%Tilakwadi%"
    assert main_params["assembly"] == "%Belagavi%"
    assert main_params["cat"] == "%Water%"
    assert main_params["st0"] == "pending"
    assert main_params["st1"] == "new"
    assert isinstance(main_params["since"], datetime)
    assert datetime.utcnow() - timedelta(days=31) < main_params["since"] < datetime.utcnow()

    assert result["total"] == 12
    assert result["high_priority"] == 1
    assert result["top_issue"] == "Water"
    assert result["top_location"] == "Tilakwadi"
    assert result["cases"][0]["location"] == "Tilakwadi"
    assert result["cases"][0]["assembly"] == "Belagavi North"
    assert result["cases"][0]["case_ref"] == "CN-101"
    assert result["cases"][1]["location"] == "Camp"
    assert result["cases"][1]["is_critical"] is True


def test_query_cases_returns_friendly_error_on_db_failure(query_filters_factory, monkeypatch):
    monkeypatch.setattr(engine, "_q", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(engine, "_q_one", lambda *args, **kwargs: None)

    result = engine.query_cases(query_filters_factory(location="Koil"), tenant_id=1)

    assert result == {
        "cases": [],
        "total": 0,
        "high_priority": 0,
        "top_issue": "",
        "top_location": "",
        "filters_applied": query_filters_factory(location="Koil"),
        "error": "DB query failed",
    }


def test_query_cases_status_mapping_for_resolved_uses_completed_and_resolved(
    query_filters_factory,
    monkeypatch,
):
    captured = []

    monkeypatch.setattr(engine, "_q", lambda sql, params=None: captured.append((sql, dict(params or {}))) or [])
    monkeypatch.setattr(engine, "_q_one", lambda sql, params=None: None)

    engine.query_cases(query_filters_factory(status="resolved"), tenant_id=5)

    main_sql, main_params = captured[0]
    assert "c.status IN (:st0, :st1)" in main_sql
    assert main_params["st0"] == "completed"
    assert main_params["st1"] == "resolved"
