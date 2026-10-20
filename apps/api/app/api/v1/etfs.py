from __future__ import annotations

from math import sqrt
from statistics import pstdev
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.db.models import EtfProfile, EtfShareDaily, IndexValuation, Instrument
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
    pe: float | None
    pb: float | None
    pe_percentile: float | None
    dividend_yield: float | None


class Bar(BaseModel):
    date: str
    close: float


class EtfDetail(EtfSummary):
    fee_rate: float | None
    return_1m: float | None
    return_3m: float | None
    return_1y: float | None
    bars: list[Bar]


class ComparePoint(BaseModel):
    date: str
    value: float


class CompareItem(BaseModel):
    code: str
    name: str
    category: str
    total_return: float
    max_drawdown: float
    volatility: float
    series: list[ComparePoint]


class CompareResponse(BaseModel):
    start: str
    end: str
    days: int
    items: list[CompareItem]


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


def _latest_valuations(
    session: Session, index_codes: list[str]
) -> dict[str, IndexValuation]:
    if not index_codes:
        return {}
    ranked = (
        select(
            IndexValuation,
            func.row_number()
            .over(
                partition_by=IndexValuation.index_code,
                order_by=IndexValuation.trade_date.desc(),
            )
            .label("rn"),
        )
        .where(IndexValuation.index_code.in_(index_codes))
        .subquery()
    )
    rows = session.execute(select(ranked).where(ranked.c.rn == 1)).all()
    return {row.index_code: row for row in rows}


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
    index_codes = sorted(
        {profile.valuation_index for _, profile in records if profile and profile.valuation_index}
    )
    valuations = _latest_valuations(session, index_codes)

    summaries: list[EtfSummary] = []
    for instrument, profile in records:
        points = closes.get(instrument.code, [])
        indicator = compute_indicators(points)
        if indicator is None:
            continue
        share = shares.get(instrument.code)
        valuation = valuations.get(profile.valuation_index) if profile else None
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
                pe=float(valuation.pe) if valuation else None,
                pb=float(valuation.pb) if valuation else None,
                pe_percentile=round(float(valuation.pe_percentile) * 100, 1)
                if valuation
                else None,
                dividend_yield=round(float(valuation.dividend_yield) * 100, 2)
                if valuation
                else None,
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


@router.get("/compare", response_model=CompareResponse, summary="ETF 归一化对比")
def compare_etfs(
    session: Annotated[Session, Depends(get_session)],
    codes: Annotated[str, Query(description="逗号分隔的 2-5 个 ETF 代码")],
    days: Annotated[int, Query(ge=30, le=1000)] = 250,
) -> CompareResponse:
    requested = list(dict.fromkeys(code.strip() for code in codes.split(",") if code.strip()))
    if len(requested) < 2 or len(requested) > 5:
        raise HTTPException(status_code=400, detail="请选择 2-5 只 ETF")
    records = session.execute(
        select(Instrument, EtfProfile)
        .join(EtfProfile, EtfProfile.code == Instrument.code, isouter=True)
        .where(Instrument.code.in_(requested), Instrument.is_active.is_(True))
    ).all()
    if len(records) != len(requested):
        raise HTTPException(status_code=404, detail="存在未知 ETF")
    by_code = {instrument.code: (instrument, profile) for instrument, profile in records}

    closes = load_recent_closes(session, requested, limit=max(days * 2, 400))
    close_maps = {
        code: {point.trade_date: float(point.close) for point in points}
        for code, points in closes.items()
    }
    if any(not close_maps.get(code) for code in requested):
        raise HTTPException(status_code=400, detail="部分 ETF 没有行情数据")
    common_dates = sorted(set.intersection(*(set(close_maps[code]) for code in requested)))
    common_dates = common_dates[-days:]
    if len(common_dates) < 2:
        raise HTTPException(status_code=400, detail="共同交易日不足")

    items: list[CompareItem] = []
    for code in requested:
        instrument, profile = by_code[code]
        raw = [close_maps[code][day] for day in common_dates]
        base = raw[0]
        values = [round(value / base * 100, 3) for value in raw]
        peak = values[0]
        max_drawdown = 0.0
        for value in values:
            peak = max(peak, value)
            max_drawdown = min(max_drawdown, (value / peak - 1) * 100)
        daily_returns = [
            raw[index] / raw[index - 1] - 1 for index in range(1, len(raw))
        ]
        volatility = (
            pstdev(daily_returns) * sqrt(252) * 100 if len(daily_returns) > 1 else 0.0
        )
        items.append(
            CompareItem(
                code=code,
                name=instrument.name,
                category=profile.category if profile else "未分类",
                total_return=round((raw[-1] / base - 1) * 100, 2),
                max_drawdown=round(max_drawdown, 2),
                volatility=round(volatility, 2),
                series=[
                    ComparePoint(date=day.isoformat(), value=value)
                    for day, value in zip(common_dates, values, strict=False)
                ],
            )
        )

    return CompareResponse(
        start=common_dates[0].isoformat(),
        end=common_dates[-1].isoformat(),
        days=len(common_dates),
        items=items,
    )


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
    valuation = (
        _latest_valuations(session, [profile.valuation_index]).get(profile.valuation_index)
        if profile and profile.valuation_index
        else None
    )
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
        pe=float(valuation.pe) if valuation else None,
        pb=float(valuation.pb) if valuation else None,
        pe_percentile=round(float(valuation.pe_percentile) * 100, 1) if valuation else None,
        dividend_yield=round(float(valuation.dividend_yield) * 100, 2) if valuation else None,
        fee_rate=float(profile.fee_rate) if profile and profile.fee_rate else None,
        return_1m=indicator.return_1m,
        return_3m=indicator.return_3m,
        return_1y=indicator.return_1y,
        bars=[Bar(date=point.trade_date.isoformat(), close=point.close) for point in points[-120:]],
    )
