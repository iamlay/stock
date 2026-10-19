from __future__ import annotations

import math
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import MarketDaily


@dataclass(frozen=True)
class BarPoint:
    trade_date: date
    close: float
    amount: float | None = None


@dataclass(frozen=True)
class Indicators:
    last_close: float
    change_pct: float
    ma5: float | None
    ma20: float | None
    ma60: float | None
    volatility_20d: float | None
    max_drawdown_1y: float | None
    high_52w: float | None
    low_52w: float | None
    return_1m: float | None
    return_3m: float | None
    return_1y: float | None
    last_amount: float | None


def load_recent_closes(
    session: Session, codes: list[str], limit: int = 260
) -> dict[str, list[BarPoint]]:
    """Load the most recent N bars per code with one window-function query."""
    if not codes:
        return {}

    ranked = (
        select(
            MarketDaily.code,
            MarketDaily.trade_date,
            MarketDaily.close,
            MarketDaily.amount,
            func.row_number()
            .over(partition_by=MarketDaily.code, order_by=MarketDaily.trade_date.desc())
            .label("rn"),
        )
        .where(MarketDaily.code.in_(codes))
        .subquery()
    )
    rows = session.execute(select(ranked).where(ranked.c.rn <= limit)).all()

    grouped: dict[str, list[BarPoint]] = defaultdict(list)
    for row in rows:
        grouped[row.code].append(
            BarPoint(
                trade_date=row.trade_date,
                close=float(row.close),
                amount=float(row.amount) if row.amount is not None else None,
            )
        )
    for points in grouped.values():
        points.sort(key=lambda point: point.trade_date)
    return dict(grouped)


def _sma(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return round(sum(values[-window:]) / window, 4)


def _period_return(values: list[float], window: int) -> float | None:
    if len(values) <= window:
        return None
    base = values[-window - 1]
    if base <= 0:
        return None
    return round((values[-1] / base - 1) * 100, 2)


def _annualized_volatility(values: list[float], window: int = 20) -> float | None:
    if len(values) <= window:
        return None
    returns = [
        values[index] / values[index - 1] - 1
        for index in range(len(values) - window, len(values))
        if values[index - 1] > 0
    ]
    if len(returns) < 2:
        return None
    return round(statistics.stdev(returns) * math.sqrt(252) * 100, 2)


def _max_drawdown(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    peak = values[0]
    worst = 0.0
    for value in values:
        peak = max(peak, value)
        if peak > 0:
            worst = min(worst, value / peak - 1)
    return round(worst * 100, 2)


def compute_indicators(points: list[BarPoint]) -> Indicators | None:
    if len(points) < 2:
        return None

    closes = [point.close for point in points]
    window = closes[-250:]
    return Indicators(
        last_close=round(closes[-1], 4),
        change_pct=round((closes[-1] / closes[-2] - 1) * 100, 2) if closes[-2] else 0.0,
        ma5=_sma(closes, 5),
        ma20=_sma(closes, 20),
        ma60=_sma(closes, 60),
        volatility_20d=_annualized_volatility(closes),
        max_drawdown_1y=_max_drawdown(window),
        high_52w=round(max(window), 4) if len(window) >= 2 else None,
        low_52w=round(min(window), 4) if len(window) >= 2 else None,
        return_1m=_period_return(closes, 20),
        return_3m=_period_return(closes, 60),
        return_1y=_period_return(closes, 250),
        last_amount=points[-1].amount,
    )
