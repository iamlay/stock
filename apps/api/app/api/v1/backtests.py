from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.db.models import Instrument
from app.quant.strategies import list_strategies
from app.services.backtest import run_for_code

router = APIRouter(prefix="/backtests", tags=["backtests"])


class BacktestRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)
    strategy: str
    start: date | None = None
    end: date | None = None
    initial_cash: float = Field(default=100_000, gt=0, le=1_000_000_000)
    params: dict[str, Any] = Field(default_factory=dict)


class MetricsOut(BaseModel):
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


class EquityOut(BaseModel):
    date: str
    equity: float
    benchmark: float
    shares: int


class TradeOut(BaseModel):
    date: str
    side: str
    price: float
    shares: int
    amount: float
    fee: float
    reason: str
    realized_pnl: float | None


class BacktestResponse(BaseModel):
    code: str
    strategy: str
    params: dict[str, Any]
    start: str | None
    end: str | None
    metrics: MetricsOut
    equity: list[EquityOut]
    trades: list[TradeOut]
    warnings: list[str]


def _downsample(points: list, maximum: int = 600) -> list:
    if len(points) <= maximum:
        return points
    step = len(points) / maximum
    sampled = [points[int(index * step)] for index in range(maximum)]
    if sampled[-1] is not points[-1]:
        sampled[-1] = points[-1]
    return sampled


@router.get("/strategies", summary="可用策略与参数")
def strategies() -> list[dict[str, Any]]:
    return list_strategies()


@router.post("", response_model=BacktestResponse, summary="运行日频回测")
def run(
    payload: BacktestRequest,
    session: Annotated[Session, Depends(get_session)],
) -> BacktestResponse:
    instrument = session.scalar(select(Instrument).where(Instrument.code == payload.code))
    if instrument is None:
        raise HTTPException(status_code=404, detail=f"unknown code {payload.code}")

    try:
        result = run_for_code(
            session,
            payload.code,
            payload.strategy,
            start=payload.start,
            end=payload.end,
            params=payload.params,
            initial_cash=payload.initial_cash,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    metrics = MetricsOut(**asdict(result.metrics))
    return BacktestResponse(
        code=result.code,
        strategy=result.strategy,
        params=result.params,
        start=result.start.isoformat() if result.start else None,
        end=result.end.isoformat() if result.end else None,
        metrics=metrics,
        equity=[
            EquityOut(
                date=point.trade_date.isoformat(),
                equity=round(point.equity, 2),
                benchmark=round(point.benchmark, 2),
                shares=point.shares,
            )
            for point in _downsample(result.equity)
        ],
        trades=[
            TradeOut(
                date=trade.trade_date.isoformat(),
                side=trade.side,
                price=trade.price,
                shares=trade.shares,
                amount=trade.amount,
                fee=trade.fee,
                reason=trade.reason,
                realized_pnl=trade.realized_pnl,
            )
            for trade in result.trades
        ],
        warnings=result.warnings,
    )
