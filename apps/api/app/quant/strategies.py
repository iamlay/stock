from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.quant.indicators import bollinger, macd, rsi, sma
from app.quant.models import Bar


@dataclass(frozen=True)
class StrategySpec:
    slug: str
    name: str
    description: str
    defaults: dict[str, float | int]
    target: Callable[[list[Bar], dict[str, Any]], float | None]
    param_schema: dict[str, dict[str, Any]] = field(default_factory=dict)
    no_sell: bool = False


def _closes(bars: list[Bar]) -> list[float]:
    return [bar.close for bar in bars]


def _buy_and_hold(bars: list[Bar], params: dict[str, Any]) -> float | None:
    return 1.0


def _dual_ma(bars: list[Bar], params: dict[str, Any]) -> float | None:
    closes = _closes(bars)
    fast = sma(closes, int(params["fast"]))
    slow = sma(closes, int(params["slow"]))
    if fast is None or slow is None:
        return None
    return 1.0 if fast > slow else 0.0


def _rsi_strategy(bars: list[Bar], params: dict[str, Any]) -> float | None:
    closes = _closes(bars)
    value = rsi(closes, int(params["period"]))
    if value is None:
        return None
    if value < float(params["oversold"]):
        return 1.0
    if value > float(params["overbought"]):
        return 0.0
    return None


def _bollinger_strategy(bars: list[Bar], params: dict[str, Any]) -> float | None:
    closes = _closes(bars)
    bands = bollinger(closes, int(params["period"]), float(params["width"]))
    if bands is None:
        return None
    lower, middle, _ = bands
    if closes[-1] < lower:
        return 1.0
    if closes[-1] > middle:
        return 0.0
    return None


def _macd_strategy(bars: list[Bar], params: dict[str, Any]) -> float | None:
    closes = _closes(bars)
    values = macd(
        closes,
        int(params["fast"]),
        int(params["slow"]),
        int(params["signal"]),
    )
    if values is None:
        return None
    dif, dea, _ = values
    return 1.0 if dif > dea else 0.0


def _deviation(bars: list[Bar], params: dict[str, Any]) -> float | None:
    closes = _closes(bars)
    average = sma(closes, int(params["window"]))
    if average is None or average <= 0:
        return None
    step = float(params["step"])
    ratio = closes[-1] / average
    weight = 0.5 - (ratio - 1) / step * 0.5
    return max(0.0, min(1.0, weight))


def _monthly_dca(bars: list[Bar], params: dict[str, Any]) -> float | None:
    """Invest 1/N of capital on the first trading day of each month, never sell."""
    if not bars:
        return None
    months = int(params["months"])
    first = bars[0].trade_date
    current = bars[-1].trade_date

    if len(bars) > 1:
        previous = bars[-2].trade_date
        if current.year == previous.year and current.month == previous.month:
            return None

    elapsed = (current.year - first.year) * 12 + (current.month - first.month) + 1
    return min(1.0, elapsed / months)


def _grid(bars: list[Bar], params: dict[str, Any]) -> float | None:
    """Ladder between the rolling low and high: lower price -> higher target weight."""
    window = int(params["window"])
    levels = int(params["levels"])
    if len(bars) < window:
        return None

    recent = bars[-window:]
    high = max(bar.high for bar in recent)
    low = min(bar.low for bar in recent)
    if high <= low:
        return None

    position = (high - bars[-1].close) / (high - low)
    weight = math.floor(max(0.0, min(1.0, position)) * levels) / levels
    return max(0.0, min(1.0, weight))


