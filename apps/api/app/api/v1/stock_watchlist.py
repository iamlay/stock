from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated

from etl.stocks import sync_stock_quote
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.stocks import BandOut, StockOut, _band_out, _base_query, _out
from app.db import get_session
from app.db.models import (
    Instrument,
    MarketDaily,
    StockFinancial,
    StockMetric,
    StockProfile,
    StockWatchlist,
    User,
)
from app.security import get_current_user
from app.services.bollinger import compute_bollinger
from app.services.entitlements import ensure_watchlist_slot
from app.services.membership import is_member

router = APIRouter(prefix="/stock-watchlist", tags=["stock-watchlist"])


class WatchIn(BaseModel):
    code: str


class FinancialLite(BaseModel):
    report_date: str
    period: str
    net_profit: float | None
    net_profit_yoy: float | None
    disclosure_date: str | None


class GridTargetLite(BaseModel):
    target_yield: float
    target_price: float
    distance_pct: float


class WatchlistStockOut(StockOut):
    bollinger_daily: BandOut | None = None
    bollinger_weekly: BandOut | None = None
    bollinger_monthly: BandOut | None = None
    bollinger_rating: str | None = None
    latest_financial: FinancialLite | None = None
    grid_targets: list[GridTargetLite] = []


@router.get("", response_model=list[StockOut], summary="个股自选列表")
def list_stock_watchlist(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[StockOut]:
    rows = session.execute(
        _base_query()
        .join(StockWatchlist, StockWatchlist.code == Instrument.code)
        .where(StockWatchlist.user_id == user.id)
        .order_by(StockWatchlist.created_at.desc())
    ).all()
    return [_out(instrument, profile, metric) for instrument, profile, metric in rows]


@router.get(
    "/enriched",
    response_model=list[WatchlistStockOut],
    summary="自选个股增强信息",
)
def list_enriched_stock_watchlist(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[WatchlistStockOut]:
    rows = session.execute(
        _base_query()
        .join(StockWatchlist, StockWatchlist.code == Instrument.code)
        .where(StockWatchlist.user_id == user.id)
        .order_by(StockWatchlist.created_at.desc())
    ).all()
    if not rows:
        return []

    codes = [instrument.code for instrument, _, _ in rows]
    cutoff = date.today() - timedelta(days=900)
    bar_rows = session.execute(
        select(MarketDaily.code, MarketDaily.trade_date, MarketDaily.close)
        .where(
            MarketDaily.code.in_(codes),
            MarketDaily.trade_date >= cutoff,
        )
        .order_by(MarketDaily.code, MarketDaily.trade_date)
    ).all()
    bars_by_code: dict[str, list[tuple[date, float]]] = {}
    for code, trade_date, close in bar_rows:
        bars_by_code.setdefault(code, []).append((trade_date, float(close)))

    financial_rows = session.scalars(
        select(StockFinancial)
        .where(StockFinancial.code.in_(codes))
        .order_by(StockFinancial.code, StockFinancial.report_date.desc())
    ).all()
    latest_financial: dict[str, StockFinancial] = {}
    for item in financial_rows:
        latest_financial.setdefault(item.code, item)

    member = is_member(user)
    items: list[WatchlistStockOut] = []
    for instrument, profile, metric in rows:
        item = WatchlistStockOut(**_out(instrument, profile, metric).model_dump())
        if member:
            bars = bars_by_code.get(instrument.code, [])
            if len(bars) >= 20:
                result = compute_bollinger(bars)
                item.bollinger_daily = _band_out(result["daily"])
                item.bollinger_weekly = _band_out(result["weekly"])
                item.bollinger_monthly = _band_out(result["monthly"])
                item.bollinger_rating = result["rating"]
            report = latest_financial.get(instrument.code)
            if report is not None:
                item.latest_financial = FinancialLite(
                    report_date=report.report_date.isoformat(),
                    period=report.period,
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
                    disclosure_date=(
                        report.disclosure_date.isoformat()
                        if report.disclosure_date
                        else None
                    ),
                )
            price = float(metric.price) if metric.price is not None else 0
            ttm = float(metric.dividend_yield_ttm or 0)
            if price > 0 and ttm > 0:
                annual_cash = price * ttm / 100
                item.grid_targets = [
                    GridTargetLite(
                        target_yield=target,
                        target_price=round(annual_cash / (target / 100), 2),
                        distance_pct=round(
                            (annual_cash / (target / 100) / price - 1) * 100, 2
                        ),
                    )
                    for target in (5, 5.5, 6)
                ]
        items.append(item)
    return items


@router.post("", summary="加入个股自选")
def add_stock_watchlist(
    body: WatchIn,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    code = body.code.strip()
    if len(code) != 6 or not code.isdigit():
        raise HTTPException(status_code=400, detail="invalid stock code")
    instrument = session.get(Instrument, code)
    metric = session.get(StockMetric, code)
    profile = session.get(StockProfile, code)
    if instrument is None or metric is None or profile is None:
        try:
            sync_stock_quote(session, code)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=404, detail=f"stock not found: {exc}") from exc
        instrument = session.get(Instrument, code)
        metric = session.get(StockMetric, code)
        profile = session.get(StockProfile, code)
    if instrument is None or metric is None or profile is None:
        raise HTTPException(status_code=404, detail="stock not found")
    if profile.status == "excluded":
        raise HTTPException(status_code=400, detail="stock excluded")

    existing = session.scalar(
        select(StockWatchlist).where(
            StockWatchlist.user_id == user.id,
            StockWatchlist.code == code,
        )
    )
    if existing is not None:
        return {"code": code, "saved": False}

    ensure_watchlist_slot(session, user)
    session.add(StockWatchlist(user_id=user.id, code=code))
    session.commit()
    return {"code": code, "saved": True}


@router.delete("/{code}", summary="移出个股自选")
def remove_stock_watchlist(
    code: str,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    row = session.scalar(
        select(StockWatchlist).where(
            StockWatchlist.user_id == user.id,
            StockWatchlist.code == code,
        )
    )
    if row is None:
        return {"code": code, "removed": False}
    session.delete(row)
    session.commit()
    return {"code": code, "removed": True}
