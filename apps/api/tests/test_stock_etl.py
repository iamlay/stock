from datetime import date

from etl.sources.eastmoney_stock import DividendRecord
from etl.sources.industry import CompanyIndustry
from etl.sources.sina_stock import SinaStockRow
from etl.sources.tencent import DailyBar, DailySeries
from etl.stocks import (
    enrich_stock_industries,
    enrich_stock_industry_details,
    refresh_stock_metrics,
    sync_stock_bars_batch,
    sync_stock_daily,
    sync_stock_dividends,
    sync_stock_dividends_bulk,
    sync_stock_pilot,
    upsert_stock_universe,
)

from app.db.models import MarketDaily, StockDividend, StockMetric, StockProfile


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


def test_sync_dividends_handles_same_year_same_plan(session, monkeypatch) -> None:
    upsert_stock_universe(session, [make_row("601877", "正泰电器", 500)])
    records = [
        DividendRecord(
            "601877",
            "正泰电器",
            date(2017, 6, 21),
            2016,
            0.3,
            "10派3.00元(含税,扣税后2.70元)",
            False,
            notice_date=date(2017, 6, 15),
            report_date=date(2016, 12, 31),
        ),
        DividendRecord(
            "601877",
            "正泰电器",
            date(2016, 9, 14),
            2016,
            0.3,
            "10派3.00元(含税,扣税后2.70元)",
            False,
            notice_date=date(2016, 9, 8),
            report_date=date(2016, 6, 30),
        ),
    ]
    monkeypatch.setattr("etl.stocks.fetch_dividends", lambda code: records)

    first = sync_stock_dividends(session, ["601877"], delay=0)
    assert first["written"] == 2
    assert session.query(StockDividend).count() == 2

    second = sync_stock_dividends(session, ["601877"], delay=0)
    assert second["written"] == 0
    assert session.query(StockDividend).count() == 2


def test_pilot_pipeline(session, monkeypatch) -> None:
    rows = [make_row("600519", "贵州茅台", 18800), make_row("601398", "工商银行", 20000)]
    monkeypatch.setattr("etl.stocks.fetch_stock_universe", lambda: (2, rows))
    monkeypatch.setattr("etl.stocks.fetch_dividends", lambda code: [])
    result = sync_stock_pilot(session, limit=2, dividend_limit=2, delay=0)
    assert result["stored"] == 2
    assert result["metrics"] == 2
    assert session.query(StockMetric).count() == 2


def test_enrich_industry_prefers_eastmoney(session, monkeypatch) -> None:
    upsert_stock_universe(session, [make_row("600519", "贵州茅台", 18800)])
    monkeypatch.setattr(
        "etl.stocks.fetch_sina_industry_map",
        lambda: ([], {"600519": "酿酒行业"}),
    )
    monkeypatch.setattr(
        "etl.stocks.fetch_eastmoney_industry",
        lambda code: CompanyIndustry(
            code=code,
            name="贵州茅台",
            eastmoney_industry="食品饮料-饮料-白酒",
            csrc_industry="制造业-酒",
            board="上交所主板A股",
            listing_date="2001-08-27",
        ),
    )
    result = enrich_stock_industries(session, limit=1, delay=0)
    profile = session.get(StockProfile, "600519")
    assert result["eastmoney"] == 1
    assert profile.industry == "食品饮料"
    assert profile.industry_path == "食品饮料-饮料-白酒"
    assert profile.industry_source == "eastmoney"
    assert profile.list_date == date(2001, 8, 27)


def test_daily_only_updates_existing_stocks(session, monkeypatch) -> None:
    upsert_stock_universe(session, [make_row("600519", "贵州茅台", 18800)])
    rows = [
        make_row("600519", "贵州茅台", 19000),
        make_row("000001", "平安银行", 2000),
    ]
    monkeypatch.setattr("etl.stocks.fetch_stock_universe", lambda: (2, rows))

    result = sync_stock_daily(session, include_dividends=False)
    assert result["matched"] == 1
    assert result["metrics"] == 1
    assert session.get(StockProfile, "000001") is None
    metric = session.get(StockMetric, "600519")
    assert float(metric.market_cap) == 19000


