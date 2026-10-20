from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.db.models import EtfProfile, Instrument, MarketDaily
from app.db.session import get_session
from app.main import app


def test_compare_two_etfs(session) -> None:
    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(app)
    try:
        for code, name, category in [
            ("510300", "沪深300ETF", "宽基"),
            ("510500", "中证500ETF", "宽基"),
        ]:
            session.add(
                Instrument(
                    code=code,
                    name=name,
                    type="etf",
                    exchange="SH",
                    lot_size=100,
                    is_active=True,
                )
            )
            session.add(EtfProfile(code=code, category=category))
        start = date(2026, 1, 2)
        closes = {
            "510300": [4.0, 4.1, 4.2, 4.15, 4.3],
            "510500": [6.0, 6.0, 6.1, 6.05, 6.2],
        }
        for code, values in closes.items():
            for index, close in enumerate(values):
                session.add(
                    MarketDaily(
                        code=code,
                        trade_date=start + timedelta(days=index),
                        open=close,
                        high=close,
                        low=close,
                        close=close,
                        prev_close=close,
                        volume=1000,
                        amount=100000,
                        adj_factor=1,
                        source="test",
                    )
                )
        session.commit()

        response = client.get(
            "/api/v1/etfs/compare?codes=510300,510500&days=30"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["days"] == 5
        assert len(body["items"]) == 2
        first = body["items"][0]
        assert first["code"] == "510300"
        assert first["series"][0]["value"] == 100
        assert first["total_return"] > 0
        assert first["max_drawdown"] <= 0
    finally:
        app.dependency_overrides.clear()
