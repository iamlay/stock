from __future__ import annotations

from datetime import date, datetime
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
    StockDividend,
    StockMetric,
    StockProfile,
    User,
)
from app.security import get_current_admin

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
    last_ex_date: str | None
    updated_at: str | None


class StockList(BaseModel):
    items: list[StockOut]
    total: int
    page: int
    page_size: int
    sort: str
    order: str


class DividendOut(BaseModel):
    ex_date: str
    fiscal_year: int
    cash_per_share: float
    plan: str
    is_special: bool


class StockDetail(StockOut):
    dividends: list[DividendOut]


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
        last_ex_date=_iso(metric.last_ex_date),
        updated_at=_iso(metric.updated_at),
    )


def _base_query():
    return (
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
    return StockDetail(
        **_out(instrument, profile, metric).model_dump(),
        dividends=[
            DividendOut(
                ex_date=item.ex_date.isoformat(),
                fiscal_year=item.fiscal_year,
                cash_per_share=float(item.cash_per_share),
                plan=item.plan,
                is_special=item.is_special,
            )
            for item in dividends
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
