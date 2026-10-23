from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Annotated, Literal

from etl.stocks import sync_stock_quote
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.db.models import (
    AdminAuditLog,
    Instrument,
    MarketDaily,
    StockDividend,
    StockFinancial,
    StockMetric,
    StockProfile,
    User,
)
from app.security import get_current_admin
from app.services.bollinger import Band, compute_bollinger

router = APIRouter(prefix="/stocks", tags=["stocks"])
admin_router = APIRouter(prefix="/admin/stocks", tags=["admin-stocks"])

SORT_FIELDS = {
    "dividend_yield_ttm": StockMetric.dividend_yield_ttm,
    "dividend_yield_fy": StockMetric.dividend_yield_fy,
    "market_cap": StockMetric.market_cap,
    "change_pct": StockMetric.change_pct,
    "pe_ttm": StockMetric.pe_ttm,
}


class StockOut(BaseModel):
    code: str
    name: str
    industry: str | None
    industry_path: str | None
    market: str | None
    is_st: bool
    price: float | None
    change_pct: float | None
    market_cap: float | None
    pe_ttm: float | None
    pb: float | None
    dividend_yield_ttm: float | None
    dividend_yield_fy: float | None
    sustainability: str | None
    last_ex_date: str | None
    updated_at: str | None


class StockList(BaseModel):
    items: list[StockOut]
    total: int
    page: int
    page_size: int
    sort: str
    order: str


class BandOut(BaseModel):
    position: str
    close: float
    mid: float
    upper: float
    lower: float
    percent_b: float
    periods: int


class StockBollingerOut(StockOut):
    daily: BandOut | None
    weekly: BandOut | None
    monthly: BandOut | None
    rating: str


class StockBollingerList(BaseModel):
    items: list[StockBollingerOut]
    total: int
    page: int
    page_size: int


class DividendOut(BaseModel):
    ex_date: str
    fiscal_year: int
    cash_per_share: float
    plan: str
    is_special: bool
    is_one_off: bool


class StockBar(BaseModel):
    date: str
    close: float


class FinancialOut(BaseModel):
    report_date: str
    period: str
    revenue: float | None
    net_profit: float | None
    revenue_yoy: float | None
    net_profit_yoy: float | None
    roe: float | None
    operating_cash_flow_per_share: float | None
    operating_cash_flow: float | None
    gross_margin: float | None
    net_margin: float | None
    disclosure_date: str | None


class AnnualFinancialOut(BaseModel):
    year: int
    net_profit: float | None
    net_profit_yoy: float | None


class StockFinancialOut(StockOut):
    annuals: list[AnnualFinancialOut]
    latest_period: str | None
    latest_report_date: str | None
    latest_net_profit: float | None
    latest_net_profit_yoy: float | None
    latest_revenue_yoy: float | None
    latest_roe: float | None
    latest_operating_cash_flow_per_share: float | None
    latest_operating_cash_flow: float | None
    latest_gross_margin: float | None
    latest_net_margin: float | None
    disclosure_date: str | None


class StockFinancialList(BaseModel):
    items: list[StockFinancialOut]
    total: int
    page: int
    page_size: int


class StockDetail(StockOut):
    dividends: list[DividendOut]
    bars: list[StockBar]
    financials: list[FinancialOut] = []


class AdminStockOut(StockOut):
    status: str


class AdminStockList(BaseModel):
    items: list[AdminStockOut]
    total: int
    page: int
    page_size: int


class StatusUpdate(BaseModel):
    status: Literal["active", "excluded"]


