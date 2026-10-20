from datetime import date

from etl.sources.eastmoney_stock import DividendRecord
from etl.sources.sina_stock import SinaStockRow
from etl.stocks import (
    refresh_stock_metrics,
    sync_stock_dividends,
    sync_stock_pilot,
    upsert_stock_universe,
)

from app.db.models import StockDividend, StockMetric


def make_row(code: str, name: str, cap: float) -> SinaStockRow:
    return SinaStockRow(
        code=code,
        name=name,
        price=10.0,
        change_pct=1.0,
        market_cap=cap,
        pe_ttm=10.0,
        pb=1.0,
        industry="未分类",
        market="SH" if code.startswith("6") else "SZ",
        is_st=False,
    )


def test_upsert_universe_limit_by_market_cap(session) -> None:
    codes = upsert_stock_universe(
        session,
        [make_row("600519", "贵州茅台", 18800), make_row("000001", "平安银行", 2000)],
        limit=1,
    )
    assert codes == ["600519"]
    assert session.get(StockMetric, "600519") is not None
    assert session.get(StockMetric, "000001") is None


def test_sync_dividends_and_yield(session, monkeypatch) -> None:
    upsert_stock_universe(session, [make_row("600519", "贵州茅台", 18800)])
    records = [
        DividendRecord("600519", "贵州茅台", date(2026, 6, 26), 2025, 28.02423, "10派280", False),
        DividendRecord("600519", "贵州茅台", date(2025, 12, 19), 2025, 23.957, "10派239", False),
    ]
    monkeypatch.setattr("etl.stocks.fetch_dividends", lambda code: records)

    result = sync_stock_dividends(session, ["600519"], delay=0)
    assert result["written"] == 2
    assert session.query(StockDividend).count() == 2

    metric = session.get(StockMetric, "600519")
    metric.price = 1000
    session.commit()

    refreshed = refresh_stock_metrics(session, ["600519"], as_of=date(2026, 10, 20))
    assert refreshed == 1
    metric = session.get(StockMetric, "600519")
    assert float(metric.dividend_yield_ttm) == 5.2
    assert metric.last_ex_date == date(2026, 6, 26)


def test_pilot_pipeline(session, monkeypatch) -> None:
    rows = [make_row("600519", "贵州茅台", 18800), make_row("601398", "工商银行", 20000)]
    monkeypatch.setattr("etl.stocks.fetch_stock_universe", lambda: (2, rows))
    monkeypatch.setattr("etl.stocks.fetch_dividends", lambda code: [])
    result = sync_stock_pilot(session, limit=2, dividend_limit=2, delay=0)
    assert result["stored"] == 2
    assert result["metrics"] == 2
    assert session.query(StockMetric).count() == 2
