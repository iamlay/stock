from datetime import date, timedelta

import pytest
from etl import pipeline
from etl.sources.eastmoney import DailyBar, DailySeries
from fastapi.testclient import TestClient

from app.db.session import get_session
from app.main import app


@pytest.fixture
def client_with_prices(session, monkeypatch) -> TestClient:
    pipeline.seed_universe(session)

    bars = []
    for index in range(120):
        close = 1.0 + index * 0.01 if index < 70 else 1.7 - (index - 70) * 0.012
        bars.append(
            DailyBar(
                trade_date=date(2024, 1, 1) + timedelta(days=index),
                open=close,
                high=close,
                low=close,
                close=close,
                volume=1_000_000,
                amount=1_000_000.0,
                amplitude=0.0,
            )
        )
    series = DailySeries(code="510300", name="沪深300ETF", bars=bars, source="test")
    monkeypatch.setattr(pipeline, "_fetch_series", lambda code, start, end: series)
    pipeline.sync_code(session, "510300", date(2024, 1, 1), date(2024, 12, 31))

    app.dependency_overrides[get_session] = lambda: session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_strategy_catalog(client_with_prices) -> None:
    response = client_with_prices.get("/api/v1/backtests/strategies")
    assert response.status_code == 200
    slugs = {item["slug"] for item in response.json()}
    assert {"buy-and-hold", "dual-ma", "rsi", "bollinger", "macd", "deviation"} <= slugs


def test_run_backtest(client_with_prices) -> None:
    response = client_with_prices.post(
        "/api/v1/backtests",
        json={
            "code": "510300",
            "strategy": "dual-ma",
            "start": "2024-01-01",
            "end": "2024-12-31",
            "params": {"fast": 5, "slow": 15},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "510300"
    assert body["strategy"] == "dual-ma"
    assert body["metrics"]["final_equity"] > 0
    assert len(body["equity"]) <= 600
    assert body["trades"]


def test_run_backtest_rejects_unknown_code(client_with_prices) -> None:
    response = client_with_prices.post(
        "/api/v1/backtests",
        json={"code": "999999", "strategy": "dual-ma"},
    )
    assert response.status_code == 404


def test_run_backtest_rejects_unknown_strategy(client_with_prices) -> None:
    response = client_with_prices.post(
        "/api/v1/backtests",
        json={"code": "510300", "strategy": "does-not-exist"},
    )
    assert response.status_code == 400