def test_bulk_dividends_only_keeps_known_codes(session, monkeypatch) -> None:
    upsert_stock_universe(
        session,
        [make_row("600519", "贵州茅台", 18800), make_row("000001", "平安银行", 2000)],
    )
    records = [
        DividendRecord("600519", "贵州茅台", date(2026, 6, 26), 2025, 28.0, "10派280", False),
        DividendRecord("999999", "未知", date(2026, 6, 26), 2025, 1.0, "10派10", False),
    ]
    monkeypatch.setattr("etl.stocks.fetch_dividends_bulk", lambda since: records)

    result = sync_stock_dividends_bulk(session, days=730)
    assert result["codes"] == 2
    assert result["written"] == 1
    assert session.query(StockDividend).count() == 1


def test_metrics_mark_one_off_dividend(session, monkeypatch) -> None:
    upsert_stock_universe(session, [make_row("600519", "贵州茅台", 18800)])
    metric = session.get(StockMetric, "600519")
    metric.price = 10
    session.commit()
    records = [
        DividendRecord("600519", "贵州茅台", date(2025, 6, 26), 2024, 0.2, "", False),
        DividendRecord("600519", "贵州茅台", date(2026, 6, 26), 2025, 1.0, "", False),
    ]
    monkeypatch.setattr("etl.stocks.fetch_dividends", lambda code: records)
    sync_stock_dividends(session, ["600519"], delay=0)

    refresh_stock_metrics(session, ["600519"], as_of=date(2026, 10, 21))
    metric = session.get(StockMetric, "600519")
    assert metric.sustainability == "one_off"
    latest = session.query(StockDividend).order_by(StockDividend.ex_date.desc()).first()
    assert latest.is_one_off is True


def test_bars_batch_caches_ohlcv(session, monkeypatch) -> None:
    upsert_stock_universe(session, [make_row("600519", "贵州茅台", 18800)])
    series = DailySeries(
        code="600519",
        name="贵州茅台",
        bars=[
            DailyBar(date(2026, 10, 19), 10, 11, 9, 10.5, 1000, 0, 0),
            DailyBar(date(2026, 10, 20), 10.5, 12, 10, 11.5, 1200, 0, 0),
        ],
    )
    monkeypatch.setattr("etl.stocks.fetch_daily_tencent", lambda code, start, end: series)

    result = sync_stock_bars_batch(session, limit=1, delay=0)
    assert result["selected"] == 1
    assert result["updated"] == 1
    assert result["skipped"] == 0
    assert session.query(MarketDaily).filter_by(code="600519").count() == 2


def test_industry_detail_preserves_sw1_level(session, monkeypatch) -> None:
    upsert_stock_universe(session, [make_row("600519", "贵州茅台", 18800)])
    profile = session.get(StockProfile, "600519")
    profile.industry = "食品饮料"
    profile.industry_path = "食品饮料"
    metric = session.get(StockMetric, "600519")
    metric.dividend_yield_ttm = 5
    session.commit()
    monkeypatch.setattr(
        "etl.stocks.fetch_eastmoney_industry",
        lambda code: CompanyIndustry(
            code=code,
            name="贵州茅台",
            eastmoney_industry="食品饮料-饮料-白酒",
            csrc_industry="制造业-酒",
            board="上交所主板A股",
            listing_date="2001-08-27",
        ),
    )

    result = enrich_stock_industry_details(session, limit=1, delay=0)
    profile = session.get(StockProfile, "600519")
    assert result["updated"] == 1
    assert profile.industry == "食品饮料"
    assert profile.industry_path == "食品饮料-饮料-白酒"
