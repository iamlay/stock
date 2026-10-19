from datetime import date, timedelta

import pytest
from etl import pipeline
from etl.sources.eastmoney import DailyBar, DailySeries
from fastapi.testclient import TestClient

from app.db.models import IndexValuation
from app.db.session import get_session
from app.main import app


@pytest.fixture
def client_with_data(session, monkeypatch):
    pipeline.seed_universe(session)

    start = date(2024, 1, 1)
    bars = []
    for index in range(30):
        close = 1.0 + index * 0.01
        bars.append(
            DailyBar(
                trade_date=start + timedelta(days=index),
                open=close,
                high=close,
                low=close,
                close=close,
                volume=1000 + index,
                amount=1_000_000.0,
                amplitude=0.0,
            )
        )
    series = DailySeries(code="510300", name="沪深300ETF", bars=bars, source="test")
    monkeypatch.setattr(pipeline, "_fetch_series", lambda code, start, end: series)
    pipeline.sync_code(session, "510300", date(2024, 1, 1), date(2024, 12, 31))
    session.add(
        IndexValuation(
            index_code="SH000300",
            trade_date=date(2024, 1, 30),
            name="沪深300",
            pe=12.9,
            pb=1.3,
            pe_percentile=0.5548,
            pb_percentile=0.2972,
            dividend_yield=0.0282,
            bond_yield=0.05,
            source="test",
        )
    )
    session.commit()

    app.dependency_overrides[get_session] = lambda: session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_etf_list_contains_indicators(client_with_data) -> None:
    response = client_with_data.get("/api/v1/etfs")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    item = rows[0]
    assert item["code"] == "510300"
    assert item["price"] == 1.29
    assert item["ma20"] is not None
    assert item["turnover"] == 1_000_000.0
    assert item["pe"] == 12.9
    assert item["pe_percentile"] == 55.5
    assert item["dividend_yield"] == 2.82


def test_etf_detail_returns_bars(client_with_data) -> None:
    response = client_with_data.get("/api/v1/etfs/510300")
    assert response.status_code == 200
    body = response.json()
    assert len(body["bars"]) == 30
    assert body["bars"][0]["date"] == "2024-01-01"
    assert body["max_drawdown_1y"] == 0.0


def test_etf_detail_404(client_with_data) -> None:
    response = client_with_data.get("/api/v1/etfs/999999")
    assert response.status_code == 404


def test_market_overview_uses_real_data(client_with_data) -> None:
    response = client_with_data.get("/api/v1/market/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["demo"] is False
    assert body["etf_count"] == 1
    assert body["turnover_billion"] == 0.01
