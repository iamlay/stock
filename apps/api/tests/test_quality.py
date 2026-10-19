from datetime import date

from etl.quality import check_series, expected_latest_trading_day
from etl.sources.eastmoney import DailyBar, DailySeries


def bar(day: str, close: float = 1.0) -> DailyBar:
    return DailyBar(
        trade_date=date.fromisoformat(day),
        open=1.0,
        high=max(1.0, close),
        low=min(1.0, close),
        close=close,
        volume=1000,
        amount=1000.0,
        amplitude=1.0,
    )


def status_of(results: list, name: str) -> str:
    return next(item.status for item in results if item.name == name)


def test_valid_series_passes() -> None:
    series = DailySeries(
        code="510300",
        name="沪深300ETF",
        bars=[bar("2024-01-02"), bar("2024-01-03")],
    )
    results = check_series(series, min_rows=1)
    assert all(item.status == "pass" for item in results)


def test_invalid_ohlc_fails() -> None:
    bad = DailyBar(
        trade_date=date(2024, 1, 2),
        open=1.0,
        high=0.9,
        low=1.1,
        close=1.0,
        volume=100,
        amount=100.0,
        amplitude=0.0,
    )
    series = DailySeries(code="510300", name="x", bars=[bad])
    results = check_series(series, min_rows=1)
    assert status_of(results, "ohlc_bounds") == "fail"


def test_duplicate_dates_fail() -> None:
    series = DailySeries(
        code="510300",
        name="x",
        bars=[bar("2024-01-02"), bar("2024-01-02")],
    )
    results = check_series(series, min_rows=1)
    assert status_of(results, "unique_dates") == "fail"


def test_short_series_warns() -> None:
    series = DailySeries(code="510300", name="x", bars=[bar("2024-01-02")])
    results = check_series(series, min_rows=250)
    assert status_of(results, "row_count") == "warn"


def test_expected_latest_skips_weekend() -> None:
    assert expected_latest_trading_day(date(2026, 10, 18)).isoformat() == "2026-10-16"
