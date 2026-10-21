from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.api.v1.etfs import EtfSummary, _summaries
from app.db import get_session
from app.db.models import Instrument, StockMetric, StockProfile

router = APIRouter(prefix="/market", tags=["market"])


class Mover(BaseModel):
    code: str
    name: str
    change_pct: float


class MarketOverview(BaseModel):
    trade_date: str | None
    quote_time: str | None
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
            quote_time=None,
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
        quote_time=max(
            (item.quote_time for item in summaries if item.quote_time),
            default=None,
        ),
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
        note="重点 ETF 等权统计，非全市场；成交额优先使用最新报价。",
    )


@router.get("/overview", response_model=MarketOverview, summary="重点 ETF 市场概览")
def market_overview(
    session: Annotated[Session, Depends(get_session)],
) -> MarketOverview:
    return _overview(_summaries(session))


class IndustryMove(BaseModel):
    name: str
    change_pct: float
    count: int
    advancing: int
    declining: int


class IndustryList(BaseModel):
    items: list[IndustryMove]
    total: int
    note: str


@router.get("/industries", response_model=IndustryList, summary="申万一级行业涨跌")
def market_industries(
    session: Annotated[Session, Depends(get_session)],
    include_st: bool = False,
    weight: Literal["equal", "cap"] = "equal",
) -> IndustryList:
    conditions = [
        Instrument.type == "stock",
        StockProfile.status == "active",
        StockProfile.industry.is_not(None),
        StockMetric.price.is_not(None),
        StockMetric.change_pct.is_not(None),
    ]
    if not include_st:
        conditions.append(StockProfile.is_st.is_(False))

    if weight == "cap":
        change_expr = func.sum(
            StockMetric.change_pct * StockMetric.market_cap
        ) / func.nullif(func.sum(StockMetric.market_cap), 0)
    else:
        change_expr = func.avg(StockMetric.change_pct)

    rows = session.execute(
        select(
            StockProfile.industry,
            change_expr.label("change_pct"),
            func.count().label("count"),
            func.sum(case((StockMetric.change_pct > 0, 1), else_=0)).label("advancing"),
            func.sum(case((StockMetric.change_pct < 0, 1), else_=0)).label("declining"),
        )
        .select_from(Instrument)
        .join(StockProfile, StockProfile.code == Instrument.code)
        .join(StockMetric, StockMetric.code == Instrument.code)
        .where(*conditions)
        .group_by(StockProfile.industry)
    ).all()

    items = [
        IndustryMove(
            name=row.industry,
            change_pct=round(float(row.change_pct or 0), 2),
            count=int(row.count or 0),
            advancing=int(row.advancing or 0),
            declining=int(row.declining or 0),
        )
        for row in rows
    ]
    items.sort(key=lambda item: item.change_pct, reverse=True)
    return IndustryList(
        items=items,
        total=len(items),
        note=(
            "申万一级行业，个股等权涨跌"
            if weight == "equal"
            else "申万一级行业，市值加权涨跌"
        ),
    )
