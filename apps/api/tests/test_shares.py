from datetime import date

from etl import pipeline
from etl.sources.tencent_quote import EtfQuote, parse_quote_line
from sqlalchemy import func, select

from app.db.models import DataJob, EtfShareDaily, MarketDaily


def make_quote(code: str, price: float = 4.0, aum: float = 1200.0) -> EtfQuote:
    return EtfQuote(
        code=code,
        name=code,
        trade_date=date(2026, 10, 19),
        price=price,
        prev_close=price - 0.1,
        open=price - 0.05,
        change_pct=0.5,
        high=price + 0.05,
        low=price - 0.1,
        volume=1_000_000,
        amount=500_000_000.0,
        aum=aum,
        shares=round(aum / price, 4),
    )


def test_parse_quote_line() -> None:
    fields = [""] * 50
    fields[1] = "沪深300ETF"
    fields[2] = "510300"
    fields[3] = "4.240"
    fields[4] = "4.236"
    fields[5] = "4.224"
    fields[6] = "12105648"
    fields[30] = "20261019160639"
    fields[32] = "0.09"
    fields[33] = "4.267"
    fields[34] = "4.220"
    fields[37] = "513710"
    fields[44] = "1210.65"

    quote = parse_quote_line("510300", "~".join(fields))
    assert quote is not None
    assert quote.price == 4.24
    assert quote.aum == 1210.65
    assert round(quote.shares, 2) == 285.53
    assert quote.trade_date == date(2026, 10, 19)
    assert quote.amount == 5_137_100_000.0


def test_sync_shares_is_idempotent(session, monkeypatch) -> None:
    pipeline.seed_universe(session)
    quotes = [make_quote("510300"), make_quote("512890", price=1.2, aum=300.0)]
    monkeypatch.setattr(pipeline, "fetch_quotes", lambda codes: quotes)

    first = pipeline.sync_shares(session, ["510300", "512890"])
    assert first["rows"] == 2
    assert first["status"] == "success"

    second = pipeline.sync_shares(session, ["510300", "512890"])
    assert second["rows"] == 2

    assert session.scalar(select(func.count()).select_from(EtfShareDaily)) == 2
    assert session.scalar(select(func.count()).select_from(MarketDaily)) == 2
    assert session.scalar(select(func.count()).select_from(DataJob)) == 2
