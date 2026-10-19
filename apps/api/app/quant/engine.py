from __future__ import annotations

import math
import statistics
from dataclasses import replace

from app.quant.models import (
    BacktestConfig,
    BacktestResult,
    Bar,
    EquityPoint,
    Metrics,
    Trade,
)
from app.quant.strategies import StrategySpec, resolve_params


def _is_suspended(bar: Bar) -> bool:
    return bar.open <= 0 or bar.volume <= 0


def _limit_hit(bar: Bar, previous_close: float, limit_pct: float) -> tuple[bool, bool]:
    if previous_close <= 0:
        return False, False
    limit_up = bar.open >= previous_close * (1 + limit_pct) - 1e-9
    limit_down = bar.open <= previous_close * (1 - limit_pct) + 1e-9
    return limit_up, limit_down


def _commission(amount: float, config: BacktestConfig) -> float:
    return max(amount * config.commission_rate, config.min_commission)


def _execute(
    bar: Bar,
    weight: float,
    cash: float,
    shares: int,
    average_cost: float,
    config: BacktestConfig,
    previous_close: float,
    reason: str,
) -> tuple[float, int, float, Trade | None, str | None]:
    """Execute a target weight at the bar open. Returns unchanged state if skipped."""
    if _is_suspended(bar):
        return cash, shares, average_cost, None, "suspended"

    limit_up, limit_down = _limit_hit(bar, previous_close, config.limit_pct)
    equity = cash + shares * bar.open
    target_value = equity * max(0.0, min(1.0, weight))

    if weight > 0:
        price = bar.open * (1 + config.slippage_bps / 10_000)
    else:
        price = bar.open * (1 - config.slippage_bps / 10_000)

    target_shares = int(target_value / (price * config.lot_size)) * config.lot_size
    delta = target_shares - shares

    # Avoid churn from tiny sizing differences (fees, lot rounding).
    if weight > 0 and abs(delta) * price < max(100.0, equity * config.min_trade_ratio):
        return cash, shares, average_cost, None, None

    if delta > 0:
        if limit_up:
            return cash, shares, average_cost, None, "limit_up"
        max_shares = int(
            cash / (price * (1 + config.commission_rate)) / config.lot_size
        ) * config.lot_size
        quantity = min(delta, max_shares)
        while quantity > 0:
            amount = quantity * price
            fee = _commission(amount, config)
            if amount + fee <= cash:
                break
            quantity -= config.lot_size
        if quantity <= 0:
            return cash, shares, average_cost, None, "insufficient_cash"

        amount = quantity * price
        fee = _commission(amount, config)
        cash -= amount + fee
        new_shares = shares + quantity
        average_cost = (average_cost * shares + amount + fee) / new_shares if new_shares else 0.0
        trade = Trade(
            trade_date=bar.trade_date,
            side="buy",
            price=round(price, 4),
            shares=quantity,
            amount=round(amount, 2),
            fee=round(fee, 2),
            reason=reason,
        )
        return cash, new_shares, average_cost, trade, None

    if delta < 0:
        if limit_down:
            return cash, shares, average_cost, None, "limit_down"
        quantity = min(-delta, shares)
        if quantity <= 0:
            return cash, shares, average_cost, None, None
        amount = quantity * price
        fee = _commission(amount, config)
        cash += amount - fee
        realized = (price - average_cost) * quantity - fee
        new_shares = shares - quantity
        trade = Trade(
            trade_date=bar.trade_date,
            side="sell",
            price=round(price, 4),
            shares=quantity,
            amount=round(amount, 2),
            fee=round(fee, 2),
            reason=reason,
            realized_pnl=round(realized, 2),
        )
        return cash, new_shares, (average_cost if new_shares else 0.0), trade, None

    return cash, shares, average_cost, None, None


