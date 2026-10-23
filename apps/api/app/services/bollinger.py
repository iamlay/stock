from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import sqrt


@dataclass(frozen=True)
class Band:
    position: str
    close: float
    mid: float
    upper: float
    lower: float
    percent_b: float
    periods: int


def _band(closes: list[float], *, period: int = 20) -> Band | None:
    if len(closes) < period:
        return None

    window = closes[-period:]
    mid = sum(window) / period
    variance = sum((value - mid) ** 2 for value in window) / period
    std = sqrt(variance)
    upper = mid + 2 * std
    lower = mid - 2 * std
    close = closes[-1]

    if close >= upper:
        position = "上轨上方"
    elif close >= mid:
        position = "中上"
    elif close >= lower:
        position = "中下"
    else:
        position = "下轨下方"

    width = upper - lower
    percent_b = ((close - lower) / width * 100) if width > 0 else 50.0

    return Band(
        position=position,
        close=round(close, 3),
        mid=round(mid, 3),
        upper=round(upper, 3),
        lower=round(lower, 3),
        percent_b=round(percent_b, 1),
        periods=period,
    )


def _period_closes(
    bars: list[tuple[date, float]],
    *,
    kind: str,
) -> list[float]:
    grouped: dict[tuple[int, int], float] = {}
    for trade_date, close in bars:
        if kind == "week":
            iso = trade_date.isocalendar()
            key = (iso.year, iso.week)
        else:
            key = (trade_date.year, trade_date.month)
        grouped[key] = float(close)
    return [grouped[key] for key in sorted(grouped)]


def _rating(daily: Band | None, weekly: Band | None, monthly: Band | None) -> str:
    if daily is None:
        return "数据不足"

    weak_daily = daily.position in {"下轨下方", "中下"}
    weak_weekly = weekly is not None and weekly.position in {"下轨下方", "中下"}
    hot_daily = daily.position in {"上轨上方", "中上"}
    hot_weekly = weekly is not None and weekly.position in {"上轨上方", "中上"}

    if weak_daily and (weekly is None or weak_weekly):
        return "回踩"
    if hot_daily and (weekly is None or hot_weekly):
        return "偏热"
    if monthly is not None and monthly.position == "上轨上方":
        return "高位"
    return "观望"


def compute_bollinger(bars: list[tuple[date, float]]) -> dict:
    ordered = sorted(bars, key=lambda item: item[0])
    closes = [float(close) for _, close in ordered]
    daily = _band(closes)
    weekly = _band(_period_closes(ordered, kind="week"))
    monthly = _band(_period_closes(ordered, kind="month"))
    return {
        "daily": daily,
        "weekly": weekly,
        "monthly": monthly,
        "rating": _rating(daily, weekly, monthly),
    }