def _iso(value: date | datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _out(
    instrument: Instrument,
    profile: StockProfile,
    metric: StockMetric,
) -> StockOut:
    return StockOut(
        code=instrument.code,
        name=instrument.name,
        industry=profile.industry,
        industry_path=profile.industry_path,
        market=profile.market,
        is_st=profile.is_st,
        price=float(metric.price) if metric.price is not None else None,
        change_pct=float(metric.change_pct) if metric.change_pct is not None else None,
        market_cap=float(metric.market_cap) if metric.market_cap is not None else None,
        pe_ttm=float(metric.pe_ttm) if metric.pe_ttm is not None else None,
        pb=float(metric.pb) if metric.pb is not None else None,
        dividend_yield_ttm=(
            float(metric.dividend_yield_ttm)
            if metric.dividend_yield_ttm is not None
            else None
        ),
        dividend_yield_fy=(
            float(metric.dividend_yield_fy)
            if metric.dividend_yield_fy is not None
            else None
        ),
        sustainability=metric.sustainability,
        last_ex_date=_iso(metric.last_ex_date),
        updated_at=_iso(metric.updated_at),
    )


def _band_out(band: Band | None) -> BandOut | None:
    if band is None:
        return None
    return BandOut(
        position=band.position,
        close=band.close,
        mid=band.mid,
        upper=band.upper,
        lower=band.lower,
        percent_b=band.percent_b,
        periods=band.periods,
    )


def _base_query():    return (
        select(Instrument, StockProfile, StockMetric)
        .join(StockProfile, StockProfile.code == Instrument.code)
        .join(StockMetric, StockMetric.code == Instrument.code)
    )


def _conditions(
    *,
    q: str | None,
    industry: str | None,
    min_yield: float | None,
    include_st: bool,
):
    conditions = [
        Instrument.type == "stock",
        StockProfile.status == "active",
        StockMetric.price.is_not(None),
    ]
    if not include_st:
        conditions.append(StockProfile.is_st.is_(False))
    if q:
        pattern = f"%{q.strip()}%"
        conditions.append(
            or_(Instrument.code.ilike(pattern), Instrument.name.ilike(pattern))
        )
    if industry:
        conditions.append(StockProfile.industry == industry)
    if min_yield is not None:
        conditions.append(StockMetric.dividend_yield_ttm >= min_yield)
    return conditions


@router.get("", response_model=StockList, summary="个股列表，支持股息率排序")
def list_stocks(
    session: Annotated[Session, Depends(get_session)],
    sort: str = Query("dividend_yield_ttm", description="排序字段"),
    order: Literal["asc", "desc"] = "desc",
    q: str | None = Query(None, max_length=32),
    industry: str | None = Query(None, max_length=32),
    min_yield: float | None = Query(None, ge=0, le=100),
    include_st: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> StockList:
    field = SORT_FIELDS.get(sort)
    if field is None:
        raise HTTPException(status_code=422, detail=f"unsupported sort: {sort}")

    conditions = _conditions(
        q=q,
        industry=industry,
        min_yield=min_yield,
        include_st=include_st,
    )
    total = (
        session.scalar(
            select(func.count())
            .select_from(Instrument)
            .join(StockProfile, StockProfile.code == Instrument.code)
            .join(StockMetric, StockMetric.code == Instrument.code)
            .where(*conditions)
        )
        or 0
    )

    ordering = field.desc().nulls_last() if order == "desc" else field.asc().nulls_last()
    rows = session.execute(
        _base_query()
        .where(*conditions)
        .order_by(ordering, StockMetric.market_cap.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return StockList(
        items=[_out(instrument, profile, metric) for instrument, profile, metric in rows],
        total=total,
        page=page,
        page_size=page_size,
        sort=sort,
        order=order,
    )


@router.get("/search", response_model=list[StockOut], summary="个股搜索建议")
def search_stocks(
    session: Annotated[Session, Depends(get_session)],
    q: str = Query(..., min_length=1, max_length=32),
    limit: int = Query(10, ge=1, le=20),
) -> list[StockOut]:
    pattern = f"%{q.strip()}%"
    rows = session.execute(
        _base_query()
        .where(
            Instrument.type == "stock",
            StockProfile.status == "active",
            StockMetric.price.is_not(None),
            or_(Instrument.code.ilike(pattern), Instrument.name.ilike(pattern)),
        )
        .order_by(StockMetric.market_cap.desc())
        .limit(limit)
    ).all()
    return [_out(instrument, profile, metric) for instrument, profile, metric in rows]


@router.get(
    "/bollinger",
    response_model=StockBollingerList,
    summary="个股布林位置，覆盖已有 K 线的标的",
)
def list_stock_bollinger(
    session: Annotated[Session, Depends(get_session)],
    q: str | None = Query(None, max_length=32),
    industry: str | None = Query(None, max_length=32),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> StockBollingerList:
    cutoff = date.today() - timedelta(days=900)
    bar_codes = (
        select(MarketDaily.code)
        .where(MarketDaily.trade_date >= cutoff)
        .distinct()
    )
    rows = session.execute(
        _base_query()
        .where(
            *_conditions(
                q=q,
                industry=industry,
                min_yield=None,
                include_st=False,
            ),
            Instrument.code.in_(bar_codes),
        )
        .order_by(
            StockMetric.dividend_yield_ttm.desc().nulls_last(),
            StockMetric.market_cap.desc().nulls_last(),
        )
    ).all()

    codes = [instrument.code for instrument, _, _ in rows]
    total = len(codes)
    if not codes:
        return StockBollingerList(items=[], total=0, page=page, page_size=page_size)

    start = (page - 1) * page_size
    page_rows = rows[start : start + page_size]
    page_codes = [instrument.code for instrument, _, _ in page_rows]
    bar_rows = session.execute(
        select(MarketDaily.code, MarketDaily.trade_date, MarketDaily.close)
        .where(
            MarketDaily.code.in_(page_codes),
            MarketDaily.trade_date >= cutoff,
        )
        .order_by(MarketDaily.code, MarketDaily.trade_date)
    ).all()
    bars_by_code: dict[str, list[tuple[date, float]]] = {}
    for code, trade_date, close in bar_rows:
        bars_by_code.setdefault(code, []).append((trade_date, float(close)))

    items: list[StockBollingerOut] = []
    for instrument, profile, metric in page_rows:
        bars = bars_by_code.get(instrument.code, [])
        if len(bars) < 20:
            continue
        result = compute_bollinger(bars)
        items.append(
            StockBollingerOut(
                **_out(instrument, profile, metric).model_dump(),
                daily=_band_out(result["daily"]),
                weekly=_band_out(result["weekly"]),
                monthly=_band_out(result["monthly"]),
                rating=result["rating"],
            )
        )

    return StockBollingerList(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/financials",
    response_model=StockFinancialList,
    summary="个股财务概览，覆盖已有财报的标的",
)
def list_stock_financials(
    session: Annotated[Session, Depends(get_session)],
    q: str | None = Query(None, max_length=32),
    industry: str | None = Query(None, max_length=32),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> StockFinancialList:
    rows = session.execute(
        _base_query()
        .where(
            *_conditions(
                q=q,
                industry=industry,
                min_yield=None,
                include_st=False,
            ),
            Instrument.code.in_(select(StockFinancial.code).distinct()),
        )
        .order_by(
            StockMetric.dividend_yield_ttm.desc().nulls_last(),
            StockMetric.market_cap.desc().nulls_last(),
        )
    ).all()
    codes = [instrument.code for instrument, _, _ in rows]
    financial_rows = session.scalars(
        select(StockFinancial)
        .where(StockFinancial.code.in_(codes))
        .order_by(StockFinancial.code, StockFinancial.report_date.desc())
    ).all()
    by_code: dict[str, list[StockFinancial]] = {}
    for item in financial_rows:
        by_code.setdefault(item.code, []).append(item)

    items: list[StockFinancialOut] = []
    for instrument, profile, metric in rows:
        reports = by_code.get(instrument.code, [])
        if not reports:
            continue
        latest = reports[0]
        annuals = [report for report in reports if report.period == "FY"][:3]
        items.append(
            StockFinancialOut(
                **_out(instrument, profile, metric).model_dump(),
                annuals=[
                    AnnualFinancialOut(
                        year=report.report_date.year,
                        net_profit=(
                            float(report.net_profit)
                            if report.net_profit is not None
                            else None
                        ),
                        net_profit_yoy=(
                            float(report.net_profit_yoy)
                            if report.net_profit_yoy is not None
                            else None
                        ),
                    )
                    for report in annuals
                ],
                latest_period=latest.period,
                latest_report_date=latest.report_date.isoformat(),
                latest_net_profit=(
                    float(latest.net_profit)
                    if latest.net_profit is not None
                    else None
                ),
                latest_net_profit_yoy=(
                    float(latest.net_profit_yoy)
                    if latest.net_profit_yoy is not None
                    else None
                ),
                latest_revenue_yoy=(
                    float(latest.revenue_yoy)
                    if latest.revenue_yoy is not None
                    else None
                ),
                latest_roe=float(latest.roe) if latest.roe is not None else None,
                latest_operating_cash_flow_per_share=(
                    float(latest.operating_cash_flow_per_share)
                    if latest.operating_cash_flow_per_share is not None
                    else None
                ),
                latest_operating_cash_flow=(
                    float(latest.operating_cash_flow)
                    if latest.operating_cash_flow is not None
                    else None
                ),
                latest_gross_margin=(
                    float(latest.gross_margin)
                    if latest.gross_margin is not None
                    else None
                ),
                latest_net_margin=(
                    float(latest.net_margin)
                    if latest.net_margin is not None
                    else None
                ),
                disclosure_date=(
                    latest.disclosure_date.isoformat()
                    if latest.disclosure_date
                    else None
                ),
            )
        )

    total = len(items)
    start = (page - 1) * page_size
    return StockFinancialList(
        items=items[start : start + page_size],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{code}", response_model=StockDetail, summary="个股详情")
def get_stock(
    code: str,
    session: Annotated[Session, Depends(get_session)],
) -> StockDetail:
    row = session.execute(
        _base_query().where(
            Instrument.code == code,
            Instrument.type == "stock",
            StockProfile.status != "excluded",
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="stock not found")
    instrument, profile, metric = row
    dividends = session.scalars(
        select(StockDividend)
        .where(StockDividend.code == code)
        .order_by(StockDividend.ex_date.desc())
        .limit(100)
    ).all()
    financials = session.scalars(
        select(StockFinancial)
        .where(StockFinancial.code == code)
        .order_by(StockFinancial.report_date.desc())
        .limit(24)
    ).all()
    bars = session.scalars(
        select(MarketDaily)
        .where(MarketDaily.code == code)
        .order_by(MarketDaily.trade_date.desc())
        .limit(600)
    ).all()
    return StockDetail(
        **_out(instrument, profile, metric).model_dump(),
        dividends=[
            DividendOut(
                ex_date=item.ex_date.isoformat(),
                fiscal_year=item.fiscal_year,
                cash_per_share=float(item.cash_per_share),
                plan=item.plan,
                is_special=item.is_special,
                is_one_off=item.is_one_off,
            )
            for item in dividends
        ],
        bars=[
            StockBar(date=item.trade_date.isoformat(), close=float(item.close))
            for item in reversed(bars)
        ],
        financials=[
            FinancialOut(
                report_date=item.report_date.isoformat(),
                period=item.period,
                revenue=float(item.revenue) if item.revenue is not None else None,
                net_profit=(
                    float(item.net_profit) if item.net_profit is not None else None
                ),
                revenue_yoy=(
                    float(item.revenue_yoy) if item.revenue_yoy is not None else None
                ),
                net_profit_yoy=(
                    float(item.net_profit_yoy)
                    if item.net_profit_yoy is not None
                    else None
                ),
                roe=float(item.roe) if item.roe is not None else None,
                operating_cash_flow_per_share=(
                    float(item.operating_cash_flow_per_share)
                    if item.operating_cash_flow_per_share is not None
                    else None
                ),
                operating_cash_flow=(
                    float(item.operating_cash_flow)
                    if item.operating_cash_flow is not None
                    else None
                ),
                gross_margin=(
                    float(item.gross_margin) if item.gross_margin is not None else None
                ),
                net_margin=(
                    float(item.net_margin) if item.net_margin is not None else None
                ),
                disclosure_date=(
                    item.disclosure_date.isoformat() if item.disclosure_date else None
                ),
            )
            for item in financials
        ],
    )


@admin_router.get("", response_model=AdminStockList, summary="后台个股列表")
def admin_list_stocks(
    session: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(get_current_admin)],
    q: str | None = Query(None, max_length=32),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> AdminStockList:
    conditions = [Instrument.type == "stock"]
    if q:
        pattern = f"%{q.strip()}%"
        conditions.append(
            or_(Instrument.code.ilike(pattern), Instrument.name.ilike(pattern))
        )
    total = (
        session.scalar(
            select(func.count())
            .select_from(Instrument)
            .join(StockProfile, StockProfile.code == Instrument.code)
            .where(*conditions)
        )
        or 0
    )
    rows = session.execute(
        _base_query()
        .where(*conditions)
        .order_by(StockMetric.market_cap.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return AdminStockList(
        items=[
            AdminStockOut(
                **_out(instrument, profile, metric).model_dump(),
                status=profile.status,
            )
            for instrument, profile, metric in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


def _audit(
    session: Session,
    request: Request,
    admin: User,
    action: str,
    code: str,
    detail: dict,
) -> None:
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip() if forwarded else (
        request.client.host if request.client else None
    )
    session.add(
        AdminAuditLog(
            user_id=admin.id,
            action=action,
            target_type="stock",
            target_id=code,
            detail=detail,
            ip=ip,
        )
    )


@admin_router.patch("/{code}", response_model=AdminStockOut, summary="启用/停用个股")
def update_stock_status(
    code: str,
    body: StatusUpdate,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    admin: Annotated[User, Depends(get_current_admin)],
) -> AdminStockOut:
    row = session.execute(
        _base_query().where(Instrument.code == code, Instrument.type == "stock")
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="stock not found")
    instrument, profile, metric = row
    profile.status = body.status
    _audit(session, request, admin, "stock_status", code, {"status": body.status})
    session.commit()
    return AdminStockOut(
        **_out(instrument, profile, metric).model_dump(),
        status=profile.status,
    )


@admin_router.post("/{code}/sync", response_model=AdminStockOut, summary="手动同步个股")
def sync_stock(
    code: str,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    admin: Annotated[User, Depends(get_current_admin)],
) -> AdminStockOut:
    try:
        sync_stock_quote(session, code)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"sync failed: {exc}") from exc
    row = session.execute(
        _base_query().where(Instrument.code == code, Instrument.type == "stock")
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="stock not found")
    instrument, profile, metric = row
    _audit(session, request, admin, "stock_sync", code, {})
    session.commit()
    return AdminStockOut(
        **_out(instrument, profile, metric).model_dump(),
        status=profile.status,
    )