def _metrics(
    equity: list[EquityPoint], trades: list[Trade], config: BacktestConfig
) -> Metrics:
    first = equity[0].equity
    last = equity[-1].equity
    total_return = last / first - 1 if first else 0.0
    years = len(equity) / config.annual_trading_days
    annualized = (1 + total_return) ** (1 / years) - 1 if years > 0 and total_return > -1 else -1.0

    peak = equity[0].equity
    max_drawdown = 0.0
    for point in equity:
        peak = max(peak, point.equity)
        if peak > 0:
            max_drawdown = min(max_drawdown, point.equity / peak - 1)

    returns = [
        equity[index].equity / equity[index - 1].equity - 1
        for index in range(1, len(equity))
        if equity[index - 1].equity > 0
    ]
    volatility = (
        statistics.stdev(returns) * math.sqrt(config.annual_trading_days)
        if len(returns) > 1
        else 0.0
    )
    sharpe = (
        statistics.mean(returns) / statistics.stdev(returns) * math.sqrt(config.annual_trading_days)
        if len(returns) > 1 and statistics.stdev(returns) > 0
        else 0.0
    )

    sells = [trade for trade in trades if trade.side == "sell" and trade.realized_pnl is not None]
    wins = [trade for trade in sells if (trade.realized_pnl or 0) > 0]
    win_rate = len(wins) / len(sells) if sells else None
    exposure = sum(1 for point in equity if point.shares > 0) / len(equity) if equity else 0.0

    return Metrics(
        total_return=round(total_return * 100, 2),
        annualized_return=round(annualized * 100, 2),
        max_drawdown=round(max_drawdown * 100, 2),
        volatility=round(volatility * 100, 2),
        sharpe=round(sharpe, 2),
        exposure=round(exposure * 100, 2),
        trades=len(trades),
        win_rate=round(win_rate * 100, 2) if win_rate is not None else None,
        benchmark_return=round((equity[-1].benchmark / equity[0].benchmark - 1) * 100, 2),
        final_equity=round(last, 2),
    )


def run_backtest(
    bars: list[Bar],
    spec: StrategySpec,
    params: dict | None = None,
    config: BacktestConfig | None = None,
) -> BacktestResult:
    if len(bars) < 2:
        raise ValueError("not enough bars to run a backtest")

    config = config or BacktestConfig()
    resolved = resolve_params(spec.slug, params)

    cash = config.initial_cash
    shares = 0
    average_cost = 0.0
    pending: float | None = None
    trades: list[Trade] = []
    equity: list[EquityPoint] = []
    warnings: list[str] = []

    equity.append(
        EquityPoint(
            trade_date=bars[0].trade_date,
            equity=cash,
            cash=cash,
            position_value=0.0,
            shares=0,
            benchmark=config.initial_cash,
        )
    )

    initial_target = spec.target(bars[:1], resolved)
    pending = (
        max(0.0, min(1.0, float(initial_target))) if initial_target is not None else None
    )

    for index in range(1, len(bars)):
        bar = bars[index]
        previous_close = bar.prev_close or bars[index - 1].close

        if pending is not None:
            cash, shares, average_cost, trade, skip_reason = _execute(
                bar,
                pending,
                cash,
                shares,
                average_cost,
                config,
                previous_close,
                f"target={pending:.0%}",
            )
            if trade is not None:
                trades.append(trade)
            if skip_reason and skip_reason not in {"insufficient_cash"}:
                warnings.append(f"{bar.trade_date} skip {skip_reason}")
            if trade is not None or skip_reason in {None, "insufficient_cash"}:
                pending = None

        target = spec.target(bars[: index + 1], resolved)
        if target is not None:
            pending = max(0.0, min(1.0, float(target)))

        position_value = shares * bar.close
        equity.append(
            EquityPoint(
                trade_date=bar.trade_date,
                equity=cash + position_value,
                cash=cash,
                position_value=position_value,
                shares=shares,
                benchmark=config.initial_cash * (bar.close / bars[0].close),
            )
        )

    return BacktestResult(
        code="",
        strategy=spec.slug,
        params=resolved,
        start=bars[0].trade_date,
        end=bars[-1].trade_date,
        metrics=_metrics(equity, trades, config),
        equity=equity,
        trades=trades,
        warnings=warnings[:20],
    )


def with_code(result: BacktestResult, code: str) -> BacktestResult:
    return replace(result, code=code)
