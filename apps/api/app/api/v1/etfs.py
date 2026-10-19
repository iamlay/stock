from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.db.models import EtfProfile, EtfShareDaily, Instrument
from app.services.indicators import compute_indicators, load_recent_closes

router = APIRouter(prefix="/etfs", tags=["etfs"])


class EtfSummary(BaseModel):
    code: str
    name: str
    category: str
    tracked_index: str | None
    trade_date: str | None
    price: float
    change_pct: float
    ma5: float | None
    ma20: float | None
    ma60: float | None
    volatility_20d: float | None
    max_drawdown_1y: float | None
    high_52w: float | None
    low_52w: float | None
    aum: float | None
    shares: float | None
    turnover: float | None


class Bar(BaseModel):
    date: str
    close: float


class EtfDetail(EtfSummary):
    fee_rate: float | None
    return_1m: float | None
    return_3m: float | None
    return_1y: float | None
    bars: list[Bar]


def _latest_shares(session: Session) -> dict[str, EtfShareDaily]:
    ranked = (
        select(
            EtfShareDaily,
            func.row_number()
            .over(
                partition_by=EtfShareDaily.code,
                order_by=EtfShareDaily.trade_date.desc(),
            )
            .label("rn"),
        )
        .subquery()
    )
    rows = session.execute(select(ranked).where(ranked.c.rn == 1)).all()
    return {row.code: row for row in rows}


def _summaries(session: Session, category: str | None = None) -> list[EtfSummary]:
    stmt = (
        select(Instrument, EtfProfile)
        .join(EtfProfile, EtfProfile.code == Instrument.code, isouter=True)
        .where(Instrument.is_active.is_(True), Instrument.type == "etf")
        .order_by(Instrument.code)
    )
    if category:
        stmt = stmt.where(EtfProfile.category == category)

    records = session.execute(stmt).all()
    codes = [instrument.code for instrument, _ in records]
    closes = load_recent_closes(session, codes, limit=260)
    shares = _latest_shares(session)

    summaries: list[EtfSummary] = []
    for instrument, profile in records:
        points = closes.get(instrument.code, [])
        indicator = compute_indicators(points)
        if indicator is None:
            continue
        share = shares.get(instrument.code)
        summaries.append(
            EtfSummary(
                code=instrument.code,
                name=instrument.name,
                category=profile.category if profile else "未分类",
                tracked_index=profile.tracked_index if profile else None,
                trade_date=points[-1].trade_date.isoformat(),
                price=indicator.last_close,
                change_pct=indicator.change_pct,
                ma5=indicator.ma5,
                ma20=indicator.ma20,
                ma60=indicator.ma60,
                volatility_20d=indicator.volatility_20d,
                max_drawdown_1y=indicator.max_drawdown_1y,
                high_52w=indicator.high_52w,
                low_52w=indicator.low_52w,
                aum=float(share.aum) if share else None,
                shares=float(share.shares) if share else None,
                turnover=indicator.last_amount,
            )
        )
    return summaries


@router.get("", response_model=list[EtfSummary], summary="ETF 列表与指标")
def list_etfs(
    session: Annotated[Session, Depends(get_session)],
    category: Annotated[
        str | None, Query(description="红利 / 现金流 / 跨境 / 宽基 / 行业")
    ] = None,
) -> list[EtfSummary]:
    return _summaries(session, category)


@router.get("/{code}", response_model=EtfDetail, summary="ETF 详情")
def get_etf(
    code: str, session: Annotated[Session, Depends(get_session)]
) -> EtfDetail:
    record = session.execute(
        select(Instrument, EtfProfile)
        .join(EtfProfile, EtfProfile.code == Instrument.code, isouter=True)
        .where(Instrument.code == code)
    ).first()
    if record is None:
        raise HTTPException(status_code=404, detail=f"unknown ETF {code}")

    instrument, profile = record
    points = load_recent_closes(session, [code], limit=260).get(code, [])
    indicator = compute_indicators(points)
    if indicator is None:
        raise HTTPException(status_code=404, detail=f"no price data for {code}")

    share = _latest_shares(session).get(code)
    return EtfDetail(
        code=instrument.code,
        name=instrument.name,
        category=profile.category if profile else "未分类",
        tracked_index=profile.tracked_index if profile else None,
        trade_date=points[-1].trade_date.isoformat(),
        price=indicator.last_close,
        change_pct=indicator.change_pct,
        ma5=indicator.ma5,
        ma20=indicator.ma20,
        ma60=indicator.ma60,
        volatility_20d=indicator.volatility_20d,
        max_drawdown_1y=indicator.max_drawdown_1y,
        high_52w=indicator.high_52w,
        low_52w=indicator.low_52w,
        aum=float(share.aum) if share else None,
        shares=float(share.shares) if share else None,
        turnover=indicator.last_amount,
        fee_rate=float(profile.fee_rate) if profile and profile.fee_rate else None,
        return_1m=indicator.return_1m,
        return_3m=indicator.return_3m,
        return_1y=indicator.return_1y,
        bars=[Bar(date=point.trade_date.isoformat(), close=point.close) for point in points[-120:]],
    )
