from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.db.models import EtfProfile, Instrument, MarketDaily
from app.db.session import get_session
from app.main import app


def test_strategy_summary_returns_real_metrics(session) -> None:
    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(app)
    try:
        session.add(
            Instrument(
                code="510300",
                name="沪深300ETF",
                type="etf",
                exchange="SH",
                lot_size=100,
                is_active=True,
            )
        )
        session.add(EtfProfile(code="510300", category="宽基"))
        start = date(2025, 1, 2)
        for index in range(180):
            close = 4 + index * 0.002 + (0.1 if index % 20 < 10 else 0)
            session.add(
                MarketDaily(
                    code="510300",
                    trade_date=start + timedelta(days=index),
                    open=close,
                    high=close * 1.005,
                    low=close * 0.995,
                    close=close,
                    prev_close=close,
                    volume=100000,
                    amount=1000000,
                    adj_factor=1,
                    source="test",
                )
            )
        session.commit()

        response = client.get("/api/v1/backtests/summary?code=510300")
        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "510300"
        assert len(body["items"]) >= 5
        first = body["items"][0]
        assert first["curve"][0] == 100
        assert "benchmark_return" in first
        assert first["trades"] >= 0
    finally:
        app.dependency_overrides.clear()
