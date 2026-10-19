from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.db.models import BacktestRun, Instrument, User
from app.quant.strategies import list_strategies
from app.security import get_current_user, get_optional_user
from app.services.backtest import run_for_code
from app.services.membership import client_key_for, is_member, quota_for

router = APIRouter(prefix="/backtests", tags=["backtests"])


class BacktestRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)
    strategy: str
    start: date | None = None
    end: date | None = None
    initial_cash: float = Field(default=100_000, gt=0, le=1_000_000_000)
    params: dict[str, Any] = Field(default_factory=dict)


class QuotaOut(BaseModel):
    plan: str
    used: int
    limit: int | None
    remaining: int | None


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
    run_id: int | None = None
    saved: bool = False
    quota: QuotaOut | None = None


class HistoryItem(BaseModel):
    id: int
    code: str
    strategy: str
    total_return: float
    created_at: str


def _downsample(points: list, maximum: int = 600) -> list:
    if len(points) <= maximum:
        return points
    step = len(points) / maximum
    sampled = [points[int(index * step)] for index in range(maximum)]
    sampled[-1] = points[-1]
    return sampled


def _serialize(result) -> dict[str, Any]:
    return {
        "code": result.code,
        "strategy": result.strategy,
        "params": result.params,
        "start": result.start.isoformat() if result.start else None,
        "end": result.end.isoformat() if result.end else None,
        "metrics": asdict(result.metrics),
        "equity": [
            {
                "date": point.trade_date.isoformat(),
                "equity": round(point.equity, 2),
                "benchmark": round(point.benchmark, 2),
                "shares": point.shares,
            }
            for point in _downsample(result.equity)
        ],
        "trades": [
            {
                "date": trade.trade_date.isoformat(),
                "side": trade.side,
                "price": trade.price,
                "shares": trade.shares,
                "amount": trade.amount,
                "fee": trade.fee,
                "reason": trade.reason,
                "realized_pnl": trade.realized_pnl,
            }
            for trade in result.trades
        ],
        "warnings": result.warnings,
    }


@router.get("/strategies", summary="可用策略与参数")
def strategies() -> list[dict[str, Any]]:
    return list_strategies()


@router.post("", response_model=BacktestResponse, summary="运行日频回测")
def run(
    payload: BacktestRequest,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User | None, Depends(get_optional_user)],
) -> BacktestResponse:
    instrument = session.scalar(select(Instrument).where(Instrument.code == payload.code))
    if instrument is None:
        raise HTTPException(status_code=404, detail=f"unknown code {payload.code}")

    forwarded = request.headers.get("x-forwarded-for", "")
    ip = (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.client.host if request.client else "unknown")
    )
    client_key = client_key_for(ip)

    quota = quota_for(session, user, client_key)
    if quota["limit"] is not None and quota["used"] >= quota["limit"]:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "message": "今日回测次数已用完。登录或开通会员可继续。",
                "quota": quota,
            },
        )

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

    data = _serialize(result)
    saved = BacktestRun(
        user_id=user.id if user else None,
        client_key=client_key,
        code=result.code,
        strategy=result.strategy,
        params=result.params,
        start_date=result.start,
        end_date=result.end,
        initial_cash=payload.initial_cash,
        status="success",
        metrics=data["metrics"],
        result=data,
        finished_at=datetime.now(UTC),
    )
    session.add(saved)
    session.commit()
    session.refresh(saved)

    refreshed = quota_for(session, user, client_key)
    return BacktestResponse(
        **data,
        run_id=saved.id,
        saved=True,
        quota=QuotaOut(**refreshed),
    )


@router.get("/history", response_model=list[HistoryItem], summary="会员回测历史")
def history(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[HistoryItem]:
    if not is_member(user):
        raise HTTPException(status_code=403, detail="会员可查看回测历史")

    rows = session.scalars(
        select(BacktestRun)
        .where(BacktestRun.user_id == user.id)
        .order_by(BacktestRun.created_at.desc())
        .limit(50)
    ).all()
    return [
        HistoryItem(
            id=row.id,
            code=row.code,
            strategy=row.strategy,
            total_return=float(row.metrics.get("total_return", 0)),
            created_at=row.created_at.isoformat(),
        )
        for row in rows
    ]


@router.get("/history/{run_id}", response_model=BacktestResponse, summary="回测快照")
def history_detail(
    run_id: int,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> BacktestResponse:
    if not is_member(user):
        raise HTTPException(status_code=403, detail="会员可查看回测历史")

    row = session.get(BacktestRun, run_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="backtest not found")
    return BacktestResponse(**row.result, run_id=row.id, saved=True)
