from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import MarketDaily
from app.quant.engine import run_backtest, with_code
from app.quant.models import BacktestConfig, BacktestResult, Bar
from app.quant.strategies import get_strategy


def load_bars(
    session: Session,
    code: str,
    start: date | None = None,
    end: date | None = None,
) -> list[Bar]:
    statement = select(MarketDaily).where(MarketDaily.code == code)
    if start is not None:
        statement = statement.where(MarketDaily.trade_date >= start)
    if end is not None:
        statement = statement.where(MarketDaily.trade_date <= end)
    rows = session.scalars(statement.order_by(MarketDaily.trade_date)).all()

    return [
        Bar(
            trade_date=row.trade_date,
            open=float(row.open),
            high=float(row.high),
            low=float(row.low),
            close=float(row.close),
            prev_close=float(row.prev_close) if row.prev_close is not None else None,
            volume=int(row.volume or 0),
        )
        for row in rows
    ]


def run_for_code(
    session: Session,
    code: str,
    strategy: str,
    *,
    start: date | None = None,
    end: date | None = None,
    params: dict | None = None,
    initial_cash: float = 100_000.0,
) -> BacktestResult:
    spec = get_strategy(strategy)
    bars = load_bars(session, code, start, end)
    if len(bars) < 2:
        raise ValueError(f"not enough bars for {code} in the selected range")

    result = run_backtest(
        bars,
        spec,
        params,
        BacktestConfig(initial_cash=initial_cash),
    )
    return with_code(result, code)
