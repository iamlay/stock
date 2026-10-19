from datetime import date, timedelta

from app.quant.engine import run_backtest
from app.quant.models import BacktestConfig, Bar
from app.quant.strategies import get_strategy


def make_bar(day: int, open_price: float, close_price: float, prev: float | None = None) -> Bar:
    return Bar(
        trade_date=date(2024, 1, day),
        open=open_price,
        high=max(open_price, close_price),
        low=min(open_price, close_price),
        close=close_price,
        prev_close=prev,
        volume=1_000_000,
    )


CONFIG = BacktestConfig(
    initial_cash=100_000,
    commission_rate=0,
    min_commission=0,
    slippage_bps=0,
)


def test_buy_and_hold_executes_next_open() -> None:
    bars = [
        make_bar(2, 10.0, 10.0),
        make_bar(3, 10.5, 11.0, prev=10.0),
        make_bar(4, 11.0, 12.0, prev=11.0),
    ]
    result = run_backtest(bars, get_strategy("buy-and-hold"), config=CONFIG)

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.trade_date == date(2024, 1, 3)  # signal at day 2 close, fill next open
    assert trade.side == "buy"
    assert trade.shares == 9_500
    assert result.metrics.total_return > 0


def test_limit_up_skips_then_fills_next_day() -> None:
    bars = [
        make_bar(2, 10.0, 10.0),
        make_bar(3, 11.0, 11.0, prev=10.0),  # +10% limit up
        make_bar(4, 11.0, 12.0, prev=11.0),
    ]
    result = run_backtest(bars, get_strategy("buy-and-hold"), config=CONFIG)

    assert len(result.trades) == 1
    assert result.trades[0].trade_date == date(2024, 1, 4)
    assert any("limit_up" in warning for warning in result.warnings)


def test_commission_and_slippage_are_charged() -> None:
    bars = [
        make_bar(2, 10.0, 10.0),
        make_bar(3, 10.0, 10.0, prev=10.0),
    ]
    config = BacktestConfig(
        initial_cash=100_000,
        commission_rate=0.001,
        min_commission=5,
        slippage_bps=10,
    )
    result = run_backtest(bars, get_strategy("buy-and-hold"), config=config)

    trade = result.trades[0]
    assert trade.price == 10.01
    assert trade.fee > 5
    assert result.metrics.final_equity < 100_000


def test_dual_ma_generates_round_trip() -> None:
    closes = [10 + index * 0.2 for index in range(40)] + [
        18 - index * 0.3 for index in range(40)
    ]
    bars = []
    for index, close in enumerate(closes):
        previous = closes[index - 1] if index else None
        bars.append(
            Bar(
                trade_date=date(2024, 1, 1) + timedelta(days=index),
                open=close,
                high=close,
                low=close,
                close=close,
                prev_close=previous,
                volume=1_000_000,
            )
        )

    result = run_backtest(
        bars,
        get_strategy("dual-ma"),
        params={"fast": 5, "slow": 15},
        config=CONFIG,
    )

    assert any(trade.side == "buy" for trade in result.trades)
    assert any(trade.side == "sell" for trade in result.trades)
    assert result.metrics.max_drawdown <= 0


def test_max_drawdown_is_negative() -> None:
    bars = [
        make_bar(2, 10.0, 10.0),
        make_bar(3, 10.0, 9.0, prev=10.0),
        make_bar(4, 9.0, 8.0, prev=9.0),
    ]
    result = run_backtest(bars, get_strategy("buy-and-hold"), config=CONFIG)
    assert result.metrics.max_drawdown < 0


def test_unknown_strategy_raises() -> None:
    bars = [make_bar(2, 10.0, 10.0), make_bar(3, 10.0, 10.0, prev=10.0)]
    try:
        run_backtest(bars, get_strategy("nope"), config=CONFIG)
    except ValueError as exc:
        assert "unknown strategy" in str(exc)
    else:
        raise AssertionError("expected ValueError")
