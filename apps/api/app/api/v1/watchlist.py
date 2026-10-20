from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.etfs import EtfSummary, _summaries
from app.db import get_session
from app.db.models import Instrument, User, WatchlistItem
from app.security import get_current_user

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


class WatchlistRequest(BaseModel):
    code: str = Field(pattern=r"^[0-9]{6}$")


class WatchlistAddResponse(BaseModel):
    code: str
    saved: bool


class WatchlistRemoveResponse(BaseModel):
    code: str
    removed: bool


def _active_etf(session: Session, code: str) -> Instrument:
    instrument = session.scalar(
        select(Instrument).where(
            Instrument.code == code,
            Instrument.type == "etf",
            Instrument.is_active.is_(True),
        )
    )
    if instrument is None:
        raise HTTPException(status_code=404, detail=f"unknown ETF {code}")
    return instrument


@router.get("", response_model=list[EtfSummary], summary="我的自选")
def list_watchlist(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[EtfSummary]:
    rows = session.scalars(
        select(WatchlistItem)
        .where(WatchlistItem.user_id == user.id)
        .order_by(WatchlistItem.created_at.desc())
    ).all()
    if not rows:
        return []
    summaries = {item.code: item for item in _summaries(session)}
    return [summaries[row.code] for row in rows if row.code in summaries]


@router.post("", response_model=WatchlistAddResponse, summary="加入自选")
def add_watchlist(
    payload: WatchlistRequest,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> WatchlistAddResponse:
    _active_etf(session, payload.code)
    existing = session.scalar(
        select(WatchlistItem).where(
            WatchlistItem.user_id == user.id,
            WatchlistItem.code == payload.code,
        )
    )
    if existing is not None:
        return WatchlistAddResponse(code=payload.code, saved=True)
    session.add(WatchlistItem(user_id=user.id, code=payload.code))
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
    return WatchlistAddResponse(code=payload.code, saved=True)


@router.delete("/{code}", response_model=WatchlistRemoveResponse, summary="移出自选")
def remove_watchlist(
    code: str,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> WatchlistRemoveResponse:
    row = session.scalar(
        select(WatchlistItem).where(
            WatchlistItem.user_id == user.id,
            WatchlistItem.code == code,
        )
    )
    if row is not None:
        session.delete(row)
        session.commit()
    return WatchlistRemoveResponse(code=code, removed=row is not None)