STRATEGIES: dict[str, StrategySpec] = {
    "buy-and-hold": StrategySpec(
        slug="buy-and-hold",
        name="买入持有",
        description="回测起点全仓买入，之后不再交易，作为其他策略的基准。",
        defaults={},
        target=_buy_and_hold,
    ),
    "dual-ma": StrategySpec(
        slug="dual-ma",
        name="双均线",
        description="快线上穿慢线买入，下穿卖出，全仓进出。",
        defaults={"fast": 20, "slow": 60},
        target=_dual_ma,
        param_schema={
            "fast": {"type": "integer", "min": 2, "max": 120, "default": 20},
            "slow": {"type": "integer", "min": 5, "max": 250, "default": 60},
        },
    ),
    "rsi": StrategySpec(
        slug="rsi",
        name="RSI 超买超卖",
        description="RSI 低于超卖线买入，高于超买线卖出，中间区间保持仓位。",
        defaults={"period": 14, "oversold": 30, "overbought": 70},
        target=_rsi_strategy,
        param_schema={
            "period": {"type": "integer", "min": 5, "max": 60, "default": 14},
            "oversold": {"type": "number", "min": 5, "max": 45, "default": 30},
            "overbought": {"type": "number", "min": 55, "max": 95, "default": 70},
        },
    ),
    "bollinger": StrategySpec(
        slug="bollinger",
        name="布林带",
        description="收盘跌破下轨买入，回到中轨上方卖出。",
        defaults={"period": 20, "width": 2.0},
        target=_bollinger_strategy,
        param_schema={
            "period": {"type": "integer", "min": 5, "max": 120, "default": 20},
            "width": {"type": "number", "min": 1.0, "max": 4.0, "default": 2.0},
        },
    ),
    "macd": StrategySpec(
        slug="macd",
        name="MACD",
        description="DIF 上穿 DEA 买入，下穿卖出。",
        defaults={"fast": 12, "slow": 26, "signal": 9},
        target=_macd_strategy,
        param_schema={
            "fast": {"type": "integer", "min": 2, "max": 60, "default": 12},
            "slow": {"type": "integer", "min": 5, "max": 120, "default": 26},
            "signal": {"type": "integer", "min": 2, "max": 60, "default": 9},
        },
    ),
    "deviation": StrategySpec(
        slug="deviation",
        name="偏离度调仓",
        description="价格低于均线越多，目标仓位越高；只调整差额，允许长期半仓。",
        defaults={"window": 60, "step": 0.08},
        target=_deviation,
        param_schema={
            "window": {"type": "integer", "min": 5, "max": 250, "default": 60},
            "step": {"type": "number", "min": 0.01, "max": 0.5, "default": 0.08},
        },
    ),
    "monthly-dca": StrategySpec(
        slug="monthly-dca",
        name="每月定投",
        description="把初始资金分成 N 份，每月首个交易日买入一份，只买不卖。",
        defaults={"months": 24},
        target=_monthly_dca,
        param_schema={
            "months": {"type": "integer", "min": 6, "max": 120, "default": 24},
        },
        no_sell=True,
    ),
    "grid": StrategySpec(
        slug="grid",
        name="滚动网格",
        description="在滚动窗口高低点之间等分网格，价格越低目标仓位越高，越高越减。",
        defaults={"window": 250, "levels": 10},
        target=_grid,
        param_schema={
            "window": {"type": "integer", "min": 20, "max": 750, "default": 250},
            "levels": {"type": "integer", "min": 3, "max": 30, "default": 10},
        },
    ),
}


def get_strategy(slug: str) -> StrategySpec:
    try:
        return STRATEGIES[slug]
    except KeyError as exc:
        raise ValueError(f"unknown strategy: {slug}") from exc


def list_strategies() -> list[dict[str, Any]]:
    return [
        {
            "slug": spec.slug,
            "name": spec.name,
            "description": spec.description,
            "defaults": spec.defaults,
            "params": spec.param_schema,
        }
        for spec in STRATEGIES.values()
    ]


def resolve_params(slug: str, params: dict[str, Any] | None) -> dict[str, Any]:
    spec = get_strategy(slug)
    merged = {**spec.defaults, **(params or {})}
    for key, rule in spec.param_schema.items():
        if key not in merged:
            continue
        value = merged[key]
        if not isinstance(value, (int, float)):
            raise ValueError(f"parameter {key} must be numeric")
        if "min" in rule and value < rule["min"]:
            raise ValueError(f"parameter {key} below minimum")
        if "max" in rule and value > rule["max"]:
            raise ValueError(f"parameter {key} above maximum")
    return merged
