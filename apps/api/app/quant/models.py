from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(frozen=True)
class Bar:
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    prev_close: float | None = None
    volume: int = 0


@dataclass
class Trade:
    trade_date: date
    side: str  # buy | sell
    price: float
    shares: int
    amount: float
    fee: float
    reason: str
    realized_pnl: float | None = None


@dataclass
class EquityPoint:
    trade_date: date
    equity: float
    cash: float
    position_value: float
    shares: int
    benchmark: float


@dataclass
class Metrics:
    total_return: float
    annualized_return: float
    max_drawdown: float
    volatility: float
    sharpe: float
    exposure: float
    trades: int
    win_rate: float | None
    benchmark_return: float
    final_equity: float


@dataclass
class BacktestConfig:
    initial_cash: float = 100_000.0
    commission_rate: float = 0.0002
    min_commission: float = 5.0
    slippage_bps: float = 2.0
    lot_size: int = 100
    limit_pct: float = 0.10
    annual_trading_days: int = 252
    min_trade_ratio: float = 0.005


@dataclass
class BacktestResult:
    code: str
    strategy: str
    params: dict[str, Any]
    start: date | None
    end: date | None
    metrics: Metrics
    equity: list[EquityPoint] = field(default_factory=list)
    trades: list[Trade] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
