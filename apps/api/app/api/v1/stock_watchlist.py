from __future__ import annotations

from typing import Annotated

from etl.stocks import sync_stock_quote
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.stocks import StockOut, _base_query, _out
from app.db import get_session
from app.db.models import (
    Instrument,
    StockMetric,
    StockProfile,
    StockWatchlist,
    User,
)
from app.security import get_current_user

router = APIRouter(prefix="/stock-watchlist", tags=["stock-watchlist"])


class WatchIn(BaseModel):
    code: str


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
