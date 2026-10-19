from etl import pipeline
from fastapi.testclient import TestClient

from app.db.session import get_session
from app.main import app


def test_data_status_returns_counts(session, monkeypatch) -> None:
    from datetime import date

    from etl.sources.eastmoney import DailyBar, DailySeries

    pipeline.seed_universe(session)
    series = DailySeries(
        code="510300",
        name="沪深300ETF",
        bars=[DailyBar(date(2024, 1, 2), 1.0, 1.0, 1.0, 1.0, 100, 100.0, 0.0)],
        source="test",
    )
    monkeypatch.setattr(pipeline, "_fetch_series", lambda code, start, end: series)
    pipeline.sync_code(session, "510300", date(2024, 1, 1), date(2024, 1, 5))

    app.dependency_overrides[get_session] = lambda: session
    try:
        client = TestClient(app)
        response = client.get("/api/v1/data/status")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["instruments"] == 20
    assert body["daily_bars"] == 1
    assert body["latest_trade_date"] == "2024-01-02"
    assert body["last_job"]["status"] == "success"
