from datetime import date, datetime

from etl.pipeline import sync_stock_watchlist_quotes
from etl.sources.tencent_quote import EtfQuote
from sqlalchemy import select

from app.db.models import Instrument, StockRealtimeQuote, StockWatchlist, User


def test_sync_stock_watchlist_quotes(session, monkeypatch) -> None:
    user = User(phone="13800006666", role="member", plan="free")
    session.add(user)
    session.add(
        Instrument(
            code="600519",
            name="贵州茅台",
            type="stock",
            exchange="SH",
            lot_size=100,
            is_active=True,
        )
    )
    session.commit()
    session.refresh(user)
    session.add(StockWatchlist(user_id=user.id, code="600519"))
    session.commit()

    quote = EtfQuote(
        code="600519",
        name="贵州茅台",
        trade_date=date(2026, 10, 27),
        quote_time=datetime(2026, 10, 27, 14, 35),
        price=1500.0,
        prev_close=1490.0,
        open=1495.0,
        change_pct=0.67,
        high=1510.0,
        low=1480.0,
        volume=1000,
        amount=1_500_000.0,
        aum=0.0,
        shares=0.0,
    )
    monkeypatch.setattr("etl.pipeline.fetch_quotes", lambda codes: [quote])

    result = sync_stock_watchlist_quotes(session)
    assert result["codes"] == 1
    assert result["quotes"] == 1
    row = session.scalar(
        select(StockRealtimeQuote).where(StockRealtimeQuote.code == "600519")
    )
    assert row is not None
    assert float(row.price) == 1500.0
    assert float(row.change_pct) == 0.67
