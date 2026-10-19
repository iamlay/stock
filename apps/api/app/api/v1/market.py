from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.etfs import EtfSummary, _summaries
from app.db import get_session

router = APIRouter(prefix="/market", tags=["market"])


class Mover(BaseModel):
    code: str
    name: str
    change_pct: float


class MarketOverview(BaseModel):
    trade_date: str | None
    demo: bool
    etf_count: int
    avg_change_pct: float | None
    advancing: int
    declining: int
    turnover_billion: float | None
    top_gainers: list[Mover]
    top_losers: list[Mover]
    note: str


def _overview(summaries: list[EtfSummary]) -> MarketOverview:
    if not summaries:
        return MarketOverview(
            trade_date=None,
            demo=True,
            etf_count=0,
            avg_change_pct=None,
            advancing=0,
            declining=0,
            turnover_billion=None,
            top_gainers=[],
            top_losers=[],
            note="数据库中暂无行情数据，请先运行 etl.cli sync-all。",
        )

    ordered = sorted(summaries, key=lambda item: item.change_pct, reverse=True)
    turnover = sum(item.turnover or 0 for item in summaries) / 100_000_000
    return MarketOverview(
        trade_date=max(item.trade_date or "" for item in summaries),
        demo=False,
        etf_count=len(summaries),
        avg_change_pct=round(sum(item.change_pct for item in summaries) / len(summaries), 2),
        advancing=sum(1 for item in summaries if item.change_pct > 0),
        declining=sum(1 for item in summaries if item.change_pct < 0),
        turnover_billion=round(turnover, 2),
        top_gainers=[
            Mover(code=item.code, name=item.name, change_pct=item.change_pct)
            for item in ordered[:5]
        ],
        top_losers=[
            Mover(code=item.code, name=item.name, change_pct=item.change_pct)
            for item in ordered[-5:][::-1]
        ],
        note="重点 ETF 等权统计，非全市场；成交额来自日线数据。",
    )


@router.get("/overview", response_model=MarketOverview, summary="重点 ETF 市场概览")
def market_overview(
    session: Annotated[Session, Depends(get_session)],
) -> MarketOverview:
    return _overview(_summaries(session))
