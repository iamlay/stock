from datetime import date, timedelta

from etl.stocks import compute_yield_percentile


def _weekly_bars(count: int) -> list[tuple[date, float]]:
    start = date(2020, 1, 3)
    return [(start + timedelta(days=index * 7), 10.0 + index * 0.01) for index in range(count)]


def test_yield_percentile_requires_enough_history() -> None:
    assert compute_yield_percentile(_weekly_bars(20), [], 5.0) is None


def test_yield_percentile_returns_bounded_value() -> None:
    dividends = [(date(2020, 1, 1), 0.5)]
    result = compute_yield_percentile(_weekly_bars(80), dividends, 5.0)
    assert result is not None
    assert 0 <= result <= 100
