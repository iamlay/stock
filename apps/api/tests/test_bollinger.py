from datetime import date, timedelta
from math import sin

from app.services.bollinger import compute_bollinger


def _bars(count: int) -> list[tuple[date, float]]:
    start = date(2024, 1, 2)
    return [
        (start + timedelta(days=index), 10 + index * 0.01 + sin(index / 5))
        for index in range(count)
    ]


def test_compute_bollinger_has_daily_weekly_monthly() -> None:
    result = compute_bollinger(_bars(800))

    assert result["daily"] is not None
    assert result["weekly"] is not None
    assert result["monthly"] is not None
    assert result["daily"].periods == 20
    assert result["rating"] in {"回踩", "偏热", "高位", "观望"}


def test_compute_bollinger_requires_enough_bars() -> None:
    result = compute_bollinger(_bars(10))

    assert result["daily"] is None
    assert result["weekly"] is None
    assert result["monthly"] is None
    assert result["rating"] == "数据不足"
