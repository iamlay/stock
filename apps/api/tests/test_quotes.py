from datetime import date, datetime

from etl.pipeline import sync_quotes
from etl.sources.tencent_quote import EtfQuote
from fastapi.testclient import TestClient

from app.db.models import EtfProfile, Instrument, MarketDaily, RealtimeQuote
from app.db.session import get_session
from app.main import app


def test_sync_quotes_overlays_latest_price(session, monkeypatch) -> None:
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
    for offset in range(3):
        session.add(
            MarketDaily(
                code="510300",
                trade_date=date(2026, 10, 17 + offset),
                open=4.0,
                high=4.0,
                low=4.0,
                close=4.0,
                prev_close=4.0,
                volume=1000,
                amount=100000,
                adj_factor=1,
                source="test",
            )
        )
    session.commit()

    quote = EtfQuote(
        code="510300",
        name="沪深300ETF",
        trade_date=date(2026, 10, 19),
        quote_time=datetime(2026, 10, 19, 14, 35),
        price=4.5,
        prev_close=4.0,
        open=4.1,
        change_pct=12.5,
        high=4.6,
        low=4.0,
        volume=2000,
        amount=500000,
        aum=100.0,
        shares=22.2,
    )
    monkeypatch.setattr("etl.pipeline.fetch_quotes", lambda codes: [quote])

    result = sync_quotes(session, ["510300"])
    assert result["quotes"] == 1
    row = session.get(RealtimeQuote, "510300")
    assert row is not None
    assert float(row.price) == 4.5

    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(app)
    try:
        detail = client.get("/api/v1/etfs/510300")
        assert detail.status_code == 200
        body = detail.json()
        assert body["price"] == 4.5
        assert body["quote_time"].startswith("2026-10-19T14:35")
    finally:
        app.dependency_overrides.clear()
